import { fail, ok } from "@/lib/errors";
import { growth } from "@/lib/instagram";

export const dynamic = "force-dynamic";

export async function GET() {
  try { return ok(await growth()); } catch (e) { return fail(e, "instagram/growth"); }
}
