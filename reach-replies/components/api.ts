"use client";

import { useCallback, useEffect, useState } from "react";

export interface ApiError { code: string; message: string }

export type Load<T> =
  | { status: "loading" }
  | { status: "ok"; data: T }
  | { status: "error"; error: ApiError };

const FALLBACK: ApiError = { code: "unknown", message: "That didn't load." };

/** Every route returns { data } or { error: { code, message } }. Nothing fails to an empty state. */
export async function api<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store", ...init });
  } catch {
    throw { code: "offline", message: "No connection. Check your signal and try again." } satisfies ApiError;
  }
  if (res.status === 401) {
    window.location.href = "/login";
    throw { code: "unauthorised", message: "Sign in again to carry on." } satisfies ApiError;
  }
  const body = (await res.json().catch(() => null)) as { data?: T; error?: ApiError } | null;
  if (body && "data" in body && res.ok) return body.data as T;
  throw body?.error ?? FALLBACK;
}

export function useApi<T>(url: string, refreshMs?: number): [Load<T>, () => void] {
  const [state, setState] = useState<Load<T>>({ status: "loading" });
  const load = useCallback(() => {
    api<T>(url).then(
      (data) => setState({ status: "ok", data }),
      (error: ApiError) => setState((s) => (s.status === "ok" && refreshMs ? s : { status: "error", error: error ?? FALLBACK })),
    );
  }, [url, refreshMs]);

  useEffect(() => {
    load();
    if (!refreshMs) return;
    const t = setInterval(load, refreshMs);
    return () => clearInterval(t);
  }, [load, refreshMs]);

  return [state, load];
}
