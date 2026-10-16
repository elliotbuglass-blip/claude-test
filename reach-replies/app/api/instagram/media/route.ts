import { fail, ok } from "@/lib/errors";
import { reels } from "@/lib/instagram";

export const dynamic = "force-dynamic";

export async function GET() {
  try { return ok(await reels()); } catch (e) { return fail(e, "instagram/media"); }
}
