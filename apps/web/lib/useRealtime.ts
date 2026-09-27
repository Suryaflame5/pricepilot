"use client";

import { useEffect, useRef, useState } from "react";
import { realtime, type LiveEnvelope, type RealtimeSnapshot } from "@/lib/realtime";

/** Reactive mirror of the realtime client state (for status pills and fallback logic). */
export function useRealtimeState(): RealtimeSnapshot {
  const [snap, setSnap] = useState<RealtimeSnapshot>(() => realtime.snapshot());
  useEffect(() => realtime.onState(setSnap), []);
  return snap;
}

/**
 * Subscribe to live envelopes. Filters: event types and aggregate ids
 * (listing/variant uuids). Handler receives every dispatched envelope.
 * Idempotent across mounts; re-subscribes on filter change.
 */
export function useRealtimeSubscription(
  topics: string[],
  entities: string[],
  handler?: (eventType: string, env: LiveEnvelope) => void
): void {
  const ref = useRef(handler);
  ref.current = handler;
  const key = topics.join(",") + "|" + entities.join(",");

  useEffect(() => {
    const off = realtime.onEvent((type, env) => ref.current?.(type, env));
    realtime.subscribe(topics, entities);
    return off;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}