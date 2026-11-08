# Flow KIS 토큰 캐시

CF-004 v1.0의 무키 캐시 격리·strict 입력·안전 저장 범위다. 제품 구현은
[token_cache.py](../../../src/agents/flow/infrastructure/token_cache.py), 실제 HTTP 연결부는
[kis_client.py](../../../src/agents/flow/infrastructure/kis_client.py)다.

서버 `base_url.rstrip('/')`와 정확한 app key·secret을 버전 표식과 함께 canonical JSON으로
직렬화해 SHA-256 문맥을 만든다. key/secret 회전·서버 변경은 별도 파일이다. 이는 암호화가 아니다.
기존 base 파일명 대신 digest를 포함한 형제 파일을 사용하며 평문 자격·서버를 파일명에 넣지 않는다.
기존 무결합 `kis_token.json`은 읽거나 옮기거나 삭제하지 않는다. 따라서 추후 실제 실행의 첫 요청은
기존 토큰을 재사용하지 못해 새 발급이 필요할 수 있다. 이번 검증에서는 실제 발급을 수행하지 않았다.

## record와 발급 계약

캐시는 `schema_version`(JSON 정수 2), `scope_digest`, `token`, `expires_at` 네 필드만 둔다.
중복 필드·잘못된 UTF-8/JSON·지원하지 않는 타입/버전·문맥 불일치·64KiB 초과 record는 miss다.
정상 일반 파일의 손상/누락·만료도 miss다. 안전 경계 위반은 발급으로 우회하지 않고 고정 오류다.

토큰은 공백/제어문자가 없는 비어 있지 않은 ASCII 문자열이어야 한다. now/시간은 bool을 제외한
유한 숫자만 받고, `now < expires_at - 60`일 때만 재사용한다. 잘못된 now는 발급 전 오류다.
발급 JSON 객체는 원형 token과 존재하는 숫자 `expires_in > 60`을 요구하며 누락을86400으로
보충하지 않는다. expiry 합계도 유한해야 한다. record 직렬화는 `allow_nan=False`이며 읽기/쓰기
상한은64KiB다. hit은 발급0회, miss는 주입 발급자 최대1회다. 발급/저장 실패 뒤 자동 retry는 없다.

## 파일 경계와 실패

caller가 전달한 경로의 부모 component만 metadata로 확인하고 symlink를 거부한다.
최종 부모를 no-follow directory FD로 열어 identity를 재대조한 뒤 entry I/O를 그 FD에 한정한다.
새 부모는0700, 기존 부모는 현재 uid 소유·일반 디렉터리·group/other 쓰기 불가여야 하며 chmod하지 않는다.
전체 home/조상을 열거하지 않는다. 기존 entry는 **열기 전에** regular·현재 uid·single-link·0600을
검사하고 no-follow/nonblocking open 뒤 fstat identity를 다시 확인한다. FIFO도 blocking open하지 않는다.

값·JSON을 검증한 후 같은 디렉터리에 배타/no-follow0600 임시 파일을 생성한다. fchmod와 mode
확인까지 첫 token byte 전에 끝낸다. write→flush→fsync→부모/기존 entry·temp identity 재대조→
동일 dirfd의 `os.replace` 순서다. 교체 전 실패는 기존 bytes/identity를 보존하고 자기 temp만 정리한다.
교체 완료 후 확인 실패는 고정 `TokenCacheError(committed=True)`로 구분하며 무변경을 주장하지 않는다.
KIS 경계의 오류는 고정 `KisError`로 번역하고 원문 provider/경로/자격/token 예외 cause를 출력하지 않는다.

## 검증 범위와 한계

[보호 Backend unit](../../../../backend/tests/unit/test_cf004_kis_token_cache.py)은 실제 stdlib 모듈을
자기 임시폴더·합성 자격·가짜 발급자로 실행한다. KIS 연결부는 AST/source 검토이며 import하지 않는다.
기존 [AI 캐시 회귀](../../../tests/flow/test_kis_token_cache.py) 다섯 의도는 유지했지만 AI pytest는
실행하지 않았다. 최종 실행 수·source SHA와 한계는 [작업 기록](../../../../docs/work/CF-004-flow-kis-token-cache.md)에 있다.

동일 uid의 악의적 프로세스·모든 조상 경로 공격·전원 장애 후 directory 영속성·동시 발급
single-flight/정확히 한 번 발급을 보장하지 않는다. 다른 프로세스 발급으로 기존 KIS 토큰이 무효화되는
제공자 한계도 남는다. 실제 자격·기존 캐시 전환·KIS 발급/수집·Flow 계산/그래프는 미검증이다.
20행/20일 의미·payload v1·다른 서비스 동작은 이번 변경에 포함하지 않는다.
