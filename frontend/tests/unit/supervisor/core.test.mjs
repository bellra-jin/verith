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

// CF027: execute actual production callbacks/pure functions with injected IO.
// These are not mounted React or effect lifecycle tests.
function sessionSource(){return fs.readFileSync('src/features/supervisor/components/supervisor-session.tsx','utf8');}
function actualSessionFunction(name,context={},callback=false){
 const source=sessionSource(),tree=ts.createSourceFile('session.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let selected;
 function visit(node){if(!callback&&ts.isFunctionDeclaration(node)&&node.name?.text===name)selected=node;if(callback&&ts.isVariableDeclaration(node)&&node.name.getText(tree)===name&&node.initializer&&ts.isCallExpression(node.initializer)&&node.initializer.expression.getText(tree)==='useCallback')selected=node.initializer.arguments[0];ts.forEachChild(node,visit);}visit(tree);assert.ok(selected,name);
 const text=callback?'const actual='+selected.getText(tree)+';module.exports=actual;':selected.getText(tree).replace(/^export /,'')+';module.exports='+name+';';
 const m={exports:{}};vm.runInNewContext(ts.transpileModule(text,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{module:m,exports:m.exports,...context},{timeout:100});return m.exports;
}
test('CF027 storage latch closes on marker/malformed/unreadable state and session generations reject stale visibility/URL/unmount',()=>{
 const stored=actualSessionFunction('storedReauthenticationRequired');assert.equal(stored(()=>null),false);
 for(const value of ['required','',JSON.stringify({unexpected:true})])assert.equal(stored(()=>value),true);assert.equal(stored(()=>{throw Error('storage denied');}),true);
 const accepts=actualSessionFunction('acceptsSessionGeneration');assert.equal(accepts(2,2,true,'/research','/research',true),true);
 for(const input of [[1,2,true,'/research','/research',true],[2,2,false,'/research','/research',true],[2,2,true,'/research','/other',true],[2,2,true,'/research','/research',false]])assert.equal(accepts(...input),false);
});
function parentCallbacks({required=true,fetcher}={}){
 const events=[],state={required,provenance:null},context={mounted:{current:true},generation:{current:1},lock:{current:false},owner:{current:null},authHref:{current:null},ownerFingerprint:{current:null},controller:{current:null},deadline:{current:null},supervisorId:null,AbortController,document:{visibilityState:'visible'},window:{location:{href:'http://synthetic/research'}},sessionStorage:{},setGrant:v=>events.push(['grant',v]),setChecking:v=>events.push(['checking',v]),clearTimeout:()=>events.push(['clear']),setTimeout(fn,ms){context.fire=fn;assert.equal(ms,15000);return 1;},matchesUrl:()=>true,requiresExplicitReauthentication:()=>state.required,requireReauthentication:()=>{state.required=true;events.push(['latch']);},acknowledgeReauthentication:()=>{state.required=false;events.push(['unlatch']);},hash:async user=>user===A?'a'.repeat(64):'b'.repeat(64),previousVerifiedOwner:()=>state.provenance,rememberVerifiedOwner:fingerprint=>{state.provenance=fingerprint;return true;},legacyFlowRecovery:()=>false,fetchSession:fetcher};
 context.acceptsSessionGeneration=actualSessionFunction('acceptsSessionGeneration');
 context.retire=actualSessionFunction('retire',context,true);context.pause=actualSessionFunction('pause',context,true);
 // Callback functions capture the same ref objects. Mutable IO below is set before each extraction.
 return {context,events,state,callback:name=>actualSessionFunction(name,context,true)};
}
test('CF027 actual parent check requires explicit reauth and merges duplicate clicks until child GET verification',async()=>{
 let release,calls=0;const p=parentCallbacks({fetcher:()=>{calls++;return new Promise(resolve=>{release=resolve;});}}),check=p.callback('checkSession');
 await check(false);assert.equal(calls,0);const first=check(true);const second=check(true);assert.equal(calls,1);assert.equal(p.context.lock.current,true);release({user_id:A});await Promise.all([first,second]);
 assert.equal(p.events.filter(([name])=>name==='grant').at(-1)[1].user,A);assert.equal(p.events.filter(([name])=>name==='grant').at(-1)[1].manual,true);assert.equal(p.state.required,true);assert.equal(p.context.lock.current,true);
 p.callback('onVerified')(A,p.context.generation.current);assert.equal(p.context.lock.current,false);assert.equal(p.state.required,false);
});
test('CF027 actual parent callbacks keep 401 latch until explicit action and ignore older owner/epoch callbacks',async()=>{
 const p=parentCallbacks({required:false,fetcher:async()=>({user_id:A})});await p.callback('checkSession')();const epoch=p.context.generation.current;
 p.callback('onAccountChange')(B,epoch);p.callback('onAccountChange')(A,epoch-1);assert.equal(p.state.required,false);
 p.callback('onAccountChange')(A,epoch);assert.equal(p.state.required,true);const before=p.events.length;
 await p.callback('checkSession')();assert.equal(p.events.slice(before).some(([name,value])=>name==='grant'&&value!==null),false);
 p.callback('onVerified')(A,epoch);assert.equal(p.state.required,true);
});
test('CF027 actual parent check cannot adopt late session200 after generation/URL/visibility/unmount invalidation',async()=>{
 for(const reason of ['generation','URL','hidden','unmount']){
  let release;const p=parentCallbacks({fetcher:()=>new Promise(resolve=>{release=resolve;})}),task=p.callback('checkSession')(true);
  if(reason==='generation')p.context.generation.current++;if(reason==='URL')p.context.window.location.href='http://synthetic/other';if(reason==='hidden')p.context.document.visibilityState='hidden';if(reason==='unmount')p.context.mounted.current=false;
  release({user_id:A});await task;assert.equal(p.events.some(([name,value])=>name==='grant'&&value!==null),false);
 }
});
test('CF027 actual parent failure/deadline keeps latch, retires request, and never creates a recovery POST/key',async()=>{
 const p=parentCallbacks({fetcher:async()=>{throw Error('synthetic401');}});await p.callback('checkSession')(true);assert.equal(p.state.required,true);assert.equal(p.context.lock.current,false);assert.equal(p.events.at(-2)[0],'grant');
 let release;const timed=parentCallbacks({fetcher:()=>new Promise(resolve=>{release=resolve;})}),task=timed.callback('checkSession')(true);timed.context.fire();assert.equal(timed.context.controller.current,null);release({user_id:A});await task;assert.equal(timed.events.some(([name,value])=>name==='grant'&&value!==null),false);
});
test('CF027 stable callbacks/effect wiring and actual-observation marker are preserved (source assertions, not lifecycle)',()=>{
 const source=sessionSource();assert.match(source,/const onAccountChange=useCallback/);assert.doesNotMatch(source,/\[retry,supervisorId\]|setRetry/);
 assert.match(source,/reauthentication\.v1/);assert.match(source,/if\(!manual&&requiresExplicitReauthentication\(\)\)/);
 assert.match(source,/manual&&automaticObservationStarted.current/);assert.match(source,/void verify\(manualRecovery\)/);assert.match(source,/automaticObservationStarted.current=false/);assert.match(source,/disabled=\{rechecking\}/);
 assert.match(source,/onAccountChange=\{onAccountChange\}/);assert.match(source,/onAccountChange,onVerified,onVerificationFailed\]/);
});
function fixtureFunction(name,context){
 const source=fs.readFileSync('tests/integration/supervisor/chat-browser-fixture.mjs','utf8'),tree=ts.createSourceFile('fixture.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const declaration=tree.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text===name);assert.ok(declaration,name);
 return vm.runInNewContext(declaration.getText(tree)+';'+name+';',context,{timeout:100});
}
test('CF027 actual fixture counts attempts before errors and caps whole instance128 / rolling2s24',()=>{
 for(const mode of ['total','rolling']){
  const attempts={total:0,session:0,core:0,GET:0,POST:0,DELETE:0},failures=[],record=fixtureFunction('recordAttempt',{attempts,recentAttempts:[],failScenario:reason=>failures.push(reason)});
  const limit=mode==='total'?128:24;
  for(let n=0;n<limit;n++)assert.equal(record(n%2?'core':'session','GET',mode==='total'?n*2001:0),true);
  assert.equal(record('core','GET',mode==='total'?limit*2001:0),false);assert.equal(attempts.total,limit+1);assert.deepEqual(failures,['REQUEST_ATTEMPT_LIMIT']);
 }
});
test('CF027 actual fixture arm/collect is bounded30s and observation-only; deadline is failure',()=>{
 let expiry,clears=0;const scenario={status:'idle'},attempts={total:2,session:1,core:1,GET:2,POST:0,DELETE:0},failures=[],context={scenario,attempts,failureWatchers:new Set([{record:{ready:true,disconnected:false}}]),scenarioTimer:null,Date:{now:()=>100},setTimeout(fn,ms){expiry=fn;assert.equal(ms,30000);return 1;},clearTimeout(){clears++;},failScenario:r=>failures.push(r),console:{log(){}}};
 const control=fixtureFunction('controlScenario',context);assert.equal(control('reauth'),true);assert.equal(control('rerender'),false);attempts.total+=3;attempts.session+=2;attempts.core++;
 assert.equal(control('collect'),true);assert.equal(scenario.delta.total,3);assert.equal(scenario.status,'collected');assert.equal(clears,1);assert.equal(control('stale-session'),true);expiry();assert.deepEqual(failures,['SCENARIO_DEADLINE']);assert.equal(control('arbitrary'),false);
});
test('CF027 actual one-shot session snapshot keeps previous owner/status while later controls change',async()=>{
 const state={account:'A',authStatus:200},context={state,currentOwner:()=>state.account==='A'?A:B,nonce:'synthetic',holdNextSession:true,heldSession:null,delays:new Map(),setTimeout:(_fn,ms)=>{assert.equal(ms,15000);return 1;},clearTimeout(){}};
 const snapshot=fixtureFunction('sessionResponseSnapshot',context)();const waiting=fixtureFunction('waitForSessionRelease',context)();
 assert.equal(context.holdNextSession,false);state.account='B';state.authStatus=401;context.heldSession();await waiting;
 assert.equal(snapshot.status,200);assert.equal(snapshot.body.user_id,A);assert.equal(context.heldSession,null);assert.equal(context.delays.size,0);
});

test('CF027 actual tab latch survives route remount and leaves fixed pending bytes untouched; uncertain storage stays closed',()=>{
 const source=sessionSource(),tree=ts.createSourceFile('session.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
 const names=['storedReauthenticationRequired','requiresExplicitReauthentication','requireReauthentication','acknowledgeReauthentication'];
 const selected=tree.statements.filter(node=>ts.isFunctionDeclaration(node)&&names.includes(node.name?.text)||ts.isVariableStatement(node)&&node.declarationList.declarations.some(d=>['reauthenticationKey','tabReauthenticationRequired'].includes(d.name.getText(tree))));
 const code=selected.map(n=>n.getText(tree)).join('\n')+'\nmodule.exports={'+names.join(',')+'};';
 const records=new Map([['fixed-pending','exact-original-body-and-key']]);let denied=false;
 const storage={getItem:key=>{if(denied)throw Error('storage unavailable');return records.get(key)??null;},setItem:(key,value)=>{if(denied)throw Error('storage unavailable');records.set(key,value);},removeItem:key=>{if(denied)throw Error('storage unavailable');records.delete(key);}};
 function mount(){const m={exports:{}};vm.runInNewContext(ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{module:m,exports:m.exports,sessionStorage:storage},{timeout:100});return m.exports;}
 const first=mount();assert.equal(first.requiresExplicitReauthentication(),false);first.requireReauthentication();assert.equal(first.requiresExplicitReauthentication(),true);
 const remounted=mount();assert.equal(remounted.requiresExplicitReauthentication(),true);assert.equal(records.get('fixed-pending'),'exact-original-body-and-key');
 remounted.acknowledgeReauthentication();assert.equal(remounted.requiresExplicitReauthentication(),false);assert.equal(records.get('fixed-pending'),'exact-original-body-and-key');
 denied=true;assert.equal(mount().requiresExplicitReauthentication(),true);remounted.requireReauthentication();remounted.acknowledgeReauthentication();assert.equal(remounted.requiresExplicitReauthentication(),true);
});

test('CF027 prepared fixture contains syntactically valid production bundle and finite scenario controls (not mounted)',()=>{
 const source=fs.readFileSync('tests/integration/supervisor/chat-browser-fixture.mjs','utf8'),tree=ts.createSourceFile('fixture.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 assert.equal(tree.parseDiagnostics.length,0);
 const declarations=tree.statements.filter(ts.isVariableStatement).flatMap(s=>[...s.declarationList.declarations]);const bundle=declarations.find(d=>d.name.getText(tree)==='bundle').initializer;assert.ok(ts.isTemplateExpression(bundle));
 const replacements=expression=>expression.startsWith('Object.entries(registry)')?'':expression==='validateFixtureTarget.toString()'?'function validateFixtureTarget(){return {id:null};}':expression==='fixtureAdapter.toString()'?'function fixtureAdapter(){}':'"synthetic"';
 const script=bundle.head.text+bundle.templateSpans.map(span=>replacements(span.expression.getText(tree))+span.literal.text).join('');
 assert.equal(ts.createSourceFile('bundle.js',script,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS).parseDiagnostics.length,0);
 assert.match(source,/recordAttempt\(req.url/);assert.match(source,/CF027_FIXTURE_ATTEMPTS/);assert.match(source,/sessionResponseSnapshot\(\)/);assert.match(source,/terminal.finish\('failed'\)/);
});

test('CF027 verified owner provenance survives hide/retire and remount, automatic A-to-B latches but explicit B can verify',async()=>{
 let sessionUser=A;const p=parentCallbacks({required:false,fetcher:async()=>({user_id:sessionUser})});
 await p.callback('checkSession')();p.callback('onVerified')(A,p.context.generation.current);assert.equal(p.state.provenance,'a'.repeat(64));
 p.callback('pause')();assert.equal(p.context.owner.current,null);assert.equal(p.state.provenance,'a'.repeat(64));
 sessionUser=B;const before=p.events.length;await p.callback('checkSession')();assert.equal(p.state.required,true);assert.equal(p.events.slice(before).some(([name,value])=>name==='grant'&&value!==null),false);
 // A new parent instance reads the tab provenance, not the old active callback ref.
 const remounted=parentCallbacks({required:false,fetcher:async()=>({user_id:B})});remounted.state.provenance=p.state.provenance;
 await remounted.callback('checkSession')();assert.equal(remounted.state.required,true);assert.equal(remounted.events.some(([name,value])=>name==='grant'&&value!==null),false);
 await remounted.callback('checkSession')(true);const granted=remounted.events.filter(([name])=>name==='grant').at(-1)[1];assert.equal(granted.user,B);assert.equal(granted.manual,true);
 remounted.callback('onVerified')(B,remounted.context.generation.current);assert.equal(remounted.state.provenance,'b'.repeat(64));assert.equal(remounted.state.required,false);
});
test('CF027 actual persisted owner fingerprint is a deny provenance, survives module remount and fails closed on drift/unreadable metadata',()=>{
 const source=sessionSource(),tree=ts.createSourceFile('session.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),names=['previousVerifiedOwner','rememberVerifiedOwner'];
 const selected=tree.statements.filter(node=>ts.isFunctionDeclaration(node)&&names.includes(node.name?.text)||ts.isVariableStatement(node)&&node.declarationList.declarations.some(d=>['verifiedOwnerKey','tabVerifiedOwnerFingerprint'].includes(d.name.getText(tree))));
 const code=ts.transpileModule(selected.map(n=>n.getText(tree)).join('\n')+';module.exports={'+names.join(',')+'};',{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const values=new Map([['fixed-pending','unchanged']]);let unavailable=false;const storage={getItem:key=>{if(unavailable)throw Error('unavailable');return values.get(key)??null;},setItem:(key,value)=>{if(unavailable)throw Error('unavailable');values.set(key,value);}};
 function mount(){const m={exports:{}};vm.runInNewContext(code,{module:m,exports:m.exports,sessionStorage:storage},{timeout:100});return m.exports;}
 const a=mount();assert.equal(a.previousVerifiedOwner(),null);assert.equal(a.rememberVerifiedOwner('a'.repeat(64)),true);assert.equal(mount().previousVerifiedOwner(),'a'.repeat(64));assert.equal(values.get('fixed-pending'),'unchanged');assert.equal(a.rememberVerifiedOwner(A),false);
 const key=[...values.keys()].find(k=>k!=='fixed-pending');values.set(key,'b'.repeat(64));assert.equal(a.previousVerifiedOwner(),'unavailable');unavailable=true;assert.equal(mount().previousVerifiedOwner(),'unavailable');assert.equal(a.rememberVerifiedOwner('b'.repeat(64)),false);
});

test('CF027 actual failure watcher receives scenario failure without a user click, never polls/retries, and ignores own abort',async()=>{
 for(const kind of ['timeout','cap','normal','transport','malformed','aborted']){
  let respond,failures=0,calls=0;const c=new AbortController();
  const watch=fixtureFunction('watchFixtureFailure',{AbortController,Date:{now:()=>0},setTimeout:()=>1,clearTimeout(){},postFixtureWatchAck:async()=>{},fetch:()=>{calls++;return new Promise(resolve=>{respond=resolve;});}});
  const task=watch(c.signal,'synthetic',()=>failures++);assert.equal(calls,1);assert.equal(failures,0);
  if(kind==='aborted')c.abort();
  if(kind==='transport')respond({ok:false});
  else respond({ok:true,headers:{get:name=>name==='x-fixture-watch'?'registered':name==='x-fixture-watch-id'?'1':'590000'},text:async()=>kind==='malformed'?'{}':JSON.stringify({failed:kind!=='normal',reason:kind==='normal'?null:kind==='cap'?'REQUEST_ATTEMPT_LIMIT':'SCENARIO_DEADLINE',terminal:true})});
  await task;assert.equal(calls,1);assert.equal(failures,['normal','aborted'].includes(kind)?0:1);
 }
});
test('CF027 actual server failure channel settles before terminal drain and removes its bounded timer/connection',async()=>{
 const {EventEmitter}=await import('node:events');const watchers=new Set();let callback,scheduled,cleared=0,resolved=false;
 const res=new EventEmitter();res.writeHead=(status,headers)=>{assert.equal(status,200);assert.equal(headers['X-Fixture-Watch'],'registered');};res.flushHeaders=()=>{};res.end=(body,done)=>{callback=()=>{assert.equal(JSON.parse(body).reason,'SCENARIO_DEADLINE');done();};};
 const context={failureWatchers:watchers,failureDelivery:{registered:0,sent:0,writeCompleted:0,closedBeforeBody:0,readyAcks:0,commitAcks:0},watchRecords:new Map(),failureTargets:new Set(),console:{log(){}},scenario:{status:'armed'},expires:590000,Date:{now:()=>1000},setTimeout(fn,ms){scheduled=fn;assert.ok([5000,589000].includes(ms));return 1;},clearTimeout(){cleared++;}};
 const task=fixtureFunction('waitForFixtureFailure',context)(res).then(()=>{resolved=true;});assert.equal(watchers.size,1);
 fixtureFunction('acknowledgeFixtureWatch',context)({watch_id:1,action:'ready',reason:null},true);fixtureFunction('notifyFailureWatchers',context)(true,'SCENARIO_DEADLINE');assert.equal(resolved,false);assert.equal(typeof callback,'function');callback();await task;assert.equal(watchers.size,0);assert.equal(resolved,true);assert.ok(cleared>0);assert.equal(res.listenerCount('close'),0);assert.equal(typeof scheduled,'function');
});

test('CF027 real fixture failure callback unmounts/locks UI and stale refresh/control cannot overwrite failure (injected callbacks, not React)',async()=>{
 const source=fs.readFileSync('tests/integration/supervisor/chat-browser-fixture.mjs','utf8'),tree=ts.createSourceFile('fixture.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const declarations=tree.statements.filter(ts.isVariableStatement).flatMap(s=>[...s.declarationList.declarations]),bundle=declarations.find(d=>d.name.getText(tree)==='bundle').initializer;
 const script=bundle.head.text+bundle.templateSpans.map(span=>(span.expression.getText(tree).startsWith('Object.entries(registry)')?'':span.expression.getText(tree)==='validateFixtureTarget.toString()'?'function validateFixtureTarget(){}':span.expression.getText(tree)==='fixtureAdapter.toString()'?'function fixtureAdapter(){}':'"synthetic"')+span.literal.text).join('');
 const parsed=ts.createSourceFile('bundle.js',script,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS),functions={};
 function visit(node){if(ts.isVariableDeclaration(node)&&['failClosed','refresh','control'].includes(node.name.getText(parsed)))functions[node.name.getText(parsed)]=node.initializer;ts.forEachChild(node,visit);}visit(parsed);
 for(const operation of ['refresh','control']){
  let release;const stats=[],states=[],context={lock:{current:false},failure:{current:false},failureReason:{current:null},watch:{current:'registered'},scenarioClock:{current:{expired:()=>false,arm:()=>true,clear(){}}},failed:false,setFailed:value=>states.push(value),setStats:value=>stats.push(value),fetch:()=>new Promise(resolve=>{release=resolve;})};
  const failureCallback=functions.failClosed.arguments[0].getText(parsed);context.failClosed=vm.runInNewContext('('+failureCallback+')',context,{timeout:100});
  const callback=vm.runInNewContext('('+functions[operation].getText(parsed)+')',context,{timeout:100});const pending=callback({scenario:'collect'});context.failClosed();
  release({ok:true,json:async()=>({scenario:{status:'collected'}})});await pending;
  assert.equal(context.failure.current,true);assert.equal(context.lock.current,true);assert.deepEqual(states,[true]);assert.equal(stats.length,1);assert.match(stats[0],/fixture 시나리오 실패/);
 }
 assert.match(script,/failed\?null:React.createElement\(Session/);assert.match(script,/return\(\)=>c.abort\(\)/);
});

test('CF027 actual client arm deadline fails closed without server delivery; collect/terminal/unmount cancel and stale callbacks cannot affect a later case',()=>{
 let now=100,failures=0,next=0;const callbacks=new Map(),cancelled=[];
 const create=fixtureFunction('createClientScenarioDeadline',{});
 const clock=create(()=>failures++,()=>now,(fn,ms)=>{const id=++next;callbacks.set(id,fn);assert.ok(ms>0&&ms<=30000);return id;},id=>cancelled.push(id));
 assert.equal(clock.arm(now),true);const old=callbacks.get(1);clock.clear();old();assert.equal(failures,0);
 clock.arm(now);now+=30000;callbacks.get(2)();assert.equal(failures,1);
 clock.arm(now);now+=30001;assert.equal(clock.expired(),true);assert.equal(failures,2);
 // A late successful arm ACK must not get a renewed thirty seconds.
 assert.equal(clock.arm(now-30001),false);assert.equal(failures,3);
 for(const reason of ['collect','terminal','unmount']){clock.arm(now);const callback=callbacks.get(next);clock.clear();callback();assert.equal(failures,3,reason);}
 assert.ok(cancelled.length>=4);
});

test('CF027 actual watch registration and receive are bounded, status is transport evidence only, and a paused late response cannot bypass deadline',async()=>{
 for(const kind of ['registration-timeout','receive-timeout','late-registration','late-receive','normal']){
  let now=0,fetchResolve,bodyResolve,failures=0;const timers=[],statuses=[];const outer=new AbortController();
  const watch=fixtureFunction('watchFixtureFailure',{AbortController,Date:{now:()=>now},setTimeout(fn,ms){timers.push({fn,ms});return timers.length;},clearTimeout(){},postFixtureWatchAck:async()=>{},fetch:(_url,options)=>new Promise((resolve,reject)=>{fetchResolve=resolve;options.signal.addEventListener('abort',()=>reject(Error('synthetic abort')),{once:true});})});
  const task=watch(outer.signal,'synthetic',()=>failures++,s=>statuses.push(s));
  assert.equal(timers[0].ms,5000);assert.equal(statuses[0],'connecting');
  if(kind==='registration-timeout'){timers[0].fn();await task;assert.equal(failures,1);continue;}
  if(kind==='late-registration')now=5001;
  fetchResolve({ok:true,headers:{get:name=>name==='x-fixture-watch'?'registered':name==='x-fixture-watch-id'?'1':'10000'},text:()=>new Promise((resolve,reject)=>{bodyResolve=resolve;outer.signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true});})});
  for(let tick=0;tick<8&&!bodyResolve&&statuses.at(-1)!=='failed';tick++)await Promise.resolve();
  if(kind==='late-registration'){await task;assert.equal(failures,1);continue;}
  assert.ok(statuses.includes('registered'));assert.equal(timers[1].ms,10000);
  if(kind==='receive-timeout'){timers[1].fn();bodyResolve('{}');await task;assert.equal(failures,1);continue;}
  if(kind==='late-receive')now=10001;
  bodyResolve(JSON.stringify({failed:false,reason:null,terminal:true}));await task;
  assert.equal(failures,kind==='normal'?0:1);assert.equal(statuses.at(-1),kind==='normal'?'closed':'failed');
 }
});

test('CF027 strict ready/commit ACKs reject duplicates/foreign records and server write alone cannot satisfy commit',async()=>{
 const record={id:1,ready:false,sent:false,disconnected:false,commitReceived:false,commitWritten:false,waiters:[]},context={watchRecords:new Map([[1,record]]),failureTargets:new Set([1]),failureDelivery:{readyAcks:0,commitAcks:0,commitResponseWritten:0},clearTimeout(){},console:{log(){}}};
 const parse=fixtureFunction('parseFixtureWatchAck',{}),ack=fixtureFunction('acknowledgeFixtureWatch',context);
 assert.equal(parse('{"watch_id":1,"action":"ready","reason":null}').action,'ready');
 for(const raw of ['{"watch_id":1,"watch_id":2,"action":"ready","reason":null}','{"watch_id":1,"action":"ready","reason":null,"extra":1}','null','[]'])assert.throws(()=>parse(raw));
 for(const body of [{watch_id:2,action:'ready',reason:null},{watch_id:'1',action:'ready',reason:null},{watch_id:1,action:'commit',reason:'SERVER_FAILURE'},{watch_id:1,action:'ready',reason:null,extra:true}])assert.throws(()=>ack(body,true),/ACK/);
 ack({watch_id:1,action:'ready',reason:null},true);assert.equal(record.ready,true);assert.throws(()=>ack({watch_id:1,action:'ready',reason:null},true),/conflict/);
 let settled=false;const waiting=fixtureFunction('waitForFailureCommit',context)().then(()=>{settled=true;});await Promise.resolve();assert.equal(settled,false);
 ack({watch_id:1,action:'commit',reason:'SERVER_FAILURE'},false);assert.equal(record.commitReceived,true);await Promise.resolve();assert.equal(settled,false);
 // Execute the actual response-write callback; received commit alone cannot drain.
 let respond;const response={writeHead:status=>assert.equal(status,200),end:(body,done)=>{assert.equal(JSON.parse(body).ack,'commit');respond=done;}};
 const written=fixtureFunction('writeFixtureWatchAck',context)(response,record,'commit');assert.equal(settled,false);respond();await Promise.all([written,waiting]);assert.equal(settled,true);assert.equal(context.failureDelivery.commitResponseWritten,1);
 assert.throws(()=>ack({watch_id:1,action:'commit',reason:'SERVER_FAILURE'},false),/conflict/);
 await assert.rejects(fixtureFunction('waitForFailureCommit',{watchRecords:new Map(),failureTargets:new Set()})(),/unconfirmed/);
});

test('CF027 actual watch ACK client sends one fixed bounded control request and rejects failed/malformed/late ACK without retry',async()=>{
 for(const kind of ['ready','commit','http','malformed','late']){
  let calls=0,now=0,timeout;const action=kind==='commit'?'commit':'ready',reason=action==='ready'?null:'SERVER_FAILURE',signal=new AbortController().signal;
  const fn=fixtureFunction('postFixtureWatchAck',{AbortController,Date:{now:()=>now},setTimeout:(_fn,ms)=>{timeout=ms;return 1;},clearTimeout(){},fetch:async(url,options)=>{
   calls++;assert.equal(url,'/fixture-control');assert.equal(options.method,'POST');assert.equal(options.redirect,'error');assert.equal(options.headers['X-Fixture-Watch-Ack'],'1');assert.deepEqual(JSON.parse(options.body),{watch_id:1,action,reason});if(kind==='late')now=5001;
   return {status:kind==='http'?409:200,text:async()=>kind==='malformed'?'{}':JSON.stringify({ack:action})};
  }});
  if(['ready','commit'].includes(kind))await fn(signal,'synthetic',1,action,reason);else await assert.rejects(fn(signal,'synthetic',1,action,reason),/ACK/);
  assert.equal(calls,1);assert.equal(timeout,5000);
 }
});

test('CF027 actual scenario cannot arm without a ready active watch and client arm/commit cleanup remain wired (source-only React assertions)',()=>{
 const context={scenario:{status:'idle'},attempts:{},failureWatchers:new Set(),Date:{now:()=>0},setTimeout(){throw Error('must not arm');},scenarioTimer:null,clearTimeout(){},console:{log(){}}};
 assert.equal(fixtureFunction('controlScenario',context)('rerender'),false);
 const source=fs.readFileSync('tests/integration/supervisor/chat-browser-fixture.mjs','utf8');
 assert.match(source,/postFixtureWatchAck\(c.signal/);assert.match(source,/\[failed,onWatchStatus\]/);assert.match(source,/createClientScenarioDeadline\(\(\)=>failClosed\('CLIENT_SCENARIO_DEADLINE'\)\)/);
 assert.match(source,/if\(value.scenario==='collect'\)scenarioClock.current.clear\(\)/);assert.match(source,/return\(\)=>scenarioClock.current.clear\(\)/);assert.match(source,/res.flushHeaders\(\)/);
 assert.match(source,/x-fixture-watch-ack/);assert.match(source,/phase:'commit_unconfirmed'/);assert.doesNotMatch(source,/react_mount:'passed'|interaction:'passed'/);
});
