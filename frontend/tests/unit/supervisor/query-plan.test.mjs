import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto,createHash} from 'node:crypto';
import ts from 'typescript';
const A='11111111-1111-4111-8111-111111111111',B='22222222-2222-4222-8222-222222222222';
const query='  삼성전자 외국인 수급  ',hash=q=>createHash('sha256').update(q).digest('hex');
function stock(){return {stock_code:'005930',stock_name:'삼성전자',market:'KOSPI'};}
function view(status='ready_for_confirmation'){
 const ambiguous=['needs_stock_selection','selection_stale'].includes(status),empty=['unsupported','needs_clarification'].includes(status),notFound=status==='not_found';
 return {version:'supervisor.flow-plan.v1',policy_version:'supervisor.flow-only.1',query_sha256:hash(query),requested_views:status==='unsupported'?['technical']:status==='needs_clarification'?[]:['flow'],status,
 reason:{ready_for_confirmation:'stock_resolved',needs_stock_selection:'stock_ambiguous',selection_stale:'selection_changed',not_found:'stock_not_found',needs_clarification:'clarify_intent',unsupported:'unsupported_views'}[status],
 resolution:empty?null:{status:ambiguous?'ambiguous':notFound?'not_found':'resolved',reason:ambiguous?'ambiguous_alias':notFound?'no_match':'exact_match',stock:ambiguous||notFound?null:stock(),candidates:ambiguous?[{...stock(),match_type:'ambiguous_group'}]:[]},candidate_ref:empty?null:'a'.repeat(64)};
}
function load(fetcher){
 const cache={};function module(file){if(cache[file])return cache[file];const bundle={exports:{}};const source=fs.readFileSync(file,'utf8');
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{module:bundle,exports:bundle.exports,URL,URLSearchParams,Request,Response,Headers,TextEncoder,TextDecoder,AbortController,AbortSignal,crypto:webcrypto,fetch:fetcher,require(name){if(name==='@/features/flow/lib/analysis-request')return module('src/features/flow/lib/analysis-request.ts');throw Error('unexpected module');}},{timeout:100});cache[file]=bundle.exports;return bundle.exports;}
 return module('src/features/supervisor/lib/query-plan.ts');
}
for(const status of ['ready_for_confirmation','needs_stock_selection','selection_stale','not_found','needs_clarification','unsupported'])test('strict planning union '+status,()=>{
 const h=load(()=>{throw Error('unexpected network');});assert.equal(h.validatePlan(view(status),hash(query)).status,status);
 const bad={...view(status),owner_user_id:A};assert.throws(()=>h.validatePlan(bad,hash(query)));
});
test('real prepare helper preserves original query, fresh owner/CSRF and selection, never analysis POST',async()=>{
 const seen=[];const h=load(async(url,init={})=>{seen.push([url,init]);return url==='/api/auth/session'?Response.json({user_id:A,csrf_token:'fresh-synthetic'}):Response.json({request_id:A,data:view(),error:null});});
 const result=await h.prepareQuery(query,A,new AbortController().signal,()=>true,{selected_ticker:'005930',candidate_ref:'a'.repeat(64)});
 assert.equal(result.status,'ready_for_confirmation');assert.equal(seen.length,3);assert.equal(seen[0][0],'/api/auth/session');assert.equal(seen[2][0],'/api/auth/session');
 const post=seen[1];assert.equal(post[0],'/api/private/flow/plans');assert.equal(post[1].headers['X-CSRF-Token'],'fresh-synthetic');assert.equal(post[1].cache,'no-store');assert.deepEqual(JSON.parse(post[1].body),{query,selected_ticker:'005930',candidate_ref:'a'.repeat(64)});
 assert.equal(seen.filter(([url])=>url.includes('analyses')).length,0);
});
for(const stage of ['before','after'])test('owner change '+stage+' cannot adopt a plan',async()=>{
 let sessions=0,posts=0;const h=load(async url=>{if(url==='/api/auth/session'){sessions++;return Response.json({user_id:stage==='before'||sessions===2?B:A,csrf_token:'fresh'});}posts++;return Response.json({request_id:A,data:view(),error:null});});
 await assert.rejects(h.prepareQuery(query,A,new AbortController().signal,()=>true));assert.equal(posts,stage==='before'?0:1);
});
test('late plan response is rejected after generation invalidation',async()=>{
 let finish;let current=true;const held=new Promise(resolve=>{finish=resolve;});let started;const reached=new Promise(resolve=>{started=resolve;});const h=load(async url=>{if(url==='/api/auth/session')return Response.json({user_id:A,csrf_token:'fresh'});started();return held;});
 const task=h.prepareQuery(query,A,new AbortController().signal,()=>current);await reached;current=false;finish(Response.json({request_id:A,data:view(),error:null}));await assert.rejects(task);
});
test('oversize decoded response cancels without reading a second chunk',async()=>{
 let sent=0,cancelled=false;const h=load(async url=>url==='/api/auth/session'?Response.json({user_id:A,csrf_token:'fresh'}):new Response(new ReadableStream({pull(c){sent++;c.enqueue(new Uint8Array(16385));},cancel(){cancelled=true;}},{highWaterMark:0})));
 await assert.rejects(h.prepareQuery(query,A,new AbortController().signal,()=>true));assert.equal(sent,1);assert.equal(cancelled,true);
});
test('canonical selection and wire corruption are closed',()=>{
 const h=load(()=>{});
 for(const mutate of [p=>p.query_sha256='0'.repeat(64),p=>p.requested_views=['flow','technical'],p=>p.resolution.stock.stock_code='１２３４５６',p=>p.resolution.stock.stock_name=' ',p=>p.resolution.stock.market='OTHER',p=>p.candidate_ref='A'.repeat(64)]){
  const p=view();mutate(p);assert.throws(()=>h.validatePlan(p,hash(query)));
 }
});
test('actual UI sources keep session/generation/URL/visibility and pending bypass boundaries (source assertions)',()=>{
 const ui=fs.readFileSync('src/features/supervisor/components/query-preparation.tsx','utf8'),parent=fs.readFileSync('src/features/flow/components/analysis-request.tsx','utf8');
 for(const part of ['locked.current=true','owner.current===userId','window.location.href===href','visibilitychange','controller.abort()','onClear()'])assert.ok(ui.includes(part));
 assert.ok(parent.includes('!hasPending&&!analysisId&&!knownId&&verified&&<QueryPreparation'));assert.ok(parent.includes('preparedHref.current!==window.location.href'));assert.ok(parent.includes('preparationBinding.current.capture(userId,window.location.href)'));assert.ok(parent.includes('dispatchPreparedAnalysis(preparationBinding.current,preparation'));assert.ok(parent.includes('postAnalysis(value,session.csrf_token'));
 assert.doesNotMatch(ui,/postAnalysis|freshPending|localStorage|sessionStorage/);
});

for(const invalidation of ['cancel','query','URL','consent','account'])test('production parent fresh dispatcher: delayed session then '+invalidation+' saves/posts zero',async()=>{
 let release,entered;const waiting=new Promise(resolve=>{entered=resolve;});let posts=0,saves=0;
 const h=load(async url=>{if(url==='/api/auth/session'){entered();return new Promise(resolve=>{release=resolve;});}posts++;throw Error('Unexpected analysis POST');});
 const binding=new h.PreparationBinding();let href='http://localhost:3200/research';binding.bind({owner:A,href,ticker:'005930',query});binding.setConsent(true);const ticket=binding.capture(A,href);assert.ok(ticket);
 const task=h.dispatchPreparedAnalysis(binding,ticket,new AbortController().signal,()=>href,()=>true,()=>{saves++;});await waiting;
 if(invalidation==='URL')href+='#changed';else if(invalidation==='consent')binding.setConsent(false);else if(invalidation==='query')binding.bind({owner:A,href,ticker:'005930',query:'changed'});else if(invalidation==='cancel')binding.clear();
 release(Response.json({user_id:invalidation==='account'?B:A,csrf_token:'fresh'}));await assert.rejects(task);assert.equal(posts,0);assert.equal(saves,0);
});
test('production parent fresh dispatcher persists exact pending then invokes actual analysis helper once',async()=>{
 let posts=0,saves=0,saved;const h=load(async(url,init={})=>{
  if(url==='/api/auth/session')return Response.json({user_id:A,csrf_token:'fresh'});
  assert.equal(url,'/api/private/flow/analyses');posts++;const body=JSON.parse(init.body);assert.equal(saves,1);assert.equal(body.ticker,'005930');assert.equal(body.question,query);assert.equal(body.allow_analysis,true);assert.equal(body.idempotency_key,saved.idempotency_key);assert.equal(init.headers['X-CSRF-Token'],'fresh');
  return Response.json({request_id:A,data:{analysis_id:A,admission_request_id:B,attempt_id:'33333333-3333-4333-8333-333333333333',state:'stored',deadline_at:'2099-01-01T00:00:00Z',report_id:B,report_url:'/reports/flow/'+B,error:null},error:null});
 });const b=new h.PreparationBinding(),href='http://localhost:3200/research';b.bind({owner:A,href,ticker:'005930',query});b.setConsent(true);
 const result=await h.dispatchPreparedAnalysis(b,b.capture(A,href),new AbortController().signal,()=>href,()=>true,p=>{saves++;saved=p;});assert.equal(result.view.state,'stored');assert.equal(result.pending,saved);assert.equal(posts,1);assert.equal(saves,1);
});
test('current preparation session keeps exact original input and requires fresh consent after replacement',async()=>{
 const h=load(async()=>Response.json({user_id:A,csrf_token:'fresh'}));const b=new h.PreparationBinding();const href='http://localhost:3200/research';b.bind({owner:A,href,ticker:'005930',query});assert.equal(b.capture(A,href),null);b.setConsent(true);const ticket=b.capture(A,href);assert.equal(ticket.query,query);
 assert.equal((await h.verifyPreparedSession(b,ticket,new AbortController().signal,()=>href,()=>true)).user_id,A);b.bind({owner:A,href,ticker:'000660',query});assert.equal(b.capture(A,href),null);assert.equal(b.accepts(ticket,A,href),false);
});
