"""Limited numeric syntax boundary for LLM prose; code value/metrics stay authoritative.

Only configured indicator identifiers and exact code-owned watchpoint fields have
numeric roles. This does not interpret Korean number words or arbitrary relations.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import re


FAILURE_REASON = "numeric_claim_unsupported"
DETAIL_FIELDS = ("detail", "detail_reason", "detail_caution", "detail_watchpoint")
SUMMARY_FIELDS = ("one_line_summary", "trend_interpretation", "signal_interpretation",
                  "risk_interpretation", "timeframe_alignment", "what_to_watch_next",
                  "invalidation_or_caution")
SUMMARY_LISTS = ("key_drivers", "warning_points")


@dataclass(frozen=True)
class NumericRole:
    indicator: str
    role: str
    expression: str
    unit: str
    window: int | None
    fields: tuple[str, ...]


@dataclass(frozen=True)
class NumericFailure:
    target: str
    indicator: str | None = None


def _plain(text: str) -> str:
    return " ".join(text.replace("**", "").split())


def build_roles(*, ma_windows: Sequence[int], rsi_period: int,
                references: Sequence[tuple[str, str]]) -> tuple[NumericRole, ...]:
    """Caller supplies code configuration and code-owned templates, never LLM text."""
    if (len(ma_windows) != 3 or any(type(n) is not int or n <= 0 for n in ma_windows)
            or len(set(ma_windows)) != 3 or type(rsi_period) is not int or rsi_period <= 0):
        raise ValueError("Invalid numeric role configuration")
    fields = DETAIL_FIELDS + SUMMARY_FIELDS + SUMMARY_LISTS + ("text",)
    roles = [NumericRole("moving_average", "identifier", expression, "daily MA window", n, fields)
             for n in ma_windows for expression in (f"{n}MA", f"{n}일선")]
    roles.append(NumericRole("rsi", "identifier", f"RSI({rsi_period})", "RSI period", rsi_period, fields))
    for indicator, expression in references:
        if indicator not in {"moving_average", "rsi"} or type(expression) is not str or not expression.strip():
            raise ValueError("Invalid numeric role configuration")
        roles.append(NumericRole(indicator, "reference", _plain(expression), "fixed code watchpoint", None,
                                 ("detail_watchpoint", "what_to_watch_next")))
    return tuple(roles)


def _identifier_span(text: str, start: int, end: int) -> bool:
    before, after = text[:start], text[end:]
    left = before.rstrip(" '\"‘’“”`([{\t\r\n")
    right = after.lstrip(" '\"‘’“”`)]}\t\r\n")
    previous, following = before[-1:], after[:1]
    # Signed/decimal/fractional prefixes and longer identifiers cannot borrow a window digit.
    if (previous.isnumeric() or previous.isascii() and previous.isalnum()
            or previous == "." or left and left[-1] in "_/+-−＋﹣／"):
        return False
    if left and left[-1] in ".,":
        prefix = left[:-1].rstrip()
        if prefix and prefix[-1].isnumeric() or not prefix and left[-1] == ".":
            return False
    if following.isnumeric() or following.isascii() and (following.isalnum() or following == "_"):
        return False
    if re.match(r"(?:[%％‰$]|(?:원|배|일선|일|주|개월|년|시간|분|초|선)(?:$|\s|[.,;:)]|[은는이가를에도]))", right):
        return False
    return True


def unsupported(text: str, *, indicators: Sequence[str], field: str,
                roles: Sequence[NumericRole]) -> bool:
    """Reject all remaining Unicode numeric characters after closed role matching."""
    plain = _plain(text)
    applicable = [r for r in roles if r.indicator in indicators and field in r.fields]
    # An entire fixed watchpoint is a reference; appending a current value/claim never qualifies.
    if any(r.role == "reference" and plain == r.expression for r in applicable):
        return False
    spans = []
    for role in applicable:
        if role.role != "identifier":
            continue
        for match in re.finditer(re.escape(role.expression), plain):
            if _identifier_span(plain, match.start(), match.end()):
                spans.append((match.start(), match.end()))
    masked = list(plain)
    for start, end in spans:
        masked[start:end] = " " * (end - start)
    return any(char.isnumeric() for char in masked)


def evaluate(output: dict, *, indicators: Sequence[str],
             roles: Sequence[NumericRole]) -> tuple[NumericFailure, ...]:
    """Targets map to existing per-indicator or whole-interpretation fallback."""
    failures = []
    for key in ("interpretation_text",) + SUMMARY_FIELDS:
        text = output.get(key)
        field = "text" if key == "interpretation_text" else key
        if isinstance(text, str) and unsupported(text, indicators=indicators, field=field, roles=roles):
            failures.append(NumericFailure(f"interpretation.{field}"))
    for key in SUMMARY_LISTS:
        items = output.get(key)
        if isinstance(items, list):
            for index, text in enumerate(items):
                if isinstance(text, str) and unsupported(text, indicators=indicators, field=key, roles=roles):
                    failures.append(NumericFailure(f"interpretation.{key}[{index}]"))
    details = output.get("details")
    if isinstance(details, list):
        for entry in details:
            if not isinstance(entry, dict) or entry.get("indicator") not in indicators:
                continue  # Existing structure validator already closes this path.
            indicator = entry["indicator"]
            for field in DETAIL_FIELDS:
                text = entry.get(field)
                if isinstance(text, str) and unsupported(text, indicators=(indicator,), field=field, roles=roles):
                    failures.append(NumericFailure(f"technical_signals[{indicator}].{field}", indicator))
    return tuple(failures)
