"""#3 — answer faithfulness gate: flag synthesized answer sentences that the
collected evidence does not support.

#1 (``extract.verify_evidence``) guarantees each graph edge's quote is verbatim
in the source, and #2 deep-links the reader to it. But the *final answer* is
prose that :func:`retrieve.generate_answer` **synthesizes** from the query rows
and chunks. Even with a strict grounding prompt, the model can slip in a
sentence the evidence doesn't back (prior-knowledge padding, an over-broad
claim, a mis-stated link). Citations sit *after* the answer; nothing checks that
each sentence is actually entailed by them.

This gate does that check. Unlike #1, the answer is *not* verbatim in the
evidence ("삼성SDI는 에코프로비엠과 경쟁한다" is synthesized from a
``{competitor: "에코프로비엠"}`` row), so string matching would drop valid
sentences wholesale. Instead an NLI-style LLM pass (thinking OFF, one call per
answer) judges each sentence against the evidence digest and we mark the
unsupported ones inline — we never delete, so a verifier misjudgment can't blank
a good answer.

The gate fails *open*: any parse failure or empty evidence returns the answer
untouched. Its job is to add a warning, never to break a working answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import get_chat_llm

# Marker appended to an unsupported sentence, and the header of the footer block.
UNVERIFIED_MARK = "⚠️미검증"

# Only known whole-answer refusals can skip claim verification. A missing-data
# phrase inside a factual answer does not make the other claims disappear.
_REFUSAL_SENTENCES = {
    "근거에서 해당 연결을 찾지 못했습니다.",
    "근거에서 관련 정보를 찾지 못했습니다.",
    "근거에서 해당 정보를 찾을 수 없습니다.",
}


@dataclass
class FaithResult:
    """Outcome of a faithfulness check.

    ``text`` is the answer with ``⚠️미검증`` appended to each unsupported
    sentence (unchanged if the gate skipped or everything is supported).
    ``unsupported`` lists the flagged sentence strings (empty when clean).
    ``checked`` is False when the gate short-circuited (refusal / no evidence /
    verifier failure) so callers can tell "verified clean" from "not checked".
    """

    text: str
    unsupported: list[str]
    checked: bool
    outcome: str = "not_run"


# A claim sentence ends at ./!/?/…/newline. The second lookbehind stops us from
# splitting on an ordinal list marker's period ("1. ", "10) ") — otherwise the
# bare number becomes a junk "sentence". We keep bullet lines whole.
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?。…])(?<![0-9][.)])\s+|\n+")
_CITATION_ONLY_RE = re.compile('^(?:\\[[GV]\\d+\\]\\s*)+$')
# A fragment with no Hangul/letter (e.g. a stray "1." or "-") asserts nothing.
_HAS_CLAIM_RE = re.compile(r"[가-힣A-Za-z]")


def _split_sentences(answer: str) -> list[str]:
    """Split an answer into claim sentences, dropping blank/citation-only/marker lines."""
    sentences: list[str] = []
    for piece in _SENT_SPLIT_RE.split(answer):
        s = piece.strip()
        if not s or _CITATION_ONLY_RE.match(s) or not _HAS_CLAIM_RE.search(s):
            continue
        sentences.append(s)
    return sentences


def _is_refusal(answer: str) -> bool:
    return answer.strip() in _REFUSAL_SENTENCES


_VERIFY_PROMPT = """\
너는 답변의 각 문장이 주어진 '근거'만으로 뒷받침되는지 판정하는 검증기다.

[판정 규칙]
- 근거에 직접 명시되거나 명백히 함의되는 문장만 SUPPORTED.
- 근거에 없는 사실·수치·평가·인과·순위를 담았거나, 사전지식/추론으로 보완한 문장은 UNSUPPORTED.
- 검증할 사실 주장이 없는 도입·전환·구조 안내 문장(예: "핵심 요인은 다음과 같습니다")은 SUPPORTED로 본다.
- 사실 주장이 애매하면 UNSUPPORTED로 판정한다(보수적).
- 각 문장 번호마다 정확히 한 줄, `번호: SUPPORTED` 또는 `번호: UNSUPPORTED` 형식으로만 출력한다.
- 설명·주석·다른 텍스트를 덧붙이지 마라.

[근거]
{evidence}

[답변 문장]
{sentences}

[판정]"""


_VERDICT_RE = re.compile(r"(\d+)\s*[:.)]\s*(SUPPORTED|UNSUPPORTED)", re.IGNORECASE)


def _parse_verdicts(text: str, n: int) -> list[bool] | None:
    """Accept one unambiguous verdict per nonempty line.

    Missing sentence indices stay unsupported (legacy conservative behavior).
    Malformed/duplicate/out-of-range output is indeterminate, never last-wins.
    """
    if type(n) is not int or n < 1 or not isinstance(text, str):
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    verdicts: dict[int, bool] = {}
    for line in lines:
        match = _VERDICT_RE.fullmatch(line)
        if match is None:
            return None
        try:
            index = int(match.group(1))
        except ValueError:
            return None
        if not 1 <= index <= n or index in verdicts:
            return None
        verdicts[index] = match.group(2).upper() == "SUPPORTED"
    return [verdicts.get(i, False) for i in range(1, n + 1)]


def check_faithfulness(
    answer: str, evidence_lines: list[str], *, llm=None
) -> FaithResult:
    """Flag answer sentences not supported by ``evidence_lines`` (inline mark).

    Fails open: returns the answer unchanged (``checked=False``) when there's no
    evidence, the answer is a refusal, there are no splittable sentences, or the
    verifier's output can't be parsed. Otherwise runs one thinking-OFF LLM pass
    and appends :data:`UNVERIFIED_MARK` to each unsupported sentence.
    """
    evidence = [e for e in (evidence_lines or []) if e and e.strip()]
    if not evidence or _is_refusal(answer):
        return FaithResult(answer, [], checked=False)

    sentences = _split_sentences(answer)
    claims = [sentence for sentence in sentences if not _is_refusal(sentence)]
    if not claims:
        return FaithResult(answer, [], checked=False)

    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(claims, 1))
    prompt = _VERIFY_PROMPT.format(evidence="\n".join(evidence), sentences=numbered)
    try:
        if llm is None:
            llm = get_chat_llm(enable_thinking=False, max_tokens=512)
        supported = _parse_verdicts(llm.invoke(prompt).content, len(claims))
    except Exception:
        supported = None
    if supported is None:  # verifier unusable -> don't touch the answer
        return FaithResult(answer, [], checked=False, outcome="indeterminate")

    marked: list[str] = []
    unsupported: list[str] = []
    verdicts = iter(supported)
    for sentence in sentences:
        if _is_refusal(sentence):
            marked.append(sentence)
            continue
        if next(verdicts):
            marked.append(sentence)
        else:
            marked.append(f"{sentence} {UNVERIFIED_MARK}")
            unsupported.append(sentence)
    if not unsupported:  # all supported -> leave original formatting untouched
        return FaithResult(answer, [], checked=True, outcome="checked")
    return FaithResult("\n".join(marked), unsupported, checked=True, outcome="checked")
