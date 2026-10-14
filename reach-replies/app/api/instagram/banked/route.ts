import { hasDb, listSnapshots } from "@/lib/db";
import { AppError, fail, ok } from "@/lib/errors";

export const dynamic = "force-dynamic";

// Follower totals this app has recorded itself, one per day.
export async function GET() {
  try {
    if (!hasDb()) throw new AppError("db_unavailable");
    return ok(await listSnapshots());
  } catch (e) {
    return fail(e instanceof AppError ? e : new AppError("db_unavailable", e), "instagram/banked");
  }
}
