"""KIS 어댑터 — "종목별 투자자매매동향(일별)" → signals.py DataFrame.

경계 번역기(boundary translator). 이 파일만이 KIS의 필드명·단위·정렬·인증을 안다.
덕분에 signals.py·verify_rules.py는 KIS를 전혀 몰라도, 자기 스키마
("개인/외국인/기관/거래대금" 컬럼 + 오름차순 날짜 index)만 신뢰하면 된다.

규약(CLAUDE.md 데이터 소스):
  - 조회(GET) 전용. 주문(매수/매도/정정/취소) 함수는 이 파일에 없다 — 실전 계좌.
  - .env의 KIS_API_KEY/KIS_API_SECRET/KIS_BASE_URL로 토큰 발급 후 호출.
  - 비밀·토큰은 로그/예외 메시지에 넣지 않는다.
  - 실패 시 다른 방법을 연쇄 시도하지 않고 명확한 예외로 멈춘다.
    (단 하나의 예외: 유량 제어 EGW00201 은 0.6초 후 1회 재시도 — _get_json 참고.)

실물로 확인된 변환 4가지(scratch_kis.py로 검증):
  (1) 필드 매핑: *_ntby_tr_pbmn → 개인/외국인/기관, acml_tr_pbmn → 거래대금
  (2) 정렬: KIS는 최신이 먼저(내림차순) → signals는 오름차순 전제 → 오름차순으로
  (3) 단위: 순매수는 백만원, acml_tr_pbmn은 원 → acml ÷ 1,000,000 로 백만원 통일
  (4) 컬럼명·순서를 signals 스키마와 정확히 일치시켜 반환
"""

from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pandas as pd
from dotenv import load_dotenv

from src.shared.runtime.deadline import DeadlineExceeded

from .token_cache import TokenCacheError, get_token, validate_issued_response

from ..domain.signals import COL_CHANGE, COL_CHANGE_RATE, COL_CLOSE, COL_FORE, COL_FORE_QTY, COL_INDI, COL_INST, COL_INST_QTY, COL_OWNERSHIP, COL_VALUE, COL_VOLUME, INST_DETAIL

_AI_ROOT = Path(__file__).resolve().parents[4]
_ENV_FILE = _AI_ROOT / ".env"

# ── KIS 엔드포인트 상수 (이 경계에서만 안다) ──────────────────
_OAUTH_PATH = "/oauth2/tokenP"
_QUOTATIONS_PATH = "/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily"
_TR_ID = "FHPTJ04160001"  # 종목별 투자자매매동향(일별). 실전전용.
_DAILY_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"
_DAILY_PRICE_TR_ID = "FHKST01010400"  # 주식현재가 일자별. 조회 전용.
_EHRT_FIELD = "hts_frgn_ehrt"         # HTS 외국인 소진율(%)
# 일자별 시세 필드 (실물 확인 2026-07-07, scratch_kis_daily_price.py):
# 항등식 성립 확인 — prdy_vrss = 종가차, prdy_ctrt = 전일비÷전일종가(소수 2자리).
_CLOSE_FIELD = "stck_clpr"            # 종가(원)
_CHANGE_FIELD = "prdy_vrss"           # 전일비(원, 부호 포함)
_RATE_FIELD = "prdy_ctrt"             # 등락률(%)
_VOL_FIELD = "acml_vol"               # 누적 거래량(주)
# 주의: 이 API에도 frgn_ntby_qty 가 있지만 매매동향의 같은 필드와 값이 다르다
# (실측 2026-07-07 — signals.COL_FORE_QTY 주석 참조). 순매매량은 매매동향으로
# 일원화하므로 여기서는 파싱하지 않는다.
_TIMEOUT = 15.0

# KIS 유량 제어: 짧은 창에 조회가 겹치면 HTTP 500 + EGW00201 로 선차단된다
# (scratch_kis_ratelimit.py 로 실물 확인 — 간헐적, 11ms 게이트웨이 즉답).
_RATE_LIMIT_MSG_CD = "EGW00201"       # "초당 거래건수를 초과하였습니다."
_RATE_LIMIT_RETRY_WAIT_SEC = 0.6      # 유량 창 하나를 넘기는 대기

# (1) KIS 원본 필드 → signals 컬럼. 매핑의 단일 출처(매직 스트링 금지).
_FIELD_MAP: dict[str, str] = {
    "prsn_ntby_tr_pbmn": COL_INDI,   # 개인   순매수 거래대금 (백만원)
    "frgn_ntby_tr_pbmn": COL_FORE,   # 외국인 순매수 거래대금 (백만원)
    "orgn_ntby_tr_pbmn": COL_INST,   # 기관계 순매수 거래대금 (백만원)
    "acml_tr_pbmn": COL_VALUE,       # 누적(총) 거래대금 (원! ← ÷1e6 필요)
    "frgn_ntby_qty": COL_FORE_QTY,   # 외국인 순매매량 (주 — 스케일 없음)
    "orgn_ntby_qty": COL_INST_QTY,   # 기관계 순매매량 (주 — 스케일 없음)
}
# 기관계 세부 7주체 (전부 백만원 — 세부 합 ≈ 기관계 항등식 실물 확인됨).
# 한글명은 KIS 공식 필드 사전(공식 GitHub) 그대로. signals.INST_DETAIL 과 일치.
_DETAIL_FIELD_MAP: dict[str, str] = {
    "scrt_ntby_tr_pbmn": "증권",
    "ivtr_ntby_tr_pbmn": "투자신탁",
    "pe_fund_ntby_tr_pbmn": "사모펀드",
    "bank_ntby_tr_pbmn": "은행",
    "insu_ntby_tr_pbmn": "보험",
    "mrbn_ntby_tr_pbmn": "종금",
    "fund_ntby_tr_pbmn": "기금",
}
assert set(_DETAIL_FIELD_MAP.values()) == set(INST_DETAIL)  # 이름 단일 출처 보장
_DATE_FIELD = "stck_bsop_date"       # "20260703"


class KisError(RuntimeError):
    """KIS 호출 실패. 메시지에 비밀·토큰을 담지 않는다."""


class KisConfigurationError(KisError):
    """Real-only market endpoints cannot use a paper or arbitrary origin."""
    code = "KIS_CONFIGURATION_INVALID"

    def __init__(self):
        super().__init__("KIS 실전 조회 서버 설정이 올바르지 않습니다.")


def _production_base_url(value: str) -> str:
    try:
        if type(value) is not str or not value.isascii() or any(ord(c) <= 32 or ord(c) == 127 for c in value):
            raise ValueError()
        url = urlsplit(value)
        if (url.scheme != 'https' or url.hostname != 'openapi.koreainvestment.com'
                or url.port != 9443 or url.username is not None or url.password is not None
                or url.path not in {'', '/'} or '?' in value or '#' in value):
            raise ValueError()
    except ValueError:
        raise KisConfigurationError() from None
    return value.rstrip('/')


def _load_credentials() -> tuple[str, str, str]:
    """.env에서 KIS 자격정보를 읽는다. 값은 반환만 하고 절대 출력하지 않는다."""
    load_dotenv(dotenv_path=_ENV_FILE, override=False)  # AI 서비스 루트 .env만 사용; process env 우선
    app_key = os.getenv("KIS_API_KEY")
    app_secret = os.getenv("KIS_API_SECRET")
    base_url = os.getenv("KIS_BASE_URL")
    missing = [name for name, value in (
        ("KIS_API_KEY", app_key),
        ("KIS_API_SECRET", app_secret),
        ("KIS_BASE_URL", base_url),
    ) if not value]
    if missing:
        # 설정 값과 누락 항목은 오류 문구에 포함하지 않는다.
        raise KisError("KIS 설정이 없습니다.")
    return app_key, app_secret, _production_base_url(base_url)


def _issue_token(client: httpx.Client, app_key: str, app_secret: str, *, execution_context=None) -> dict:
    """발급 JSON의 원형 token/TTL을 검증한다. 원문 예외·응답은 노출하지 않는다."""
    try:
        kwargs={} if execution_context is None else {"timeout":execution_context.timeout("kis_token", _TIMEOUT)}
        identity=execution_context.begin_call('kis','token') if execution_context is not None else None
        resp = client.post(
            _OAUTH_PATH,
            json={"grant_type": "client_credentials",
                  "appkey": app_key, "appsecret": app_secret},
            **kwargs,
        )
        if execution_context is not None:
            execution_context.http_observed(identity,resp.status_code)
            execution_context.check('kis_token_result')
        if resp.status_code != 200:
            raise KisError("KIS 토큰 발급 실패.")
        body = resp.json()
        validate_issued_response(body)
        return body
    except (DeadlineExceeded, httpx.TimeoutException, TimeoutError):
        raise DeadlineExceeded("KIS deadline exceeded") from None
    except Exception:
        raise KisError("KIS 토큰 발급 실패.") from None


# 주입 base 경로는 파일명 계산의 기준일 뿐, 이 legacy 파일은 읽거나 변경하지 않는다.
_TOKEN_CACHE_PATH = Path.home() / ".cache" / "verith" / "kis_token.json"


def _get_token(client: httpx.Client, app_key: str, app_secret: str, base_url: str, *, execution_context=None) -> str:
    """서버/자격 문맥별 캐시. 실발급 single-flight나 반응형 재발급은 보장하지 않는다."""
    timed_out = False
    def issue():
        nonlocal timed_out
        try:
            return _issue_token(client, app_key, app_secret, execution_context=execution_context)
        except (DeadlineExceeded, httpx.TimeoutException, TimeoutError):
            timed_out = True
            raise DeadlineExceeded("KIS deadline exceeded") from None
    try:
        return get_token(_TOKEN_CACHE_PATH, base_url, app_key, app_secret, time.time(), issue)
    except TokenCacheError:
        if timed_out:raise DeadlineExceeded("KIS deadline exceeded") from None
        raise KisError("KIS 토큰 캐시 처리 실패.") from None


def _auth_headers(app_key: str, app_secret: str, token: str, tr_id: str) -> dict:
    """KIS 조회 공통 헤더. TR마다 tr_id만 다르다."""
    return {
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
        "custtype": "P",
    }


def _get_json(client: httpx.Client, path: str, headers: dict, params: dict, what: str, *, execution_context=None) -> dict:
    """조회 GET 의 HTTP 층 공통 경로 — 실패 처리를 한 곳에 모은다.

    유일한 재시도: KIS 유량 제어 신호(HTTP 500 + EGW00201)에 한해 0.6초 대기 후
    딱 1회. 문서화된 흐름 제어에 대한 규정된 대응이지, 원인 불명 실패의 연쇄
    시도가 아니다 — 그 외 모든 실패는 즉시 고정 오류로 닫고 원문은 내보내지 않는다.
    """
    try:
        for attempt in (1, 2):
            kwargs = {} if execution_context is None else {"timeout":execution_context.timeout("kis_data", _TIMEOUT)}
            action='supply' if path==_QUOTATIONS_PATH else 'quotes' if path==_DAILY_PRICE_PATH else None
            if execution_context is not None and action is None:raise ValueError('Unknown KIS action')
            identity=execution_context.begin_call('kis',action) if execution_context is not None else None
            resp = client.get(path, headers=headers, params=params, **kwargs)
            if execution_context is not None:
                execution_context.http_observed(identity,resp.status_code)
                execution_context.check("kis_data_result")
            if resp.status_code == 200:
                return resp.json()
            try:
                body = resp.json()
                msg_cd = body.get("msg_cd") if isinstance(body,dict) else None
            except ValueError:
                msg_cd = None
            if attempt == 1 and resp.status_code == 500 and msg_cd == _RATE_LIMIT_MSG_CD:
                if execution_context is not None: execution_context.wait_allowed(_RATE_LIMIT_RETRY_WAIT_SEC)
                time.sleep(_RATE_LIMIT_RETRY_WAIT_SEC)
                continue
            raise KisError("KIS 조회 실패.")
    except (DeadlineExceeded, httpx.TimeoutException, TimeoutError):
        raise DeadlineExceeded("KIS deadline exceeded") from None
    except Exception:
        raise KisError("KIS 조회 실패.") from None
    raise AssertionError("unreachable")


def fetch_supply_demand(
    base_date: date | str,
    ticker: str,
    *, execution_context=None,
) -> tuple[pd.DataFrame, str | None]:
    """기준일(base_date)까지의 일별 투자자매매동향을 signals 스키마로 반환한다.

    Args:
        base_date: 조회 기준일. date 또는 "YYYYMMDD" 문자열. 실측(2026-07-06):
                   휴장일 요청은 마지막 거래일로 클램프되고, 오늘(장중) 요청은
                   에러가 아니라 미확정 행을 조용히 준다 — 확정일 보장은 KIS 가
                   아니라 게이트1(18시 규칙)의 책임이다.
        ticker:    6자리 종목코드. 기본값 없음 — 경계 번역기는 "선호 종목"을
                   모른다. 호출부(그래프)가 반드시 지정한다(조각2).

    Returns:
        (df, market) 튜플:
          df     : index=날짜(오름차순), columns=[개인, 외국인, 기관, 거래대금
                   (+기관 세부 7주체)]. 모든 값 단위는 백만원.
          market : output1.rprs_mrkt_kor_name 원본 그대로(실측: 'KOSPI200',
                   'KSQ150'). 없으면 None. 표시 전용 문자열이라 게이트2 검증
                   대상이 아니며(숫자 아님·대조할 제2 출처 없음), 매핑·가공도
                   하지 않는다(우리 해석 금지 — 원본 이름 그대로).
    """
    if execution_context is not None: execution_context.check('kis_credentials')
    app_key, app_secret, base_url = _load_credentials()
    date_str = base_date.strftime("%Y%m%d") if isinstance(base_date, date) else str(base_date)

    with httpx.Client(base_url=base_url, timeout=_TIMEOUT) as client:
        token = _get_token(client, app_key, app_secret, base_url, **({} if execution_context is None else {"execution_context":execution_context}))
        body = _get_json(
            client, _QUOTATIONS_PATH,
            headers=_auth_headers(app_key, app_secret, token, _TR_ID),
            params={  # KIS 공식 예제 기준 파라미터 세트(scratch_kis.py로 확인)
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker,
                "FID_INPUT_DATE_1": date_str,
                "FID_ORG_ADJ_PRC": "",
                "FID_ETC_CLS_CODE": "",
            },
            what="투자자매매동향",
            **({} if execution_context is None else {"execution_context":execution_context}),
        )

    if body.get("rt_cd") != "0":
        # 업무 실패도 원문/종목/날짜를 내보내지 않고 멈춘다(재시도 없음).
        raise KisError("KIS 투자자매매동향 조회 실패.")
    rows = body.get("output2") or []
    if not rows:
        raise KisError("KIS 투자자매매동향 결과가 없습니다.")

    market = (body.get("output1") or {}).get("rprs_mrkt_kor_name") or None
    return _to_signals_frame(rows), market


def _to_signals_frame(rows: list[dict]) -> pd.DataFrame:
    """KIS output2(내림차순 원본) → signals 스키마 DataFrame(오름차순, 백만원)."""
    # (1) 필드 매핑: KIS 필드명을 signals 컬럼명으로 갈아끼운다(세부 7주체 포함).
    full_map = {**_FIELD_MAP, **_DETAIL_FIELD_MAP}
    records = [{col: row[kis] for kis, col in full_map.items()} for row in rows]
    dates = [row[_DATE_FIELD] for row in rows]

    df = pd.DataFrame.from_records(records)
    # KIS 값은 문자열 → 숫자. 예상 밖 값이면 조용히 넘기지 않고 에러(실패는 정보).
    df = df.apply(pd.to_numeric, errors="raise")

    # 날짜 문자열 → datetime index(이름 "날짜"), signals/fixtures와 동일한 형태.
    df.index = pd.to_datetime(dates, format="%Y%m%d")
    df.index.name = "날짜"

    # (3) 단위 통일: acml_tr_pbmn(원) ÷ 1,000,000 → 백만원(순매수와 같은 단위).
    #     이 한 줄이 없으면 강도(순매수/거래대금)가 100만 배 어긋난다.
    df[COL_VALUE] = df[COL_VALUE] / 1_000_000

    # (2) 정렬: 날짜 오름차순(과거→최신). KIS 내림차순을 뒤집어 signals의
    #     tail(5)·reversed 순회 전제와 정확히 맞춘다.
    df = df.sort_index()

    # (4) 컬럼 순서를 signals 스키마와 정확히 일치시켜 반환
    #     (+ 기관 세부 7주체 + 순매매량[주] 2컬럼 — 날짜별 시세 표용).
    return df[[COL_INDI, COL_FORE, COL_INST, COL_VALUE, *INST_DETAIL,
               COL_FORE_QTY, COL_INST_QTY]]


def fetch_daily_quotes(
    base_date: date | str,
    ticker: str,
    *, execution_context=None,
) -> pd.DataFrame:
    """base_date까지의 일자별 시세를 오름차순 DataFrame으로 반환한다.

    컬럼: 종가·전일비(원), 등락률(%), 거래량·외국인순매매량(주),
    외국인한도소진율(%) — 전부 한 API(FHKST01010400)의 같은 행에서 나온다.
    소진율과 시세 표가 이 함수 하나를 공유해 KIS 호출은 리포트당 1회다.

    실물로 확인된 변환 3가지(scratch_kis_ehrt.py·scratch_kis_daily_price.py):
      (1) 필드: 모듈 상단 _*_FIELD 상수 참조 (전일비는 부호 포함,
          항등식 전일비=종가차·등락률=전일비÷전일종가 실측 성립)
      (2) 정렬: KIS 내림차순 → 오름차순으로 뒤집는다
      (3) 절단: 이 API는 오늘(장중 미확정) 행을 포함한다(매매동향 API와 다름!)
          → base_date 이후 행을 잘라내 리포트 기준일과 정합시킨다.
    """
    if execution_context is not None: execution_context.check('kis_credentials')
    app_key, app_secret, base_url = _load_credentials()
    date_str = base_date.strftime("%Y%m%d") if isinstance(base_date, date) else str(base_date)

    with httpx.Client(base_url=base_url, timeout=_TIMEOUT) as client:
        token = _get_token(client, app_key, app_secret, base_url, **({} if execution_context is None else {"execution_context":execution_context}))
        body = _get_json(
            client, _DAILY_PRICE_PATH,
            headers=_auth_headers(app_key, app_secret, token, _DAILY_PRICE_TR_ID),
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker,
                "FID_PERIOD_DIV_CODE": "D",   # 일별
                "FID_ORG_ADJ_PRC": "0",       # 수정주가 반영
            },
            what="일자별 시세",
            **({} if execution_context is None else {"execution_context":execution_context}),
        )

    if body.get("rt_cd") != "0":
        raise KisError("KIS 일자별 시세 조회 실패.")
    rows = body.get("output") or []          # 주의: 이 API는 output2가 아니라 output
    if not rows:
        raise KisError("KIS 일자별 시세 결과가 없습니다.")

    field_to_col = {
        _CLOSE_FIELD: COL_CLOSE, _CHANGE_FIELD: COL_CHANGE, _RATE_FIELD: COL_CHANGE_RATE,
        _VOL_FIELD: COL_VOLUME, _EHRT_FIELD: COL_OWNERSHIP,
    }
    quotes = pd.DataFrame(
        {col: [row[field] for row in rows] for field, col in field_to_col.items()},
        index=pd.to_datetime([row[_DATE_FIELD] for row in rows], format="%Y%m%d"),
    )
    quotes = quotes.apply(pd.to_numeric, errors="raise")  # 예상 밖 값이면 멈춤(실패는 정보)
    quotes.index.name = "날짜"
    quotes = quotes.sort_index()                          # (2) 오름차순

    # (3) base_date 이후 절단 — 장중(미확정) 행이 리포트에 섞이는 것을 구조로 차단.
    quotes = quotes.loc[: pd.to_datetime(date_str, format="%Y%m%d")]
    if quotes.empty:
        raise KisError("KIS 기준일 이전 시세 결과가 없습니다.")
    return quotes


def fetch_foreign_ownership(
    base_date: date | str,
    ticker: str,
) -> pd.Series:
    """base_date까지의 일별 외국인 한도소진율(%)을 오름차순 Series로 반환한다.

    fetch_daily_quotes 의 소진율 컬럼을 꺼내는 얇은 래퍼(같은 API·같은 행) —
    독립 호출부 호환용으로 남긴다. 그래프는 fetch_daily_quotes 하나만 불러
    시세와 소진율을 함께 얻는다(호출 1회).

    의미(실물 확인 — SKT 소진율 77.28% vs 실보유 ~38%): hts_frgn_ehrt 는
    외국인 '한도 대비' 소진 비율이다. 한도 100% 종목(삼성전자 등 대부분)은
    보유율과 같지만 한도 제한 종목(통신·항공)은 전혀 다르다 — 그래서 이름도
    소진율로 부른다(라벨 정직성). 보유율 환산은 한도 데이터가 확실해지면 별도 결정.
    """
    return fetch_daily_quotes(base_date, ticker)[COL_OWNERSHIP]
