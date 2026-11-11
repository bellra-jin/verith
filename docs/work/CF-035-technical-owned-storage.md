# CF-035 Technical 내부 저장과 본인 복구

기준 develop `41e1f9a9e61162d6fd1ff882290fc6b799ddc69d`에서 시작한 `feat/technical-owned-storage`의 정확16파일 작업이다.
CF021/CF031의 비영속 계약을 보존하고 새 내부 stage-only 저장·본인 read만 추가한다. legacy AI 생성·자체 commit 경로,
public API/BFF/UI/profile·usage·실제 engine/provider는 연결하지 않는다.

stage는 검증 Principal/session lock과 독립 L/B/frozen을 재검사하고 기존 canonical stock 조회만 한다. 기존 ID/index는
충돌로 닫고 root/자식/snapshot/owned index를 같은 transaction에 flush한다. read는 SQL owner/전체 index 정확1개를 먼저
검사하고 immutable snapshot에서 CF031 restore와 실제 projection을 재검증한다. 저장 session anchor는 새 로그인과 구분한다.

구현 중 독립 읽기 검토에서 저장 session anchor 누락과 context identity TEXT의 normalize 우회를 확인해 보완했다.
보호 worker의 필수 origin 입력과 AI source 금지의 충돌은 정확한 기존 순수 readonly Flow6파일을 고정하는 범위로 정정했다.
worker/OS/FS/network 보호를 바꾸거나 가짜 origin을 만들지 않았다. readonly6개와 fixture1개는 변경 파일이 아니다.

직접 검사(2026-11-11): 기존 설치 Python을 전용 worktree의 검증된 alias로 사용하고 clean env의 절대 Python
`-I -S -B backend/scripts/check_safe.py technical-owned-self` / `technical-owned-unit` 보호 입구를 실행했다.
최종 self3·단일 unit65가 통과했고 guard0·parent exit0·각 소유 임시 root 정리를 확인했다. 앞선 unit63 통과는
missing chart/잠금 순서 회귀 추가 전 이력이며 최종 수에 더하지 않는다. 이 모의 session/SQL 결과는 실제 PG와 구분한다.

별도 고정 source-copy launcher에서 기존 `--verify-technical-owned-db` 입구로 새 Verith 전용 일회용 owned PG를
한 회차 생성·검사·정리했다. proof/CreationReceipt, readonly preflight와 동일 검증 연결 migration, 제한 role,
private dotenv/외부 network 차단을 재사용했다. 공통 harness를 포함한 source245개(불변 순수 AI 호환6·공유 fixture1)를
고정했으며 이를 제품 변경16파일과 구분한다. unit OS sandbox와 PG의 proof/role/socket 보호 범위도 구분한다.

실제 PG의 여섯 묶음이 통과했다: upgrade/빈-owned downgrade/re-upgrade와 legacy NULL row 보존, stage flush의
타 transaction 미노출/commit 후 새 로그인 복구·detached preview, 실제 session 만료/철회/위조 거절,
SQL owner·전체 index/snapshot 조건과 immutable UPDATE·projection 변조 거절, 중간 실패 rollback·동일 ID 경합
승자1·request 충돌·commit 완료 뒤 합성 ACK 손실의 고정 ID read(재stage0), owned 데이터의 downgrade 거절.
저장 당시 session을 자기 합성 DB에서 정리한 뒤 새 유효 session으로도 복구했다. snapshot UPDATE는 DB trigger가
거절한 결과이며, root/child/index projection은 service read가 거절한 결과다.

PG parent exit0, 정확 소유 DB receipt에 따른 제거/부재, 자기 source root 제거, source/dependency/origin 후검사가
통과했다. dotenv/network/HTTP 관측 거절 카운터는0이고 engine/provider/public HTTP 호출도0이다.
독립 중간 리뷰의 commit ACK 손실 주입 누락은 real commit 후 합성 예외를 넣고 read-only 복구로 보완했다.
최종 독립 delta 리뷰는 정확16파일·고정13파일·보존 로그5개를 읽어 대조했고 미해결 blocker가 없었다.
독립 검토자는 검사를 재실행하지 않았다. Draft PR 게시와 원격 exact-head CI는 이후 별도 단계다.

운영 DB migration, 실제 인증 HTTP/브라우저, AI/키/provider·실사용 예산/원장 변경은 없다. 기존 다른 worktree/WIP와
불확정 실제 모델 실행 기록은 보존한다. 실제 제품 공개나 Technical 전체 연결 완료로 표현하지 않는다. merge는 사용자가 한다.
