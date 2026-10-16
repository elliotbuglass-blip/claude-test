import { fail, ok } from "@/lib/errors";
import { total } from "@/lib/instagram";

export const dynamic = "force-dynamic";

export async function GET() {
  try { return ok(await total()); } catch (e) { return fail(e, "instagram/total"); }
}
