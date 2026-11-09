// Actual production Session + ChatView + CSS over same-origin synthetic HTTP.
// This fixture never proves real Backend/authentication/PG/model acceptance.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import ts from 'typescript';
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
const state={account:'A',authStatus:200,httpStatus:200,status:'ready',delay:0};
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
 const status=['running','unknown','result_ready','stored','failed'].includes(state.status)?state.status:'stored';
 return {supervisor_id:row.id,plan:row.plan,plan_status:'confirmed',effective_scope:{selected_views:['flow'],fixed_observation_window:true,all_subjects_retained:true,waived_conditions:row.body.consent.waived_conditions,partial_consent:row.body.consent.allow_partial},views:row.plan.requested_views.map(view=>({view,state:view==='flow'?status:'not_executed',reason:view==='flow'?'flow_state':'not_connected'})),coverage:status==='stored'?(row.plan.partial?'partial':'fulfilled'):['failed','unknown'].includes(status)?'unfulfilled':'pending',flow:{analysis_id:row.analysis,admission_request_id:row.analysis,attempt_id:row.analysis,state:status,deadline_at:new Date(Date.now()+120000).toISOString(),report_id:status==='stored'?row.report:null,report_url:status==='stored'?'/reports/flow/'+row.report:null,error:null}};
}
const bundle=`const modules={${Object.entries(registry).map(([id,body])=>JSON.stringify(id)+':function(module,exports,require){'+body+'\n}').join(',')}};const cache={};function require(id){if(!Object.hasOwn(modules,id))throw Error('Closed fixture registry');if(!cache[id]){const m={exports:{}};cache[id]=m;modules[id](m,m.exports,require);}return cache[id].exports;}
const React=require('react'),Session=require('SupervisorSession').SupervisorSession;
function Fixture(){const [id,setId]=React.useState(null),[stats,setStats]=React.useState('합성 제어 대기'),[failed,setFailed]=React.useState(false);const lock=React.useRef(false);
 const refresh=async()=>{const r=await fetch('/fixture-counts');if(!r.ok)throw Error();setStats(JSON.stringify(await r.json()));};
 const control=async(value)=>{if(lock.current||failed)return;lock.current=true;try{const r=await fetch('/fixture-control',{method:'POST',headers:{'Content-Type':'application/json','X-Fixture-Nonce':${JSON.stringify(nonce)}},body:JSON.stringify(value)});if(!r.ok)throw Error();setStats('적용 완료 · '+JSON.stringify(await r.json()));}catch{setFailed(true);setStats('안전한 fixture 제어 오류 · 다음 클릭 중지');}finally{lock.current=false;}};
 const navigate=React.useCallback((href,replace=false)=>{const u=new URL(href,location.href);if(u.pathname!=='/research'){setStats('합성 navigation 관측 · '+u.pathname);return;}history[replace?'replaceState':'pushState']({},'',u);setId(u.searchParams.get('supervisor_id'));},[]);
 const legacy=React.useCallback(()=>React.createElement('p',null,'기존 Flow pending 복구 seam · 이번 fixture는 새 storage 사용'),[]);
 return React.createElement(React.Fragment,null,React.createElement('aside',null,React.createElement('p',null,'CF023 실제 production controller / 합성 HTTP. 질문 예: 삼성전자 수급, 수급, 005930 수급, 삼성전자 외국인 수급과 차트'),React.createElement('p',{role:'status'},stats),...['ready','pending','unknown','running','result_ready','stored','failed'].map(status=>React.createElement('button',{key:status,disabled:failed,onClick:()=>control({status})},'합성 '+status)),... [200,401,403,503].map(httpStatus=>React.createElement('button',{key:'http'+httpStatus,disabled:failed,onClick:()=>control({httpStatus})},'합성 HTTP '+httpStatus)),... [0,250,16000].map(delay=>React.createElement('button',{key:'delay'+delay,disabled:failed,onClick:()=>control({delay})},'합성 지연 '+delay+'ms')),...['A','B'].map(account=>React.createElement('button',{key:account,disabled:failed,onClick:()=>control({account})},'합성 계정 '+account)),React.createElement('button',{onClick:()=>void refresh(),disabled:failed},'합성 카운터 확인')),React.createElement(Session,{supervisorId:id,navigate,renderLegacy:legacy}));}
history.replaceState({},'','/research');require('react-dom/client').createRoot(document.getElementById('app')).render(React.createElement(Fixture));`;
let finish,expired=false;
const stopped=new Promise(resolve=>{finish=resolve;});
const server=http.createServer(async(req,res)=>{
 res.setHeader('Cache-Control','no-store');
 res.setHeader('Content-Security-Policy',`default-src 'none'; script-src 'nonce-${nonce}'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'`);
 const json=(value,code=200)=>{res.writeHead(code,{'Content-Type':'application/json'});res.end(JSON.stringify(value));};
 const fail=(code,status)=>json(failure(code),status);
 if(req.headers.origin&&req.headers.origin!==origin){fail('AUTH_REQUEST_INVALID',403);return;}
 let body=null;
 if(req.method==='POST'){
  let raw='';for await(const chunk of req){raw+=chunk;if(Buffer.byteLength(raw)>16384){fail('INPUT_INVALID',422);return;}}
  try{body=JSON.parse(raw);}catch{fail('INPUT_INVALID',422);return;}
 }
 if(req.url==='/fixture-counts'&&req.method==='GET'){json({counts,state});return;}
 if(req.url==='/fixture-control'&&req.method==='POST'&&req.headers['x-fixture-nonce']===nonce){
  if(Object.keys(body).some(k=>!['status','account','authStatus','httpStatus','delay'].includes(k))||body.status!==undefined&&!['ready','pending','unknown','running','result_ready','stored','failed'].includes(body.status)||body.account!==undefined&&!['A','B'].includes(body.account)||body.authStatus!==undefined&&![200,401].includes(body.authStatus)||body.httpStatus!==undefined&&![200,401,403,503].includes(body.httpStatus)||body.delay!==undefined&&![0,250,16000].includes(body.delay)){json({},422);return;}
  Object.assign(state,body);json({applied:true,counts,state});return;
 }
 if(req.url==='/api/auth/session'&&req.method==='GET'){
  counts.sessionGET++;json(state.authStatus===200?{user_id:currentOwner(),csrf_token:nonce}:{detail:{code:'AUTH_REQUIRED'}},state.authStatus);return;
 }
 if(req.url?.startsWith('/api/private/supervisor/core/')){
  if(state.authStatus!==200){fail('AUTH_REQUIRED',401);return;}
  if(state.httpStatus!==200){fail(state.httpStatus===401?'AUTH_REQUIRED':state.httpStatus===403?'AUTH_REQUEST_INVALID':'SERVICE_UNAVAILABLE',state.httpStatus);return;}
  if(req.method!=='GET'&&req.headers['x-csrf-token']!==nonce){fail('AUTH_REQUEST_INVALID',403);return;}
  if(state.delay)await new Promise(resolve=>setTimeout(resolve,state.delay));
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
 if(req.url==='/'||req.url==='/research'){
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CF023 synthetic production chat</title><link rel="stylesheet" href="/chat.css"><div id="app"></div><script nonce="'+nonce+'" src="/bundle.js"></script>');return;
 }
 json({},404);
});
const deadline=setTimeout(()=>{expired=true;server.closeAllConnections();server.close(finish);},590000);
try{
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(cap.ports[0],'127.0.0.1',resolve);});
 fs.writeFileSync('cf019-ready.json',JSON.stringify({nonce,pid:process.pid,cwd:process.cwd(),port:cap.ports[0]}),{mode:0o600});
 await stopped;
 if(expired)throw Error('Core browser evidence incomplete');
 console.log('CF023_FIXTURE_CLOSED '+JSON.stringify(counts));
}finally{
 clearTimeout(deadline);server.closeAllConnections();
 if(server.listening)await new Promise(resolve=>server.close(resolve));
 fs.rmSync('cf019-ready.json',{force:true});
 for(const record of cap.reactProduction)checked(record);
}
