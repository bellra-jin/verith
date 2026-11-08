"""Bounded immutable evidence menu, strict ID selection and code-owned prose.

No provider, config, pandas, I/O or payload mutation. Raw evidence is frozen as
canonical JSON; a bank is independently rebuilt before composition/verification.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re

from .observation_window import finite_number, iso_date, observation_window, relation_text
from .verification.consecutive import verify_consecutive

POLICY_ID = "flow.fact-selection.v1"
SUBJECTS = ("개인", "외국인", "기관")


class SelectionInvalid(ValueError):
    def __init__(self):
        super().__init__("Invalid grounded selection")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def sign(value):
    return 1 if value > 0 else -1 if value < 0 else 0


def matches(claim, actual):
    return (finite_number(claim) and finite_number(actual) and sign(claim) == sign(actual)
            and math.isclose(claim, actual, rel_tol=1e-9, abs_tol=1e-6))


def formatted(value, precision, unit, *, scale=1):
    """One conversion/formatter; a rounded nonzero never becomes measured zero."""
    shown = value * scale
    if not finite_number(shown):
        raise SelectionInvalid()
    text = f"{abs(shown):,.{precision}f}"
    if shown != 0 and float(text.replace(",", "")) == 0:
        return ("양수" if value > 0 else "음수") + f"·표시 정밀도 미만({unit})"
    return ("+" if value > 0 else "-" if value < 0 else "") + text + unit


@dataclass(frozen=True)
class Fact:
    id: str
    kind: str
    subject: str
    dates: tuple[str, ...]
    unit: str
    values: tuple[int | float, ...]
    signs: tuple[int, ...]
    precision: int
    sentence: str


@dataclass(frozen=True)
class FactBank:
    meta_json: str
    evidence_json: str
    signals_json: str
    recent_days: int
    trend_days: int
    threshold: int
    facts: tuple[Fact, ...]
    skeleton: tuple[str, ...]
    notice: str


def _rows(rows, columns, confirmed):
    if type(rows) is not list or not 1 <= len(rows) <= 4096:
        return False
    previous = None
    for row in rows:
        if (type(row) is not dict or not iso_date(row.get("date"))
                or previous is not None and previous >= row["date"]
                or not all(finite_number(row.get(column)) for column in columns)):
            return False
        previous = row["date"]
    return previous == confirmed


def _build_bank(signals, evidence, meta, *, gate2_passed, recent_days=5, trend_days=20, threshold=3):
    """Issue only independently matched claims; missing evidence is never zero."""
    if (gate2_passed is not True or type(signals) is not dict or type(evidence) is not dict
            or type(meta) is not dict or not iso_date(meta.get("base_date"))
            or type(meta.get("ticker")) is not str or re.fullmatch(r"[0-9]{6}", meta["ticker"]) is None
            or type(recent_days) is not int or type(trend_days) is not int
            or not 1 <= recent_days <= trend_days <= 20 or type(threshold) is not int or threshold < 1):
        return None
    try:
        # Copy/freeze without retaining mutable references or nonfinite JSON.
        mj, ej, sj = canonical(meta), canonical(evidence), canonical(signals)
        meta, evidence, signals = json.loads(mj), json.loads(ej), json.loads(sj)
    except (ValueError, TypeError, OverflowError, RecursionError):
        return None
    confirmed = meta["base_date"]
    rows = evidence.get("supply")
    if not _rows(rows, SUBJECTS, confirmed):
        return None
    # The displayed tail is evidence from these exact supplied observations,
    # never an independent substitute for the raw window/count.
    daily = signals.get("daily")
    shown = rows[-trend_days:]
    if (type(daily) is not list or len(daily) != len(shown)
            or any(type(claim) is not dict or claim.get("date") != raw["date"]
                   or any(not matches(claim.get(subject), raw[subject]) for subject in SUBJECTS)
                   for claim, raw in zip(daily, shown))):
        return None
    dates = tuple(row["date"] for row in rows)
    recent = rows[-recent_days:]
    n = len(recent)
    facts, directions = [], []

    def add(kind, subject, source_dates, unit, values, precision, sentence):
        if not all(finite_number(value) for value in values):
            return
        binding = [POLICY_ID, mj, kind, subject, source_dates, unit, values, precision, sentence]
        digest = hashlib.sha256(canonical(binding).encode("utf-8")).hexdigest()
        facts.append(Fact(f"{kind}:{subject}:{digest}", kind, subject, tuple(source_dates), unit,
                          tuple(values), tuple(sign(v) for v in values), precision, sentence))

    sums = {subject: math.fsum(row[subject] for row in recent) for subject in SUBJECTS}
    if not all(finite_number(value) for value in sums.values()):
        return None
    alignment = ("동반매수" if sums["외국인"] > 0 and sums["기관"] > 0 else
                 "동반매도" if sums["외국인"] < 0 and sums["기관"] < 0 else "엇갈림")
    if signals.get("alignment") != alignment:
        return None
    denominator_values = [row.get("거래대금") for row in recent]
    denominator = (math.fsum(denominator_values) / n
                   if all(finite_number(v) for v in denominator_values) else None)
    usable_denominator = finite_number(denominator) and denominator > 0
    for subject in SUBJECTS:
        claim = signals.get("consecutive", {}).get(subject, {})
        if type(claim) is not dict or not verify_consecutive(
                [row[subject] for row in rows], claim.get("days"), claim.get("signal"), threshold,
                dates=dates, subject=subject):
            return None
        net = sums[subject]
        direction = "순매수" if net > 0 else "순매도" if net < 0 else "합 0·중립"
        directions.append(f"{subject}은 최근 실제 관측 {n}행 기준 {direction}")
        window_dates = tuple(row["date"] for row in recent)
        period = f"{window_dates[0]}~{confirmed} 최근 실제 관측 {n}행"
        add("supply", subject, window_dates, "million_KRW→억원", (net,), 1,
            f"{subject}의 {period} 순매수합은 {formatted(net, 1, '억원', scale=0.01)}이다.")
        days = claim["days"]
        add("consecutive", subject, dates, "observations", (days,), 0,
            f"{subject}의 {dates[0]}~{confirmed} 제공 관측 {len(rows)}행 내 최신 연속 순매수는 {days}행이다. 제공 이전 기간은 보증하지 않는다.")
        strength = signals.get("strength", {}).get(subject, {})
        ratio = strength.get("ratio") if type(strength) is dict else None
        if usable_denominator and matches(ratio, net / denominator):
            add("strength", subject, window_dates, "ratio→%", (ratio, net, denominator), 1,
                f"{subject}의 {period} 순매수 강도는 {formatted(ratio, 1, '%', scale=100)}이다"
                "(최근 실제 관측 순매수합 ÷ 동일 창의 종목 일평균 거래대금; 전체 거래대금 비중·보유율이 아니며 100% 초과 가능).")
    window = observation_window(signals, recent_days, trend_days)
    if window["status"] == "sufficient_rows":
        for subject in SUBJECTS:
            p = signals["persistence"][subject]
            actual_short = sums[subject]
            actual_long = math.fsum(row[subject] for row in rows[-trend_days:])
            if matches(p["sum_5"], actual_short) and matches(p["sum_20"], actual_long):
                add("persistence", subject, tuple(row["date"] for row in rows[-trend_days:]),
                    "million_KRW→억원", (p["sum_5"], p["sum_20"]), 1,
                    f"{subject}의 제공 자료 {dates[-trend_days]}~{confirmed}에서 최근 {n}행 합 "
                    f"{formatted(p['sum_5'], 1, '억원', scale=0.01)}, {trend_days}행 합 "
                    f"{formatted(p['sum_20'], 1, '억원', scale=0.01)}이며 {relation_text(window['relations'][subject])}이다.")
    quotes, price = evidence.get("quotes"), signals.get("price_daily")
    if (_rows(quotes, ("종가", "전일비", "등락률"), confirmed)
            and type(price) is list and price and type(price[-1]) is dict
            and price[-1].get("date") == confirmed):
        for column, key, label, unit, precision in (("종가", "close", "종가", "원", 0),
                ("전일비", "change", "전일 대비", "원", 0), ("등락률", "change_rate", "등락률", "%", 2)):
            raw = quotes[-1][column]
            if matches(price[-1].get(key), raw):
                add("price", key, (confirmed,), unit, (raw,), precision,
                    f"{confirmed} 확정일 시세의 {label}는 {formatted(raw, precision, unit)}이다.")
    ownership, claimed = evidence.get("ownership"), signals.get("ownership")
    if (_rows(ownership, ("value",), confirmed) and type(claimed) is list and claimed
            and len(claimed) == min(len(ownership), recent_days)):
        shown = ownership[-recent_days:]
        if all(type(c) is dict and c.get("date") == r["date"] and matches(c.get("ratio"), r["value"])
               for c, r in zip(claimed, shown)):
            first, last = shown[0]["value"], shown[-1]["value"]
            add("ownership", "외국인", (confirmed,), "%", (last,), 2,
                f"{confirmed} 외국인 한도소진율은 {formatted(last, 2, '%')}이다.")
            add("ownership", "외국인변화", tuple(r["date"] for r in shown), "%p", (last - first,), 2,
                f"외국인 한도소진율은 {shown[0]['date']}~{confirmed} 제공 관측 {len(shown)}행에서 "
                f"{formatted(last - first, 2, '%p')} 변했다.")
    if not usable_denominator:
        directions.append("강도 산출근거 부족: 동일 창의 일평균 거래대금 미확인; 기존 ratio 0 후퇴를 측정 0%로 해석하지 않는다")
    skeleton = (f"확정 거래일 {confirmed}, 종목 {meta['ticker']}. 외국인·기관 관계는 {alignment}이다(개인 제외).",
                " · ".join(directions) + ".")
    return FactBank(mj, ej, sj, recent_days, trend_days, threshold, tuple(facts[:24]), skeleton,
                    window["notice"] + " · 제공 자료 행수이며 시장 거래일 완비를 보증하지 않는다.")


def build_bank(signals, evidence, meta, *, gate2_passed, recent_days=5, trend_days=20, threshold=3):
    try:
        return _build_bank(signals, evidence, meta, gate2_passed=gate2_passed,
                           recent_days=recent_days, trend_days=trend_days, threshold=threshold)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
        return None


def valid_bank(bank, meta, signals):
    if type(bank) is not FactBank:
        return False
    try:
        return (canonical(meta) == bank.meta_json and canonical(signals) == bank.signals_json
                and build_bank(signals, json.loads(bank.evidence_json), meta, gate2_passed=True,
                    recent_days=bank.recent_days, trend_days=bank.trend_days, threshold=bank.threshold) == bank)
    except (ValueError, TypeError, OverflowError, AttributeError, RecursionError):
        return False


def parse_selection(raw, bank):
    try:
        if type(raw) is not str or not raw.strip() or len(raw.encode("utf-8")) > 4096:
            raise SelectionInvalid()
        def pairs(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise SelectionInvalid()
                value[key] = item
            return value
        value = json.loads(raw, object_pairs_hook=pairs)
        if (type(bank) is not FactBank or type(value) is not dict
                or set(value) != {"schema_version", "fact_ids"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 1):
            raise SelectionInvalid()
        ids = value["fact_ids"]
        known = {fact.id for fact in bank.facts}
        if (type(ids) is not list or not 1 <= len(ids) <= 8
                or any(type(i) is not str or not 1 <= len(i) <= 160 or i not in known for i in ids)
                or len(set(ids)) != len(ids)):
            raise SelectionInvalid()
        return tuple(ids)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise SelectionInvalid() from None


def compose(bank, selection, meta, signals):
    if not valid_bank(bank, meta, signals):
        raise SelectionInvalid()
    ids = parse_selection(canonical({"schema_version": 1, "fact_ids": list(selection)}), bank)
    chosen = [fact for fact in bank.facts if fact.id in ids]
    supply = [f.sentence for f in chosen if f.kind in ("supply", "strength", "consecutive")]
    context = [f.sentence for f in chosen if f.kind in ("price", "persistence", "ownership")]
    return "\n\n".join((" ".join(bank.skeleton), " ".join(supply) or "선택된 추가 수급 fact 없음.",
                          bank.notice + " " + (" ".join(context) or "선택된 추가 맥락 fact 없음.")))
