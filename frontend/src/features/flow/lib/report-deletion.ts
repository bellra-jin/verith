// Same-origin report observation/deletion only; UI identity is not authorization.
const UUID=/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
const object=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
function identity(v:string):string{if(!UUID.test(v))throw new ReportActionError('stale');return v.toLowerCase();}
export type ReportTarget=Readonly<{reportId:string;userId:string;href:string;returnTo:string}>;
export type ReportObservation=Readonly<{identity:string;href:string}>;
export function sameReportObservation(value:ReportObservation|null,identity:string,href:string):value is ReportObservation{
 return value!==null&&value.identity===identity&&value.href===href;
}
export type ReportFailure='auth'|'gone'|'unavailable'|'stale'|'timeout'|'busy';
export class ReportActionError extends Error{constructor(public readonly code:ReportFailure){super('결과 요청을 확인할 수 없습니다.');}}
export const reportError=(error:unknown):string=>error instanceof ReportActionError&&error.code==='gone'?'이미 없거나 접근할 수 없는 결과입니다. 이번 삭제의 성공을 확인한 것은 아닙니다.':error instanceof ReportActionError&&error.code==='auth'?'같은 계정의 로그인을 확인한 뒤 다시 조회해 주세요.':error instanceof ReportActionError&&error.code==='timeout'?'요청 확인 시간이 지났습니다. 삭제가 반영됐을 수 있으므로 상태를 다시 조회해 주세요.':'요청을 확인할 수 없습니다. 상태를 다시 조회한 뒤 새로 확인해 주세요.';
export function safeReturnTo(value:string):string{
 if(!value.startsWith('/')||value.startsWith('//')||value.includes('\\'))throw new ReportActionError('stale');
 const url=new URL(value,'https://owned.invalid');
 if(url.origin!=='https://owned.invalid'||url.pathname!=='/'||url.hash)throw new ReportActionError('stale');
 for(const key of url.searchParams.keys())if(!['limit','offset'].includes(key)||url.searchParams.getAll(key).length!==1)throw new ReportActionError('stale');
 if(!url.search)return '/';
 const limit=url.searchParams.get('limit')??'20',offset=url.searchParams.get('offset')??'0';
 if(!/^[1-9][0-9]*$/.test(limit)||!/^(0|[1-9][0-9]*)$/.test(offset)||!Number.isSafeInteger(Number(offset))||Number(offset)>Number.MAX_SAFE_INTEGER-100||Number(limit)>100)throw new ReportActionError('stale');
 return `/?limit=${limit}&offset=${offset}`;
}
export function reportTarget(reportId:string,userId:string,href:string,returnTo:string):ReportTarget{
 const report=identity(reportId),owner=identity(userId),url=new URL(href);
 if(!['http:','https:'].includes(url.protocol)||url.username||url.password||url.pathname.toLowerCase()!=='/reports/flow/'+report)throw new ReportActionError('stale');
 return Object.freeze({reportId:report,userId:owner,href:url.href,returnTo:safeReturnTo(returnTo)});
}
// Stored v1 UUID text is preserved by Backend UUID(value); URL IDs stay strict.
export function sourceReportId(value:unknown):string|null{
 if(typeof value!=='string')return null;
 let raw=value.toLowerCase();if(raw.startsWith('urn:uuid:'))raw=raw.slice(9);
 if(raw.startsWith('{')&&raw.endsWith('}'))raw=raw.slice(1,-1);
 raw=raw.replaceAll('-','');if(!/^[0-9a-f]{32}$/.test(raw))return null;
 return `${raw.slice(0,8)}-${raw.slice(8,12)}-${raw.slice(12,16)}-${raw.slice(16,20)}-${raw.slice(20)}`;
}
type Timers={set:(fn:()=>void,ms:number)=>unknown;clear:(id:unknown)=>void};
const timers:Timers={set:(fn,ms)=>setTimeout(fn,ms),clear:id=>clearTimeout(id as ReturnType<typeof setTimeout>)};
export class ReportIntent{
 private generation=0;private controller:AbortController|null=null;
 get pending():boolean{return this.controller!==null;}
 constructor(private readonly fetcher:typeof fetch=fetch,private readonly clock:Timers=timers){this.fetcher=fetcher.bind(globalThis);}
 invalidate():void{this.generation++;this.controller?.abort();this.controller=null;}
 private async run<T>(current:()=>boolean,work:(signal:AbortSignal,guard:()=>void)=>Promise<T>):Promise<T>{
  if(this.pending)throw new ReportActionError('busy');
  const generation=this.generation,controller=new AbortController();this.controller=controller;
  const guard=()=>{if(generation!==this.generation||controller.signal.aborted||!current())throw new ReportActionError('stale');};
  let timer:unknown;
  const timeout=new Promise<never>((_,reject)=>{timer=this.clock.set(()=>{if(this.controller===controller){this.generation++;controller.abort();}reject(new ReportActionError('timeout'));},15000);});
  try{guard();const result=await Promise.race([work(controller.signal,guard),timeout]);guard();return result;}
  catch(error){if(error instanceof ReportActionError)throw error;throw new ReportActionError('unavailable');}
  finally{this.clock.clear(timer);controller.abort();if(this.controller===controller)this.controller=null;}
 }
 private async session(target:ReportTarget,signal:AbortSignal,guard:()=>void):Promise<string>{
  guard();const response=await this.fetcher('/api/auth/session',{cache:'no-store',signal});guard();
  if(response.status===401||response.status===403)throw new ReportActionError('auth');
  if(response.status!==200)throw new ReportActionError('unavailable');
  const value:unknown=await response.json();guard();
  if(!object(value)||typeof value.user_id!=='string'||identity(value.user_id)!==target.userId||typeof value.csrf_token!=='string'||!value.csrf_token)throw new ReportActionError('auth');
  return value.csrf_token;
 }
 verify(target:ReportTarget,current:()=>boolean):Promise<void>{return this.run(current,async(signal,guard)=>{
  await this.session(target,signal,guard);guard();
  const response=await this.fetcher('/api/private/flow/reports/'+target.reportId,{cache:'no-store',signal});guard();
  if(response.status===404)throw new ReportActionError('gone');if(response.status===401||response.status===403)throw new ReportActionError('auth');
  if(response.status!==200)throw new ReportActionError('unavailable');
  const value:unknown=await response.json();guard();
  if(!object(value)||!object(value.report)||typeof value.report_id!=='string'||identity(value.report_id)!==target.reportId||sourceReportId(value.report.report_id)!==target.reportId)throw new ReportActionError('unavailable');
 });}
 remove(target:ReportTarget,current:()=>boolean):Promise<string>{return this.run(current,async(signal,guard)=>{
  const csrf=await this.session(target,signal,guard);guard();
  const response=await this.fetcher('/api/private/flow/reports/'+target.reportId,{method:'DELETE',headers:{'X-CSRF-Token':csrf},cache:'no-store',signal});guard();
  if(response.status===404)throw new ReportActionError('gone');if(response.status===401||response.status===403)throw new ReportActionError('auth');
  if(response.status!==204)throw new ReportActionError('unavailable');return target.returnTo;
 });}
}
