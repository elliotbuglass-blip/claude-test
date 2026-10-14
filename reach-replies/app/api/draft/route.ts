import { draftFollowUp } from "@/lib/anthropic";
import { AppError, fail, ok } from "@/lib/errors";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function POST(req: Request) {
  try {
    const body = (await req.json().catch(() => null)) as { transcript?: string; workingDays?: number } | null;
    if (!body?.transcript?.trim()) throw new AppError("bad_request");
    const wd = Math.max(0, Math.min(365, Math.round(Number(body.workingDays) || 0)));
    return ok({ text: await draftFollowUp(body.transcript, wd) });
  } catch (e) {
    return fail(e, "draft");
  }
}
