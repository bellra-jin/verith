"""Read-only display evidence from existing v1 fields, never market coverage.

Stdlib only. No I/O, config/producer imports, payload changes or stored-value
replacement. Counts describe supplied rows; sums below only cross-check evidence.
"""
from datetime import date
import math

SUBJECTS = ("개인", "외국인", "기관")


def finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def iso_date(value):
    if type(value) is not str or len(value) != 10:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def safe_daily(signals):
    """All-or-placeholder display rows. Never drop, sort, fill or repair a row."""
    daily = signals.get("daily") if type(signals) is dict else None
    if type(daily) is not list or not daily or len(daily) > 20:
        return None
    rows = []
    for row in daily:
        if type(row) is not dict or not iso_date(row.get("date")):
            return None
        if not all(finite_number(row.get(subject)) for subject in SUBJECTS):
            return None
        if rows and rows[-1]["date"] >= row["date"]:
            return None
        rows.append({"date": row["date"], **{subject: row[subject] for subject in SUBJECTS}})
    return rows


def _sum_rows(rows, subject):
    # Explicit sequential binary64 addition, matching JS reduce. Python 3.12
    # built-in sum uses compensation and must not decide different view evidence.
    total = 0.0
    for row in rows:
        total = total + float(row[subject])
    return total


def _sign(value):
    return 1 if value > 0 else -1 if value < 0 else 0


def _relation(short, long):
    if short == 0 or long == 0:
        return "neutral"
    if _sign(short) != _sign(long):
        return "opposite"
    return "buy" if short > 0 else "sell"


def relation_text(relation):
    return {"buy": "단기·장기 모두 순매수", "sell": "단기·장기 모두 순매도",
            "opposite": "단기·장기 방향 차이", "neutral": "합 0 포함 · 판단 보류"}.get(relation, "지속성 비교 보류")


def observation_window(signals, recent_days, trend_days):
    raw = signals.get("daily") if type(signals) is dict else None
    shown = len(raw) if type(raw) is list else None
    rows = safe_daily(signals)
    result = {"status": "unknown", "shownRows": shown, "shortCount": None, "longCount": None,
              "notice": "계산창 관측기간 미확인 · 지속성 비교 보류",
              "shortLabel": "단기 합 (기간 미확인)", "longLabel": "장기 합 (기간 미확인)",
              "dailyLabel": (f"표시 {shown}행 · 계산창 관측기간 미확인" if rows is not None
                             else f"제공된 일별자료 {shown}행 · 표시 미확인" if shown is not None
                             else "제공된 일별자료 · 표시 미확인"),
              "interpretationNotice": "저장 당시 해석 · 관측기간 미확인, 아래 원문의 기간 주장은 현재 보증되지 않음",
              "relations": {subject: "unknown" for subject in SUBJECTS}}
    if (type(recent_days) is not int or type(trend_days) is not int
            or not 1 <= recent_days <= trend_days <= 20 or rows is None
            or not 1 <= len(rows) <= trend_days):
        return result
    dates = [row["date"] for row in rows]
    if any(a >= b for a, b in zip(dates, dates[1:])):
        return result
    persistence = signals.get("persistence")
    if type(persistence) is not dict:
        return result
    relations = {}
    for subject in SUBJECTS:
        claim = persistence.get(subject)
        if type(claim) is not dict or type(claim.get("consistent")) is not bool:
            return result
        short, long = claim.get("sum_5"), claim.get("sum_20")
        if not finite_number(short) or not finite_number(long):
            return result
        derived_short = _sum_rows(rows[-recent_days:], subject)
        derived_long = _sum_rows(rows[-trend_days:], subject)
        if not finite_number(derived_short) or not finite_number(derived_long):
            return result
        if not all(math.isclose(float(stored), derived, rel_tol=1e-9, abs_tol=1e-6)
                   and _sign(stored) == _sign(derived)
                   for stored, derived in ((short, derived_short), (long, derived_long))):
            return result
        consistent = _sign(derived_short) == _sign(derived_long) != 0
        stored_consistent = _sign(short) == _sign(long) != 0
        if claim["consistent"] != consistent or claim["consistent"] != stored_consistent:
            return result
        relations[subject] = _relation(short, long)
    count = len(rows)
    short_count = min(count, recent_days)
    sufficient = count == trend_days
    result.update(status="sufficient_rows" if sufficient else "insufficient",
                  shortCount=short_count, longCount=count,
                  shortLabel=f"단기 제공 {short_count}개", longLabel=f"장기 제공 {count}개",
                  dailyLabel=f"제공된 일별자료 {count}행")
    if sufficient:
        result.update(notice=f"제공 자료 기준 단기 {short_count}개·장기 {count}개 관측 비교",
                      interpretationNotice="저장 당시 해석 · 제공 자료 행수 정합만 확인했으며 거래일 완비·원천 계산창을 보증하지 않음",
                      relations=relations)
    else:
        result["notice"] = (f"제공 관측 {count}개 · {recent_days}/{trend_days}개 기준 자료 부족 · 지속성 비교 보류"
                            if count < recent_days else
                            f"제공 자료 기준 단기 {short_count}개·장기 {count}개 관측 · 장기 관측 부족 · 지속성 비교 보류")
        result["interpretationNotice"] = "저장 당시 해석 · 관측기간 부족, 아래 원문의 기간 주장은 현재 보증되지 않음"
    return result
