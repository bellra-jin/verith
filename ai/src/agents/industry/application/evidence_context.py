"""기업·거시 답변용 근거 문맥, 공시 출처 및 인용 표시.

조회/모델 실행과 분리된 근거 표시 책임이다. 기존 RAW_DIR·캐시 동작을
유지하며 이 모듈의 import가 설정 읽기로부터 격리되었다고 가정하지 않는다.
"""
from __future__ import annotations

import json
import re
import urllib.parse

from ..config import RAW_DIR

def _strip_evidence(value):
    if isinstance(value, dict):
        return {
            k: _strip_evidence(v)
            for k, v in value.items()
            if k not in {"evidence_edges", "evidences", "origins"}
        }
    if isinstance(value, list):
        return [_strip_evidence(v) for v in value]
    return value


def _truncate(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def _edge_label(edge: dict) -> str:
    src = edge.get("source") or "?"
    rel = edge.get("relation") or "?"
    tgt = edge.get("target") or "?"
    return f"{src}-[{rel}]->{tgt}"


def _format_overview_evidence(view: str, record: dict) -> str | None:
    if view == "공급_허브":
        supplier = record.get("supplier")
        deg = record.get("deg")
        if supplier is None or deg is None:
            return None
        return f"공급_허브: {supplier} deg={deg}"
    if view == "경쟁_상위":
        company = record.get("company")
        deg = record.get("deg")
        if company is None or deg is None:
            return None
        return f"경쟁_상위: {company} deg={deg}"
    if view == "산업별_소속":
        industry = record.get("industry")
        n = record.get("n")
        sample = record.get("sample") or []
        if industry is None or n is None:
            return None
        sample_text = ", ".join(map(str, sample)) if isinstance(sample, list) else str(sample)
        return f"산업별_소속: {industry} n={n} sample={sample_text}"
    return None


def _collect_overview_evidence(row: dict) -> list[str]:
    """Render structural-overview aggregate rows as deterministic graph refs."""
    views = ("공급_허브", "경쟁_상위", "산업별_소속")
    if not any(view in row for view in views):
        return []

    records_by_view = {
        view: records
        for view in views
        if isinstance((records := row.get(view)), list)
    }
    refs: list[str] = []
    max_len = max((len(records) for records in records_by_view.values()), default=0)
    for idx in range(max_len):
        for view in views:
            records = records_by_view.get(view, [])
            if idx >= len(records) or not isinstance(records[idx], dict):
                continue
            body = _format_overview_evidence(view, records[idx])
            if body:
                refs.append(body)
    return refs


# --- Source deep links (click a citation -> jump to the exact sentence) -------
# Each filing's DART viewer URL serves the business-content prose directly in the
# page body, so a text-fragment directive (`#:~:text=`) makes the browser scroll
# to and highlight the quoted sentence — no manual Ctrl+F. #1's verbatim
# verification is what guarantees the quote matches the page so the fragment
# resolves (Chromium/Safari; Firefox/table quotes fall back to the section top).

_FILING_META: dict[str, dict] | None = None


def _load_filing_meta() -> dict[str, dict]:
    """{stock_code: {source_url, report_nm}} from each company's meta.json, cached.

    ``source_url``/``report_nm`` are per filing (one per company), so an edge's
    ``origins`` (stock codes) are enough to source it — no chunk match needed.
    """
    global _FILING_META
    if _FILING_META is None:
        meta: dict[str, dict] = {}
        for meta_path in RAW_DIR.glob("*/meta.json"):
            try:
                m = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            code = str(m.get("stock_code") or meta_path.parent.name)
            meta[code] = {
                "source_url": m.get("source_url", ""),
                "report_nm": m.get("report_nm", ""),
            }
        _FILING_META = meta
    return _FILING_META


_SOURCE_NORM: dict[str, str] = {}


def _source_text_norm(code: str) -> str:
    """Whitespace-normalized full filing text for a stock code, cached."""
    if code not in _SOURCE_NORM:
        path = RAW_DIR / code / "business_content.txt"
        _SOURCE_NORM[code] = (
            " ".join(path.read_text(encoding="utf-8").split()) if path.exists() else ""
        )
    return _SOURCE_NORM[code]


def _pick_origin(origins: list, quote: str | None) -> str | None:
    """Select a filing containing the whole ordered quote, never invent a fallback.

    Origins and quotes are unioned independently. Unmatched/short quotes cannot
    establish which origin owns them; no-quote structural provenance is unchanged.
    """
    if not quote:
        return str(origins[0]) if origins else None
    fragments = [" ".join(part.split()) for part in re.split(r"\.\.\.+|…", quote) if part.strip()]
    if not fragments or not any(len(fragment) >= 8 for fragment in fragments):
        return None
    for code in origins:
        try:
            source = _source_text_norm(str(code))
        except (OSError, UnicodeError):
            continue
        position = 0
        for fragment in fragments:
            index = source.find(fragment, position)
            if index < 0:
                break
            position = index + len(fragment)
        else:
            return str(code)
    return None


def _chunk_body(text: str) -> str:
    """Verbatim source prose of a chunk, dropping vectorize's ``[회사] 섹션`` header.

    ``vectorize`` prepends a synthetic ``[company] breadcrumb\\n`` line for context;
    that header is not in the DART page, so the deep link must target the body.
    """
    return str(text or "").split("\n", 1)[-1]


def _first_phrase(text: str, max_words: int = 12, max_chars: int = 80) -> str:
    """A short scroll target from the head of a longer chunk (one phrase)."""
    words = " ".join(str(text or "").split()).split()[:max_words]
    return " ".join(words)[:max_chars]


def _text_fragment(quote: str) -> str:
    """Build a `#:~:text=` directive that resolves to ``quote`` in the page.

    Ellipsis-joined quotes (``A ... B``) become a range ``text=A,B``. A long single
    sentence uses head/tail words as a range (shorter URL, still anchored). Every
    piece is fully percent-encoded so ``,``/``&``/``-`` can't clash with the syntax.
    """
    enc = lambda s: urllib.parse.quote(s, safe="")
    parts = [p.strip() for p in re.split(r"\.\.\.+|…", quote) if p.strip()]
    if len(parts) >= 2:
        return f"#:~:text={enc(parts[0])},{enc(parts[-1])}"
    q = (parts[0] if parts else quote).strip()
    words = q.split()
    if len(q) > 60 and len(words) >= 6:
        return f"#:~:text={enc(' '.join(words[:4]))},{enc(' '.join(words[-4:]))}"
    return f"#:~:text={enc(q)}"


def _deeplink(source_url: str, quote: str | None) -> str:
    """``source_url`` (+ text fragment when a quote is given). Empty if no url."""
    if not source_url:
        return ""
    if not quote:
        return source_url
    return source_url + _text_fragment(quote)


def _source_link(origins: list[str], quote: str | None) -> str:
    """Markdown link to the filing the quote came from, jumping to it if present."""
    code = _pick_origin(origins, quote)
    if code is None:
        return ""
    info = _load_filing_meta().get(code)
    if not info or not info.get("source_url"):
        return ""
    url = _deeplink(info["source_url"], quote)
    return f"[↗원문]({url})" if url else ""


def _collect_graph_evidence(rows: list[dict]) -> list[dict]:
    """Graph citation items: ``{display, quote, origins}`` (quote/origins optional).

    ``quote``/``origins`` let :func:`_format_citations` attach a source deep link;
    structural-overview refs (degree counts) carry neither and stay link-free.
    """
    seen: set[str] = set()
    refs: list[dict] = []

    def _add(display: str, quote: str | None = None, origins: list | None = None):
        if display not in seen:
            seen.add(display)
            refs.append({"display": display, "quote": quote, "origins": origins or []})

    for row in rows:
        if isinstance(row, dict):
            for body in _collect_overview_evidence(row):
                _add(body)
        for edge in row.get("evidence_edges") or []:
            if not isinstance(edge, dict):
                continue
            label = _edge_label(edge)
            evidences = [e for e in edge.get("evidences") or [] if e]
            origins = [o for o in edge.get("origins") or [] if o]
            if evidences:
                _add(f"{label}: \"{_truncate(evidences[0], 220)}\"", evidences[0], origins)
            elif origins:
                _add(f"{label}: origins={', '.join(map(str, origins))}", None, origins)
            else:
                _add(label)
    return refs


def _received_chunk_id(chunk: dict) -> str:
    """Return the existing vector locator only; not a verified/release identity.

    vectorize uses stock-index-truncatedhash. Do not invent IDs, coerce values,
    accept injected lines or attach an ID to a different explicit stock code.
    """
    value, stock = chunk.get("id"), chunk.get("stock_code")
    if not isinstance(value, str) or not isinstance(stock, str):
        return ""
    if re.fullmatch(r"[0-9]{6}-[0-9]{4,9}-[0-9a-f]{8}", value) is None:
        return ""
    return value if stock == value[:6] else ""


def _format_chunk_context(chunks: list[dict]) -> str:
    if not chunks:
        return "[]"
    compact = []
    for i, chunk in enumerate(chunks[:5], 1):
        compact.append({
            "ref": f"V{i}",
            "chunk_id": _received_chunk_id(chunk),
            "chunk_id_semantics": "received locator only; immutable release/version unconfirmed",
            "company": chunk.get("company"),
            "section": chunk.get("section"),
            "report_nm": chunk.get("report_nm"),
            "bsns_year": chunk.get("bsns_year"),
            "text": _truncate(chunk.get("text", ""), 900),
        })
    return json.dumps(compact, ensure_ascii=False, indent=2)


def _format_citations(rows: list[dict], chunks: list[dict]) -> str:
    lines: list[str] = []
    for i, ev in enumerate(_collect_graph_evidence(rows)[:8], 1):
        link = _source_link(ev["origins"], ev["quote"])
        suffix = f" {link}" if link else ""
        lines.append(f"[G{i}] {ev['display']}{suffix}")
    for i, chunk in enumerate(chunks[:5], 1):
        source = " · ".join(
            str(v) for v in [
                chunk.get("company"), chunk.get("section"),
                chunk.get("report_nm"), chunk.get("bsns_year"),
            ] if v
        )
        score = chunk.get("score")
        score_text = f", score={score:.3f}" if isinstance(score, float) else ""
        text = chunk.get("text", "")
        url = _deeplink(chunk.get("source_url", ""), _first_phrase(_chunk_body(text)))
        link = f" [↗원문]({url})" if url else ""
        lines.append(f"[V{i}] {source}{score_text}: \"{_truncate(text, 220)}\"{link}")
    return "\n".join(lines)


def _evidence_lines(rows: list[dict], chunks: list[dict]) -> list[str]:
    """Grounding material for the faithfulness gate — the same evidence shown in
    citations: each graph edge's display (relation + quote) and each chunk's
    verbatim body prose (minus vectorize's synthetic header)."""
    lines = [ev["display"] for ev in _collect_graph_evidence(rows)]
    for chunk in chunks[:5]:
        body = _truncate(_chunk_body(chunk.get("text", "")), 900)
        if body:
            lines.append(body)
    return lines
