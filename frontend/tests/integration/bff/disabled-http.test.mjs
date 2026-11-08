// Local Next HTTP verification only. No IdP, database, or real AI endpoint is used.
import test from "node:test";
import assert from "node:assert/strict";
import {ownedHTTP} from "../../helpers/safe-http.mjs";

test("actual Next HTTP rejects legacy proxy calls and SSR without upstream requests", { timeout: 120000 }, async () => {
  let upstreamCalls = 0;
  const readPaths=[];
  const scope = await ownedHTTP((request, response) => { readPaths.push(request.url); if(request.url!=="/api/auth/session") upstreamCalls++; response.writeHead(401,{"Content-Type":"application/json"}); response.end("{}"); });
  const base=scope.base;
  try {
    const paths = ["/api/supervisor/analyze", "/api/flow/reports", "/api/fundamental/reports",
      "/api/technical/reports", "/api/industry/reports", "/api/news/reports",
      "/api/fundamental/reports/synthetic/html", "/api/industry/reports/synthetic/html"];
    for (const target of paths) {
      for (const headers of [{}, { Cookie: "session=expired" }, { Cookie: "session=revoked" },
        { "X-User-ID": "spoofed", Authorization: "Bearer spoofed" }, { Cookie: "session=opaque-unverified" }]) {
        const response = await fetch(base + target, { method: target.endsWith("/html") ? "GET" : "POST",
          headers, ...(target.endsWith("/html") ? {} : { body: "not-json" }) });
        assert.equal(response.status, 403, `${target}: ${await response.text()}`);
        assert.equal(response.headers.get("cache-control"), "private, no-store");
      }
    }
    for (const target of ["/research", "/reports/flow/12345678-1234-1234-1234-123456789012", "/reports/technical/demo"]) {
      const response = await fetch(base + target);
      assert.equal(response.status, 200);
      assert.match(await response.text(), /준비 중/);
    }
    assert.equal(upstreamCalls, 0, "Forbidden upstream analysis/data request was made");
    assert.ok(readPaths.every(path=>path==="/api/auth/session"));
  } finally {
    await scope.close();
  }
});
