// CF-002: do not parse payloads, trust identity headers, or call an upstream here.
export function unavailableFeature(): Response {
  return Response.json(
    { error: { code: "FEATURE_UNAVAILABLE", message: "현재 사용할 수 없는 기능입니다." } },
    { status: 403, headers: { "Cache-Control": "private, no-store", Vary: "Cookie, Authorization, Origin" } },
  );
}
