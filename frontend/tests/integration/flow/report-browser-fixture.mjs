// Real installed production React + synthetic HTTP in the same protected unit worker.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import ts from 'typescript';
import {reactProductionFiles} from '../../../scripts/check-local-ports.mjs';
const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
if(cap.workload!=='unit'||cap.ports.length!==2||cap.lifetime>600||cap.root!==process.cwd()||cap.reactProduction?.length!==5)throw Error('CF019 exact unit capability required');
const A='11111111-1111-4111-8111-111111111111',B='22222222-2222-4222-8222-222222222222',R='33333333-3333-4333-8333-333333333333',S='44444444-4444-4444-8444-444444444444';
function checkedProduction(record){
 const file=path.join(cap.dependency,record.relative),meta=fs.lstatSync(file),data=fs.readFileSync(file);
 if(!reactProductionFiles.includes(record.relative)||fs.realpathSync(file)!==file||!meta.isFile()||meta.nlink!==1||meta.size!==record.size||crypto.createHash('sha256').update(data).digest('hex')!==record.sha256)throw Error('CF019 production dependency drift');
 return data.toString();
}
const modules={},ids=['react','react/jsx-runtime','react-dom','react-dom/client','scheduler'];
for(let i=0;i<5;i++){if(cap.reactProduction[i].relative!==reactProductionFiles[i])throw Error('CF019 exact registry');modules[ids[i]]=checkedProduction(cap.reactProduction[i]);}
for(const [id,file] of Object.entries({
 '@/features/flow/lib/report-display':'src/features/flow/lib/report-display.ts','@/features/flow/lib/report-deletion':'src/features/flow/lib/report-deletion.ts',
 '@/features/flow/lib/analysis-request':'src/features/flow/lib/analysis-request.ts','../lib/query-plan':'src/features/supervisor/lib/query-plan.ts',QueryPreparation:'src/features/supervisor/components/query-preparation.tsx',
 '@/features/flow/lib/observation-window':'src/features/flow/lib/observation-window.ts',SessionControls:'src/features/flow/components/session-controls.tsx',FlowReportView:'src/features/flow/components/flow-report-view.tsx'}))
 modules[id]=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
let account=A,status=204,authStatus=200,reportStatus=200,delay=0;const removed=new Set(),counts={sessionGET:0,reportGET:0,DELETE:0,plansPOST:0,analysisPOST:0},nonce=cap.nonce,origin='http://127.0.0.1:'+cap.ports[0];
const planningOnly=cap.cf020Planning===true;
const payload={meta:{stock_name:'합성 표시 종목',ticker:'000000',base_date:'2026-11-06'},report_id:R,signals:{strength:{외국인:{ratio:0,strong:false},기관:{ratio:null,strong:false}},consecutive:{},inst_detail:{기금:0,증권:-1}},verification:{outcome:'fact_only',regen_count:0},interpretation:null};
const bundle=`const registry={${Object.entries(modules).map(([id,body])=>JSON.stringify(id)+':function(module,exports,require){'+body+'\n}').join(',')}};const cache={};function require(id){if(!Object.hasOwn(registry,id))throw Error('Closed registry');if(!cache[id]){const m={exports:{}};cache[id]=m;registry[id](m,m.exports,require);}return cache[id].exports;}
const React=require('react'),root=require('react-dom/client').createRoot(document.getElementById('app')),Controls=require('SessionControls').SessionControls,View=require('FlowReportView').FlowReportView;
function App(){const [id,setId]=React.useState(${JSON.stringify(R)}),[stats,setStats]=React.useState(''),[display,setDisplay]=React.useState('missing'),[controlState,setControlState]=React.useState({phase:'idle',text:'합성 제어 미적용'});const controlLock=React.useRef(false),recheckClicks=React.useRef(0);const [focusState,setFocusState]=React.useState({hasFocus:false,visibility:'unknown',recheckClicks:0});

 const shown={...${JSON.stringify(payload)},report_id:id,signals:{...${JSON.stringify(payload.signals)}}};
 const ratios=display==='zero'?[0,0]:display==='tiny'?[1e-8,-1e-8]:display==='large'?[1.234,.2]:[null,null];
 shown.signals.strength={외국인:{ratio:ratios[0],strong:false},기관:{ratio:ratios[1],strong:false}};
 shown.signals.inst_detail=display==='negative'?{기금:-1,증권:-2}:display==='zero'?{기금:0,증권:-1}:{기금:0,증권:null};
 if(display==='tiny')shown.signals.price_daily=[{date:'2026-11-06',close:10000,change:-1e-12,change_rate:1e-12,volume:0,inst_qty:null,frgn_qty:0}];
 async function control(value){
  if(controlLock.current)return;controlLock.current=true;setControlState({phase:'pending',text:'합성 제어 적용 중'});
  try{const response=await fetch('/fixture-control',{method:'POST',headers:{'Content-Type':'application/json','X-Fixture-Nonce':${JSON.stringify(nonce)}},body:JSON.stringify(value),cache:'no-store',signal:AbortSignal.timeout(5000)});
   if(!response.ok)throw Error('Fixture control failed');const applied=await response.json();
   if(applied.updated!==true||!['A','B'].includes(applied.account)||![204,404,401,403,500].includes(applied.status)||![200,401,403].includes(applied.authStatus)||![200,401,403,404,500].includes(applied.reportStatus)||![0,250,16000].includes(applied.delay))throw Error('Fixture control failed');
   setControlState({phase:'complete',text:'적용 완료 · '+JSON.stringify({account:applied.account,status:applied.status,authStatus:applied.authStatus,reportStatus:applied.reportStatus,delay:applied.delay})});controlLock.current=false;
  }catch{setControlState({phase:'error',text:'합성 fixture 제어 오류 · 다음 클릭을 중단하고 새로고침하세요'});}
 }
 React.useEffect(()=>{
  const sample=()=>setFocusState({hasFocus:document.hasFocus(),visibility:document.visibilityState,recheckClicks:recheckClicks.current});
  const capture=event=>{if(event.target instanceof Element&&event.target.closest('button')?.textContent==='결과 상태 다시 확인'){recheckClicks.current++;sample();}};
  document.addEventListener('click',capture,true);
  const t=setInterval(()=>{sample();void fetch('/fixture-counts').then(r=>r.json()).then(v=>setStats(JSON.stringify(v)));},300);
  return()=>{clearInterval(t);document.removeEventListener('click',capture,true);};
 },[]);
 return React.createElement(React.Fragment,null,React.createElement('h1',null,'CF019 synthetic React fixture'),React.createElement('p',{'data-testid':'counts'},stats),React.createElement('p',{'data-testid':'focus-state'},'합성 focus 관측 · '+JSON.stringify(focusState)),React.createElement('p',{'role':'status','data-testid':'control-state'},controlState.text),React.createElement('fieldset',{disabled:controlState.phase==='pending'||controlState.phase==='error'},
 ...[['계정 A',{account:${JSON.stringify(A)}}],['계정 B',{account:${JSON.stringify(B)}}],['응답 204',{status:204}],['응답 404',{status:404}],['응답 401',{status:401}],['응답 403',{status:403}],['응답 500',{status:500}],['세션 401',{authStatus:401}],['세션 403',{authStatus:403}],['세션 200',{authStatus:200}],['보고서 404',{reportStatus:404}],['보고서 200',{reportStatus:200}],['지연 응답',{delay:250}],['15초 초과 DELETE',{delay:16000}],['즉시 응답',{delay:0}],['합성 보고서 복원',{restore:true}]].map(([name,value])=>React.createElement('button',{key:name,onClick:()=>control(value)},name)),
 ...['missing','zero','tiny','large','negative'].map(name=>React.createElement('button',{key:'display-'+name,onClick:()=>setDisplay(name)},'표시 '+name)),
 React.createElement('button',{onClick:()=>{const next=id===${JSON.stringify(R)}?${JSON.stringify(S)}:${JSON.stringify(R)};history.pushState(null,'','/reports/flow/'+next);setId(next);}},'대상 변경'),
 React.createElement('button',{onClick:()=>fetch('/fixture-stop',{method:'POST',headers:{'X-Fixture-Nonce':${JSON.stringify(nonce)}}})},'fixture 종료')),
 React.createElement('div',{inert:controlState.phase==='pending'||controlState.phase==='error'},React.createElement(Controls,{csrfToken:'synthetic',reportId:id,userId:${JSON.stringify(A)},returnTo:'/?limit=20&offset=40'},React.createElement(View,{payload:shown}))));}
function PlanningApp(){
 const Preparation=require('QueryPreparation').QueryPreparation,analysis=require('@/features/flow/lib/analysis-request');
 const [prepared,setPrepared]=React.useState(null),[consent,setConsent]=React.useState(false),[stats,setStats]=React.useState(''),[outcome,setOutcome]=React.useState(''),[accountRevision,setAccountRevision]=React.useState(0);const locked=React.useRef(false);
 const clear=React.useCallback(()=>{setPrepared(null);setConsent(false);},[]);
 React.useEffect(()=>{const timer=setInterval(()=>fetch('/fixture-counts').then(r=>r.json()).then(v=>setStats(JSON.stringify(v))),300);return()=>clearInterval(timer);},[]);
 async function execute(){
  if(locked.current||!prepared||!consent)return;locked.current=true;
  const abort=new AbortController();const timer=setTimeout(()=>abort.abort(),15000);
  try{const session=await analysis.fetchSession(abort.signal);if(session.user_id!==${JSON.stringify(A)})throw Error('Synthetic account mismatch');const pending=analysis.freshPending(prepared.ticker,prepared.query);const value=await analysis.postAnalysis(pending,session.csrf_token,abort.signal);setOutcome('기존 실제 helper 합성 POST 완료 · '+value.state);}
  catch{setOutcome('합성 실행 확인 실패');}finally{clearTimeout(timer);locked.current=false;}
 }
 return React.createElement(React.Fragment,null,React.createElement('h1',null,'CF020 synthetic preparation React'),React.createElement('p',{'data-testid':'counts'},stats),
 React.createElement(Preparation,{key:accountRevision,userId:${JSON.stringify(A)},onPrepared:setPrepared,onClear:clear,onAccountChange:()=>{clear();setAccountRevision(v=>v+1);}}),
 React.createElement('label',null,React.createElement('input',{type:'checkbox',checked:consent,disabled:!prepared,onChange:e=>setConsent(e.target.checked)}),'단일 Flow 분석 실행 동의'),
 React.createElement('button',{disabled:!prepared||!consent,onClick:()=>void execute()},'확정 입력으로 기존 분석 POST'),React.createElement('p',{'role':'status'},outcome),
 ...[['계정 A',{account:${JSON.stringify(A)}}],['계정 B',{account:${JSON.stringify(B)}}],['계획 지연',{delay:250}],['계획 즉시',{delay:0}]].map(([label,value])=>React.createElement('button',{key:label,onClick:async()=>{try{const r=await fetch('/fixture-control',{method:'POST',headers:{'Content-Type':'application/json','X-Fixture-Nonce':${JSON.stringify(nonce)}},body:JSON.stringify(value)});if(!r.ok)throw Error();setOutcome('합성 제어 적용 완료');}catch{setOutcome('합성 제어 오류 · 중단');}}},label)));
}
root.render(React.createElement(${JSON.stringify(planningOnly)}?PlanningApp:App));`;
let finish,expired=false;const stopped=new Promise(resolve=>{finish=resolve;});
const server=http.createServer(async(req,res)=>{
 res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Content-Security-Policy',`default-src 'none'; script-src 'nonce-${nonce}'; connect-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`);
 const p=req.url.split('?')[0],json=(v,code=200)=>{res.writeHead(code,{'Content-Type':'application/json'});res.end(JSON.stringify(v));};
 if(req.headers.origin&&req.headers.origin!==origin){json({},403);return;}
 if(p==='/fixture-stop'&&req.method==='POST'&&req.headers['x-fixture-nonce']===nonce){json({stopped:true});server.close(()=>finish());return;}
 if(p==='/fixture-control'&&req.method==='POST'&&req.headers['x-fixture-nonce']===nonce){
  let raw='';for await(const chunk of req){raw+=chunk;if(raw.length>1024){json({},422);return;}}
  let value;try{value=JSON.parse(raw);}catch{json({},422);return;}
  if(value.account===A||value.account===B)account=value.account;if([204,404,401,403,500].includes(value.status))status=value.status;if([200,401,403].includes(value.authStatus))authStatus=value.authStatus;if([200,404,401,403,500].includes(value.reportStatus))reportStatus=value.reportStatus;if([0,250,16000].includes(value.delay))delay=value.delay;if(value.restore===true){removed.clear();status=204;authStatus=200;reportStatus=200;delay=0;}json({updated:true,account:account===A?'A':'B',status,authStatus,reportStatus,delay});return;
 }
 if(p==='/fixture-counts'&&req.method==='GET'){json(counts);return;}
 if(planningOnly&&p==='/api/private/flow/plans'&&req.method==='POST'){
  counts.plansPOST++;let raw='';for await(const chunk of req){raw+=chunk;if(Buffer.byteLength(raw)>4096){json({},422);return;}}
  let value;try{value=JSON.parse(raw);if(typeof value.query!=='string'||!value.query.trim()||value.query.length>300)throw Error();}catch{json({},422);return;}
  if(account!==A||req.headers['x-csrf-token']!=='synthetic-fresh-csrf'){json({},401);return;}
  const question=value.query;if(delay)await new Promise(resolve=>setTimeout(resolve,delay));
  const stock={stock_code:'005930',stock_name:'합성 삼성전자',market:'KOSPI'},candidate={...stock,match_type:'ambiguous_group'};
  const unsupported=/차트|종합|뉴스|rsi|이동평균/i.test(question),flow=/수급|외국인|기관/.test(question),ambiguous=question.includes('모호');
  const status=unsupported?'unsupported':!flow?'needs_clarification':ambiguous&&!value.selected_ticker?'needs_stock_selection':'ready_for_confirmation';
  const resolution=['unsupported','needs_clarification'].includes(status)?null:{status:status==='needs_stock_selection'?'ambiguous':'resolved',reason:status==='needs_stock_selection'?'ambiguous_alias':'exact_match',stock:status==='needs_stock_selection'?null:stock,candidates:status==='needs_stock_selection'?[candidate]:[]};
  const plan={version:'supervisor.flow-plan.v1',policy_version:'supervisor.flow-only.1',query_sha256:crypto.createHash('sha256').update(question).digest('hex'),requested_views:unsupported?['technical']:flow?['flow']:[],status,reason:{unsupported:'unsupported_views',needs_clarification:'clarify_intent',needs_stock_selection:'stock_ambiguous',ready_for_confirmation:'stock_resolved'}[status],resolution,candidate_ref:resolution?'a'.repeat(64):null};
  json({request_id:A,data:plan,error:null});return;
 }
 if(planningOnly&&p==='/api/private/flow/analyses'&&req.method==='POST'){
  counts.analysisPOST++;let raw='';for await(const chunk of req){raw+=chunk;if(Buffer.byteLength(raw)>4096){json({},422);return;}}
  let value;try{value=JSON.parse(raw);if(value.ticker!=='005930'||typeof value.question!=='string'||value.allow_analysis!==true||typeof value.idempotency_key!=='string')throw Error();}catch{json({},422);return;}
  if(account!==A||req.headers['x-csrf-token']!=='synthetic-fresh-csrf'){json({},401);return;}
  json({request_id:A,data:{analysis_id:A,admission_request_id:B,attempt_id:S,state:'stored',deadline_at:new Date(Date.now()+120000).toISOString(),report_id:R,report_url:'/reports/flow/'+R,error:null},error:null});return;
 }
 if(p==='/api/auth/session'&&req.method==='GET'){counts.sessionGET++;json(authStatus===200?{user_id:account,csrf_token:'synthetic-fresh-csrf'}:{},authStatus);return;}
 if(['/api/private/flow/reports/'+R,'/api/private/flow/reports/'+S].includes(p)){
  if(req.method==='GET'){counts.reportGET++;json({report_id:p.endsWith(R)?R:S,report:{report_id:p.endsWith(R)?R:S}},removed.has(p.endsWith(R)?R:S)?404:reportStatus);return;}
  if(req.method==='DELETE'){counts.DELETE++;const selected=status;if(delay)await new Promise(resolve=>setTimeout(resolve,delay));if(account!==A||req.headers['x-csrf-token']!=='synthetic-fresh-csrf'){json({},403);return;}if(selected===204){removed.add(p.endsWith(R)?R:S);res.writeHead(204);res.end();}else json({},selected);return;}
 }
 if(p==='/bundle.js'&&req.method==='GET'){res.writeHead(200,{'Content-Type':'text/javascript'});res.end(bundle);return;}
 if(p.startsWith('/reports/flow/')&&req.method==='GET'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(`<!doctype html><meta charset="utf-8"><title>CF019 synthetic fixture</title><div id="app"></div><script nonce="${nonce}" src="/bundle.js"></script>`);return;}
 if(p==='/'&&req.method==='GET'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end('<h1>합성 보관함</h1><p>204 navigation target</p>');return;}
 json({},404);
});
const deadline=setTimeout(()=>{expired=true;server.closeAllConnections();server.close(()=>finish());},590000);
try{
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(cap.ports[0],'127.0.0.1',resolve);});
 fs.writeFileSync('cf019-ready.json',JSON.stringify({nonce,pid:process.pid,cwd:process.cwd(),port:cap.ports[0]}),{mode:0o600});
 await stopped;if(expired)throw Error('CF019 deadline: browser evidence incomplete');console.log('CF019_FIXTURE_CLOSED '+JSON.stringify({counts,click_evidence:'separate observation required'}));
}finally{
 clearTimeout(deadline);server.closeAllConnections();if(server.listening)await new Promise(resolve=>server.close(resolve));fs.rmSync('cf019-ready.json',{force:true});for(const record of cap.reactProduction)checkedProduction(record);
}
