import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';
import ts from 'typescript';
const root=path.resolve(import.meta.dirname,'../../..');
function load(fetchSpy=()=>{throw Error('Unexpected fetch');}){
 const source=ts.transpileModule(fs.readFileSync(path.join(root,'src/features/fundamental/lib/analysis-request.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const bundle={exports:{}};vm.runInNewContext(source,{module:bundle,exports:bundle.exports,Response,Headers,Request,AbortSignal,TextEncoder,URL,URLSearchParams,crypto:{randomUUID},fetch:fetchSpy});return bundle.exports;
}
const a='AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA',b='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const pending={ticker:'005930',question:'합성 요청',idempotency_key:a};
function view(state='running'){return {analysis_id:a,admission_request_id:a,attempt_id:b,state,deadline_at:'2026-11-08T00:02:00Z',report_id:state==='stored'?b:null,report_url:state==='stored'?'/reports/fundamental/'+b:null,error:['failed','unknown'].includes(state)?{code:'SERVICE_UNAVAILABLE'}:null};}

test('strict wire, status and original IDs; only stored links to report',async()=>{
 const h=load();for(const state of ['running','result_ready','stored','failed','unknown']){
  const result=await h.wire(Response.json({request_id:a,data:view(state),error:null},{status:['stored','failed'].includes(state)?200:202}));
  assert.equal(result.analysis_id,a.toLowerCase());assert.equal(result.report_url,state==='stored'?'/reports/fundamental/'+b:null);
 }
 for(const change of [{report_url:'/reports/fundamental/'+b},{state:'deleted'},{owner_user_id:a},{attempt_id:'bad'}])assert.throws(()=>h.analysisView({...view(),...change}));
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
 assert.equal(h.canReplay(a,{...pending,analysis_id:a.toLowerCase()}),true);assert.equal(h.canReplay(null,pending),true);
 assert.equal(h.matchesAnalysisUrl('/fundamental','?analysis_id='+a,a.toLowerCase()),true);
 assert.equal(h.matchesAnalysisUrl('/fundamental','?analysis_id='+b,a),false);
 const intent=new h.AnalysisIntent(),ticket=intent.begin();assert.equal(intent.begin(),null);intent.invalidate();assert.equal(intent.accepts(ticket),false);
 const next=intent.begin();intent.finish(ticket);assert.equal(intent.begin(),null);intent.finish(next);assert.notEqual(intent.begin(),null);
});
test('GET never POSTS and explicit replay retains request key/body while stripping result identity',async()=>{
 const calls=[];const h=load(async(url,options)=>{calls.push({url,options});return Response.json({request_id:a,error:null,data:view()},{status:202});});
 await h.getAnalysis(a,new AbortController().signal);assert.equal(calls[0].url.endsWith(a.toLowerCase()),true);assert.equal(calls[0].options.method,undefined);
 await h.postAnalysis({...pending,analysis_id:a},'synthetic-csrf',new AbortController().signal);
 const sent=JSON.parse(calls[1].options.body);assert.deepEqual(Object.keys(sent).sort(),['allow_analysis','idempotency_key','question','ticker']);assert.equal(sent.idempotency_key,a.toLowerCase());assert.equal(sent.allow_analysis,true);
});
test('lifecycle wiring has explicit foreground verification, synchronous invalidation and URL guards (source only)',()=>{
 const source=fs.readFileSync(path.join(root,'src/features/fundamental/components/analysis-request.tsx'),'utf8');
 assert.match(source,/function shown\(\)[\s\S]*?generation\.current\+\+[\s\S]*?void verify\(\)/);
 for(const part of ['pending.current=null','setHasPending(false)',"setTicker('')","setQuestion('')",'setChecked(false)','clearTimeout(timer.current)','controller.current?.abort()','generation.current++'])assert.ok(source.includes(part),part);
 assert.ok(source.includes('canReplay(analysisId,pending.current)'));assert.ok(source.includes('pollRequest.current(result.analysis_id)'));
 assert.ok(source.includes('if(accepts())void verify(id)'));assert.equal(source.includes('.textContent='),false);
 const page=fs.readFileSync(path.join(root,'src/app/fundamental/page.tsx'),'utf8');assert.equal(page.includes('sessionBackendFetch'),false);
});

test('source links accept only http/https and preserve zero/null, raw UUIDs never throw',()=>{
 const h=load();for(const v of ['javascript:alert(1)','data:text/html,bad','file:///private','invalid',null])assert.equal(h.safeSourceUrl(v),null);
 assert.equal(h.safeSourceUrl('https://source.unit/report'),'https://source.unit/report');assert.equal(h.displayValue(0),'0');assert.equal(h.displayValue(null),'자료 없음');
 for(const value of [a,a.replaceAll('-',''),'{'+a+'}','urn:uuid:'+a])assert.equal(h.storedUuid(value),a.toLowerCase());
 for(const value of ['invalid','',null,5])assert.equal(h.storedUuid(value),null);
 const view=fs.readFileSync(path.join(root,'src/features/fundamental/components/fundamental-report-view.tsx'),'utf8');
 assert.equal(/iframe|dangerouslySetInnerHTML|window\.open/.test(view),false);assert.ok(view.includes('storedUuid(root.id)'));assert.ok(view.includes('safeSourceUrl(row.source_url)'));
 const component=fs.readFileSync(path.join(root,'src/features/fundamental/components/analysis-request.tsx'),'utf8');
 assert.ok(component.includes('Date.now()<Date.parse(value.deadline_at)'));assert.ok(component.includes('상태 다시 조회 (실행 없음)'));assert.ok(component.includes('if(id)pollRequest.current(id)'));assert.ok(component.includes('analysisId??pending.current?.analysis_id??view?.analysis_id'));assert.equal(component.includes('disabled={!verified||busy||!view}'),false);
});
