"use client";
import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {AnalysisAccountChanged} from '@/features/flow/lib/analysis-request';
import {prepareQuery,type Plan} from '../lib/query-plan';

type Props={userId:string;disabled?:boolean;onPrepared:(value:{ticker:string;query:string})=>void;onClear:()=>void;onAccountChange:()=>void};
export function QueryPreparation(props:Props){return <PreparationState key={props.userId} {...props}/>;}
function PreparationState({userId,disabled=false,onPrepared,onClear,onAccountChange}:Props){
 const [planHref,setPlanHref]=useState<string|null>(null);
 const [query,setQuery]=useState(''),[plan,setPlan]=useState<Plan|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const owner=useRef(userId);useLayoutEffect(()=>{owner.current=userId;},[userId]);
 const revision=useRef(0),locked=useRef(false),abort=useRef<AbortController|null>(null),active=useRef(true);
 useEffect(()=>{
  active.current=true;const generation=revision;const invalidate=()=>{revision.current++;abort.current?.abort();locked.current=false;setBusy(false);setPlan(null);setPlanHref(null);setError('');onClear();};
  const hide=()=>invalidate(),changed=()=>{if(document.visibilityState==='hidden')hide();};
  let href=window.location.href;const locationCheck=()=>{if(href!==window.location.href){href=window.location.href;hide();}};const locationTimer=setInterval(locationCheck,200);
  window.addEventListener('pagehide',hide);window.addEventListener('popstate',hide);window.addEventListener('hashchange',hide);document.addEventListener('visibilitychange',changed);
  return()=>{clearInterval(locationTimer);active.current=false;generation.current++;abort.current?.abort();window.removeEventListener('pagehide',hide);window.removeEventListener('popstate',hide);window.removeEventListener('hashchange',hide);document.removeEventListener('visibilitychange',changed);};
 },[userId,onClear]);
 function edit(value:string){revision.current++;abort.current?.abort();locked.current=false;setBusy(false);setQuery(value);setPlan(null);setPlanHref(null);setError('');onClear();}
 async function prepare(selected_ticker?:string){
  if(locked.current||disabled||document.visibilityState==='hidden')return;
  if(selected_ticker&&planHref!==window.location.href){edit(query);return;}
  locked.current=true;setBusy(true);setError('');onClear();
  const ticket=++revision.current,href=window.location.href,controller=new AbortController();abort.current?.abort();abort.current=controller;
  const current=()=>active.current&&owner.current===userId&&ticket===revision.current&&window.location.href===href&&document.visibilityState!=='hidden';
  const timeout=setTimeout(()=>controller.abort(),15000);
  try{
   const selection=selected_ticker&&plan?.candidate_ref?{selected_ticker,candidate_ref:plan.candidate_ref}:undefined;
   const result=await prepareQuery(query,userId,controller.signal,current,selection);
   if(!current()||controller.signal.aborted)return;setPlan(result);setPlanHref(href);
   if(result.status==='ready_for_confirmation'&&result.requested_views.join(',')==='flow'&&result.resolution?.stock)onPrepared({ticker:result.resolution.stock.stock_code,query});
  }catch(e){if(current()){setPlan(null);setPlanHref(null);setError('분석 준비를 확인할 수 없습니다. 다시 준비해 주세요.');if(e instanceof AnalysisAccountChanged)onAccountChange();}}
  finally{clearTimeout(timeout);if(ticket===revision.current){locked.current=false;setBusy(false);}}
 }
 return <section aria-label="자연어 분석 준비">
  <h2>어떤 수급이 궁금한가요?</h2><p>현재 개별 종목의 명확한 수급 질문만 Flow로 준비합니다. 계획은 분석 실행이나 비용 예약이 아닙니다.</p>
  <label>질문<textarea value={query} maxLength={300} disabled={disabled} onChange={e=>edit(e.target.value)}/></label>
  <button type="button" disabled={busy||disabled||!query.trim()} onClick={()=>void prepare()}>{busy?'준비 확인 중':'질문 준비'}</button>
  <button type="button" onClick={()=>edit(query)}>준비 취소</button>
  {error&&<p role="alert">{error}</p>}
  {plan?.status==='ready_for_confirmation'&&plan.resolution?.stock&&<p>확인 종목: {plan.resolution.stock.stock_name} ({plan.resolution.stock.stock_code}) · 선택 관점: Flow. 아래에서 명시적으로 동의한 뒤 분석을 요청하세요. 종목명은 준비 시점 안내이며 실제 접수 시 마스터가 다시 검증됩니다.</p>}
  {plan?.status==='needs_stock_selection'&&<fieldset><legend>종목을 직접 확인해 주세요</legend>{plan.resolution?.candidates.length?plan.resolution.candidates.map(c=><button type="button" key={c.stock_code} disabled={busy||disabled} onClick={()=>void prepare(c.stock_code)}>{c.stock_name} ({c.stock_code}) {c.market??''}</button>):<p>현재 선택할 후보가 없습니다. 질문을 구체화해 주세요.</p>}</fieldset>}
  {plan?.status==='selection_stale'&&<p>후보 또는 질문이 달라졌습니다. 새로 준비해 주세요.</p>}
  {plan?.status==='not_found'&&<p>등록 종목을 찾지 못했습니다. 다른 이름으로 질문해 주세요.</p>}
  {plan?.status==='needs_clarification'&&<p>개별 종목과 수급 관점을 구체적으로 질문해 주세요.</p>}
  {plan?.status==='unsupported'&&<p>요청한 관점은 아직 지원하지 않습니다. 차트·종합·재무·거시·뉴스를 Flow로 대신 실행하지 않습니다.</p>}
 </section>;
}
