"""Closed evidence acceptance profile. Model text never supplies policy or consent."""
from dataclasses import dataclass
from datetime import date
import re
from src.supervisor.domain.meaning import CoreInvalid, Draft, Evidence, MeaningFrame, sha
from src.supervisor.domain.meaning_proposals import MeaningProposal

VIEW_WORDS = {
    'flow': ('수급', '순매수', '순매도', '자금흐름', '자금 흐름', 'flow'),
    'technical': ('차트', '캔들', '이동평균', '이평', 'rsi', 'macd', '모멘텀', '지지', '저항', 'technical'),
    'fundamental': ('재무', '실적', '매출', 'fundamental'),
    'macro': ('거시', '금리', '환율', 'macro'),
    'industry': ('산업', '업종', 'industry'),
    'news': ('뉴스', 'news'),
    'overview': ('주식 정보', '주식정보', '기업 정보', '기업정보', '종합', 'overview'),
}
ACTORS = ('외국인', '기관', '개인')
NEGATION = re.compile(r'\s*(?:은|는|을|를)?\s*(말고|제외|빼고|아닌|없이)')
FINANCIAL = re.compile(r'재무|실적|매출|분기|\b(?:OFS|CFS|annual|latest|years)\b', re.I)
MARKET = re.compile(r'시장(?:\s*전체)?|증시|전체\s*종목|모든\s*종목')
INJECTION = re.compile(r'제한\s*무시|ignore\s+instructions|system\s+prompt', re.I)
STOCK = re.compile(r'(?<!\d)[0-9]{6}(?!\d)|[가-힣A-Za-z][가-힣A-Za-z0-9.&]*(?:전자|하이닉스|바이오|자동차|전기|증권|은행|카카오|네이버)')
PERIOD = re.compile(r'(?:최근|지난|과거)?\s*(?<![.\d+\-])\d+\s*(?:거래일|개월|개년|years|주|일|년|달|시간)', re.I)
TIME = re.compile(r'\d{4}-\d{2}-\d{2}|(?:19|20)\d{2}\s*년|어제|그저께|그제|지난주|지난달|작년|재작년|지난해|올해|내년|내일|오늘|이번주|이번달|요즘|현재|지금|최근|지난|과거|향후|앞으로|기준일|시점|기간')
FILLERS = tuple(sorted(('알려주세요', '보여주세요', '분석해줘', '알려줘', '보여줘', '봐줘', '궁금해', '궁금합니다', '어때요', '어때', '어떻게', '리포트', '분석', '의', '을', '를', '은', '는', '이', '가', '와', '과', '좀'), key=len, reverse=True))
SCOPE_SINGLE = {'선택한 한 종목만', '개별 종목만', '한 종목만'}
# These suffixes describe bounded name shapes, never canonical stock identity.
NAME_ENDINGS = {'전자', '하이닉스', '바이오', '자동차', '전기', '증권', '은행', '건설', '전력', '제약'}
MENTION_MODIFIERS = re.compile(r'목표가|매집|저평가|고평가|매수|매도|이상|이하|초과|미만|보다|대비|조건|기준|이후|이전|부터|까지|없이|말고|제외|빼고|아닌|\b(?:buy|sell)\b', re.I)
QUANTITY = re.compile(r'\d+(?:[.,]\d+)?\s*(?:[천만억조](?:원)?|원|%|배|주|거래일|개월|개년|년|일|달|시간)|(?:^|\s)\d+(?:[.,]\d+)?(?=$|\s)', re.I)
NAME_CHARACTER = re.compile(r'[가-힣A-Za-z0-9.&_-]')
STOCK_PARTICLE = re.compile(r'(?:은|는|을|를|이|가|와|과)(?=$|[^가-힣A-Za-z0-9.&_-])')



def normalized(text):
    return re.sub(r'\s+', ' ', text.strip()).lower()


def stock_name_shape(raw):
    """A name span cannot claim coverage for views, amounts, periods or modifiers."""
    if not raw or len(raw) > 256 or not re.fullmatch(r'[가-힣A-Za-z0-9 .&_-]+', raw):
        return False
    if re.fullmatch(r'[0-9]{6}', raw):
        return True
    semantic_words = [word for words in VIEW_WORDS.values() for word in words] + list(ACTORS)
    if any(word in normalized(raw) for word in semantic_words) or MENTION_MODIFIERS.search(raw) or QUANTITY.search(raw) or PERIOD.search(raw) or TIME.search(raw):
        return False
    parts = raw.split()
    if len(parts) == 1:
        return bool(re.search(r'[가-힣A-Za-z]', raw))
    # Multiword proper names have a bounded compound shape; arbitrary prose is not a name.
    return len(parts) == 2 and (parts[-1] in NAME_ENDINGS or re.fullmatch(r'[A-Z]{1,8}', parts[0]) is not None)


def exact_name_boundary(text, start, end):
    if start and NAME_CHARACTER.fullmatch(text[start - 1]):
        return False
    if end == len(text) or not NAME_CHARACTER.fullmatch(text[end]):
        return True
    tail = text[end:]
    if STOCK_PARTICLE.match(tail):
        return True
    negative = NEGATION.match(tail)
    return bool(negative and (negative.end() == len(tail) or not NAME_CHARACTER.fullmatch(tail[negative.end()])))


@dataclass(frozen=True)
class Assessment:
    frame: MeaningFrame
    remainder: tuple
    needs_supplement: bool
    hard_meaning: bool


class Grounding:
    def __init__(self, draft):
        self.draft = draft
        self.sources = {('original_query', None): draft.original_query}
        self.slots = {}
        for answer in draft.answers:
            key = ('clarification_answer', answer.answer_id)
            self.sources[key] = answer.value
            self.slots[key] = answer.slot
        self.covered = {key: [False] * len(text) for key, text in self.sources.items()}
        self.mentions = []
        self.views = []
        self.conditions = {}

    def evidence(self, key, start, end):
        return Evidence(source_kind=key[0], answer_id=key[1], start=start, end=end, text=self.sources[key][start:end])

    def validate(self, evidence):
        key = (evidence.source_kind, evidence.answer_id)
        text = self.sources.get(key)
        if text is None or not 0 <= evidence.start < evidence.end <= len(text) or text[evidence.start:evidence.end] != evidence.text:
            raise CoreInvalid()
        return key, text

    def cover(self, evidence):
        key, _ = self.validate(evidence)
        self.covered[key][evidence.start:evidence.end] = [True] * (evidence.end - evidence.start)

    def positive_and_negation(self, evidence):
        key, text = self.validate(evidence)
        embedded = re.search(r'\s*(말고|제외|빼고|아닌|없이)\s*$', evidence.text)
        if embedded:
            return evidence.text[:embedded.start()].strip(), self.evidence(key, evidence.start + embedded.start(1), evidence.start + embedded.end(1)), True
        following = NEGATION.match(text[evidence.end:])
        if following:
            return evidence.text, self.evidence(key, evidence.end + following.start(1), evidence.end + following.end(1)), False
        return evidence.text, None, False

    def negation(self, evidence, supplied=None, *, proposal=False, cover=True):
        positive, actual, embedded = self.positive_and_negation(evidence)
        if supplied is not None:
            self.validate(supplied)
            if actual is None or supplied != actual:
                raise CoreInvalid()
        elif proposal and actual is not None and not embedded:
            raise CoreInvalid()
        if cover:
            if actual is not None:
                self.cover(actual)
            self.cover(evidence)
        return normalized(positive), actual is not None

    def add_mention(self, evidence, supplied=None, *, proposal=False):
        raw, actual, _ = self.positive_and_negation(evidence)
        raw = raw.strip()
        if not stock_name_shape(raw):
            raise CoreInvalid()
        _, negative = self.negation(evidence, supplied, proposal=proposal, cover=False)
        # Mention.text must still exactly match its source span.
        if raw != evidence.text:
            key, source = self.validate(evidence)
            offset = source.find(raw, evidence.start, evidence.end)
            evidence = self.evidence(key, offset, offset + len(raw))
        # Only the validated name and its explicit negation receive name coverage.
        # Condition/view coverage belongs to their own parsers, never a proposed whole question.
        self.cover(evidence)
        if actual is not None:
            self.cover(actual)
        value = {'text': evidence.text, 'negated': negative, 'evidence': evidence.model_dump(mode='json')}
        if value not in self.mentions:
            self.mentions.append(value)

    def connect_stock_answer(self, answer):
        """Link only an exact, bounded original occurrence of a validated typed name."""
        key = ('clarification_answer', answer.answer_id)
        names = [mention['text'] for mention in self.mentions if mention['evidence']['answer_id'] == answer.answer_id]
        original = self.draft.original_query
        for name in names:
            for match in re.finditer(re.escape(name), original):
                if exact_name_boundary(original, *match.span()):
                    # Re-read original adjacent negation; the answer cannot make it positive.
                    self.add_mention(self.evidence(('original_query', None), *match.span()))

    def cover_view_selection(self, key, text):
        """Only a complete typed views answer may use the finite '<view>만' selection."""
        answer = normalized(text)
        choices = {normalized(word) + suffix for words in VIEW_WORDS.values() for word in words for suffix in ('만', ' 만')}
        if answer in choices:
            self.cover(self.evidence(key, 0, len(text)))

    def view_for(self, evidence):
        _, source = self.validate(evidence)
        text, _, _ = self.positive_and_negation(evidence)
        value = normalized(text)
        for view, words in VIEW_WORDS.items():
            if value in {normalized(word) for word in words}:
                return view
        if value in ACTORS and re.search(r'수급|순매수|순매도|매매|투자', source):
            return 'flow'
        return None

    def add_view(self, view, evidence, supplied=None, *, proposal=False):
        if self.view_for(evidence) != view:
            raise CoreInvalid()
        positive, actual, _ = self.positive_and_negation(evidence)
        if normalized(positive) in ACTORS and actual is not None:
            if proposal:
                raise CoreInvalid()
            return  # Excluding a participant is not a negated Flow perspective.
        _, negative = self.negation(evidence, supplied, proposal=proposal)
        value = (view, negative, evidence)
        if value not in self.views:
            self.views.append(value)

    def parsed_condition(self, evidence):
        _, source = self.validate(evidence)
        positive, actual, _ = self.positive_and_negation(evidence)
        value = normalized(positive)
        if value in ACTORS:
            return 'flow', 'exclude' if actual else 'focus', positive.strip()
        if value in {'ofs', 'cfs', '별도', '연결'}:
            if value in {'별도', '연결'} and not FINANCIAL.search(source):
                return None
            return 'fundamental', 'statement_basis', 'OFS' if value in {'ofs', '별도'} else 'CFS'
        if re.fullmatch(r'(?:\d{4}년\s*)?(?:[1-4]\s*분기|분기|연간|annual|latest)', value):
            return 'fundamental', 'financial_period', positive.strip()
        if re.fullmatch(r'\d+\s*분봉', value):
            number = int(re.search(r'\d+', value).group())
            return ('technical', 'candle_unit', positive.strip()) if 1 <= number <= 10000 else None
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            try: date.fromisoformat(value)
            except ValueError: return None
            return 'flow', 'cutoff', positive.strip()
        if re.fullmatch(r'(?:19|20)\d{2}\s*년', value):
            return ('fundamental', 'financial_period', positive.strip()) if FINANCIAL.search(source) else ('flow', 'cutoff', positive.strip())
        if PERIOD.fullmatch(positive.strip()):
            digits = re.search(r'\d+', value)
            if digits is None or not 1 <= int(digits.group()) <= 10000:
                return None
            kind = 'years' if re.search(r'개년|years', value) or FINANCIAL.search(source) and re.search(r'년$', value) else 'period'
            return 'fundamental' if kind == 'years' else 'flow', kind, positive.strip()
        if TIME.fullmatch(positive.strip()):
            return 'flow', 'cutoff', positive.strip()
        return None

    def add_condition(self, domain, kind, value, evidence, supplied=None, *, proposal=False):
        parsed = self.parsed_condition(evidence)
        if parsed is None or parsed[:2] != (domain, kind) or normalized(parsed[2]) != normalized(value):
            raise CoreInvalid()
        _, negative = self.negation(evidence, supplied, proposal=proposal)
        if kind in {'focus', 'exclude'} and (kind == 'exclude') != negative:
            raise CoreInvalid()
        positive, actual, _ = self.positive_and_negation(evidence)
        key, text = self.validate(evidence)
        start = text.find(positive.strip(), evidence.start, evidence.end)
        canonical_evidence = self.evidence(key, start, start + len(positive.strip()))
        self.condition(domain, kind, parsed[2], [canonical_evidence] + ([actual] if actual is not None else []))

    def condition(self, domain, kind, value, evidence):
        body = {'domain': domain, 'kind': kind, 'value': value, 'evidence': [e.model_dump(mode='json') for e in evidence], 'disposition': 'unsupported'}
        identifier = 'c' + sha(body)[:24]
        self.conditions[identifier] = {'condition_id': identifier, **body}

    def scan(self):
        for key, text in self.sources.items():
            slot = self.slots.get(key)
            if slot == 'stock':
                try:
                    self.add_mention(self.evidence(key, 0, len(text)))
                except CoreInvalid:
                    # Invalid typed prose stays unrecognized rather than erasing its conditions.
                    pass
                else:
                    answer = next(answer for answer in self.draft.answers if answer.answer_id == key[1])
                    self.connect_stock_answer(answer)
            else:
                for match in STOCK.finditer(text):
                    try:
                        self.add_mention(self.evidence(key, *match.span()))
                    except CoreInvalid:
                        pass  # An overbroad heuristic match leaves meaningful text uncovered.
            for view, words in VIEW_WORDS.items():
                for word in words:
                    for match in re.finditer(re.escape(word), text, re.I):
                        self.add_view(view, self.evidence(key, *match.span()))
            for actor in ACTORS:
                for match in re.finditer(actor, text):
                    evidence = self.evidence(key, *match.span())
                    if self.view_for(evidence) == 'flow':
                        self.add_view('flow', evidence)
                    parsed = self.parsed_condition(evidence)
                    self.add_condition(*parsed, evidence)
            patterns = [PERIOD, TIME, re.compile(r'OFS|CFS|별도|연결|(?:\d{4}년\s*)?[1-4]\s*분기|분기|연간|annual|latest|\d+\s*분봉', re.I)]
            for pattern in patterns:
                for match in pattern.finditer(text):
                    evidence = self.evidence(key, *match.span())
                    parsed = self.parsed_condition(evidence)
                    if parsed is not None:
                        self.add_condition(*parsed, evidence)
            if slot == 'views':
                self.cover_view_selection(key, text)
            if slot == 'scope' and normalized(text) in {normalized(v) for v in SCOPE_SINGLE}:
                self.cover(self.evidence(key, 0, len(text)))

    def apply(self, proposal):
        for item in proposal.mentions:
            self.add_mention(item.evidence, item.negation, proposal=True)
        for item in proposal.views:
            self.add_view(item.view, item.evidence, item.negation, proposal=True)
        for item in proposal.conditions:
            self.add_condition(item.domain, item.kind, item.value, item.evidence, item.negation, proposal=True)

    def remainder(self):
        for key, text in self.sources.items():
            mask = self.covered[key]
            for word in FILLERS:
                for match in re.finditer(re.escape(word), text, re.I):
                    a, b = match.span()
                    left = a == 0 or mask[a - 1] or text[a - 1] in ' \t\n,.!?'
                    right = b == len(text) or mask[b] or text[b] in ' \t\n,.!?'
                    if left and right and not any(mask[a:b]):
                        mask[a:b] = [True] * (b - a)
        ranges = []
        for key, text in self.sources.items():
            mask = self.covered[key]
            start = None
            for i in range(len(text) + 1):
                residual = i < len(text) and not mask[i] and text[i] not in ' \t\n,.!?'
                if residual and start is None: start = i
                if start is not None and not residual:
                    ranges.append(self.evidence(key, start, i));start = None
        return ranges

    def assess(self, source='deterministic'):
        requested = {view for view, negative, _ in self.views if not negative}
        negated = {view for view, negative, _ in self.views if negative}
        answers = [answer for answer in self.draft.answers if answer.slot == 'views']
        if answers:
            last = answers[-1].answer_id
            requested = {view for view, negative, e in self.views if e.answer_id == last and not negative}
        requested -= negated
        mentions = list(self.mentions)
        stock_answers = [a for a in self.draft.answers if a.slot == 'stock' and any(m['evidence']['answer_id'] == a.answer_id for m in self.mentions)]
        original_active = {m['text'] for m in mentions if not m['negated'] and m['evidence']['source_kind'] == 'original_query'}
        if stock_answers:
            last = stock_answers[-1].answer_id
            mentions = [m for m in mentions if m['negated'] or m['evidence']['answer_id'] == last]
        active = {m['text'] for m in mentions if not m['negated']}
        unresolved = []
        positive_stocks = {normalized(m['text']) for m in self.mentions if not m['negated']}
        negative_stocks = {normalized(m['text']) for m in self.mentions if m['negated']}
        if positive_stocks & negative_stocks:
            unresolved.append('scope')
            evidence = [Evidence.model_validate(m['evidence']) for m in self.mentions if normalized(m['text']) in positive_stocks & negative_stocks]
            self.condition('flow', 'unrecognized', '종목 포함·제외 조건 충돌', evidence)
        if not active: unresolved.append('stock')
        elif len(active) > 1: unresolved.append('multi_stock')
        if not requested or requested == {'overview'}: unresolved.append('views')
        market = MARKET.search(self.draft.original_query)
        scope_answered = bool(stock_answers and len(active) == 1 and any(a.slot == 'scope' and normalized(a.value) in {normalized(v) for v in SCOPE_SINGLE} for a in self.draft.answers))
        if market:
            evidence = self.evidence(('original_query', None), *market.span());self.cover(evidence)
            self.condition('flow', 'unrecognized', market.group(), [evidence])
            if not scope_answered: unresolved.append('scope')
        if len(original_active) > 1 and stock_answers:
            evidence = [Evidence.model_validate(m['evidence']) for m in self.mentions if m['evidence']['source_kind'] == 'original_query' and not m['negated']]
            self.condition('flow', 'unrecognized', '원래 다중 종목 요청에서 단일 종목으로 좁힘', evidence)
        remainder = self.remainder()
        for evidence in remainder:
            self.condition('overview', 'unrecognized', evidence.text, [evidence])
        hard = bool(INJECTION.search(self.draft.original_query))
        if remainder or hard: unresolved.append('meaning')
        values = list(self.conditions.values())
        actor = {(c['kind'], c['value']) for c in values if c['kind'] in {'focus', 'exclude'}}
        if any(('focus', x) in actor and ('exclude', x) in actor for x in ACTORS):
            unresolved.append('scope')
        frame = MeaningFrame(original_query=self.draft.original_query, query_sha256=sha(self.draft.original_query), revision=self.draft.revision,
                             answers=self.draft.answers, mentions=mentions, requested_views=[v for v in VIEW_WORDS if v in requested],
                             negated_views=[v for v in VIEW_WORDS if v in negated], conditions=sorted(values, key=lambda c:c['condition_id']),
                             unresolved_slots=list(dict.fromkeys(unresolved)), interpretation_source=source)
        needs = bool(remainder) and not hard
        return Assessment(frame, tuple(remainder), needs, hard)


def align_model_proposal(draft, proposal):
    """Anchor model text only to its unique exact occurrence in the named source.

    Raw offsets retain their strict wire shape but never disambiguate evidence.
    Dump/revalidate both sides of the transformation; no caller object is mutated.
    Canonical stored frames and deterministic scans never pass through this seam.
    """
    raw = proposal.model_dump(mode='python') if isinstance(proposal, MeaningProposal) else proposal
    data = MeaningProposal.model_validate(raw).model_dump(mode='python')
    sources = {('original_query', None): draft.original_query}
    sources.update({('clarification_answer', answer.answer_id): answer.value for answer in draft.answers})
    for section in ('mentions', 'views', 'conditions'):
        for item in data[section]:
            for field in ('evidence', 'negation'):
                evidence = item[field]
                if evidence is None:
                    continue
                text = sources.get((evidence['source_kind'], evidence['answer_id']))
                if text is None:
                    raise CoreInvalid()
                start = text.find(evidence['text'])
                # start+1 includes overlapping occurrences ("aa" in "aaa").
                if start < 0 or text.find(evidence['text'], start + 1) >= 0:
                    raise CoreInvalid()
                evidence['start'], evidence['end'] = start, start + len(evidence['text'])
    return MeaningProposal.model_validate(data)


def assess(draft, proposal=None, *, source='deterministic'):
    draft = Draft.model_validate(draft.model_dump())
    grounding = Grounding(draft)
    grounding.scan()
    if proposal is not None:
        grounding.apply(align_model_proposal(draft, proposal))
    return grounding.assess(source)


def validate_fixed_frame(draft, frame):
    grounding = Grounding(draft)
    grounding.scan()
    for mention in frame.mentions:
        _, actual, _ = grounding.positive_and_negation(mention.evidence)
        if mention.negated != (actual is not None):
            raise CoreInvalid()
        grounding.add_mention(mention.evidence)
    for condition in frame.conditions:
        if condition.kind != 'unrecognized':
            grounding.add_condition(condition.domain, condition.kind, condition.value, condition.evidence[0], condition.evidence[1] if len(condition.evidence) == 2 else None, proposal=True)
    expected = grounding.assess(frame.interpretation_source).frame
    if expected != frame:
        raise CoreInvalid()
    return frame
