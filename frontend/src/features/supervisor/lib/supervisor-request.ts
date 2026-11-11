// Fixed owner/key recovery. No session tokens, results or plan bodies in storage.
import {canonicalUuid,uuid,fetchSession,AnalysisAccountChanged,analysisView,readPending as readFlowPending,AnalysisHttpError} from '@/features/flow/lib/analysis-request';
import type {Draft,Plan,Outcome,Confirm,Pending,Answer,Preparation,PrepareBody,PreparePending} from '../model/chat';
export const VERSION='supervisor.core.v1';
const views=['flow','technical','fundamental','macro','industry','news','overview'];
export const object=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
const hex=(v:unknown):v is string=>typeof v==='string'&&/^[0-9a-f]{64}$/.test(v);
export class CoreHttpError extends Error{constructor(public status:number,public code:string='SERVICE_UNAVAILABLE'){super('요청을 확인할 수 없습니다. 고정된 요청을 보존하고 상태를 다시 확인해 주세요.');
}}
export function canonical(v:unknown):string{
 if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';
 if(object(v))return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';
 if(v===null||typeof v==='string'||typeof v==='boolean'||typeof v==='number'&&Number.isFinite(v))return JSON.stringify(v);
 throw new CoreHttpError(422);
}
export async function hash(v:unknown){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(v)))),n=>n.toString(16).padStart(2,'0')).join('');
}
export function draftValue(v:unknown):Draft{
 if(!object(v)||Object.keys(v).some(k=>!['original_query','answers','revision','selected_ticker','candidate_ref'].includes(k))||typeof v.original_query!=='string'||!v.original_query.trim()||v.original_query.length>2000||v.original_query.includes('\0')||!Number.isInteger(v.revision)||Number(v.revision)<0||Number(v.revision)>4||!Array.isArray(v.answers)||v.answers.length>8)throw new CoreHttpError(422);
 for(const a of v.answers)if(!object(a)||Object.keys(a).sort().join(',')!=='answer_id,slot,value'||!uuid(a.answer_id)||!['stock','views','flow_focus','period','scope'].includes(String(a.slot))||typeof a.value!=='string'||!a.value.trim()||a.value.length>300)throw new CoreHttpError(422);
 if(new Set(v.answers.map(a=>a.answer_id)).size!==v.answers.length||Number(v.revision)>v.answers.length||v.revision===0&&v.answers.length)throw new CoreHttpError(422);
 if((v.selected_ticker==null)!=(v.candidate_ref==null)||v.selected_ticker!=null&&(typeof v.selected_ticker!=='string'||!/^\d{6}$/.test(v.selected_ticker)||!hex(v.candidate_ref)))throw new CoreHttpError(422);
 return v as Draft;
}
export async function planValue(v:unknown,draft?:Draft):Promise<Plan>{
 if(!object(v)||v.schema_version!==VERSION||!['supervisor.flow-core.1','supervisor.flow-core.2'].includes(String(v.policy_version))||!object(v.frame)||!hex(v.plan_hash)||!Array.isArray(v.requested_views)||v.requested_views.some(x=>!views.includes(String(x)))||!Array.isArray(v.selected_views)||v.selected_views.some(x=>x!=='flow')||!Array.isArray(v.capabilities)||!Array.isArray(v.required_waivers)||typeof v.partial!=='boolean'||!['ready','scope_confirmation','needs_clarification','needs_stock_selection','selection_stale','not_found','unsupported'].includes(String(v.status)))throw new CoreHttpError(502);
 const {plan_hash,...semantic}=v;
 if(await hash(semantic)!==plan_hash||typeof v.frame.original_query!=='string'||v.frame.query_sha256!==await hash(v.frame.original_query))throw new CoreHttpError(502);
 if(draft?.selected_ticker&&['ready','scope_confirmation'].includes(String(v.status))&&(!object(v.resolution)||!object(v.resolution.stock)||v.resolution.stock.stock_code!==draft.selected_ticker||v.candidate_ref!==draft.candidate_ref))throw new CoreHttpError(502);
 if(draft&&(v.frame.original_query!==draft.original_query||v.frame.revision!==draft.revision||canonical(v.frame.answers)!==canonical(draft.answers)))throw new CoreHttpError(502);
 if(['ready','scope_confirmation'].includes(String(v.status))&&(!object(v.resolution)||v.resolution.status!=='resolved'||!object(v.resolution.stock)||typeof v.resolution.stock.stock_code!=='string'||!/^\d{6}$/.test(v.resolution.stock.stock_code)||v.selected_views.join(',')!=='flow'))throw new CoreHttpError(502);
 return v as Plan;
}
export async function outcomeValue(v:unknown):Promise<Outcome>{
 if(!object(v)||!uuid(v.supervisor_id)||!['confirmed','deleted'].includes(String(v.plan_status))||!['pending','partial','fulfilled','unfulfilled','deleted'].includes(String(v.coverage))||!Array.isArray(v.views))throw new CoreHttpError(502);
 if(v.plan_status==='deleted'){if(v.plan!==null||v.effective_scope!==null||v.flow!==null||v.views.length||v.coverage!=='deleted')throw new CoreHttpError(502);
 }else{
  await planValue(v.plan);
  if(!object(v.effective_scope)||!Array.isArray(v.effective_scope.waived_conditions)||v.effective_scope.fixed_observation_window!==true||v.effective_scope.all_subjects_retained!==true)throw new CoreHttpError(502);
  if(v.flow!==null)analysisView(v.flow);
 }
 return v as Outcome;
}
async function bounded(response:Response,signal:AbortSignal){
 const reader=response.body?.getReader();
 if(!reader)throw new CoreHttpError(502);
 const parts:Uint8Array[]=[];
 let size=0;
 const abort=()=>{void reader.cancel().catch(()=>{});
 };
 signal.addEventListener('abort',abort,{once:true});
 try{while(true){if(signal.aborted)throw new CoreHttpError(504);
 const next=await reader.read();
 if(signal.aborted)throw new CoreHttpError(504);
 if(next.done)break;
 size+=next.value.byteLength;
 if(size>65536){await reader.cancel();
 throw new CoreHttpError(502);
 }parts.push(next.value);
 }
 const all=new Uint8Array(size);
 let offset=0;
 for(const p of parts){all.set(p,offset);
 offset+=p.length;
 }return JSON.parse(new TextDecoder('utf8',{fatal:true}).decode(all)) as unknown;
 }catch(e){if(e instanceof CoreHttpError)throw e;
 throw new CoreHttpError(signal.aborted?504:502);
 }finally{signal.removeEventListener('abort',abort);
 reader.releaseLock();
 }
}
export async function coreRequest(kind:'prepare'|'confirm'|'get',payload:Draft|Confirm|string,user:string,signal:AbortSignal,current:()=>boolean):Promise<Plan|Outcome>{
 const guard=()=>{if(signal.aborted||!current())throw new CoreHttpError(409);
 };
 guard();
 const session=await fetchSession(signal);
 guard();
 if(session.user_id!==canonicalUuid(user))throw new AnalysisAccountChanged();
 const path='/api/private/supervisor/core/'+(kind==='prepare'?'prepare':kind==='confirm'?'requests':'requests/'+canonicalUuid(String(payload)));
 const response=await globalThis.fetch(path,{...(kind==='get'?{}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf_token},body:JSON.stringify(payload)}),cache:'no-store',redirect:'error',signal});
 guard();
 const value=await bounded(response,signal);
 guard();
 if(!object(value)||value.schema_version!==VERSION||!uuid(value.request_id)||!uuid(value.trace_id))throw new CoreHttpError(502);
 if(!response.ok){const code=object(value.error)&&typeof value.error.code==='string'?value.error.code:'SERVICE_UNAVAILABLE';
 throw new CoreHttpError(response.status,['USAGE_LIMIT_EXCEEDED','PLAN_STALE','HANDOFF_EXPIRED','RESOURCE_NOT_FOUND','IDEMPOTENCY_CONFLICT','PREPARATION_EXPIRED','PREPARATION_DELETED','PREPARATION_CONSUMED','MEANING_LIMIT_EXCEEDED'].includes(code)?code:'SERVICE_UNAVAILABLE');
 }
 if(value.error!==null)throw new CoreHttpError(502);
 const result=kind==='prepare'?await planValue(value.data,payload as Draft):await outcomeValue(value.data);
 guard();
 const after=await fetchSession(signal);
 guard();
 if(after.user_id!==canonicalUuid(user))throw new AnalysisAccountChanged();
 if(kind==='get'&&(result as Outcome).supervisor_id!==canonicalUuid(String(payload)))throw new CoreHttpError(502);
 return result;
}
export function pendingKey(user:string){return 'verith.supervisor.core.v1:'+canonicalUuid(user);
}
export function pendingValue(v:unknown):Pending{
 if(!object(v)||Object.keys(v).some(k=>!['version','confirm','supervisor_id'].includes(k))||v.version!=='supervisor.core.pending.v1'||!object(v.confirm)||!uuid(v.confirm.client_key)||!hex(v.confirm.expected_plan_hash)||v.confirm.preparation_id!==undefined&&!uuid(v.confirm.preparation_id)||!object(v.confirm.consent)||v.confirm.consent.allow_flow!==true||typeof v.confirm.consent.allow_partial!=='boolean'||!Array.isArray(v.confirm.consent.waived_conditions)||v.supervisor_id!==undefined&&!uuid(v.supervisor_id))throw new CoreHttpError(422);
 draftValue(v.confirm.draft);
 if(new TextEncoder().encode(JSON.stringify(v.confirm)).byteLength>16384)throw new CoreHttpError(422);
 return v as Pending;
}
export function readPending(store:Storage,user:string):Pending|null{const raw=store.getItem(pendingKey(user));
if(raw===null)return null;
if(raw.length>32768)throw new CoreHttpError(422);
return pendingValue(JSON.parse(raw));
}
export function loadCoreRecovery(store:Storage|(()=>Storage),user:string,id:string|null){
 try{
  const pending=readPending(typeof store==='function'?store():store,user);
  const matching=id===null||pending?.supervisor_id!==undefined&&canonicalUuid(pending.supervisor_id)===canonicalUuid(id);
  return {pending:matching?pending:null,storageReadable:true};
 }catch{
  // A known owner-checked URL remains observable without trusting damaged storage.
  return {pending:null,storageReadable:false};
 }
}
export function clarificationSlot(slot:string):Answer['slot']{
 if(slot==='stock'||slot==='multi_stock'||slot==='scope')return 'stock';
 if(slot==='views')return 'views';
 if(slot==='period')return 'period';
 return 'scope';
}
export function writePending(store:Storage,user:string,pending:Pending){store.setItem(pendingKey(user),JSON.stringify(pendingValue(pending)));
}
export function freshPending(draft:Draft,plan:Plan,partial:boolean,waived:string[],preparationId?:string):Pending{return pendingValue({version:'supervisor.core.pending.v1',confirm:{...(preparationId?{preparation_id:canonicalUuid(preparationId)}:{}),client_key:crypto.randomUUID(),draft:draftValue(draft),expected_plan_hash:plan.plan_hash,consent:{allow_flow:true,allow_partial:partial,waived_conditions:waived}}});
}
export function matchesUrl(href:string,id:string|null){const u=new URL(href);
return u.pathname==='/research'&&[...u.searchParams.keys()].every(k=>k==='supervisor_id')&&(id===null?!u.searchParams.has('supervisor_id'):u.searchParams.getAll('supervisor_id').length===1&&uuid(u.searchParams.get('supervisor_id'))&&canonicalUuid(u.searchParams.get('supervisor_id')!)===canonicalUuid(id));
}

export function legacyFlowRecovery(store:Storage,user:string,supervisorId:string|null){return supervisorId===null&&readFlowPending(store,user)!==null;
}
export function canReplayCore(id:string|null,pending:Pending|null){return pending!==null&&(id===null||pending.supervisor_id!==undefined&&canonicalUuid(pending.supervisor_id)===canonicalUuid(id));
}
export function requiresReauthentication(error:unknown){return error instanceof AnalysisAccountChanged||error instanceof AnalysisHttpError&&error.status===401||error instanceof CoreHttpError&&error.status===401;
}
export function conditionLabel(kind:string){return ({focus:'집중 요청',exclude:'제외 요청',period:'요청 기간',cutoff:'요청 기준 시점',coverage:'자료 완전성',candle_unit:'차트 단위',statement_basis:'재무 기준',financial_period:'재무 기간',years:'요청 연수'} as Record<string,string>)[kind]??'확인할 조건';
}
export function conditionDisposition(id:string,original:string,effective:Outcome['effective_scope']){return effective?.waived_conditions.includes(id)?'명시 동의로 조정됨 · 원조건은 보존':original==='honored'?'반영됨':'현재 지원하지 않음 · 동의 전';
}

/** A stopped/replaced poll cannot invalidate a later manual observation. */
export class CoreObservationTimer {
 private epoch=0;
 private handle:unknown=null;
 constructor(
  private schedule:(run:()=>void,delay:number)=>unknown=(run,delay)=>globalThis.setTimeout(run,delay),
  private cancel:(handle:unknown)=>void=handle=>globalThis.clearTimeout(handle as ReturnType<typeof setTimeout>),
 ){}
 stop(){
  this.epoch++;
  if(this.handle!==null)this.cancel(this.handle);
  this.handle=null;
 }
 start(current:()=>boolean,run:()=>void,delay:number){
  this.stop();
  const epoch=this.epoch;
  this.handle=this.schedule(()=>{
   if(this.epoch!==epoch||!current())return;
   this.handle=null;
   run();
  },delay);
 }
}

export function clarifiedDraft(draft:Draft,slot:Answer['slot'],value:string):Draft{
 if(draft.revision>=4||draft.answers.length>=8)throw new CoreHttpError(422);
 return draftValue({...draft,answers:[...draft.answers,{answer_id:crypto.randomUUID(),slot,value}],revision:draft.revision+1,selected_ticker:null,candidate_ref:null});
}


export function preparationKey(user:string){return 'verith.supervisor.meaning.v1:'+canonicalUuid(user);}
export async function preparePendingValue(raw:unknown):Promise<PreparePending>{
 if(!object(raw)||Object.keys(raw).some(k=>!['version','body','digest','preparation_id','binding_digest'].includes(k))||raw.version!=='supervisor.meaning.pending.v1'||!object(raw.body)||Object.keys(raw.body).sort().join(',')!=='draft,parent_preparation_id,prepare_key'||!uuid(raw.body.prepare_key)||raw.body.parent_preparation_id!==null&&!uuid(raw.body.parent_preparation_id)||raw.preparation_id!==undefined&&!uuid(raw.preparation_id)||!hex(raw.digest))throw new CoreHttpError(422);
 const draft=draftValue(raw.body.draft);
 if((raw.body.parent_preparation_id===null)!=(draft.selected_ticker==null)||await hash(raw.body)!==raw.digest||new TextEncoder().encode(JSON.stringify(raw)).byteLength>32768)throw new CoreHttpError(422);
 if(raw.preparation_id!==undefined&&(!hex(raw.binding_digest)||await hash({body:raw.body,preparation_id:canonicalUuid(raw.preparation_id)})!==raw.binding_digest)||raw.preparation_id===undefined&&raw.binding_digest!==undefined)throw new CoreHttpError(422);
 return raw as PreparePending;
}
export async function newPreparation(draft:Draft,parent:string|null=null):Promise<PreparePending>{
 const body:PrepareBody={prepare_key:crypto.randomUUID(),draft:{...draftValue(draft),selected_ticker:draft.selected_ticker??null,candidate_ref:draft.candidate_ref??null},parent_preparation_id:parent};
 return preparePendingValue({version:'supervisor.meaning.pending.v1',body,digest:await hash(body)});
}
export async function readPreparation(store:Storage,user:string):Promise<PreparePending|null>{
 const raw=store.getItem(preparationKey(user));
 if(raw===null)return null;
 if(raw.length>32768)throw new CoreHttpError(422);
 return preparePendingValue(JSON.parse(raw));
}
export async function writePreparation(store:Storage,user:string,value:PreparePending,current:()=>boolean=()=>true){
 const checked=await preparePendingValue(value);
 if(!current())throw new CoreHttpError(409);
 store.setItem(preparationKey(user),JSON.stringify(checked));
}
export async function preparationValue(raw:unknown,draft?:Draft):Promise<Preparation>{
 if(!object(raw)||Object.keys(raw).sort().join(',')!=='consumed_binding_id,created_at,expires_at,meaning_status,plan,preparation_id,state'||!uuid(raw.preparation_id)||typeof raw.created_at!=='string'||!Number.isFinite(Date.parse(raw.created_at))||typeof raw.expires_at!=='string'||!Number.isFinite(Date.parse(raw.expires_at))||Date.parse(raw.expires_at)<=Date.parse(raw.created_at)||!['pending','ready','clarification','unsupported','failed','unknown','expired','deleted','consumed'].includes(String(raw.state))||!['pending','deterministic','supplemented','unavailable','rejected','incomplete','unsupported','counter_unavailable','failed','unknown','expired','deleted','consumed'].includes(String(raw.meaning_status)))throw new CoreHttpError(502);
 const complete=['ready','clarification','unsupported'].includes(String(raw.state));
 if(complete!==(raw.plan!==null)||raw.consumed_binding_id!==null&&(raw.state!=='consumed'||!uuid(raw.consumed_binding_id)))throw new CoreHttpError(502);
 if(complete){const plan=await planValue(raw.plan,draft);if(plan.policy_version!=='supervisor.flow-core.2')throw new CoreHttpError(502);}
 return raw as Preparation;
}
export async function preparationRequest(kind:'post'|'get'|'delete',payload:PrepareBody|string,user:string,signal:AbortSignal,current:()=>boolean):Promise<Preparation>{
 const guard=()=>{if(signal.aborted||!current())throw new CoreHttpError(409);};
 const postSession=async()=>{
  guard();
  const controller=new AbortController(),until=performance.now()+15000;
  let stop=()=>{};
  const cancelled=new Promise<never>((_,reject)=>{stop=()=>{controller.abort();reject(new CoreHttpError(503));};});
  signal.addEventListener('abort',stop,{once:true});
  const timer=setTimeout(stop,15000);
  try{
   if(signal.aborted){stop();return await cancelled;}
   const value=await Promise.race([fetchSession(controller.signal),cancelled]);
   guard();
   if(controller.signal.aborted||performance.now()>=until)throw new CoreHttpError(503);
   return value;
  }finally{clearTimeout(timer);signal.removeEventListener('abort',stop);}
 };
 guard();
 const session=await (kind==='post'?postSession():fetchSession(signal));
 guard();
 if(session.user_id!==canonicalUuid(user))throw new AnalysisAccountChanged();
 const path='/api/private/supervisor/core/preparations'+(kind==='post'?'':'/'+canonicalUuid(String(payload)));
 const response=await globalThis.fetch(path,{method:kind==='post'?'POST':kind==='get'?'GET':'DELETE',headers:kind==='get'?{}:{'Content-Type':'application/json','X-CSRF-Token':session.csrf_token},...(kind==='post'?{body:JSON.stringify(payload)}:{}),cache:'no-store',redirect:'error',signal});
 guard();
 const wire=await bounded(response,signal);
 guard();
 if(!object(wire)||wire.schema_version!==VERSION||!uuid(wire.request_id)||!uuid(wire.trace_id))throw new CoreHttpError(502);
 if(!response.ok){const code=object(wire.error)&&typeof wire.error.code==='string'?wire.error.code:'SERVICE_UNAVAILABLE';throw new CoreHttpError(response.status,['PREPARATION_EXPIRED','PREPARATION_DELETED','PREPARATION_CONSUMED','MEANING_LIMIT_EXCEEDED','IDEMPOTENCY_CONFLICT','PLAN_STALE'].includes(code)?code:'SERVICE_UNAVAILABLE');}
 if(wire.error!==null)throw new CoreHttpError(502);
 const value=await preparationValue(wire.data,kind==='post'?(payload as PrepareBody).draft:undefined);
 guard();
 if(kind!=='post'&&canonicalUuid(value.preparation_id)!==canonicalUuid(String(payload)))throw new CoreHttpError(502);
 const after=await (kind==='post'?postSession():fetchSession(signal));
 guard();
 if(after.user_id!==canonicalUuid(user))throw new AnalysisAccountChanged();
 return value;
}
export function meaningLabel(status:string){return ({deterministic:'원문 근거 확인 · 모델 호출 없음',supplemented:'근거에 연결된 의미 보완',unavailable:'의미 보완 사용 불가 · 확인 필요',counter_unavailable:'비용 계수 근거 미확정 · 실제 호출 차단',rejected:'의미 후보를 채택하지 않음',incomplete:'남은 의미를 확인해야 함',unsupported:'현재 지원 범위 밖',pending:'준비 응답 대기',unknown:'준비 상태 불명 · 자동 재생성 안 함',failed:'준비 결과를 채택하지 못함',expired:'준비 유효기간 종료',deleted:'준비 원문 삭제됨',consumed:'기존 확정 요청에 연결됨'} as Record<string,string>)[status]??'준비 상태 확인';}

/** Only a first prepared adoption has a preparation TTL. Binding replay always keeps its original key. */
export function canAdoptPreparation(value:Preparation|null,plan:Plan,now=Date.now()){
 return value!==null&&value.state==='ready'&&value.plan?.plan_hash===plan.plan_hash&&Number.isFinite(now)&&now<Date.parse(value.expires_at);
}

export async function bindPreparation(saved:PreparePending,id:string):Promise<PreparePending>{
 const preparation_id=canonicalUuid(id);
 return preparePendingValue({...saved,preparation_id,binding_digest:await hash({body:saved.body,preparation_id})});
}

export function canResetConversation(pending:Pending|null,known:string|null,outcome:Outcome|null){
 if(pending===null&&known===null)return true;
 return outcome!==null&&(outcome.plan_status==='deleted'||outcome.flow!==null&&['stored','failed'].includes(outcome.flow.state));
}
