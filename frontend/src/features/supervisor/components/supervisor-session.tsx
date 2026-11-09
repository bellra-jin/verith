"use client";
import {useCallback,useEffect,useRef,useState,type ReactNode} from 'react';
import {fetchSession,AnalysisIntent,AnalysisObservation,AnalysisAccountChanged} from '@/features/flow/lib/analysis-request';
import {ChatView} from './chat-view';
import {coreRequest,loadCoreRecovery,writePending,freshPending,pendingKey,matchesUrl,CoreHttpError,legacyFlowRecovery,canReplayCore,requiresReauthentication,CoreObservationTimer,clarifiedDraft,newPreparation,readPreparation,writePreparation,preparationKey,preparationRequest,canAdoptPreparation,bindPreparation,planValue,canResetConversation} from '../lib/supervisor-request';
import type {Draft,Plan,Outcome,Pending,Answer,Preparation,PreparePending} from '../model/chat';
import '../styles/chat.css';
const empty=():Draft=>({original_query:'',answers:[],revision:0});
export type SessionNavigation=(href:string,replace?:boolean)=>void;
export function SupervisorSession({supervisorId,navigate,renderLegacy}:{supervisorId:string|null;navigate:SessionNavigation;renderLegacy:()=>ReactNode}){
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
 if(legacy)return renderLegacy();
 return <Conversation key={user+':'+(supervisorId??'new')} user={user} supervisorId={supervisorId} navigate={navigate} onAccountChange={()=>{setUser(null);
 setRetry(v=>v+1);
 }}/>;
}
function Conversation({user,supervisorId,onAccountChange,navigate}:{user:string;
supervisorId:string|null;
onAccountChange:()=>void;navigate:SessionNavigation}){
 const
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
  [replayable,setReplayable]=useState(false),
  [preparation,setPreparation]=useState<Preparation|null>(null);
 const preparing=useRef<PreparePending|null>(null),preparationRef=useRef<Preparation|null>(null);
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
 preparationRef.current=null;
 setPreparation(null);
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
    if(!known.current&&!saved){
     const prepared=await readPreparation(sessionStorage,user);
     if(!current())return;
     preparing.current=prepared;
     if(prepared){
      draftRef.current=prepared.body.draft;
      setDraft(prepared.body.draft);
      if(prepared.preparation_id){
       const result=await preparationRequest('get',prepared.preparation_id,user,c.signal,current);
       if(result.plan)await planValue(result.plan,prepared.body.draft);
       if(!current())return;
       if(result.state==='consumed'&&result.consumed_binding_id){known.current=result.consumed_binding_id;setLocked(true);setReplayable(false);}
       preparationRef.current=result;
       setPreparation(result);
       planRef.current=result.plan;
       setPlan(result.plan);
      }
     }
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
 async function edit(next:Draft){if(pending.current||known.current)return;
 if(preparing.current&&!await cancelPreparation())return;
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
 async function action(kind:'prepare'|'confirm',nextDraft?:Draft,parentId:string|null=null){
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
    let saved=preparing.current;
    if(nextDraft&&parentId){saved=null;}
    if(!saved){
     saved=await newPreparation(value,parentId);
     if(!current())return;
     await writePreparation(sessionStorage,user,saved);
     if(!current())return;
     preparing.current=saved;
    }
    const result=await preparationRequest(saved.preparation_id?'get':'post',saved.preparation_id??saved.body,user,c.signal,current);
    if(!current())return;
    if(result.plan)await planValue(result.plan,saved.body.draft);
    if(!current())return;
    const updated=await bindPreparation(saved,result.preparation_id);
    await writePreparation(sessionStorage,user,updated);
    if(!current())return;
    preparing.current=updated;
    preparationRef.current=result;
    setPreparation(result);
    draftRef.current=saved.body.draft;
    setDraft(saved.body.draft);
    planRef.current=result.plan;
    setPlan(result.plan);
    if(result.state==='consumed'&&result.consumed_binding_id){known.current=result.consumed_binding_id;setLocked(true);setReplayable(false);navigate('/research?supervisor_id='+result.consumed_binding_id,true);}
   }else{
    let value=pending.current;
    if(!value){const p=planRef.current!,binding=consentRef.current;
    const prepared=preparationRef.current;
    if(p.policy_version==='supervisor.flow-core.2'&&(!canAdoptPreparation(prepared,p)||preparing.current?.preparation_id!==prepared?.preparation_id)){setError('준비 유효기간이 끝났습니다. 준비를 취소한 뒤 명시적으로 새 질문을 확인해 주세요.');clearConsent();return;}
    value=freshPending(draftRef.current,p,binding.partial,binding.waivers,prepared?.preparation_id);
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
    navigate('/research?supervisor_id='+result.supervisor_id,true);
   }
  }catch(e){if(current()){
  if(kind==='confirm'&&e instanceof CoreHttpError&&e.status===409&&['PREPARATION_EXPIRED','PREPARATION_DELETED','PREPARATION_CONSUMED'].includes(e.code)&&!known.current){
   // The server checks binding replay first. This explicit rejection proves first adoption did not create our binding.
   sessionStorage.removeItem(pendingKey(user));
   pending.current=null;
   setLocked(false);
   setReplayable(false);
   clearConsent();
  }
  setError(e instanceof CoreHttpError?e.message:'응답을 확인하지 못했습니다. 확정한 입력과 키는 유지됩니다.');
  if(requiresReauthentication(e)){invalidate();
  onAccountChange();
  }}}
  finally{clearTimeout(t);
  intent.current.finish(ticket);
  if(rev===generation.current)setBusy(false);
  }
 }
 async function answer(slot:Answer['slot'],value:string){if(draftRef.current.revision>=4||draftRef.current.answers.length>=8)return;
 const next=clarifiedDraft(draftRef.current,slot,value);
 await edit(next);
 if(draftRef.current===next)void action('prepare',next);
 }
 async function cancelPreparation(){
  if(pending.current||known.current)return false;
  generation.current++;
  intent.current.invalidate();
  controller.current?.abort();
  timer.current.stop();
  clearConsent();
  planRef.current=null;
  setPlan(null);
  const saved=preparing.current;
  if(!saved)return true;
  if(!saved.preparation_id){setBusy(false);setError('준비 접수 여부가 불명확합니다. 같은 준비 요청으로 확인한 뒤 원문을 삭제할 수 있습니다.');return false;}
  const rev=generation.current,target=window.location.href,c=new AbortController();
  controller.current=c;
  const current=()=>active.current&&generation.current===rev&&window.location.href===target&&document.visibilityState!=='hidden';
  const deadline=setTimeout(()=>c.abort(),16000);
  setBusy(true);
  try{
   const result=await preparationRequest('delete',saved.preparation_id,user,c.signal,current);
   if(!current())return false;
   preparing.current=null;
   preparationRef.current=result;
   setPreparation(result);
   sessionStorage.removeItem(preparationKey(user));
   return true;
  }catch(e){if(current()){setError(e instanceof CoreHttpError?e.message:'준비 삭제를 확인하지 못했습니다. 기존 키를 보존합니다.');if(requiresReauthentication(e)){invalidate();onAccountChange();}}return false;}
  finally{clearTimeout(deadline);if(current())setBusy(false);}
 }
 async function startNew(){if(busy)return;
 if(!canResetConversation(pending.current,known.current,outcomeRef.current)){setError('미확정 실행과 같은 키 복구 입력을 보존합니다. 기존 요청 상태 또는 snapshot 게시를 먼저 확인해 주세요.');return;}
 const completed=Boolean(outcomeRef.current||preparationRef.current?.state==='consumed');
 if(!completed&&preparing.current&&!await cancelPreparation())return;
 generation.current++;
 intent.current.invalidate();
 controller.current?.abort();
 timer.current.stop();
 observation.current=new AnalysisObservation();
 observedFlow.current=null;
 pending.current=null;
 known.current=null;
 preparing.current=null;
 preparationRef.current=null;
 planRef.current=null;
 outcomeRef.current=null;
 draftRef.current=empty();
 sessionStorage.removeItem(pendingKey(user));
 sessionStorage.removeItem(preparationKey(user));
 clearConsent();
 setDraft(empty());setPlan(null);setOutcome(null);setPreparation(null);
 setLocked(false);setReplayable(false);setEnded(false);setError('');
 setVerified(false);verifiedHref.current=null;
 navigate('/research',true);
 if(supervisorId===null)restore.current(true);
 }
 if(!verified)return <section className="supervisor-chat"><h1>Supervisor 리서치</h1><p>계정과 요청 상태를 다시 확인해야 합니다. 원문과 결과는 숨겨졌습니다.</p>{error&&<p role="alert">{error}</p>}<button onClick={()=>restore.current(true)}>상태 다시 확인 · GET만</button><button onClick={()=>navigate('/')}>보관함</button></section>;
 return <ChatView canStartNew={canResetConversation(pending.current,known.current,outcome)} preparation={preparation} onCancelPreparation={()=>void cancelPreparation()} draft={draft} plan={plan} outcome={outcome} busy={busy} verified={verified} locked={locked} replayable={replayable} error={error} consent={consent} partialConsent={partial} waivers={waivers} observationEnded={ended} onQuery={q=>void edit({original_query:q,answers:[],revision:0})} onPrepare={()=>void action('prepare')} onAnswer={(slot,value)=>void answer(slot,value)} onSelect={ticker=>{const next={...draftRef.current,selected_ticker:ticker,candidate_ref:planRef.current?.candidate_ref};
 clearConsent();
 void action('prepare',next,preparationRef.current?.preparation_id??null);
 }} onConsent={v=>{consentRef.current.allow=v;
 setConsent(v);
 }} onPartial={v=>{consentRef.current.partial=v;
 setPartial(v);
 }} onWaiver={(id,v)=>{const next=v?[...consentRef.current.waivers.filter(x=>x!==id),id]:consentRef.current.waivers.filter(x=>x!==id);
 consentRef.current.waivers=next;
 setWaivers(next);
 }} onConfirm={()=>void action('confirm')} onObserve={()=>restore.current(true)} onNew={()=>void startNew()} onArchive={()=>navigate('/')}/>;
}
