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

The key source is exactly `verith/ai/.env` under the reviewed worktree parent.
Backend, Frontend, the verifier worktree and alternative paths are refused. This
service-location correction does not rebind a consumed grant or permit replay.

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
# CF026 fixed-window renewal

The private aggregate controller retains the historical cutoff and accepts only
the separately reviewed current window, with a fixed lower start bound and upper
expiry bound. Header and child schema keys, the cumulative budget and original
unknown hold, canonical aggregate identity, one-shot issuance and delayed key
supply remain unchanged. An expired historical descriptor cannot be revived by
changing its expiry. Current source, runtime and contract evidence must be bound
again before any execution. Synthetic future leases do not grant live access.


## CF-026 후속 준비 전용 계약 prototype

기존 frozen aggregate는 reopen하거나 rewrite하지 않는다. 현재 전체 예약
150,000,000nanoUSD에는 과거 unknown carry가 이미 포함되어 있으므로 다시
더하거나 환불하지 않는다. `FIRST_SETTLEMENT_UNCONFIRMED`는 aggregate의
종료 사유이고 `KEY_SOURCE_INVALID`는 supplier 단계 원인이다. count 예약 1·
generation 예약 0·HTTP unknown·estimated=null을 각각 유지한다.

이번 준비는 기존 단일 unit 안의 순수 test-only prototype이다. runtime에서
import하거나 실행하는 planner/API가 아니며 실제 파일의 진위 확인·예산 예약·
발급·권한 생성 기능이 없다. 외부에서 검증된 선행 증거 projection과 독립 expected
hash를 입력으로 받아 original root, aggregate header/state, child grant,
closure/accounting, 실행 당시 source/runtime 및 carry의 연결을 대조한다.
이 입력의 실제 파일 검증/독립 witness 확보는 아직 구현·검증하지 않았다.
합성 hash가 실제 승인이나 실제 증거로 승격되는 것이 아니다.

제안은 원래 첫 질문 하나의 명시적인 1회 재검증이다. 두 고정 draft의 독립
request/projection hash를 대조하되 첫 항목만 고르며 둘째로 대체하지 않는다.
count 1/generation 1/HTTP 2·자동 retry 0·같은 모델/default tier/origin/endpoints·
input 16384/output 2048과 정확 AI source 제안만 수용한다. 기존 count 1을 포함해
계획 count 2이며, 신규 보수 예약 50,000,000을 가정한 누적 200,000,000/잔여
800,000,000nanoUSD를 계산한다. 실제 예약이나 실사용액이 아니다. 새 두 질문
batch 100,000,000안은 채택하지 않는다.

결과는 언제나 `execution_authorized=false`, `new_source_bound=false`다.
이전 retry 0 정책이 재검증을 자동 허용하지 않는다. 첫 요청의 명시적 1회 재검증과
새 bounded 시간창 결정, 동일 선행 사건을 중복 후속에서 소비하지 못하게 하는
독립 단일 소비 witness, fresh AI source capability와 검토된 단일 실행 조립이
없으면 실행할 수 없다. 기존 두 질문 legacy runner와 source/hold가 다른
continuation receipt를 우회하거나 그대로 재사용하지 않는다.

프로토타입은 controller의 128KiB provenance 상한을 늘리지 않으며 실제 controller/
entry/worker/guard/AI32·기존 실행 산출물은 변경하지 않는다. 실제 실행 기능이
필요해지면 정확한 추가 파일과 보호 입력 범위를 별도 검토해야 한다. 이 계약의
수용은 순수 합성 계산/거절 회귀이며 실제 authority·PG·provider 수용이 아니다.

## CF-026 단일 successor helper · 실제 activation 전

별도 `scripts.cf026_successor`는 private DI용 단일 helper이며 CLI/issuer/기본
credential loader가 없다. authority/source/journal이 없으면 부작용 전에 닫는다.
기존 controller·verifier·gateway·PhaseBudget·worker/guard와 private 실행 산출물은
변경하지 않는다. 실제 authority adapter는 아직 제공하지 않으며 합성 callback이
실제 소비 권위라고 주장하지 않는다.

읽기 검증은 실제 frozen header/state, child grant/state, closure, coordination
head, 과거 carry grant/state/closure 및 당시 runtime의 10개 pinned JSON을 쓴다.
파일을 열기 전에 canonical 경로/종류를 제한하고, owner·mode0600·nlink1·symlink
거절·identity/hash를 검사한다. header의 carry hash, allocation/child/회계 연결,
coordination의 root/header/state head와 directory/lock pin, closure의 adapter
pin, 당시 source/runtime 연결을 교차 대조한다. 예전 raw schema를 단순한 projection
schema로 바꿔 수용하지 않는다. 새 source는 별도의 정확 AI capability다.

successor-once identity는 원 namespace와 원 bootstrap에 고정한다. 실제 최종
head는 따로 pin하며 source/invocation·해시 표현을 바꿔 슬롯을 늘릴 수 없다.
독립 consume/readback ACK가 reserve50m→issue→start의 local fsync/fresh readback보다
선행하고, start 뒤에만 자기 자원을 만든다. local journal은 검토된 private 경로의
추가 증거이며 새 budget root나 authority가 아니다. 원 부모150m은 불변이고 후속
보수 예약50m과 결합한 값만200m이다. 실제 adapter의 원자성·보존은 미검증이다.

lease는 독립 ACK의 발급 시각부터 최대600초, start는30초 이내다. 두 제한 모두
wall-time과 monotonic을 확인하며 사용자 지정 기간으로 표현하지 않는다. await/
ACK/fsync 뒤와 driver 호출·소유 engine의 SQL/commit 직전에 재검사한다. SQL
listener는 새 소유 engine에만 붙고 finally에서 제거한다. 이는 전송 직전 검사이며
이미 서버가 받은 명령의 원자적 취소를 보장하지 않는다. 과거 날짜를 다시 열지 않는다.

새 조립은 기존 verify_live를 정확 한 번 호출한다. 소유 setup의 동일 attestation/
migration·Principal·최초 epoch INSERT/fresh SELECT 구조를 유지하고 그 engine에
lease guard를 더한다. local epoch100m/2는 그대로이며 외부 count1/generation1/
attempt1·50m 권한이 더 좁게 제한한다. 기존 준비 owner/draft/spec/attempt/epoch
조회 helper를 재사용하고 count root ACK→local PhaseBudget ACK 뒤 deferred source를
최대 한 번 공급한다. 실제 source/key는 이번 무키 검사에서 읽지 않는다.

모든 실패 경로에서 fresh ledger/고정 진단을 먼저 로컬에 보존하고 외부 회계 ACK
뒤에만 정확 소유 자원을 정리한다. 회계 ACK가 불명이면 proof를 보존하며 preserve도
driver timeout/외부 bound 안에 둔다. 뒤늦은 취소가 앞선 오류에 가려지지 않는다.
raw provider/자유 예외·키·비밀 hash를 보존하지 않고 HTTP unknown과 usage null,
권리/예약을 유지한다. local 증거 유실 뒤에도 독립 권위가 재소비를 막아야 한다.

현재 수용은 새 helper의 실제 함수·자기 합성 파일 journal/fsync·authority 모의와
verify_live keyword/phase/supplier DI spy다. 실제 Principal/ASGI/PG/provider가 모두
실행된 수용이 아니다. actual activation에는 신규265-source/provenance, AI source
metadata, 단일 scope/lease descriptor, 명시 private successor entry, 실제 독립
authority adapter의 최종 검토가 남아 있다. 기존 private entry/manifest/flags를
조용히 바꾸거나 소비된 grant를 재사용하지 않는다.
# CF026 명시 재시도 ordinal 1 추가 경계

소비된 최초 successor가 provider 전에 입력/readback timeout으로 종료된 뒤의 명시 재시도는 원 once의 재개가 아니다. 원 frozen 부모 150m과 소비된 successor 50m은 그대로 보존하고, 정확한 timeout/원복 증거 및 원문 item·turn·UTF-8 본문 hash, 새 동의에 묶인 고정 ordinal 1만 별도로 검증한다. 기본 authority는 계속 unavailable이며, local evidence나 boolean/hash만으로 실제 실행권이 생기지 않는다.

동일 namespace/bootstrap와 고정 ordinal 1이 identity를 결정한다. source·invocation·동의 ID·증거 직렬화 변경으로 추가 슬롯을 만들 수 없다. 실제 외부 조율은 같은 canonical lock 아래 소비 전 이력 확인·최초 추가 50m 기록·독립 readback을 수행해야 한다. 같은 record/nonce나 비어 있는 old journal을 재사용하지 않고, 이후 자동 retry와 ordinal 2는 닫는다.

기존 200m에 추가 50m을 합친 250m만 이 분기의 server record·phase ACK·회계·반환값으로 수용한다. 이는 실제 청구액이 아니며 기존 보류를 환불하거나 예산을 초기화하지 않는다. 첫 동일 질문 한 개, 무료 count 1·generation 1·HTTP 2·자동 provider retry 0은 유지한다. 원 과거 HTTP unknown과 별도 timeout의 미호출 관측도 구분한다.

새 helper의 시작 제한은 발급 시각 기준 wall/monotonic 120초이며 private ready 입력도 120초로 제한한다. 전체 lease 600초·provider/verifier 60초·callback 5초·cleanup 30초·예약 전 source preload 30초는 유지한다. 입력/ACK 수신 시점부터 시계를 다시 시작하지 않고 늦은 ACK에는 새 자원/키/송신을 막는다. 이번 무키 수용은 실제 권위 발급이나 PG/provider 성공을 뜻하지 않는다.

## CF026 policy2 deadline·정산·안전 진단 추록

위 재시도 조립의 시간 설명은 당시 이력이다. 이번 무키 변경에서 policy2의
`provider_seconds`를 5에서 55로 변경하고 `verifier_seconds`는 60으로 유지했다.
AI와 Backend mirror의 새 semantic SHA는
`c3cb325b4b4e92cf72b1ff62714dec6e12f8637220dcaa0b2d9443644b397251`이다.
모델·가격·토큰·시도 상한·schema·prompt·endpoint와 자동 retry 0은 그대로다.
이는 새 semantic spec이며 과거 승인·epoch·준비·frozen source·입력·manifest를
새 hash로 갱신하거나 기존 consumed 권리를 복구하지 않는다.

policy2의 meaning/route/client/preparation 상한은 각각 60/65/70/75초다.
policy1의 meaning 5초·client 8초·total 15초와 body/auth 제한은 보존한다.
gateway에는 meaning outer를 포함한 가장 이른 절대 deadline을 내부 전달한다.
최대 5초, 짧은 잔여 시간에서는 그 1/4 이하의 정산 tail을 남기고 각 HTTP는
`min(55, 남은 shared send deadline)`으로 제한한다. authority가 좁힌 기한을
다시 늘리지 않는다. 별도 settlement deadline이 없는 기존 budget은 현재 송신
기한과 budget deadline의 교집합을 사용한다.

정산 시작을 await 전에 latch하여 정상/실패 경로 전체에서 finish는 최대 1회다.
성공 정산 ACK 손실·DB 예외·정산 timeout 뒤 추가 finish나 provider retry는 없다.
외부 cancellation은 취소된 task에서 정산 SQL을 다시 실행하지 않고 전파하며
unknown/hold를 보존한다. 정산 기한도 원 absolute/authority와 최대 5초보다 길지 않다.

새 private `gateway_diagnostic`은 최대 16개의 고정 stage/elapsed_ms와 정산 불명
flag만 담고 기존 public DTO와 verifier stages에는 섞지 않는다. dispatch 진입은
wire 송신 증거가 아니다. 응답 관측·count 검증·usage·정산 ACK를 구분하며 키·본문·
헤더·자유 예외·HTTP status는 durable projection에 남기지 않는다. verifier 반환
전에 외부 취소나 바깥 timeout이 끝나면 이 진단이 없을 수 있다.

실제 helper의 정확한 Closed 타입·등록 code만 고정 오류로 전달하고 후기 정산
gate도 최종 회계 전에 보존한다. 이 변경은 무키 회귀 수용이며 기존 250m 보수
예약을 환불하거나 실제 생성 결과·비용·모델 품질을 확인한 것이 아니다.
