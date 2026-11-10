# Supervisor core v1

`supervisor.core.v1` / policy `supervisor.flow-core.1`의 공통 계약 정본이다. 기존 [Flow 분석](flow-analysis-v1.md)과 [usage](flow-usage-v1.md), Fundamental wire·fingerprint·저장 snapshot은 바꾸지 않는다.

## 의미와 계획

`MeaningFrame`은 불변 원질문/hash, active·negated 종목 mention과 정확한 evidence span, requested·negated views, typed 조건, unresolved slots, 최대4 revision/8 typed clarification answers와 해석 출처를 보존한다. 답변 evidence는 원문이 아닌 해당 answer ID/텍스트의 offset이다. 모델 제안은 검증 대상이며 canonical 종목·권한·capability의 근거가 아니다. 명시 종목·부정·기간 조건을 설명 없이 제거한 제안은 채택하지 않는다.

결정론 경로는 제한된 명시 표현만 처리한다. production meaning gateway는 unavailable이며 typed fake로만 검증한다. 실제 모델 품질·일반 NLU·완료된 대화 기억을 보장하지 않는다. 정보 부족은 명확화하고 다중 종목·시장 전체는 단일 Flow로 임의 축소하지 않는다.

`Plan`은 요청 관점, 연결 capability, 선택 관점을 구분한다. 현재 실행은 Flow 하나다. Technical·재무·거시·News의 실행을 열지 않는다. 고정 관측창·모든 주체를 유지하는 Flow가 이행하지 못하는 주체 focus/제외·과거 cutoff·기간 조건은 원조건으로 남긴다. `required_waivers`의 조건 ID와 부분 범위에 별도 명시 동의해야 한다. 확정 snapshot 및 Outcome의 `effective_scope`는 실제 동의한 고정 관측창/주체 유지/waiver를 원조건과 함께 추적한다.

semantic plan hash는 정렬된 finite JSON의 SHA-256이다. 원문/답변/revision·canonical resolution/ref·조건·policy·capability·선택을 포함하고 transport ID·준비 시각·미배정 Flow as_of는 포함하지 않는다. stock master 변경으로 첫 확정 계획이 달라지면 stale 재확인하며, 기존 binding replay는 최초 admission snapshot을 유지한다.

## HTTP 경계

| 경로 | 동작 |
|---|---|
| POST `/api/supervisor/core/prepare` | 비영속 의미 확인→필요할 때 canonical resolver1회→continuation |
| POST `/api/supervisor/core/requests` | 명시 동의·고정 owner/key binding 확정→기존 owned Flow 호출 또는 같은 입력 복구 |
| GET `/api/supervisor/core/requests/{supervisor_id}` | owner binding과 Flow 상태 관측. model/resolver/provider·snapshot 게시0 |

Next는 동일 origin `/api/private/supervisor/core/...` 세 경로만 전달한다. transport는 `schema_version/request_id/trace_id/data/error`이며 data/error는 상호 배타다. 요청 body16384/decoded 응답65536 bytes, 준비 전체15초, confirmed POST140초/BFF145초다. identity encoding·no redirect·trust_env=False와 기존 service token 경계를 유지한다. 세션/Origin/CSRF·private no-store·고정 오류가 적용된다. 오류 원본문·query·token을 출력하지 않는다.

AI 내부 `/internal/supervisor/core/plan`은 start→검증된 mention의 도구 요청→Backend canonical resolution→continuation이다. Backend에 자연어 classifier를 복제하지 않는다. 의미 모델5/resolve3/continuation3초는 전체15초 안에 속하며 retry0이다. 응답 전 fresh DB transaction에서 실제 세션을 재검증한다. legacy analyze/executor·rewrite·직접 FlowAdapter 실행은 닫힌다.

## Immutable binding과 기존 실행

`supervisor_request_bindings` 한 표는 owner/client key digest에 유일한 확정 계획/Flow body/hash만 연결한다. 실행 상태·예약·attempt·결과를 복제하지 않는다. Flow body는 원질문·확정 canonical ticker·DB 시각 as_of·binding UUID의 고정 key·명시 opt-in이며 원래 AnalysisService/FlowUsageControl을 사용한다.

owner/key의 기존 행부터 확인한다. 동일 입력은 고정 snapshot을 사용하며 모델/resolver0, 다른 질문/답변/선택/동의는409다. 최초 부재가 확인된 경합에서는 의미 검증이 두 번 일어날 수 있으나 UNIQUE 승자 binding만 사용한다. binding commit ACK가 불명이면 최초 Flow0이다. 후속 primary 조회로 행이 확인된 replay만 복구하며 부재/조회불명을 구분한다.

`handoff_before=confirmed_at+120초`는 Flow run이 없을 때 **Flow 호출 직전 DB 시각 검사**다. 기존 Flow 내부 lock 대기/admission의 원자 시각 상한은 아니다. binding lock/바깥 transaction을 유지한 채 Flow를 호출하지 않는다. 기존 실행 원장·claim/fence·deadline·usage·멱등·snapshot만이 실행 권위다.

## Outcome과 삭제

관점별 상태와 전체 coverage는 별개다. 미연결 관점은 not_executed, stored Flow만 있는 혼합 질문은 partial이다. running은 pending, result_ready는 저장 성공이 아니며 explicit same-key POST만 snapshot 게시를 복구한다. unknown은 failed/cancelled/환불이 아니다.

Flow 보고서 삭제의 기존 transaction/잠금 순서(session→analysis→root) 뒤 binding 민감 JSON도 redact한다. 실패하면 보고서·binding 모두 rollback한다. hashes/owner/key/usage는 보존한다. 관측 뒤 binding redaction을 다시 읽어 삭제와 경합한 이전 질문/계획/본문을 반환하지 않는다. deleted는 plan/effective scope/Flow 참조를 숨긴다. migration 선행조건을 표 부재 무시로 대체하지 않는다.

## UI와 검증의 한계

기본 `/research`는 단일 SupervisorChat이다. 기존 `analysis_id` 및 owner별 Flow pending은 원래 AnalysisEntry로 복구하고, Sup pending은 별도 schema/owner 저장소를 쓴다. direct supervisor URL에 고정 pending이 없으면 GET-only다. session401/계정·URL·visibility/generation 변경은 비공개 표시/동의를 무효화한다. 원입력과 key는 보존한다.

[디자인/상태 기준](../design/supervisor-core.md)과 [실행 기록](../work/CF-022-supervisor-core.md)은 실제 증거 수준을 구분한다. Backend 합성 HTTP/소유 PG는 실제 모델·브라우저·운영 배포의 검증이 아니다.

## CF-023: meaning policy2와 고정 준비

transport `supervisor.core.v1`과 기존 policy1/plan hash/Confirm digest·binding replay는 보존한다. 새 `supervisor.meaning.v1` 후보는 정확 span의 mention/view/negation/typed 조건만 제안하며 canonical stock·권한·disposition·실행 동의는 제안하지 못한다. `supervisor.flow-core.2` 서버 정책이 값·단위·영역·부정 scope를 유한 규칙으로 검증하고 충분성/미인식 잔여를 판단한다. 충분한 명시 입력은 model0, 보완은 최대1회다. production gateway는 unavailable이다.

새 POST `/api/supervisor/core/preparations`와 GET/DELETE `/api/supervisor/core/preparations/{preparation_id}`는 owner/key에 고정한 짧은 준비 저장본이다. DB10분 TTL은 첫 채택만 제한하며 claim/usage를 되돌리는 기한이 아니다. ACK 불명·pending/unknown은 새 추출로 reclaim하지 않는다. child 후보 선택은 원 root frame/원질문을 재사용하며 model0·parent 이하 TTL이고 민감 JSON을 복제하지 않는다.

Confirm의 optional preparation_id가 없으면 legacy 필드 집합으로만 digest한다. 있으면 저장한 plan/draft/선택·동의·owner·현재 canonical을 검증하고 root→leaf 모든 ancestor를 원자적으로 소비·redact하여 승리 binding에 연결한다. 기존 binding replay가 preparation 잠금·TTL보다 우선한다. sibling/parent-child는 shared ancestor에 의해 하나의 binding만 채택한다. 미소비 sibling도 consumed/deleted/expired ancestor 뒤 plan/원문을 노출하거나 재사용하지 않는다.

준비 삭제는 child ID여도 실제 root 원문까지 redact한다. consumed lineage는 보고서 삭제 경로를 사용하고, 만료 미소비 원문 삭제는 허용한다. 운영 purge/미접근 만료행의 물리 잔류 정리 전체는 보장하지 않는다. 실제 OpenAI credential/전송과 전체 입력/계수 요금 증빙은 별도 pending이며 한정 verifier 외에서 호출을 열지 않는다.

## CF-024 private 검증 조립

production 기본 gateway는 unavailable로 유지한다. private verifier의 synthetic 모드는 같은 실제 Principal·준비 claim/attempt·CF023 epoch와 DurableMeaningBudget을 실제 PreparationService/AIClient/ASGI/OpenAIMeaningGateway 경계에 연결하며 공급자 transport와 credential만 고정 합성값이다. 별도 성공용 후보 반환 경로·public budget endpoint·AI DB 자격은 없다.

live 모드의 초기화는 원본 owned proof/CreationReceipt object identity·명시 epoch UUID/생성시각/상태 결합의 SELECT 검증만 수행한다. verifier_epoch의 INSERT는 합성 일회용 DB 초기화에만 사용한다. 다른 resource/새 작업 번호/같은 UUID를 근거로 epoch를 새로 만들거나 재설정하지 않는다. live는 외부에서 확인된 action-time authority와 정확한 DeferredKeySource/source capability, 계수 mapping/요금 근거를 요구한다. 이 repo가 bool/hash/합성 fixture로 실제 승인을 발급하지 않는다.

각 count/generation phase는 동일 proof의 fresh session에서 Principal·준비 owner/key/draft/spec/attempt/epoch·상태를 검증한 뒤 같은 session scope의 기존 durable 승인으로 위임한다. count 예약 commit ACK 이후에만 key supplier를 최대1회 호출한다. 키 결과는 attempt의 지역 참조로만 사용하며 종료 시 instance 참조를 제거한다. 문자열의 완전한 메모리 소거를 보장하지 않는다.

provider5초·verifier60초·승인 만료 중 가장 이른 절대 deadline을 공급/HTTP/정산·실패 정리에 적용하며 단계마다 시간을 갱신하지 않는다. 정산/취소/ACK불명은 성공 후보로 보고하지 않고 원 hold를 보존한다. 영속 block ACK를 확인하지 못하면 block 완료로 주장하지 않으며 같은 proof/epoch 확인 전에 추가 송신하지 않는다. 실제 모델/key 전송과 계수 요금 근거는 pending이며 이번 합성 검증은 실제 비용/모델 품질·운영 인수의 증거가 아니다.
# CF-026 private one-shot live controller

The controller adds no public endpoint or production default key loader. An
external trusted coordinator supplies a fixed grant and an approval capability;
JSON flags, synthetic grants and document digests alone do not authorize live
traffic. The grant binds two ordered drafts, exact rendered request/projection,
semantic/prompt/schema/price identity, explicit default tier, official count and
generation destinations, free-count evidence, source capability and expiry. The
existing verifier remains SELECT-only and owns phase/preparation/Principal and
durable reservation checks.

The private grant/state use owner-only0700 directories and0600 regular,
single-link files without symlinks. A stable separate lock inode is held for the
whole run. The exact directory/lock identity is in the approved scope so copying
an issued grant to another store cannot reset its budget. Claim is atomically
replaced and file/directory-fsynced before creating a resource. Missing, changed,
claimed, closed or unacknowledged state has no regeneration fallback.

Only the original newly created owned PG proof and CreationReceipt can initialize
one explicit CF023 epoch: USD0.10 total, USD0.05 per attempt, maximum2. INSERT ACK
and a fresh SELECT precede a live binding. The next snapshot keeps the same
resource, epoch ID and created_at; it is permitted only after the first exact
request/projection has observed durable settlement. No epoch reset, unit-label
change or new grant recovers unknown use. A private journal survives DB cleanup.

The approved existing key source is fixed by canonical location and owner,
device/inode, regular/single-link, no-symlink and mode0644 identity. It is not
chmodded or copied to a0600 replacement. Only `OPENAI_API_KEY=value` with an
optional pair of matching quotes is supported: maximum64KiB file,4KiB line and512
printable ASCII key bytes. Duplicate target entries, whitespace/escape,
interpolation, ambiguous quotes or multiline keys are refused. Other values are
not interpreted. Source and expiry are checked again after count reservation ACK;
the deferred source is supplied at most once per attempt. Keys are not logged or
stored in state, argv, environment, result or DB. Reference release does not imply
complete memory erasure.

Code-copy provenance is separate from credential provenance. A live caller must
provide the exact reviewed original worktree capability (directory identity and
controller hash); original and copied controller bytes must match. The key path
is only its fixed approved sibling location, never a path discovered from the
temporary copy, environment or CLI. This metadata capability does not read the
key or authorize a call by itself.

Cancellation, exception or timeout does not discard accounting. Before disposal
the controller attempts a bounded fresh owned ledger read. If unavailable,
count/generation/usage remain unknown and the entire100,000,000nanoUSD approval is
conservatively held. The accounting record must have durable ACK before cleanup;
otherwise the approval stays claimed and exact owned cleanup evidence is retained
for coordination. No new send/retry follows. Cancellation is re-raised after
bounded evidence and cleanup. Cleanup uncertainty is failure, never absence.

The synthetic-only validation provisions a fake grant outside the DB/source-copy
and exercises the actual controller, owned bootstrap/migration/Principal, explicit
epoch and existing reviewed ASGI/gateway MockTransport assembly. Its success then
unknown sequence is not live authority or provider evidence. Production live
remains closed until the coordinator fixes the actual grant, source capability,
official evidence and runtime scope. Current execution results and limitations
are tracked in [CF-026 worklog](../work/CF-026-supervisor-live-controller.md).

### CF-026 v1.3 bounded failure observations

Each of at most two attempts records only closed verifier stage labels (maximum16),
existing meaning-status enums and observed/hold/unconfirmed/not_called settlement.
Projection occurs immediately on return, before settlement failure gates. No
verifier return is represented by false plus nullable fields; malformed fields
are a fixed diagnostic failure, never arbitrary text or its hash. The private
controller's result summary also contains only these projected verifier fields.

The controller supplier records entered, approval_checked, source_read_entered,
source_read_returned and failed/cancelled/timed_out labels. The recorder never
receives the key value. Read entry is not proof of content-read completion or
HTTP transmission. Fixed ControllerError codes are retained; other errors,
cancellation and timeouts are normalized without message/locals/body/path/hash.

Classification distinguishes before-supplier, supplier failure, returned supplier
with HTTP unknown, verified generation authority before reservation, observed
generation reservation, and unknown. Each includes the exact labels used.
Count/generation HTTP remain unknown: no gateway/transport instrumentation was
added. Reservation ACKs are ledger evidence, not physical send receipts.

Attempt observations are aggregated into existing settlement/final-accounting
records under the same atomic persistence/ACK boundary. The journal cap remains24;
nonterminal work stops at21 entries to reserve final accounting, closing and
cleanup. No new diagnostic events or additional waits are introduced. Mandatory
diagnostic/accounting ACK loss stops later attempts and retains claimed state,
hold and exact cleanup proof. Final ledger capture still precedes preservation
or disposal, and cancellation is propagated. These observations do not authorize
calls and cannot diagnose the earlier closed one-shot attempt retroactively.

### CF-026 v1.4 one-time residual continuation

The closed original approval is never reopened. A separate trusted issuer may
create one fixed continuation slot under the original canonical namespace and
stable execution lock. Before any local issuance write it must obtain a durable
one-shot consumption ACK and fresh readback from an independent authority. The
authority must have an explicitly pre-provisioned available parent namespace;
missing, lost, unavailable or ambiguous state is not first issuance. Atomic
available-to-consumed CAS is keyed by the original anchor, not a permission object
or new receipt ID. The exact authority identity is bound by the receipt's required
`issuance_authority_sha256`; changing providers cannot reset the same receipt.

An immutable local issuance tombstone outside the slot is then written and
fsynced before slot creation. It is supplementary evidence, not the source of
the one-shot right: loss of both slot and tombstone still leaves the external
namespace consumed. Partial issuance, ACK loss, a missing or changed witness,
replay and concurrent issuance fail closed. Runtime rechecks the same external
consumption and requires the fully issued identity-bound capability; it does not
reconstruct or issue a capability from JSON or local absence.

`OneShotIssuanceAuthority` requires trusted observe/CAS callbacks and has no
production implementation, default provider or create-on-missing behavior here.
Live issuance remains blocked until independently durable authority storage,
its fixed identity/namespace and atomic consumption/readback semantics are
provided and reviewed. The file-backed synthetic callback provider is only a
test simulation and cannot satisfy a live-mode permission. These tests do not
prove recovery or safe reissuance if the independent authority itself is reset.

The original grant, state and closure evidence remain byte-identical. Historical
expiry is retained as history; current permission, evidence, source capability,
runtime and expiry are checked separately. Only the first identical original
request is eligible. The inherited50,000,000nanoUSD unknown hold plus one child
reservation50,000,000nanoUSD consumes the same total100,000,000nanoUSD allowance
and original1+child1 attempt limit. This is neither a new budget nor a bill.
Aggregate actual usage remains unknown while the original usage is unknown.

Claim, preparation/attempt identity and each count/generation right are durably
acknowledged under the original lock. A new owned child epoch is an execution
ledger, not restored budget: its phase reservation follows the external authority
ACK, and the deferred supplier follows the local count reservation ACK. Each phase
is allowed once. Accounting ACK loss preserves claimed state, conservative hold
and exact cleanup proof; cancellation still propagates. The journal remains
bounded to24 entries with terminal space reserved.

Live dispatch calls the unchanged private `verify_live`, preserving its rejection
of synthetic authority, mapping and transport and its shared-driver wrapper. The
synthetic-only test assembly injects the actual continuation authority into the
existing PhaseBudget/gateway/ASGI/preparation path using reviewed MockTransport.
It is not live authority or provider evidence. Controller source-copy provenance
has an explicit128KiB code-only read limit; credential, grant and state reads
retain their64KiB limits. Current results and remaining live prerequisites are
recorded in the worklog; no actual continuation is issued by these tests.

### CF-026 v1.6 new approval aggregate

A distinct explicitly approved aggregate includes the original unknown carry of
50,000,000nanoUSD within a total1,000,000,000nanoUSD ceiling. It neither reopens the
old closed approval nor supplies the missing v1.4 live issuance authority. The
first supported child remains the fixed Supervisor two-candidate batch with a
100,000,000nanoUSD worst-case reservation. Total reserved becomes150,000,000;
850,000,000 remains. Current Flow913,500,000 exceeds that remainder; Flow and
Technical are not integrated executable kinds in this wrapper.

Only a trusted coordinator may bootstrap the canonical root once. Durable private
coordination history must consume the bootstrap opportunity before root creation,
retain partial/uncertain attempts and pin root/header/stable lock identities plus
initial and latest confirmed heads. Runtime is open-only. Missing roots, history,
head evidence, drift and ambiguous writes never cause bootstrap or budget reset.
Reopening requires independently retained binding/head and explicit restart
attestation, not the same approval message. Local history and reference evidence
being lost or rolled back together cannot be recovered automatically; that is a
blocked state, never an unused approval.

Under one aggregate lock the order is reservation ACK, issuance-right consumption
ACK, child creation/binding ACK, execution-start-right consumption ACK, then the
unchanged legacy runner. Aggregate locks precede child locks. Intent authorization
pins exact payload/source/spec/price/model/tier/caps, child identity/path/nonce and
expiry. Rights and reservations are monotonic and never refunded by success,
failure, no-call, low usage, cancellation or child disposal. No allocation replay
issues or starts another child. Confirmed head advances only after local fsync,
fresh read and coordination ACK; pending transitions retain the prior confirmed
head separately. Allocation count is bounded to9 and state to64KiB.

The legacy child keeps its original validation, first observed gate, durable
usage, SELECT-only live verifier and deferred key boundary. An aggregate-owned
accounting callback must ACK the final child accounting before child disposal;
ACK loss uses the existing claimed/proof-preservation path. Cancellation propagates.
The allocator records sanitized accounting and cleanup evidence without raw input
or secrets. Current expiry may not exceed2026-11-10 21:00 UTC; later allocation or
supplier work is closed while bounded accounting/owned cleanup remains permitted.
No already-sent remote request can be assumed cancelled or free.

The coordinator history interface has no default live storage or discovery.
Synthetic file/CAS callbacks are separate from actual coordination history and
actual issuance. A shared synthetic-only DI assembly uses the existing PhaseBudget/gateway/ASGI
and reviewed MockTransport for the exact two candidates, keeping the unchanged
checker and live factory guards intact. Focused results and the initial narrower
synthetic-factory rejection are tracked in the worklog. No actual aggregate bootstrap,
allocation, key or provider call is authorized by synthetic test success alone.

Reproducible synthetic fixtures use an explicitly synthetic-mode six-minute
lease relative to fixture creation. They are not bound to the historical live
approval cutoff. Live headers still reject any expiry after2026-11-10 21:00 UTC,
and live authorization is closed after that fixed cutoff. Synthetic mode also
requires synthetic history/source/child scope and fixed synthetic DI; it cannot
be promoted into a live approval. No clock, deadline override or environment
fallback is exposed to production callers.
