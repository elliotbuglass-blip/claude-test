import { fail, ok } from "@/lib/errors";
import { thread } from "@/lib/gmail";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  try { return ok(await thread((await params).id)); } catch (e) { return fail(e, "gmail/thread"); }
}
