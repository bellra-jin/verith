'use client';
import {useCallback,useEffect,useLayoutEffect,useRef,useState,type ReactNode} from 'react';
import {ReportIntent,reportTarget,reportError,sameReportObservation,type ReportTarget,type ReportObservation} from '@/features/flow/lib/report-deletion';

function ReportControls({reportId,userId,returnTo,children}:{reportId:string;userId:string;returnTo:string;children?:ReactNode}){
 const intent=useRef<ReportIntent|null>(null);if(intent.current===null)intent.current=new ReportIntent();
 const identity=reportId+'|'+userId+'|'+returnTo,rendered=useRef(identity);
 const generation=useRef(0),alive=useRef(false),focused=useRef(true);
 const [visible,setVisible]=useState<ReportObservation|null>(null),[confirm,setConfirm]=useState<{target:ReportTarget;epoch:number}|null>(null),[pending,setPending]=useState(false),[error,setError]=useState('');
 const endIntent=useCallback(()=>{generation.current++;intent.current!.invalidate();},[]);
 const invalidate=useCallback(()=>{endIntent();setVisible(null);setConfirm(null);setPending(false);setError('');},[endIntent]);
 useLayoutEffect(()=>{rendered.current=identity;},[identity]);
 const observe=useCallback(async()=>{
  if(!alive.current)return;
  focused.current=document.hasFocus();
  invalidate();const epoch=generation.current;
  const href=window.location.href;const sameContext=()=>alive.current&&epoch===generation.current&&rendered.current===identity&&window.location.href===href;
  const current=()=>sameContext()&&focused.current&&document.hasFocus()&&document.visibilityState!=='hidden';
  try{
   if(document.visibilityState==='hidden'||!focused.current)return;
   const target=reportTarget(reportId,userId,window.location.href,returnTo);
   setPending(true);await intent.current!.verify(target,current);
   if(current()){setVisible({identity,href:target.href});setError('');}
  }catch(e){if(current())setError(reportError(e));}
  finally{if(sameContext()){if(!current())setVisible(null);setPending(false);}}
 },[identity,reportId,userId,returnTo,invalidate]);
 useEffect(()=>{
  alive.current=true;focused.current=document.hasFocus();let active=true;queueMicrotask(()=>{if(active)void observe();});
  const hide=()=>invalidate();const show=()=>{void observe();};
  const blur=()=>{focused.current=false;hide();};const focus=()=>{void observe();};
  window.addEventListener('blur',blur);window.addEventListener('focus',focus);
  let href=window.location.href;const locationCheck=()=>{if(href!==window.location.href){href=window.location.href;show();}};const locationTimer=setInterval(locationCheck,200);
  window.addEventListener('hashchange',locationCheck);
  window.addEventListener('pagehide',hide);window.addEventListener('pageshow',show);window.addEventListener('popstate',show);document.addEventListener('visibilitychange',show);
  return()=>{active=false;window.removeEventListener('blur',blur);window.removeEventListener('focus',focus);clearInterval(locationTimer);window.removeEventListener('hashchange',locationCheck);alive.current=false;endIntent();window.removeEventListener('pagehide',hide);window.removeEventListener('pageshow',show);window.removeEventListener('popstate',show);document.removeEventListener('visibilitychange',show);};
 },[observe,invalidate,endIntent]);
 function askConfirm(){
  if(!document.hasFocus()||document.visibilityState==='hidden'){invalidate();return;}
  if(!focused.current||!sameReportObservation(visible,identity,window.location.href)||intent.current!.pending){if(visible&&visible.href!==window.location.href)invalidate();return;}
  try{setConfirm({target:reportTarget(reportId,userId,window.location.href,returnTo),epoch:generation.current});}
  catch(e){invalidate();setError(reportError(e));}
 }
 async function remove(){
  if(!confirm||!sameReportObservation(visible,identity,window.location.href)||intent.current!.pending){if(confirm&&confirm.target.href!==window.location.href)invalidate();return;}
  const {target,epoch}=confirm;
  const sameContext=()=>alive.current&&epoch===generation.current&&rendered.current===identity&&window.location.href===target.href;
  const current=()=>sameContext()&&focused.current&&document.hasFocus()&&document.visibilityState!=='hidden';
  if(!current()){invalidate();return;}
  try{
   const task=intent.current!.remove(target,current);setPending(true);setConfirm(null);setError('');
   const next=await task;if(current()){setVisible(null);window.location.assign(next);}
  }catch(e){if(current()){setVisible(null);setError(reportError(e));}}
  finally{if(sameContext()){if(!current())setVisible(null);setPending(false);}}
 }
 const ready=sameReportObservation(visible,identity,typeof window==='undefined'?'':window.location.href);
 return <section aria-label="본인 결과 확인">
  {error&&<p role="alert">{error}</p>}
  {pending&&<p role="status">요청 확인 중…</p>}
  {!ready&&<button type="button" disabled={pending} onClick={()=>void observe()}>결과 상태 다시 확인</button>}
  {ready&&<>
   {!confirm?<button type="button" disabled={pending} onClick={askConfirm}>이 결과 삭제</button>:<div role="group" aria-label="결과 삭제 확인">
    <p>현재 결과를 삭제합니다. 되돌릴 수 없습니다. 분석 사용 횟수·불명 비용 예약은 자동 환불되지 않습니다.</p>
    <button type="button" disabled={pending} onClick={()=>setConfirm(null)}>취소</button>
    <button type="button" disabled={pending} onClick={()=>void remove()}>삭제 확인</button>
   </div>}
   {children}
  </>}
 </section>;
}
export function SessionControls({csrfToken,reportId,userId,returnTo='/',children}:{csrfToken:string;reportId?:string;userId?:string;returnTo?:string;children?:ReactNode}){
 const [error,setError]=useState('');
 async function logout(){try{const response=await fetch('/api/auth/logout',{method:'POST',headers:{'X-CSRF-Token':csrfToken},cache:'no-store'});if(!response.ok){setError('요청을 처리할 수 없습니다. 다시 로그인해 주세요.');return;}window.location.assign('/');}catch{setError('요청을 처리할 수 없습니다.');}}
 if(reportId)return <ReportControls reportId={reportId} userId={userId??''} returnTo={returnTo}>{children}</ReportControls>;
 return <div><button type="button" onClick={()=>void logout()}>로그아웃</button>{error&&<p role="alert">{error}</p>}</div>;
}
