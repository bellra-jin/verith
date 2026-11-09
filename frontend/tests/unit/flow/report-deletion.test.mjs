import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const source=fs.readFileSync('src/features/flow/lib/report-deletion.ts','utf8');
const bundle={exports:{}};vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{module:bundle,exports:bundle.exports,URL,AbortController,setTimeout,clearTimeout,fetch,Promise},{timeout:100});
const h=bundle.exports,A='11111111-1111-4111-8111-111111111111',B='22222222-2222-4222-8222-222222222222',R='33333333-3333-4333-8333-333333333333';
const target=()=>h.reportTarget(R,A,'http://127.0.0.1:32123/reports/flow/'+R+'?limit=20&offset=40','/?limit=20&offset=40');
const session=(user=A)=>Response.json({user_id:user,csrf_token:'synthetic-fresh-csrf'});
const report=()=>Response.json({report_id:R,report:{report_id:R}});
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};};
test('fixed canonical identity and safe archive pagination reject external/ambiguous targets',()=>{
 assert.equal(target().returnTo,'/?limit=20&offset=40');
 for(const value of ['//evil.invalid','https://evil.invalid','javascript:alert(1)','/research','/?limit=0','/?limit=20&limit=20','/?offset=-1','/?offset=99999999999999999','/\\evil.invalid'])assert.throws(()=>h.safeReturnTo(value));
 assert.throws(()=>h.reportTarget(R,A,'http://127.0.0.1/reports/flow/'+B,'/'));
});
test('fresh GET verifies same account/report and never mutates; original target remains frozen',async()=>{
 const seen=[],value=target();const intent=new h.ReportIntent(async(url,init)=>{seen.push([url,init]);return url==='/api/auth/session'?session():report();});
 await intent.verify(value,()=>true);assert.equal(seen.length,2);assert.ok(seen.every(([,i])=>i.cache==='no-store'&&i.method===undefined));assert.ok(Object.isFrozen(value));
});
test('confirmation helper sends exactly one DELETE with fresh CSRF while duplicate attempt is refused',async()=>{
 const held=deferred(),seen=[];const intent=new h.ReportIntent(async(url,init)=>{seen.push([url,init]);if(url==='/api/auth/session')return held.promise;return new Response(null,{status:204});});
 const task=intent.remove(target(),()=>true);assert.equal(intent.pending,true);await assert.rejects(intent.remove(target(),()=>true),e=>e.code==='busy');
 held.resolve(session());assert.equal(await task,'/?limit=20&offset=40');assert.equal(seen.filter(([,i])=>i.method==='DELETE').length,1);assert.equal(seen[1][1].headers['X-CSRF-Token'],'synthetic-fresh-csrf');assert.equal(intent.pending,false);
});
test('changed session owner refuses DELETE and all raw errors stay hidden',async()=>{
 let deletes=0;const intent=new h.ReportIntent(async(url,init)=>{if(init.method==='DELETE')deletes++;return session(B);});
 await assert.rejects(intent.remove(target(),()=>true),e=>e.code==='auth');assert.equal(deletes,0);assert.doesNotMatch(h.reportError(new Error('PRIVATE-SENTINEL')),/PRIVATE/);
});
for(const status of [200,202,404,401,403,500])test('only 204 is deletion success; safe status '+status,async()=>{
 const intent=new h.ReportIntent(async(url)=>url==='/api/auth/session'?session():new Response(null,{status}));
 await assert.rejects(intent.remove(target(),()=>true));assert.equal(intent.pending,false);
});
test('invalidation/target/URL changes refuse delayed continuation and cannot unlock newer intent',async()=>{
 const old=deferred(),fresh=deferred();let calls=0;const seen=[];const intent=new h.ReportIntent(async(url,init)=>{seen.push([url,init]);return ++calls===1?old.promise:fresh.promise;});
 const first=intent.remove(target(),()=>true);intent.invalidate();const next=intent.verify(target(),()=>true);
 old.resolve(session());await assert.rejects(first,e=>e.code==='stale');assert.equal(intent.pending,true);assert.equal(seen.some(([,i])=>i.method==='DELETE'),false);
 intent.invalidate();fresh.resolve(session());await assert.rejects(next,e=>e.code==='stale');
 let current=true;const delay=deferred();const other=new h.ReportIntent(async()=>delay.promise);const task=other.remove(target(),()=>current);current=false;delay.resolve(session());await assert.rejects(task,e=>e.code==='stale');
});
test('single 15s total budget covers session and DELETE body, no automatic retry',async()=>{
 let timeout,cleared=0,requested=0,ms;const never=deferred();const intent=new h.ReportIntent(async()=>{requested++;return never.promise;},{set(fn,value){timeout=fn;ms=value;return 1;},clear(){cleared++;}});
 const task=intent.remove(target(),()=>true);assert.equal(ms,15000);timeout();await assert.rejects(task,e=>e.code==='timeout');assert.equal(requested,1);assert.equal(cleared,1);assert.equal(intent.pending,false);never.resolve(session());await Promise.resolve();assert.equal(requested,1);
});
test('failed read can be manually reverified with same immutable identity, no POST/DELETE',async()=>{
 const seen=[];let bad=true;const intent=new h.ReportIntent(async(url,init)=>{seen.push(init.method);if(bad)throw Error('PRIVATE');return url==='/api/auth/session'?session():report();});
 await assert.rejects(intent.verify(target(),()=>true));bad=false;await intent.verify(target(),()=>true);assert.ok(seen.every(v=>v===undefined));
});
test('active SSR wraps body and component wires cancel/invalidation without changing logout (source assertion)',()=>{
 const jsx=fs.readFileSync('src/features/flow/components/session-controls.tsx','utf8'),page=fs.readFileSync('src/app/reports/flow/[reportId]/page.tsx','utf8');
 for(const phrase of ['취소','삭제 확인','pagehide','pageshow','visibilitychange','rendered.current===identity','setVisible(null)','intent.current!.remove'])assert.ok(jsx.includes(phrase));
 assert.match(jsx,/onClick=\{\(\)=>setConfirm\(null\)\}/);assert.match(jsx,/if\(reportId\)return <ReportControls/);assert.match(jsx,/fetch\('\/api\/auth\/logout'/);
 assert.match(page,/userId=\{session.user_id\}/);assert.ok(page.indexOf('<SessionControls')<page.indexOf('<FlowReportView'));assert.ok(page.indexOf('</SessionControls>')>page.indexOf('<FlowReportView'));
});

test('confirmation captures immutable URL/epoch before request; stale catches cannot update new URL (source assertion)',()=>{
 const jsx=fs.readFileSync('src/features/flow/components/session-controls.tsx','utf8');
 assert.match(jsx,/setConfirm\(\{target:reportTarget/);assert.match(jsx,/const \{target,epoch\}=confirm/);
 assert.match(jsx,/catch\(e\)\{if\(current\(\)\)/);assert.match(jsx,/finally\{if\(sameContext\(\)\)/);
 assert.match(jsx,/hashchange/);assert.match(jsx,/setInterval\(locationCheck,200\)/);
});

test('verified observation binds exact href; replaceState/hash change before polling cannot open confirmation',()=>{
 const verified={identity:'report|owner',href:target().href};
 assert.equal(h.sameReportObservation(verified,'report|owner',verified.href),true);
 assert.equal(h.sameReportObservation(verified,'report|owner',verified.href+'#changed'),false);
 assert.equal(h.sameReportObservation(verified,'other|owner',verified.href),false);
 assert.equal(h.sameReportObservation(null,'report|owner',verified.href),false);
 const jsx=fs.readFileSync('src/features/flow/components/session-controls.tsx','utf8');
 assert.match(jsx,/setVisible\(\{identity,href:target.href\}\)/);
 const ask=jsx.slice(jsx.indexOf('function askConfirm'),jsx.indexOf('async function remove'));
 assert.ok(ask.indexOf('sameReportObservation(visible,identity,window.location.href)')<ask.indexOf('setConfirm({target:reportTarget'));
});

test('canonical envelope binds stored v1 UUID spellings without changing original JSON',async()=>{
 for(const raw of [R,R.replaceAll('-',''),'urn:uuid:'+R,'{'+R+'}']){
  const payload={report_id:R,report:{report_id:raw}},before=JSON.stringify(payload);
  const intent=new h.ReportIntent(async(url)=>url==='/api/auth/session'?session():Response.json(payload));
  await intent.verify(target(),()=>true);assert.equal(JSON.stringify(payload),before);assert.equal(h.sourceReportId(raw),R);
 }
 for(const raw of ['malformed',B,null]){
  const intent=new h.ReportIntent(async(url)=>url==='/api/auth/session'?session():Response.json({report_id:R,report:{report_id:raw}}));
  await assert.rejects(intent.verify(target(),()=>true));
 }
});

test('15s total deadline also aborts an already-started DELETE once, without replay',async()=>{
 let timeout;const held=deferred(),reachedDELETE=deferred(),seen=[];
 const intent=new h.ReportIntent(async(url,init)=>{seen.push([url,init]);if(url==='/api/auth/session')return session();reachedDELETE.resolve();return held.promise;},{set(fn,ms){assert.equal(ms,15000);timeout=fn;return 1;},clear(){}});
 const task=intent.remove(target(),()=>true);
 await reachedDELETE.promise;
 assert.equal(seen.filter(([,i])=>i.method==='DELETE').length,1);const signal=seen[1][1].signal;
 timeout();await assert.rejects(task,e=>e.code==='timeout');assert.equal(signal.aborted,true);
 held.resolve(new Response(null,{status:204}));await Promise.resolve();assert.equal(seen.filter(([,i])=>i.method==='DELETE').length,1);
});
test('window blur/focus is an explicit invalidation/revalidation boundary, not instantaneous server monitoring (source assertion)',()=>{
 const jsx=fs.readFileSync('src/features/flow/components/session-controls.tsx','utf8');
 assert.match(jsx,/blur=\(\)=>\{focused.current=false;hide\(\)/);assert.match(jsx,/focus=\(\)=>\{void observe\(\)/);
 for(const event of ['blur','focus']){assert.ok(jsx.includes("addEventListener('"+event+"'"));assert.ok(jsx.includes("removeEventListener('"+event+"'"));}
 assert.match(jsx,/&&focused.current&&document.hasFocus\(\)&&document.visibilityState/);
});


// Execute the actual fixed observe callback with synthetic refs/DOM/transport;
// this is a VM lifecycle slice, not a React click.
function observationSlice({cached=false,actual=true,visibility='visible',fetcher}={}){
 const jsx=fs.readFileSync('src/features/flow/components/session-controls.tsx','utf8');
 const parsed=ts.createSourceFile('session-controls.tsx',jsx,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),found=[];
 function visit(node){if(ts.isVariableDeclaration(node)&&node.name.getText(parsed)==='observe')found.push(node);ts.forEachChild(node,visit);}visit(parsed);
 assert.equal(found.length,1);const callback=found[0].initializer.arguments[0];assert.ok(ts.isArrowFunction(callback));
 const focus={actual,visibility},focused={current:cached},generation={current:0},alive={current:true},identity='synthetic-identity',rendered={current:identity},seen=[];
 const state={visible:null,pending:false,error:''};
 const controller=new h.ReportIntent(fetcher??(async(url,init)=>{seen.push([url,init]);return url==='/api/auth/session'?session():report();}));
 const context={alive,focused,generation,rendered,identity,reportId:R,userId:A,returnTo:'/',intent:{current:controller},
  document:{hasFocus:()=>focus.actual,get visibilityState(){return focus.visibility;}},window:{location:{href:'http://127.0.0.1/reports/flow/'+R}},
  invalidate(){generation.current++;controller.invalidate();state.visible=null;state.pending=false;state.error='';},
  reportTarget:h.reportTarget,reportError:h.reportError,setVisible:v=>{state.visible=v;},setPending:v=>{state.pending=v;},setError:v=>{state.error=v;}};
 const code=ts.transpileModule('const observe='+callback.getText(parsed)+';observe;',{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
 return {run:vm.runInNewContext(code,context,{timeout:100}),focus,focused,state,seen};
}
test('actual observe re-samples stale false focus and performs GET-only owner/report verification',async()=>{
 const slice=observationSlice({cached:false,actual:true});await slice.run();
 assert.equal(slice.focused.current,true);assert.ok(slice.state.visible);assert.equal(slice.state.pending,false);
 assert.deepEqual(slice.seen.map(([url])=>url),['/api/auth/session','/api/private/flow/reports/'+R]);assert.ok(slice.seen.every(([,init])=>init.method===undefined));
});
for(const [actual,visibility] of [[false,'visible'],[true,'hidden'],[false,'hidden']])test('actual observe stays closed with focus='+actual+' visibility='+visibility,async()=>{
 const slice=observationSlice({cached:true,actual,visibility});await slice.run();
 assert.equal(slice.focused.current,actual);assert.equal(slice.seen.length,0);assert.equal(slice.state.visible,null);assert.equal(slice.state.pending,false);
});
test('actual observe rejects a late session response after real focus changes without a cached event',async()=>{
 const held=deferred(),started=deferred(),seen=[];
 const slice=observationSlice({cached:false,actual:true,fetcher:async(url,init)=>{seen.push([url,init]);started.resolve();return held.promise;}});
 const task=slice.run();await started.promise;slice.focus.actual=false;held.resolve(session());await task;
 assert.equal(seen.length,1);assert.equal(slice.state.visible,null);assert.equal(slice.state.error,'');assert.equal(slice.state.pending,false);
});


for(const injected of [false,true])test('browser-like global fetch keeps its global receiver for '+(injected?'injected':'default')+' verify/remove',async()=>{
 const mod={exports:{}};const context=vm.createContext({module:mod,exports:mod.exports,URL,AbortController,setTimeout,clearTimeout,Promise,Response});
 vm.runInContext(`globalThis.calls=[];globalThis.brandRejected=0;globalThis.fetch=function(url,init){
  'use strict';if(this!==globalThis){globalThis.brandRejected++;throw new TypeError('SYNTHETIC-RECEIVER-ERROR');}
  calls.push({url,method:init.method,cache:init.cache,csrf:init.headers?.['X-CSRF-Token']});
  if(url==='/api/auth/session')return Promise.resolve(Response.json({user_id:${JSON.stringify(A)},csrf_token:'synthetic-fresh-csrf'}));
  if(init.method==='DELETE')return Promise.resolve(new Response(null,{status:204}));
  return Promise.resolve(Response.json({report_id:${JSON.stringify(R)},report:{report_id:${JSON.stringify(R)}}}));
 };`,context,{timeout:100});
 const nativeLike=vm.runInContext('fetch',context);
 assert.throws(()=>nativeLike.call({},'/api/auth/session',{}),/SYNTHETIC-RECEIVER-ERROR/);
 assert.equal(vm.runInContext('calls.length',context),0); // the fake really brand-checks before transport
 vm.runInContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,context,{timeout:100});
 const intent=injected?new mod.exports.ReportIntent(nativeLike):new mod.exports.ReportIntent();
 await intent.verify(target(),()=>true);assert.equal(await intent.remove(target(),()=>true),'/?limit=20&offset=40');
 const calls=JSON.parse(vm.runInContext('JSON.stringify(calls)',context));
 assert.deepEqual(calls.map(c=>c.url),['/api/auth/session','/api/private/flow/reports/'+R,'/api/auth/session','/api/private/flow/reports/'+R]);
 assert.deepEqual(calls.map(c=>c.method),[undefined,undefined,undefined,'DELETE']);assert.ok(calls.every(c=>c.cache==='no-store'));
 assert.equal(calls[3].csrf,'synthetic-fresh-csrf');assert.equal(vm.runInContext('brandRejected',context),1);assert.equal(intent.pending,false);
});
