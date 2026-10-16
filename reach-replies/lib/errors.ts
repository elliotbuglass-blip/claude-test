// Mapped error codes. The client renders `message` directly, so every message
// is a plain sentence Elliot reads — never an upstream body or a status code.

export type ErrorCode =
  | "ig_token_expired"
  | "ig_rate_limited"
  | "ig_empty"
  | "ig_not_configured"
  | "gmail_auth"
  | "gmail_unreachable"
  | "gmail_not_found"
  | "db_unavailable"
  | "bad_request"
  | "unauthorised"
  | "unknown";

const COPY: Record<ErrorCode, string> = {
  ig_token_expired: "The Instagram connection has lapsed. Re-authorise it in settings.",
  ig_rate_limited: "Instagram is rate-limiting us. Try again in a few minutes.",
  ig_empty: "No data came back from Instagram for that period.",
  ig_not_configured: "Instagram isn't set up yet. Add the Instagram keys in Vercel.",
  gmail_auth: "The Gmail connection isn't working. Check the app password.",
  gmail_unreachable: "Couldn't reach Gmail. Try again in a moment.",
  gmail_not_found: "That thread couldn't be found in Gmail.",
  db_unavailable: "The database isn't connected, so history can't be recorded.",
  bad_request: "That request was missing something.",
  unauthorised: "Sign in again to carry on.",
  unknown: "That didn't load.",
};

export class AppError extends Error {
  constructor(public code: ErrorCode, public detail?: unknown) {
    super(COPY[code]);
  }
}

export function copyFor(code: ErrorCode): string {
  return COPY[code];
}

const STATUS: Partial<Record<ErrorCode, number>> = {
  ig_rate_limited: 429,
  bad_request: 400,
  unauthorised: 401,
  gmail_not_found: 404,
};

export function ok<T>(data: T, init?: ResponseInit): Response {
  return Response.json({ data }, init);
}

/** Logs the real cause server-side and returns only the mapped code and sentence. */
export function fail(e: unknown, where: string): Response {
  const err = e instanceof AppError ? e : new AppError("unknown", e);
  console.error(`[${where}] ${err.code}`, err.detail ?? e);
  return Response.json(
    { error: { code: err.code, message: err.message } },
    { status: STATUS[err.code] ?? 502 },
  );
}
