"""render/builder.py — 신호·검증 → HTML 리포트 한 장.

원리: "render는 표시만 한다."
  계산·검증은 signals.py·verify_rules.py가 이미 끝냈다. 여기서는 그 결과를
  받아 사람이 읽을 화면으로 '그리기만' 한다 — 숫자를 다시 계산하거나 단위를
  바꾸지 않는다(진실은 한 곳). 허용되는 건 표시용 포맷(부호·백분율·막대 폭)과
  이미 있는 값의 재표현(분류·문구 조립)뿐. signals dict는 절대 수정하지 않는다.

입력:
  signals : compute_signals(df) 결과 dict
  gate2   : verify_signals(df, signals) 결과 GateResult
  meta    : {"stock_name","ticker","base_date"} 표시용 메타
  interpretation : 게이트3 통과분만 그래프가 넘김(없으면 None → placeholder)
출력:
  HTML 문자열 한 장 (자체 CSS 포함, 외부 링크 없음 — iframe 취합 대비).
"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from ... import config
from ...domain.signals import COL_FORE, COL_INST, INST_DETAIL, SUBJECTS
from ...domain.models import GateResult
from ...domain.observation_window import finite_number, observation_window, relation_text, safe_daily

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATE_NAME = "supply_demand.html"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _display_number(value, precision=0, unit="", scale=1, signed=True):
    """Presentation wrapper preserves the raw nonzero sign before unit underflow."""
    if not finite_number(value):
        return "자료 없음"
    nonzero, positive = value != 0, value > 0
    try:
        shown = value * scale
    except OverflowError:
        return "표시 범위 초과"
    if not finite_number(shown):
        return "표시 범위 초과"
    text = f"{abs(shown):,.{precision}f}"
    if nonzero and (shown == 0 or float(text.replace(",", "")) == 0):
        return ("양수" if positive else "음수") + f"·표시 정밀도 미만({unit})"
    return ("-" if shown < 0 else "+" if signed and shown > 0 else "") + text + unit


def _record(value):
    return value if type(value) is dict else {}


def _direction(value):
    return "판단 보류" if not finite_number(value) else "매수" if value > 0 else "매도" if value < 0 else "중립"


def _fact_rows(signals: dict) -> list[dict]:
    consecutive = _record(signals.get("consecutive"))
    strength = _record(signals.get("strength"))
    persistence = _record(signals.get("persistence"))
    ratios = {name: _record(strength.get(name)).get("ratio") for name in SUBJECTS}
    max_abs = max((abs(v) for v in ratios.values() if finite_number(v)), default=0)
    rows = []
    for name in SUBJECTS:
        claim = _record(consecutive.get(name))
        raw = ratios[name]
        ratio = raw if finite_number(raw) else None
        days = claim.get("days")
        days = days if type(days) is int and days >= 0 else None
        amount = _record(persistence.get(name)).get("sum_5")
        rows.append(dict(name=name, days=days, consec_signal=days is not None and claim.get("signal") is True,
            ratio=ratio, strong=ratio is not None and _record(strength.get(name)).get("strong") is True,
            direction=_direction(ratio), pct=_display_number(ratio, 1, "%", 100),
            amt=_display_number(amount, 1, "억원", .01) if finite_number(amount) else None,
            bar_w=round(abs(ratio) / max_abs * 50, 1) if ratio is not None and max_abs else 0))
    return rows


def _gauge(signals: dict) -> dict:
    strength = _record(signals.get("strength"))
    fore, inst = (_record(strength.get(name)).get("ratio") for name in (COL_FORE, COL_INST))
    verdict, total = "판단 보류", None
    if finite_number(fore) and finite_number(inst):
        total = fore + inst
        if finite_number(total):
            verdict = "매수 우위" if total > 0 else "매도 우위" if total < 0 else "중립"
    if verdict == "매수 우위":
        return dict(verdict=verdict, color="#F04452", arc="M 140 30 A 110 110 0 0 1 237.1 88.4", knob_x=237.1, knob_y=88.4)
    if verdict == "매도 우위":
        return dict(verdict=verdict, color="#3182F6", arc="M 42.9 88.4 A 110 110 0 0 1 140 30", knob_x=42.9, knob_y=88.4)
    return dict(verdict=verdict, color="#8B95A1", arc=None, knob_x=140, knob_y=30)


def _daily_view(signals: dict) -> list[dict] | None:
    """일별 팩트 → 차트 표시용 뷰. 값 변형 없음 — 표시 스케일·포맷만.

    h 는 기간 내 최대 |값| 을 48%(트랙 반높이 여유분)로 놓은 상대 막대 높이
    — M1 게이지·강도 바와 같은 '표시 스케일' 범주다. 값 텍스트는 천단위
    콤마 포맷뿐, 단위는 팩트 그대로 백만원(변환 없음). daily 가 없으면
    None → 템플릿이 placeholder 로 후퇴(구버전 신호 dict 방어).
    """
    daily = safe_daily(signals)
    if daily is None:
        return None
    max_abs = max(
        (abs(row[s]) for row in daily for s in SUBJECTS), default=0.0
    )
    view = []
    for row in daily:
        bars = []
        for s in SUBJECTS:
            v = row[s]
            bars.append({
                "subject": s,
                "cls": "buy" if v > 0 else "sell" if v < 0 else "mut",
                "h": round(abs(v) / max_abs * 48.0, 1) if max_abs and v else 0.0,
                "val": _display_number(v),
            })
        iso = row.get("date", "")
        view.append({"iso": iso, "label": iso[5:].replace("-", "/"), "bars": bars})
    return view


def _persistence_view(signals: dict, window: dict | None = None) -> dict:
    """Read stored sums only; missing/invalid cells are never replaced by zero."""
    if window is None:
        window = observation_window(signals, config.RECENT_DAYS, config.TREND_DAYS)
    raw = signals.get("persistence")
    persistence = raw if type(raw) is dict else {}
    values = [p.get(key) for subject in SUBJECTS
              if type(p := persistence.get(subject)) is dict
              for key in ("sum_5", "sum_20") if finite_number(p.get(key))]
    max_abs = max((abs(value) for value in values), default=0.0)
    rows = []
    for subject in SUBJECTS:
        raw_claim = persistence.get(subject)
        claim = raw_claim if type(raw_claim) is dict else {}
        row = {"name": subject, "consistent": (claim.get("consistent")
               if window["status"] == "sufficient_rows" else None)}
        for key, out in (("sum_5", "d5"), ("sum_20", "d20")):
            value = claim.get(key)
            available = finite_number(value)
            row[out] = {"val": _display_number(value),
                        "cls": "buy" if available and value > 0 else "sell" if available and value < 0 else "mut",
                        "w": round(abs(value) / max_abs * 100.0, 1) if available and max_abs else 0.0,
                        "available": available}
        rows.append(row)
    verdict = " · ".join(f"{subject}은 {relation_text(window['relations'][subject])}" for subject in SUBJECTS) if window["status"] == "sufficient_rows" else ""
    return {"rows": rows, "verdict": verdict}


def _ownership_view(signals: dict) -> dict | None:
    raw = signals.get("ownership")
    if type(raw) is not list:
        return None
    rows = [r for r in raw if type(r) is dict and type(r.get("date")) is str and finite_number(r.get("ratio"))]
    if not rows:
        return None
    ratios = [r["ratio"] for r in rows]
    lo, hi = min(ratios), max(ratios)
    span, delta = hi-lo, ratios[-1]-ratios[0]
    if not finite_number(span) or not finite_number(delta):
        return None
    bars = [dict(iso=r["date"], label=r["date"][5:].replace("-", "/"), num=_display_number(r["ratio"], 2, signed=False),
        h=round(26+(r["ratio"]-lo)/span*64 if span else 55, 1)) for r in rows]
    return dict(bars=bars, latest=_display_number(ratios[-1], 2, "%", signed=False), delta=_display_number(delta, 2, "%p"),
        delta_cls="buy" if delta > 0 else "sell" if delta < 0 else "mut", delta_arrow="▲" if delta > 0 else "▼" if delta < 0 else "―")


# 표시용 라벨: KIS 공식명 기본 + 통칭 병기(확인 가능성 — 원본과 같은 이름).
_DETAIL_LABELS = {"기금": "기금(연기금)", "증권": "증권(금융투자)"}
# 목업이 보여주는 5개(검증은 7개 전체, 표시는 이 5개만).
_DETAIL_DISPLAY = ("기금", "증권", "투자신탁", "사모펀드", "보험")


def _inst_detail_view(signals: dict) -> dict | None:
    detail = _record(signals.get("inst_detail"))
    shown = [(name, detail.get(name)) for name in _DETAIL_DISPLAY if finite_number(detail.get(name))]
    if not shown:
        return None
    shown.sort(key=lambda pair: pair[1], reverse=True)
    max_abs = max(abs(value) for _, value in shown)
    rows = [dict(label=_DETAIL_LABELS.get(name, name), val=_display_number(value),
        cls="buy" if value > 0 else "sell" if value < 0 else "mut",
        w=round(abs(value) / max_abs * 100, 1) if max_abs else 0) for name, value in shown]
    name, value = shown[0]
    leader = f"{_DETAIL_LABELS.get(name, name)} 주도" if value > 0 else "표시된 세부 중 순매수 없음(0 포함)" if value == 0 else "표시된 세부 값은 모두 순매도"
    return dict(rows=rows, leader=leader)


def _price_table_view(signals: dict) -> list[dict] | None:
    price = signals.get("price_daily")
    if type(price) is not list or not price:
        return None
    def quantity(value):
        return dict(txt=_display_number(value), cls="buy" if finite_number(value) and value > 0 else "sell" if finite_number(value) and value < 0 else "mut")
    rows = []
    for row in reversed(price):
        if type(row) is not dict or type(row.get("date")) is not str:
            continue
        change = row.get("change")
        arrow = "▲ " if finite_number(change) and change > 0 else "▼ " if finite_number(change) and change < 0 else "― " if finite_number(change) else ""
        rows.append(dict(label=row["date"][5:].replace("-", "/"), close=_display_number(row.get("close"), signed=False),
            chg=arrow+_display_number(change, signed=False).lstrip("-"), chg_cls=quantity(change)["cls"],
            rate=_display_number(row.get("change_rate"), 2, "%"), vol=_display_number(row.get("volume"), signed=False),
            inst=quantity(row.get("inst_qty")), fore=quantity(row.get("frgn_qty"))))
    return rows or None


# 해석 강조 마커(**…**) — 프롬프트가 1~2곳만 허용한 볼드 표시.
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _interpretation_html(text: str | None) -> Markup | None:
    """해석의 **강조** 마커 → <b>, 줄바꿈 → 문단(<p>) (표시용 마크업 변환만).

    본문 전체를 escape 한 뒤 우리 마커만 태그로 바꾼다 — LLM 이 HTML 을
    흘려도 문자 그대로 보이고, 허용되는 마크업은 볼드·문단 둘뿐이다.
    문단은 프롬프트가 지시한 빈 줄(또는 단일 줄바꿈) 기준으로 나눈다.
    """
    if text is None:
        return None
    escaped = _BOLD_RE.sub(r"<b>\1</b>", str(escape(text)))
    paragraphs = [p.strip() for p in re.split(r"\n+", escaped) if p.strip()]
    return Markup("".join(f"<p>{p}</p>" for p in paragraphs))


def _header_price(signals: dict) -> dict | None:
    rows = _price_table_view(signals)
    if not rows:
        return None
    row = rows[0]
    return dict(close=row["close"], chg=row["chg"], rate="("+row["rate"]+")", cls=row["chg_cls"])


def _headline(rows: list[dict]) -> str:
    """요약 헤드라인 — 각 주체 direction(이미 확정된 부호의 단어)을 문구로 조립.

    표시용 문구 조립일 뿐, 방향 자체는 rows 의 direction 을 그대로 쓴다.
    """
    buyers = [r["name"] for r in rows if r["direction"] == "매수"]
    sellers = [r["name"] for r in rows if r["direction"] == "매도"]
    if buyers and sellers:
        return f"{'·'.join(buyers)}이 사고, {'·'.join(sellers)}이 파는 국면"
    if buyers:
        return f"{'·'.join(buyers)} 매수 국면"
    if sellers:
        return f"{'·'.join(sellers)} 매도 국면"
    return "자료 부족으로 방향 판단 보류" if any(r["direction"] == "판단 보류" for r in rows) else "방향이 뚜렷하지 않은 국면"


def build_report(
    signals: dict,
    gate2: GateResult,
    meta: dict,
    interpretation: str | None = None,
    gate1: GateResult | None = None,   # 게이트1(입력 검증) — None이면 배지 생략(구버전 호환)
) -> str:
    """신호·게이트2·메타(+선택적 해석)를 받아 HTML 리포트 문자열을 반환한다.

    render는 표시 전용: interpretation은 '있으면 그대로 그리고 없으면 placeholder'.
    "게이트3 통과분만 넘긴다"는 판정은 그래프가 하고, 여기선 판단·가공하지 않는다.
    """
    rows = _fact_rows(signals)
    observation = observation_window(signals, config.RECENT_DAYS, config.TREND_DAYS)
    context = {
        "observation": observation,
        "meta": meta,
        "market": meta.get("market"),       # KIS 대표 시장명 원본. None → 템플릿이 칩 생략
        "gate1": gate1,                     # None이면 템플릿이 배지 생략
        "gate2": gate2,
        "rows": rows,
        "alignment": signals.get("alignment"),
        "gauge": _gauge(signals),
        "headline": _headline(rows),
        "interpretation": interpretation,   # None이면 템플릿이 placeholder로 후퇴
        "interpretation_html": _interpretation_html(interpretation),  # **…** → <b>
        "daily": _daily_view(signals),      # None이면 템플릿이 placeholder로 후퇴
        "persistence": _persistence_view(signals, observation),  # None이면 placeholder로 후퇴
        "inst_detail": _inst_detail_view(signals),  # None이면 placeholder로 후퇴
        "ownership": _ownership_view(signals),      # None이면 placeholder로 후퇴
        "price_table": _price_table_view(signals),  # None이면 placeholder로 후퇴
        "price_days": config.PRICE_TABLE_DAYS,
        "header_price": _header_price(signals),     # None이면 헤더는 종전대로
        # 임계값 표기는 config 를 '표시'하는 것(재계산 아님).
        "consec_threshold": config.CONSECUTIVE_THRESHOLD,
        "strength_threshold": f"{config.STRENGTH_THRESHOLD * 100:.0f}%",
        "recent_days": config.RECENT_DAYS,
        "trend_days": config.TREND_DAYS,
        "disclaimer": "본 리포트는 투자 자문이 아니며 과거 수급 데이터 기반 참고 자료입니다.",
    }
    template = _env.get_template(_TEMPLATE_NAME)
    return template.render(**context)
