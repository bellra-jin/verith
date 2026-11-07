import { NextResponse, type NextRequest } from "next/server";

// Closed during provider/session/owner setup; this is not an authentication check.
export function proxy(request: NextRequest) {
  const response = request.nextUrl.pathname.startsWith("/reports/flow/")
    ? NextResponse.next()
    : NextResponse.rewrite(new URL("/unavailable", request.url));
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export const config = { matcher: ["/reports/:path*"] };
