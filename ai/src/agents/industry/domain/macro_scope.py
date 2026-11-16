"""Narrow current-indicator request boundary, not a general temporal/NLP parser.

No authoritative current macro source is wired into Industry. Arbitrary row/chunk
source names and dates cannot establish that authority or freshness.
"""
from __future__ import annotations

import re

_INDICATOR = r"(?:기준금리|금리|환율|물가|경기|소비자물가|CPI|GDP)"
_MODIFIER = r"(?:오늘|현재|지금|최신|최근)"
_REGION = r"(?:(?:한국은행|한국|미국|한은|원달러|원/달러|원·달러)\s*)?"
_REQUEST = r"(?:얼마|몇|어때|어떻|현황|수준|알려|값|수치|조회|[?？]|$)"
_CURRENT_FIRST = re.compile(
    _MODIFIER + r"\s*" + _REGION + _INDICATOR + r"(?:은|는|이|가)?\s*" + _REQUEST,
    re.IGNORECASE)
_INDICATOR_FIRST = re.compile(
    _INDICATOR + r"(?:은|는|이|가)?\s*" + _MODIFIER + r"\s*" + _REQUEST,
    re.IGNORECASE)
_ENGLISH = re.compile(
    r"^\s*(?:(?:what\s+is|what['’]s|tell\s+me|show\s+me|give\s+me|how\s+much\s+is)\s+)?"
    r"(?:the\s+)?(?:current|latest|today['’]?s?)\s+(?:(?:US|Korean?)\s+)?"
    r"(?:interest\s+rates?|exchange\s+rates?|inflation\s+rate|CPI|GDP)"
    r"(?:\s+(?:value|level))?\s*[?？]?\s*$",
    re.IGNORECASE)



def current_macro_hold(question: str) -> str:
    """Hold only recognized direct current-value requests; other wording is legacy.

    Not a full intent classifier. Historical/explanatory questions are not held
    merely because 'current' modifies a different subject. Mixed requests with a
    recognized current-value clause are held as a whole, not partially answered.
    """
    if not isinstance(question, str):
        return ""
    matches = [match for pattern in (_CURRENT_FIRST, _INDICATOR_FIRST, _ENGLISH)
               for match in pattern.finditer(question)]
    # A dated 'as of/current' phrase is not automatically a request for today.
    def dated(match):
        prefix = question[:match.start()]
        return re.search(r"(?:[12][0-9]{3}년|in [12][0-9]{3})[ ,]*$", prefix, re.IGNORECASE) is not None
    if not any(not dated(match) for match in matches):
        return ""
    return (
        "현재 거시 지표 현황은 미확인입니다. 이 AI 답변 경로에는 신뢰·최신성을 확인한 "
        "최신 지표 원천이 연결되어 있지 않아 요청한 현재 수치 답변을 보류합니다. "
        "기업 공시·검색 청크의 과거 수치나 출처 이름·날짜만으로 오늘의 금리·환율·물가·경기를 "
        "확정하지 않습니다. 자료가 존재하지 않는다는 뜻은 아닙니다."
    )
