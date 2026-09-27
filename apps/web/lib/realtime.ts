// Realtime live-event client for the V2 data layer.
//
// Model: REST snapshot first, WebSocket incremental updates only.
//   - typed envelopes (v1) from /ws/live
//   - reconnect with exponential backoff (+jitter), capped at 30s
//   - app-level heartbeat (ping/pong) detects dead connections
//   - dedup by event_id, sequence protection per event type
//   - stale-event rejection (occurred_at older than 5 min)
//   - state: connecting -> live | reconnecting -> offline (REST fallback)
// Real-time is a progressive enhancement: a failed socket never breaks the UI.

export type RealtimeState = "connecting" | "live" | "reconnecting" | "degraded" | "offline";

export interface LiveEnvelope {
  v: number;
  event_id: string;
  event_type: string;
  aggregate_type: string;
  aggregate_id: string;
  sequence: number | null;
  occurred_at: string;
  observed_at: string;
  payload: Record<string, unknown>;
}

export interface RealtimeSnapshot {
  state: RealtimeState;
  lastEventAt: number | null;
  eventsReceived: number;
  lastError: string | null;
}

const isElectron = typeof window !== 'undefined' && (window as any).electronAPI;

async function getApiUrl(): Promise<string> {
  if (isElectron) {
    try {
      return await (window as any).electronAPI.getBackendUrl();
    } catch (error) {
      console.error('Failed to get backend URL from Electron:', error);
      return 'http://localhost:8000';
    }
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

let API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
let WS_URL = API_URL.replace(/^http/, "ws") + "/ws/live";

// Initialize URLs asynchronously if in Electron
if (isElectron) {
  getApiUrl().then(url => {
    API_URL = url;
    WS_URL = url.replace(/^http/, "ws") + "/ws/live";
  });
}

const BASE_BACKOFF_MS = 500;
const MAX_BACKOFF_MS = 30_000;
const MAX_RECONNECT_ATTEMPTS = 3;
const HEARTBEAT_MS = 25_000;
const TRAFFIC_TIMEOUT_MS = 45_000; // no server traffic -> degraded
const DEAD_TIMEOUT_MS = 60_000; // no server traffic -> force reconnect
const STALE_EVENT_MS = 5 * 60_000;
const SEEN_CAP = 400;

const num = (v: unknown): number | null => {
  const n = typeof v === "number" ? v : typeof v === "string" ? Number(v) : NaN;
  return Number.isFinite(n) ? n : null;
};

type EventHandler = (eventType: string, env: LiveEnvelope) => void;

class RealtimeClient {
  private ws: WebSocket | null = null;
  private state: RealtimeState = "connecting";
  private attempt = 0;
  private lastTrafficAt = 0;
  private eventsReceived = 0;
  private lastEventAt: number | null = null;
  private lastError: string | null = null;
  private seq: Map<string, number> = new Map();
  private seen: Set<string> = new Set();
  private keepalive: number | null = null;
  private retryTimer: number | null = null;
  private topics = new Set<string>();
  private entities = new Set<string>();
  private handlers = new Set<EventHandler>();
  private stateHandlers = new Set<(snap: RealtimeSnapshot) => void>();
  private destroyed = false;

  snapshot(): RealtimeSnapshot {
    return {
      state: this.state,
      lastEventAt: this.lastEventAt,
      eventsReceived: this.eventsReceived,
      lastError: this.lastError,
    };
  }

  onState(cb: (snap: RealtimeSnapshot) => void): () => void {
    this.stateHandlers.add(cb);
    return () => this.stateHandlers.delete(cb);
  }

  onEvent(cb: EventHandler): () => void {
    this.handlers.add(cb);
    return () => this.handlers.delete(cb);
  }

  /** Subscribe (idempotent). Call from browser-only code (useEffect). */
  subscribe(topics: string[], entities: string[] = []): void {
    const added = topics.filter((t) => !this.topics.has(t));
    topics.forEach((t) => this.topics.add(t));
    entities.forEach((e) => this.entities.add(e));
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      if (added.length > 0) this.sendSubscribe();
    }
    if (!this.ws) this.connect();
  }

  private async url(): Promise<string> {
    const apiUrl = await getApiUrl();
    const wsUrl = apiUrl.replace(/^http/, "ws") + "/ws/live";
    const q = new URLSearchParams();
    q.set("topics", Array.from(this.topics).join(","));
    q.set("entities", Array.from(this.entities).join(","));
    return `${wsUrl}?${q.toString()}`;
  }

  private sendSubscribe(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "subscribe",
          topics: Array.from(this.topics),
          entities: Array.from(this.entities),
        })
      );
    }
  }

  private async connect(): Promise<void> {
    if (typeof window === "undefined" || this.destroyed || this.ws) return;
    this.setState(this.attempt === 0 ? "connecting" : this.attempt <= MAX_RECONNECT_ATTEMPTS ? "reconnecting" : "offline");

    let ws: WebSocket;
    try {
      ws = new WebSocket(await this.url());
    } catch (err) {
      this.lastError = err instanceof Error ? err.message : "websocket unavailable";
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      this.attempt = 0;
      this.sendSubscribe();
      this.setState("live");
      if (this.keepalive == null) {
        this.keepalive = window.setInterval(() => this.heartbeat(), HEARTBEAT_MS);
      }
    };

    ws.onmessage = (m) => this.handleMessage(m);

    ws.onclose = () => {
      this.clearSocket();
      this.scheduleReconnect();
    };

    ws.onerror = () => {
      this.lastError = "websocket error";
      // onclose always follows onerror; let it drive the reconnect
    };
  }

  private handleMessage(m: MessageEvent): void {
    this.lastTrafficAt = Date.now();
    let msg: Record<string, unknown>;
    try {
      msg = JSON.parse(String(m.data));
    } catch {
      return;
    }
    const type = msg["type"];
    if (type === "ping") {
      this.ws?.send(JSON.stringify({ type: "pong" }));
      return;
    }
    if (type === "pong" || type === "hello" || type === "subscribed") return;
    if (typeof type !== "string" || !type.startsWith("price.") && !msg["event_type"]) return;
    this.dispatch(msg as unknown as LiveEnvelope);
  }

  private dispatch(env: LiveEnvelope): void {
    const eventType = env.event_type;
    if (!eventType) return;

    // 1) dedup by event id
    if (env.event_id && this.seen.has(env.event_id)) return;
    if (this.seen.size >= SEEN_CAP) this.seen.delete(this.seen.values().next().value as string);
    if (env.event_id) this.seen.add(env.event_id);

    // 2) sequence protection: never regress within a type
    if (env.sequence != null) {
      const prev = this.seq.get(eventType);
      if (prev != null && env.sequence <= prev) return;
      this.seq.set(eventType, env.sequence);
    }

    // 3) stale rejection: ancient events must not overwrite fresher UI
    const at = Date.parse(env.occurred_at ?? "");
    if (Number.isFinite(at) && Date.now() - at > STALE_EVENT_MS) return;

    this.eventsReceived += 1;
    this.lastEventAt = Date.now();
    for (const cb of Array.from(this.handlers)) cb(eventType, env);
  }

  private heartbeat(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    const idle = Date.now() - this.lastTrafficAt;
    if (idle > DEAD_TIMEOUT_MS) {
      this.lastError = "connection stalled";
      this.ws.close();
      return;
    }
    if (idle > TRAFFIC_TIMEOUT_MS) this.setState("degraded");
    else if (this.state === "degraded") this.setState("live");
    this.ws.send(JSON.stringify({ type: "ping" }));
  }

  private scheduleReconnect(): void {
    if (this.destroyed) return;
    if (this.retryTimer != null) window.clearTimeout(this.retryTimer);
    this.attempt += 1;
    const backoff =
      this.attempt > MAX_RECONNECT_ATTEMPTS
        ? MAX_BACKOFF_MS
        : Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * 2 ** (this.attempt - 1));
    const delay = backoff * (0.8 + Math.random() * 0.4);
    this.setState(this.attempt <= MAX_RECONNECT_ATTEMPTS ? "reconnecting" : "offline");
    this.retryTimer = window.setTimeout(() => {
      this.ws = null;
      this.connect();
    }, delay);
  }

  private clearSocket(): void {
    if (this.keepalive != null) {
      window.clearInterval(this.keepalive);
      this.keepalive = null;
    }
    this.ws = null;
  }

  private setState(state: RealtimeState): void {
    if (this.state === state) return;
    this.state = state;
    const snap = this.snapshot();
    for (const cb of Array.from(this.stateHandlers)) cb(snap);
  }
}

export const realtime = new RealtimeClient();

export { num };