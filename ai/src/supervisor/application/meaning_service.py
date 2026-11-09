"""Conservative explicit extraction plus validated, optional bounded model proposals."""
import asyncio
import re
from src.supervisor.domain.meaning import CoreInvalid, MeaningFrame, sha
from src.supervisor.infrastructure.meaning_gateway import MeaningUnavailable, UnavailableMeaningGateway
MARKERS = {'flow': ('수급', '외국인', '기관', '순매수', '순매도', '자금흐름'), 'technical': ('차트', '이동평균', '이평', 'rsi', 'macd', '모멘텀', '지지', '저항', '캔들'), 'fundamental': ('재무', '실적', '매출', 'ofs', 'cfs', '분기', 'annual', 'years'), 'macro': ('거시', '금리', '환율'), 'industry': ('산업', '업종'), 'news': ('뉴스', 'news'), 'overview': ('주식 정보', '주식정보', '종합', '기업 정보')}

def deterministic(draft):
    mentions = []
    conditions = []
    requested = []
    negated = []
    slots = []
    sources = [(draft.original_query, 'original_query', None, None)] + [(a.value, 'clarification_answer', a.answer_id, a.slot) for a in draft.answers]

    def evidence(text, kind, aid, start, end):
        return dict(source_kind=kind, answer_id=aid, start=start, end=end, text=text[start:end])
    for (text, kind, aid, slot) in sources:
        low = text.lower()
        if slot == 'stock':
            matches = [(0, len(text))]
        else:
            matches = [m.span() for m in re.finditer('(?<!\\d)[0-9]{6}(?!\\d)|[가-힣A-Za-z][가-힣A-Za-z0-9.&]*(?:전자|하이닉스|바이오|자동차|전기|증권|은행|카카오|네이버)', text)]
        local = []
        for (start, end) in matches:
            item = dict(text=text[start:end], negated=bool(re.match('\\s*(?:말고|제외|빼고|아닌)', text[end:])), evidence=evidence(text, kind, aid, start, end))
            local.append(item)
        if slot == 'stock':
            mentions = [m for m in mentions if m['negated']] + local
        else:
            mentions += local
        for (view, markers) in MARKERS.items():
            hits = [m for marker in markers for m in re.finditer(re.escape(marker), low)]
            for m in hits:
                excluded = bool(re.match('\\s*(?:말고|제외|빼고|아닌)', low[m.end():]))
                if view == 'flow' and m.group() in {'외국인', '기관', '개인'} and excluded:
                    continue
                target = negated if excluded else requested
                if view not in target:
                    target.append(view)
        if slot == 'views':
            answer_requested = []
            answer_negated = []
            for (view, markers) in MARKERS.items():
                for marker in (*markers, view):
                    for match in re.finditer(re.escape(marker), low):
                        excluded = bool(re.match('\\s*(?:말고|제외|빼고|아닌)', low[match.end():]))
                        target = answer_negated if excluded else answer_requested
                        if view not in target:
                            target.append(view)
            requested = answer_requested
            negated = list(dict.fromkeys([*negated, *answer_negated]))
        for actor in ('외국인', '기관', '개인'):
            for m in re.finditer(actor, text):
                excluded = bool(re.match('\\s*(?:말고|제외|빼고|아닌)', text[m.end():]))
                k = 'exclude' if excluded else 'focus'
                conditions.append(dict(condition_id='c' + str(len(conditions)), domain='flow', kind=k, value=actor, evidence=[evidence(text, kind, aid, m.start(), m.end())], disposition='unsupported'))
        for (pattern, domain, k) in [('(?:최근|지난|과거)?\\s*\\d+\\s*(?:거래일|개월|주|일|년|달|시간)', 'flow', 'period'), ('\\d{4}-\\d{2}-\\d{2}', 'flow', 'cutoff'), ('(?:19|20)\\d{2}년|어제|그제|그저께|지난주|지난달|작년|재작년|지난해|올해|이번주|이번달|오늘|내일|모레|금일|현재|지금|요즘|최근|지난|과거|향후|앞으로|기준일|시점|기간', 'flow', 'cutoff'), ('(?:완전|모두)\\s*20\\s*(?:거래일|일)', 'flow', 'coverage'), ('\\d+\\s*분봉', 'technical', 'candle_unit'), ('(?i)(?:3m|1y|5y)', 'technical', 'period'), ('(?i)(?:OFS|CFS|별도|연결)', 'fundamental', 'statement_basis'), ('(?i)(?:분기|latest|annual)', 'fundamental', 'financial_period'), ('(?i)\\d+\\s*years', 'fundamental', 'years')]:
            for m in re.finditer(pattern, text):
                conditions.append(dict(condition_id='c' + str(len(conditions)), domain=domain, kind=k, value=m.group(), evidence=[evidence(text, kind, aid, m.start(), m.end())], disposition='unsupported'))
        if slot == 'period' and (not any((c['evidence'][0]['answer_id'] == aid for c in conditions))):
            conditions.append(dict(condition_id='c' + str(len(conditions)), domain='flow', kind='period', value=text, evidence=[evidence(text, kind, aid, 0, len(text))], disposition='unsupported'))
    requested = [v for v in requested if v not in negated]
    active = {m['text'] for m in mentions if not m['negated']}
    if len(active) > 1:
        slots.append('multi_stock')
    elif not active:
        slots.append('stock')
    if not requested or requested == ['overview']:
        slots.append('views')
    scope_match = re.search('시장|증시|전체\\s*종목|모든\\s*종목', draft.original_query)
    if scope_match:
        conditions.append(dict(condition_id='c' + str(len(conditions)), domain='flow', kind='unrecognized', value=scope_match.group(), evidence=[evidence(draft.original_query, 'original_query', None, scope_match.start(), scope_match.end())], disposition='unsupported'))
        narrowed = any((a.slot in {'stock', 'scope'} and a.value in active and (not re.search('시장|증시|전체|모든', a.value)) for a in draft.answers))
        if not narrowed:
            slots.append('scope')
    if any((x in draft.original_query.lower() for x in ('제한 무시', '제한무시', 'ignore instructions', 'system prompt'))):
        slots.append('meaning')
    return MeaningFrame(original_query=draft.original_query, query_sha256=sha(draft.original_query), revision=draft.revision, answers=draft.answers, mentions=mentions, requested_views=requested, negated_views=negated, conditions=conditions, unresolved_slots=slots, interpretation_source='deterministic')

async def understand(draft, gateway=None):
    frame = deterministic(draft)
    if not frame.unresolved_slots:
        return frame
    try:
        async with asyncio.timeout(5):
            proposed = MeaningFrame.model_validate(await (gateway or UnavailableMeaningGateway()).extract(draft))
        if proposed.original_query != draft.original_query or proposed.answers != draft.answers or proposed.revision != draft.revision or (proposed.interpretation_source != 'model_assisted'):
            raise CoreInvalid()
        if any((c.model_dump() not in [x.model_dump() for x in proposed.conditions] for c in frame.conditions)) or not set(frame.negated_views) <= set(proposed.negated_views):
            raise CoreInvalid()
        if frame.requested_views and frame.requested_views != ['overview'] and (set(proposed.requested_views) != set(frame.requested_views)):
            raise CoreInvalid()
        if proposed.mentions != frame.mentions:
            raise CoreInvalid()
        active = {m.text for m in proposed.mentions if not m.negated}
        # Explicit clarification and injection barriers require an actual typed answer.
        # A model proposal cannot silently turn a broad request into Flow-only consent.
        protected = set(frame.unresolved_slots)
        if not protected <= set(proposed.unresolved_slots) or (len(active) != 1 and (not {'stock', 'multi_stock'} & set(proposed.unresolved_slots))):
            raise CoreInvalid()
        return proposed
    except (MeaningUnavailable, CoreInvalid, ValueError, TypeError):
        return frame.model_copy(update={'interpretation_source': 'unavailable'})
