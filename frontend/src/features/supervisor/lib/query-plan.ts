// Preparation only. Authentication and execution authority stay on Backend.
import {canonicalUuid,fetchSession,AnalysisAccountChanged,freshPending,postAnalysis,type PendingAnalysis} from '@/features/flow/lib/analysis-request';
export const VERSION='supervisor.flow-plan.v1',POLICY='supervisor.flow-only.1';
export type Stock={stock_code:string;stock_name:string;market:'KOSPI'|'KOSDAQ'|'KONEX'|null};
export type Candidate=Stock&{match_type:'stock_code'|'stock_name'|'alias'|'ambiguous_group'};
export type Resolution={status:'resolved'|'ambiguous'|'not_found';reason:string;stock:Stock|null;candidates:Candidate[]};
export type Plan={version:typeof VERSION;policy_version:typeof POLICY;query_sha256:string;requested_views:string[];status:'ready_for_confirmation'|'needs_stock_selection'|'selection_stale'|'not_found'|'needs_clarification'|'unsupported';reason:string;resolution:Resolution|null;candidate_ref:string|null};
const object=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
const keys=(v:Record<string,unknown>,expected:string[])=>Object.keys(v).length===expected.length&&expected.every(k=>Object.hasOwn(v,k));
const ref=(v:unknown):v is string=>typeof v==='string'&&/^[0-9a-f]{64}$/.test(v);
const code=(v:unknown):v is string=>typeof v==='string'&&/^[0-9]{6}$/.test(v);
function stock(v:unknown,candidate=false):v is Stock|Candidate{
 return object(v)&&keys(v,['stock_code','stock_name','market',...(candidate?['match_type']:[])])&&code(v.stock_code)&&typeof v.stock_name==='string'&&v.stock_name.length<=256&&v.stock_name.trim().length>0&&!/[\u0000-\u001f\u007f-\u009f]/.test(v.stock_name)&&[null,'KOSPI','KOSDAQ','KONEX'].includes(v.market as null)&&(!candidate||['stock_code','stock_name','alias','ambiguous_group'].includes(v.match_type as string));
}
export class PlanError extends Error{constructor(public readonly status:number){super('분석 준비를 확인할 수 없습니다. 다시 준비해 주세요.');}}
export function validatePlan(value:unknown,hash:string):Plan{
 if(!object(value)||!keys(value,['version','policy_version','query_sha256','requested_views','status','reason','resolution','candidate_ref'])||value.version!==VERSION||value.policy_version!==POLICY||value.query_sha256!==hash||!Array.isArray(value.requested_views)||value.requested_views.some(v=>typeof v!=='string'||!['flow','technical','fundamental','macro','industry','news','overview'].includes(v))||new Set(value.requested_views).size!==value.requested_views.length)throw new PlanError(502);
 const reasons:Record<string,string[]>= {ready_for_confirmation:['stock_resolved'],needs_stock_selection:['stock_ambiguous'],selection_stale:['selection_changed'],not_found:['stock_not_found'],needs_clarification:['clarify_intent','clarify_stock_scope'],unsupported:['unsupported_views']};
 if(typeof value.status!=='string'||!Object.hasOwn(reasons,value.status)||!reasons[value.status].includes(value.reason as string))throw new PlanError(502);
 if(['unsupported','needs_clarification'].includes(value.status)){
  if(value.resolution!==null||value.candidate_ref!==null)throw new PlanError(502);
 }else{
  const r=value.resolution;
  if(value.requested_views.join(',')!=='flow'||!ref(value.candidate_ref)||!object(r)||!keys(r,['status','reason','stock','candidates'])||!Array.isArray(r.candidates)||r.candidates.length>10||!r.candidates.every(c=>stock(c,true))||new Set(r.candidates.map(c=>c.stock_code)).size!==r.candidates.length)throw new PlanError(502);
  const expectedStatus:Record<string,string>={ready_for_confirmation:'resolved',needs_stock_selection:'ambiguous',selection_stale:'ambiguous',not_found:'not_found'};const wanted=expectedStatus[value.status];
  if(r.status!==wanted)throw new PlanError(502);
  if(r.status==='resolved'&&(!stock(r.stock)||r.candidates.length!==0||r.reason!=='exact_match'))throw new PlanError(502);
  if(r.status==='not_found'&&(r.stock!==null||r.candidates.length!==0||r.reason!=='no_match'))throw new PlanError(502);
  if(r.status==='ambiguous'&&(r.stock!==null||!['multiple_stocks','conflicting_identifiers','ambiguous_alias','unknown_identifier'].includes(r.reason as string)))throw new PlanError(502);
 }
 return value as Plan;
}
export async function queryHash(query:string){const bytes=new TextEncoder().encode(query);const hash=await globalThis.crypto.subtle.digest('SHA-256',bytes);return Array.from(new Uint8Array(hash),x=>x.toString(16).padStart(2,'0')).join('');}
async function read(response:Response,signal:AbortSignal):Promise<unknown>{
 const reader=response.body?.getReader();if(!reader)throw new PlanError(502);const chunks:Uint8Array[]=[];let size=0;
 const abort=()=>{void reader.cancel().catch(()=>{});};signal.addEventListener('abort',abort,{once:true});
 try{while(true){if(signal.aborted)throw new PlanError(504);const part=await reader.read();if(signal.aborted)throw new PlanError(504);if(part.done)break;size+=part.value.byteLength;if(size>16384){await reader.cancel();throw new PlanError(502);}chunks.push(part.value);}
 const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
 }catch(error){if(error instanceof PlanError)throw error;throw new PlanError(signal.aborted?504:502);}
 finally{signal.removeEventListener('abort',abort);reader.releaseLock();}
}
export async function prepareQuery(query:string,userId:string,signal:AbortSignal,current:()=>boolean,selection?:{selected_ticker:string;candidate_ref:string}):Promise<Plan>{
 if(!query.trim()||query.length>300||query.includes('\0')||selection&&(!code(selection.selected_ticker)||!ref(selection.candidate_ref)))throw new PlanError(422);
 const owner=canonicalUuid(userId);const guard=()=>{if(signal.aborted||!current())throw new PlanError(409);};guard();
 const before=await fetchSession(signal);guard();if(before.user_id!==owner)throw new AnalysisAccountChanged();
 const hash=await queryHash(query);guard();
 const response=await globalThis.fetch('/api/private/flow/plans',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':before.csrf_token},body:JSON.stringify({query,...selection}),signal,cache:'no-store',redirect:'error'});
 guard();const value=await read(response,signal);guard();
 if(!response.ok)throw new PlanError(response.status);
 if(!object(value)||!keys(value,['request_id','data','error'])||typeof value.request_id!=='string'||value.error!==null)throw new PlanError(502);
 canonicalUuid(value.request_id);const result=validatePlan(value.data,hash);
 const after=await fetchSession(signal);guard();if(after.user_id!==owner)throw new AnalysisAccountChanged();
 return result;
}


// Synchronous preparation identity. It is a UI freshness fence, never authority.
export type PreparedTicket=Readonly<{owner:string;href:string;ticker:string;query:string;revision:number}>;
export class PreparationBinding{
 private value:{owner:string;href:string;ticker:string;query:string}|null=null;
 private revision=0;private consent=false;
 bind(value:{owner:string;href:string;ticker:string;query:string}){this.revision++;this.value={...value};this.consent=false;}
 clear(){this.revision++;this.value=null;this.consent=false;}
 setConsent(value:boolean){this.revision++;this.consent=value;}
 capture(owner:string,href:string):PreparedTicket|null{
  if(!this.value||!this.consent||this.value.owner!==owner||this.value.href!==href)return null;
  return Object.freeze({...this.value,revision:this.revision});
 }
 accepts(ticket:PreparedTicket,owner:string,href:string){
  return Boolean(this.value&&this.consent&&ticket.revision===this.revision&&ticket.owner===owner&&ticket.href===href&&this.value.owner===ticket.owner&&this.value.href===ticket.href&&this.value.ticker===ticket.ticker&&this.value.query===ticket.query);
 }
}
export async function verifyPreparedSession(binding:PreparationBinding,ticket:PreparedTicket,signal:AbortSignal,href:()=>string,current:()=>boolean){
 const guard=()=>{if(signal.aborted||!current()||!binding.accepts(ticket,ticket.owner,href()))throw new PlanError(409);};
 guard();const session=await fetchSession(signal);guard();if(session.user_id!==ticket.owner)throw new AnalysisAccountChanged();return session;
}

// The production parent's fresh execution boundary, also exercised without Next.
export async function dispatchPreparedAnalysis(binding:PreparationBinding,ticket:PreparedTicket,signal:AbortSignal,href:()=>string,current:()=>boolean,save:(pending:PendingAnalysis)=>void){
 const session=await verifyPreparedSession(binding,ticket,signal,href,current);
 const guard=()=>{if(signal.aborted||!current()||!binding.accepts(ticket,session.user_id,href()))throw new PlanError(409);};
 guard();const pending=freshPending(ticket.ticker,ticket.query);save(pending);guard();
 const view=await postAnalysis(pending,session.csrf_token,signal);guard();return {pending,view};
}
