"""Known-company scope and observed source attribution, not corpus completeness."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from itertools import islice
import re

MAX_VECTOR_RESULTS = 5
SURFACE_PRIORITY = {"canonical": 0, "alias": 1, "stock_code": 2}


@dataclass(frozen=True)
class CompanyScope:
    question: str
    companies: tuple[str, ...] = ()
    matched: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    reason: str = "unscoped"
    discarded: int = 0


def plan_company_scope(question: str, surfaces: list[tuple[str, str, str]]) -> CompanyScope:
    candidates = []
    for key, canonical, kind in surfaces:
        if not key:
            continue
        pattern = r"\s*".join(re.escape(char) for char in key)
        if kind == "stock_code":
            pattern = r"(?<!\d)" + pattern + r"(?!\d)"
        else:
            pattern = (r"(?<![a-z0-9_])" if key[0].isascii() and key[0].isalnum() else "") + pattern
            if key[-1].isascii() and key[-1].isalnum():
                pattern += r"(?![a-z0-9_])"
        for match in re.finditer(pattern, question, re.IGNORECASE):
            candidates.append((len(key), -SURFACE_PRIORITY[kind], match.start(), match.end(), canonical))
    chosen = []
    for length, priority, start, end, canonical in sorted(candidates, reverse=True):
        if any(start < prior[1] and end > prior[0] for prior in chosen):
            continue
        ties = {item[4] for item in candidates if item[0] == length and item[2:4] == (start, end)}
        if len(ties) != 1:
            return CompanyScope(question, reason="ambiguous")
        chosen.append((start, end, canonical))
    companies = tuple(dict.fromkeys(item[2] for item in sorted(chosen)))
    if not companies:
        return CompanyScope(question)
    compact = "".join(question.lower().split())
    excluded = any(word in compact for word in (
        "제외", "말고", "빼고", "이외", "아닌", "만으로", "공시만", "자료만",
        "최신", "현재", "최근", "올해", "작년", "이후", "이전", "동일시점", "동일기간"))
    excluded |= bool(re.search(r"\b(?:except|excluding|exclude|instead|not)\b", question, re.IGNORECASE))
    excluded |= bool(re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)", question))
    comparison = any(word in compact for word in ("비교", "차이", "대비", "각각", "compare", "comparison", "versus", "difference"))
    comparison |= bool(re.search(r"(?<![a-z])vs\.?(?![a-z])", question, re.IGNORECASE))
    if excluded or len(companies) > 2 or comparison and len(companies) != 2 or len(companies) == 2 and not comparison:
        return CompanyScope(question, companies=companies, reason="ambiguous")
    return CompanyScope(question, companies=companies, missing=companies, reason="pending")


def _source_company(chunk: dict, surfaces, normalize) -> str | None:
    identities = []
    for field, kinds in (("company", {"canonical", "alias"}), ("stock_code", {"stock_code"})):
        value = chunk.get(field)
        if value is None or value == "":
            continue
        if not isinstance(value, str) or not value.strip():
            return None
        if field == "stock_code" and (len(value) != 6 or not value.isascii() or not value.isdecimal()):
            return None
        key = value if field == "stock_code" else normalize(value)
        found = {canonical for surface, canonical, kind in surfaces if kind in kinds and surface == key}
        if len(found) != 1:
            return None
        identities.append(next(iter(found)))
    if not identities or len(set(identities)) != 1:
        return None
    return identities[0]


def retain_company_chunks(plan: CompanyScope, chunks, surfaces, normalize):
    selected, matched, discarded = [], set(), 0
    for chunk in islice(iter(chunks), MAX_VECTOR_RESULTS):
        identity = _source_company(chunk, surfaces, normalize) if isinstance(chunk, dict) else None
        if identity is None or plan.companies and identity not in plan.companies:
            discarded += 1
            continue
        selected.append(deepcopy(chunk))
        matched.add(identity)
    missing = tuple(company for company in plan.companies if company not in matched)
    reason = "search_uncovered" if missing or not selected else "observed"
    return selected, CompanyScope(plan.question, plan.companies, tuple(sorted(matched)),
                                   missing, reason, discarded)


def company_scope_policy(scope: CompanyScope | None, question: str) -> tuple[bool, str]:
    if scope is None:
        return False, ""
    if type(scope) is not CompanyScope or scope.question != question or scope.reason in {"ambiguous", "pending"}:
        return True, "기업 식별 또는 범위 조건을 확인해야 해 분석을 보류합니다. 여러 기업·제외·시점 조건을 임의로 추정하지 않았습니다."
    if scope.reason == "search_uncovered":
        names = "·".join(scope.missing)
        return True, (f"이번 검색 범위에서 {names + '의 ' if names else ''}기업 식별정보가 일치하는 검색 근거를 모두 확보하지 못해 분석을 보류합니다. "
                      "해당 기업의 실제 자료가 없다는 뜻은 아닙니다.")
    if (scope.reason != "observed" or scope.missing
            or not set(scope.companies).issubset(scope.matched)):
        return True, "기업 근거의 검색 범위가 확인되지 않아 분석을 보류합니다."
    if len(scope.companies) == 2:
        return False, ("기업별 검색 범위: " + "·".join(scope.companies) +
                       "의 검색 근거를 구분해 제공했습니다. 상위 검색 결과 범위이며 전체 자료·동일 시점·기업 전체 coverage 검증을 뜻하지 않습니다.")
    if scope.discarded:
        return False, "검색 결과 일부는 기업 식별정보를 일치시키지 못해 분석 근거에서 제외했습니다. 전체 자료의 부재를 뜻하지 않습니다."
    return False, ""
