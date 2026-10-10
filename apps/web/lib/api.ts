// API client for PricePilot (Local FastAPI + Vercel Serverless Adaptive Support)
const isElectron = typeof window !== "undefined" && (window as any).electronAPI;

async function getApiUrl(): Promise<string> {
  if (isElectron) {
    try {
      return await (window as any).electronAPI.getBackendUrl();
    } catch {
      return "http://localhost:8000";
    }
  }

  if (
    process.env.NEXT_PUBLIC_API_URL &&
    !process.env.NEXT_PUBLIC_API_URL.includes("localhost") &&
    !process.env.NEXT_PUBLIC_API_URL.includes("127.0.0.1")
  ) {
    return process.env.NEXT_PUBLIC_API_URL;
  }

  if (typeof window !== "undefined") {
    // In browser, relative /api works everywhere: Vercel, Netlify, custom domain, and localhost
    return "/api";
  }

  return "http://127.0.0.1:8000";
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const url = await getApiUrl();
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const fullTarget = url === "/api" ? `/api${cleanPath}` : `${url}${cleanPath}`;

  const res = await fetch(fullTarget, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${body ? `: ${body.slice(0, 200)}` : ""}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const get = <T>(path: string) => api<T>(path);
export const post = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const del = <T>(path: string) => api<T>(path, { method: "DELETE" });

export { inr, inrCompact, inrPrecise, pct } from "./formatting";
