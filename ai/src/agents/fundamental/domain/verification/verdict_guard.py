from __future__ import annotations

import re
from math import isfinite
from dataclasses import dataclass
from typing import Any

from ..contracts import Evidence


FORBIDDEN_PATTERNS = (
    re.compile(r"(?<!아닙니다\s)(?<!아닌\s)(매수|매도|목표주가|적정주가|투자\s*추천)"),
)
UNSUPPORTED_METRICS = {
    "PER": re.compile(r"(?<![A-Za-z])PER(?![A-Za-z])", re.IGNORECASE),
    "PBR": re.compile(r"(?<![A-Za-z])PBR(?![A-Za-z])", re.IGNORECASE),
    "ROIC": re.compile(r"(?<![A-Za-z])ROIC(?![A-Za-z])", re.IGNORECASE),
    "주가": re.compile(r"(?<![가-힣])주가(?!치)"),
    "시가총액": re.compile(r"시가총액"),
}
PLACEHOLDER_PATTERNS = (
    re.compile(r"(한\s*문장|3\s*-\s*5\s*문장|one Korean sentence|3-5 Korean)", re.IGNORECASE),
)
BENCHMARK_NUMBERS = {0.0, 100.0}
EXTREME_PERCENT_LIMIT = 300.0


@dataclass
class GuardResult:
    ok: bool
    violations: list[str]


def _numbers(text: str) -> list[float]:
    values: list[float] = []
    for raw, unit, suffix in re.findall(r"([-+]?\d[\d,]*(?:\.\d+)?)\s*(%p|%|원|점)\s*([가-힣]{0,8})", text):
        if unit == "%p":
            continue
        normalized = raw.replace(",", "")
        try:
            value = float(normalized)
        except ValueError:
            continue
        if value > 0 and any(token in suffix for token in ("감소", "하락", "줄", "부진")):
            value = -value
        if 2020 <= value <= 2030:
            continue
        values.append(value)
    return values


def _extract_numbers(data: Any) -> list[float]:
    values: list[float] = []
    if isinstance(data, dict):
        for value in data.values():
            values.extend(_extract_numbers(value))
    elif isinstance(data, list):
        for value in data:
            values.extend(_extract_numbers(value))
    elif isinstance(data, (int, float)):
        values.append(float(data))
    return values


def _allowed_numbers(
    ratios: dict[str, Any],
    evidence: list[Evidence],
    trend: dict[str, Any] | None = None,
    insights: dict[str, Any] | None = None,
) -> list[float]:
    values: list[float] = []
    for item in ratios.values():
        value = item.get("value")
        if isinstance(value, (int, float)):
            if item.get("unit") == "%" and abs(float(value)) > EXTREME_PERCENT_LIMIT:
                continue
            values.append(float(value))
    values.extend(float(item.value) for item in evidence)
    if trend:
        for series in trend.values():
            if not isinstance(series, list):
                continue
            for value in series:
                if isinstance(value, (int, float)):
                    values.append(float(value))
    if insights:
        values.extend(_extract_numbers(insights))
    return values


def _matches_allowed(value: float, allowed: list[float], *, allow_benchmarks: bool = True) -> bool:
    if not isfinite(value):
        return False
    if allow_benchmarks and value in BENCHMARK_NUMBERS:
        return True
    for candidate in allowed:
        if not isfinite(candidate):
            continue
        if abs(value - candidate) <= 0.05:
            return True
        if abs(value - round(candidate, 1)) <= 0.05:
            return True
        if abs(value - round(candidate)) <= 0.05:
            return True
    return False



METRIC_CLAIM_ALIASES = {
    "roe": ("ROE", "자기자본이익률", "자기자본수익률"),
    "operating_margin": ("영업이익률",), "net_margin": ("순이익률",),
    "debt_ratio": ("부채비율", "부채 비율"), "current_ratio": ("유동비율", "유동 비율"),
    "revenue_growth": ("매출성장률", "매출 성장률", "매출액성장률", "매출 증가율"),
    "operating_income_growth": ("영업이익성장률", "영업이익 성장률", "영업이익 증가율"),
    "eps": ("EPS", "기본 EPS", "주당순이익"), "bps": ("BPS", "주당순자산"),
}


def _metric_claim_checks(text: str, ratios: dict[str, Any]) -> tuple[list[str], list[tuple[int, int]]]:
    # 명시적인 지표명+숫자 단언만 현재 지표에 묶는다. 복합/과거/기준 비교의 NLP 증명은 아니다.
    violations = []
    negated_spans = []
    body = (r"\s*(?:(?:의\s*)?(?:값|수치)\s*)?(?:은|는|이|가|:|=)?\s*(?:약\s*|대략\s*)?"
            r"([-+]?\d[\d,]*(?:\.\d+)?)\s*(%p|%|원|점)")
    all_names = "|".join(re.escape(alias).replace(r"\ ", r"\s*")
                         for aliases in METRIC_CLAIM_ALIASES.values() for alias in aliases)
    continuation = r"\s*(?:" + all_names + r")(?![A-Za-z])" + body
    for metric, aliases in METRIC_CLAIM_ALIASES.items():
        names = "|".join(re.escape(name).replace(r"\ ", r"\s*") for name in sorted(aliases, key=len, reverse=True))
        pattern = r"(?<![A-Za-z])(?:" + names + r")(?![A-Za-z])" + body
        item = ratios.get(metric) if isinstance(ratios.get(metric), dict) else {}
        for claim in re.finditer(pattern, text, re.IGNORECASE):
            raw, unit = claim.groups()
            if unit == "%p":
                continue  # 기존 percent-point 정책은 바꾸지 않는다.
            tail = text[claim.end():]
            if re.match(r"\s*(?:의\s*)?(?:기준|임계|경계|상한|하한|보다|이상|이하|미만|초과|에서|였으나|이었으나|였지만|이었지만)", tail):
                continue
            prefix = re.split(r"[,;!?\n]|(?<!\d)\.|\.(?!\d)", text[max(0, claim.start()-40):claim.start()])[-1]
            year = re.search(r"((?:19|20)\d{2})\s*년", prefix)
            if (re.search(r"전년|전기|지난해|작년|과거|이전", prefix)
                    or (year and str(item.get("fiscal_year")) != year.group(1))):
                continue
            value = item.get("value")
            if (not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value)
                    or item.get("status") in {"unavailable", "not_meaningful"}):
                violations.append(f"metric claim unavailable: {metric}")
                continue
            number = float(raw.replace(",", ""))
            negation = re.match(r"\s*(?:가|이|는|은)?\s*(?:아닙니다|아니라|아니고|아니며|아니다|아닌|아님)", tail)
            if negation:
                if not isfinite(number):
                    violations.append(f"metric claim number invalid: {metric}")
                    continue
                # 부정은 반올림 허용값이 아니라 실제값의 부정인지 확인한다.
                denies_actual = abs(number - float(value)) <= 1e-9
                if re.search(r"(?:약|대략)\s*[-+]?\d", claim.group(0)):
                    denies_actual = _matches_allowed(number, [float(value)], allow_benchmarks=False)
                if unit == item.get("unit") and denies_actual:
                    violations.append(f"metric claim contradicts: {metric}")
                negated_spans.append((claim.start(1), claim.end(2)))
                remainder = tail[negation.end():]
                correction = re.match(r"\s*(?:약\s*|대략\s*)?([-+]?\d[\d,]*(?:\.\d+)?)\s*(%p|%|원|점)", remainder)
                if not correction:
                    standalone = (re.search(r"(?:아닙니다|아니다|아님)$", negation.group(0))
                                  and re.match(r"\s*(?:[.!?;\n]|$)", remainder))
                    named_next = re.match(continuation, remainder, re.IGNORECASE)
                    if not standalone and not named_next:
                        violations.append(f"metric negation ambiguous: {metric}")
                    continue
                if re.match(r"\s*(?:의\s*)?(?:기준|임계|경계|상한|하한|보다|이상|이하|미만|초과|에서)", remainder[correction.end():]):
                    continue  # 정정 뒤의 기준/범위 비교도 현재 단일값으로 오인하지 않는다.
                raw, unit = correction.groups()
                number = float(raw.replace(",", ""))
            else:
                parsed = _numbers(raw + unit + tail)
                number = parsed[0] if parsed else number
            if unit != item.get("unit"):
                violations.append(f"metric unit mismatch: {metric}")
                continue
            if not _matches_allowed(number, [float(value)], allow_benchmarks=False):
                violations.append(f"metric claim mismatch: {metric}")
    return violations, negated_spans

def guard_llm_output(
    verdict: str,
    interpretation: str,
    ratios: dict[str, Any],
    evidence: list[Evidence],
    *,
    score: int | None = None,
    trend: dict[str, Any] | None = None,
    insights: dict[str, Any] | None = None,
) -> GuardResult:
    # LLM 문장에 등장한 숫자는 계산 결과, evidence, trend, insight, score 화이트리스트 안에 있어야 한다.
    text = f"{verdict}\n{interpretation}"
    violations: list[str] = []
    allowed = _allowed_numbers(ratios, evidence, trend, insights)
    if score is not None:
        allowed.append(float(score))

    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            violations.append("forbidden investment expression")
            break

    for metric, pattern in UNSUPPORTED_METRICS.items():
        if pattern.search(text):
            violations.append(f"unsupported metric mentioned: {metric}")

    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.search(text):
            violations.append("schema placeholder text returned")
            break

    metric_violations, negated_spans = _metric_claim_checks(text, ratios)
    numeric_text = text
    # 직접 부정으로 대조한 숫자는 긍정적 사실값 whitelist에서만 제외한다.
    for start, end in sorted(set(negated_spans), reverse=True):
        numeric_text = numeric_text[:start] + " " * (end - start) + numeric_text[end:]
    for value in _numbers(numeric_text):
        if not _matches_allowed(value, allowed):
            violations.append(f"unbound or altered number: {value:g}")

    violations.extend(metric_violations)
    return GuardResult(ok=not violations, violations=violations)
