// Only request identity belongs in tab storage. Never store a session/token/result.
export type PendingAnalysis={ticker:string;question:string;as_of:string;idempotency_key:string;analysis_id?:string};
export type AnalysisState='running'|'result_ready'|'stored'|'failed'|'unknown';
export type AnalysisView={analysis_id:string;admission_request_id:string;attempt_id:string;state:AnalysisState;deadline_at:string;report_id:string|null;report_url:string|null;error:Record<string,unknown>|null};
const api='/api/private/flow/analyses';
const uuidPattern=/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
export const uuid=(v:unknown):v is string=>typeof v==='string'&&uuidPattern.test(v);
export function canonicalUuid(v:string):string{if(!uuid(v))throw Error('Invalid identity');return v.toLowerCase();}
const record=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
const stamp=(v:unknown):v is string=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}T/.test(v)&&Number.isFinite(Date.parse(v));

export type AnalysisSafeCode='USAGE_LIMIT_EXCEEDED';
export class AnalysisHttpError extends Error {constructor(public readonly status:number,public readonly code:AnalysisSafeCode|null=null){super(code==='USAGE_LIMIT_EXCEEDED'?'분석 사용 한도에 도달했습니다. 입력과 멱등키는 유지됩니다. 기존 결과는 상태 다시 조회로 확인할 수 있습니다.':'분석 요청을 확인할 수 없습니다.');}}
export function pendingKey(user:string):string{return 'verith.flow.analysis.v1:'+canonicalUuid(user);}
export function pendingValue(v:unknown):PendingAnalysis{
 if(!record(v)||Object.keys(v).some(k=>!['ticker','question','as_of','idempotency_key','analysis_id'].includes(k))||
    typeof v.ticker!=='string'||!/^\d{6}$/.test(v.ticker)||typeof v.question!=='string'||!v.question.trim()||v.question.length>2000||
    !stamp(v.as_of)||new Date(v.as_of).toISOString()!==v.as_of||!uuid(v.idempotency_key)||v.analysis_id!==undefined&&!uuid(v.analysis_id))throw Error('요청 기록이 손상됐습니다.');
 const value:PendingAnalysis={ticker:v.ticker,question:v.question,as_of:v.as_of,idempotency_key:canonicalUuid(v.idempotency_key),...(v.analysis_id===undefined?{}:{analysis_id:canonicalUuid(v.analysis_id)})};
 if(new TextEncoder().encode(JSON.stringify({...value,analysis_id:undefined,allow_analysis:true})).byteLength>4096)throw Error('요청이 너무 깁니다.');
 return value;
}
export function freshPending(ticker:string,question:string):PendingAnalysis{return pendingValue({ticker,question,as_of:new Date().toISOString(),idempotency_key:crypto.randomUUID()});}
export function readPending(store:Storage,user:string):PendingAnalysis|null{const raw=store.getItem(pendingKey(user));if(raw===null)return null;if(raw.length>8192)throw Error('요청 기록이 손상됐습니다.');return pendingValue(JSON.parse(raw));}
export function writePending(store:Storage,user:string,value:PendingAnalysis):void{store.setItem(pendingKey(user),JSON.stringify(pendingValue(value)));}

export function analysisView(v:unknown):AnalysisView{
 if(!record(v)||Object.keys(v).sort().join(',')!=='admission_request_id,analysis_id,attempt_id,deadline_at,error,report_id,report_url,state'||
    !uuid(v.analysis_id)||!uuid(v.admission_request_id)||!uuid(v.attempt_id)||!stamp(v.deadline_at)||
    !['running','result_ready','stored','failed','unknown'].includes(String(v.state)))throw new AnalysisHttpError(502);
 const state=v.state as AnalysisState;
 if(state==='stored'){
  if(!uuid(v.report_id)||v.report_url!=='/reports/flow/'+canonicalUuid(v.report_id)||v.error!==null)throw new AnalysisHttpError(502);
 }else if(v.report_id!==null||v.report_url!==null)throw new AnalysisHttpError(502);
 if(['failed','unknown'].includes(state)){
  if(!record(v.error)||typeof v.error.code!=='string')throw new AnalysisHttpError(502);
 }else if(v.error!==null)throw new AnalysisHttpError(502);
 return {analysis_id:canonicalUuid(v.analysis_id),admission_request_id:canonicalUuid(v.admission_request_id),attempt_id:canonicalUuid(v.attempt_id),state,
  deadline_at:v.deadline_at,report_id:typeof v.report_id==='string'?canonicalUuid(v.report_id):null,report_url:typeof v.report_url==='string'?v.report_url:null,error:record(v.error)?v.error:null};
}
export async function wire(response:Response):Promise<AnalysisView>{
 let value:unknown;try{value=await response.json();}catch{throw new AnalysisHttpError(502);}
 if(!record(value)||!uuid(value.request_id)||Object.keys(value).sort().join(',')!=='data,error,request_id')throw new AnalysisHttpError(502);
 if(!response.ok){
  const limited=response.status===429&&value.data===null&&record(value.error)&&Object.keys(value.error).sort().join(',')==='code,message'&&value.error.code==='USAGE_LIMIT_EXCEEDED'&&typeof value.error.message==='string';
  throw new AnalysisHttpError(response.status,limited?'USAGE_LIMIT_EXCEEDED':null);
 }
 if(value.error!==null)throw new AnalysisHttpError(502);
 const view=analysisView(value.data);
 if(response.status!==(['stored','failed'].includes(view.state)?200:202))throw new AnalysisHttpError(502);
 return view;
}
export async function fetchSession(signal:AbortSignal):Promise<{user_id:string;csrf_token:string}>{
 const response=await fetch('/api/auth/session',{cache:'no-store',signal});if(!response.ok)throw new AnalysisHttpError(response.status);
 const v:unknown=await response.json();if(!record(v)||!uuid(v.user_id)||typeof v.csrf_token!=='string'||!v.csrf_token)throw new AnalysisHttpError(502);
 return {user_id:canonicalUuid(v.user_id),csrf_token:v.csrf_token};
}
export async function getAnalysis(id:string,signal:AbortSignal):Promise<AnalysisView>{
 const view=await wire(await fetch(api+'/'+canonicalUuid(id),{cache:'no-store',signal}));if(view.analysis_id!==canonicalUuid(id))throw new AnalysisHttpError(502);return view;
}
export async function postAnalysis(pending:PendingAnalysis,csrf:string,signal:AbortSignal):Promise<AnalysisView>{
 const v=pendingValue(pending);
 const view=await wire(await fetch(api,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
  body:JSON.stringify({ticker:v.ticker,question:v.question,as_of:v.as_of,idempotency_key:v.idempotency_key,allow_analysis:true}),cache:'no-store',signal}));
 if(v.analysis_id!==undefined&&v.analysis_id!==view.analysis_id)throw new AnalysisHttpError(502);return view;
}
export function analysisHref(id:string):string{return '/research?analysis_id='+canonicalUuid(id);}
export function canReplay(id:string|null,pending:PendingAnalysis|null):boolean{
 return pending!==null&&(id===null||pending.analysis_id!==undefined&&canonicalUuid(pending.analysis_id)===canonicalUuid(id));
}
export function matchesAnalysisUrl(pathname:string,search:string,id:string|null):boolean{
 if(pathname!=='/research')return false;
 const query=new URLSearchParams(search),values=query.getAll('analysis_id');
 if([...query.keys()].some(k=>k!=='analysis_id')||values.length>1)return false;
 if(id===null)return values.length===0;
 return values.length===1&&uuid(values[0])&&canonicalUuid(values[0])===canonicalUuid(id);
}

export class AnalysisIntent{
 private generation=0;private busy=false;
 invalidate():void{this.generation++;this.busy=false;}
 begin():number|null{if(this.busy)return null;this.busy=true;return ++this.generation;}
 accepts(ticket:number):boolean{return this.generation===ticket;}
 finish(ticket:number):void{if(this.accepts(ticket))this.busy=false;}
}

// One fixed budget per analysis; responses and timer reservations cannot extend it.
export class AnalysisObservation {
 private id:string|null=null;
 private started=0;
 private last=0;
 private until=0;
 private finalUsed=false;
 private deadlineBound=false;
 private closed=false;
 begin(id:string,monotonic:number):void{
  id=canonicalUuid(id);if(this.id===id)return;
  this.id=id;this.started=this.last=monotonic;this.until=monotonic+120000;this.finalUsed=false;this.deadlineBound=false;
  this.closed=!Number.isFinite(monotonic)||monotonic<0;
 }
 stop():void{this.closed=true;}
 permit(monotonic:number):boolean{
  if(this.id===null||this.closed)return false;
  if(!Number.isFinite(monotonic)||monotonic<this.last){this.closed=true;return false;}
  this.last=monotonic;
  if(monotonic>=this.until){
   if(this.finalUsed){this.closed=true;return false;}
   this.finalUsed=true;
  }
  return true;
 }
 next(view:AnalysisView,monotonic:number,wall:number):{kind:'stop'|'wait'|'final';delay:number}{
  const stop=()=>({kind:'stop' as const,delay:0});
  if(this.closed)return stop();
  if(!uuid(view.analysis_id)||canonicalUuid(view.analysis_id)!==this.id||view.state!=='running'||!Number.isFinite(monotonic)||monotonic<this.last||!Number.isFinite(wall)){
   this.closed=true;return stop();
  }
  this.last=monotonic;
  if(!this.deadlineBound){
   const deadline=Date.parse(view.deadline_at);
   if(!stamp(view.deadline_at)||!/(?:Z|[+-]\d{2}:\d{2})$/i.test(view.deadline_at)||!Number.isFinite(deadline)){this.closed=true;return stop();}
   this.until=Math.min(this.started+120000,monotonic+Math.max(0,deadline-wall));this.deadlineBound=true;
  }
  if(this.finalUsed){this.closed=true;return stop();}
  if(monotonic<this.until)return {kind:'wait',delay:Math.min(1000,this.until-monotonic)};
  return {kind:'final',delay:0};
 }
}

export function observationId(urlId:string|null,pendingId:string|undefined|null):string|null{
 // An explicit URL can never be replaced by another tab's pending identity.
 if(urlId!==null)return uuid(urlId)?canonicalUuid(urlId):null;
 return uuid(pendingId)?canonicalUuid(pendingId):null;
}
export class AnalysisAccountChanged extends Error{}
export async function observeAnalysis(userId:string,id:string|null,signal:AbortSignal,current:()=>boolean,allowRead:()=>boolean=()=>true):Promise<{view:AnalysisView|null;stopped?:boolean}|null>{
 try{
 if(!current())return null;
 if(signal.aborted)throw new AnalysisHttpError(503);
 const session=await fetchSession(signal);
 if(!current())return null;
 if(signal.aborted)throw new AnalysisHttpError(503);
 if(session.user_id!==canonicalUuid(userId))throw new AnalysisAccountChanged('로그인 계정이 변경됐습니다.');
 if(id!==null&&!allowRead())return {view:null,stopped:true};
 const view=id===null?null:await getAnalysis(canonicalUuid(id),signal);
 if(!current())return null;
 if(signal.aborted)throw new AnalysisHttpError(503);
 return {view};
 }catch(error){if(!current())return null;
 if(signal.aborted)throw new AnalysisHttpError(503);throw error;}
}
