// Single-password gate. The cookie holds a hash derived from APP_PASSWORD, so
// changing the password signs every device out. Works in the edge runtime.

export const COOKIE = "rr_session";
export const MAX_AGE = 60 * 60 * 24 * 180; // 180 days — the home-screen app stays signed in

export async function sessionValue(password: string): Promise<string> {
  const data = new TextEncoder().encode(`reach-replies:v1:${password}`);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash), (b) => b.toString(16).padStart(2, "0")).join("");
}

export function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
