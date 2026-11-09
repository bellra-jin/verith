'use client';
import Link from 'next/link';
import {PreparationBinding,dispatchPreparedAnalysis} from '@/features/supervisor/lib/query-plan';
import {QueryPreparation} from '@/features/supervisor/components/query-preparation';
import {useCallback,useEffect,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {AnalysisAccountChanged,AnalysisHttpError,AnalysisIntent,AnalysisObservation,analysisHref,canReplay,canonicalUuid,fetchSession,matchesAnalysisUrl,observationId,observeAnalysis,pendingKey,postAnalysis,readPending,writePending,type AnalysisView,type PendingAnalysis} from '../lib/analysis-request';

export function AnalysisEntry({analysisId}:{analysisId:string|null}){
 const [userId,setUserId]=useState<string|null>(null);const [error,setError]=useState('로그인 상태를 확인 중입니다.');
 const [retry,setRetry]=useState(0);const [checking,setChecking]=useState(true);const checkingRef=useRef(true);
 useEffect(()=>{const abort=new AbortController();const timeout=setTimeout(()=>abort.abort(),15000);let active=true;checkingRef.current=true;
  void fetchSession(abort.signal).then(value=>{if(active&&!abort.signal.aborted&&document.visibilityState!=='hidden'){setUserId(value.user_id);setError('');}}).catch(()=>{if(active){setUserId(null);setError('로그인 상태를 확인할 수 없습니다.');}}).finally(()=>{if(active){checkingRef.current=false;setChecking(false);}});
  return()=>{active=false;clearTimeout(timeout);abort.abort();};
 },[analysisId,retry]);
 function retrySession(){if(checkingRef.current)return;checkingRef.current=true;setChecking(true);setRetry(value=>value+1);}
 if(!userId)return <main><h1>Flow 분석</h1><p>{error||'로그인 후 이용하세요.'}</p><button disabled={checking} onClick={retrySession}>로그인 상태 다시 확인</button><Link href="/api/auth/login">로그인</Link><Link href="/">홈</Link></main>;
 return <AnalysisRequest key={userId+':'+(analysisId??'new')} userId={userId} analysisId={analysisId} initialView={null} onAccountChange={setUserId}/>;
}

export function AnalysisRequest({userId,analysisId,initialView,onAccountChange}:{userId:string;analysisId:string|null;initialView:AnalysisView|null;onAccountChange:(id:string|null)=>void}){
 const router=useRouter();const [view,setView]=useState(initialView);const [verified,setVerified]=useState(false);const [busy,setBusy]=useState(false);
 const [ticker,setTicker]=useState('');const [question,setQuestion]=useState('');const [checked,setChecked]=useState(false);const [error,setError]=useState('');const [hasPending,setHasPending]=useState(false);const [replayable,setReplayable]=useState(false);
 const [prepared,setPrepared]=useState(false);
 const [blocked,setBlocked]=useState(false);const [knownId,setKnownId]=useState<string|null>(analysisId);const [reading,setReading]=useState<'auto'|'manual'|null>(null);const [observationEnded,setObservationEnded]=useState(false);
 const preparedHref=useRef<string|null>(null);const preparationBinding=useRef(new PreparationBinding());
 const pending=useRef<PendingAnalysis|null>(null);const intent=useRef(new AnalysisIntent());const readIntent=useRef(new AnalysisIntent());const observation=useRef(new AnalysisObservation());
 const generation=useRef(0);const busyRef=useRef(false);const readingRef=useRef<'auto'|'manual'|null>(null);const knownIdRef=useRef<string|null>(analysisId);
 const controller=useRef<AbortController|null>(null);const timer=useRef<ReturnType<typeof setTimeout>|null>(null);const area=useRef<HTMLDivElement|null>(null);const active=useRef(true);
 const readRequest=useRef<(manual:boolean,id?:string)=>void>(()=>{});
 const invalidate=useCallback(()=>{generation.current++;intent.current.invalidate();readIntent.current.invalidate();busyRef.current=false;readingRef.current=null;controller.current?.abort();controller.current=null;if(timer.current)clearTimeout(timer.current);timer.current=null;pending.current=null;knownIdRef.current=null;setKnownId(null);setHasPending(false);setReplayable(false);setTicker('');setQuestion('');setChecked(false);setPrepared(false);preparedHref.current=null;preparationBinding.current.clear();setBusy(false);setReading(null);setVerified(false);setView(null);if(area.current)area.current.hidden=true;},[]);
 const currentUrlMatches=useCallback(()=>matchesAnalysisUrl(window.location.pathname,window.location.search,analysisId),[analysisId]);
 useEffect(()=>{
  active.current=true;generation.current++;let disposed=false;
  async function verify(manual=false,idOverride?:string){
   if(busyRef.current||manual&&readingRef.current==='manual'||!active.current||!currentUrlMatches())return;
   // Synchronize invalidation before an old abort/catch/finally can run.
   if(timer.current)clearTimeout(timer.current);timer.current=null;controller.current?.abort();readIntent.current.invalidate();
   const ticket=readIntent.current.begin();if(ticket===null)return;
   const revision=++generation.current;readingRef.current=manual?'manual':'auto';
   const accepts=()=>!disposed&&active.current&&generation.current===revision&&readIntent.current.accepts(ticket)&&currentUrlMatches();
   const abort=new AbortController();controller.current=abort;const timeout=setTimeout(()=>abort.abort(),15000);
   try{
    let loaded:PendingAnalysis|null=null;let storageBlocked=false;
    try{loaded=readPending(sessionStorage,userId);}catch{storageBlocked=true;}
    const id=observationId(analysisId,loaded?.analysis_id??idOverride??knownIdRef.current);
    // A known same-account identity may be retried after a GET failure; it never
    // authorizes POST. Every attempt below revalidates the actual session first.
    if(id){knownIdRef.current=id;setKnownId(id);observation.current.begin(id,performance.now());}
    if(manual){observation.current.stop();setObservationEnded(true);}
    setReading(manual?'manual':'auto');
    const result=await observeAnalysis(userId,id,abort.signal,accepts,()=>manual||observation.current.permit(performance.now()));if(result===null||!accepts())return;
    pending.current=loaded;setHasPending(loaded!==null);setReplayable(canReplay(id,loaded));setBlocked(storageBlocked);
    if(loaded&&canReplay(analysisId,loaded)){setTicker(loaded.ticker);setQuestion(loaded.question);}
    else{setTicker('');setQuestion('');setChecked(false);}
    if(!result.stopped)setView(result.view);setVerified(!result.stopped);setError(storageBlocked?'요청 기록을 읽지 못해 POST는 차단했습니다. 알려진 상태만 조회할 수 있습니다.':'');
    if(result.stopped)setObservationEnded(true);
    if(!manual&&result.view){
     const next=observation.current.next(result.view,performance.now(),Date.now());
     setObservationEnded(next.kind==='stop'&&result.view.state==='running');
     if(next.kind!=='stop')timer.current=setTimeout(()=>{if(accepts())void verify(false,id??undefined);},next.delay);
    }
   }catch(e){if(accepts()){
    setView(null);setVerified(false);setObservationEnded(true);
    if(e instanceof AnalysisAccountChanged){invalidate();onAccountChange(null);router.replace('/research');}
    else if(e instanceof AnalysisHttpError&&e.status===401){invalidate();onAccountChange(null);}
    setError('상태를 확인하지 못했습니다. 알려진 ID로 상태 다시 조회가 가능합니다. 새 분석은 자동 실행하지 않습니다.');
   }}finally{
    clearTimeout(timeout);readIntent.current.finish(ticket);
    if(generation.current===revision){readingRef.current=null;setReading(null);}
   }
  }
  readRequest.current=(manual,id)=>{void verify(manual,id);};
  function hidden(){active.current=false;invalidate();}
  function shown(){if(document.visibilityState==='hidden')return;if(!currentUrlMatches()){invalidate();router.refresh();return;}active.current=true;generation.current++;void verify();}
  function visibility(){if(document.visibilityState==='hidden')hidden();else shown();}
  window.addEventListener('pagehide',hidden);window.addEventListener('pageshow',shown);document.addEventListener('visibilitychange',visibility);void verify();
  return()=>{disposed=true;active.current=false;readRequest.current=()=>{};invalidate();window.removeEventListener('pagehide',hidden);window.removeEventListener('pageshow',shown);document.removeEventListener('visibilitychange',visibility);};
 },[userId,analysisId,router,invalidate,currentUrlMatches,onAccountChange]);
 const clearPreparation=useCallback(()=>{if(pending.current||knownIdRef.current)return;preparationBinding.current.clear();if(busyRef.current){generation.current++;intent.current.invalidate();controller.current?.abort();busyRef.current=false;setBusy(false);}preparedHref.current=null;setPrepared(false);setTicker('');setQuestion('');setChecked(false);},[]);
 const acceptPreparation=useCallback((value:{ticker:string;query:string})=>{if(!active.current||pending.current||knownIdRef.current||!currentUrlMatches())return;preparedHref.current=window.location.href;preparationBinding.current.bind({owner:userId,href:window.location.href,ticker:value.ticker,query:value.query});setTicker(value.ticker);setQuestion(value.query);setChecked(false);setPrepared(true);},[currentUrlMatches,userId]);
 async function execute(){
  if(busyRef.current||readingRef.current!==null||!pending.current&&(!prepared||preparedHref.current!==window.location.href)||!checked||!verified||blocked||!currentUrlMatches()||analysisId!==null&&!canReplay(analysisId,pending.current)||knownIdRef.current!==null&&!canReplay(knownIdRef.current,pending.current))return;
  const preparation=pending.current?null:preparationBinding.current.capture(userId,window.location.href);
  if(!pending.current&&!preparation)return;
  busyRef.current=true;setBusy(true);setError('');if(timer.current)clearTimeout(timer.current);readIntent.current.invalidate();
  const ticket=intent.current.begin();if(ticket===null){busyRef.current=false;setBusy(false);return;}
  const revision=++generation.current;const abort=new AbortController();controller.current?.abort();controller.current=abort;const timeout=setTimeout(()=>abort.abort(),135000);
  try{
   const save=(value:PendingAnalysis)=>{
    try{writePending(sessionStorage,userId,value);}catch{setBlocked(true);throw Error('Request storage unavailable');}
    pending.current=value;setHasPending(true);
   };
   let value:PendingAnalysis,result:AnalysisView;
   if(preparation){
    const outcome=await dispatchPreparedAnalysis(preparationBinding.current,preparation,abort.signal,()=>window.location.href,()=>active.current&&revision===generation.current&&intent.current.accepts(ticket)&&currentUrlMatches()&&document.visibilityState!=='hidden',save);
    value=outcome.pending;result=outcome.view;
   }else{
    const session=await fetchSession(abort.signal);if(abort.signal.aborted||revision!==generation.current||!intent.current.accepts(ticket))return;
    if(session.user_id!==canonicalUuid(userId)){invalidate();onAccountChange(null);router.replace('/research');return;}
    if(!pending.current)return;value=pending.current;save(value);
    result=await postAnalysis(value,session.csrf_token,abort.signal);
   }
   if(abort.signal.aborted||revision!==generation.current||!intent.current.accepts(ticket)||!currentUrlMatches())return;
   const known={...value,analysis_id:result.analysis_id};writePending(sessionStorage,userId,known);pending.current=known;knownIdRef.current=result.analysis_id;setKnownId(result.analysis_id);setReplayable(canReplay(result.analysis_id,known));setView(result);
   router.replace(analysisHref(result.analysis_id));
   // Start observation after the POST finally releases the synchronous busy gate.
   if(result.state==='running')timer.current=setTimeout(()=>{if(revision===generation.current)readRequest.current(false,result.analysis_id);},0);
  }catch(e){if(revision===generation.current&&intent.current.accepts(ticket)){
   if(e instanceof AnalysisAccountChanged){invalidate();onAccountChange(null);router.replace('/research');}
   else if(e instanceof AnalysisHttpError&&e.status===401){invalidate();onAccountChange(null);}
   setError(e instanceof AnalysisHttpError&&e.code==='USAGE_LIMIT_EXCEEDED'?e.message:'응답을 확인하지 못했습니다. 입력과 멱등키를 유지합니다. 동일 요청 확인은 버튼을 누르세요.');
  }}finally{clearTimeout(timeout);intent.current.finish(ticket);if(revision===generation.current){busyRef.current=false;setBusy(false);}}
 }
 function startNew(){invalidate();pending.current=null;try{sessionStorage.removeItem(pendingKey(userId));window.location.assign('/research');}catch{setBlocked(true);setError('요청 기록을 변경할 수 없습니다.');}}
 const terminal=view&&['stored','failed','unknown'].includes(view.state);
 return <main><h1>Flow 분석</h1><p>수급 자료를 분석하고 본인 리포트로 저장합니다.</p>
  {!hasPending&&!analysisId&&!knownId&&verified&&<QueryPreparation userId={userId} disabled={busy||reading!==null||blocked} onPrepared={acceptPreparation} onClear={clearPreparation} onAccountChange={()=>{invalidate();onAccountChange(null);}}/>}
  {(hasPending||analysisId||knownId)&&<><label>종목코드<input value={ticker} maxLength={6} inputMode="numeric" disabled={!verified||busy} readOnly={hasPending||Boolean(analysisId)} onChange={e=>setTicker(e.target.value)}/></label>
  <label>질문<textarea value={question} maxLength={2000} disabled={!verified||busy} readOnly={hasPending||Boolean(analysisId)} onChange={e=>setQuestion(e.target.value)}/></label></>}
  <label><input type="checkbox" checked={checked} disabled={busy||!hasPending&&!prepared} onChange={e=>{preparationBinding.current.setConsent(e.target.checked);setChecked(e.target.checked);}}/>분석 실행에 동의합니다.</label>
  <button type="button" disabled={!checked||!verified||!hasPending&&!prepared||busy||reading!==null||blocked||Boolean(terminal)||Boolean((analysisId||knownId)&&!replayable)||view?.state==='running'} onClick={()=>void execute()}>{busy?'요청 중':hasPending?'동일 요청 확인':'Flow 분석 요청'}</button>
  <button type="button" disabled={busy||reading==='manual'||!(analysisId||knownId)} onClick={()=>readRequest.current(true)}>상태 다시 조회 (실행 없음)</button>
  <button type="button" onClick={startNew}>새 요청 준비</button><Link href="/">본인 보관함</Link>
  {error&&<p role="alert">{error}</p>}
  {observationEnded&&<p>자동 관측을 종료했습니다. 상태 다시 조회는 GET만 수행합니다. 대기 종료가 AI 작업이나 과금 중단을 뜻하지는 않습니다.</p>}
  <div ref={area} hidden={!verified} aria-live="polite">{view&&<><p>상태: {view.state}</p><p>분석 요청 ID: {view.analysis_id}</p>
   {view.state==='stored'&&view.report_url&&<Link href={view.report_url}>저장된 본인 리포트 보기</Link>}
   {view.state==='unknown'&&<p>실행 결과가 불명확합니다. 외부 작업이 중단됐다는 뜻이 아니며 자동 재분석하지 않습니다.</p>}
   {view.state==='result_ready'&&<p>결과가 보존됐습니다. 상태 GET은 게시하지 않습니다. 동의 후 동일 요청 확인 POST로 snapshot만 게시하며 AI를 재호출하지 않습니다.</p>}
   {view.state==='failed'&&<p>분석 또는 게시에 실패했습니다. 이 요청은 재실행되지 않습니다.</p>}
  </>}</div>
 </main>;
}
