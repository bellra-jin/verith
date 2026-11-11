import {fetchSession} from '@/features/flow/lib/analysis-request';
import {decodeTechnicalBoundary, type TechnicalReadExpected} from './strict-boundary-read';

export const ownedReadLimits={list:65536,detail:4259840,request:16384,result:2097152,session:15000,http:20000,action:55000} as const;
const api='/api/private/technical/owned-reports',uuid=/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/,sha=/^[0-9a-f]{64}$/;
type Obj=Record<string,unknown>;
export type OwnedItem={report_id:string;stock:{stock_code:string;stock_name:string;market:string|null};created_at:string;requested_as_of:string;execution_mode:'synthetic';cutoff_validation:'unverified'};
export type OwnedList={items:OwnedItem[];limit:number;offset:number;has_more:boolean};
export type OwnedDetail={report_id:string;created_at:string;response:unknown;expected:TechnicalReadExpected};
export type OwnedReadState={kind:'idle'|'pending'}|{kind:'error';code:string}|{kind:'list';value:OwnedList}|{kind:'detail';value:OwnedDetail};
export class OwnedReadError extends Error {constructor(public readonly code:string){super('저장된 차트 결과를 확인할 수 없습니다.');}}
function check(ok:unknown):asserts ok {if(!ok)throw new OwnedReadError('RESULT_CONTRACT_INVALID');}
function object(value:unknown,keys:string[]):Obj {
  check(value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype);
  const o=value as Obj,d=Object.getOwnPropertyDescriptors(o);
  check(Object.getOwnPropertySymbols(o).length===0&&Object.keys(d).length===keys.length&&keys.every(k=>Object.hasOwn(d,k)&&d[k].enumerable&&'value' in d[k]));return o;
}
function text(v:unknown):asserts v is string {check(typeof v==='string');for(const c of v){const n=c.codePointAt(0)!;check(n<0xd800||n>0xdfff);}}
function id(v:unknown):asserts v is string {text(v);check(uuid.test(v));}
function stamp(v:unknown):asserts v is string {
  text(v);check(/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)$/.test(v)&&!v.startsWith('0000')
    &&Number(v.slice(11,13))<24&&Number(v.slice(14,16))<60&&Number(v.slice(17,19))<60&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v.slice(0,10));
}
export function ownedReportId(value:unknown):string {id(value);return value;}
export function ownedReadQuery(search=''):string {
  const pairs=[...new URLSearchParams(search)],v=Object.fromEntries(pairs);
  if(pairs.length!==Object.keys(v).length||Object.keys(v).some(k=>!['stock_code','limit','offset'].includes(k))||v.stock_code!==undefined&&!/^[0-9]{6}$/.test(v.stock_code)
    ||['limit','offset'].some(k=>v[k]!==undefined&&!/^[0-9]{1,5}$/.test(v[k]))||Number(v.limit??10)<1||Number(v.limit??10)>20||Number(v.offset??0)>10000)throw new OwnedReadError('INPUT_INVALID');
  const q=new URLSearchParams();for(const key of ['stock_code','limit','offset'])if(v[key]!==undefined)q.set(key,v[key]);return q.size?'?'+q.toString():'';
}
export function matchesOwnedReadUrl(reportId:string|null,pathname:string,search:string):boolean {
  try {if(reportId===null){ownedReadQuery(search);return pathname==='/reports/technical';}return pathname==='/reports/technical/'+ownedReportId(reportId)&&search==='';}catch{return false;}
}
function list(value:unknown):OwnedList {
  const v=object(value,['items','limit','offset','has_more']);
  check(Number.isInteger(v.limit)&&Number(v.limit)>=1&&Number(v.limit)<=20&&Number.isInteger(v.offset)&&Number(v.offset)>=0&&Number(v.offset)<=10000
    &&typeof v.has_more==='boolean'&&Array.isArray(v.items)&&Object.getPrototypeOf(v.items)===Array.prototype&&v.items.length<=Number(v.limit));
  const array=v.items as unknown[],d=Object.getOwnPropertyDescriptors(array);
  check(Object.getOwnPropertySymbols(array).length===0&&Object.keys(d).length===array.length+1&&Object.entries(d).every(([k,p])=>k==='length'||p.enumerable&&'value' in p&&/^(0|[1-9][0-9]*)$/.test(k)&&Number(k)<array.length));
  const items=array.map(entry=>{
    const item=object(entry,['report_id','stock','created_at','requested_as_of','execution_mode','cutoff_validation']);id(item.report_id);stamp(item.created_at);stamp(item.requested_as_of);
    const stock=object(item.stock,['stock_code','stock_name','market']);text(stock.stock_code);text(stock.stock_name);
    check(/^[0-9]{6}$/.test(stock.stock_code)&&stock.stock_name.trim().length>0&&[...stock.stock_name].length<=256&&!/[\u0000-\u001f\u007f-\u009f]/.test(stock.stock_name)
      &&['KOSPI','KOSDAQ','KONEX',null].includes(stock.market as string|null)&&item.execution_mode==='synthetic'&&item.cutoff_validation==='unverified');return structuredClone(item) as OwnedItem;
  });check(new Set(items.map(x=>x.report_id)).size===items.length);
  return {items,limit:Number(v.limit),offset:Number(v.offset),has_more:v.has_more as boolean};
}
async function hash(value:string):Promise<string> {return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))].map(x=>x.toString(16).padStart(2,'0')).join('');}
export async function decodeOwnedWire(value:unknown,reportId:string|null,status=200):Promise<OwnedList|OwnedDetail> {
  const wire=object(value,['schema_version','request_id','data','error']);id(wire.request_id);check(wire.schema_version==='technical.owned-read.v1'&&(wire.data===null)!==(wire.error===null));
  if(status!==200){
    check(wire.data===null);const e=object(wire.error,['code','message']);text(e.code);
    const statuses:Record<string,number>={AUTH_REQUIRED:401,AUTH_REQUEST_INVALID:403,FEATURE_UNAVAILABLE:403,RESOURCE_NOT_FOUND:404,INPUT_INVALID:422,RESULT_CONTRACT_INVALID:502,SERVICE_UNAVAILABLE:503,DEADLINE_EXCEEDED:504};
    check(Object.hasOwn(statuses,e.code)&&statuses[e.code]===status&&e.message==='Technical result unavailable');throw new OwnedReadError(e.code);
  }
  check(wire.error===null);if(reportId===null)return list(wire.data);
  const data=object(wire.data,['report_id','created_at','request_json','request_sha256','result_json','result_sha256']);id(data.report_id);stamp(data.created_at);check(data.report_id===ownedReportId(reportId));
  for(const key of ['request','result'] as const){text(data[key+'_json']);text(data[key+'_sha256']);check(sha.test(data[key+'_sha256'] as string));check(new TextEncoder().encode(data[key+'_json'] as string).length<=ownedReadLimits[key]);}
  const [a,b]=await Promise.all([hash(data.request_json as string),hash(data.result_json as string)]);check(a===data.request_sha256&&b===data.result_sha256);
  let request:unknown,response:unknown;try{request=JSON.parse(data.request_json as string);response=JSON.parse(data.result_json as string);}catch{throw new OwnedReadError('RESULT_CONTRACT_INVALID');}
  const expected={request,request_sha256:a};
  try{const decoded=decodeTechnicalBoundary(response,expected);check(decoded.kind==='success'&&decoded.preview.report_id===reportId);}
  catch{throw new OwnedReadError('RESULT_CONTRACT_INVALID');}
  return {report_id:reportId,created_at:data.created_at,response,expected};
}
function interrupted(signal:AbortSignal){if(signal.aborted)throw new OwnedReadError('DEADLINE_EXCEEDED');}
function abortable<T>(promise:Promise<T>,signal:AbortSignal):Promise<T>{return new Promise((resolve,reject)=>{
  const abort=()=>reject(new OwnedReadError('DEADLINE_EXCEEDED'));if(signal.aborted){abort();return;}signal.addEventListener('abort',abort,{once:true});
  promise.then(resolve,reject).finally(()=>signal.removeEventListener('abort',abort));
});}
async function bounded<T>(signal:AbortSignal,ms:number,work:(signal:AbortSignal)=>Promise<T>):Promise<T>{
  const child=new AbortController(),abort=()=>child.abort();if(signal.aborted)child.abort();else signal.addEventListener('abort',abort,{once:true});const timer=setTimeout(abort,ms);
  try{return await abortable(work(child.signal),child.signal);}finally{clearTimeout(timer);signal.removeEventListener('abort',abort);}
}
export async function getOwnedRead(reportId:string|null,search:string,signal:AbortSignal):Promise<OwnedList|OwnedDetail>{
  if(reportId!==null&&search!=='')throw new OwnedReadError('INPUT_INVALID');
  const query=reportId===null?ownedReadQuery(search):'';if(reportId!==null)ownedReportId(reportId);
  return bounded(signal,ownedReadLimits.http,async local=>{
    const response=await fetch(api+(reportId===null?query:'/'+reportId),{headers:{Accept:'application/json'},cache:'no-store',redirect:'manual',credentials:'same-origin',signal:local});
    const reader=response.body?.getReader(),chunks:Uint8Array[]=[];let size=0;
    try{if(reader)while(true){const chunk=await abortable(reader.read(),local);if(chunk.done)break;size+=chunk.value.byteLength;
      if(size>(reportId===null?ownedReadLimits.list:ownedReadLimits.detail)){void reader.cancel().catch(()=>{});throw new OwnedReadError('RESULT_CONTRACT_INVALID');}chunks.push(chunk.value);}}
    finally{if(local.aborted)void reader?.cancel().catch(()=>{});try{reader?.releaseLock();}catch{/* cancelled read */}}
    interrupted(local);const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
    let packet:unknown;try{packet=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}catch{throw new OwnedReadError('RESULT_CONTRACT_INVALID');}
    const result=await abortable(decodeOwnedWire(packet,reportId,response.status),local);interrupted(local);
    if(reportId===null){const q=new URLSearchParams(query),value=result as OwnedList;check(value.limit===Number(q.get('limit')??10)&&value.offset===Number(q.get('offset')??0));}return result;
  });
}

/** Single read action only: no polling, storage, POST or execution authority. */
export class OwnedReadAction {
  private generation=0;
  private current:{token:number;controller:AbortController;timer:ReturnType<typeof setTimeout>}|null=null;
  constructor(private publish:(state:OwnedReadState)=>void,private context:(id:string|null,search:string)=>boolean){}
  cancel(publish=true):void{const old=this.current;this.current=null;this.generation++;if(old){clearTimeout(old.timer);old.controller.abort();}if(publish)this.publish({kind:'idle'});}
  async run(reportId:string|null,search=''):Promise<boolean>{
    if(this.current!==null||!this.context(reportId,search))return false;
    const controller=new AbortController(),token=++this.generation,ticket={token,controller,timer:setTimeout(()=>controller.abort(),ownedReadLimits.action)};
    this.current=ticket;this.publish({kind:'pending'});const owns=()=>this.current===ticket&&this.generation===token;
    const active=()=>owns()&&!controller.signal.aborted&&this.context(reportId,search);
    try{
      const before=await bounded(controller.signal,ownedReadLimits.session,fetchSession);if(!active())return false;
      const value=await getOwnedRead(reportId,search,controller.signal);if(!active())return false;
      const after=await bounded(controller.signal,ownedReadLimits.session,fetchSession);if(!active())return false;
      if(before.user_id!==after.user_id||before.csrf_token!==after.csrf_token)throw new OwnedReadError('ACCOUNT_CHANGED');
      this.publish(reportId===null?{kind:'list',value:value as OwnedList}:{kind:'detail',value:value as OwnedDetail});return true;
    }catch(error){
      if(owns()&&this.context(reportId,search)){
        const status=typeof error==='object'&&error!==null&&'status' in error?(error as {status:number}).status:null;
        this.publish({kind:'error',code:status===401?'AUTH_REQUIRED':error instanceof OwnedReadError?error.code:controller.signal.aborted?'DEADLINE_EXCEEDED':'SERVICE_UNAVAILABLE'});
      }return false;
    }finally{clearTimeout(ticket.timer);if(owns()){this.current=null;if(!this.context(reportId,search))this.publish({kind:'idle'});}}
  }
}
