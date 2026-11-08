import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import ts from 'typescript';
const root=path.resolve(import.meta.dirname, '../../..');
function load(relative,fetchSpy) {
 const source=ts.transpileModule(fs.readFileSync(path.join(root,relative),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const bundle={exports:{}};
 vm.runInNewContext(source,{module:bundle,exports:bundle.exports,Response,Request,Headers,URL,URLSearchParams,fetch:fetchSpy,require(name){
  if(name==='server-only')return {};
  if(name==='./session-backend')return {sessionBackendUrl:()=> 'http://backend.unit'};
  if(name==='@/shared/server/session-proxy')return load('src/shared/server/session-proxy.ts',fetchSpy);
  throw new Error('Unexpected import '+name);
 }});
 return bundle.exports;
}
test('protected BFF forwards cookie/Origin/CSRF to fixed backend, omits owner/spoofed headers and never caches',async()=>{
 const seen=[];
 const handlers=load('src/app/api/private/[...path]/route.ts',async(url,init)=>{
  seen.push({url,init});
  return Response.json({detail:{code:'AUTH_REQUIRED'}},{status:401});
 });
 const response=await handlers.GET(new Request('https://app.unit/api/private/reports/archive?owner_user_id=other&agent_type=flow',{headers:{Cookie:'verith_session=revoked',Authorization:'Bearer spoofed','X-User-ID':'other'}}),{params:Promise.resolve({path:['reports','archive']})});
 assert.equal(response.status,401);
 assert.equal(response.headers.get('cache-control'),'private, no-store');
 assert.equal(seen[0].url,'http://backend.unit/api/reports/archive?agent_type=flow');
 assert.equal(seen[0].init.cache,'no-store');
 assert.equal(seen[0].init.headers.get('cookie'),'verith_session=revoked');
 assert.equal(seen[0].init.headers.get('authorization'),null);
 assert.equal(seen[0].init.headers.get('x-user-id'),null);
 const deletion=await handlers.DELETE(new Request('https://app.unit/api/private/flow/reports/12345678-1234-1234-1234-123456789012',{method:'DELETE',headers:{Cookie:'verith_session=synthetic','X-CSRF-Token':'synchronizer',Origin:'https://app.unit'}}),{params:Promise.resolve({path:['flow','reports','12345678-1234-1234-1234-123456789012']})});
 assert.equal(deletion.status,401);
 assert.equal(seen[1].init.headers.get('origin'),'https://app.unit');
 assert.equal(seen[1].init.headers.get('x-csrf-token'),'synchronizer');
 for(const value of [['flow','reports'],['supervisor','analyze'],['..','auth','login'],['technical','reports']]){
  assert.equal((await handlers.DELETE(new Request('https://app.unit/api/private/forbidden',{method:'DELETE'}),{params:Promise.resolve({path:value})})).status,403);
 }
 assert.equal(seen.length,2);
 for (const cookie of ['verith_session=expired; verith_session=valid-B','verith_session=valid-B; verith_session=expired']) {
  const denied=await handlers.GET(new Request('https://app.unit/api/private/reports/archive',{headers:{Cookie:cookie}}),{params:Promise.resolve({path:['reports','archive']})});
  assert.equal(denied.status,401);
  assert.equal(seen.at(-1).init.headers.get('cookie'),cookie);
 }
 assert.equal(seen.length,4);
});
test('auth BFF forwards only allowlisted actions and propagates HttpOnly cookie + redirect',async()=>{
 const seen=[];
 const handlers=load('src/app/api/auth/[action]/route.ts',async(url,init)=>{
  seen.push({url,init});
  return new Response(null,{status:303,headers:{Location:'https://accounts.google.com/o/oauth2/v2/auth','Set-Cookie':'verith_login=synthetic; HttpOnly; Secure; SameSite=Lax; Path=/api/auth/callback'}});
 });
 const response=await handlers.GET(new Request('https://app.unit/api/auth/login?next=https://evil.unit'),{params:Promise.resolve({action:'login'})});
 assert.equal(seen[0].url,'http://backend.unit/api/auth/login');
 assert.equal(response.status,303);
 assert.match(response.headers.get('set-cookie'),/HttpOnly/);
 assert.match(response.headers.get('location'),/^https:\/\/accounts.google.com/);
 assert.equal((await handlers.POST(new Request('https://app.unit/api/auth/session',{method:'POST'}),{params:Promise.resolve({action:'session'})})).status,404);
 assert.equal(seen.length,1);
});
