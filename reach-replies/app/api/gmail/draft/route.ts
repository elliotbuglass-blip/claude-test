import { AppError, fail, ok } from "@/lib/errors";
import { saveDraft } from "@/lib/gmail";

export const dynamic = "force-dynamic";

// Saves a draft to Gmail. Never sends.
export async function POST(req: Request) {
  try {
    const body = (await req.json().catch(() => null)) as { threadId?: string; body?: string } | null;
    if (!body?.threadId || !body.body?.trim() || body.body.length > 20_000) throw new AppError("bad_request");
    return ok(await saveDraft(body.threadId, body.body));
  } catch (e) {
    return fail(e, "gmail/draft");
  }
}
