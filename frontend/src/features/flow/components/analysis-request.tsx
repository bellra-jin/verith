'use client';
import Link from 'next/link';
import {useCallback,useEffect,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {AnalysisHttpError,AnalysisIntent,analysisHref,canReplay,canonicalUuid,fetchSession,freshPending,getAnalysis,matchesAnalysisUrl,pendingKey,postAnalysis,readPending,writePending,type AnalysisView,type PendingAnalysis} from '../lib/analysis-request';

export function AnalysisEntry({analysisId}:{analysisId:string|null}){
 const [userId,setUserId]=useState<string|null>(null);const [error,setError]=useState('로그인 상태를 확인 중입니다.');
 useEffect(()=>{const abort=new AbortController();const timeout=setTimeout(()=>abort.abort(),15000);let active=true;
  void fetchSession(abort.signal).then(value=>{if(active){setUserId(value.user_id);setError('');}}).catch(()=>{if(active){setUserId(null);setError('로그인 상태를 확인할 수 없습니다.');}});
  return()=>{active=false;clearTimeout(timeout);abort.abort();};
 },[analysisId]);
 if(!userId)return <main><h1>Flow 분석</h1><p>{error||'로그인 후 이용하세요.'}</p><Link href="/api/auth/login">로그인</Link><Link href="/">홈</Link></main>;
 return <AnalysisRequest key={userId+':'+(analysisId??'new')} userId={userId} analysisId={analysisId} initialView={null} onAccountChange={setUserId}/>;
}

export function AnalysisRequest({userId,analysisId,initialView,onAccountChange}:{userId:string;analysisId:string|null;initialView:AnalysisView|null;onAccountChange:(id:string|null)=>void}){
 const router=useRouter();const [view,setView]=useState(initialView);const [verified,setVerified]=useState(false);const [busy,setBusy]=useState(false);
 const [ticker,setTicker]=useState('');const [question,setQuestion]=useState('');const [checked,setChecked]=useState(false);const [error,setError]=useState('');const [hasPending,setHasPending]=useState(false);const [replayable,setReplayable]=useState(false);
 const [blocked,setBlocked]=useState(false);const pending=useRef<PendingAnalysis|null>(null);const intent=useRef(new AnalysisIntent());
 const generation=useRef(0);const busyRef=useRef(false);const controller=useRef<AbortController|null>(null);const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const area=useRef<HTMLDivElement|null>(null);const active=useRef(true);const polls=useRef(0);
 const pollRequest=useRef<(id:string)=>void>(()=>{});
 const invalidate=useCallback(()=>{generation.current++;intent.current.invalidate();busyRef.current=false;controller.current?.abort();controller.current=null;if(timer.current)clearTimeout(timer.current);timer.current=null;pending.current=null;setHasPending(false);setReplayable(false);setTicker('');setQuestion('');setChecked(false);setBusy(false);setVerified(false);setView(null);if(area.current)area.current.hidden=true;},[]);
 const currentUrlMatches=useCallback(()=>matchesAnalysisUrl(window.location.pathname,window.location.search,analysisId),[analysisId]);
 useEffect(()=>{
  active.current=true;generation.current++;polls.current=0;let disposed=false;
  async function verify(idOverride?:string){
   const revision=generation.current;
   const accepts=()=>!disposed&&active.current&&generation.current===revision&&currentUrlMatches();
   const abort=new AbortController();controller.current?.abort();controller.current=abort;
   const timeout=setTimeout(()=>abort.abort(),15000);
   try{
    const session=await fetchSession(abort.signal);if(!accepts()||abort.signal.aborted)return;
    if(session.user_id!==canonicalUuid(userId)){invalidate();onAccountChange(session.user_id);return;}
    pending.current=readPending(sessionStorage,userId);setHasPending(pending.current!==null);setReplayable(canReplay(analysisId,pending.current));setBlocked(false);
    if(pending.current&&canReplay(analysisId,pending.current)){setTicker(pending.current.ticker);setQuestion(pending.current.question);}
    else{setTicker('');setQuestion('');setChecked(false);}
    const id=idOverride??analysisId??pending.current?.analysis_id;
    if(id){const value=await getAnalysis(id,abort.signal);if(!accepts()||abort.signal.aborted)return;setView(value);
     if(value.state==='running'&&polls.current++<15)timer.current=setTimeout(()=>{if(accepts())void verify(id);},1000);
    }
    if(accepts())setVerified(true);
   }catch(e){if(accepts()){setView(null);setVerified(false);if(e instanceof AnalysisHttpError&&e.status===401){invalidate();onAccountChange(null);}setError(e instanceof AnalysisHttpError&&e.status===401?'로그인 상태를 확인하세요.':'요청 상태를 확인할 수 없습니다. 새 분석을 자동 실행하지 않습니다.');}}
   finally{clearTimeout(timeout);}
  }
  pollRequest.current=id=>{polls.current=0;void verify(id);};
  function hidden(){active.current=false;invalidate();}
  function shown(){if(document.visibilityState==='hidden')return;if(!currentUrlMatches()){invalidate();router.refresh();return;}active.current=true;generation.current++;polls.current=0;void verify();}
  function visibility(){if(document.visibilityState==='hidden')hidden();else shown();}
  window.addEventListener('pagehide',hidden);window.addEventListener('pageshow',shown);document.addEventListener('visibilitychange',visibility);
  void verify();
  return()=>{disposed=true;active.current=false;pollRequest.current=()=>{};invalidate();window.removeEventListener('pagehide',hidden);window.removeEventListener('pageshow',shown);document.removeEventListener('visibilitychange',visibility);};
 },[userId,analysisId,router,invalidate,currentUrlMatches,onAccountChange]);
 async function execute(){
  if(busyRef.current||!checked||!verified||blocked||!currentUrlMatches()||analysisId!==null&&!canReplay(analysisId,pending.current))return;
  busyRef.current=true;setBusy(true);setError('');if(timer.current)clearTimeout(timer.current);polls.current=0;
  const ticket=intent.current.begin();if(ticket===null){busyRef.current=false;setBusy(false);return;}
  const revision=++generation.current;const abort=new AbortController();controller.current?.abort();controller.current=abort;
  const timeout=setTimeout(()=>abort.abort(),135000);
  try{
   const session=await fetchSession(abort.signal);if(abort.signal.aborted||revision!==generation.current||!intent.current.accepts(ticket))return;
   if(session.user_id!==canonicalUuid(userId)){invalidate();onAccountChange(session.user_id);return;}
   const value=pending.current??freshPending(ticker,question);
   try{writePending(sessionStorage,userId,value);}catch{setBlocked(true);throw Error('Request storage unavailable');}
   pending.current=value;setHasPending(true);
   const result=await postAnalysis(value,session.csrf_token,abort.signal);
   if(abort.signal.aborted||revision!==generation.current||!intent.current.accepts(ticket)||!currentUrlMatches())return;
   const known={...value,analysis_id:result.analysis_id};writePending(sessionStorage,userId,known);pending.current=known;setReplayable(canReplay(analysisId,known));setView(result);
   router.replace(analysisHref(result.analysis_id));if(result.state==='running')pollRequest.current(result.analysis_id);
  }catch(e){if(revision===generation.current&&intent.current.accepts(ticket)){
   if(e instanceof AnalysisHttpError&&e.status===401){invalidate();onAccountChange(null);}
   setError('응답을 확인하지 못했습니다. 입력과 멱등키를 유지합니다. 동일 요청 확인은 버튼을 누르세요.');
  }}finally{clearTimeout(timeout);intent.current.finish(ticket);if(revision===generation.current){busyRef.current=false;setBusy(false);}}
 }
 function startNew(){invalidate();pending.current=null;try{sessionStorage.removeItem(pendingKey(userId));window.location.assign('/research');}catch{setBlocked(true);setError('요청 기록을 변경할 수 없습니다.');}}
 const terminal=view&&['stored','failed','unknown'].includes(view.state);
 return <main><h1>Flow 분석</h1><p>수급 자료를 분석하고 본인 리포트로 저장합니다.</p>
  <label>종목코드<input value={ticker} maxLength={6} inputMode="numeric" disabled={!verified||busy} readOnly={hasPending||Boolean(analysisId)} onChange={e=>setTicker(e.target.value)}/></label>
  <label>질문<textarea value={question} maxLength={2000} disabled={!verified||busy} readOnly={hasPending||Boolean(analysisId)} onChange={e=>setQuestion(e.target.value)}/></label>
  <label><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/>분석 실행에 동의합니다.</label>
  <button type="button" disabled={!checked||!verified||busy||blocked||Boolean(terminal)||Boolean(analysisId&&!replayable)||view?.state==='running'} onClick={()=>void execute()}>{busy?'요청 중':hasPending?'동일 요청 확인':'Flow 분석 요청'}</button>
  <button type="button" onClick={startNew}>새 요청 준비</button><Link href="/">본인 보관함</Link>
  {error&&<p role="alert">{error}</p>}
  <div ref={area} hidden={!verified} aria-live="polite">{view&&<><p>상태: {view.state}</p><p>분석 요청 ID: {view.analysis_id}</p>
   {view.state==='stored'&&view.report_url&&<Link href={view.report_url}>저장된 본인 리포트 보기</Link>}
   {view.state==='unknown'&&<p>실행 결과가 불명확합니다. 외부 작업이 중단됐다는 뜻이 아니며 자동 재분석하지 않습니다.</p>}
   {view.state==='result_ready'&&<p>결과가 보존됐습니다. 동일 요청 확인은 저장만 복구하며 AI를 다시 호출하지 않습니다.</p>}
   {view.state==='failed'&&<p>분석 또는 게시에 실패했습니다. 이 요청은 재실행되지 않습니다.</p>}
  </>}</div>
 </main>;
}
