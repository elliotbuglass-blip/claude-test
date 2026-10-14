// Follow-up drafting. The transcript sent here is the one place thread
// contents leave the app. Keep every STYLE rule — see docs/01-product.md.

import Anthropic from "@anthropic-ai/sdk";
import { AppError } from "./errors";

export const STYLE = [
  "You are drafting a short follow-up email for Elliot Cameron, a Newcastle-based content creator and part-time model (@elliotcameron._) working across menswear, automotive and lifestyle.",
  "He is chasing a conversation that has gone quiet. Write the follow-up he would send.",
  "",
  "Rules, which matter more than anything else:",
  "- Plain, natural English. No marketing language. Nothing that sounds like a pitch deck.",
  "- Short: three or four sentences at most. Cut anything not earning its place.",
  "- Never apologise for following up and never grovel. He is not asking for a favour.",
  "- Never invent facts, figures, dates or commitments that are not in the thread.",
  "- Do not restate the thread back at them.",
  "- Give them an easy way to reply, or one specific small next step.",
  "- Sign off 'Cheers,' then 'Elliot'.",
  "- Output the email body only. No subject line, no preamble, no notes.",
].join("\n");

const MODEL = "claude-opus-5-5";
const MAX_TRANSCRIPT = 6 * 1_900 + 2_000;

let client: Anthropic | null = null;

export async function draftFollowUp(transcript: string, workingDays: number): Promise<string> {
  if (!process.env.ANTHROPIC_API_KEY) throw new AppError("draft_failed", "ANTHROPIC_API_KEY not set");
  client ??= new Anthropic();

  const prompt =
    `It has been ${workingDays} working days since Elliot's last message.\n\n` +
    `The thread so far:\n\n${transcript.slice(0, MAX_TRANSCRIPT)}`;

  try {
    const res = await client.beta.messages.create({
      model: MODEL,
      max_tokens: 16_000,
      system: STYLE,
      output_config: { effort: "medium" },
      // Server-side fallback if a safety classifier declines (e.g. a false positive).
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      messages: [{ role: "user", content: prompt }],
    });
    if (res.stop_reason === "refusal") throw new AppError("draft_failed", res.stop_details);
    const text = res.content.flatMap((b) => (b.type === "text" ? [b.text] : [])).join("").trim();
    if (!text) throw new AppError("draft_failed", "empty response");
    return text;
  } catch (e) {
    if (e instanceof AppError) throw e;
    throw new AppError("draft_failed", e);
  }
}
