"""infrastructure/llm/explain.py — 검증된 팩트 → LLM 한국어 해석 문장.

원리: "LLM을 잘 쓰기가 아니라, 거짓말 못 하게 가두기."
  LLM은 확률적·환각적이므로 (1) 입력을 검증된 팩트로만 좁히고(원문·원본 데이터
  차단), (2) 지시문으로 역할을 해석 전용으로 못박고, (3) 저온도로 변동을 줄인다.
  2겹째인 게이트3(해석↔팩트 검증)은 다음 단계 — 여기선 관통선만 얇게 뚫는다.

입력: signals dict + gate2(GateResult, 통과분) + 표시용 meta(stock_name/ticker/base_date)
      — 사용자 원문·원본 KIS DataFrame은 넣지 않는다(인젝션·환각 차단).
출력: 한국어 해석 문자열(2~3문장).
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from ... import config
from ...domain.signals import SUBJECTS
from ...domain.observation_window import observation_window, relation_text
from ...domain.models import GateResult

_AI_ROOT = Path(__file__).resolve().parents[5]
_ENV_FILE = _AI_ROOT / ".env"
_PROMPT_PATH = Path(__file__).parents[2] / "prompts" / "explain.txt"
_MODEL = config.INTERPRETER_MODEL    # 해석용(비용 낮음). 교체는 config 한 곳에서 — payload 기록과 동기.
_TEMPERATURE = 0.2        # 낮게 — 해석이 튀지 않게.


def _facts_to_text(signals: dict, meta: dict) -> str:
    """검증된 팩트 dict → 사람이 읽는 팩트 목록 텍스트(결정론적).

    LLM에 넣는 건 '이미 확정된 숫자'뿐. 여기서 새 숫자를 만들거나 바꾸지 않는다.
    각 주체의 순매수/순매도 '방향'은 코드가 ratio 부호로 확정해 팩트에 박는다
    → LLM은 방향을 추론하지 않고 복사만 하면 된다(관계 환각 예방). 강도는
    표시용으로만 백분율화(render와 동일 규칙), 내부 팩트는 불변.
    """
    consecutive = signals.get("consecutive", {})
    strength = signals.get("strength", {})
    persistence = signals.get("persistence", {})
    window = observation_window(signals, config.RECENT_DAYS, config.TREND_DAYS)
    lines = [
        f"종목: {meta.get('stock_name')} ({meta.get('ticker')})",
        f"기준일: {meta.get('base_date')}",
        f"관측 안내: {window['notice']}",
        f"외국인·기관 수급구도: {signals.get('alignment')}",
        "  ('엇갈림/동반매수/동반매도'는 오직 외국인과 기관 두 주체 사이의 관계다."
        " 개인은 이 관계에 포함하지 않는다.)",
    ]
    for subject in SUBJECTS:                     # 개인 → 외국인 → 기관 순서 고정
        days = consecutive.get(subject, {}).get("days")
        ratio = strength.get(subject, {}).get("ratio")
        if ratio is None:
            direction, ratio_pct = "방향 미상", "N/A"
        else:
            direction = "순매수" if ratio > 0 else "순매도" if ratio < 0 else "중립"
            ratio_pct = f"{'+' if ratio > 0 else ''}{ratio * 100:.1f}%"
        # 관측 근거가 충족된 제공 자료에 한해서만 저장 합/판정을 전달한다.
        persist = ""
        if window["status"] == "sufficient_rows":
            p = persistence[subject]
            s5, s20 = p["sum_5"], p["sum_20"]
            persist = (f", 제공 자료 기준 {window['shortLabel']} 순매수 합 {s5 / 100:+,.1f}억원"
                       f" · {window['longLabel']} 합 {s20 / 100:+,.1f}억원"
                       f" ({relation_text(window['relations'][subject])})")
        lines.append(
            f"- {subject}: {direction} 방향(순매수 강도 {ratio_pct}),"
            f" 최근 연속 순매수 {days}일{persist}"
        )
    # 시세 맥락: 기준일 종가·등락률 (게이트2 규칙8 검증분의 마지막 행).
    price = signals.get("price_daily")
    if price:
        last = price[-1]
        lines.append(
            f"- 기준일 시세: 종가 {last['close']:,.0f}원,"
            f" 전일 대비 {last['change']:+,.0f}원 ({last['change_rate']:+.2f}%)"
        )
    # 외국인 한도소진율: 표시 창의 처음↔끝 변화 (게이트2 규칙7 검증분).
    ownership = signals.get("ownership")
    if ownership:
        first, latest = ownership[0]["ratio"], ownership[-1]["ratio"]
        lines.append(
            f"- 외국인 한도소진율: 최신 {latest:.2f}%,"
            f" 표시 창({len(ownership)}거래일) 동안 {latest - first:+.2f}%p 변화"
        )
    return "\n".join(lines)


def explain(signals: dict, gate2: GateResult, meta: dict, *, execution_context=None) -> str:
    """검증된 팩트로 해석 문장을 생성한다. 팩트만 입력, 원문·원본 데이터 차단."""
    # 검증 안 된 팩트는 해석 대상이 아니다(게이트2 통과가 전제).
    if not gate2.passed:
        raise ValueError("게이트2 미통과 팩트로는 해석하지 않는다.")

    if execution_context is not None: execution_context.check('explain')
    load_dotenv(dotenv_path=_ENV_FILE, override=False)       # OPENAI_API_KEY 확보(값 미출력)

    # 프롬프트 = 고정 지시문 + 결정론적 팩트 텍스트. 사용자 원문이 낄 자리가 없다.
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.replace("{{facts}}", _facts_to_text(signals, meta))

    kwargs = {} if execution_context is None else {'timeout':execution_context.timeout('openai'), 'max_retries':0, 'max_completion_tokens':1000}
    llm = ChatOpenAI(model=_MODEL, temperature=_TEMPERATURE, **kwargs)
    response = llm.invoke(prompt)
    if execution_context is not None: execution_context.check('openai_result')
    return response.content.strip()
