import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';
import ts from 'typescript';
const root=path.resolve(import.meta.dirname,'../../..');
function load(fetchSpy=()=>{throw Error('Unexpected fetch');},newKey=randomUUID){
 const source=ts.transpileModule(fs.readFileSync(path.join(root,'src/features/flow/lib/analysis-request.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const bundle={exports:{}};vm.runInNewContext(source,{module:bundle,exports:bundle.exports,Response,Headers,Request,AbortSignal,TextEncoder,URLSearchParams,crypto:{randomUUID:newKey},fetch:fetchSpy});return bundle.exports;
}
const a='AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA',b='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const pending={ticker:'005930',question:'합성 요청',as_of:'2026-11-08T00:00:00.000Z',idempotency_key:a};
function view(state='running'){return {analysis_id:a,admission_request_id:a,attempt_id:b,state,deadline_at:'2026-11-08T00:02:00Z',report_id:state==='stored'?b:null,report_url:state==='stored'?'/reports/flow/'+b:null,error:['failed','unknown'].includes(state)?{code:'SERVICE_UNAVAILABLE'}:null};}

test('strict wire, status and original IDs; only stored links to report',async()=>{
 const h=load();for(const state of ['running','result_ready','stored','failed','unknown']){
  const result=await h.wire(Response.json({request_id:a,data:view(state),error:null},{status:['stored','failed'].includes(state)?200:202}));
  assert.equal(result.analysis_id,a.toLowerCase());assert.equal(result.report_url,state==='stored'?'/reports/flow/'+b:null);
 }
 for(const change of [{report_url:'/reports/flow/'+b},{state:'deleted'},{owner_user_id:a},{attempt_id:'bad'}])assert.throws(()=>h.analysisView({...view(),...change}));
 await assert.rejects(()=>h.wire(Response.json({request_id:a,data:view('running'),error:null},{status:200})));
});
test('pending retains exact request in account/tab storage, no credentials/result',()=>{
 const h=load();const values=new Map(),store={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v)};
 h.writePending(store,a,pending);assert.equal(values.size,1);assert.equal(h.readPending(store,b),null);
 assert.equal(h.readPending(store,a).idempotency_key,a.toLowerCase());
 assert.equal([...values.values()].some(v=>/csrf|token|payload|result/.test(v)),false);
 assert.throws(()=>h.pendingValue({...pending,csrf_token:'forbidden'}));assert.throws(()=>h.readPending({getItem:()=>'{bad'},a));
 assert.throws(()=>h.writePending({setItem(){throw Error('blocked');}},a,pending));
});
test('explicit URL cannot replay another pending; stale intent cannot complete',()=>{
 const h=load();assert.equal(h.canReplay(a,{...pending,analysis_id:b}),false);assert.equal(h.canReplay(a,pending),false);
 assert.equal(h.canReplay(a,null),false);assert.equal(h.canReplay(a,{...pending,analysis_id:b}),false);
 assert.equal(h.canReplay(a,{...pending,analysis_id:a.toLowerCase()}),true);assert.equal(h.canReplay(null,pending),true);
 assert.equal(h.matchesAnalysisUrl('/research','?analysis_id='+a,a.toLowerCase()),true);
 assert.equal(h.matchesAnalysisUrl('/research','?analysis_id='+b,a),false);
 const intent=new h.AnalysisIntent(),ticket=intent.begin();assert.equal(intent.begin(),null);intent.invalidate();assert.equal(intent.accepts(ticket),false);
 const next=intent.begin();intent.finish(ticket);assert.equal(intent.begin(),null);intent.finish(next);assert.notEqual(intent.begin(),null);
});
test('GET never POSTS and explicit replay retains request key/body while stripping result identity',async()=>{
 const calls=[];const h=load(async(url,options)=>{calls.push({url,options});return Response.json({request_id:a,error:null,data:view()},{status:202});});
 await h.getAnalysis(a,new AbortController().signal);assert.equal(calls[0].url.endsWith(a.toLowerCase()),true);assert.equal(calls[0].options.method,undefined);
 await h.postAnalysis({...pending,analysis_id:a},'synthetic-csrf',new AbortController().signal);
 const sent=JSON.parse(calls[1].options.body);assert.deepEqual(Object.keys(sent).sort(),['allow_analysis','as_of','idempotency_key','question','ticker']);assert.equal(sent.idempotency_key,a.toLowerCase());assert.equal(sent.allow_analysis,true);
});
test('lifecycle wiring has explicit foreground verification, synchronous invalidation and URL guards (source only)',()=>{
 const source=fs.readFileSync(path.join(root,'src/features/flow/components/analysis-request.tsx'),'utf8');
 assert.match(source,/function shown\(\)[\s\S]*?generation\.current\+\+[\s\S]*?void verify\(\)/);
 for(const part of ['pending.current=null','setHasPending(false)',"setTicker('')","setQuestion('')",'setChecked(false)','clearTimeout(timer.current)','controller.current?.abort()','generation.current++'])assert.ok(source.includes(part),part);
 assert.ok(source.includes('canReplay(analysisId,pending.current)'));assert.ok(source.includes('readRequest.current(false,result.analysis_id)'));assert.ok(source.includes('observeAnalysis(userId,id,abort.signal,accepts'));assert.ok(source.includes('observation.current.permit(performance.now())'));assert.ok(source.includes('observation.current.next(result.view,performance.now(),Date.now())'));
 assert.ok(source.includes('if(accepts())void verify(false,id??undefined)'));assert.ok(source.includes('manual&&readingRef.current'));assert.ok(source.includes('readIntent.current.invalidate()'));assert.ok(source.includes('if(generation.current===revision)'));assert.ok(source.includes('if(!result.stopped)setView(result.view)'));assert.equal(source.includes('.textContent='),false);
 const page=fs.readFileSync(path.join(root,'src/app/research/page.tsx'),'utf8');assert.equal(page.includes('sessionBackendFetch'),false);
});

test('actual observation budget continues beyond fifteen seconds to stored; no terminal reservations',()=>{
 const h=load(),clock=Date.parse('2026-11-08T00:00:00Z');const policy=new h.AnalysisObservation();policy.begin(a,0);let scheduled=0;
 for(let second=0;second<=20;second++){
  assert.equal(policy.permit(second*1000),true);
  const result=policy.next({...view(second===20?'stored':'running'),deadline_at:'2026-11-08T00:02:00Z'},second*1000,clock+second*1000);
  if(second===20)assert.equal(result.kind,'stop');else{assert.equal(result.kind,'wait');scheduled++;}
 }
 assert.equal(scheduled,20);assert.equal(policy.permit(21000),false);
 for(const state of ['stored','failed','unknown','result_ready']){const p=new h.AnalysisObservation();p.begin(a,0);assert.equal(p.next(view(state),0,clock).kind,'stop');assert.equal(p.permit(1),false);}
});
test('first deadline and monotonic 120s are fixed; only one final GET can start',()=>{
 const h=load(),clock=Date.parse('2026-11-08T00:00:00Z');
 for(const first of ['2026-11-08T00:02:00Z','2099-01-01T00:00:00Z']){
  const p=new h.AnalysisObservation();p.begin(a,0);assert.equal(p.permit(0),true);assert.equal(p.next({...view(),deadline_at:first},0,clock).kind,'wait');
  p.begin(a,119000);assert.equal(p.next({...view(),deadline_at:'2099-01-01T00:00:00Z'},119000,clock-999999).delay,1000);
  assert.equal(p.permit(120000),true);assert.equal(p.next(view(),120000,clock+120000).kind,'stop');assert.equal(p.permit(120001),false);assert.equal(p.permit(999999),false);
 }
 const shorter=new h.AnalysisObservation();shorter.begin(a,0);assert.equal(shorter.next({...view(),deadline_at:'2026-11-08T00:00:30Z'},0,clock).kind,'wait');
 assert.equal(shorter.permit(30000),true);assert.equal(shorter.next({...view(),deadline_at:'2099-01-01T00:00:00Z'},30001,clock).kind,'stop');assert.equal(shorter.permit(30002),false);
});
test('invalid/past deadlines and invalid monotonic input fail closed; manual stop cannot extend',()=>{
 const h=load(),clock=Date.parse('2026-11-08T00:00:00Z');
 for(const deadline of ['invalid','','2026-11-08T00:00:10',null]){const p=new h.AnalysisObservation();p.begin(a,0);assert.equal(p.next({...view(),deadline_at:deadline},0,clock).kind,'stop');assert.equal(p.permit(1),false);}
 const past=new h.AnalysisObservation();past.begin(a,0);assert.equal(past.next({...view(),deadline_at:'2026-11-07T00:00:00Z'},0,clock).kind,'final');assert.equal(past.permit(0),true);assert.equal(past.next(view(),1,clock).kind,'stop');assert.equal(past.permit(2),false);
 for(const mono of [NaN,Infinity,-1]){const p=new h.AnalysisObservation();p.begin(a,mono);assert.equal(p.permit(0),false);}
 const backwards=new h.AnalysisObservation();backwards.begin(a,100);assert.equal(backwards.permit(99),false);
 const stopped=new h.AnalysisObservation();stopped.begin(a,0);stopped.stop();stopped.begin(a,50000);assert.equal(stopped.permit(50000),false);
});
test('actual GET-only helper retries session/GET failure with same URL or same-user pending, no POST/new key',async()=>{
 const seen=[];let sessionFail=true,getFail=true,keys=0;
 const h=load(async(url,init)=>{seen.push({url,init});if(url==='/api/auth/session'){if(sessionFail){sessionFail=false;return new Response(null,{status:503});}return Response.json({user_id:b,csrf_token:'synthetic'});}
  if(getFail){getFail=false;return Response.json({request_id:a,data:null,error:{code:'SERVICE_UNAVAILABLE'}},{status:503});}return Response.json({request_id:a,data:view('stored'),error:null});
 },()=>{keys++;return randomUUID();});
 const store={getItem:()=>JSON.stringify({...pending,analysis_id:a})};const saved=h.readPending(store,b);const before=JSON.stringify(saved);
 const id=h.observationId(a,b);assert.equal(id,a.toLowerCase());const signal=new AbortController().signal;
 await assert.rejects(()=>h.observeAnalysis(b,id,signal,()=>true),e=>e.status===503);
 await assert.rejects(()=>h.observeAnalysis(b,id,signal,()=>true),e=>e.status===503);
 const result=await h.observeAnalysis(b,h.observationId(null,saved.analysis_id),signal,()=>true);assert.equal(result.view.state,'stored');assert.equal(JSON.stringify(saved),before);
 assert.equal(seen.filter(v=>v.url.includes('/flow/analyses/')).length,2);assert.equal(seen.every(v=>v.init.method===undefined),true);assert.equal(keys,0);
 assert.equal(h.observationId(null,undefined),null);assert.equal(h.observationId('invalid',a),null);
 const noId=await h.observeAnalysis(b,null,signal,()=>true);assert.equal(noId.view,null);
 const timeout=new AbortController();timeout.abort();await assert.rejects(()=>h.observeAnalysis(b,id,timeout.signal,()=>true),e=>e.status===503);
});
test('storage failure cannot hide explicit URL GET; 401 and other account never read analysis',async()=>{
 let gets=0,account=b,status=200;const h=load(async url=>{
  if(url==='/api/auth/session')return status===200?Response.json({user_id:account,csrf_token:'synthetic'}):new Response(null,{status});
  gets++;return Response.json({request_id:a,data:view('stored'),error:null});
 });
 let saved=null;try{saved=h.readPending({getItem(){throw Error('storage blocked');}},b);}catch{}
 assert.equal((await h.observeAnalysis(b,h.observationId(a,saved?.analysis_id),new AbortController().signal,()=>true)).view.state,'stored');assert.equal(gets,1);
 account=a;await assert.rejects(()=>h.observeAnalysis(b,a,new AbortController().signal,()=>true),e=>e instanceof h.AnalysisAccountChanged);assert.equal(gets,1);
 account=b;status=401;await assert.rejects(()=>h.observeAnalysis(b,a,new AbortController().signal,()=>true),e=>e.status===401);assert.equal(gets,1);
 const source=fs.readFileSync(path.join(root,'src/features/flow/components/analysis-request.tsx'),'utf8');assert.ok(source.includes('setBlocked(storageBlocked)'));assert.ok(source.includes('if(busyRef.current||readingRef.current!==null'));assert.ok(source.includes('로그인 상태 다시 확인'));assert.ok(source.includes('[analysisId,retry]'));assert.ok(source.includes('setError(storageBlocked?'));
});
test('duplicate read intent, old abort and late response cannot erase a fresh success',async()=>{
 let finishOld;let analysisCalls=0;const h=load(async url=>{
  if(url==='/api/auth/session')return Response.json({user_id:b,csrf_token:'synthetic'});
  analysisCalls++;if(analysisCalls===1)return new Promise(resolve=>{finishOld=resolve;});return Response.json({request_id:a,data:view('stored'),error:null});
 });
 const intent=new h.AnalysisIntent(),first=intent.begin(),old=new AbortController();assert.equal(intent.begin(),null);
 const previous=h.observeAnalysis(b,a,old.signal,()=>intent.accepts(first));
 await Promise.resolve();await Promise.resolve();
 // Allow the synthetic session JSON promise to resolve without real-duration sleep.
 while(!finishOld)await new Promise(resolve=>setImmediate(resolve));
 old.abort();intent.invalidate();const next=intent.begin();const current=await h.observeAnalysis(b,a,new AbortController().signal,()=>intent.accepts(next));assert.equal(current.view.state,'stored');
 finishOld(Response.json({request_id:a,data:view(),error:null},{status:202}));assert.equal(await previous,null);intent.finish(first);assert.equal(intent.begin(),null);intent.finish(next);assert.notEqual(intent.begin(),null);
});
test('stopped observation after invalidation rechecks session but cannot verify a missing view or enable POST',async()=>{
 let stateGets=0;const h=load(async url=>url==='/api/auth/session'?Response.json({user_id:b,csrf_token:'synthetic'}):(stateGets++,Response.json({request_id:a,data:view('stored'),error:null})));
 const p=new h.AnalysisObservation();p.begin(a,0);p.next(view('stored'),0,Date.parse('2026-11-08T00:00:00Z'));
 const result=await h.observeAnalysis(b,a,new AbortController().signal,()=>true,()=>p.permit(5000));
 assert.equal(result.stopped,true);assert.equal(result.view,null);assert.equal(stateGets,0);
 const source=fs.readFileSync(path.join(root,'src/features/flow/components/analysis-request.tsx'),'utf8');assert.ok(source.includes('setVerified(!result.stopped)'));assert.ok(source.includes('!checked||!verified'));assert.ok(source.includes('knownIdRef.current!==null&&!canReplay(knownIdRef.current,pending.current)'));assert.ok(source.includes('setReplayable(canReplay(id,loaded))'));assert.ok(source.includes("disabled={busy||reading==='manual'||!(analysisId||knownId)}"));
 const recovered=await h.observeAnalysis(b,a,new AbortController().signal,()=>true);assert.equal(recovered.view.state,'stored');assert.equal(stateGets,1);assert.equal(p.permit(6000),false);
});
