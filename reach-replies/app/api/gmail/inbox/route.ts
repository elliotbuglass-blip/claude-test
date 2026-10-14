import { cached } from "@/lib/db";
import { fail, ok } from "@/lib/errors";
import { inbox } from "@/lib/gmail";

export const dynamic = "force-dynamic";

export async function GET() {
  try { return ok(await cached("gmail:inbox", 60, inbox)); } catch (e) { return fail(e, "gmail/inbox"); }
}
