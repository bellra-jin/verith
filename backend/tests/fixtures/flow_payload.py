"""Synthetic v1 payload from the real pure exporter; no graph/data/LLM imports."""

import sys
from pathlib import Path
from uuid import uuid4

_AI_SRC = str(Path(__file__).resolve().parents[3] / "ai" / "src")
sys.path.append(_AI_SRC)
try:
    from agents.flow.export.to_json import build_payload
    from agents.flow.schemas import GateResult
finally:
    sys.path.remove(_AI_SRC)


def make_flow_payload() -> dict:
    signals = {
        "alignment": "엇갈림",
        "consecutive": {"외국인": {"days": 0, "signal": False}},
        "strength": {"외국인": {"ratio": 0, "strong": False}},
        "persistence": {"외국인": {"sum_5": 0, "sum_20": -15.5, "consistent": False}},
        "daily": [{"date": "2026-11-05", "개인": 0, "외국인": -3.5, "기관": 3.5}],
        "inst_detail": None,
        "ownership": [{"date": "2026-11-05", "ratio": 0}],
        "price_daily": [
            {
                "date": "2026-11-05",
                "close": 100,
                "change": 0,
                "change_rate": 0.0,
                "volume": 0,
                "frgn_qty": None,
                "inst_qty": 0,
            }
        ],
    }
    return build_payload(
        signals,
        {
            "ticker": "005930",
            "stock_name": "합성 종목",
            "market": "KOSPI200",
            "base_date": "2026-11-05",
        },
        GateResult(gate=1, passed=True, checks=["합성 입력"]),
        GateResult(gate=2, passed=True, checks=["합성 수치"]),
        GateResult(gate=3, passed=True, checks=["합성 해석"]),
        "합성 해석",
        uuid4(),
        provider="fixture",
        model="synthetic",
    )
