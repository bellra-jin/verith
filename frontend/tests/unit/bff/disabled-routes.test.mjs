import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { createRequire } from "node:module";
import ts from "typescript";

const root = path.resolve(import.meta.dirname, '../../..');
const loadCommonJs = createRequire(import.meta.url);
const routeFiles = [
  "src/app/api/supervisor/analyze/route.ts",
  "src/app/api/flow/reports/route.ts",
  "src/app/api/fundamental/reports/route.ts",
  "src/app/api/technical/reports/route.ts",
  "src/app/api/industry/reports/route.ts",
  "src/app/api/news/reports/route.ts",
  "src/app/api/fundamental/reports/[reportId]/html/route.ts",
  "src/app/api/industry/reports/[reportId]/html/route.ts",
];

function load(relative, fetchSpy) {
  const filename = path.join(root, relative);
  const source = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const bundle = { exports: {} };
  vm.runInNewContext(source, {
    module: bundle, exports: bundle.exports, Response, Request, URL, fetch: fetchSpy,
    process: { env: { AI_SUPERVISOR_URL: "http://upstream.invalid", BACKEND_URL: "http://upstream.invalid" } },
    require(name) {
      if (name === "@/shared/server/disabled-feature") return load("src/shared/server/disabled-feature.ts", fetchSpy);
      if (name === "next/server") return loadCommonJs("next/server");
      throw new Error(`Unexpected dependency: ${name}`);
    },
  }, { filename });
  return bundle.exports;
}

for (const route of routeFiles) {
  test(`${route}: every method rejects before upstream, independent of unverified identity`, async () => {
    let upstreamCalls = 0;
    const fetchSpy = async () => { upstreamCalls++; throw new Error("Upstream must not run"); };
    const handlers = load(route, fetchSpy);
    for (const method of ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]) {
      for (const headers of [{}, { Cookie: "session=expired" }, { Cookie: "session=revoked" },
        { "X-User-ID": "spoofed", Authorization: "Bearer spoofed" }, { Cookie: "session=opaque-unverified" }]) {
        const request = new Request("http://unit/api/forbidden", {
          method, headers,
          ...(method === "GET" || method === "HEAD" ? {} : { body: "not-json" }),
        });
        const response = await handlers[method](request, { params: Promise.resolve({ reportId: "other-user" }) });
        assert.equal(response.status, 403);
        assert.equal(response.headers.get("cache-control"), "private, no-store");
        assert.equal((await response.json()).error.code, "FEATURE_UNAVAILABLE");
      }
    }
    assert.equal(upstreamCalls, 0);
  });
}

test("client analysis entry cannot call an upstream or return demo-success", async () => {
  let upstreamCalls = 0;
  const client = load("src/features/supervisor/api/analyze.ts", async () => { upstreamCalls++; });
  await assert.rejects(client.analyzeQuery("synthetic query"));
  assert.equal(upstreamCalls, 0);
});

test("SSR reports are rewritten before page data access without external calls", () => {
  const { proxy, config } = load("src/proxy.ts", () => { throw new Error("unexpected upstream"); });
  assert.deepEqual(Array.from(config.matcher), ["/reports/:path*", "/flow/demo/:path*"]);
  const response = proxy({url:"http://unit/reports/technical/demo",nextUrl:{pathname:"/reports/technical/demo"}});
  assert.equal(response.headers.get("x-middleware-rewrite"), "http://unit/unavailable");
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  const flow = proxy({url:"http://unit/reports/flow/synthetic",nextUrl:{pathname:"/reports/flow/synthetic"}});
  assert.equal(flow.headers.get("x-middleware-next"), "1");
});
