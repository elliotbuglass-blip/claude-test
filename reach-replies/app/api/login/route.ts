import { NextResponse } from "next/server";
import { COOKIE, MAX_AGE, safeEqual, sessionValue } from "@/lib/auth";

export async function POST(req: Request) {
  const form = await req.formData().catch(() => null);
  const given = String(form?.get("password") ?? "");
  const password = process.env.APP_PASSWORD;
  const url = new URL(req.url);

  if (!password || !given || !safeEqual(await sessionValue(given), await sessionValue(password))) {
    await new Promise((r) => setTimeout(r, 800)); // slow down guessing
    return NextResponse.redirect(new URL("/login?wrong=1", url), { status: 303 });
  }
  const res = NextResponse.redirect(new URL("/", url), { status: 303 });
  res.cookies.set(COOKIE, await sessionValue(password), {
    httpOnly: true, secure: url.protocol === "https:", sameSite: "lax", path: "/", maxAge: MAX_AGE,
  });
  return res;
}
