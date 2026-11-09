import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import vm from 'node:vm';import ts from 'typescript';import {webcrypto} from 'node:crypto';
const A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const shared=JSON.parse(fs.readFileSync('tests/fixtures/cf022-supervisor-core.json','utf8'));
function load(fetcher=()=>{throw Error('Unexpected network');}){
 const cache={};function mod(file){if(cache[file])return cache[file];const m={exports:{}};vm.runInNewContext(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{module:m,exports:m.exports,URL,URLSearchParams,Response,Request,Headers,TextEncoder,TextDecoder,AbortController,AbortSignal,crypto:webcrypto,fetch:fetcher,require(id){if(id==='@/features/flow/lib/analysis-request')return mod('src/features/flow/lib/analysis-request.ts');throw Error('Closed module registry');}},{timeout:100});cache[file]=m.exports;return m.exports;}
 return {h:mod('src/features/supervisor/lib/supervisor-request.ts'),flow:mod('src/features/flow/lib/analysis-request.ts')};
}
const draft={original_query:'삼성전자 수급과 차트',answers:[],revision:0};
async function plan(h){const value={schema_version:'supervisor.core.v1',policy_version:'supervisor.flow-core.1',frame:{original_query:draft.original_query,query_sha256:await h.hash(draft.original_query),revision:0,answers:[],mentions:[],requested_views:['flow','technical'],negated_views:[],conditions:[],unresolved_slots:[],interpretation_source:'deterministic'},resolution:{status:'resolved',reason:'exact_match',stock:{stock_code:'005930',stock_name:'삼성전자',market:'KOSPI'},candidates:[]},candidate_ref:'a'.repeat(64),requested_views:['flow','technical'],capabilities:[{view:'flow',connected:true,reason:'connected_flow'}],selected_views:['flow'],status:'scope_confirmation',partial:true,required_waivers:[]};return {...value,plan_hash:await h.hash(value)};}
function store(value){const records=new Map(Object.entries(value??{}));return {getItem:k=>records.get(k)??null,setItem:(k,v)=>records.set(k,v),removeItem:k=>records.delete(k)};}
for(const c of shared.cases)test('shared original meaning fixture retains raw query: '+c.query,()=>{const {h}=load();const d=h.draftValue({original_query:c.query,answers:[],revision:0});assert.equal(d.original_query,c.query);});
test('existing Flow pending without URL is prioritized, never deleted or converted to a Sup key',()=>{const {h,flow}=load();const legacy=flow.freshPending('005930','기존 질문');const saved=store();flow.writePending(saved,A,legacy);const before=saved.getItem(flow.pendingKey(A));assert.equal(h.legacyFlowRecovery(saved,A,null),true);assert.equal(h.legacyFlowRecovery(saved,A,B),false);assert.equal(saved.getItem(flow.pendingKey(A)),before);assert.equal(h.readPending(saved,A),null);});
test('direct link recovery without matching fixed pending is GET-only',async()=>{const {h}=load();const p=h.freshPending(draft,await plan(h),true,[]);assert.equal(h.canReplayCore(A,null),false);assert.equal(h.canReplayCore(A,p),false);p.supervisor_id=A;assert.equal(h.canReplayCore(A,p),true);assert.equal(h.canReplayCore(B,p),false);});
test('uppercase and mixed UUID links use canonical comparison',()=>{const {h}=load();assert.equal(h.matchesUrl('http://localhost:3200/research?supervisor_id='+A.toUpperCase(),A),true);assert.equal(h.matchesUrl('http://localhost:3200/research?supervisor_id='+A+'&supervisor_id='+A,A),false);assert.equal(h.matchesUrl('http://localhost:3200/research?analysis_id='+A,null),false);});
test('401 from session and core invalidates authentication, ordinary503 remains retryable',()=>{const {h,flow}=load();assert.equal(h.requiresReauthentication(new flow.AnalysisHttpError(401)),true);assert.equal(h.requiresReauthentication(new h.CoreHttpError(401)),true);assert.equal(h.requiresReauthentication(new flow.AnalysisAccountChanged()),true);assert.equal(h.requiresReauthentication(new h.CoreHttpError(503)),false);});
test('focus/exclude and original versus explicitly waived conditions remain distinct',()=>{const {h}=load();assert.notEqual(h.conditionLabel('focus'),h.conditionLabel('exclude'));assert.match(h.conditionDisposition('c0','unsupported',null),/동의 전/);assert.match(h.conditionDisposition('c0','unsupported',{waived_conditions:['c0']}),/명시 동의/);assert.match(h.conditionDisposition('c1','unsupported',{waived_conditions:['c0']}),/동의 전/);});
test('actual prepare function checks owner twice, bounded envelope/hash, and preserves original draft',async()=>{let requests=[];let target;const {h}=load(async(url,init={})=>{requests.push([url,init]);return url==='/api/auth/session'?Response.json({user_id:A,csrf_token:'fresh'}):Response.json({schema_version:'supervisor.core.v1',request_id:A,trace_id:B,data:target,error:null});});target=await plan(h);const result=await h.coreRequest('prepare',draft,A,new AbortController().signal,()=>true);assert.equal(result.plan_hash,target.plan_hash);assert.equal(requests.length,3);assert.equal(requests[1][0],'/api/private/supervisor/core/prepare');assert.equal(JSON.parse(requests[1][1].body).original_query,draft.original_query);assert.equal(requests[1][1].headers['X-CSRF-Token'],'fresh');assert.equal(requests.filter(([u])=>u.includes('/requests')).length,0);});
for(const when of ['before','after'])test('account changed '+when+' cannot adopt plan or send confirm',async()=>{let sessions=0,posts=0,target;const {h}=load(async url=>{if(url==='/api/auth/session')return Response.json({user_id:when==='before'||++sessions===2?B:A,csrf_token:'fresh'});posts++;return Response.json({schema_version:'supervisor.core.v1',request_id:A,trace_id:B,data:target,error:null});});target=await plan(h);await assert.rejects(h.coreRequest('prepare',draft,A,new AbortController().signal,()=>true));assert.equal(posts,when==='before'?0:1);});
test('late first session after generation/cancel does not issue planning or execution HTTP',async()=>{let release,entered;const reached=new Promise(r=>{entered=r;});let posts=0,current=true;const {h}=load(async url=>{if(url==='/api/auth/session'){entered();return new Promise(r=>{release=r;});}posts++;throw Error('Forbidden POST');});const job=h.coreRequest('prepare',draft,A,new AbortController().signal,()=>current);await reached;current=false;release(Response.json({user_id:A,csrf_token:'fresh'}));await assert.rejects(job);assert.equal(posts,0);});
test('fixed pending survives503 and is owner-scoped; no result/token is stored',async()=>{const {h}=load();const pending=h.freshPending(draft,await plan(h),true,[]),saved=store();h.writePending(saved,A,pending);const before=saved.getItem(h.pendingKey(A));assert.equal(h.readPending(saved,B),null);assert.equal(JSON.stringify(h.readPending(saved,A).confirm),JSON.stringify(pending.confirm));assert.equal(saved.getItem(h.pendingKey(A)),before);assert.doesNotMatch(before,/csrf_token|session|result_json/);});
test('production wiring preserves fixed replay/no-op timer identity and hides401 (source assertions)',()=>{const source=fs.readFileSync('src/features/supervisor/components/supervisor-session.tsx','utf8')+fs.readFileSync('src/features/supervisor/components/supervisor-chat.tsx','utf8');for(const part of ['legacyFlowRecovery(sessionStorage','<AnalysisEntry analysisId={null}/>','requiresReauthentication(e)','timer.current.stop();','timer.current.start(current,()=>void verify(),next.delay)','!canReplayCore(known.current,pending.current)','verifiedHref.current!==window.location.href'])assert.ok(source.includes(part),part);const view=fs.readFileSync('src/features/supervisor/components/chat-view.tsx','utf8');assert.ok(view.includes('!p.replayable'));assert.ok(view.includes('conditionDisposition'));assert.doesNotMatch(view,/dangerouslySetInnerHTML|iframe/);});

test('multi-stock/scope clarification uses the same stock answer typed slot as production ChatView',()=>{const {h}=load();assert.equal(h.clarificationSlot('multi_stock'),'stock');assert.equal(h.clarificationSlot('scope'),'stock');assert.equal(h.clarificationSlot('views'),'views');const source=fs.readFileSync('src/features/supervisor/components/chat-view.tsx','utf8');assert.ok(source.includes('clarificationSlot(slot),value)'));});
for(const broken of ['json','denied'])test('known ID remains GET-only with '+broken+' pending storage',async()=>{let gets=0;const {h}=load(async url=>{if(url==='/api/auth/session')return Response.json({user_id:A,csrf_token:'fresh'});gets++;return Response.json({schema_version:'supervisor.core.v1',request_id:A,trace_id:B,data:{supervisor_id:A,plan:null,plan_status:'deleted',effective_scope:null,flow:null,views:[],coverage:'deleted'},error:null});});const storage=broken==='json'?store({[h.pendingKey(A)]:'{bad'}):()=>{throw Error('Synthetic storage denied');};const recovery=h.loadCoreRecovery(storage,A,A);assert.equal(recovery.storageReadable,false);assert.equal(h.canReplayCore(A,recovery.pending),false);const out=await h.coreRequest('get',A,A,new AbortController().signal,()=>true);assert.equal(out.plan_status,'deleted');assert.equal(gets,1);});
test('an actual confirm503 response preserves the exact fixed pending and sends only once',async()=>{let posts=0;const {h}=load(async url=>{if(url==='/api/auth/session')return Response.json({user_id:A,csrf_token:'fresh'});posts++;return Response.json({schema_version:'supervisor.core.v1',request_id:A,trace_id:B,data:null,error:{code:'SERVICE_UNAVAILABLE',message:'fixed'}},{status:503});});const saved=store(),pending=h.freshPending(draft,await plan(h),true,[]);h.writePending(saved,A,pending);const before=saved.getItem(h.pendingKey(A));await assert.rejects(h.coreRequest('confirm',pending.confirm,A,new AbortController().signal,()=>true),e=>e.status===503);assert.equal(posts,1);assert.equal(saved.getItem(h.pendingKey(A)),before);});

test('production observation timer rejects replaced, stopped and stale generation callbacks',()=>{const {h}=load();let queue=[],cancelled=[],runs=0,current=true;const timer=new h.CoreObservationTimer(run=>{queue.push(run);return queue.length;},id=>cancelled.push(id));timer.start(()=>current,()=>runs++,1);const old=queue[0];timer.stop();old();assert.equal(runs,0);timer.start(()=>current,()=>runs++,1);const replaced=queue[1];timer.start(()=>current,()=>runs++,1);replaced();assert.equal(runs,0);current=false;queue[2]();assert.equal(runs,0);current=true;timer.start(()=>current,()=>runs++,1);queue[3]();assert.equal(runs,1);assert.ok(cancelled.length>=3);});

for(const c of shared.clarifications)test('production typed clarification wire: '+c.unresolved_slot,()=>{const {h}=load();const next=h.clarifiedDraft({original_query:c.query,answers:[],revision:0},h.clarificationSlot(c.unresolved_slot),c.value);assert.equal(next.original_query,c.query);assert.equal(next.answers[0].slot,c.wire_slot);assert.equal(next.answers[0].value,c.value);assert.equal(next.revision,1);});


test('CF023 policy2 validated fixtures use actual hash validators and first-adoption TTL only',async()=>{
 const {h}=load();const cases=JSON.parse(fs.readFileSync('tests/fixtures/cf023-supervisor-meaning.json','utf8')).validated_plans;
 for(const item of cases){const p=await h.planValue(item.plan,item.draft);assert.equal(p.policy_version,'supervisor.flow-core.2');}
 const p=cases.find(c=>c.plan.status==='ready').plan;
 const preparation={preparation_id:A,state:'ready',plan:p,created_at:'2026-11-09T00:00:00Z',expires_at:'2026-11-09T00:10:00Z',meaning_status:'deterministic',consumed_binding_id:null};
 assert.equal(h.canAdoptPreparation(preparation,p,Date.parse('2026-11-09T00:09:59Z')),true);
 assert.equal(h.canAdoptPreparation(preparation,p,Date.parse(preparation.expires_at)),false);
 const pending=h.freshPending(cases[0].draft,p,false,[],A);assert.equal(pending.confirm.preparation_id,A);
 assert.equal(h.canReplayCore(null,pending),true);assert.equal(h.pendingValue(pending).confirm.preparation_id,A);
});

test('CF023 preparation key/body/ID binding survives actual503, rejects mixed ID and reads known result via GET',async()=>{
 let requests=[],status=503,responseData=null;
 const {h}=load(async(url,init={})=>{requests.push([url,init]);if(url==='/api/auth/session')return Response.json({user_id:A,csrf_token:'fresh'});return Response.json({schema_version:'supervisor.core.v1',request_id:A,trace_id:B,data:status===200?responseData:null,error:status===200?null:{code:'SERVICE_UNAVAILABLE',message:'fixed'}},{status});});
 const saved=store(),value=await h.newPreparation({original_query:'삼성전자 수급',answers:[],revision:0});
 await h.writePreparation(saved,A,value);const before=saved.getItem(h.preparationKey(A));
 await assert.rejects(h.preparationRequest('post',value.body,A,new AbortController().signal,()=>true),e=>e.status===503);
 assert.equal(saved.getItem(h.preparationKey(A)),before);
 const bound=await h.bindPreparation(value,A);await h.writePreparation(saved,A,bound);
 await assert.rejects(h.preparePendingValue({...bound,preparation_id:B}));
 const item=JSON.parse(fs.readFileSync('tests/fixtures/cf023-supervisor-meaning.json','utf8')).validated_plans.find(c=>c.plan.status==='ready');
 responseData={preparation_id:A,state:'ready',plan:item.plan,created_at:'2026-11-09T00:00:00Z',expires_at:'2026-11-09T00:10:00Z',meaning_status:'deterministic',consumed_binding_id:null};status=200;
 const result=await h.preparationRequest('get',A,A,new AbortController().signal,()=>true);
 await h.planValue(result.plan,value.body.draft);
 await assert.rejects(h.planValue(result.plan,{...value.body.draft,original_query:'다른 질문'}));
 assert.equal(requests.at(-2)[1].method,'GET');assert.equal(requests.filter(([u])=>u.includes('/requests')).length,0);
});

for(const reason of ['cancel','URL','hidden'])test('CF023 delayed session then '+reason+' sends no preparation POST',async()=>{
 let release,entered,posts=0,current=true;const waiting=new Promise(r=>{entered=r;});
 const {h}=load(async url=>{if(url==='/api/auth/session'){entered();return new Promise(resolve=>{release=resolve;});}posts++;throw Error('Unexpected POST');});
 const value=await h.newPreparation({original_query:'삼성전자 수급',answers:[],revision:0});
 const job=h.preparationRequest('post',value.body,A,new AbortController().signal,()=>current);await waiting;current=false;release(Response.json({user_id:A,csrf_token:'fresh'}));await assert.rejects(job);assert.equal(posts,0);
});

test('CF023 terminal first-adoption rejections retain fixed codes; uncertain503 remains distinct',async()=>{
 for(const code of ['PREPARATION_EXPIRED','PREPARATION_DELETED','PREPARATION_CONSUMED']){
  const {h}=load(async url=>url==='/api/auth/session'?Response.json({user_id:A,csrf_token:'fresh'}):Response.json({schema_version:'supervisor.core.v1',request_id:A,trace_id:B,data:null,error:{code,message:'fixed'}},{status:409}));
  const p=await plan(h);await assert.rejects(h.coreRequest('confirm',h.freshPending(draft,p,true,[]).confirm,A,new AbortController().signal,()=>true),e=>e.status===409&&e.code===code);
 }
});

test('CF023 controller moved once; fixture mounts production Session and uses native HTTP (source assertions)',()=>{
 const wrapper=fs.readFileSync('src/features/supervisor/components/supervisor-chat.tsx','utf8'),session=fs.readFileSync('src/features/supervisor/components/supervisor-session.tsx','utf8'),fixture=fs.readFileSync('tests/integration/supervisor/chat-browser-fixture.mjs','utf8');
 assert.doesNotMatch(wrapper,/useState|fetchSession|function Conversation/);assert.match(wrapper,/SupervisorSession/);
 assert.match(session,/preparationKey\(user\)/);assert.match(session,/known.current=null/);assert.match(session,/canAdoptPreparation/);assert.match(session,/planValue\(result.plan,prepared.body.draft\)/);
 assert.match(fixture,/SupervisorSession/);assert.doesNotMatch(fixture,/function FakeApp|verified:true|fetchSession.*=>/);
});


test('new conversation cannot discard unknown ACK, running or result_ready fixed keys',async()=>{
 const {h}=load(),p=await plan(h),pending=h.freshPending(draft,p,true,[]);
 assert.equal(h.canResetConversation(pending,null,null),false);
 for(const state of ['running','unknown','result_ready'])assert.equal(h.canResetConversation(pending,A,{plan_status:'confirmed',flow:{state}}),false);
 for(const state of ['stored','failed'])assert.equal(h.canResetConversation(pending,A,{plan_status:'confirmed',flow:{state}}),true);
 assert.equal(h.canResetConversation(pending,A,{plan_status:'deleted',flow:null}),true);
});
