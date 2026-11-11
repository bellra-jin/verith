"use client";
import {useCallback,useEffect,useRef,useState,type ReactNode} from 'react';
import {fetchSession,AnalysisIntent,AnalysisObservation,AnalysisAccountChanged} from '@/features/flow/lib/analysis-request';
import {ChatView} from './chat-view';
import {coreRequest,loadCoreRecovery,writePending,freshPending,pendingKey,matchesUrl,CoreHttpError,legacyFlowRecovery,canReplayCore,requiresReauthentication,CoreObservationTimer,clarifiedDraft,newPreparation,readPreparation,writePreparation,preparationKey,preparationRequest,canAdoptPreparation,bindPreparation,planValue,canResetConversation,hash} from '../lib/supervisor-request';
import type {Draft,Plan,Outcome,Pending,Answer,Preparation,PreparePending} from '../model/chat';
import '../styles/chat.css';
const empty=():Draft=>({original_query:'',answers:[],revision:0});
export type SessionNavigation=(href:string,replace?:boolean)=>void;
const reauthenticationKey='verith.supervisor.reauthentication.v1';
let tabReauthenticationRequired=false;
const verifiedOwnerKey='verith.supervisor.verified-owner.v1';
let tabVerifiedOwnerFingerprint:string|null=null;
function previousVerifiedOwner(){
 try{
  const stored=sessionStorage.getItem(verifiedOwnerKey);
  if(stored!==null&&!/^[0-9a-f]{64}$/.test(stored))return 'unavailable';
  if(tabVerifiedOwnerFingerprint!==null&&stored!==null&&stored!==tabVerifiedOwnerFingerprint)return 'unavailable';
  return tabVerifiedOwnerFingerprint??stored;
 }catch{return 'unavailable';}
}
function rememberVerifiedOwner(fingerprint:string){
 if(!/^[0-9a-f]{64}$/.test(fingerprint))return false;
 try{sessionStorage.setItem(verifiedOwnerKey,fingerprint);tabVerifiedOwnerFingerprint=fingerprint;return true;}catch{return false;}
}

export function storedReauthenticationRequired(read:()=>string|null){
 try{return read()!==null;}catch{return true;}
}
function requiresExplicitReauthentication(){
 return tabReauthenticationRequired||storedReauthenticationRequired(()=>sessionStorage.getItem(reauthenticationKey));
}
function requireReauthentication(){
 tabReauthenticationRequired=true;
 try{sessionStorage.setItem(reauthenticationKey,'required');}catch{/* Memory remains closed if storage is unavailable. */}
}
function acknowledgeReauthentication(){
 try{sessionStorage.removeItem(reauthenticationKey);tabReauthenticationRequired=false;}catch{tabReauthenticationRequired=true;}
}
export function acceptsSessionGeneration(expected:number,actual:number,mounted:boolean,href:string,currentHref:string,visible:boolean){
 return expected===actual&&mounted&&href===currentHref&&visible;
}
type VerificationToken={owner:string;href:string;generation:number;controller:AbortController};
export class ConversationVerification {
 private token:VerificationToken|null=null;
 get pending(){return this.token!==null;}
 begin(token:VerificationToken){if(this.token)return false;this.token=token;return true;}
 accepts(token:VerificationToken){return this.token===token;}
 finish(token:VerificationToken){if(!this.accepts(token))return false;this.token=null;return true;}
 invalidate(){this.token?.controller.abort();this.token=null;}
}
type FocusRequest={generation:number;owner:string;href:string;origin:HTMLElement;planHash:string|null;pendingBody:boolean};
export class PlanFocusIntent {
 private request:FocusRequest|null=null;
 begin(generation:number,owner:string,href:string,origin:HTMLElement|null,body:HTMLElement){
  this.request=origin&&origin!==body?{generation,owner,href,origin,planHash:null,pendingBody:false}:null;
 }
 invalidate(){this.request=null;}
 moved(target:EventTarget|null,body:HTMLElement){
  const request=this.request;
  if(!request||target===request.origin)return;
  // Disabled/removed origin is a known consequence of our pending render.
  if(target===body&&(request.pendingBody||!request.origin.isConnected||request.origin.matches(':disabled'))){request.pendingBody=true;return;}
  this.invalidate();
 }
 adopt(planHash:string){if(this.request)this.request.planHash=planHash;}
 pendingCommit(current:Element|null,body:HTMLElement){
  const request=this.request;
  // Native blur can happen after the pending commit without a body focusin.
  // Preserve only the observed disabled/removed origin, never an arbitrary body/HTML.
  if(request&&(current===request.origin||current===body)&&(!request.origin.isConnected||request.origin.matches(':disabled')))request.pendingBody=true;
 }
 consume(planHash:string,generation:number,owner:string,href:string,current:Element|null,body:HTMLElement){
  const request=this.request;this.request=null;
  return Boolean(request&&request.planHash===planHash&&request.generation===generation&&request.owner===owner&&request.href===href&&
   (current===request.origin||current===body&&(request.pendingBody||!request.origin.isConnected||request.origin.matches(':disabled'))));
 }
}
export function SupervisorSession({supervisorId,navigate,renderLegacy}:{supervisorId:string|null;navigate:SessionNavigation;renderLegacy:()=>ReactNode}){
 const [grant,setGrant]=useState<{user:string;epoch:number;route:string|null;href:string;legacy:boolean;manual:boolean}|null>(null);
 const [checking,setChecking]=useState(false);
 const mounted=useRef(false),generation=useRef(0),lock=useRef(false);
 const controller=useRef<AbortController|null>(null),deadline=useRef<ReturnType<typeof setTimeout>|null>(null);
 const owner=useRef<string|null>(null),authHref=useRef<string|null>(null),ownerFingerprint=useRef<string|null>(null);
 const retire=useCallback(()=>{
  generation.current++;
  controller.current?.abort();controller.current=null;
  if(deadline.current!==null)clearTimeout(deadline.current);
  deadline.current=null;lock.current=false;owner.current=null;authHref.current=null;ownerFingerprint.current=null;
 },[]);
 const pause=useCallback(()=>{retire();setGrant(null);setChecking(false);},[retire]);
 const onAccountChange=useCallback((user:string,epoch:number)=>{
  if(!mounted.current||epoch!==generation.current||owner.current!==user||authHref.current!==window.location.href)return;
  requireReauthentication();pause();
 },[pause]);
 const onVerified=useCallback((user:string,epoch:number)=>{
  if(!mounted.current||epoch!==generation.current||owner.current!==user||authHref.current!==window.location.href)return;
  if(!ownerFingerprint.current||!rememberVerifiedOwner(ownerFingerprint.current)){requireReauthentication();pause();return;}
  if(deadline.current!==null)clearTimeout(deadline.current);
  deadline.current=null;lock.current=false;setChecking(false);
  acknowledgeReauthentication();
 },[pause]);
 const onVerificationFailed=useCallback((user:string,epoch:number)=>{
  if(lock.current&&mounted.current&&epoch===generation.current&&owner.current===user&&authHref.current===window.location.href){requireReauthentication();pause();}
 },[pause]);
 const checkSession=useCallback(async(manual=false)=>{
  if(lock.current||!mounted.current||document.visibilityState==='hidden'||!matchesUrl(window.location.href,supervisorId))return;
  if(!manual&&requiresExplicitReauthentication()){setGrant(null);return;}
  retire();lock.current=true;setChecking(true);setGrant(null);
  const epoch=generation.current,href=window.location.href,c=new AbortController();controller.current=c;authHref.current=href;
  const current=()=>acceptsSessionGeneration(epoch,generation.current,mounted.current,href,window.location.href,document.visibilityState!=='hidden')&&!c.signal.aborted;
  // One explicit recovery is bounded across parent authentication and child GET verification.
  deadline.current=setTimeout(()=>{if(current()){requireReauthentication();pause();}},15000);
  try{
   const session=await fetchSession(c.signal);
   if(!current())return;
   const fingerprint=await hash(session.user_id);
   if(!current())return;
   const previous=previousVerifiedOwner();
   if(!manual&&(previous==='unavailable'||previous!==null&&previous!==fingerprint)){requireReauthentication();pause();return;}
   const legacy=supervisorId===null&&legacyFlowRecovery(sessionStorage,session.user_id,null);
   if(!current())return;
   owner.current=session.user_id;ownerFingerprint.current=fingerprint;
   setGrant({user:session.user_id,epoch,route:supervisorId,href,legacy,manual});
   if(legacy){if(!rememberVerifiedOwner(fingerprint)){requireReauthentication();pause();return;}if(deadline.current!==null)clearTimeout(deadline.current);deadline.current=null;lock.current=false;setChecking(false);acknowledgeReauthentication();}
  }catch{if(current()){requireReauthentication();pause();}}
 },[supervisorId,retire,pause]);
 useEffect(()=>{
  mounted.current=true;let href=window.location.href;
  const hide=()=>pause();
  const show=()=>{if(document.visibilityState!=='hidden')void checkSession();};
  const changed=()=>{if(href!==window.location.href){href=window.location.href;pause();}};
  const visibility=()=>document.visibilityState==='hidden'?hide():show();
  const poll=setInterval(changed,200);
  window.addEventListener('pagehide',hide);window.addEventListener('pageshow',show);
  window.addEventListener('popstate',changed);window.addEventListener('hashchange',changed);
  document.addEventListener('visibilitychange',visibility);
  const initialGeneration=generation.current;
  // Start after commit; an intervening hide/new attempt/unmount invalidates this startup.
  void Promise.resolve().then(()=>{if(mounted.current&&generation.current===initialGeneration)void checkSession();});
  return()=>{mounted.current=false;retire();clearInterval(poll);
   window.removeEventListener('pagehide',hide);window.removeEventListener('pageshow',show);
   window.removeEventListener('popstate',changed);window.removeEventListener('hashchange',changed);
   document.removeEventListener('visibilitychange',visibility);
  };
 },[checkSession,pause,retire]);
 if(!grant||grant.route!==supervisorId||grant.href!==window.location.href)return <section className="supervisor-chat"><h1>Supervisor 리서치</h1><p>로그인 상태를 확인한 뒤 질문을 보여드립니다. 재인증이 필요하면 직접 다시 확인해 주세요.</p><button disabled={checking} onClick={()=>void checkSession(true)}>{checking?'로그인과 요청 상태 확인 중':'로그인 상태 다시 확인'}</button><button onClick={()=>window.location.assign('/api/auth/login')}>로그인</button></section>;
 if(grant.legacy)return renderLegacy();
 return <Conversation key={grant.user+':'+(supervisorId??'new')+':'+grant.epoch} user={grant.user} authEpoch={grant.epoch} rechecking={checking} manualRecovery={grant.manual} supervisorId={supervisorId} navigate={navigate} onAccountChange={onAccountChange} onVerified={onVerified} onVerificationFailed={onVerificationFailed}/>;
}
function Conversation({user,authEpoch,rechecking,manualRecovery,supervisorId,onAccountChange,onVerified,onVerificationFailed,navigate}:{user:string;authEpoch:number;rechecking:boolean;manualRecovery:boolean;
supervisorId:string|null;
onAccountChange:(user:string,epoch:number)=>void;onVerified:(user:string,epoch:number)=>void;onVerificationFailed:(user:string,epoch:number)=>void;navigate:SessionNavigation}){
 const
  [draft,setDraft]=useState<Draft>(empty),
  [plan,setPlan]=useState<Plan|null>(null),
  [outcome,setOutcome]=useState<Outcome|null>(null),
  [busy,setBusy]=useState(false),
  [verificationPending,setVerificationPending]=useState(false),
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
 const observedFlow=useRef<string|null>(null),automaticObservationStarted=useRef(false);
 const restore=useRef<(manual?:boolean)=>void>(()=>{});
 const verification=useRef(new ConversationVerification()),planFocus=useRef(new PlanFocusIntent());
 const commandPending=useRef(false),focusMovement=useRef(0);
 const clearConsent=useCallback(()=>{consentRef.current={allow:false,partial:false,waivers:[]};
 setConsent(false);
 setPartial(false);
 setWaivers([]);
 },[]);
 const invalidate=useCallback(()=>{generation.current++;
 verification.current.invalidate();
 planFocus.current.invalidate();
 setVerificationPending(false);
 commandPending.current=false;
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
   if(verification.current.pending||commandPending.current||!active.current||document.visibilityState==='hidden'||!matchesUrl(window.location.href,supervisorId))return;
   const c=new AbortController(),rev=generation.current+1,target=window.location.href;
   const token={owner:user,href:target,generation:rev,controller:c};
   if(!verification.current.begin(token))return;
   setVerificationPending(true);
   planFocus.current.invalidate();
   timer.current.stop();
   controller.current?.abort();
   intent.current.invalidate();
   generation.current=rev;
   controller.current=c;
   const t=setTimeout(()=>c.abort(),15000);
   const contextCurrent=()=>!disposed&&active.current&&generation.current===rev&&window.location.href===target&&document.visibilityState!=='hidden';
   const current=()=>verification.current.accepts(token)&&contextCurrent();
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
    if(manual&&automaticObservationStarted.current){observation.current.stop();
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
     if(next.kind!=='stop'){automaticObservationStarted.current=true;timer.current.start(contextCurrent,()=>void verify(),next.delay);}
     else if(result.flow.state==='running')setEnded(true);
     }
    }
    if(!current())return;
    verifiedHref.current=target;
    setVerified(true);
    onVerified(user,authEpoch);
    setError(recovery.storageReadable?'':'고정 입력을 읽지 못해 GET-only로 확인합니다. POST 복구는 잠겨 있습니다.');
   }catch(e){if(current()){setVerified(false);
   setError(e instanceof CoreHttpError?e.message:'상태를 확인하지 못했습니다. 같은 ID로 GET 재조회할 수 있습니다.');
   if(requiresReauthentication(e)){invalidate();
   onAccountChange(user,authEpoch);
   }else onVerificationFailed(user,authEpoch);}}
   finally{clearTimeout(t);
    if(verification.current.finish(token))setVerificationPending(false);
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
  void verify(manualRecovery);
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
 },[user,authEpoch,supervisorId,manualRecovery,invalidate,onAccountChange,onVerified,onVerificationFailed]);
 useEffect(()=>{
  const focusIntent=planFocus.current;
  const key=(event:KeyboardEvent)=>{if(event.key==='Tab'){focusMovement.current++;focusIntent.invalidate();}};
  const pointer=()=>{focusMovement.current++;focusIntent.invalidate();};
  const focus=(event:FocusEvent)=>{if(event.target!==document.body)focusMovement.current++;focusIntent.moved(event.target,document.body);};
  document.addEventListener('keydown',key,true);
  document.addEventListener('pointerdown',pointer,true);
  document.addEventListener('focusin',focus,true);
  window.addEventListener('blur',pointer);
  return()=>{focusIntent.invalidate();document.removeEventListener('keydown',key,true);document.removeEventListener('pointerdown',pointer,true);document.removeEventListener('focusin',focus,true);window.removeEventListener('blur',pointer);};
 },[]);
 const onPlanCommit=useCallback((value:Plan,heading:HTMLHeadingElement)=>{
  if(!active.current||document.visibilityState==='hidden'||!document.hasFocus()||verifiedHref.current!==window.location.href||!matchesUrl(window.location.href,supervisorId)||planRef.current!==value){planFocus.current.invalidate();return;}
  if(planFocus.current.consume(value.plan_hash,generation.current,user,window.location.href,document.activeElement,document.body))heading.focus({preventScroll:true});
 },[user,supervisorId]);
 const onPendingCommit=useCallback(()=>planFocus.current.pendingCommit(document.activeElement,document.body),[]);
 async function edit(next:Draft){if(verification.current.pending||pending.current||known.current)return;
 planFocus.current.invalidate();
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
 async function action(kind:'prepare'|'confirm',nextDraft?:Draft,parentId:string|null=null,focusStart?:{origin:HTMLElement|null;movement:number}){
  if(verification.current.pending)return;
  if(!verified||verifiedHref.current!==window.location.href||!active.current||document.visibilityState==='hidden'||!matchesUrl(window.location.href,supervisorId))return;
  if(kind==='prepare'&&(pending.current||known.current))return;
  if(kind==='confirm'&&known.current&&!canReplayCore(known.current,pending.current))return;
  if(kind==='confirm'&&!pending.current){const p=planRef.current,c=consentRef.current;
  if(!p||!['ready','scope_confirmation'].includes(p.status)||!c.allow||p.partial&&!c.partial||p.required_waivers.some(id=>!c.waivers.includes(id)))return;
  }
  const selectedPreparation=kind==='prepare'&&!(nextDraft&&parentId)?preparing.current:null;
  const preparationMethod=selectedPreparation?.preparation_id?'get':'post';
  const ticket=intent.current.begin();
  if(ticket===null)return;
  const rev=++generation.current,target=window.location.href,c=new AbortController();
  const previousPlanHash=planRef.current?.plan_hash;
  planFocus.current.invalidate();
  if(kind==='prepare'&&(!focusStart||focusStart.movement===focusMovement.current))planFocus.current.begin(rev,user,target,focusStart?focusStart.origin:document.activeElement instanceof HTMLElement?document.activeElement:null,document.body);
  commandPending.current=true;
  controller.current?.abort();
  controller.current=c;
  setBusy(true);
  setError('');
  timer.current.stop();
  const sameContext=()=>active.current&&rev===generation.current&&intent.current.accepts(ticket)&&window.location.href===target&&verifiedHref.current===target&&document.visibilityState!=='hidden';
  const current=()=>sameContext()&&!c.signal.aborted;
  const t=setTimeout(()=>{
   c.abort();
   if(sameContext()){
    planFocus.current.invalidate();
    setError('응답을 확인하지 못했습니다. 확정한 입력과 키는 유지됩니다.');
    intent.current.finish(ticket);
    commandPending.current=false;setBusy(false);
   }
  },kind==='confirm'?145000:preparationMethod==='post'?130000:16000);
  try{
   if(kind==='prepare'){
    clearConsent();
    planRef.current=null;
    setPlan(null);
    const value=nextDraft??draftRef.current;
    let saved=selectedPreparation;
    if(!saved){
     saved=await newPreparation(value,parentId);
     if(!current())return;
     await writePreparation(sessionStorage,user,saved,current);
     if(!current())return;
     preparing.current=saved;
    }
    if((saved.preparation_id?'get':'post')!==preparationMethod)throw new CoreHttpError(409);
    const result=await preparationRequest(preparationMethod,saved.preparation_id??saved.body,user,c.signal,current);
    if(!current())return;
    if(result.plan)await planValue(result.plan,saved.body.draft);
    if(!current())return;
    const updated=await bindPreparation(saved,result.preparation_id);
    if(!current())return;
    await writePreparation(sessionStorage,user,updated,current);
    if(!current())return;
    preparing.current=updated;
    preparationRef.current=result;
    setPreparation(result);
    draftRef.current=saved.body.draft;
    setDraft(saved.body.draft);
    planRef.current=result.plan;
    if(result.plan&&result.plan.plan_hash!==previousPlanHash&&result.state!=='consumed')planFocus.current.adopt(result.plan.plan_hash);
    else planFocus.current.invalidate();
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
  }catch(e){if(sameContext()){
  planFocus.current.invalidate();
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
  onAccountChange(user,authEpoch);
  }}}
  finally{clearTimeout(t);
  const ownsPending=rev===generation.current&&intent.current.accepts(ticket);
  intent.current.finish(ticket);
  if(ownsPending){commandPending.current=false;setBusy(false);}
  }
 }
 async function answer(slot:Answer['slot'],value:string){if(verification.current.pending||draftRef.current.revision>=4||draftRef.current.answers.length>=8)return;
 const focusStart={origin:document.activeElement instanceof HTMLElement?document.activeElement:null,movement:focusMovement.current};
 const next=clarifiedDraft(draftRef.current,slot,value);
 await edit(next);
 if(draftRef.current===next)void action('prepare',next,null,focusStart);
 }
 async function cancelPreparation(){
  if(verification.current.pending||pending.current||known.current)return false;
  planFocus.current.invalidate();
  generation.current++;
  commandPending.current=false;
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
  commandPending.current=true;
  setBusy(true);
  try{
   const result=await preparationRequest('delete',saved.preparation_id,user,c.signal,current);
   if(!current())return false;
   preparing.current=null;
   preparationRef.current=result;
   setPreparation(result);
   sessionStorage.removeItem(preparationKey(user));
   return true;
  }catch(e){if(current()){setError(e instanceof CoreHttpError?e.message:'준비 삭제를 확인하지 못했습니다. 기존 키를 보존합니다.');if(requiresReauthentication(e)){invalidate();onAccountChange(user,authEpoch);}}return false;}
  finally{clearTimeout(deadline);if(current()){commandPending.current=false;setBusy(false);}}
 }
 async function startNew(){if(verification.current.pending||busy)return;
 planFocus.current.invalidate();
 if(!canResetConversation(pending.current,known.current,outcomeRef.current)){setError('미확정 실행과 같은 키 복구 입력을 보존합니다. 기존 요청 상태 또는 snapshot 게시를 먼저 확인해 주세요.');return;}
 const completed=Boolean(outcomeRef.current||preparationRef.current?.state==='consumed');
 if(!completed&&preparing.current&&!await cancelPreparation())return;
 generation.current++;
 intent.current.invalidate();
 controller.current?.abort();
 timer.current.stop();
 observation.current=new AnalysisObservation();
 observedFlow.current=null;
 automaticObservationStarted.current=false;
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
 if(!verified)return <section className="supervisor-chat" aria-busy={verificationPending}><h1>Supervisor 리서치</h1><p>계정과 요청 상태를 다시 확인해야 합니다. 원문과 결과는 숨겨졌습니다.</p>{error&&<p role="alert">{error}</p>}{verificationPending&&<p role="status">상태 확인 중 · 실행 없음</p>}<button disabled={rechecking||verificationPending} onClick={()=>restore.current(true)}>상태 다시 확인 · GET만</button><button onClick={()=>navigate('/')}>보관함</button></section>;
 return <ChatView onPendingCommit={onPendingCommit} onPlanCommit={onPlanCommit} verificationPending={verificationPending} canStartNew={canResetConversation(pending.current,known.current,outcome)} preparation={preparation} onCancelPreparation={()=>void cancelPreparation()} draft={draft} plan={plan} outcome={outcome} busy={busy} verified={verified} locked={locked} replayable={replayable} error={error} consent={consent} partialConsent={partial} waivers={waivers} observationEnded={ended} onQuery={q=>void edit({original_query:q,answers:[],revision:0})} onPrepare={()=>void action('prepare')} onAnswer={(slot,value)=>void answer(slot,value)} onSelect={ticker=>{if(verification.current.pending)return;const next={...draftRef.current,selected_ticker:ticker,candidate_ref:planRef.current?.candidate_ref};
 clearConsent();
 void action('prepare',next,preparationRef.current?.preparation_id??null);
 }} onConsent={v=>{if(verification.current.pending)return;consentRef.current.allow=v;
 setConsent(v);
 }} onPartial={v=>{if(verification.current.pending)return;consentRef.current.partial=v;
 setPartial(v);
 }} onWaiver={(id,v)=>{if(verification.current.pending)return;const next=v?[...consentRef.current.waivers.filter(x=>x!==id),id]:consentRef.current.waivers.filter(x=>x!==id);
 consentRef.current.waivers=next;
 setWaivers(next);
 }} onConfirm={()=>void action('confirm')} onObserve={()=>restore.current(true)} onNew={()=>void startNew()} onArchive={()=>navigate('/')}/>;
}
