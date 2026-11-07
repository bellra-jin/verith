// Local Next HTTP verification only. No IdP, database, or real AI endpoint is used.
import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { once } from "node:events";
import path from "node:path";

test("actual Next HTTP rejects legacy proxy calls and SSR without upstream requests", { timeout: 60000 }, async () => {
  let upstreamCalls = 0;
  const readPaths=[];
  const spy = createServer((request, response) => { readPaths.push(request.url); if(request.url!=="/api/auth/session") upstreamCalls++; response.writeHead(401,{"Content-Type":"application/json"}); response.end("{}"); });
  spy.listen(0, "127.0.0.1");
  await once(spy, "listening");
  const spyUrl = `http://127.0.0.1:${spy.address().port}`;
  const reserve = createServer();
  reserve.listen(0, "127.0.0.1");
  await once(reserve, "listening");
  const port = reserve.address().port;
  await new Promise((resolve) => reserve.close(resolve));
  const root = path.resolve(import.meta.dirname, "..");
  const child = spawn(process.execPath, [path.join(root, "node_modules/next/dist/bin/next"),
    "dev", "--hostname", "127.0.0.1", "--port", String(port)], {
    cwd: root, detached: true, stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1", BACKEND_URL: spyUrl,
      NEXT_PUBLIC_API_URL: spyUrl, AI_SUPERVISOR_URL: spyUrl },
  });
  let output = "";
  for (const stream of [child.stdout, child.stderr]) stream.on("data", (data) => { output = (output + data).slice(-6000); });
  const base = `http://127.0.0.1:${port}`;
  try {
    let ready = false;
    for (let attempt = 0; attempt < 60; attempt++) {
      if (child.exitCode !== null) throw new Error(`Next exited: ${output}`);
      try {
        if ((await fetch(base, { signal: AbortSignal.timeout(2000) })).ok) { ready = true; break; }
      } catch { /* wait only for this newly spawned local process */ }
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    assert.ok(ready, `Next did not become ready: ${output}`);
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
    if (child.exitCode === null) {
      process.kill(-child.pid, "SIGTERM");
      await Promise.race([once(child, "exit"), new Promise((resolve) => setTimeout(resolve, 3000))]);
      if (child.exitCode === null) process.kill(-child.pid, "SIGKILL");
    }
    await new Promise((resolve) => spy.close(resolve));
  }
});
