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
 vm.runInNewContext(source,{module:bundle,exports:bundle.exports,Response,Request,Headers,URL,URLSearchParams,TextEncoder,AbortSignal:options.AbortSignal ?? AbortSignal,fetch:fetchSpy,process:{env:options.env ?? {}},require(name){
  if(name==='server-only')return {};
  if(name==='./session-backend')return {sessionBackendUrl:()=> options.base===undefined?'http://backend.unit':options.base};
  if(name==='./fundamental-analysis-config'||name==='@/shared/server/fundamental-analysis-config')return load('src/shared/server/fundamental-analysis-config.ts',fetchSpy,options);
  if(name==='./flow-analysis-config'||name==='@/shared/server/flow-analysis-config')return load('src/shared/server/flow-analysis-config.ts',fetchSpy,options);
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

test('analysis gate uses actual exact environment value and strict fixed forwarding',async()=>{
 for(const value of [undefined,'false','TRUE','1','true']){
  const config=load('src/shared/server/flow-analysis-config.ts',()=>{}, {env:value===undefined?{}:{FLOW_ANALYSIS_ENABLED:value}});
  assert.equal(config.flowAnalysisEnabled(),value==='true');
 }
 const seen=[];
 const proxy=load('src/shared/server/session-proxy.ts',async(url,options)=>{seen.push({url,options});return Response.json({synthetic:true});},{env:{FLOW_ANALYSIS_ENABLED:'true'}});
 const body=JSON.stringify({ticker:'005930',question:'합성',as_of:'2026-11-08T00:00:00Z',idempotency_key:'fixed',allow_analysis:true});
 const headers={'content-type':'application/json',cookie:'verith_session=synthetic',origin:'https://app.unit','x-csrf-token':'synthetic',authorization:'forbidden','x-flow-service-token':'forbidden','x-user-id':'forbidden'};
 const result=await proxy.sessionProxy(new Request('https://app.unit/api/private/flow/analyses',{method:'POST',headers,body}),'/api/flow/analyses');
 assert.equal(result.status,200);assert.equal(result.headers.get('cache-control'),'private, no-store');assert.equal(seen.length,1);
 assert.equal(seen[0].url,'http://backend.unit/api/flow/analyses');assert.equal(seen[0].options.redirect,'manual');assert.ok(seen[0].options.signal instanceof AbortSignal);
 for(const name of ['authorization','x-user-id','x-flow-service-token'])assert.equal(seen[0].options.headers.get(name),null);
 assert.equal(seen[0].options.headers.get('cookie'),'verith_session=synthetic');
 for(const size of [4096,4097]){
  const request=new Request('https://app.unit/api/private/flow/analyses',{method:'POST',headers,body:body+' '.repeat(size-new TextEncoder().encode(body).length)});
  assert.equal((await proxy.sessionProxy(request,'/api/flow/analyses')).status,size===4096?200:422);
 }
});
test('analysis single wall deadline bounds unfinished body and upstream response',async()=>{
 for(const slowBody of [true,false]){
  const deadline=new AbortController(),seen=[],timeouts=[];
  const proxy=load('src/shared/server/session-proxy.ts',async(url,options)=>{seen.push(options);return new Response(new ReadableStream({start(c){c.enqueue(new TextEncoder().encode('{'));}}));},{env:{FLOW_ANALYSIS_ENABLED:'true'},AbortSignal:{timeout(value){timeouts.push(value);return deadline.signal;}}});
  const body=slowBody?new ReadableStream({start(c){c.enqueue(new TextEncoder().encode('{'));}}):'{}';
  const request=new Request('https://app.unit/api/private/flow/analyses',{method:'POST',headers:{'content-type':'application/json'},body,duplex:'half'});
  const operation=proxy.sessionProxy(request,'/api/flow/analyses');setImmediate(()=>deadline.abort());
  const result=await operation;assert.equal(result.status,slowBody?422:503);assert.deepEqual(timeouts,[130000]);assert.equal(seen.length,slowBody?0:1);
  if(!slowBody)assert.equal(seen[0].signal,deadline.signal);
 }
});

test('Fundamental exact four field request and owned readers/delete retain boundary and 70s deadline',async()=>{
 const seen=[];const signals=[];const options={env:{FUNDAMENTAL_ANALYSIS_ENABLED:'true'},AbortSignal:{timeout(ms){signals.push(ms);return new AbortController().signal;}}};
 const route=load('src/app/api/private/[...path]/route.ts',async(url,init)=>{seen.push({url,init});return init.method==='DELETE'?new Response(null,{status:204}):Response.json({safe:true});},options);
 const id=randomUUID(),ctx=path=>({params:Promise.resolve({path:path.split('/')})});
 const response=await route.POST(new Request('https://app.unit/api/private/fundamental/analyses',{method:'POST',headers:{'content-type':'application/json',Cookie:'verith_session=a; verith_session=b',Origin:'https://app.unit','X-CSRF-Token':'fixed','X-Fundamental-Service-Token':'not-forwarded'},body:'{}'}),ctx('fundamental/analyses'));
 assert.equal(response.status,200);assert.equal(seen[0].url,'http://backend.unit/api/fundamental/analyses');assert.equal(seen[0].init.headers.get('cookie'),'verith_session=a; verith_session=b');assert.equal(seen[0].init.headers.get('x-fundamental-service-token'),null);assert.equal(signals[0],70000);
 assert.equal((await route.GET(new Request('https://app.unit/api/private/fundamental/reports?limit=20&offset=0'),ctx('fundamental/reports'))).status,200);
 assert.equal(seen.at(-1).url,'http://backend.unit/api/fundamental/reports?limit=20&offset=0');
 assert.equal((await route.DELETE(new Request('https://app.unit/api/private/fundamental/reports/'+id,{method:'DELETE'}),ctx('fundamental/reports/'+id))).status,204);
 const count=seen.length;
 for(const [method,path] of [['POST','fundamental/reports'],['POST','fundamental/reports/save'],['DELETE','fundamental/reports'],['GET','fundamental/reports/'+id+'/html']])assert.equal((await route[method](new Request('https://app.unit/api/private/'+path,{method}),ctx(path))).status,422);
 assert.equal(seen.length,count);
 for(const v of ['', 'TRUE','1','false']){const config=load('src/shared/server/fundamental-analysis-config.ts',()=>{}, {env:{FUNDAMENTAL_ANALYSIS_ENABLED:v}});assert.equal(config.fundamentalAnalysisEnabled(),false);}
});


test('CF020 exact planning POST forwards only safe headers and uses a twelve-second budget',async()=>{
 const seen=[],timeouts=[];const handlers=load('src/app/api/private/[...path]/route.ts',async(url,init)=>{seen.push([url,init]);return Response.json({request_id:randomUUID(),data:null,error:null});},{env:{FLOW_ANALYSIS_ENABLED:'true'},AbortSignal:{timeout(ms){timeouts.push(ms);return new AbortController().signal;}}});
 const response=await handlers.POST(new Request('http://app.unit/api/private/flow/plans',{method:'POST',headers:{'content-type':'application/json',cookie:'synthetic-cookie',origin:'http://app.unit','x-csrf-token':'synthetic-csrf','x-flow-service-token':'must-not-forward','x-user-id':'spoof'},body:'{"query":"합성 수급"}'}),{params:Promise.resolve({path:['flow','plans']})});
 assert.equal(response.status,200);assert.equal(seen.length,1);assert.equal(seen[0][0],'http://backend.unit/api/flow/plans');assert.deepEqual(timeouts,[12000]);
 assert.equal(seen[0][1].headers.get('cookie'),'synthetic-cookie');assert.equal(seen[0][1].headers.get('x-csrf-token'),'synthetic-csrf');assert.equal(seen[0][1].headers.get('x-flow-service-token'),null);assert.equal(seen[0][1].headers.get('x-user-id'),null);assert.equal(seen[0][1].redirect,'manual');assert.match(response.headers.get('cache-control'),/no-store/);
 for(const [method,path,search] of [['GET',['flow','plans'],''],['POST',['flow','plans','extra'],''],['POST',['flow','plans'],'?x=1']]){
  const bad=await handlers[method](new Request('http://app.unit/api/private/'+path.join('/')+search,{method}),{params:Promise.resolve({path})});assert.equal(bad.status,422);
 }
 assert.equal(seen.length,1);
});
test('CF020 raw body limit and decoded response limit fail closed without a redirect',async()=>{
 let calls=0;const proxy=load('src/shared/server/session-proxy.ts',async()=>{calls++;return new Response('x'.repeat(16385));},{env:{FLOW_ANALYSIS_ENABLED:'true'}});
 const request=body=>new Request('http://app.unit/api/private/flow/plans',{method:'POST',headers:{'content-type':'application/json'},body});
 assert.equal((await proxy.sessionProxy(request('x'.repeat(4097)),'/api/flow/plans')).status,422);assert.equal(calls,0);
 assert.equal((await proxy.sessionProxy(request('{"query":"합성"}'),'/api/flow/plans')).status,502);assert.equal(calls,1);
});
test('CF020 planning streaming timeout begins before body read',async()=>{
 const controller=new AbortController();let calls=0;const proxy=load('src/shared/server/session-proxy.ts',async()=>{calls++;throw Error('must not send');},{env:{FLOW_ANALYSIS_ENABLED:'true'},AbortSignal:{timeout(ms){assert.equal(ms,12000);return controller.signal;}}});
 const stream=new ReadableStream({start(){}});const request=new Request('http://app.unit/api/private/flow/plans',{method:'POST',headers:{'content-type':'application/json'},body:stream,duplex:'half'});
 const result=proxy.sessionProxy(request,'/api/flow/plans');controller.abort();assert.equal((await result).status,504);assert.equal(calls,0);
});

test('CF022 exact core BFF keeps16KiB/64KiB bounds and prepare16s versus confirm145s with spoof0',async()=>{
 const seen=[],timeouts=[];const options={env:{FLOW_ANALYSIS_ENABLED:'true'},AbortSignal:{timeout:n=>{timeouts.push(n);return new AbortController().signal;}}};
 const proxy=load('src/shared/server/session-proxy.ts',async(url,init)=>{seen.push([url,init]);return Response.json({safe:true});},options);
 for(const path of ['/api/supervisor/core/prepare','/api/supervisor/core/requests']){const response=await proxy.sessionProxy(new Request('https://app.unit'+path,{method:'POST',body:'{}',headers:{'Content-Type':'application/json',Cookie:'synthetic',Origin:'https://app.unit','X-CSRF-Token':'fresh','X-Flow-Service-Token':'spoof','X-User-ID':'spoof'}}),path);assert.equal(response.status,200);}
 assert.deepEqual(timeouts,[16000,145000]);assert.equal(seen[0][1].headers.get('x-flow-service-token'),null);assert.equal(seen[0][1].headers.get('x-user-id'),null);assert.equal(seen[0][1].headers.get('x-csrf-token'),'fresh');
 const oversized=await proxy.sessionProxy(new Request('https://app.unit/api/supervisor/core/prepare',{method:'POST',body:'x'.repeat(16385),headers:{'Content-Type':'application/json'}}),'/api/supervisor/core/prepare');assert.equal(oversized.status,422);assert.equal(seen.length,2);
});

test('CF023 exact preparation POST/GET/DELETE preserve CSRF/owner boundary and sixteen-second deadline',async()=>{
 const seen=[],timeouts=[],id=randomUUID();
 const handlers=load('src/app/api/private/[...path]/route.ts',async(url,init)=>{seen.push([url,init]);return Response.json({safe:true});},{env:{FLOW_ANALYSIS_ENABLED:'true'},AbortSignal:{timeout:ms=>{timeouts.push(ms);return new AbortController().signal;}}});
 const base='supervisor/core/preparations',ctx=p=>({params:Promise.resolve({path:p.split('/')})});
 for(const [method,target] of [['POST',base],['GET',base+'/'+id],['DELETE',base+'/'+id]]){
  const request=new Request('https://app.unit/api/private/'+target,{method,headers:{'content-type':'application/json',Cookie:'synthetic',Origin:'https://app.unit','x-csrf-token':'fresh','x-user-id':'spoof','x-flow-service-token':'spoof'},...(method==='POST'?{body:'{}'}:{})});
  const response=await handlers[method](request,ctx(target));assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'private, no-store');
 }
 assert.deepEqual(timeouts,[16000,16000,16000]);assert.equal(seen.length,3);
 for(const [url,init] of seen){assert.match(url,/^http:\/\/backend.unit\/api\/supervisor\/core\/preparations/);assert.equal(init.redirect,'manual');assert.equal(init.headers.get('x-csrf-token'),'fresh');assert.equal(init.headers.get('x-flow-service-token'),null);assert.equal(init.headers.get('x-user-id'),null);}
 for(const [method,target] of [['GET',base],['DELETE',base],['POST',base+'/'+id],['GET',base+'/'+id+'/extra'],['POST',base+'?x=1']]){
  assert.equal((await handlers[method](new Request('https://app.unit/api/private/'+target,{method}),ctx(target.split('?')[0]))).status,422);
 }
 assert.equal(seen.length,3);
});
