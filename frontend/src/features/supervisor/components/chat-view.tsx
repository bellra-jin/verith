"use client";
import {conditionLabel,conditionDisposition,clarificationSlot} from '../lib/supervisor-request';
import type {Draft,Plan,Outcome,Answer} from '../model/chat';
export type ChatProps={draft:Draft;
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
 return <section className="supervisor-chat" aria-label="Supervisor 리서치 대화">
  <header className="sc-header"><span className="sc-eyebrow">VERIθ · RESEARCH</span><h1>무엇이 궁금하신가요?</h1><p>질문을 확인하고, 지금 연결된 분석부터 근거와 함께 살펴봅니다.</p><div className="sc-badges"><span>연결됨 · Flow</span><span>차트·재무 · 아직 미연결</span></div></header>
  <div className="sc-thread" aria-live="polite">
   {deleted?<article className="sc-card"><h2>삭제된 결과입니다</h2><p>원질문과 계획·결과를 다시 표시하지 않습니다.</p></article>:<>
    {p.draft.original_query&&<article className="sc-question"><small>내 질문</small><p>{p.draft.original_query}</p></article>}
    {p.draft.answers.map(a=><p className="sc-answer" key={a.answer_id}>확인 답변 · {a.slot}: {a.value}</p>)}
    {p.busy&&<p role="status">요청을 확인 중입니다. 분석 진행률을 추정하지 않습니다.</p>}
    {plan&&<article className="sc-card"><h2>{plan.status==='needs_clarification'?'질문을 조금 더 확인할게요':plan.status==='needs_stock_selection'?'어떤 종목인가요?':'요청 범위와 연결 가능한 분석'}</h2>
      <div className="sc-badges">{plan.requested_views.map(v=><span key={v}>{labels[v]??v}</span>)}</div>
      {plan.frame.unresolved_slots.map(slot=><div className="sc-clarify" key={slot}><label>{['stock','multi_stock'].includes(slot)?'확인할 종목명 또는 코드':slot==='views'?'분석 관점':slot==='scope'?'시장 전체는 미지원입니다. 개별 종목으로 좁히려면 종목명/코드를 입력해 주세요':'범위를 다시 확인해 주세요'}<input name={slot} disabled={p.busy||p.locked||p.draft.revision>=4} placeholder={slot==='views'?'flow 또는 flow,technical':'답변 입력'} onKeyDown={e=>{if(e.key==='Enter'&&e.currentTarget.value.trim())p.onAnswer(clarificationSlot(slot),e.currentTarget.value);
      }}/></label><small>답변 후 Enter · 최대 4회 확인</small></div>)}
      {plan.resolution?.stock&&<p className="sc-stock">{plan.resolution.stock.stock_name} <span>{plan.resolution.stock.stock_code} · {plan.resolution.stock.market??'시장 미확인'}</span></p>}
      {plan.resolution?.status==='ambiguous'&&<div className="sc-candidates">{plan.resolution.candidates.length?plan.resolution.candidates.map(c=><button key={c.stock_code} disabled={p.busy||p.locked} onClick={()=>p.onSelect(c.stock_code)}>{c.stock_name} · {c.stock_code} · {c.market??'미확인'}</button>):<p>선택할 후보가 없습니다. 질문을 구체화해 주세요.</p>}</div>}
      {plan.status==='selection_stale'&&<p>종목 후보 또는 의미가 바뀌었습니다. 새로 확인해 주세요.</p>}
      {plan.status==='not_found'&&<p>등록된 종목을 찾지 못했습니다. 서비스 장애와는 다른 결과입니다.</p>}
      {plan.status==='unsupported'&&<p>요청 관점은 아직 실행할 수 없습니다. Flow로 바꾸어 실행하지 않습니다.</p>}
      {plan.frame.conditions.length>0&&<ul className="sc-conditions">{plan.frame.conditions.map(c=><li key={c.condition_id}><strong>{conditionLabel(c.kind)}: {c.value}</strong> · {conditionDisposition(c.condition_id,c.disposition,p.outcome?.effective_scope??null)}<small>조건 {c.condition_id} · {c.evidence.map(e=>(e.source_kind==='original_query'?'원질문':'확인 답변')+' «'+e.text+'»').join(' / ')}</small>{ready&&!p.locked&&plan.required_waivers.includes(c.condition_id)&&<label><input type="checkbox" disabled={p.busy} checked={p.waivers.includes(c.condition_id)} onChange={e=>p.onWaiver(c.condition_id,e.target.checked)}/> 이 조건을 조정하고 고정 관측창·전체 주체 결과를 받겠습니다</label>}</li>)}</ul>}
      {p.outcome?.effective_scope&&<p>확정 유효 범위: Flow / 고정 관측창 / 전체 주체 유지 · 명시 조정 {p.outcome.effective_scope.waived_conditions.length}건</p>}
      {ready&&!p.locked&&<div className="sc-consent">{plan.partial&&<label><input type="checkbox" checked={p.partialConsent} disabled={p.busy} onChange={e=>p.onPartial(e.target.checked)}/> Flow 부분 범위만 실행하고 미연결 관점은 실행하지 않는 데 동의합니다</label>}<label><input type="checkbox" checked={p.consent} disabled={p.busy} onChange={e=>p.onConsent(e.target.checked)}/> 확인한 계획의 Flow 실행에 동의합니다</label><button className="sc-primary" disabled={!p.verified||p.busy||!p.consent||plan.partial&&!p.partialConsent||plan.required_waivers.some(id=>!p.waivers.includes(id))} onClick={p.onConfirm}>확인한 Flow 실행</button></div>}
     </article>}
    {p.outcome&&<article className="sc-card"><h2>{p.outcome.coverage==='partial'?'부분 결과':p.outcome.coverage==='fulfilled'?'확정 범위 결과':'실행 상태'}</h2>{p.outcome.views.map(v=><p key={v.view}>{labels[v.view]??v.view} · {v.state==='not_executed'?'미연결 · 실행하지 않음':v.state}</p>)}
     {status==='unknown'&&<p>결과가 불명확합니다. 실패·취소 또는 과금 중단을 뜻하지 않습니다. 자동 재실행하지 않습니다.</p>}
     {status==='result_ready'&&<p>결과는 보존됐지만 아직 게시되지 않았습니다. 같은 요청의 명시적 POST로 snapshot만 게시합니다.</p>}
     {status==='stored'&&p.outcome.flow?.report_url&&<a href={p.outcome.flow.report_url}>저장된 본인 Flow 보고서 보기</a>}
     {p.outcome.coverage==='partial'&&<p>Flow 결과만 제공됐습니다. 원질문의 미연결 관점·조정 조건까지 모두 이행했다는 뜻이 아닙니다.</p>}
     {p.outcome.flow&&<p>Flow deadline · {p.outcome.flow.deadline_at}</p>}
    </article>}
   </>}
  </div>
  {p.error&&<p className="sc-error" role="alert">{p.error}</p>}
  {p.locked&&<div className="sc-recovery"><button disabled={p.busy} onClick={p.onObserve}>상태 다시 확인 · GET만</button>{!deleted&&<button disabled={p.busy||!p.verified||!p.replayable||status==='running'||status==='stored'||status==='failed'||status==='unknown'} onClick={p.onConfirm}>같은 확정 요청 확인 · 필요시 snapshot 게시</button>}{!p.replayable&&<p>이 직접 링크에는 고정 확인 입력이 없어 GET-only 조회만 가능합니다. 기존 요청을 새 키로 재구성하지 않습니다.</p>}<p>확정된 원문·조건·키를 유지합니다. GET은 실행하거나 게시하지 않습니다.</p></div>}
  {p.observationEnded&&<p>자동 관측이 끝났습니다. 상태 다시 확인은 계속 사용할 수 있습니다.</p>}
  {!p.locked&&<form className="sc-composer" onSubmit={e=>{e.preventDefault();
  p.onPrepare();
  }}><label htmlFor="sc-query">리서치 질문<textarea id="sc-query" value={p.draft.original_query} maxLength={2000} disabled={p.busy||!p.verified} onChange={e=>p.onQuery(e.target.value)} placeholder="예: 삼성전자 외국인 수급이 요즘 어때?"/></label><button className="sc-primary" disabled={p.busy||!p.verified||!p.draft.original_query.trim()}>질문 확인</button><small>실제 의미 모델은 아직 연결되지 않았습니다. 불명확한 질문은 확인하고 넘어갑니다.</small></form>}
  <footer><button disabled={p.busy} onClick={p.onNew}>명시적으로 새 요청 시작</button><button onClick={p.onArchive}>본인 보관함</button></footer>
 </section>;
}
