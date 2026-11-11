import nodeTest,{after} from 'node:test';
const failures=[];
function test(name,body){return nodeTest(name,async()=>{try{return await body();}catch(error){failures.push({name,message:String(error?.stack??error).slice(0,1600)});throw error;}});}
after(()=>{for(const failure of failures)console.error('CF036_TEST_FAILURE '+JSON.stringify(failure));});
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import crypto from 'node:crypto';
import ts from 'typescript';
const fixture=JSON.parse(fs.readFileSync('tests/fixtures/cf036-technical-owned-read.json','utf8'));
const report=fixture.detail.data.report_id,second=fixture.second_detail.data.report_id;
const owner='40000000-0000-4000-8000-000000000001',other='40000000-0000-4000-8000-000000000002';
const clone=value=>structuredClone(value),json=value=>Response.json(value);
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function harness(send=async()=>json(fixture.list),options={}){
 const registry=new Map(),seen=[],timers=new Map(),budgets=[];let serial=0;
 const context={Object,Array,Set,Date,JSON,Uint8Array,TextEncoder,TextDecoder,URLSearchParams,AbortController,AbortSignal,structuredClone,Response,
  crypto:options.crypto??crypto.webcrypto,process:{env:{NODE_ENV:'production'}},
  setTimeout(fn,ms){const id=++serial;timers.set(id,{fn,ms});budgets.push(ms);return id;},clearTimeout(id){timers.delete(id);},
  fetch:async(url,init)=>{seen.push({url,init});return send(url,init);},
  require(name){assert.ok(registry.has(name),'closed owned read registry '+name);return registry.get(name);}};
 function evaluate(source){const compiled={exports:{}};vm.runInNewContext(source,{...context,module:compiled,exports:compiled.exports},{timeout:100});return compiled.exports;}
 function load(file){return evaluate(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText);}
 const projection=load('src/features/technical/lib/boundary-preview.ts');registry.set('./boundary-preview',{boundaryPreview:v=>projection.boundaryPreview(clone(v))});
 const decoder=load('src/features/technical/lib/strict-boundary-read.ts');registry.set('./strict-boundary-read',{decodeTechnicalBoundary:(v,e)=>decoder.decodeTechnicalBoundary(clone(v),clone(e))});
 registry.set('@/features/flow/lib/analysis-request',load('src/features/flow/lib/analysis-request.ts'));
 const read=load('src/features/technical/lib/owned-report-read.ts');registry.set('../lib/owned-report-read',read);
 const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));assert.equal(cap.cf032Display,true);
 const files=['react/cjs/react.production.js','react/cjs/react-jsx-runtime.production.js','react-dom/cjs/react-dom.production.js','react-dom/cjs/react-dom-client.production.js','scheduler/cjs/scheduler.production.js'];
 assert.deepEqual(cap.reactProduction.map(r=>r.relative),files);assert.deepEqual(cap.ports,[]);
 for(const record of cap.reactProduction){const filename=path.join(cap.dependency,record.relative),bytes=fs.readFileSync(filename),actual=fs.lstatSync(filename,{bigint:true});assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),record.sha256);assert.equal(bytes.length,record.size);for(const [key,field]of[['dev','dev'],['ino','ino'],['mode','mode'],['size','size'],['mtime','mtimeNs'],['ctime','ctimeNs'],['nlink','nlink']])assert.equal(record.identity.at(-1)[key],String(actual[field]));}
 const React=evaluate(fs.readFileSync(path.join(cap.dependency,files[0]),'utf8'));registry.set('react',React);registry.set('react/jsx-runtime',evaluate(fs.readFileSync(path.join(cap.dependency,files[1]),'utf8')));
 function ChartSentinel(){throw Error('Real Recharts mount belongs to browser acceptance');}registry.set('./technical-boundary-preview',{TechnicalBoundaryPreview:ChartSentinel});
 const view=load('src/features/technical/components/owned-report-view.tsx');
 return {read,view,React,ChartSentinel,seen,timers,budgets,expire(ms){for(const [id,t]of [...timers])if(t.ms===ms){timers.delete(id);t.fn();}}};
}
function session(user=owner,csrf='session-a'){return json({user_id:user,csrf_token:csrf});}
const drain=async()=>{for(let i=0;i<100;i++)await Promise.resolve();};
async function until(condition){for(let i=0;i<100&&!condition();i++)await new Promise(setImmediate);assert.ok(condition(),'expected lifecycle phase entered');}
function nodes(React,tree){if(Array.isArray(tree))return tree.flatMap(x=>nodes(React,x));if(!React.isValidElement(tree))return [];return [tree,...nodes(React,tree.props.children)];}
function text(React,tree){if(Array.isArray(tree))return tree.map(x=>text(React,x)).join(' ');if(typeof tree==='string'||typeof tree==='number')return String(tree);if(!React.isValidElement(tree)||typeof tree.type!=='string')return '';return text(React,tree.props.children);}

test('canonical TEXT hashes validate exact bytes and independent expected produces detached detail',async()=>{
 const h=harness();const result=await h.read.decodeOwnedWire(clone(fixture.detail),report);
 assert.equal(result.report_id,report);assert.deepEqual(result.response,JSON.parse(fixture.detail.data.result_json));
 assert.deepEqual(result.expected.request,JSON.parse(fixture.detail.data.request_json));assert.equal(result.expected.request_sha256,fixture.detail.data.request_sha256);
 assert.equal(await h.read.decodeOwnedWire(clone(fixture.second_detail),second).then(v=>v.report_id),second);
 assert.equal(result.expected.request.data.original_query,'  삼성전자 이동평균과 RSI 차트 분석  ');
 assert.equal(h.seen.length,0);
});
for(const mutate of ['hash','raw-bytes','url-id','outer-id','snapshot-id','missing-field','extra-field','schema','error-and-data','unsafe-number'])test('detail closes '+mutate,async()=>{
 const h=harness(),value=clone(fixture.detail);let id=report;
 if(mutate==='hash')value.data.result_sha256='0'.repeat(64);
 if(mutate==='raw-bytes')value.data.request_json+=' ';
 if(mutate==='url-id')id=second;
 if(mutate==='outer-id')value.data.report_id=second;
 if(mutate==='snapshot-id'||mutate==='unsafe-number'){
  const data=JSON.parse(value.data.result_json);
  if(mutate==='snapshot-id')data.data.request_snapshot.context.report_id=second;
  else data.data.result.charts[0].chart_data.candles[0].volume=9007199254740992;
  value.data.result_json=JSON.stringify(data);value.data.result_sha256=crypto.createHash('sha256').update(value.data.result_json).digest('hex');
 }
 if(mutate==='missing-field')delete value.data.request_sha256;
 if(mutate==='extra-field')value.data.owner='private';
 if(mutate==='schema')value.schema_version='other';
 if(mutate==='error-and-data')value.error={code:'BUSY',message:'private'};
 await assert.rejects(h.read.decodeOwnedWire(value,id),/저장된 차트/);
});
test('strict list permits empty/null/zero but rejects hidden ownership and duplicate rows',async()=>{
 const h=harness();assert.deepEqual(clone(await h.read.decodeOwnedWire(clone(fixture.empty),null)),fixture.empty.data);
 for(const change of ['duplicate','owner','limit','market','created','extra']){const wire=clone(fixture.list);if(change==='duplicate')wire.data.items[1].report_id=wire.data.items[0].report_id;if(change==='owner')wire.data.items[0].owner=owner;if(change==='limit')wire.data.limit='10';if(change==='market')wire.data.items[0].stock.market='NASDAQ';if(change==='created')wire.data.items[0].created_at='2026-02-30T00:00:00Z';if(change==='extra')wire.data.more=true;await assert.rejects(h.read.decodeOwnedWire(wire,null));}
});
for(const query of ['?owner=x','?stock_code=005930&stock_code=000660','?stock_code=１２３４５６','?limit=0','?limit=21','?limit=','?offset=10001','?offset=-1'])test('exact query rejects '+query,()=>{assert.throws(()=>harness().read.ownedReadQuery(query));});
test('fixed GET/client limits and list pagination echo are checked',async()=>{
 const h=harness();assert.equal(h.read.ownedReadQuery('?offset=0&stock_code=005930&limit=10'),'?stock_code=005930&limit=10&offset=0');
 await h.read.getOwnedRead(null,'',new AbortController().signal);
 assert.equal(h.seen[0].url,'/api/private/technical/owned-reports');assert.equal(h.seen[0].init.cache,'no-store');assert.equal(h.seen[0].init.credentials,'same-origin');assert.equal(h.seen[0].init.redirect,'manual');assert.equal(h.seen[0].init.method,undefined);assert.equal(h.timers.size,0);
 await assert.rejects(h.read.getOwnedRead(report,'?owner=x',new AbortController().signal));assert.equal(h.seen.length,1);
 assert.equal(h.read.matchesOwnedReadUrl(report,'/reports/technical/'+report,''),true);assert.equal(h.read.matchesOwnedReadUrl(report,'/reports/technical/'+second,''),false);
 const mismatched=harness(async()=>json({...fixture.list,data:{...fixture.list.data,offset:1}}));await assert.rejects(mismatched.read.getOwnedRead(null,'',new AbortController().signal));
});
test('bounded stream refuses list cap and invalid UTF8 without displaying server text',async()=>{
 for(const body of [new Uint8Array(65537),new Uint8Array([255])]){const h=harness(async()=>new Response(body));await assert.rejects(h.read.getOwnedRead(null,'',new AbortController().signal),e=>e.code==='RESULT_CONTRACT_INVALID');assert.equal(h.timers.size,0);}
});
test('error codes require exact fixed message and matching status',async()=>{
 const h=harness();await assert.rejects(h.read.decodeOwnedWire(clone(fixture.error),report,404),e=>e.code==='RESOURCE_NOT_FOUND');
 for(const value of [{...fixture.error,error:{...fixture.error.error,message:'private'}},{...fixture.error,error:{...fixture.error.error,code:'UNKNOWN'}}])await assert.rejects(h.read.decodeOwnedWire(value,report,404),e=>e.code==='RESULT_CONTRACT_INVALID');
 await assert.rejects(h.read.decodeOwnedWire(fixture.error,report,503),e=>e.code==='RESULT_CONTRACT_INVALID');
});
test('session before/GET/session after publishes only after same owner and token',async()=>{
 let sessionCalls=0;const h=harness(async url=>url==='/api/auth/session'?(sessionCalls++,session()):json(fixture.list)),states=[];
 const action=new h.read.OwnedReadAction(s=>states.push(s),()=>true);assert.equal(await action.run(null),true);
 assert.equal(sessionCalls,2);assert.deepEqual(h.seen.map(s=>s.url),['/api/auth/session','/api/private/technical/owned-reports','/api/auth/session']);assert.deepEqual(states.map(s=>s.kind),['pending','list']);assert.deepEqual(h.budgets,[55000,15000,20000,15000]);assert.equal(h.timers.size,0);
});
for(const type of ['owner','session','401'])test('post-read '+type+' hides result and requires explicit new read',async()=>{
 let n=0;const h=harness(async url=>url!=='/api/auth/session'?json(fixture.detail):++n===1?session():type==='owner'?session(other):type==='session'?session(owner,'session-b'):new Response(null,{status:401})),states=[];
 const action=new h.read.OwnedReadAction(s=>states.push(s),()=>true);assert.equal(await action.run(report),false);assert.deepEqual(states.map(s=>s.kind),['pending','error']);assert.equal(states.at(-1).code,type==='401'?'AUTH_REQUIRED':'ACCOUNT_CHANGED');assert.equal(h.timers.size,0);
});
test('synchronous in-flight rejects duplicates; old finally cannot clear new selection or publish late',async()=>{
 const first=deferred();let sessionCalls=0;const h=harness(async url=>url==='/api/auth/session'?(++sessionCalls===1?first.promise:session()):json(fixture.list)),states=[];
 const action=new h.read.OwnedReadAction(s=>states.push(s),()=>true),a=action.run(null);assert.equal(await action.run(null),false);assert.equal(sessionCalls,1);
 action.cancel();const b=action.run(null);first.resolve(session());assert.equal(await a,false);assert.equal(await b,true);assert.deepEqual(states.map(s=>s.kind),['pending','idle','pending','list']);assert.equal(h.timers.size,0);
});
for(const phase of ['session','http','post-session','action'])test('nonrenewing '+phase+' deadline closes pending and permits explicit retry',async()=>{
 const held=deferred();let sessions=0;const h=harness(async url=>{if(url==='/api/auth/session'){sessions++;return phase==='session'||phase==='action'||phase==='post-session'&&sessions===2?held.promise:session();}return phase==='http'?held.promise:json(fixture.list);}),states=[];
 const action=new h.read.OwnedReadAction(s=>states.push(s),()=>true),run=action.run(null);await until(()=>phase==='post-session'?sessions===2:phase==='http'?h.seen.some(s=>s.url==='/api/private/technical/owned-reports'):sessions===1);h.expire(phase==='http'?20000:phase==='action'?55000:15000);assert.equal(await run,false);assert.equal(states.at(-1).kind,'error');assert.equal(states.at(-1).code,'DEADLINE_EXCEEDED');assert.equal(h.timers.size,0);held.resolve(session());await drain();assert.equal(states.at(-1).kind,'error');
});
test('abort during hash await prevents result adoption and old validation cannot republish',async()=>{
 const hashes=deferred(),actual=crypto.webcrypto;const h=harness(async url=>url==='/api/auth/session'?session():json(fixture.detail),{crypto:{subtle:{digest:async(...args)=>{await hashes.promise;return actual.subtle.digest(...args);}}}}),states=[];
 const action=new h.read.OwnedReadAction(s=>states.push(s),()=>true),run=action.run(report);await drain();action.cancel();assert.equal(await run,false);assert.equal(states.at(-1).kind,'idle');hashes.resolve();await drain();assert.equal(states.at(-1).kind,'idle');assert.equal(h.timers.size,0);
});
test('URL/visibility generation mismatch clears pending without exposing a late result',async()=>{
 const held=deferred();let allowed=true;const h=harness(async url=>url==='/api/auth/session'?held.promise:json(fixture.list)),states=[];
 const action=new h.read.OwnedReadAction(s=>states.push(s),()=>allowed),run=action.run(null);allowed=false;held.resolve(session());assert.equal(await run,false);assert.deepEqual(states.map(s=>s.kind),['pending','idle']);assert.equal(h.seen.length,1);
});
test('production React content composition uses safe links/status and report key prevents first-render stale chart',async()=>{
 const h=harness(),detail=await h.read.decodeOwnedWire(fixture.detail,report),a=h.view.OwnedReportView({reportId:report}),b=h.view.OwnedReportView({reportId:second});
 assert.equal(a.key,report);assert.notEqual(a.key,b.key);assert.equal(a.type,b.type);assert.equal(h.view.OwnedReportView({reportId:report}).key,a.key);assert.equal(h.view.OwnedReportView({}).key,'owned-list');
 for(const state of [{kind:'idle'},{kind:'pending'},{kind:'error',code:'AUTH_REQUIRED'},{kind:'error',code:'RESOURCE_NOT_FOUND'},{kind:'list',value:fixture.empty.data}]){
  const tree=h.view.OwnedReadContent({state,onRetry(){}}),els=nodes(h.React,tree);assert.equal(els.filter(n=>n.type===h.ChartSentinel).length,0);assert.ok(text(h.React,tree).includes('새 분석을 실행하지 않습니다'));assert.ok(els.some(n=>n.type==='a'&&n.props.href==='/research'));assert.equal(els.find(n=>n.type==='button').props.disabled,state.kind==='pending');
 }
 const tree=h.view.OwnedReadContent({state:{kind:'detail',value:detail},onRetry(){}}),els=nodes(h.React,tree),chart=els.find(n=>n.type===h.ChartSentinel);assert.deepEqual(chart.props.expected,detail.expected);assert.deepEqual(chart.props.response,detail.response);assert.ok(!text(h.React,tree).includes(detail.expected.request.data.original_query));
 const list=h.view.OwnedReadContent({state:{kind:'list',value:fixture.list.data},onRetry(){}});assert.ok(nodes(h.React,list).some(n=>n.type==='a'&&n.props.href==='/reports/technical/'+report));
});
