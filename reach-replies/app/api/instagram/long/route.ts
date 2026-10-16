import { fail, ok } from "@/lib/errors";
import { longView } from "@/lib/instagram";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function GET() {
  try { return ok(await longView()); } catch (e) { return fail(e, "instagram/long"); }
}
