import { hasDb, listSnapshots } from "@/lib/db";
import { copyFor, AppError } from "@/lib/errors";
import * as gmail from "@/lib/gmail";
import * as ig from "@/lib/instagram";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

// Build step 1: proves each connection works from the deployed function.
// Open /api/health after every setup change. Signed-in only.
async function probe(fn: () => Promise<unknown>): Promise<{ ok: boolean; detail: string }> {
  try {
    const v = await fn();
    return { ok: true, detail: typeof v === "string" ? v : JSON.stringify(v).slice(0, 200) };
  } catch (e) {
    return { ok: false, detail: e instanceof AppError ? copyFor(e.code) : "That didn't load." };
  }
}

export async function GET() {
  const [total, overview, growth, media, inbox, database] = await Promise.all([
    probe(async () => { const t = await ig.total(); return `${t.followers} followers, ${t.media} posts`; }),
    probe(async () => { const o = await ig.overview(); return `${o.rows.length} days, 30-day reach ${o.reach30}; latest ${JSON.stringify(o.rows[o.rows.length - 1])}`; }),
    probe(async () => { const r = await ig.growth(); return `${r.length} days; latest ${JSON.stringify(r[r.length - 1])}`; }),
    probe(async () => `${(await ig.reels()).length} reels in the last 7 days`),
    probe(async () => { const b = await gmail.check(); return `signed in; all mail = ${b.all}, drafts = ${b.drafts}`; }),
    probe(async () => (hasDb() ? `${(await listSnapshots()).length} banked days` : Promise.reject(new AppError("db_unavailable")))),
  ]);
  return Response.json({ instagram: { total, overview, growth, media }, gmail: inbox, database, drafting: { ok: !!process.env.ANTHROPIC_API_KEY, detail: process.env.ANTHROPIC_API_KEY ? "key set" : "ANTHROPIC_API_KEY not set" } });
}
