"use client";
import {useCallback,useEffect,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {AnalysisEntry} from '@/features/flow/components/analysis-request';
import {fetchSession,AnalysisIntent,AnalysisObservation,AnalysisAccountChanged} from '@/features/flow/lib/analysis-request';
import {ChatView} from './chat-view';
import {coreRequest,loadCoreRecovery,writePending,freshPending,pendingKey,matchesUrl,CoreHttpError,legacyFlowRecovery,canReplayCore,requiresReauthentication,CoreObservationTimer,clarifiedDraft} from '../lib/supervisor-request';
import type {Draft,Plan,Outcome,Pending,Answer} from '../model/chat';
import '../styles/chat.css';
const empty=():Draft=>({original_query:'',answers:[],revision:0});
export function SupervisorChat({supervisorId}:{supervisorId:string|null}){
 const [user,setUser]=useState<string|null>(null),
  [retry,setRetry]=useState(0),
  [legacy,setLegacy]=useState(false);
 useEffect(()=>{const c=new AbortController(),t=setTimeout(()=>c.abort(),15000);
 let live=true;
 void fetchSession(c.signal).then(s=>{if(live&&!c.signal.aborted){setLegacy(supervisorId===null&&legacyFlowRecovery(sessionStorage,s.user_id,null));
 setUser(s.user_id);
 }}).catch(()=>{if(live)setUser(null);
 });
 return()=>{live=false;
 clearTimeout(t);
 c.abort();
 };
 },[retry,supervisorId]);
 if(!user)return <section className="supervisor-chat"><h1>Supervisor 리서치</h1><p>로그인 상태를 확인한 뒤 질문을 보여드립니다.</p><button onClick={()=>setRetry(v=>v+1)}>로그인 상태 다시 확인</button><button onClick={()=>window.location.assign('/api/auth/login')}>로그인</button></section>;
 if(legacy)return <AnalysisEntry analysisId={null}/>;
 return <Conversation key={user+':'+(supervisorId??'new')} user={user} supervisorId={supervisorId} onAccountChange={()=>{setUser(null);
 setRetry(v=>v+1);
 }}/>;
}
function Conversation({user,supervisorId,onAccountChange}:{user:string;
supervisorId:string|null;
onAccountChange:()=>void}){
 const router=useRouter(),
  [draft,setDraft]=useState<Draft>(empty),
  [plan,setPlan]=useState<Plan|null>(null),
  [outcome,setOutcome]=useState<Outcome|null>(null),
  [busy,setBusy]=useState(false),
  [verified,setVerified]=useState(false),
  [locked,setLocked]=useState(Boolean(supervisorId)),
  [error,setError]=useState(''),
  [consent,setConsent]=useState(false),
  [partial,setPartial]=useState(false),
  [waivers,setWaivers]=useState<string[]>([]),
  [ended,setEnded]=useState(false),
  [replayable,setReplayable]=useState(false);
 const draftRef=useRef(draft),planRef=useRef<Plan|null>(null),outcomeRef=useRef<Outcome|null>(null),
 pending=useRef<Pending|null>(null),
 known=useRef<string|null>(supervisorId),
 intent=useRef(new AnalysisIntent()),
 generation=useRef(0),
 controller=useRef<AbortController|null>(null),
 active=useRef(true),
 verifiedHref=useRef<string|null>(null),
 consentRef=useRef({allow:false,partial:false,waivers:[] as string[]}),
 observation=useRef(new AnalysisObservation()),
 timer=useRef(new CoreObservationTimer());
 const observedFlow=useRef<string|null>(null);
 const restore=useRef<(manual?:boolean)=>void>(()=>{});
 const clearConsent=useCallback(()=>{consentRef.current={allow:false,partial:false,waivers:[]};
 setConsent(false);
 setPartial(false);
 setWaivers([]);
 },[]);
 const invalidate=useCallback(()=>{generation.current++;
 intent.current.invalidate();
 controller.current?.abort();
 timer.current.stop();
 verifiedHref.current=null;
 setVerified(false);
 setReplayable(false);
 setBusy(false);
 planRef.current=null;
 outcomeRef.current=null;
 setPlan(null);
 setOutcome(null);
 setDraft(empty());
 clearConsent();
 },[clearConsent]);
 useEffect(()=>{
  active.current=true;
  let disposed=false,href=window.location.href;
  async function verify(manual=false){
   if(!active.current||document.visibilityState==='hidden'||!matchesUrl(window.location.href,supervisorId))return;
   timer.current.stop();
   controller.current?.abort();
   intent.current.invalidate();
   const c=new AbortController(),rev=++generation.current,target=window.location.href;
   controller.current=c;
   const t=setTimeout(()=>c.abort(),15000);
   const current=()=>!disposed&&active.current&&generation.current===rev&&window.location.href===target&&document.visibilityState!=='hidden';
   try{
    const session=await fetchSession(c.signal);
    if(!current()||c.signal.aborted)return;
    if(session.user_id!==user)throw new AnalysisAccountChanged();
    const recovery=loadCoreRecovery(()=>window.sessionStorage,user,supervisorId);
    const saved=recovery.pending;
    if(!recovery.storageReadable&&!supervisorId)throw new CoreHttpError(503);
    pending.current=saved;
    known.current=supervisorId??saved?.supervisor_id??known.current;
    setReplayable(canReplayCore(known.current,saved));
    setLocked(Boolean(known.current||saved));
    if(saved){draftRef.current=saved.confirm.draft;
    setDraft(saved.confirm.draft);
    }
    if(manual){observation.current.stop();
    setEnded(true);
    }
    if(known.current){
     if(!manual&&observedFlow.current&&!observation.current.permit(performance.now())){setEnded(true);
     setVerified(false);
     return;
     }
     const result=await coreRequest('get',known.current,user,c.signal,current) as Outcome;
     if(!current())return;
     setOutcome(result);
     outcomeRef.current=result;
     if(result.plan){setPlan(result.plan);
     planRef.current=result.plan;
     draftRef.current={original_query:result.plan.frame.original_query,answers:result.plan.frame.answers,revision:result.plan.frame.revision};
     setDraft(draftRef.current);
     }
     if(result.plan_status==='deleted'){setDraft(empty());
     draftRef.current=empty();
     setPlan(null);
     planRef.current=null;
     }
     if(!manual&&result.flow){observedFlow.current=result.flow.analysis_id;
     observation.current.begin(result.flow.analysis_id,performance.now());
     const next=observation.current.next(result.flow,performance.now(),Date.now());
     if(next.kind!=='stop')timer.current.start(current,()=>void verify(),next.delay);
     else if(result.flow.state==='running')setEnded(true);
     }
    }
    if(!current())return;
    verifiedHref.current=target;
    setVerified(true);
    setError(recovery.storageReadable?'':'고정 입력을 읽지 못해 GET-only로 확인합니다. POST 복구는 잠겨 있습니다.');
   }catch(e){if(current()){setVerified(false);
   setError(e instanceof CoreHttpError?e.message:'상태를 확인하지 못했습니다. 같은 ID로 GET 재조회할 수 있습니다.');
   if(requiresReauthentication(e)){invalidate();
   onAccountChange();
   }}}
   finally{clearTimeout(t);
   }
  }
  restore.current=(manual=false)=>void verify(manual);
  const hide=()=>{active.current=false;
  invalidate();
  },show=()=>{if(document.visibilityState==='hidden')return;
  active.current=true;
  void verify();
  },location=()=>{if(href!==window.location.href){href=window.location.href;
  hide();
  }};
  const poll=setInterval(location,200),visibility=()=>document.visibilityState==='hidden'?hide():show();
  window.addEventListener('pagehide',hide);
  window.addEventListener('pageshow',show);
  document.addEventListener('visibilitychange',visibility);
  window.addEventListener('popstate',hide);
  window.addEventListener('hashchange',hide);
  void verify();
  return()=>{disposed=true;
  active.current=false;
  clearInterval(poll);
  restore.current=()=>{};
  invalidate();
  window.removeEventListener('pagehide',hide);
  window.removeEventListener('pageshow',show);
  document.removeEventListener('visibilitychange',visibility);
  window.removeEventListener('popstate',hide);
  window.removeEventListener('hashchange',hide);
  };
 },[user,supervisorId,invalidate,onAccountChange]);
 function edit(next:Draft){if(pending.current||known.current)return;
 generation.current++;
 intent.current.invalidate();
 controller.current?.abort();
 setBusy(false);
 clearConsent();
 planRef.current=null;
 setPlan(null);
 draftRef.current=next;
 setDraft(next);
 }
 async function action(kind:'prepare'|'confirm',nextDraft?:Draft){
  if(!verified||verifiedHref.current!==window.location.href||!active.current||document.visibilityState==='hidden'||!matchesUrl(window.location.href,supervisorId))return;
  if(kind==='prepare'&&(pending.current||known.current))return;
  if(kind==='confirm'&&known.current&&!canReplayCore(known.current,pending.current))return;
  if(kind==='confirm'&&!pending.current){const p=planRef.current,c=consentRef.current;
  if(!p||!['ready','scope_confirmation'].includes(p.status)||!c.allow||p.partial&&!c.partial||p.required_waivers.some(id=>!c.waivers.includes(id)))return;
  }
  const ticket=intent.current.begin();
  if(ticket===null)return;
  const rev=++generation.current,target=window.location.href,c=new AbortController();
  controller.current?.abort();
  controller.current=c;
  setBusy(true);
  setError('');
  timer.current.stop();
  const current=()=>active.current&&rev===generation.current&&intent.current.accepts(ticket)&&window.location.href===target&&verifiedHref.current===target&&document.visibilityState!=='hidden';
  const t=setTimeout(()=>c.abort(),kind==='confirm'?145000:16000);
  try{
   if(kind==='prepare'){
    clearConsent();
    planRef.current=null;
    setPlan(null);
    const value=nextDraft??draftRef.current;
    const result=await coreRequest('prepare',value,user,c.signal,current) as Plan;
    if(!current())return;
    planRef.current=result;
    setPlan(result);
   }else{
    let value=pending.current;
    if(!value){const p=planRef.current!,binding=consentRef.current;
    value=freshPending(draftRef.current,p,binding.partial,binding.waivers);
    writePending(sessionStorage,user,value);
    pending.current=value;
    setReplayable(true);
    setLocked(true);
    }
    const result=await coreRequest('confirm',value.confirm,user,c.signal,current) as Outcome;
    if(!current())return;
    if(value.supervisor_id&&value.supervisor_id!==result.supervisor_id)throw new CoreHttpError(502);
    const saved={...value,supervisor_id:result.supervisor_id};
    writePending(sessionStorage,user,saved);
    pending.current=saved;
    setReplayable(true);
    known.current=result.supervisor_id;
    outcomeRef.current=result;
    setOutcome(result);
    if(result.plan){planRef.current=result.plan;
    setPlan(result.plan);
    }
    router.replace('/research?supervisor_id='+result.supervisor_id);
   }
  }catch(e){if(current()){setError(e instanceof CoreHttpError?e.message:'응답을 확인하지 못했습니다. 확정한 입력과 키는 유지됩니다.');
  if(requiresReauthentication(e)){invalidate();
  onAccountChange();
  }}}
  finally{clearTimeout(t);
  intent.current.finish(ticket);
  if(rev===generation.current)setBusy(false);
  }
 }
 function answer(slot:Answer['slot'],value:string){if(draftRef.current.revision>=4||draftRef.current.answers.length>=8)return;
 const next=clarifiedDraft(draftRef.current,slot,value);
 edit(next);
 void action('prepare',next);
 }
 function startNew(){if(busy)return;
 sessionStorage.removeItem(pendingKey(user));
 window.location.assign('/research');
 }
 if(!verified)return <section className="supervisor-chat"><h1>Supervisor 리서치</h1><p>계정과 요청 상태를 다시 확인해야 합니다. 원문과 결과는 숨겨졌습니다.</p>{error&&<p role="alert">{error}</p>}<button onClick={()=>restore.current(true)}>상태 다시 확인 · GET만</button><button onClick={()=>router.push('/')}>보관함</button></section>;
 return <ChatView draft={draft} plan={plan} outcome={outcome} busy={busy} verified={verified} locked={locked} replayable={replayable} error={error} consent={consent} partialConsent={partial} waivers={waivers} observationEnded={ended} onQuery={q=>edit({original_query:q,answers:[],revision:0})} onPrepare={()=>void action('prepare')} onAnswer={answer} onSelect={ticker=>{const next={...draftRef.current,selected_ticker:ticker,candidate_ref:planRef.current?.candidate_ref};
 edit(next);
 void action('prepare',next);
 }} onConsent={v=>{consentRef.current.allow=v;
 setConsent(v);
 }} onPartial={v=>{consentRef.current.partial=v;
 setPartial(v);
 }} onWaiver={(id,v)=>{const next=v?[...consentRef.current.waivers.filter(x=>x!==id),id]:consentRef.current.waivers.filter(x=>x!==id);
 consentRef.current.waivers=next;
 setWaivers(next);
 }} onConfirm={()=>void action('confirm')} onObserve={()=>restore.current(true)} onNew={startNew} onArchive={()=>router.push('/')}/>;
}
