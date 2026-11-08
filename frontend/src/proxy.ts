import { NextResponse, type NextRequest } from "next/server";

// Closed during provider/session/owner setup; this is not an authentication check.
export function proxy(request: NextRequest) {
  const response = (request.nextUrl.pathname.startsWith("/reports/flow/") || request.nextUrl.pathname==="/flow/demo" || request.nextUrl.pathname.startsWith("/flow/demo/"))
    ? NextResponse.next()
    : NextResponse.rewrite(new URL("/unavailable", request.url));
  response.headers.set("Cache-Control", "private, no-store");
  response.headers.set("Vary", "Cookie, Origin");
  return response;
}

export const config = { matcher: ["/reports/:path*", "/flow/demo/:path*"] };
