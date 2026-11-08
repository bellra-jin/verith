import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';
import ts from 'typescript';
const root=path.resolve(import.meta.dirname,'../../..');
const ids={user:'aaaaaaaa-0000-4000-8000-000000000001',run:'bbbbbbbb-0000-4000-8000-000000000002',request:'cccccccc-0000-4000-8000-000000000003',attempt:'dddddddd-0000-4000-8000-000000000004',input:'eeeeeeee-0000-4000-8000-000000000005',execution:'ffffffff-0000-4000-8000-000000000006'};
function load(fetchSpy=()=>{throw Error('unexpected fetch');}){const source=ts.transpileModule(fs.readFileSync(path.join(root,'src/features/flow/lib/synthetic-demo.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const bundle={exports:{}};vm.runInNewContext(source,{module:bundle,exports:bundle.exports,Response,Request,Headers,URL,fetch:fetchSpy,crypto:{randomUUID}});return bundle.exports;}
function value(stage='admitted'){
 const executing=!['admitted','prepared'].includes(stage),terminal=['succeeded','failed','timed_out'].includes(stage),success=stage==='succeeded';
 return {version:1,synthetic:true,mode:'synthetic_demo',run_id:ids.run,request_id:ids.request,attempt_id:ids.attempt,input_snapshot_id:stage==='admitted'?null:ids.input,execution_id:executing?ids.execution:null,stage,deadline_at:executing?'2026-11-08T00:00:10Z':null,finished_at:terminal?'2026-11-08T00:00:01Z':null,result_stored:success,result:success?{contract_version:1,mode:'synthetic_only',synthetic:true,execution_id:ids.execution,input_snapshot_id:ids.input,input_sha256:'a'.repeat(64),source_reference:{run_id:ids.run,request_id:ids.request,attempt_id:ids.attempt,owner_user_id:ids.user},ticker:'005930',requested_as_of:'2026-11-08T00:00:00Z',engine_id:'flow.fake.summary.v1',row_count:20,start_date:'2026-10-20',end_date:'2026-11-08',calendar:'consecutive_calendar_dates_not_trading_days',quantity_unit:'share',trading_value_unit:'KRW',totals:{individual:0,foreign:800000,institution:200000,trading_value:20000000},notice:'synthetic only'}:null,result_sha256:success?'a'.repeat(64):null,failure_code:stage==='failed'?'fake_failed':stage==='timed_out'?'deadline_expired':null};
}
function response(data){return Response.json({request_id:randomUUID(),data,error:null});}
test('all coherent stages and exact contradictions; zero stays zero without recomputation',()=>{
 const api=load();for(const stage of ['admitted','prepared','running','succeeded','failed','timed_out'])assert.ok(api.demoView(value(stage),ids.user));
 assert.equal(api.demoView(value('succeeded'),ids.user).result.totals.individual,0);
 for(const change of [{stage:'running'},{input_snapshot_id:ids.input},{execution_id:ids.execution},{result_stored:1},{synthetic:1},{version:true},{result:{}},{extra:true}])assert.equal(api.demoView({...value(),...change},ids.user),null);
 for(const change of [{row_count:4},{quantity_unit:'KRW'},{ticker:'000660'},{input_snapshot_id:ids.run},{source_reference:{run_id:ids.run,request_id:ids.request,attempt_id:ids.attempt,owner_user_id:ids.input}}]){const v=value('succeeded');v.result={...v.result,...change};assert.equal(api.demoView(v,ids.user),null);}
});
test('direct uppercase URL, pending run IDs and account namespace are canonical; key bytes stay stable',async()=>{
 const calls=[];const api=load(async(url,init)=>{calls.push({url,init});return response(value());});
 const upper=ids.run.toUpperCase();assert.equal((await api.fetchDemo(upper,ids.user,new AbortController().signal)).run_id,ids.run);
 assert.equal(calls[0].url,api.DEMO_BFF+'/'+ids.run);assert.equal(api.demoHref(upper),'/flow/demo?run_id='+ids.run);
 const pending=api.pendingValue({idempotency_key:ids.request.toUpperCase(),as_of:'2026-11-08T00:00:00.000Z',run_id:upper});assert.equal(pending.run_id,ids.run);assert.equal(pending.idempotency_key,ids.request.toUpperCase());assert.equal(api.pendingKey(ids.user.toUpperCase()),api.pendingKey(ids.user));
});
test('pending is tab/account scoped, exact fields only; storage failure or corruption never silently produces another intent',()=>{
 const api=load();const records=new Map();const seen=[];const store={getItem:key=>(seen.push(key),records.get(key)??null),setItem:(key,v)=>records.set(key,v)};
 const p=api.freshPending();api.writePending(store,ids.user,p);const read=api.readPending(store,ids.user);assert.equal(read.idempotency_key,p.idempotency_key);assert.equal(read.as_of,p.as_of);
 assert.equal(api.readPending(store,ids.input),null);assert.ok(seen.every(key=>key.startsWith('verith.flow.synthetic-demo.v1:')));
 records.set(api.pendingKey(ids.user),'{');assert.throws(()=>api.readPending(store,ids.user));
 assert.throws(()=>api.writePending({setItem(){throw Error('quota');}},ids.user,p));
 assert.throws(()=>api.pendingValue({...p,result:{}}));assert.throws(()=>api.pendingValue({...p,as_of:'not-date'}));
});
test('synchronous busy identity and generation reject double click, old response and old timer; running POST uses same capped loop',()=>{
 const api=load();const intent=new api.DemoIntent();intent.reset(ids.user);const first=intent.begin(ids.user,'same');assert.ok(first);assert.equal(intent.begin(ids.user,'same'),null);
 intent.reset(ids.user);const second=intent.begin(ids.user,'new');intent.finish(first);assert.equal(intent.begin(ids.user,'third'),null);assert.equal(intent.accepts(first,'same'),false);assert.equal(intent.accepts(second,'new'),true);
 const life=new api.DemoLifecycle();const old=life.invalidate();assert.equal(life.takePoll(old),true);const fresh=life.invalidate();assert.equal(life.accepts(old),false);assert.equal(life.takePoll(old),false);
 for(let i=0;i<15;i++)assert.equal(life.takePoll(fresh),true);assert.equal(life.takePoll(fresh),false);
 const code=fs.readFileSync(path.join(root,'src/features/flow/components/synthetic-demo.tsx'),'utf8');
 assert.match(code,/clearTimeout\(timer\.current\)/);assert.match(code,/life\.current\.invalidate\(\)/);assert.match(code,/publishRef\.current\(result,generation\)/);assert.match(code,/life\.current\.accepts\(generation\)/);
 const parsed=ts.createSourceFile('demo.tsx',code,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let effects=0;
 function walk(node){if(ts.isCallExpression(node)&&node.expression.getText(parsed)==='useEffect'){effects++;assert.doesNotMatch(node.arguments[0].getText(parsed),/postDemo\s*\(|execute\s*\(/);}ts.forEachChild(node,walk);}walk(parsed);assert.equal(effects,1);
 const newFn=code.slice(code.indexOf('function startNew()'));assert.ok(newFn.indexOf('effectActive.current=false')<newFn.indexOf("window.location.assign('/flow/demo')"));assert.ok(newFn.indexOf('invalidate()')<newFn.indexOf("window.location.assign('/flow/demo')"));
});
test('client sends fixed raw JSON identity once per explicit call; GET and 401 never synthesize a POST',async()=>{
 const calls=[];const api=load(async(url,init)=>{calls.push({url,init});return response(value());});
 const pending={idempotency_key:ids.request,as_of:'2026-11-08T00:00:00.000Z'};const session={user_id:ids.user,csrf_token:'synthetic-csrf'};
 await api.postDemo(pending,session,new AbortController().signal);await api.postDemo(pending,session,new AbortController().signal);
 assert.equal(calls[0].init.body,calls[1].init.body);assert.deepEqual(JSON.parse(calls[0].init.body),{...pending,allow_fake:true});assert.equal(calls[0].init.headers['X-CSRF-Token'],'synthetic-csrf');
 await api.fetchDemo(ids.run,ids.user,new AbortController().signal);assert.equal(calls[2].init.method,undefined);
 const denied=load(async()=>Response.json({request_id:randomUUID(),data:null,error:{code:'AUTH_REQUIRED',message:'fixed'}},{status:401}));await assert.rejects(denied.fetchDemo(ids.run,ids.user,new AbortController().signal),e=>e.status===401);
});
