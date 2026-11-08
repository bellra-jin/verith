// Only request identity belongs in tab storage. Never store a session/token/result.
export type PendingAnalysis={ticker:string;question:string;idempotency_key:string;analysis_id?:string};
export type AnalysisState='running'|'result_ready'|'stored'|'failed'|'unknown';
export type AnalysisView={analysis_id:string;admission_request_id:string;attempt_id:string;state:AnalysisState;deadline_at:string;report_id:string|null;report_url:string|null;error:Record<string,unknown>|null};
const api='/api/private/fundamental/analyses';
const uuidPattern=/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
export const uuid=(v:unknown):v is string=>typeof v==='string'&&uuidPattern.test(v);
export function canonicalUuid(v:string):string{if(!uuid(v))throw Error('Invalid identity');return v.toLowerCase();}
const record=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
const stamp=(v:unknown):v is string=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}T/.test(v)&&Number.isFinite(Date.parse(v));

export class AnalysisHttpError extends Error {constructor(public readonly status:number){super('분석 요청을 확인할 수 없습니다.');}}
export function pendingKey(user:string):string{return 'verith.fundamental.analysis.v1:'+canonicalUuid(user);}
export function pendingValue(v:unknown):PendingAnalysis{
 if(!record(v)||Object.keys(v).some(k=>!['ticker','question','idempotency_key','analysis_id'].includes(k))||
    typeof v.ticker!=='string'||!/^\d{6}$/.test(v.ticker)||typeof v.question!=='string'||!v.question.trim()||v.question.length>2000||
    !uuid(v.idempotency_key)||v.analysis_id!==undefined&&!uuid(v.analysis_id))throw Error('요청 기록이 손상됐습니다.');
 const value:PendingAnalysis={ticker:v.ticker,question:v.question,idempotency_key:canonicalUuid(v.idempotency_key),...(v.analysis_id===undefined?{}:{analysis_id:canonicalUuid(v.analysis_id)})};
 if(new TextEncoder().encode(JSON.stringify({...value,analysis_id:undefined,allow_analysis:true})).byteLength>4096)throw Error('요청이 너무 깁니다.');
 return value;
}
export function freshPending(ticker:string,question:string):PendingAnalysis{return pendingValue({ticker,question,idempotency_key:crypto.randomUUID()});}
export function readPending(store:Storage,user:string):PendingAnalysis|null{const raw=store.getItem(pendingKey(user));if(raw===null)return null;if(raw.length>8192)throw Error('요청 기록이 손상됐습니다.');return pendingValue(JSON.parse(raw));}
export function writePending(store:Storage,user:string,value:PendingAnalysis):void{store.setItem(pendingKey(user),JSON.stringify(pendingValue(value)));}

export function analysisView(v:unknown):AnalysisView{
 if(!record(v)||Object.keys(v).sort().join(',')!=='admission_request_id,analysis_id,attempt_id,deadline_at,error,report_id,report_url,state'||
    !uuid(v.analysis_id)||!uuid(v.admission_request_id)||!uuid(v.attempt_id)||!stamp(v.deadline_at)||
    !['running','result_ready','stored','failed','unknown'].includes(String(v.state)))throw new AnalysisHttpError(502);
 const state=v.state as AnalysisState;
 if(state==='stored'){
  if(!uuid(v.report_id)||v.report_url!=='/reports/fundamental/'+canonicalUuid(v.report_id)||v.error!==null)throw new AnalysisHttpError(502);
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
 if(!response.ok)throw new AnalysisHttpError(response.status);
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
  body:JSON.stringify({ticker:v.ticker,question:v.question,idempotency_key:v.idempotency_key,allow_analysis:true}),cache:'no-store',signal}));
 if(v.analysis_id!==undefined&&v.analysis_id!==view.analysis_id)throw new AnalysisHttpError(502);return view;
}
export function analysisHref(id:string):string{return '/fundamental?analysis_id='+canonicalUuid(id);}
export function canReplay(id:string|null,pending:PendingAnalysis|null):boolean{
 return pending!==null&&(id===null||pending.analysis_id!==undefined&&canonicalUuid(pending.analysis_id)===canonicalUuid(id));
}
export function matchesAnalysisUrl(pathname:string,search:string,id:string|null):boolean{
 if(pathname!=='/fundamental')return false;
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

export function safeSourceUrl(value:unknown):string|null{if(typeof value!=='string')return null;try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:null;}catch{return null;}}
export function displayValue(value:unknown):string{if(value===null||value===undefined)return '자료 없음';if(typeof value==='string')return value;if(typeof value==='number'&&Number.isFinite(value)||typeof value==='boolean')return String(value);return '미확인';}
// Stored UUID text is preserved; URL identities remain strict canonical UUIDs.
export function storedUuid(value:unknown):string|null{
 if(typeof value!=='string')return null;let v=value;
 if(v.startsWith('urn:uuid:'))v=v.slice(9);
 if(v.startsWith('{')&&v.endsWith('}'))v=v.slice(1,-1);
 if(/^[0-9a-f]{32}$/i.test(v))v=v.slice(0,8)+'-'+v.slice(8,12)+'-'+v.slice(12,16)+'-'+v.slice(16,20)+'-'+v.slice(20);
 return uuid(v)?v.toLowerCase():null;
}
