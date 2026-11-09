"""Pure bounded intent classification; never imports agents, classifiers or LLMs."""
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Interpretation:
    requested_views: tuple[str, ...]
    should_resolve: bool
    reason: str

def interpret(query: str) -> Interpretation:
    low = query.lower()
    groups = {
        'flow': ('수급','외국인','기관','순매수','순매도','자금흐름'),
        'technical': ('차트','캔들','이평','기술분석','기술 분석','거래량','지지','저항','이동평균','모멘텀','rsi','macd','볼린저','스토캐스틱','주가','가격'),
        'fundamental': ('재무','실적','밸류','배당','per','pbr','roe'),
        'macro': ('거시','금리','환율','경제'),
        'industry': ('산업','업종','섹터'),
        'news': ('뉴스','news'),
    }
    views = tuple(name for name, markers in groups.items() if any(m in low for m in markers))
    if any(m in low for m in ('종합','모든 관점','주식 정보','주식정보','전체 분석','전부 실행')):
        return Interpretation(views or ('overview',), False, 'unsupported_views')
    if any(v != 'flow' for v in views):
        return Interpretation(views, False, 'unsupported_views')
    if views==('flow',) and re.search(r'(?:수급|외국인|기관|순매수|순매도)\s*(?:말고|제외|빼고|아니라)',low):
        return Interpretation(views,False,'clarify_intent')
    if not views:
        return Interpretation((), False, 'clarify_intent')
    if any(m in low for m in ('시장','증시','코스피','코스닥','전체 종목','시장전체')):
        return Interpretation(views, False, 'clarify_stock_scope')
    return Interpretation(views, True, 'resolve_required')
