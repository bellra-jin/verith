import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import ts from 'typescript';
import {randomUUID} from 'node:crypto';
const root=path.resolve(import.meta.dirname, '../../..');
function load(relative,fetchSpy,options={}) {
 const source=ts.transpileModule(fs.readFileSync(path.join(root,relative),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const bundle={exports:{}};
 vm.runInNewContext(source,{module:bundle,exports:bundle.exports,Response,Request,Headers,URL,URLSearchParams,fetch:fetchSpy,process:{env:options.env ?? {}},require(name){
  if(name==='server-only')return {};
  if(name==='./session-backend')return {sessionBackendUrl:()=> options.base===undefined?'http://backend.unit':options.base};
  if(name==='./flow-demo-config'||name==='@/shared/server/flow-demo-config')return {flowDemoEnabled:()=>options.demo===true};
  if(name==='node:crypto')return {randomUUID};
  if(name==='next/headers')return {headers:async()=>new Headers()};
  if(name==='@/shared/server/session-proxy')return load('src/shared/server/session-proxy.ts',fetchSpy,options);
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


test('demo off/on bounded raw POST preserves malformed bytes and duplicate Cookie; query/alias never forwards',async()=>{
 const calls=[];const spy=async(url,init)=>{calls.push({url,init});return Response.json({request_id:randomUUID(),data:null,error:{code:'INPUT_INVALID',message:'fixed'}},{status:422});};
 const route='src/app/api/private/[...path]/route.ts';const context={params:Promise.resolve({path:['flow','synthetic-demo','runs']})};
 const off=load(route,spy);const request=()=>new Request('https://app.unit/api/private/flow/synthetic-demo/runs',{method:'POST',headers:{'Content-Type':'application/json',Cookie:'verith_session=A; verith_session=B',Origin:'https://app.unit','X-CSRF-Token':'fixed','Authorization':'spoof','X-User-ID':'other'},body:new Uint8Array([255,123,0])});
 assert.equal((await off.POST(request(),context)).status,403);assert.equal(calls.length,0);
 const on=load(route,spy,{demo:true});const response=await on.POST(request(),context);assert.equal(response.status,422);
 assert.deepEqual(Array.from(new Uint8Array(calls[0].init.body)),[255,123,0]);assert.equal(calls[0].init.headers.get('cookie'),'verith_session=A; verith_session=B');
 assert.equal(calls[0].init.headers.get('authorization'),null);assert.equal(calls[0].init.headers.get('x-user-id'),null);assert.equal(calls[0].init.headers.get('x-csrf-token'),'fixed');assert.equal(calls[0].init.headers.get('origin'),'https://app.unit');
 assert.equal(response.headers.get('cache-control'),'private, no-store');assert.equal(response.headers.get('vary'),'Cookie, Origin');
 const large=new Request('https://app.unit/api/private/flow/synthetic-demo/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:'x'.repeat(4097)});
 assert.equal((await on.POST(large,context)).status,422);assert.equal(calls.length,1);
 assert.equal((await on.POST(new Request('https://app.unit/api/private/flow/synthetic-demo/runs?owner=other',{method:'POST'}),context)).status,422);assert.equal(calls.length,1);
 const alias={params:Promise.resolve({path:['flow','synthetic-demo','runs','alias','extra']})};assert.equal((await on.GET(new Request('https://app.unit/api/private/flow/synthetic-demo/runs/alias/extra'),alias)).status,403);assert.equal(calls.length,1);
});
test('demo malformed/missing backend and transport failure keep safe envelope; legacy logout has no body',async()=>{
 const absent=load('src/shared/server/session-proxy.ts',()=>{throw Error('no upstream');},{demo:true,base:null});const response=await absent.sessionProxy(new Request('https://app.unit/x'),'/api/flow/synthetic-demo/runs/00000000-0000-4000-8000-000000000001');assert.equal(response.status,503);assert.equal((await response.json()).data,null);
 const url=load('src/shared/server/session-backend.ts',()=>{}, {env:{BACKEND_URL:'not a URL'}});assert.equal(url.sessionBackendUrl(),null);
 let body='untouched';const auth=load('src/app/api/auth/[action]/route.ts',async(target,init)=>{body=init.body;return new Response(null,{status:204});});await auth.POST(new Request('https://app.unit/api/auth/logout',{method:'POST',body:'ignored'}),{params:Promise.resolve({action:'logout'})});assert.equal(body,undefined);
});


test('real server flag accepts only exact true in a synthetic environment',()=>{
 for(const [env,expected] of [[{},false],[{FLOW_SYNTHETIC_DEMO_ENABLED:'true'},true],[{FLOW_SYNTHETIC_DEMO_ENABLED:'false'},false],[{FLOW_SYNTHETIC_DEMO_ENABLED:'TRUE'},false],[{FLOW_SYNTHETIC_DEMO_ENABLED:'1'},false],[{FLOW_SYNTHETIC_DEMO_ENABLED:'true '},false]]){
  const config=load('src/shared/server/flow-demo-config.ts',()=>{throw Error('flag must not fetch');},{env});assert.equal(config.flowDemoEnabled(),expected);
 }
});
test('demo valid fixed upstream transport rejection returns safe private envelope',async()=>{
 let calls=0;const api=load('src/shared/server/session-proxy.ts',async()=>{calls++;throw Error('synthetic-sensitive-transport');},{demo:true,base:'http://backend.unit'});
 const response=await api.sessionProxy(new Request('https://app.unit/api/private/flow/synthetic-demo/runs/00000000-0000-4000-8000-000000000001'),'/api/flow/synthetic-demo/runs/00000000-0000-4000-8000-000000000001');
 assert.equal(calls,1);assert.equal(response.status,503);const body=await response.json();assert.equal(body.data,null);assert.equal(body.error.code,'SERVICE_UNAVAILABLE');assert.doesNotMatch(JSON.stringify(body),/synthetic-sensitive-transport/);assert.equal(response.headers.get('vary'),'Cookie, Origin');
});
