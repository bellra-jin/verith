// Actual production Session + ChatView + CSS over same-origin synthetic HTTP.
// This fixture never proves real Backend/authentication/PG/model acceptance.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import ts from 'typescript';
import {validateFixtureTarget,fixtureAdapter,createFixtureTerminal,terminalAction,browserNotExecuted} from '../../helpers/supervisor-fixture.mjs';
import {reactProductionFiles} from '../../../scripts/check-local-ports.mjs';

const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
if(cap.workload!=='unit'||cap.cf022Core!==true||cap.ports.length!==2||cap.lifetime>600||cap.root!==process.cwd()||cap.reactProduction.length!==5)throw Error('Core exact fixture capability required');
const registry={},ids=['react','react/jsx-runtime','react-dom','react-dom/client','scheduler'];
function checked(record){
 const file=path.join(cap.dependency,record.relative),meta=fs.lstatSync(file),raw=fs.readFileSync(file);
 if(!reactProductionFiles.includes(record.relative)||fs.realpathSync(file)!==file||!meta.isFile()||meta.nlink!==1||meta.size!==record.size||crypto.createHash('sha256').update(raw).digest('hex')!==record.sha256)throw Error('Production dependency drift');
 return raw.toString();
}
for(let i=0;i<5;i++){
 if(cap.reactProduction[i].relative!==reactProductionFiles[i])throw Error('Exact production registry');
 registry[ids[i]]=checked(cap.reactProduction[i]);
}
for(const [id,file] of Object.entries({
 SupervisorSession:'src/features/supervisor/components/supervisor-session.tsx',
 './chat-view':'src/features/supervisor/components/chat-view.tsx',
 '../lib/supervisor-request':'src/features/supervisor/lib/supervisor-request.ts',
 '@/features/flow/lib/analysis-request':'src/features/flow/lib/analysis-request.ts',
}))registry[id]=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
registry['../styles/chat.css']='module.exports={};';
const css=fs.readFileSync('src/features/supervisor/styles/chat.css','utf8');
const fixtures=JSON.parse(fs.readFileSync('tests/fixtures/cf023-supervisor-meaning.json','utf8')).validated_plans;
const nonce=cap.nonce,origin='http://127.0.0.1:'+cap.ports[0];
const A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const counts={sessionGET:0,preparePOST:0,prepareGET:0,prepareDELETE:0,confirmPOST:0,outcomeGET:0,model:0,provider:0};
const state={account:'A',authStatus:200,httpStatus:200,status:'ready',delay:0,coreFailure:'none'};
const attempts={total:0,session:0,core:0,GET:0,POST:0,DELETE:0};
const recentAttempts=[],failureWatchers=new Set(),watchRecords=new Map(),failureTargets=new Set();
const failureDelivery={registered:0,sent:0,writeCompleted:0,closedBeforeBody:0,readyAcks:0,commitAcks:0,commitResponseWritten:0};
const scenario={name:null,status:'idle',reason:null,started_at:null,baseline:null,delta:null};
let scenarioTimer,holdNextSession=false,heldSession=null;
function fixtureObservations(){return {attempts:{...attempts},scenario:{...scenario},sessionDelay:{armed:holdNextSession,held:heldSession!==null},failureDelivery:{...failureDelivery,active:failureWatchers.size}};}
function failScenario(reason){
 if(scenario.status==='failed')return;
 scenario.status='failed';scenario.reason=reason;
 console.log('CF027_SCENARIO_FAILED '+JSON.stringify({reason,attempts}));
 notifyFailureWatchers(true,reason);
 void terminal.finish('failed').catch(error=>{terminalError=error;finish();});
}
function notifyFailureWatchers(failed,reason){
 for(const watcher of failureWatchers){if(failed&&watcher.record.ready)failureTargets.add(watcher.record.id);watcher.finish({failed,reason,terminal:true});}
 // A client deadline may commit its failure before the server's thirty-second timer.
 if(failed&&!failureTargets.size){const latest=[...watchRecords.values()].at(-1);if(latest?.ready&&latest.commitReceived)failureTargets.add(latest.id);}
}
function parseFixtureWatchAck(raw){
 const body=JSON.parse(raw);
 if(!body||Array.isArray(body)||raw!==JSON.stringify({watch_id:body.watch_id,action:body.action,reason:body.reason}))throw Error('Fixture watch ACK invalid');
 return body;
}
function acknowledgeFixtureWatch(body,open){
 if(!body||Object.keys(body).sort().join()!=='action,reason,watch_id'||!Number.isSafeInteger(body.watch_id)||body.watch_id<1||body.watch_id>128||!['ready','commit'].includes(body.action))throw Error('Fixture watch ACK invalid');
 const record=watchRecords.get(body.watch_id);if(!record)throw Error('Fixture watch ACK conflict');
 if(body.action==='ready'){
  if(body.reason!==null||!open||record.ready||record.sent||record.disconnected)throw Error('Fixture watch ACK conflict');
  record.ready=true;clearTimeout(record.readyTimer);failureDelivery.readyAcks++;
 }else{
  if(!record.ready||record.commitReceived||!['CLIENT_SCENARIO_DEADLINE','SERVER_FAILURE','CHANNEL_FAILURE','CLIENT_FAILURE'].includes(body.reason))throw Error('Fixture watch ACK conflict');
  record.commitReceived=true;record.commitReason=body.reason;failureDelivery.commitAcks++;
 }
 console.log('CF027_WATCH_PHASE '+JSON.stringify({phase:body.action==='ready'?'ready_ack_received':'commit_ack_received',readyAcks:failureDelivery.readyAcks,commitAcks:failureDelivery.commitAcks}));
 return record;
}
function writeFixtureWatchAck(res,record,action){
 res.writeHead(200,{'Content-Type':'application/json'});
 return new Promise(resolve=>res.end(JSON.stringify({ack:action}),error=>{
  if(action==='commit'&&!error){record.commitWritten=true;failureDelivery.commitResponseWritten++;console.log('CF027_WATCH_PHASE '+JSON.stringify({phase:'commit_ack_response_written',count:failureDelivery.commitResponseWritten}));for(const done of record.waiters)done();record.waiters=[];}
  resolve();
 }));
}
async function respondFixtureWatchAck(res,record,action){
 // A collected server observation cannot overrule the client's expired deadline.
 // Start failure without awaiting drain: this ACK handler must settle first.
 if(action==='commit'&&terminal.open())failScenario(record.commitReason==='CLIENT_SCENARIO_DEADLINE'?'SCENARIO_DEADLINE':'CLIENT_FAILURE');
 await bounded(writeFixtureWatchAck(res,record,action),5000);
}
async function waitForFailureCommit(){
 const records=[...failureTargets].map(id=>watchRecords.get(id));
 if(!records.length||records.some(record=>!record?.ready))throw Error('Fixture failure commit unconfirmed');
 await Promise.all(records.map(record=>record.commitWritten?Promise.resolve():new Promise(resolve=>record.waiters.push(resolve))));
}

function waitForFixtureFailure(res){
 return new Promise(resolve=>{
  if(failureWatchers.size>=2||watchRecords.size>=128){res.writeHead(409,{'Content-Type':'application/json'});res.end('{}');resolve();return;}
  const record={id:watchRecords.size+1,ready:false,sent:false,disconnected:false,commitReceived:false,commitWritten:false,readyTimer:null,waiters:[]};watchRecords.set(record.id,record);
  let sent=false,closed=false,written=false,timer;
  const cleanup=()=>{if(closed)return;closed=true;clearTimeout(timer);clearTimeout(record.readyTimer);if(!written){failureDelivery.closedBeforeBody++;record.disconnected=true;console.log('CF027_WATCH_PHASE '+JSON.stringify({phase:'closed_before_body',count:failureDelivery.closedBeforeBody}));}failureWatchers.delete(watcher);res.off('close',cleanup);resolve();};
  const watcher={record,finish(value){if(sent)return;sent=true;record.sent=true;failureDelivery.sent++;clearTimeout(timer);res.end(JSON.stringify(value),error=>{if(!error){written=true;failureDelivery.writeCompleted++;console.log('CF027_WATCH_PHASE '+JSON.stringify({phase:'server_body_write_completed',count:failureDelivery.writeCompleted,client_commit_ack_received:record.commitReceived,client_commit_ack_response_written:record.commitWritten}));}cleanup();});}};
  failureWatchers.add(watcher);failureDelivery.registered++;res.once('close',cleanup);
  const remaining=Math.max(1,expires-Date.now());
  res.writeHead(200,{'Content-Type':'application/json','X-Fixture-Watch':'registered','X-Fixture-Watch-Id':String(record.id),'X-Fixture-Remaining-Ms':String(remaining)});
  res.flushHeaders();console.log('CF027_WATCH_PHASE '+JSON.stringify({phase:'headers_flushed',registered:failureDelivery.registered,active:failureWatchers.size}));
  record.readyTimer=setTimeout(()=>{if(!record.ready)failScenario('WATCH_READY_UNCONFIRMED');},Math.min(5000,remaining));
  timer=setTimeout(()=>watcher.finish({failed:true,reason:'FIXTURE_DEADLINE',terminal:true}),remaining);
  if(scenario.status==='failed')watcher.finish({failed:true,reason:scenario.reason,terminal:true});
 });
}
async function postFixtureWatchAck(signal,nonce,watchId,action,reason){
 const c=new AbortController(),started=Date.now(),abort=()=>c.abort();let timer;
 if(signal.aborted)throw Error('Fixture watch ACK aborted');
 signal.addEventListener('abort',abort,{once:true});timer=setTimeout(abort,5000);
 try{
  const response=await globalThis.fetch('/fixture-control',{method:'POST',headers:{'Content-Type':'application/json','X-Fixture-Nonce':nonce,'X-Fixture-Watch-Ack':'1'},body:JSON.stringify({watch_id:watchId,action,reason}),cache:'no-store',redirect:'error',signal:c.signal});
  if(c.signal.aborted||Date.now()-started>=5000||response.status!==200)throw Error('Fixture watch ACK unavailable');
  const raw=await response.text();if(c.signal.aborted||Date.now()-started>=5000||raw.length>1024)throw Error('Fixture watch ACK unavailable');
  const value=JSON.parse(raw);if(!value||Object.keys(value).join()!=='ack'||value.ack!==action)throw Error('Fixture watch ACK invalid');
 }finally{clearTimeout(timer);signal.removeEventListener('abort',abort);}
}
async function watchFixtureFailure(signal,nonce,onFailure,onStatus=()=>{}){
 if(signal.aborted)return;
 const controller=new AbortController(),started=Date.now();let timer,failed=false;
 const abort=()=>controller.abort();
 const fail=(reason='CHANNEL_FAILURE')=>{if(failed||signal.aborted)return;failed=true;clearTimeout(timer);onStatus('failed');onFailure(reason);controller.abort();};
 signal.addEventListener('abort',abort,{once:true});onStatus('connecting');
 timer=setTimeout(()=>fail(),5000);
 try{
  const response=await globalThis.fetch('/fixture-counts',{headers:{'X-Fixture-Failure-Watch':nonce},cache:'no-store',redirect:'error',signal:controller.signal});
  if(signal.aborted||failed)return;
  if(!response.ok||response.headers.get('x-fixture-watch')!=='registered')throw Error('Fixture failure channel unavailable');
  const remaining=Number(response.headers.get('x-fixture-remaining-ms')),watchId=Number(response.headers.get('x-fixture-watch-id'));
  if(!Number.isSafeInteger(watchId)||watchId<1||watchId>128)throw Error('Fixture watch identity unavailable');
  if(!Number.isInteger(remaining)||remaining<1||remaining>590000||Date.now()-started>=5000)throw Error('Fixture failure registration deadline');
  await postFixtureWatchAck(controller.signal,nonce,watchId,'ready',null);
  if(signal.aborted||failed||Date.now()-started>=5000)throw Error('Fixture watch registration deadline');
  clearTimeout(timer);onStatus('registered',watchId);
  const receiveBefore=Math.min(started+590000,Date.now()+remaining);
  timer=setTimeout(()=>fail(),Math.max(1,receiveBefore-Date.now()));
  const raw=await response.text();if(signal.aborted||failed)return;
  if(Date.now()>=receiveBefore||raw.length>1024)throw Error('Fixture failure message invalid');
  const value=JSON.parse(raw);
  if(!value||Object.keys(value).sort().join()!=='failed,reason,terminal'||typeof value.failed!=='boolean'||value.terminal!==true||value.failed&&!['SCENARIO_DEADLINE','REQUEST_ATTEMPT_LIMIT','FIXTURE_DEADLINE','WATCH_READY_UNCONFIRMED','CLIENT_FAILURE'].includes(value.reason)||!value.failed&&value.reason!==null)throw Error('Fixture failure message invalid');
  onStatus('received');
  if(value.failed)fail('SERVER_FAILURE');else onStatus('closed');
 }catch{fail();}finally{clearTimeout(timer);signal.removeEventListener('abort',abort);}
}
function createClientScenarioDeadline(onFailure,now=Date.now,schedule=setTimeout,cancel=clearTimeout){
 let handle=null,deadline=null,epoch=0;
 const clear=()=>{epoch++;if(handle!==null)cancel(handle);handle=null;deadline=null;};
 const expired=()=>{if(deadline!==null&&now()>=deadline){clear();onFailure();return true;}return false;};
 return {clear,expired,arm(started=now()){
  clear();deadline=started+30000;
  if(expired())return false;
  const revision=epoch;handle=schedule(()=>{if(revision!==epoch||deadline===null)return;handle=null;deadline=null;epoch++;onFailure();},Math.max(1,deadline-now()));return true;
 }};
}
function recordAttempt(kind,method,now=Date.now()){
 attempts.total++;attempts[kind]++;attempts[method]++;
 while(recentAttempts.length&&recentAttempts[0]<=now-2000)recentAttempts.shift();recentAttempts.push(now);
 if(attempts.total>128||recentAttempts.length>24){failScenario('REQUEST_ATTEMPT_LIMIT');return false;}
 return true;
}
function controlScenario(name){
 const names=['rerender','reauth','stale-session','recovery','new-request','get-verification','plan-focus','mounted-get-stored','mounted-get-error-retry','mounted-get-deleted'];
 if(name==='collect'){
  if(scenario.status!=='armed')return false;
  clearTimeout(scenarioTimer);scenarioTimer=null;
  scenario.status='collected';scenario.delta=Object.fromEntries(Object.keys(attempts).map(key=>[key,attempts[key]-scenario.baseline[key]]));
  console.log('CF027_SCENARIO_OBSERVATION '+JSON.stringify({name:scenario.name,delta:scenario.delta,status:'collected_not_acceptance'}));return true;
 }
 if(!names.includes(name)||scenario.status==='armed'||scenario.status==='failed'||![...failureWatchers].some(w=>w.record.ready&&!w.record.disconnected))return false;
 if(name.startsWith('mounted-get-')&&![...bindings.values()].some(row=>row.owner===currentOwner()))return false;
 scenario.name=name;scenario.status='armed';scenario.reason=null;scenario.started_at=Date.now();scenario.baseline={...attempts};scenario.delta=null;
 scenarioTimer=setTimeout(()=>failScenario('SCENARIO_DEADLINE'),30000);return true;
}
function sessionResponseSnapshot(){const status=state.authStatus;return {status,body:status===200?{user_id:currentOwner(),csrf_token:nonce}:{detail:{code:'AUTH_REQUIRED'}}};}
function waitForSessionRelease(){
 holdNextSession=false;
 return new Promise(resolve=>{
  const release=()=>{clearTimeout(timer);delays.delete(timer);if(heldSession===release)heldSession=null;resolve();};
  const timer=setTimeout(release,15000);delays.set(timer,release);heldSession=release;
 });
}

const preparations=new Map(),keys=new Map(),bindings=new Map(),confirmKeys=new Map();
function canonical(value){return Array.isArray(value)?'['+value.map(canonical).join(',')+']':value&&typeof value==='object'?'{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}':JSON.stringify(value);}
const digest=value=>crypto.createHash('sha256').update(canonical(value)).digest('hex');
function fixtureIdentity(draft){return canonical({...draft,answers:draft.answers.map(({slot,value})=>({slot,value})),candidate_ref:draft.selected_ticker?'selected-reference':null});}
function rebindFixture(template,draft,parent){
 const plan=structuredClone(template.plan),ids=new Map(template.draft.answers.map((answer,index)=>[answer.answer_id,draft.answers[index].answer_id]));
 plan.frame.answers=structuredClone(draft.answers);
 const renamed=new Map();
 for(const condition of plan.frame.conditions){
  for(const evidence of condition.evidence)if(evidence.answer_id!==null)evidence.answer_id=ids.get(evidence.answer_id);
  const {condition_id,...body}=condition;condition.condition_id='c'+digest(body).slice(0,24);renamed.set(condition_id,condition.condition_id);
 }
 plan.frame.conditions.sort((a,b)=>a.condition_id.localeCompare(b.condition_id));
 for(const mention of plan.frame.mentions)if(mention.evidence.answer_id!==null)mention.evidence.answer_id=ids.get(mention.evidence.answer_id);
 plan.required_waivers=plan.required_waivers.map(id=>renamed.get(id)??id);
 if(plan.candidate_ref){
  const {selected_ticker:omittedTicker,candidate_ref:omittedRef,...identity}=draft;
  void omittedTicker;void omittedRef;
  plan.candidate_ref=parent?parent.plan.candidate_ref:digest({policy:plan.policy_version,draft:identity,resolution:{...plan.resolution,candidates:[...plan.resolution.candidates].sort((a,b)=>a.stock_code.localeCompare(b.stock_code))}});
 }
 const {plan_hash:oldHash,...semantic}=plan;void oldHash;
 plan.plan_hash=digest(semantic);
 return plan;
}
const currentOwner=()=>state.account==='A'?A:B;
const envelope=data=>({schema_version:'supervisor.core.v1',request_id:A,trace_id:B,data,error:null});
const failure=code=>({schema_version:'supervisor.core.v1',request_id:A,trace_id:B,data:null,error:{code,message:'Supervisor request unavailable'}});
function preparedView(row){
 const ancestor=row.parent?preparations.get(row.parent):null;
 const consumed=row.consumed??ancestor?.consumed;
 const deleted=row.deleted||ancestor?.deleted;
 const expired=Date.now()>=Date.parse(row.expires);
 const status=consumed?'consumed':deleted?'deleted':expired?'expired':['pending','unknown','failed'].includes(state.status)?state.status:row.plan.status==='unsupported'?'unsupported':['ready','scope_confirmation'].includes(row.plan.status)?'ready':'clarification';
 return {preparation_id:row.id,state:status,plan:['ready','clarification','unsupported'].includes(status)?row.plan:null,created_at:row.created,expires_at:row.expires,meaning_status:['ready','clarification','unsupported'].includes(status)?row.meaning:status,consumed_binding_id:consumed??null};
}
function outcome(row){
 if(state.status==='deleted')return {supervisor_id:row.id,plan:null,plan_status:'deleted',effective_scope:null,views:[],coverage:'deleted',flow:null};
 const status=['running','unknown','result_ready','stored','failed'].includes(state.status)?state.status:'stored';
 return {supervisor_id:row.id,plan:row.plan,plan_status:'confirmed',effective_scope:{selected_views:['flow'],fixed_observation_window:true,all_subjects_retained:true,waived_conditions:row.body.consent.waived_conditions,partial_consent:row.body.consent.allow_partial},views:row.plan.requested_views.map(view=>({view,state:view==='flow'?status:'not_executed',reason:view==='flow'?'flow_state':'not_connected'})),coverage:status==='stored'?(row.plan.partial?'partial':'fulfilled'):['failed','unknown'].includes(status)?'unfulfilled':'pending',flow:{analysis_id:row.analysis,admission_request_id:row.analysis,attempt_id:row.analysis,state:status,deadline_at:new Date(Date.now()+120000).toISOString(),report_id:status==='stored'?row.report:null,report_url:status==='stored'?'/reports/flow/'+row.report:null,error:null}};
}
function fixtureFocusSnapshot(doc,phase){
 const target=doc.activeElement;
 return {phase,tag:target?.tagName??'NONE',disabled:Boolean(target?.matches?.(':disabled')),connected:Boolean(target?.isConnected),hasFocus:doc.hasFocus(),visibility:doc.visibilityState};
}
function watchPublicFocus(doc,win,update,Observer=win.MutationObserver){
 let snapshots=[],lastRoot=null,lastPending=null,lastHeading=null;
 const events={focusin:0,windowFocus:0,windowBlur:0};
 const sample=phase=>{snapshots=[...snapshots.slice(-7),fixtureFocusSnapshot(doc,phase)];update(JSON.stringify({snapshots,events:{...events}}));};
 const focusin=()=>{events.focusin=Math.min(32,events.focusin+1);sample('focusin');};
 const focus=()=>{events.windowFocus=Math.min(32,events.windowFocus+1);sample('window-focus');};
 const blur=()=>{events.windowBlur=Math.min(32,events.windowBlur+1);sample('window-blur');};
 const committed=()=>{
  const root=doc.querySelector('.supervisor-chat'),pending=root?.getAttribute('aria-busy')==='true',heading=root?.querySelector('.sc-card h2[tabindex="-1"]')??null;
  if(root!==lastRoot){lastRoot=root;sample('session-commit');}
  if(pending!==lastPending){lastPending=pending;sample('pending-commit');}
  if(heading!==lastHeading){lastHeading=heading;if(heading)sample('plan-commit');}
 };
 const observer=new Observer(committed),app=doc.getElementById('app');
 observer.observe(app,{subtree:true,childList:true,attributes:true,attributeFilter:['aria-busy']});
 doc.addEventListener('focusin',focusin);win.addEventListener('focus',focus);win.addEventListener('blur',blur);committed();
 return()=>{observer.disconnect();doc.removeEventListener('focusin',focusin);win.removeEventListener('focus',focus);win.removeEventListener('blur',blur);};
}
async function runMountedGetCase(kind,{doc,nonce,signal,current,onArm,onCollect,onPhase,fetcher=fetch}){
 if(!['stored','error-retry','deleted'].includes(kind))throw Error('Mounted GET case invalid');
 const target=doc.location.href,c=new AbortController(),started=Date.now();
 let reads=0,polls=0;
 const abort=()=>c.abort();
 signal.addEventListener('abort',abort,{once:true});
 const deadline=setTimeout(abort,20000);
 const check=value=>{if(!value)throw Error('Mounted GET case failed');};
 const alive=()=>check(!signal.aborted&&!c.signal.aborted&&current()&&doc.location.href===target&&doc.visibilityState==='visible'&&Date.now()-started<20000);
 const root=()=>{const found=doc.querySelectorAll('.supervisor-chat');check(found.length===1);return found[0];};
 const button=()=>{
  const found=[...root().querySelectorAll('button')].filter(node=>node.textContent.trim()==='상태 다시 확인 · GET만'&&node.isConnected&&node.getClientRects().length>0);
  check(found.length===1);return found[0];
 };
 const pending=()=>root().getAttribute('aria-busy')==='true'&&[...root().querySelectorAll('[role="status"]')].some(node=>node.textContent.trim()==='상태 확인 중 · 실행 없음');
 const error=()=>Boolean(root().querySelector('[role="alert"]'));
 const deleted=()=>[...root().querySelectorAll('h2')].some(node=>node.textContent.trim()==='삭제된 결과입니다');
 const read=async(path,value)=>{
  alive();check(++reads<=100);
  const response=await fetcher(path,{signal:c.signal,...(value?{method:'POST',headers:{'Content-Type':'application/json','X-Fixture-Nonce':nonce},body:JSON.stringify(value)}:{})});
  alive();check(response.status===200);const result=await response.json();alive();return result;
 };
 const sample=()=>read('/fixture-counts');
 const control=value=>read('/fixture-control',value);
 const pause=()=>new Promise((resolve,reject)=>{
  alive();const done=()=>{c.signal.removeEventListener('abort',cancel);resolve();};
  const timer=setTimeout(done,50),cancel=()=>{clearTimeout(timer);c.signal.removeEventListener('abort',cancel);reject(Error('Mounted GET case cancelled'));};
  c.signal.addEventListener('abort',cancel,{once:true});
 });
 const until=async predicate=>{while(++polls<=80){alive();const value=await sample();if(predicate(value))return value;await pause();}throw Error('Mounted GET case polling limit');};
 const delta=(value,base)=>Object.fromEntries(['session','core','GET','POST','DELETE'].map(key=>[key,value.attempts[key]-base.attempts[key]]));
 const unchanged=(value,base)=>{
  check(value.attempts.POST===base.attempts.POST&&value.attempts.DELETE===base.attempts.DELETE);
  for(const key of ['preparePOST','prepareGET','prepareDELETE','confirmPOST','model','provider'])check(value.counts[key]===base.counts[key]);
 };
 const phase=(name,value,base)=>onPhase({phase:kind+':'+name,pending:pending(),disabled:button().disabled,delta:delta(value,base)});
 try{
  alive();check(validateFixtureTarget(doc.location.pathname+doc.location.search+doc.location.hash).id!==null);
  check(root().querySelectorAll('a[href^="/reports/flow/"]').length===1&&!button().disabled&&!pending()&&!error());
  const initial=await sample();check(initial.counts.confirmPOST>0&&['A','B'].includes(initial.state.account)&&initial.state.authStatus===200&&initial.state.httpStatus===200&&initial.state.status==='stored'&&initial.state.delay===0&&!initial.sessionDelay.armed&&!initial.sessionDelay.held);
  const armed=await control({scenario:'mounted-get-'+kind});check(armed.scenario.status==='armed'&&armed.scenario.name==='mounted-get-'+kind);check(onArm(started));
  if(kind==='error-retry'){
   await control({httpStatus:503});button().click();
   const failed=await until(()=>error()&&!pending()&&!button().disabled);unchanged(failed,initial);
   check(failed.attempts.session-initial.attempts.session===2&&failed.attempts.core-initial.attempts.core===1);phase('actual-503-error',failed,initial);
   await control({httpStatus:200});
  }else if(kind==='deleted'){
   await control({status:'deleted'});button().click();
   const gone=await until(()=>deleted()&&!pending()&&!button().disabled);unchanged(gone,initial);phase('actual-deleted-GET',gone,initial);
  }
  const base=await sample();check(!button().disabled&&!pending()&&!base.sessionDelay.armed&&!base.sessionDelay.held);
  const heldArm=await control({sessionAction:'hold_next'});check(heldArm.sessionDelay.armed&&!heldArm.sessionDelay.held);
  const clickedAt=Date.now();button().click();
  const held=await until(value=>value.sessionDelay.held&&!value.sessionDelay.armed&&pending()&&button().disabled);
  unchanged(held,base);check(held.attempts.session-base.attempts.session===1&&held.attempts.core===base.attempts.core);phase('held',held,base);
  button().click();await pause();await pause();
  const duplicate=await sample();unchanged(duplicate,base);
  check(duplicate.sessionDelay.held&&duplicate.attempts.session-base.attempts.session===1&&duplicate.attempts.core===base.attempts.core);phase('disabled-click-no-extra-HTTP',duplicate,base);
  alive();check(Date.now()-clickedAt<3000);
  // No release if a fresh acknowledgement cannot prove this one-shot is still held.
  const fresh=await sample();check(fresh.sessionDelay.held&&!fresh.sessionDelay.armed&&Date.now()-clickedAt<3000);
  await control({sessionAction:'release'});
  const settled=await until(value=>!value.sessionDelay.held&&!pending()&&!button().disabled&&!error()&&(kind!=='deleted'||deleted()));
  unchanged(settled,base);unchanged(settled,initial);
  check(settled.attempts.session-base.attempts.session===3&&settled.attempts.core-base.attempts.core===1&&settled.attempts.GET-base.attempts.GET===4);
  check(settled.counts.sessionGET-base.counts.sessionGET===3&&settled.counts.outcomeGET-base.counts.outcomeGET===1);phase('settled',settled,base);
  const collected=await control({scenario:'collect'});check(collected.scenario.status==='collected'&&collected.scenario.name==='mounted-get-'+kind);unchanged(collected,initial);onCollect();
  phase('collected-programmatic-mounted',collected,base);
 }finally{clearTimeout(deadline);signal.removeEventListener('abort',abort);c.abort();}
}
const bundle=`const modules={${Object.entries(registry).map(([id,body])=>JSON.stringify(id)+':function(module,exports,require){'+body+'\n}').join(',')}};const cache={};function require(id){if(!Object.hasOwn(modules,id))throw Error('Closed fixture registry');if(!cache[id]){const m={exports:{}};cache[id]=m;modules[id](m,m.exports,require);}return cache[id].exports;}
const validateFixtureTarget=${validateFixtureTarget.toString()},fixtureAdapter=${fixtureAdapter.toString()},postFixtureWatchAck=${postFixtureWatchAck.toString()},watchFixtureFailure=${watchFixtureFailure.toString()},createClientScenarioDeadline=${createClientScenarioDeadline.toString()};
const React=require('react'),Session=require('SupervisorSession').SupervisorSession;
const fixtureFocusSnapshot=${fixtureFocusSnapshot.toString()},watchPublicFocus=${watchPublicFocus.toString()};
const runMountedGetCase=${runMountedGetCase.toString()};
function Fixture(){const [id,setId]=React.useState(()=>validateFixtureTarget(location.pathname+location.search+location.hash).id),[stats,setStats]=React.useState('합성 제어 대기'),[failed,setFailed]=React.useState(false),[watchStatus,setWatchStatus]=React.useState('connecting'),[focusLabel,setFocusLabel]=React.useState('focus · 관측 대기'),[mountedRunning,setMountedRunning]=React.useState(false);const lock=React.useRef(false),failure=React.useRef(false),watch=React.useRef('connecting'),watchId=React.useRef(null),failureReason=React.useRef(null),scenarioClock=React.useRef(null),mountedOperation=React.useRef({controller:null,alive:true});
 const failClosed=React.useCallback((reason='CLIENT_FAILURE')=>{if(failure.current)return;failure.current=true;failureReason.current=reason;lock.current=true;setFailed(true);setStats('fixture 시나리오 실패 · 새 작업을 중단했습니다. 정리 결과를 확인하세요.');},[]);
 if(scenarioClock.current===null)scenarioClock.current=createClientScenarioDeadline(()=>failClosed('CLIENT_SCENARIO_DEADLINE'));
 const onWatchStatus=React.useCallback((value,id=null)=>{if(value==='registered')watchId.current=id;watch.current=value;setWatchStatus(value);},[]);
 React.useEffect(()=>{const c=new AbortController();void watchFixtureFailure(c.signal,${JSON.stringify(nonce)},failClosed,onWatchStatus);return()=>c.abort();},[failClosed,onWatchStatus]);
 React.useEffect(()=>{if(failed){scenarioClock.current.clear();mountedOperation.current.controller?.abort();}return()=>scenarioClock.current.clear();},[failed]);
 React.useEffect(()=>{const owned=mountedOperation.current;owned.alive=true;return()=>{owned.alive=false;owned.controller?.abort();};},[]);
 React.useEffect(()=>{
  if(!failed||failureReason.current===null||watchId.current===null)return;
  const c=new AbortController();onWatchStatus('commit-sent');
  void postFixtureWatchAck(c.signal,${JSON.stringify(nonce)},watchId.current,'commit',failureReason.current).then(()=>onWatchStatus('commit-acknowledged'),()=>onWatchStatus('commit-unconfirmed'));
  return()=>c.abort();
 },[failed,onWatchStatus]);
 const refresh=async()=>{if(lock.current||failure.current||scenarioClock.current.expired())return;try{const r=await fetch('/fixture-counts');if(lock.current||failure.current||scenarioClock.current.expired())return;if(!r.ok)throw Error();const value=await r.json();if(lock.current||failure.current||scenarioClock.current.expired())return;if(value.scenario?.status==='failed'){failClosed();return;}setStats(JSON.stringify(value));}catch{failClosed();}};
 const control=async(value)=>{if(lock.current||failure.current||scenarioClock.current.expired())return;
 const arming=value.scenario&&value.scenario!=='collect',started=Date.now();
 if(arming&&watch.current!=='registered'){failClosed();return;}
 lock.current=true;
 try{
  const r=await fetch('/fixture-control',{method:'POST',headers:{'Content-Type':'application/json','X-Fixture-Nonce':${JSON.stringify(nonce)}},body:JSON.stringify(value)});
  if(failure.current||scenarioClock.current.expired())return;if(!r.ok)throw Error();
  const applied=await r.json();if(failure.current||scenarioClock.current.expired())return;
  if(arming){if(applied.scenario?.status!=='armed'||applied.scenario.name!==value.scenario)throw Error();if(!scenarioClock.current.arm(started))return;}
  if(value.scenario==='collect')scenarioClock.current.clear();
  setStats('적용 완료 · '+JSON.stringify(applied));
 }catch{failClosed();}finally{if(!failure.current)lock.current=false;}};
 React.useEffect(()=>watchPublicFocus(document,window,setFocusLabel),[]);
 const mountedCase=async(kind)=>{
  if(lock.current||failure.current||watch.current!=='registered'||scenarioClock.current.expired())return;
  lock.current=true;setMountedRunning(true);const c=new AbortController();mountedOperation.current.controller=c;const target=location.href,phases=[];
  try{await runMountedGetCase(kind,{doc:document,nonce:${JSON.stringify(nonce)},signal:c.signal,current:()=>mountedOperation.current.alive&&!failure.current&&location.href===target,onArm:started=>scenarioClock.current.arm(started),onCollect:()=>scenarioClock.current.clear(),onPhase:value=>{if(!failure.current&&mountedOperation.current.alive){phases.push(value);setStats(JSON.stringify(phases));}}});}
  catch{if(mountedOperation.current.alive&&!failure.current)failClosed();}
  finally{if(mountedOperation.current.controller===c){mountedOperation.current.controller=null;if(!failure.current&&mountedOperation.current.alive){lock.current=false;setMountedRunning(false);}}}
 };
 const adapter=React.useMemo(()=>fixtureAdapter({origin:location.origin,location,history,events:window,onChange:setId,onInvalid:()=>{setId(null);setFailed(true);setStats('안전한 fixture URL 오류');},onOutside:()=>setStats('범위 밖 합성 navigation 관측')}),[]);
 React.useEffect(()=>adapter.listen(),[adapter]);
 const finishFixture=async(action)=>{if(lock.current||failed||scenarioClock.current.expired())return;scenarioClock.current.clear();lock.current=true;try{const response=await fetch('/fixture-finish',{method:'POST',headers:{'Content-Type':'application/json','X-Fixture-Nonce':${JSON.stringify(nonce)}},body:JSON.stringify({action})});const value=await response.json();if(failure.current)return;if(response.status!==200||value.state!==(action==='complete'?'completed':'cancelled'))throw Error();failure.current=true;setFailed(true);setStats(action==='complete'?'fixture 수명주기 완료 · UI 수용 아님':'fixture 취소 · UI 수용 미완');}catch{setFailed(true);setStats('안전한 fixture 종료 오류 · 재전송하지 마세요');}};
 const navigate=React.useCallback((href,replace=false)=>adapter.navigate(href,replace),[adapter]);
 const legacy=React.useCallback(()=>React.createElement('p',null,'기존 Flow pending 복구 seam · 이번 fixture는 새 storage 사용'),[]);
 return React.createElement(React.Fragment,null,React.createElement('aside',null,React.createElement('p',null,'CF023 실제 production controller / 합성 HTTP. 질문 예: 삼성전자 수급, 수급, 005930 수급, 삼성전자 외국인 수급과 차트'),React.createElement('p',{role:'status'},stats),React.createElement('p',null,focusLabel),React.createElement('p',null,'failure watch · '+watchStatus+' · 전달 상태이며 UI 수용 결과가 아님'),...['none','usage','feature','deadline','service'].map(coreFailure=>React.createElement('button',{key:'error-'+coreFailure,disabled:failed||mountedRunning,onClick:()=>void control({coreFailure})},'오류 응답 · '+coreFailure)),...['ready','pending','unknown','running','result_ready','stored','failed','deleted'].map(status=>React.createElement('button',{key:status,disabled:failed||mountedRunning,onClick:()=>control({status})},'합성 '+status)),... [200,401,403,503].map(httpStatus=>React.createElement('button',{key:'http'+httpStatus,disabled:failed||mountedRunning,onClick:()=>control({httpStatus})},'합성 HTTP '+httpStatus)),... [0,250,16000].map(delay=>React.createElement('button',{key:'delay'+delay,disabled:failed||mountedRunning,onClick:()=>control({delay})},'합성 지연 '+delay+'ms')),...['A','B'].map(account=>React.createElement('button',{key:account,disabled:failed||mountedRunning,onClick:()=>control({account})},'합성 계정 '+account)),...['rerender','reauth','stale-session','recovery','new-request','get-verification','plan-focus'].map(scenario=>React.createElement('button',{key:'scenario'+scenario,disabled:failed||mountedRunning||watchStatus!=='registered',onClick:()=>control({scenario})},'시나리오 arm · '+scenario)),React.createElement('button',{onClick:()=>control({scenario:'collect'}),disabled:failed||mountedRunning},'30초 내 관측 수집'),...['hold_next','release'].map(sessionAction=>React.createElement('button',{key:sessionAction,disabled:failed||mountedRunning,onClick:()=>control({sessionAction})},'session '+sessionAction)),...[200,401].map(authStatus=>React.createElement('button',{key:'auth'+authStatus,disabled:failed||mountedRunning,onClick:()=>control({authStatus})},'session HTTP '+authStatus)),...['stored','error-retry','deleted'].map(kind=>React.createElement('button',{key:'mounted'+kind,disabled:failed||mountedRunning||watchStatus!=='registered'||id===null,onClick:()=>void mountedCase(kind)},'고정 mounted GET · '+kind)),React.createElement('button',{onClick:()=>void refresh(),disabled:failed||mountedRunning},'합성 카운터 확인'),React.createElement('button',{onClick:()=>void finishFixture('complete'),disabled:failed||mountedRunning},'fixture 완료'),React.createElement('button',{onClick:()=>void finishFixture('cancel'),disabled:failed||mountedRunning},'fixture 취소')),failed?null:React.createElement(Session,{supervisorId:id,navigate,renderLegacy:legacy}));}
require('react-dom/client').createRoot(document.getElementById('app')).render(React.createElement(Fixture));`;
let finish,terminalError,terminalResponse,closeDeadline=Infinity;
const started=Date.now(),expires=started+590000,delays=new Map(),active=new Set();
const waitDelay=ms=>new Promise(resolve=>{const timer=setTimeout(()=>{delays.delete(timer);resolve();},ms);delays.set(timer,resolve);});
const bounded=async(task,ms)=>{let timer;try{return await Promise.race([task,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Fixture cleanup deadline')),Math.max(1,Math.min(ms,expires-Date.now(),closeDeadline-Date.now())));})]);}finally{clearTimeout(timer);}};
function receiptFile(value){
 const filename='cf025-terminal.json',temporary=filename+'.tmp';
 if(fs.existsSync(filename))throw Error('Fixture receipt already exists');
 const fd=fs.openSync(temporary,fs.constants.O_WRONLY|fs.constants.O_CREAT|fs.constants.O_EXCL,0o600);
 try{fs.writeFileSync(fd,JSON.stringify(value));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
 fs.renameSync(temporary,filename);return value;
}
const stopped=new Promise(resolve=>{finish=resolve;});
const server=http.createServer((req,res)=>{
 const task=handle(req,res).catch(()=>{if(!res.headersSent)res.writeHead(422);res.end();});active.add(task);void task.finally(()=>active.delete(task));
});
const terminal=createFixtureTerminal({
 stopWork(){notifyFailureWatchers(scenario.status==='failed',scenario.status==='failed'?scenario.reason:null);clearTimeout(scenarioTimer);scenarioTimer=null;holdNextSession=false;if(heldSession)heldSession();console.log('CF027_FIXTURE_ATTEMPTS '+JSON.stringify(fixtureObservations()));closeDeadline=Math.min(expires,Date.now()+5000);for(const [timer,resolve] of delays){clearTimeout(timer);resolve();}delays.clear();},
 async drain(){await bounded(Promise.all([...active]),5000);if(scenario.status==='failed'){try{await bounded(waitForFailureCommit(),5000);}catch{console.log('CF027_WATCH_PHASE '+JSON.stringify({phase:'commit_unconfirmed'}));}}},
 async writeReceipt(value){return receiptFile({schema:'cf025.terminal.v1',nonce,pid:process.pid,cwd:process.cwd(),port:cap.ports[0],...value,counts:{...counts},browser:browserNotExecuted()});},
 async ack(value){if(terminalResponse)await bounded(new Promise((resolve,reject)=>{terminalResponse.once('error',reject);terminalResponse.end(JSON.stringify({state:value.state}),resolve);}),5000);},
 async close(){server.closeAllConnections();if(server.listening)await bounded(new Promise(resolve=>server.close(resolve)),5000);},
 settled(){finish();},
});
function readBody(req,limit){
 return new Promise((resolve,reject)=>{
  const parts=[];let size=0,settled=false;
  const cleanup=()=>{clearTimeout(timer);req.off('data',data);req.off('end',end);req.off('error',error);req.off('aborted',aborted);};
  const fail=()=>{if(settled)return;settled=true;cleanup();req.pause();reject(Error('Fixture body invalid'));};
  const data=chunk=>{size+=chunk.length;if(size>limit){fail();return;}parts.push(chunk);};
  const end=()=>{if(settled)return;settled=true;cleanup();resolve(Buffer.concat(parts).toString('utf8'));};
  const error=()=>fail(),aborted=()=>fail();
  const timer=setTimeout(fail,Math.max(1,Math.min(5000,expires-Date.now())));
  req.on('data',data);req.once('end',end);req.once('error',error);req.once('aborted',aborted);
 });
}
function fundamentalNavigationTarget(target,method){
 if(typeof target!=='string'||!target.startsWith('/fundamental'))return null;
 if(target!=='/fundamental')return {status:422};
 return {status:method==='GET'?200:405};
}
async function handle(req,res){
 res.setHeader('Cache-Control','no-store');
 res.setHeader('Content-Security-Policy',`default-src 'none'; script-src 'nonce-${nonce}'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'`);
 const json=(value,code=200)=>{res.writeHead(code,{'Content-Type':'application/json'});res.end(JSON.stringify(value));};
 const fail=(code,status)=>json(failure(code),status);
 if(req.headers.host!=='127.0.0.1:'+cap.ports[0]){fail('AUTH_REQUEST_INVALID',403);return;}
 if(req.headers.origin&&req.headers.origin!==origin){fail('AUTH_REQUEST_INVALID',403);return;}
 const research=validateFixtureTarget(req.url);
 if(req.url==='/fixture-finish'){
  if(req.method!=='POST'){json({},405);return;}
  if(req.headers.origin!==origin||req.headers['x-fixture-nonce']!==nonce){json({},403);return;}
  if(!terminal.open()){json({},409);return;}
  if(req.headers['content-type']!=='application/json'){json({},422);return;}
  let action;try{action=terminalAction(await readBody(req,1024));}catch{res.setHeader('Connection','close');json({},422);return;}
  if(!terminal.open()){json({},409);return;}
  terminalResponse=res;res.writeHead(200,{'Content-Type':'application/json'});
  // Return without awaiting finish: this handler settles before drain completes.
  void terminal.finish(action).catch(error=>{terminalError=error;finish();});return;
 }
 if(req.url==='/fixture-control'&&req.headers['x-fixture-watch-ack']!==undefined){
  if(req.method!=='POST'){json({},405);return;}
  if(req.headers['x-fixture-watch-ack']!=='1'||req.headers.origin!==origin||req.headers['x-fixture-nonce']!==nonce){json({},403);return;}
  if(req.headers['content-type']!=='application/json'){json({},422);return;}
  let body,record;try{body=parseFixtureWatchAck(await readBody(req,1024));record=acknowledgeFixtureWatch(body,terminal.open());}catch{json({},409);return;}
  await respondFixtureWatchAck(res,record,body.action);return;
 }
 if(!terminal.open()){json({},409);return;}
 const navigation=fundamentalNavigationTarget(req.url,req.method);
 if(navigation!==null){
  if(navigation.status!==200){json({},navigation.status);return;}
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});
  res.end('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CF041 재무 탐색 목적지</title><link rel="stylesheet" href="/chat.css"><main class="supervisor-chat"><h1>재무 화면 탐색 목적지</h1><p>합성 탐색 목적지이며 실제 재무 화면·인증·분석 수용을 뜻하지 않습니다.</p><a href="/research">리서치 대화로 돌아가기</a></main>');return;
 }
 if(research.status===422){json({},422);return;}
 const apiRoot='/api/private/supervisor/core/';
 const method=req.url==='/research'||research.kind==='research'||['/bundle.js','/chat.css','/fixture-counts','/api/auth/session'].includes(req.url)?['GET']:req.url==='/fixture-control'||req.url===apiRoot+'preparations'||req.url===apiRoot+'requests'?['POST']:/^\/api\/private\/supervisor\/core\/preparations\/[0-9a-f-]{36}$/.test(req.url)?['GET','DELETE']:/^\/api\/private\/supervisor\/core\/requests\/[0-9a-f-]{36}$/.test(req.url)?['GET']:null;
 if(!method){json({},404);return;}if(!method.includes(req.method)){json({},405);return;}
 if(req.url==='/api/auth/session'||req.url.startsWith(apiRoot)){if(!recordAttempt(req.url==='/api/auth/session'?'session':'core',req.method)){json({fixture_error:'REQUEST_ATTEMPT_LIMIT'},503);return;}}
 let body=null;
 if(req.method==='POST'){
  try{body=JSON.parse(await readBody(req,16384));if(!body||Array.isArray(body)||typeof body!=='object')throw Error();}catch{res.setHeader('Connection','close');json({},422);return;}
  if(!terminal.open()){json({},409);return;}
 }
 if(req.url==='/fixture-counts'&&req.method==='GET'){
  if(req.headers['x-fixture-failure-watch']!==undefined){if(req.headers['x-fixture-failure-watch']!==nonce){json({},403);return;}await waitForFixtureFailure(res);return;}
  json({counts,state,...fixtureObservations()});return;
 }
 if(req.url==='/fixture-control'&&req.method==='POST'&&req.headers['x-fixture-nonce']===nonce){
  const keys=Object.keys(body),stateKeys=['status','account','authStatus','httpStatus','delay','coreFailure'];
  if(keys.some(k=>![...stateKeys,'scenario','sessionAction'].includes(k))||body.status!==undefined&&!['ready','pending','unknown','running','result_ready','stored','failed','deleted'].includes(body.status)||body.account!==undefined&&!['A','B'].includes(body.account)||body.authStatus!==undefined&&![200,401].includes(body.authStatus)||body.httpStatus!==undefined&&![200,401,403,503].includes(body.httpStatus)||body.coreFailure!==undefined&&!['none','usage','feature','deadline','service'].includes(body.coreFailure)||body.delay!==undefined&&![0,250,16000].includes(body.delay)||body.scenario!==undefined&&(keys.length!==1||!['rerender','reauth','stale-session','recovery','new-request','get-verification','plan-focus','mounted-get-stored','mounted-get-error-retry','mounted-get-deleted','collect'].includes(body.scenario))||body.sessionAction!==undefined&&(keys.length!==1||!['hold_next','release'].includes(body.sessionAction))){json({},422);return;}
  if(body.scenario!==undefined&&!controlScenario(body.scenario)){json({},409);return;}
  if(body.sessionAction==='hold_next'){if(holdNextSession||heldSession){json({},409);return;}holdNextSession=true;}
  if(body.sessionAction==='release'){if(!heldSession){json({},409);return;}heldSession();}
  for(const key of stateKeys)if(body[key]!==undefined)state[key]=body[key];
  json({applied:true,counts,state,...fixtureObservations()});return;
 }
 if(req.url==='/api/auth/session'&&req.method==='GET'){
  // Snapshot before the one-shot delay; later account/status controls cannot rewrite this response.
  const {status,body}=sessionResponseSnapshot();
  counts.sessionGET++;
  if(holdNextSession)await waitForSessionRelease();
  if(!terminal.open()){json({},409);return;}
  json(body,status);return;
 }
 if(req.url?.startsWith('/api/private/supervisor/core/')){
  if(state.authStatus!==200){fail('AUTH_REQUIRED',401);return;}
  if(state.httpStatus!==200){fail(state.httpStatus===401?'AUTH_REQUIRED':state.httpStatus===403?'AUTH_REQUEST_INVALID':'SERVICE_UNAVAILABLE',state.httpStatus);return;}
  if(req.method!=='GET'&&req.headers['x-csrf-token']!==nonce){fail('AUTH_REQUEST_INVALID',403);return;}
  const coreFailure=state.coreFailure;
  if(state.delay)await waitDelay(state.delay);
  if(!terminal.open()){json({},409);return;}
  if(coreFailure!=='none'){const [code,status]=({usage:['USAGE_LIMIT_EXCEEDED',429],feature:['FEATURE_UNAVAILABLE',403],deadline:['DEADLINE_EXCEEDED',504],service:['SERVICE_UNAVAILABLE',503]})[coreFailure];fail(code,status);return;}
  const owner=currentOwner(),root='/api/private/supervisor/core/';
  if(req.url===root+'preparations'&&req.method==='POST'){
   counts.preparePOST++;
   const key=owner+':'+body.prepare_key,prior=keys.get(key);
   if(prior){if(prior.digest!==canonical(body)){fail('IDEMPOTENCY_CONFLICT',409);return;}const v=preparedView(prior);json(envelope(v),v.state==='pending'?202:200);return;}
   const template=fixtures.find(value=>fixtureIdentity(value.draft)===fixtureIdentity(body.draft));
   if(!template){fail('INPUT_INVALID',422);return;}
   const parent=body.parent_preparation_id?preparations.get(body.parent_preparation_id):null;
   if(body.parent_preparation_id&&(!parent||parent.owner!==owner||parent.consumed||parent.deleted)){fail('PREPARATION_CONSUMED',409);return;}
   if(parent&&body.draft.candidate_ref!==parent.plan.candidate_ref){fail('PLAN_STALE',409);return;}
   const created=new Date(),row={id:crypto.randomUUID(),owner,digest:canonical(body),plan:rebindFixture(template,body.draft,parent),meaning:template.meaning_status??'deterministic',parent:parent?.id??null,created:created.toISOString(),expires:new Date(Math.min(created.getTime()+600000,parent?Date.parse(parent.expires):Infinity)).toISOString()};
   preparations.set(row.id,row);keys.set(key,row);const v=preparedView(row);json(envelope(v),v.state==='pending'?202:200);return;
  }
  const preparation=/^\/api\/private\/supervisor\/core\/preparations\/([0-9a-f-]{36})$/.exec(req.url);
  if(preparation&&['GET','DELETE'].includes(req.method)){
   const row=preparations.get(preparation[1]);if(!row||row.owner!==owner){fail('RESOURCE_NOT_FOUND',404);return;}
   if(req.method==='DELETE'){counts.prepareDELETE++;if(preparedView(row).state==='consumed'){fail('PREPARATION_CONSUMED',409);return;}row.deleted=true;let p=row;while(p.parent){p=preparations.get(p.parent);p.deleted=true;}}
   else counts.prepareGET++;
   json(envelope(preparedView(row)));return;
  }
  if(req.url===root+'requests'&&req.method==='POST'){
   counts.confirmPOST++;const key=owner+':'+body.client_key,prior=confirmKeys.get(key);
   if(prior){if(canonical(prior.body)!==canonical(body)){fail('IDEMPOTENCY_CONFLICT',409);return;}json(envelope(outcome(prior)));return;}
   const prepared=preparations.get(body.preparation_id);
   if(!prepared||prepared.owner!==owner){fail('RESOURCE_NOT_FOUND',404);return;}
   if(preparedView(prepared).state!=='ready'){fail('PREPARATION_'+preparedView(prepared).state.toUpperCase(),409);return;}
   if(body.expected_plan_hash!==prepared.plan.plan_hash||body.consent.allow_flow!==true||prepared.plan.partial&&!body.consent.allow_partial||canonical([...body.consent.waived_conditions].sort())!==canonical([...prepared.plan.required_waivers].sort())){fail('INPUT_INVALID',422);return;}
   const row={id:crypto.randomUUID(),analysis:crypto.randomUUID(),report:crypto.randomUUID(),owner,body,plan:prepared.plan};
   let p=prepared;while(p){p.consumed=row.id;p=p.parent?preparations.get(p.parent):null;}
   bindings.set(row.id,row);confirmKeys.set(key,row);json(envelope(outcome(row)));return;
  }
  const request=/^\/api\/private\/supervisor\/core\/requests\/([0-9a-f-]{36})$/.exec(req.url);
  if(request&&req.method==='GET'){counts.outcomeGET++;const row=bindings.get(request[1]);if(!row||row.owner!==owner){fail('RESOURCE_NOT_FOUND',404);return;}json(envelope(outcome(row)));return;}
  fail('INPUT_INVALID',422);return;
 }
 if(req.url==='/bundle.js'){res.writeHead(200,{'Content-Type':'text/javascript'});res.end(bundle);return;}
 if(req.url==='/chat.css'){res.writeHead(200,{'Content-Type':'text/css'});res.end(css);return;}
 if(research.kind==='research'){
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CF023 synthetic production chat</title><link rel="stylesheet" href="/chat.css"><div id="app"></div><script nonce="'+nonce+'" src="/bundle.js"></script>');return;
 }
 json({},404);
}
const deadline=setTimeout(()=>{notifyFailureWatchers(true,'FIXTURE_DEADLINE');void terminal.finish('timed_out').catch(error=>{terminalError=error;finish();});},590000);
try{
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(cap.ports[0],'127.0.0.1',resolve);});
 fs.writeFileSync('cf019-ready.json',JSON.stringify({nonce,pid:process.pid,cwd:process.cwd(),port:cap.ports[0]}),{mode:0o600});
 await stopped;
 if(terminalError)throw terminalError;
 if(!['completed','cancelled'].includes(terminal.phase))throw Error('Core browser evidence incomplete');
 console.log('CF025_FIXTURE_CLOSED '+JSON.stringify({state:terminal.phase,counts,browser:browserNotExecuted()}));
}finally{
 clearTimeout(deadline);server.closeAllConnections();
 if(server.listening)await new Promise(resolve=>server.close(resolve));
 fs.rmSync('cf019-ready.json',{force:true});
 for(const record of cap.reactProduction)checked(record);
}
