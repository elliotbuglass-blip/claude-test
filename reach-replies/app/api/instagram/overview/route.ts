import { fail, ok } from "@/lib/errors";
import { overview } from "@/lib/instagram";

export const dynamic = "force-dynamic";

export async function GET() {
  try { return ok(await overview()); } catch (e) { return fail(e, "instagram/overview"); }
}
