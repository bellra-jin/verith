'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {DemoIntent,DemoLifecycle,DemoHttpError,canonicalUuid,demoHref,fetchDemo,fetchSession,postDemo,freshPending,readPending,writePending,pendingKey,uuid,type Pending,type DemoView} from '@/features/flow/lib/synthetic-demo';

export function SyntheticDemo({userId,runId,initialView}:{userId:string;runId:string|null;initialView:DemoView|null}) {
 const router=useRouter();const intent=useRef(new DemoIntent());const life=useRef(new DemoLifecycle());
 const controller=useRef<AbortController|null>(null);const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const pending=useRef<Pending|null>(null);const busyRef=useRef(false);const owner=useRef(userId);const activeRun=useRef(runId);const effectActive=useRef(true);
 const area=useRef<HTMLDivElement|null>(null);const publishRef=useRef<(value:DemoView,generation:number)=>void>(()=>{});
 const [view,setView]=useState<DemoView|null>(initialView);const [verified,setVerified]=useState(false);const [checked,setChecked]=useState(false);const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [hasPending,setHasPending]=useState(false);const [pendingRun,setPendingRun]=useState<string|null>(null);const [storageBlocked,setStorageBlocked]=useState(false);
 const invalidate=useCallback(()=>{
  life.current.invalidate();if(timer.current!==null){clearTimeout(timer.current);timer.current=null;}controller.current?.abort();
  activeRun.current=null;intent.current.reset(null);busyRef.current=false;
  if(area.current)area.current.hidden=true;
  setView(null);setVerified(false);setBusy(false);
 },[]);
 useEffect(()=>{
  let disposed=false;effectActive.current=true;owner.current=userId;
  const current=(generation:number)=>!disposed&&effectActive.current&&life.current.accepts(generation);
  function publish(value:DemoView,generation:number){
   if(!current(generation)||activeRun.current!==value.run_id||owner.current!==userId)return;
   setView(value);setVerified(true);if(area.current)area.current.hidden=false;
   if(timer.current!==null){clearTimeout(timer.current);timer.current=null;}
   if(value.stage==='running'&&life.current.takePoll(generation))timer.current=setTimeout(()=>void poll(value.run_id,generation),1000);
  }
  publishRef.current=publish;
  async function poll(id:string,generation:number){
   if(!current(generation)||activeRun.current!==id)return;
   const abort=new AbortController();controller.current=abort;
   try{
    const session=await fetchSession(abort.signal);
    if(!current(generation)||abort.signal.aborted)return;
    if(session.user_id!==userId){invalidate();setError('계정이 변경됐습니다. 요청 화면을 다시 여세요.');return;}
    const result=await fetchDemo(id,session.user_id,abort.signal);
    if(!current(generation)||abort.signal.aborted)return;
    publish(result,generation);
   }catch{if(current(generation)&&!abort.signal.aborted){invalidate();setError('상태 확인을 중단했습니다. 화면을 다시 여세요.');}}
  }
  async function verify(target:string|null){
   if(disposed||!effectActive.current)return;
   invalidate();activeRun.current=target;const generation=life.current.current();const abort=new AbortController();controller.current=abort;
   pending.current=null;setHasPending(false);setPendingRun(null);setStorageBlocked(false);setError('');
   try{
    const session=await fetchSession(abort.signal);
    if(!current(generation)||abort.signal.aborted)return;
    if(session.user_id!==userId){setError('계정이 변경됐습니다. 요청 화면을 다시 여세요.');return;}
    owner.current=session.user_id;intent.current.reset(session.user_id);
    try{pending.current=readPending(sessionStorage,session.user_id);setHasPending(pending.current!==null);setPendingRun(pending.current?.run_id ?? null);}catch{setStorageBlocked(true);setError('요청 기록이 손상됐거나 저장소를 사용할 수 없습니다. 새 합성 데모를 명시적으로 선택하세요.');}
    if(target!==null){
     const result=await fetchDemo(target,session.user_id,abort.signal);
     if(!current(generation)||abort.signal.aborted)return;
     publish(result,generation);
    }else{setVerified(true);if(area.current)area.current.hidden=false;}
   }catch(e){if(current(generation)&&!abort.signal.aborted){invalidate();setError(e instanceof DemoHttpError&&e.status===401?'세션이 종료됐습니다. 다시 로그인하세요.':'본인 데모를 확인할 수 없습니다.');}}
  }
  function shown(event?:PageTransitionEvent){
   if(event?.persisted)effectActive.current=true;
   if(!effectActive.current)return;
   const query=new URL(window.location.href).searchParams;const ids=query.getAll('run_id');
   if(ids.length>1||Array.from(query.keys()).some(k=>k!=='run_id')||ids.length===1&&!uuid(ids[0])){invalidate();return;}
   void verify(ids.length===1?canonicalUuid(ids[0]):null);
  }
  function visibility(){if(document.visibilityState==='hidden')invalidate();else if(effectActive.current)shown();}
  window.addEventListener('pagehide',invalidate);window.addEventListener('pageshow',shown);document.addEventListener('visibilitychange',visibility);
  void verify(runId);
  return()=>{disposed=true;effectActive.current=false;invalidate();publishRef.current=()=>{};window.removeEventListener('pagehide',invalidate);window.removeEventListener('pageshow',shown);document.removeEventListener('visibilitychange',visibility);};
 },[userId,runId,invalidate]);

 async function execute(){
  if(busyRef.current||!checked||!verified||storageBlocked)return;
  busyRef.current=true;setBusy(true);setError('');const generation=life.current.current();
  const abort=new AbortController();controller.current?.abort();controller.current=abort;
  let ticket:ReturnType<DemoIntent['begin']>=null;
  try{
   const session=await fetchSession(abort.signal);
   if(abort.signal.aborted||!life.current.accepts(generation)||controller.current!==abort)return;
   if(session.user_id!==userId||owner.current!==userId){invalidate();throw new DemoHttpError(401);}
   const value=pending.current ?? freshPending();
   writePending(sessionStorage,session.user_id,value);pending.current=value;setHasPending(true);setPendingRun(value.run_id ?? null);
   ticket=intent.current.begin(session.user_id,value.idempotency_key);if(!ticket)return;
   const result=await postDemo(value,session,abort.signal);
   if(abort.signal.aborted||!life.current.accepts(generation)||!intent.current.accepts(ticket,pending.current?.idempotency_key ?? '')||owner.current!==session.user_id)return;
   const known={...value,run_id:result.run_id};writePending(sessionStorage,session.user_id,known);pending.current=known;setPendingRun(known.run_id);activeRun.current=result.run_id;
   publishRef.current(result,generation);router.replace(demoHref(result.run_id));
  }catch(e){if(!abort.signal.aborted&&life.current.accepts(generation)){if(e instanceof DemoHttpError&&e.status===401)invalidate();setError('응답을 확인하지 못했습니다. 기존 요청을 유지합니다. 동일 요청 확인은 버튼을 누르세요.');}}
  finally{if(ticket)intent.current.finish(ticket);if(controller.current===abort){busyRef.current=false;setBusy(false);}}
 }
 function startNew(){
  effectActive.current=false;invalidate();pending.current=null;setPendingRun(null);setChecked(false);setError('');
  try{sessionStorage.removeItem(pendingKey(userId));setStorageBlocked(false);setHasPending(false);}catch{setStorageBlocked(true);setError('요청 기록을 저장할 수 없습니다.');return;}
  window.location.assign('/flow/demo');
 }
 const canRetry=hasPending&&(!runId||pendingRun===runId);
 return <main><h1>Flow 합성 데모</h1><p>합성 데모 · 실제 시세/수급/투자 분석 아님 · 실제 보관함에 게시되지 않음</p><p>005930 표시용 예시 · 합성 20개 달력 행</p>
  <label><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/>합성 데모 실행에 동의합니다.</label>
  <button type="button" disabled={!checked||busy||!verified||storageBlocked||Boolean(runId&&!canRetry)||Boolean(view&&['running','succeeded','failed','timed_out'].includes(view.stage))} onClick={()=>void execute()}>{busy?'요청 중':hasPending?'동일 요청 확인':'합성 데모 실행'}</button>
  <button type="button" onClick={startNew}>새 합성 데모 (이전 요청과 별개)</button><Link href="/">홈</Link>
  {error&&<p role="alert">{error}</p>}
  <div ref={area} hidden={!verified} aria-live="polite">{view&&<><p>단계: {view.stage}</p><p>데모 요청 ID: {view.run_id}</p>
   {view.result&&<><h2>데모 전용 결과 저장됨</h2><p>{view.result.start_date} ~ {view.result.end_date} · {view.result.row_count}개 달력 행</p><p>개인 {view.result.totals.individual}주 · 외국인 {view.result.totals.foreign}주 · 기관 {view.result.totals.institution}주 · 거래대금 {view.result.totals.trading_value} KRW</p><p>{view.result.notice}</p></>}
   {(view.stage==='failed'||view.stage==='timed_out')&&<p>결과 없음 · 이 요청은 재실행되지 않습니다.</p>}
   {(view.stage==='admitted'||view.stage==='prepared')&&<p>접수/입력 준비 단계이며 분석 성공이 아닙니다. 원래 요청 기록이 있으면 동일 요청 확인을 명시적으로 선택하세요.</p>}
  </>}</div>
 </main>;
}
