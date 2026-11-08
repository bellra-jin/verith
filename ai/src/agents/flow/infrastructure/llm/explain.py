"""Validated immutable fact menu to strict LLM ID selection.

The provider selects IDs only; code owns all sentences. Rejected responses are
consumed by workflow/Gate3 and never exported. Existing provider caps remain.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from ... import config
from ...domain.models import GateResult
from ...domain.interpretation_claims import valid_bank, SelectionInvalid

_AI_ROOT = Path(__file__).resolve().parents[5]
_ENV_FILE = _AI_ROOT / ".env"
_PROMPT_PATH = Path(__file__).parents[2] / "prompts" / "explain.txt"
_MODEL = config.INTERPRETER_MODEL    # 해석용(비용 낮음). 교체는 config 한 곳에서 — payload 기록과 동기.
_TEMPERATURE = 0.2        # 낮게 — 해석이 튀지 않게.


def _facts_to_text(signals: dict, meta: dict, bank) -> str:
    """Only immutable reviewed fact menus, never the user's free-form question."""
    if not valid_bank(bank, meta, signals):
        raise SelectionInvalid()
    lines = [*bank.skeleton, bank.notice,
        "강도 정의: 최근 실제 관측 N행 순매수합 ÷ 동일 창의 종목 일평균 거래대금."
        " N은 실제 제공 행수와 RECENT_DAYS 중 작은 값; 전체 거래대금 비중·보유율이 아니다.",
        "각 fact의 확정일·실제 관측 N·주체·단위는 변경할 수 없다."]
    lines.extend(f"{fact.id} | {fact.sentence}" for fact in bank.facts)
    return "\n".join(lines)


def explain(signals: dict, gate2: GateResult, meta: dict, *, bank=None, execution_context=None) -> str:
    """검증된 팩트로 해석 문장을 선택한다. 검증 fact ID 외 자유 텍스트는 Gate3에서 거부."""
    # 검증 안 된 팩트는 해석 대상이 아니다(게이트2 통과가 전제).
    if not gate2.passed:
        raise ValueError("게이트2 미통과 팩트로는 해석하지 않는다.")

    if execution_context is not None: execution_context.check('explain')
    load_dotenv(dotenv_path=_ENV_FILE, override=False)       # OPENAI_API_KEY 확보(값 미출력)

    # 프롬프트 = 고정 지시문 + 결정론적 팩트 텍스트. 사용자 원문이 낄 자리가 없다.
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.replace("{{facts}}", _facts_to_text(signals, meta, bank))

    kwargs = {} if execution_context is None else {'timeout':execution_context.timeout('openai'), 'max_retries':0, 'max_completion_tokens':1000}
    llm = ChatOpenAI(model=_MODEL, temperature=_TEMPERATURE, **kwargs)
    response = llm.invoke(prompt)
    if execution_context is not None: execution_context.check('openai_result')
    return response.content
