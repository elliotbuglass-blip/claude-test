import { hasDb, upsertSnapshot } from "@/lib/db";
import { iso } from "@/lib/format";
import { refreshTokenIfDue, total } from "@/lib/instagram";
import { safeEqual } from "@/lib/auth";

export const dynamic = "force-dynamic";

// Daily at 06:17 UTC (vercel.json). Refreshes the Instagram token if it is
// within 10 days of expiry, then banks today's follower total. Idempotent.
export async function GET(req: Request) {
  const secret = process.env.CRON_SECRET;
  const auth = req.headers.get("authorization") ?? "";
  if (!secret || !safeEqual(auth, `Bearer ${secret}`)) return new Response("Unauthorised", { status: 401 });

  const out: Record<string, unknown> = {};
  try {
    out.token = await refreshTokenIfDue();
  } catch (e) {
    console.error("[cron] token refresh failed", e);
    out.token = "failed";
  }
  try {
    if (!hasDb()) throw new Error("DATABASE_URL not set");
    const t = await total();
    const day = iso(new Date());
    await upsertSnapshot(day, t.followers);
    out.snapshot = { day, total: t.followers };
  } catch (e) {
    console.error("[cron] snapshot failed", e);
    return Response.json({ ...out, snapshot: "failed" }, { status: 500 });
  }
  return Response.json(out);
}
