"""Existing quote/source verification; no collection or output writes."""
from __future__ import annotations

import re
from rapidfuzz import fuzz

from ...config import RAW_DIR


VERIFY_THRESHOLD = 90


def _norm_ws(text: str) -> str:
    """Collapse every whitespace run to a single space.

    The LLM quote and the source may differ only in newlines/indentation (chunking,
    PDF-to-text), so both sides are normalized the same way before comparison.
    """
    return " ".join(str(text or "").split())


_SOURCE_NORM_CACHE: dict[str, str] = {}


def _load_source_norm(origin: str) -> str:
    """Whitespace-normalized full source text for a filer (stock_code), cached per origin.

    Verifying against the *whole* filing (not the originating chunk) makes the check
    independent of CHUNK_SIZE and immune to quotes that straddle a chunk boundary.
    Empty string (missing file) means every evidence for this origin fails to verify.
    """
    if origin not in _SOURCE_NORM_CACHE:
        path = RAW_DIR / origin / "business_content.txt"
        if path.exists():
            _SOURCE_NORM_CACHE[origin] = _norm_ws(path.read_text(encoding="utf-8"))
        else:
            print(f"  [verify] no source text for {origin}; its evidence cannot be verified")
            _SOURCE_NORM_CACHE[origin] = ""
    return _SOURCE_NORM_CACHE[origin]


_ELLIPSIS_RE = re.compile(r"\.\.\.+|…")


def _match_score(span: str, source_norm: str) -> int:
    """Verbatim -> 100, else best-window fuzzy ratio (tolerates 조사/구두점 drift)."""
    if span in source_norm:
        return 100
    return int(round(fuzz.partial_ratio(span, source_norm)))


def verify_evidence(evidence: str, source_norm: str) -> tuple[bool, int]:
    """Does ``evidence`` actually occur in the source? Exact substring -> (True, 100).

    The LLM often stitches two non-contiguous — but individually verbatim — spans with
    an ellipsis (``A ... B``). Scoring the whole string then penalizes the gap and drops
    a genuinely grounded quote, so ellipsis-joined quotes are verified **per fragment**
    and scored by their weakest fragment. A single span (or a summarized/fabricated
    quote) is scored whole; both are rejected below :data:`VERIFY_THRESHOLD`.
    """
    ev = _norm_ws(evidence)
    if not ev or not source_norm:
        return False, 0
    fragments = [f for f in (_norm_ws(p) for p in _ELLIPSIS_RE.split(ev)) if len(f) >= 8]
    if len(fragments) > 1:
        worst = min(_match_score(f, source_norm) for f in fragments)
        return worst >= VERIFY_THRESHOLD, worst
    score = _match_score(ev, source_norm)
    return score >= VERIFY_THRESHOLD, score
