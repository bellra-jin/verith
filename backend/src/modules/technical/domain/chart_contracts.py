"""Backend typed mirror of the pinned canonical Technical pure model definitions."""
from __future__ import annotations
INTRADAY_CONFIDENCE_ADJUSTMENT_CAP=0.05
INTRADAY_RISK_NOTE_MAX_COUNT=3
from enum import Enum

class Regime(str, Enum):
    """국면 — `daily_regime` · `final_regime` 공통 값 집합 (enums.md §1)."""
    OVERSOLD_REBOUND_WATCH = 'oversold_rebound_watch'
    OVERHEATED = 'overheated'
    BULLISH_REVERSAL_WATCH = 'bullish_reversal_watch'
    UPTREND_INTACT = 'uptrend_intact'
    DOWNTREND = 'downtrend'
    SIDEWAYS = 'sideways'
    UNAVAILABLE = 'unavailable'

class Consensus(str, Enum):
    """신호 종합 — `signal.consensus` (enums.md §2). 경계값은 config(MVP 잠정)."""
    STRONG_POSITIVE = 'strong_positive'
    WEAK_POSITIVE = 'weak_positive'
    NEUTRAL = 'neutral'
    WEAK_NEGATIVE = 'weak_negative'
    STRONG_NEGATIVE = 'strong_negative'

class Signal(str, Enum):
    """지표별 개별 신호 — `technical_signals[].signal` (enums.md §3)."""
    POSITIVE = 'positive'
    NEUTRAL = 'neutral'
    NEGATIVE = 'negative'

class DirectionalBias(str, Enum):
    """해석 방향성 표시값 — `interpretation.directional_bias`. **consensus 에서 결정론 파생**(재판정 아님).

    프론트 카드가 상승/중립/하락을 한눈에 뿌리기 위한 표시 필드다. LLM 이 만들지 않는다(코드 파생)."""
    BULLISH = 'bullish'
    NEUTRAL = 'neutral'
    BEARISH = 'bearish'

class Trend(str, Enum):
    """타임프레임 추세 — `weekly_trend` · `monthly_trend` (enums.md §4)."""
    UP = 'up'
    DOWN = 'down'
    SIDEWAYS = 'sideways'
    UNAVAILABLE = 'unavailable'

class AlignmentFlag(str, Enum):
    """멀티프레임 정합 — `alignment_flag` (enums.md §5)."""
    ALIGNED = 'aligned'
    COUNTER_TREND = 'counter_trend'
    NEUTRAL = 'neutral'

class ConfidenceLevel(str, Enum):
    """신뢰도 구간(표시용) — `confidence`에서 파생. **DB 저장 안 함** (enums.md §6, contracts.md §3)."""
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'

class RiskFlag(str, Enum):
    """리스크 라벨(코드 생성 배열) — `risk.items[].flag` (enums.md §7)."""
    VOLUME_NOT_CONFIRMED = 'volume_not_confirmed'
    NEAR_RESISTANCE = 'near_resistance'
    NEAR_SUPPORT = 'near_support'
    MIXED_SIGNALS = 'mixed_signals'
    OVERHEATED_MOMENTUM = 'overheated_momentum'
    COUNTER_HIGHER_TREND = 'counter_higher_trend'
    LOW_LIQUIDITY = 'low_liquidity'

class DataStatus(str, Enum):
    """데이터/분석 상태 — `data_status` (enums.md §8)."""
    NORMAL = 'normal'
    STALE_CACHE = 'stale_cache'
    DATA_LIMITED = 'data_limited'
    REGIME_UNAVAILABLE = 'regime_unavailable'

class GenerationSource(str, Enum):
    """LLM 문장 최종 출처 — `interpretation.source` · `technical_signals[].detail_source` 공유 (enums.md §9).

    필드명은 contracts 기준대로 `source` / `detail_source`를 각각 유지하되, 값 집합은 이 하나를 공유한다.
    """
    LLM = 'llm'
    LLM_REGENERATED = 'llm_regenerated'
    TEMPLATE_FALLBACK = 'template_fallback'

class ChartPeriod(str, Enum):
    """차트 기간 — `charts[].period` (enums.md §10). 멤버명은 숫자로 시작 못 해 영문으로 둔다."""
    THREE_MONTHS = '3m'
    ONE_YEAR = '1y'
    FIVE_YEARS = '5y'
    ONE_DAY = '1d'

class VerificationOutcome(str, Enum):
    """검증 최종 결과 — `verification.outcome`.

    enums.md에 별도 표는 없고 contracts.md 예시에서 확인되는 값만 반영한다.
    재생성/부분 실패 등은 별도 값이 아니라 `regen_count`·`interpretation_source`·`detail_source`로 표현한다.
    """
    PASSED = 'passed'
    TEMPLATE_FALLBACK = 'template_fallback'

class IndicatorType(str, Enum):
    """지표 종류 — `technical_signals[].indicator` (contracts.md). 기본 5개만 허용(오타·임의값 방지)."""
    MOVING_AVERAGE = 'moving_average'
    RSI = 'rsi'
    VOLUME = 'volume'
    SUPPORT_RESISTANCE = 'support_resistance'
    PATTERN = 'pattern'

import math
import re
from datetime import date as _date
from typing import Annotated
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator
_ISO_DATE_RE = re.compile('^\\d{4}-\\d{2}-\\d{2}$')

def _validate_iso_date(value: str) -> str:
    """ISO 'YYYY-MM-DD' 형식 + 실제 달력 날짜만 허용 (schema 내부 validator, service 의존 없음)."""
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        raise ValueError(f"date must be ISO 'YYYY-MM-DD': {value!r}")
    try:
        _date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'invalid calendar date: {value!r}') from exc
    return value

def _validate_finite_non_negative(value: int | float) -> int | float:
    """inf/nan 불허 + 음수 불허. int/float 표현은 그대로 보존(강제 캐스팅 없음)."""
    if isinstance(value, float) and (not math.isfinite(value)):
        raise ValueError('must be a finite number (no inf/nan)')
    if value < 0:
        raise ValueError('must be >= 0')
    return value
IsoDate = Annotated[str, AfterValidator(_validate_iso_date)]
NonNegativeNumber = Annotated[int | float, AfterValidator(_validate_finite_non_negative)]

class OHLCV(BaseModel):
    """한 봉(일/주/월)의 내부 표준 OHLCV. 계약에 없는 필드 유입 차단(extra=forbid)."""
    model_config = ConfigDict(extra='forbid')
    date: IsoDate
    open: NonNegativeNumber
    high: NonNegativeNumber
    low: NonNegativeNumber
    close: NonNegativeNumber
    volume: int = Field(ge=0)
    trading_value: int = Field(ge=0)

    @model_validator(mode='after')
    def _high_ge_low(self) -> OHLCV:
        if self.high < self.low:
            raise ValueError(f'high({self.high}) must be >= low({self.low})')
        return self

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
AnnotationKind = Literal['golden_cross', 'dead_cross', 'volume_spike', 'support_touch', 'resistance_touch', 'rsi_overbought', 'rsi_oversold', 'box_range_candidate', 'box_breakout_candidate', 'cup_handle_candidate']

class _StrictModel(BaseModel):
    """chart 하위 모델 공통 베이스 — 문서에 없는 key 거부."""
    model_config = ConfigDict(extra='forbid')

class MaPoint(_StrictModel):
    date: IsoDate
    value: float = Field(ge=0, allow_inf_nan=False)

class MovingAverageOverlay(_StrictModel):
    window: int = Field(gt=0)
    points: list[MaPoint]

class SupportResistanceOverlay(_StrictModel):
    model_config = ConfigDict(extra='forbid', serialize_by_alias=True)
    type: Literal['support', 'resistance']
    price: float = Field(ge=0, allow_inf_nan=False)
    from_: IsoDate = Field(alias='from')
    to: IsoDate
    touch_count: int = Field(ge=0)

class Overlays(_StrictModel):
    moving_average: list[MovingAverageOverlay]
    support_resistance: list[SupportResistanceOverlay]

class RsiPoint(_StrictModel):
    date: IsoDate
    value: float = Field(ge=0, le=100, allow_inf_nan=False)

class RsiSubchart(_StrictModel):
    period: int = Field(gt=0)
    overbought: int = Field(ge=0, le=100)
    oversold: int = Field(ge=0, le=100)
    points: list[RsiPoint]

    @model_validator(mode='after')
    def _oversold_lt_overbought(self) -> RsiSubchart:
        if self.oversold >= self.overbought:
            raise ValueError(f'oversold({self.oversold}) must be < overbought({self.overbought})')
        return self

class VolumeBar(_StrictModel):
    date: IsoDate
    volume: int = Field(ge=0)
    avg_volume: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    is_spike: bool

class VolumeSubchart(_StrictModel):
    avg_window: int = Field(gt=0)
    bars: list[VolumeBar]

class Subcharts(_StrictModel):
    rsi: RsiSubchart
    volume: VolumeSubchart

class ChartAnnotation(_StrictModel):
    id: str
    kind: AnnotationKind
    date: IsoDate
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    label: str
    importance: Literal['low', 'medium', 'high']
    source: Literal['code']
    meta: dict[str, Any] = Field(default_factory=dict)

class ChartData(_StrictModel):
    candle_unit: Literal['D', 'W', 'M']
    candles: list[OHLCV]
    overlays: Overlays
    subcharts: Subcharts
    annotations: list[ChartAnnotation]

import re
from datetime import datetime
from typing import Annotated, Literal
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator
_ISO_DATETIME_RE = re.compile('^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}$')

def _validate_iso_datetime(value: str) -> str:
    """ISO 'YYYY-MM-DDTHH:MM:SS' 형식 + 실제 달력·시각만 허용(초 단위, tz 없음)."""
    if not isinstance(value, str) or not _ISO_DATETIME_RE.match(value):
        raise ValueError(f"timestamp must be ISO 'YYYY-MM-DDTHH:MM:SS': {value!r}")
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'invalid datetime: {value!r}') from exc
    return value
IsoDateTime = Annotated[str, AfterValidator(_validate_iso_datetime)]
IntradayInterval = Literal['1min']

class _StrictModel(BaseModel):
    """intraday 하위 모델 공통 베이스 — 문서에 없는 key 거부."""
    model_config = ConfigDict(extra='forbid')

class IntradayCandle(_StrictModel):
    """한 분봉. D/W/M OHLCV와 달리 `timestamp`(날짜+시각)를 가진다."""
    timestamp: IsoDateTime
    open: NonNegativeNumber
    high: NonNegativeNumber
    low: NonNegativeNumber
    close: NonNegativeNumber
    volume: int = Field(ge=0)
    trading_value: int | None = Field(default=None, ge=0)
    interval: IntradayInterval

    @model_validator(mode='after')
    def _high_ge_low(self) -> IntradayCandle:
        if self.high < self.low:
            raise ValueError(f'high({self.high}) must be >= low({self.low})')
        return self

class IntradayPoint(_StrictModel):
    """시각별 파생 수치 1점 — short MA / VWAP / intraday RSI 공용(라인 시리즈)."""
    timestamp: IsoDateTime
    value: float = Field(ge=0, allow_inf_nan=False)

class IntradayChartData(_StrictModel):
    """1d 차트 데이터. `ChartPayload.chart_data` 판별 유니온의 intraday 분기.

    D/W/M `ChartData`와 완전히 분리된 타입이며, candle_unit="1min"으로 구분된다.
    """
    candle_unit: Literal['1min']
    candles: list[IntradayCandle]
    previous_close: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    day_high: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    day_low: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    short_ma: list[IntradayPoint] = Field(default_factory=list)
    vwap: list[IntradayPoint] = Field(default_factory=list)
    rsi: list[IntradayPoint] = Field(default_factory=list)
IntradayStatus = Literal['normal', 'data_limited', 'unavailable', 'market_closed', 'not_trading_day', 'api_error']
IntradayRegimeHint = Literal['upward_intraday', 'downward_intraday', 'sideways_intraday', 'volatile_intraday', 'unavailable']
RegimeAlignment = Literal['aligned', 'counter', 'neutral', 'unavailable']
ShortMaTrend = Literal['up', 'down', 'flat']

class IntradayContext(_StrictModel):
    """1D intraday 보조 컨텍스트 — `TechnicalAgentOutput.intraday_context`(optional).

    **관측 데이터 컨테이너**다. D/W/M 판단의 보조 근거로만 쓰며, `final_regime`을 바꾸지 않는다.
    이 단계 범위는 **계약(필드)뿐** — 계산 로직·실제 보정은 후속(Phase 2)이다.
    intraday risk는 기존 `RiskFlag`(enums.py)를 확장하지 않고 `risk_notes`(문자열 리스트)로만 담는다.
    값이 없으면 0/빈값으로 강제 채우지 않고 None(또는 상태 라벨)로 둔다(honest scoping).
    """
    source: Literal['KIS'] = 'KIS'
    status: IntradayStatus
    as_of: datetime
    interval: IntradayInterval | None = None
    latest_timestamp: IsoDateTime | None = None
    latest_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    previous_close: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    intraday_return_pct: float | None = Field(default=None, allow_inf_nan=False)
    day_high: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    day_low: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    day_range_position: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    short_ma: list[IntradayPoint] = Field(default_factory=list)
    short_ma_trend: ShortMaTrend | None = None
    cumulative_volume: int | None = Field(default=None, ge=0)
    cumulative_trading_value: int | None = Field(default=None, ge=0)
    volume_spike: bool | None = None
    vwap: list[IntradayPoint] = Field(default_factory=list)
    rsi: list[IntradayPoint] = Field(default_factory=list)
    intraday_regime_hint: IntradayRegimeHint | None = None
    regime_alignment: RegimeAlignment | None = None
    confidence_adjustment: float = Field(default=0.0, ge=-INTRADAY_CONFIDENCE_ADJUSTMENT_CAP, le=INTRADAY_CONFIDENCE_ADJUSTMENT_CAP, allow_inf_nan=False)
    signal_score_adjustment: float = Field(default=0.0, ge=-INTRADAY_CONFIDENCE_ADJUSTMENT_CAP, le=INTRADAY_CONFIDENCE_ADJUSTMENT_CAP, allow_inf_nan=False)
    risk_notes: list[str] = Field(default_factory=list, max_length=INTRADAY_RISK_NOTE_MAX_COUNT)

import re
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class _StrictModel(BaseModel):
    """모든 계약 모델의 베이스. 계약에 없는 필드가 들어오면 거부한다(임의 필드 유입 방지)."""
    model_config = ConfigDict(extra='forbid')
_TICKER_RE = re.compile('\\d{6}')

class TechnicalAgentInput(_StrictModel):
    ticker: str
    query: str
    request_id: str
    as_of: datetime
    stock_name: str | None = None

    @field_validator('ticker')
    @classmethod
    def _ticker_is_6_digits(cls, v: str) -> str:
        if not _TICKER_RE.fullmatch(v):
            raise ValueError('ticker must be exactly 6 digits')
        return v

    @field_validator('query', 'request_id')
    @classmethod
    def _not_blank(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f'{info.field_name} must not be blank')
        return v

    @field_validator('as_of')
    @classmethod
    def _as_of_not_future(cls, v: datetime) -> datetime:
        now = datetime.now(v.tzinfo) if v.tzinfo is not None else datetime.now()
        if v > now:
            raise ValueError('as_of must not be in the future')
        return v

class RegimeResult(_StrictModel):
    """멀티프레임 국면. → TECHNICAL_REPORTS. LLM이 바꿀 수 없는 코드 확정값."""
    daily_regime: Regime
    final_regime: Regime
    weekly_trend: Trend
    monthly_trend: Trend
    alignment_flag: AlignmentFlag
    regime_context: str

class SignalSummary(_StrictModel):
    """신호 종합·신뢰도. regime 판단 불가 시 상위에서 null 가능(종합·신뢰도 스킵)."""
    consensus: Consensus
    signal_score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    confidence_basis: str

class TechnicalSignal(_StrictModel):
    """지표별 기술 신호. → REPORT_SIGNALS.

    코드 확정(indicator·signal·value·metrics·weight)과 LLM 서술(detail)의 경계를 한 항목에 담는다.
    필드명은 `indicator`이며 `strategy`는 쓰지 않는다(contracts.md).
    """
    indicator: IndicatorType
    signal: Signal
    value: float | None
    metrics: list[str]
    detail: str
    detail_source: GenerationSource
    weight: float = Field(ge=0.0, le=1.0)
    detail_reason: str | None = None
    detail_caution: str | None = None
    detail_watchpoint: str | None = None

class RiskItem(_StrictModel):
    """리스크 관찰점 1건. → REPORT_RISK_NOTES. flag·note·ref_price를 한 항목에 묶어 짝짓기 오류 방지."""
    flag: RiskFlag
    note: str
    ref_price: float | None = None

class RiskSummary(_StrictModel):
    items: list[RiskItem]

class ChartPayload(_StrictModel):
    """기간별 차트. → REPORT_CHARTS. chart_data는 자유 dict가 아니라 chart_annotation_spec.md 정본
    구조를 따르는 계약으로 검증한다. D/W/M은 ChartData(schemas/chart.py), 1d 장중 분봉은
    IntradayChartData(schemas/intraday.py)로, `candle_unit`을 discriminator로 하는 판별 유니온이다.
    chart_builder가 만든 dict가 여기서 candle_unit에 따라 해당 타입으로 파싱·검증된다."""
    period: ChartPeriod
    chart_data: ChartData | IntradayChartData = Field(discriminator='candle_unit')

    @model_validator(mode='after')
    def _period_matches_candle_unit(self) -> ChartPayload:
        expected = {ChartPeriod.THREE_MONTHS: 'D', ChartPeriod.ONE_YEAR: 'D', ChartPeriod.FIVE_YEARS: 'W', ChartPeriod.ONE_DAY: '1min'}[self.period]
        if self.chart_data.candle_unit != expected:
            raise ValueError(f'period={self.period.value}의 candle_unit은 {expected}여야 합니다: {self.chart_data.candle_unit}')
        return self

class InterpretationResult(_StrictModel):
    """종합 해석. → REPORT_INTERPRETATION. 원칙적으로 항상 존재(검증 실패 시 template_fallback).

    `text` 는 하위호환·검증용 종합 문장(3~5문장). 아래 구조화 섹션은 **프론트 카드 렌더용 additive 필드**로,
    계산값을 재산출하지 않고 **이미 확정된 regime/signal/risk 를 설명·파생**한 것이다. LLM 실패 시에도
    template fallback 이 같은 구조를 deterministic 하게 채운다(빈약 착지 방지). `directional_bias` 는 LLM 이
    아니라 **consensus 에서 코드가 파생**한다(재판정 아님)."""
    text: str
    source: GenerationSource
    one_line_summary: str | None = None
    directional_bias: DirectionalBias | None = None
    trend_interpretation: str | None = None
    signal_interpretation: str | None = None
    risk_interpretation: str | None = None
    timeframe_alignment: str | None = None
    key_drivers: list[str] = Field(default_factory=list)
    warning_points: list[str] = Field(default_factory=list)
    what_to_watch_next: str | None = None
    invalidation_or_caution: str | None = None

class VerificationResult(_StrictModel):
    """검증 결과. → REPORT_VERIFICATION."""
    calc_passed: bool
    regime_passed: bool
    label_matched: bool
    outcome: VerificationOutcome
    regen_count: int

class TechnicalAgentOutput(_StrictModel):
    """에이전트 최종 반환 JSON. 의미 단위 중첩 구조 유지(backend가 테이블별 flatten 저장)."""
    request_id: str
    ticker: str
    as_of: datetime
    source: Literal['KIS', 'KIS (stale)']
    trace_id: str
    data_status: DataStatus
    regime: RegimeResult
    signal: SignalSummary | None = None
    technical_signals: list[TechnicalSignal] = Field(default_factory=list)
    risk: RiskSummary | None = None
    charts: list[ChartPayload] = Field(default_factory=list)
    interpretation: InterpretationResult
    verification: VerificationResult
    intraday_context: IntradayContext | None = None
    resolved_stock_name: str | None = None
