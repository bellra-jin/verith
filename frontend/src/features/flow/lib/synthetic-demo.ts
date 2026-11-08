// Pure wire/intent rules. Browser storage access is limited to the supplied account namespace.
export type Stage='admitted'|'prepared'|'running'|'succeeded'|'failed'|'timed_out';
export type Pending={idempotency_key:string;as_of:string;run_id?:string};
export type Session={user_id:string;csrf_token:string};
export type Artifact={requested_as_of:string;row_count:number;start_date:string;end_date:string;quantity_unit:'share';trading_value_unit:'KRW';totals:{individual:number;foreign:number;institution:number;trading_value:number};notice:string};
export type DemoView={version:1;synthetic:true;mode:'synthetic_demo';run_id:string;request_id:string;attempt_id:string;input_snapshot_id:string|null;execution_id:string|null;stage:Stage;deadline_at:string|null;finished_at:string|null;result_stored:boolean;result:Artifact|null;result_sha256:string|null;failure_code:string|null};
export const DEMO_BFF='/api/private/flow/synthetic-demo/runs';
export function record(v:unknown):v is Record<string,unknown>{return v!==null&&typeof v==='object'&&!Array.isArray(v);}
export function uuid(v:unknown):v is string{return typeof v==='string'&&/^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}$/i.test(v);}
export function canonicalUuid(v:string):string{if(!uuid(v))throw Error('Invalid UUID');return v.toLowerCase();}
function sameUuid(a:unknown,b:unknown):boolean{return uuid(a)&&uuid(b)&&canonicalUuid(a)===canonicalUuid(b);}
function stamp(v:unknown):v is string{return typeof v==='string'&&/^\d{4}-\d\d-\d\dT/.test(v)&&Number.isFinite(Date.parse(v))&&/(?:Z|[+-]\d\d:\d\d)$/.test(v);}
function hash(v:unknown):v is string{return typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);}
function stage(v:unknown):v is Stage{return v==='admitted'||v==='prepared'||v==='running'||v==='succeeded'||v==='failed'||v==='timed_out';}
export function sessionValue(v:unknown):Session|null {return record(v)&&uuid(v.user_id)&&typeof v.csrf_token==='string'&&v.csrf_token.length>0?{user_id:canonicalUuid(v.user_id),csrf_token:v.csrf_token}:null;}
export function demoHref(id:string):string{if(!uuid(id))throw Error('Invalid run');return '/flow/demo?run_id='+encodeURIComponent(canonicalUuid(id));}
function amount(v:unknown):v is number{return typeof v==='number'&&Number.isSafeInteger(v);}
function artifact(v:unknown,parent:Record<string,unknown>,user?:string):Artifact|null {
 if(!record(v)||v.contract_version!==1||v.synthetic!==true||v.mode!=='synthetic_only'||v.engine_id!=='flow.fake.summary.v1'||!sameUuid(v.execution_id,parent.execution_id)||!sameUuid(v.input_snapshot_id,parent.input_snapshot_id)||!hash(v.input_sha256)||!record(v.source_reference)||!sameUuid(v.source_reference.run_id,parent.run_id)||!sameUuid(v.source_reference.request_id,parent.request_id)||!sameUuid(v.source_reference.attempt_id,parent.attempt_id)||!uuid(v.source_reference.owner_user_id)||user!==undefined&&!sameUuid(v.source_reference.owner_user_id,user)||v.ticker!=='005930'||!stamp(v.requested_as_of)||v.row_count!==20||v.calendar!=='consecutive_calendar_dates_not_trading_days'||v.quantity_unit!=='share'||v.trading_value_unit!=='KRW'||typeof v.start_date!=='string'||typeof v.end_date!=='string'||!/^\d{4}-\d\d-\d\d$/.test(v.start_date)||!/^\d{4}-\d\d-\d\d$/.test(v.end_date)||!record(v.totals)||!amount(v.totals.individual)||!amount(v.totals.foreign)||!amount(v.totals.institution)||!amount(v.totals.trading_value)||typeof v.notice!=='string')return null;
 return {requested_as_of:v.requested_as_of,row_count:v.row_count,start_date:v.start_date,end_date:v.end_date,quantity_unit:v.quantity_unit,trading_value_unit:v.trading_value_unit,totals:{individual:v.totals.individual,foreign:v.totals.foreign,institution:v.totals.institution,trading_value:v.totals.trading_value},notice:v.notice};
}
export function demoView(v:unknown,user?:string):DemoView|null {
 if(!record(v)||Object.keys(v).sort().join(',')!==['version','synthetic','mode','run_id','request_id','attempt_id','input_snapshot_id','execution_id','stage','deadline_at','finished_at','result_stored','result','result_sha256','failure_code'].sort().join(',')||v.version!==1||v.synthetic!==true||v.mode!=='synthetic_demo'||!uuid(v.run_id)||!uuid(v.request_id)||!uuid(v.attempt_id)||!stage(v.stage)||typeof v.result_stored!=='boolean')return null;
 if(v.input_snapshot_id!==null&&!uuid(v.input_snapshot_id)||v.execution_id!==null&&!uuid(v.execution_id)||v.deadline_at!==null&&!stamp(v.deadline_at)||v.finished_at!==null&&!stamp(v.finished_at)||v.result_sha256!==null&&!hash(v.result_sha256)||v.failure_code!==null&&typeof v.failure_code!=='string')return null;
 const execution=!['admitted','prepared'].includes(v.stage),terminal=['succeeded','failed','timed_out'].includes(v.stage),success=v.stage==='succeeded';
 if((v.input_snapshot_id!==null)!==(v.stage!=='admitted')||(v.execution_id!==null)!==execution||(v.deadline_at!==null)!==execution||(v.finished_at!==null)!==terminal||v.result_stored!==success||(v.result!==null)!==success||(v.result_sha256!==null)!==success||(v.failure_code!==null)!==['failed','timed_out'].includes(v.stage))return null;
 if(v.stage==='failed'&&(v.failure_code===null||!['fake_failed','result_invalid'].includes(v.failure_code))||v.stage==='timed_out'&&(v.failure_code===null||!['coroutine_timeout','deadline_expired'].includes(v.failure_code)))return null;
 const result=success?artifact(v.result,v,user):null;
 if(success&&(!result||typeof v.deadline_at!=='string'||typeof v.finished_at!=='string'||Date.parse(v.finished_at)>=Date.parse(v.deadline_at)))return null;
 return {version:1,synthetic:true,mode:'synthetic_demo',run_id:canonicalUuid(v.run_id),request_id:canonicalUuid(v.request_id),attempt_id:canonicalUuid(v.attempt_id),input_snapshot_id:v.input_snapshot_id===null?null:canonicalUuid(v.input_snapshot_id),execution_id:v.execution_id===null?null:canonicalUuid(v.execution_id),stage:v.stage,deadline_at:v.deadline_at,finished_at:v.finished_at,result_stored:v.result_stored,result,result_sha256:v.result_sha256,failure_code:v.failure_code};
}
export class DemoHttpError extends Error{constructor(public status:number){super('합성 데모 요청을 확인할 수 없습니다.');}}
export async function wireView(response:Response,user:string):Promise<DemoView>{
 const value:unknown=await response.json();
 if(!record(value)||!uuid(value.request_id)||Object.keys(value).sort().join(',')!=='data,error,request_id')throw new DemoHttpError(502);
 if(!response.ok){if(value.data!==null||!record(value.error)||typeof value.error.code!=='string')throw new DemoHttpError(502);throw new DemoHttpError(response.status);}
 if(value.error!==null)throw new DemoHttpError(502);
 const parsed=demoView(value.data,user);if(!parsed)throw new DemoHttpError(502);return parsed;
}
export async function fetchSession(signal:AbortSignal):Promise<Session>{const response=await fetch('/api/auth/session',{cache:'no-store',signal});if(!response.ok)throw new DemoHttpError(response.status);const value=sessionValue(await response.json());if(!value)throw new DemoHttpError(502);return value;}
export async function fetchDemo(id:string,user:string,signal:AbortSignal):Promise<DemoView>{if(!uuid(id))throw new DemoHttpError(422);const value=await wireView(await fetch(DEMO_BFF+'/'+canonicalUuid(id),{cache:'no-store',signal}),user);if(value.run_id.toLowerCase()!==id.toLowerCase())throw new DemoHttpError(502);return value;}
export async function postDemo(intent:Pending,session:Session,signal:AbortSignal):Promise<DemoView>{const value=await wireView(await fetch(DEMO_BFF,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf_token},body:JSON.stringify({idempotency_key:intent.idempotency_key,as_of:intent.as_of,allow_fake:true}),cache:'no-store',signal}),session.user_id);if(intent.run_id!==undefined&&value.run_id!==canonicalUuid(intent.run_id)||value.result&&Date.parse(value.result.requested_as_of)!==Date.parse(intent.as_of))throw new DemoHttpError(502);return value;}
export function pendingKey(user:string):string{if(!uuid(user))throw Error('Invalid account');return 'verith.flow.synthetic-demo.v1:'+canonicalUuid(user);}
export function pendingValue(v:unknown):Pending {
 if(!record(v)||Object.keys(v).some(k=>!['idempotency_key','as_of','run_id'].includes(k))||!uuid(v.idempotency_key)||!stamp(v.as_of)||new Date(v.as_of).toISOString()!==v.as_of||v.run_id!==undefined&&!uuid(v.run_id))throw Error('합성 데모 요청 기록이 손상됐습니다.');
 return {idempotency_key:v.idempotency_key,as_of:v.as_of,...(v.run_id===undefined?{}:{run_id:canonicalUuid(v.run_id)})};
}
export function readPending(store:Storage,user:string):Pending|null{const raw=store.getItem(pendingKey(user));if(raw===null)return null;if(raw.length>1024)throw Error('Invalid pending record');return pendingValue(JSON.parse(raw));}
export function writePending(store:Storage,user:string,value:Pending):void{store.setItem(pendingKey(user),JSON.stringify(pendingValue(value)));}
export function freshPending():Pending{return {idempotency_key:crypto.randomUUID(),as_of:new Date().toISOString()};}
export type Ticket={revision:number;user:string;key:string};
export class DemoIntent {
 private revision=0;private user:string|null=null;private busy=false;
 reset(user:string|null):void{this.revision++;this.user=user===null?null:canonicalUuid(user);this.busy=false;}
 begin(user:string,key:string):Ticket|null{const account=canonicalUuid(user);if(this.busy||this.user!==account)return null;this.busy=true;return {revision:++this.revision,user:account,key};}
 accepts(ticket:Ticket,key:string):boolean{return this.revision===ticket.revision&&this.user===ticket.user&&ticket.key===key;}
 finish(ticket:Ticket):void{if(this.revision===ticket.revision&&this.user===ticket.user)this.busy=false;}
}

export class DemoLifecycle {
 private generation=0;private polls=0;
 invalidate():number{this.polls=0;return ++this.generation;}
 current():number{return this.generation;}
 accepts(generation:number):boolean{return generation===this.generation;}
 takePoll(generation:number):boolean{if(!this.accepts(generation)||this.polls>=15)return false;this.polls++;return true;}
}
