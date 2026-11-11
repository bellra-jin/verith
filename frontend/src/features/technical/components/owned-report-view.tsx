"use client";
import {useEffect,useRef,useState} from 'react';
import {TechnicalBoundaryPreview} from './technical-boundary-preview';
import {OwnedReadAction,type OwnedReadState,matchesOwnedReadUrl} from '../lib/owned-report-read';

export function OwnedReadContent({state,onRetry}:{state:OwnedReadState;onRetry:()=>void}){
  const pending=state.kind==='pending';
  return <section aria-label="본인 저장 차트 · 조회 전용" aria-busy={pending} className="min-w-0 space-y-4 break-words">
    <header className="space-y-2"><h1 className="text-xl font-semibold">본인 저장 차트 · 조회 전용</h1>
      <p className="text-sm text-slate-600">저장된 결과만 조회합니다. 새 분석을 실행하지 않습니다.</p>
      <a href="/research" className="inline-block rounded-lg underline focus-visible:outline-2">리서치 대화로 돌아가기</a></header>
    {pending&&<p role="status">저장된 차트 확인 중 · 새 분석 실행 없음</p>}
    {state.kind==='idle'&&<p role="status">내용을 숨겼습니다. 다시 보려면 로그인 상태와 결과를 확인해 주세요.</p>}
    {state.kind==='error'&&<p role="alert">{state.code==='AUTH_REQUIRED'||state.code==='ACCOUNT_CHANGED'?'로그인 상태가 바뀌었습니다. 본인 계정으로 다시 확인해 주세요.':
      state.code==='RESOURCE_NOT_FOUND'?'본인이 볼 수 있는 저장 결과를 찾을 수 없습니다.':state.code==='DEADLINE_EXCEEDED'?'조회 시간이 지났습니다. 다시 확인할 수 있습니다.':'저장된 차트 결과를 표시할 수 없습니다. 다시 확인해 주세요.'}</p>}
    {state.kind==='list'&&(state.value.items.length===0?<p role="status">본인이 볼 수 있는 저장 차트가 없습니다.</p>:
      <ul className="grid min-w-0 gap-3">{state.value.items.map(item=><li key={item.report_id} className="min-w-0 rounded-xl border border-slate-200 bg-white p-4">
        <a href={'/reports/technical/'+item.report_id} className="font-semibold underline focus-visible:outline-2">{item.stock.stock_name} · 저장 차트 보기</a>
        <p className="mt-2 text-sm text-slate-600">저장 시각 {new Date(item.created_at).toLocaleString('ko-KR')}</p>
        <p className="text-sm text-slate-600">요청 기준시점 {new Date(item.requested_as_of).toLocaleString('ko-KR')} · 합성 자료 · 기준시점 적용 미검증</p>
      </li>)}</ul>)}
    {state.kind==='list'&&state.value.has_more&&<p className="text-sm text-slate-600">표시 범위 뒤에 저장된 결과가 더 있습니다.</p>}
    {state.kind==='detail'&&<>{/* eslint-disable-next-line @next/next/no-html-link-for-pages -- Native navigation disposes the prior owned read session. */}
      <a href="/reports/technical" className="inline-block underline">본인 저장 차트 목록</a><TechnicalBoundaryPreview response={state.value.response} expected={state.value.expected}/></>}
    <button type="button" disabled={pending} onClick={onRetry} className="rounded-xl border border-slate-300 bg-white px-4 py-2 disabled:opacity-50 focus-visible:outline-2">저장 결과 다시 확인 · GET 조회만</button>
  </section>;
}

export function OwnedReportView({reportId=null}:{reportId?:string|null}){
  return <OwnedReadSession key={reportId??'owned-list'} reportId={reportId}/>;
}

function OwnedReadSession({reportId}:{reportId:string|null}){
  const [state,setState]=useState<OwnedReadState>({kind:'idle'}),action=useRef<OwnedReadAction|null>(null);
  useEffect(()=>{
    const search=window.location.search,current=new OwnedReadAction(setState,(id,query)=>document.visibilityState==='visible'&&window.location.search===query&&matchesOwnedReadUrl(id,window.location.pathname,query));
    action.current=current;const hide=()=>{if(document.visibilityState!=='visible')current.cancel();},leave=()=>current.cancel();
    document.addEventListener('visibilitychange',hide);window.addEventListener('pagehide',leave);window.addEventListener('popstate',leave);void current.run(reportId,search);
    return ()=>{current.cancel(false);if(action.current===current)action.current=null;document.removeEventListener('visibilitychange',hide);window.removeEventListener('pagehide',leave);window.removeEventListener('popstate',leave);};
  },[reportId]);
  return <OwnedReadContent state={state} onRetry={()=>void action.current?.run(reportId,window.location.search)}/>;
}
