import { NextResponse, type NextRequest } from "next/server";
import { COOKIE, safeEqual, sessionValue } from "@/lib/auth";

// Everything is behind the password except the sign-in page, the cron route
// (which checks CRON_SECRET itself) and the icons the home screen needs.
const OPEN = ["/login", "/api/login", "/api/cron/", "/manifest.webmanifest", "/icon", "/apple-icon", "/favicon"];

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (OPEN.some((p) => pathname === p || pathname.startsWith(p))) return NextResponse.next();

  const password = process.env.APP_PASSWORD;
  if (!password) {
    // Fail closed: an unset password never means "open".
    return new NextResponse("APP_PASSWORD is not set. This app stays locked until it is.", { status: 503 });
  }
  const cookie = req.cookies.get(COOKIE)?.value ?? "";
  if (cookie && safeEqual(cookie, await sessionValue(password))) return NextResponse.next();

  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: { code: "unauthorised", message: "Sign in again to carry on." } }, { status: 401 });
  }
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
