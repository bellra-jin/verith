"""New-generation Gate3 expectations. Raw AI pytest is not the safe entry."""
from datetime import date, timedelta
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from agents.flow.domain.interpretation_claims import build_bank, compose
from agents.flow.domain.verification.interpretation import verify_interpretation


def _case():
    dates = [(date(2026, 7, 1) + timedelta(days=i)).isoformat() for i in range(20)]
    subjects = {"개인": 1, "외국인": -2, "기관": 1}
    s = dict(alignment="엇갈림", daily=[dict(date=d, **subjects) for d in dates],
        strength={k: dict(ratio=v*5/100, strong=False) for k, v in subjects.items()},
        consecutive={k: dict(days=20 if v>0 else 0, signal=v>0) for k, v in subjects.items()},
        persistence={k: dict(sum_5=v*5, sum_20=v*20, consistent=True) for k, v in subjects.items()},
        ownership=None, price_daily=None)
    meta = dict(stock_name="합성 종목", ticker="005930", base_date=dates[-1], market=None)
    evidence = dict(supply=[dict(date=d, 거래대금=100, **subjects) for d in dates], quotes=None, ownership=None)
    bank = build_bank(s, evidence, meta, gate2_passed=True)
    ids = tuple(f.id for f in bank.facts if f.kind=="strength")
    return s, meta, bank, ids, compose(bank, ids, meta, s)


def test_gate3_passes_on_code_composed_grounded_interpretation():
    s, m, b, ids, text = _case()
    assert verify_interpretation(text, s, bank=b, selection=ids, meta=m).passed


def test_gate3_catches_flipped_foreign_direction():
    s, m, b, ids, text = _case()
    assert not verify_interpretation(text.replace("순매도", "순매수"), s, bank=b, selection=ids, meta=m).passed


def test_gate3_catches_personal_misattribution():
    s, m, b, ids, text = _case()
    assert not verify_interpretation(text+"개인과 외국인은 동반매수다.", s, bank=b, selection=ids, meta=m).passed


def test_gate3_catches_opposite_alignment():
    s, m, b, ids, text = _case()
    assert not verify_interpretation(text.replace("엇갈림", "동반매수"), s, bank=b, selection=ids, meta=m).passed


def test_gate3_requires_manifest_and_preserves_fixed_order():
    s, m, b, ids, text = _case()
    assert compose(b, tuple(reversed(ids)), m, s)==text
    assert not verify_interpretation(text, s).passed
    assert not verify_interpretation("", s, bank=b, selection=ids, meta=m).passed
