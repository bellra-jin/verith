"use client";
import {useState,useEffect,useLayoutEffect,useRef} from 'react';
import {conditionLabel,conditionDisposition,clarificationSlot,meaningLabel} from '../lib/supervisor-request';
import type {Draft,Plan,Outcome,Answer,Preparation} from '../model/chat';
export type ChatProps={canStartNew?:boolean;
verificationPending?:boolean;
onPlanCommit?:(plan:Plan,heading:HTMLHeadingElement)=>void;
onPendingCommit?:()=>void;
preparation?:Preparation|null;
onCancelPreparation?:()=>void;
draft:Draft;
plan:Plan|null;
outcome:Outcome|null;
busy:boolean;
verified:boolean;
locked:boolean;
replayable:boolean;
error:string;
consent:boolean;
partialConsent:boolean;
waivers:string[];
observationEnded:boolean;
onQuery:(v:string)=>void;
onPrepare:()=>void;
onAnswer:(slot:Answer['slot'],value:string)=>void;
onSelect:(ticker:string)=>void;
onConsent:(v:boolean)=>void;
onPartial:(v:boolean)=>void;
onWaiver:(id:string,value:boolean)=>void;
onConfirm:()=>void;
onObserve:()=>void;
onNew:()=>void;onArchive:()=>void};
const labels:Record<string,string>={flow:'수급 · Flow',technical:'차트 · 미연결',fundamental:'재무 · 미연결',macro:'거시 · 후순위',industry:'산업 · 미연결',news:'뉴스 · 제외',overview:'종합 · 범위 확인'};
export function ChatView(p:ChatProps){
 const plan=p.outcome?.plan??p.plan,deleted=p.outcome?.plan_status==='deleted',status=p.outcome?.flow?.state;
 const ready=plan&&['ready','scope_confirmation'].includes(plan.status);
 const blocked=p.busy||Boolean(p.verificationPending),heading=useRef<HTMLHeadingElement|null>(null);
 const {busy,onPendingCommit,onPlanCommit}=p;
 useLayoutEffect(()=>{if(busy)onPendingCommit?.();},[busy,onPendingCommit]);
 useEffect(()=>{if(plan&&heading.current)onPlanCommit?.(plan,heading.current);},[plan,onPlanCommit]);
 return <section className="supervisor-chat" aria-label="Supervisor 리서치 대화" aria-busy={blocked}>
  <header className="sc-header"><span className="sc-eyebrow">VERIθ · RESEARCH</span><h1>무엇이 궁금하신가요?</h1><p>질문을 확인하고, 지금 연결된 분석부터 근거와 함께 살펴봅니다.</p><div className="sc-badges"><span>연결됨 · Flow</span><span>차트·재무 · 아직 미연결</span></div></header>
  <div className="sc-thread" aria-live="polite">
   {p.verificationPending&&<p role="status">상태 확인 중 · 실행 없음</p>}
   {deleted?<article className="sc-card"><h2>삭제된 결과입니다</h2><p>원질문과 계획·결과를 다시 표시하지 않습니다.</p></article>:<>
    {p.draft.original_query&&<article className="sc-question"><small>내 질문</small><p>{p.draft.original_query}</p></article>}
    {p.draft.answers.map(a=><p className="sc-answer" key={a.answer_id}>확인 답변 · {({stock:'종목',views:'분석 관점',flow_focus:'수급 주체',period:'기간',scope:'범위'} as const)[a.slot]}: {a.value}</p>)}
    {p.preparation&&<p className="sc-preparation" role="status">{meaningLabel(p.preparation.meaning_status)} · 첫 채택 <PreparationTime expiresAt={p.preparation.expires_at}/>{p.preparation.state==='consumed'&&<span> 준비가 이미 확정 요청에 연결됐습니다. 기존 요청으로 확인하세요.</span>}</p>}
    {p.busy&&<p role="status">요청을 확인 중입니다. 분석 진행률을 추정하지 않습니다.</p>}
    {plan&&<article className="sc-card"><h2 ref={heading} tabIndex={-1}>{plan.status==='needs_clarification'?'질문을 조금 더 확인할게요':plan.status==='needs_stock_selection'?'어떤 종목인가요?':'요청 범위와 연결 가능한 분석'}</h2>
      <div className="sc-badges">{plan.requested_views.map(v=><span key={v}>{labels[v]??v}</span>)}</div>
      {plan.frame.unresolved_slots.map(slot=>slot==='meaning'?<p key={slot}>현재 정책으로 남은 의미를 확정할 수 없습니다. 원질문을 구체적으로 편집해 주세요. 답변 반복으로 이 장벽을 없애지 않습니다.</p>:<Clarification key={slot} slot={slot} disabled={blocked||p.locked||p.draft.revision>=4} onAnswer={value=>p.onAnswer(slot==='scope'&&plan.policy_version==='supervisor.flow-core.2'?'scope':clarificationSlot(slot),value)}/>)}
      {plan.resolution?.stock&&<p className="sc-stock">{plan.resolution.stock.stock_name} <span>{plan.resolution.stock.stock_code} · {plan.resolution.stock.market??'시장 미확인'}</span></p>}
      {plan.resolution?.status==='ambiguous'&&<div className="sc-candidates">{plan.resolution.candidates.length?plan.resolution.candidates.map(c=><button key={c.stock_code} disabled={blocked||p.locked} onClick={()=>p.onSelect(c.stock_code)}>{c.stock_name} · {c.stock_code} · {c.market??'미확인'}</button>):<p>선택할 후보가 없습니다. 질문을 구체화해 주세요.</p>}</div>}
      {plan.status==='selection_stale'&&<p>종목 후보 또는 의미가 바뀌었습니다. 새로 확인해 주세요.</p>}
      {plan.status==='not_found'&&<p>등록된 종목을 찾지 못했습니다. 서비스 장애와는 다른 결과입니다.</p>}
      {plan.status==='unsupported'&&<p>요청 관점은 아직 실행할 수 없습니다. Flow로 바꾸어 실행하지 않습니다.</p>}
      {plan.frame.conditions.length>0&&<ul className="sc-conditions">{plan.frame.conditions.map(c=><li key={c.condition_id}><strong>{conditionLabel(c.kind)}: {c.value}</strong> · {conditionDisposition(c.condition_id,c.disposition,p.outcome?.effective_scope??null)}<small>조건 {c.condition_id} · {c.evidence.map(e=>(e.source_kind==='original_query'?'원질문':'확인 답변')+' «'+e.text+'»').join(' / ')}</small>{ready&&!p.locked&&plan.required_waivers.includes(c.condition_id)&&<label><input type="checkbox" disabled={blocked} checked={p.waivers.includes(c.condition_id)} onChange={e=>p.onWaiver(c.condition_id,e.target.checked)}/> 이 조건을 조정하고 고정 관측창·전체 주체 결과를 받겠습니다</label>}</li>)}</ul>}
      {p.outcome?.effective_scope&&<p>확정 유효 범위: Flow / 고정 관측창 / 전체 주체 유지 · 명시 조정 {p.outcome.effective_scope.waived_conditions.length}건</p>}
      {ready&&!p.locked&&<div className="sc-consent">{plan.partial&&<label><input type="checkbox" checked={p.partialConsent} disabled={blocked} onChange={e=>p.onPartial(e.target.checked)}/> Flow 부분 범위만 실행하고 미연결 관점은 실행하지 않는 데 동의합니다</label>}<label><input type="checkbox" checked={p.consent} disabled={blocked} onChange={e=>p.onConsent(e.target.checked)}/> 확인한 계획의 Flow 실행에 동의합니다</label><button className="sc-primary" disabled={!p.verified||blocked||!p.consent||plan.partial&&!p.partialConsent||plan.required_waivers.some(id=>!p.waivers.includes(id))} onClick={p.onConfirm}>확인한 Flow 실행</button></div>}
     </article>}
    {p.outcome&&<article className="sc-card"><h2>{p.outcome.coverage==='partial'?'부분 결과':p.outcome.coverage==='fulfilled'?'확정 범위 결과':'실행 상태'}</h2>{p.outcome.views.map(v=><p key={v.view}>{labels[v.view]??v.view} · {({not_executed:'미연결 · 실행하지 않음',not_admitted:'접수 전',running:'실행 중',result_ready:'결과 보존 · 게시 대기',stored:'저장됨',failed:'실패',unknown:'상태 불명',deleted:'삭제됨'} as Record<string,string>)[v.state]??'상태 확인 필요'}</p>)}
     {status==='unknown'&&<p>결과가 불명확합니다. 실패·취소 또는 과금 중단을 뜻하지 않습니다. 자동 재실행하지 않습니다.</p>}
     {status==='result_ready'&&<p>결과는 보존됐지만 아직 게시되지 않았습니다. 같은 요청의 명시적 POST로 snapshot만 게시합니다.</p>}
     {status==='stored'&&p.outcome.flow?.report_url&&<a href={p.outcome.flow.report_url}>저장된 본인 Flow 보고서 보기</a>}
     {p.outcome.coverage==='partial'&&<p>Flow 결과만 제공됐습니다. 원질문의 미연결 관점·조정 조건까지 모두 이행했다는 뜻이 아닙니다.</p>}
     {p.outcome.flow&&<p>Flow deadline · {new Date(p.outcome.flow.deadline_at).toLocaleString('ko-KR')}</p>}
    </article>}
   </>}
  </div>
  {p.error&&<p className="sc-error" role="alert">{p.error}</p>}
  {p.locked&&<div className="sc-recovery"><button disabled={blocked} onClick={p.onObserve}>상태 다시 확인 · GET만</button>{!deleted&&<button disabled={blocked||!p.verified||!p.replayable||status==='running'||status==='stored'||status==='failed'||status==='unknown'} onClick={p.onConfirm}>같은 확정 요청 확인 · 필요시 snapshot 게시</button>}{!p.replayable&&<p>이 직접 링크에는 고정 확인 입력이 없어 GET-only 조회만 가능합니다. 기존 요청을 새 키로 재구성하지 않습니다.</p>}<p>확정된 원문·조건·키를 유지합니다. GET은 실행하거나 게시하지 않습니다.</p></div>}
  {p.observationEnded&&<p>자동 관측이 끝났습니다. 상태 다시 확인은 계속 사용할 수 있습니다.</p>}
  {!p.locked&&<form className="sc-composer" onSubmit={e=>{e.preventDefault();
  p.onPrepare();
  }}><label htmlFor="sc-query">리서치 질문<textarea id="sc-query" value={p.draft.original_query} maxLength={2000} disabled={blocked||!p.verified} onChange={e=>p.onQuery(e.target.value)} placeholder="예: 삼성전자 외국인 수급이 요즘 어때?"/></label><button className="sc-primary" disabled={blocked||!p.verified||!p.draft.original_query.trim()}>질문 확인</button><small>의미 보완은 근거와 비용 경계가 확인될 때만 사용합니다. 현재 운영 gateway는 닫혀 있으며, 미확정 의미는 확인합니다.</small></form>}
  {!p.locked&&p.preparation&&!['deleted','consumed'].includes(p.preparation.state)&&<button className="sc-cancel" disabled={blocked} onClick={p.onCancelPreparation}>확인 전 준비 취소 · 원문 삭제</button>}
  <footer>{p.canStartNew===false&&<p>미확정 요청의 키와 복구 입력을 보존합니다. 기존 요청을 먼저 확인해 주세요.</p>}<button disabled={blocked||p.canStartNew===false} onClick={p.onNew}>명시적으로 새 요청 시작</button><button onClick={p.onArchive}>본인 보관함</button></footer>
 </section>;
}

function Clarification({slot,disabled,onAnswer}:{slot:string;disabled:boolean;onAnswer:(value:string)=>void}){
 const [value,setValue]=useState('');
 const submit=()=>{if(!disabled&&value.trim())onAnswer(value);};
 return <form className="sc-clarify" onSubmit={e=>{e.preventDefault();submit();}}>
  <label>{['stock','multi_stock'].includes(slot)?'확인할 한 종목':slot==='views'?'분석 관점':slot==='scope'?'명시적으로 좁힐 범위':'확인할 조건'}
  <input name={slot} value={value} disabled={disabled} placeholder={slot==='views'?'예: 수급만':slot==='scope'?'예: 선택한 한 종목만':'답변 입력'} onChange={e=>setValue(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&(e.nativeEvent.isComposing||e.keyCode===229))e.preventDefault();}}/>
  </label><button type="submit" disabled={disabled||!value.trim()}>답변 확인</button><small>최대 4회 확인 · 원조건의 제외·기간은 유지합니다.</small>
 </form>;
}

function PreparationTime({expiresAt}:{expiresAt:string}){
 const [now,setNow]=useState(()=>Date.now());
 useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[expiresAt]);
 const seconds=Math.max(0,Math.ceil((Date.parse(expiresAt)-now)/1000));
 return <span>{seconds===0?'유효기간 종료':'남은 시간 약 '+Math.max(1,Math.ceil(seconds/60))+'분'}</span>;
}
