import { cached } from "@/lib/db";
import { fail, ok } from "@/lib/errors";
import { followUps } from "@/lib/gmail";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function GET() {
  try { return ok(await cached("gmail:followups", 60, () => followUps())); } catch (e) { return fail(e, "gmail/followups"); }
}
