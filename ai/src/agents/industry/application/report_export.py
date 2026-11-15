"""Export one live agent answer as the research-report.v1 JSON payload.

The report template in ``make_report/`` consumes a report-shaped JSON
object, while the LangGraph agent returns its natural execution state
(``question``, ``label``, ``cypher``, ``rows``, ``chunks``, ``answer``). This
module bridges those two shapes without changing the answer pipeline.

Run:
    uv run python -m src.agents.industry.application.report_export "에코프로에서 시작된 원료 공급 경로는?"
    uv run python -m src.agents.industry.application.report_export "..." --out data/reports/latest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent import build_agent
from ..domain.answer_verification import bound_verification
from ..config import get_neo4j_graph
from ..api.report.render import TEMPLATE_PATH, render_report_html
from ..api.report.pipeline import _pipeline_steps
from ..api.report.graph_payload import MAX_TAGS, _extract_tags, _slug, build_graph_and_evidence

SCHEMA_VERSION = "research-report.v1"
LOCALE = "ko-KR"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_answer(answer: str) -> dict[str, Any]:
    """Split the current rendered answer into body, faithfulness, and citations."""
    text = (answer or "").strip()
    citation_text = ""
    body_part = text
    if "\n근거\n" in body_part:
        body_part, citation_text = body_part.split("\n근거\n", 1)
    elif "\n\n근거\n" in body_part:
        body_part, citation_text = body_part.split("\n\n근거\n", 1)

    unsupported: list[dict[str, str]] = []
    unsupported_re = re.compile(
        r"(?:^|\n)⚠️ 검증되지 않은 진술 \d+건:\n(?P<items>(?:- .*(?:\n|$))+)",
        re.MULTILINE,
    )
    match = unsupported_re.search(body_part)
    if match:
        for line in match.group("items").splitlines():
            raw = line.removeprefix("- ").strip()
            if raw:
                unsupported.append({
                    "sentence": raw.strip('"'),
                    "reason": "The faithfulness gate marked this claim as unsupported.",
                })
        body_part = unsupported_re.sub("", body_part).strip()

    body = re.sub(r"\n{3,}", "\n\n", body_part).strip()
    headline = _headline_from_body(body)
    # 인용은 출처일 뿐 검증 실행/성공 증거가 아니다. 현재 answer 문자열은 checked를 보존하지 않는다.
    status = "warning" if unsupported else "unchecked"
    label = {
        "verified": "근거 검증 완료",
        "warning": "일부 진술 검증 경고 포함",
        "unchecked": "근거 검증 정보 없음",
    }[status]

    return {
        "headline": headline,
        "body": body,
        "faithfulness": {
            "status": status,
            "label": label,
            "unsupportedClaims": unsupported,
        },
        "citationText": citation_text.strip(),
    }


def _headline_from_body(body: str, limit: int = 140) -> str:
    first_para = next((part.strip() for part in body.split("\n\n") if part.strip()), "")
    sentence_match = re.search(r"^(.+?[.!?。…]|.+?다\.)", first_para)
    headline = sentence_match.group(1).strip() if sentence_match else first_para
    headline = re.sub(r"^\d+\.\s*", "", headline)
    return headline if len(headline) <= limit else headline[:limit].rstrip() + "..."


def _retrieval_flow(final_state: dict[str, Any]) -> str:
    parts = ["LangGraph classify"]
    if final_state.get("cypher"):
        parts.extend(["Cypher", "Neo4j rows"])
    if final_state.get("chunks"):
        parts.append("vector chunks")
    parts.extend(["grounded answer", "faithfulness gate"])
    return " -> ".join(parts)


def _graph_snapshot(graph) -> dict[str, dict[str, int]]:
    """Return live graph counts. Fails soft so export still works in tests."""
    try:
        node_rows = graph.query(
            "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count ORDER BY label"
        )
        rel_rows = graph.query(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY type"
        )
    except Exception:
        return {"nodes": {}, "relationships": {}}
    return {
        "nodes": {str(row["label"]): int(row["count"]) for row in node_rows},
        "relationships": {str(row["type"]): int(row["count"]) for row in rel_rows},
    }


def build_report_payload(
    final_state: dict[str, Any],
    *,
    graph_snapshot: dict[str, Any] | None = None,
    created_at: str | None = None,
    report_id: str | None = None,
) -> dict[str, Any]:
    """Build a research-report.v1 payload from one final agent state."""
    rows = final_state.get("rows") or []
    chunks = final_state.get("chunks") or []
    parsed_answer = parse_answer(final_state.get("answer") or "")
    verification = bound_verification(final_state)
    if verification and verification.outcome == "checked":
        # 기존 문자열 경고를 지우지 않는다. 동일 실행 기록만 positive 상태를 복원한다.
        faith = parsed_answer["faithfulness"]
        if verification.unsupported:
            faith.update(status="warning", label="일부 진술 검증 경고 포함",
                         unsupportedClaims=[{"sentence": sentence,
                             "reason": "The faithfulness gate marked this claim as unsupported."}
                             for sentence in verification.unsupported])
        elif faith["status"] != "warning":
            faith.update(status="verified", label="문장 근거 검사 통과")
    nodes, edges, evidence = build_graph_and_evidence(rows, chunks)
    tags = _extract_tags(nodes, edges)
    if not tags:
        tags = parsed_answer["body"].split()[:MAX_TAGS]

    created = created_at or _now_iso()
    question = final_state.get("question") or ""
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "reportId": report_id or f"rpt_{created[:10].replace('-', '')}_{_slug(question)[:48]}",
        "createdAt": created,
        "locale": LOCALE,
        "question": {
            "text": question,
            "type": final_state.get("label") or "unknown",
            "label": _question_label(final_state.get("label")),
        },
        "answer": {
            "headline": parsed_answer["headline"],
            "body": parsed_answer["body"],
            "tags": tags,
            "faithfulness": parsed_answer["faithfulness"],
        },
        "metrics": {
            "rows": len(rows),
            "attempts": final_state.get("attempts") or 0,
            "graphEdges": len(edges),
            "graphNodes": len(nodes),
            "citations": len(evidence),
        },
        "graph": {
            "nodes": nodes,
            "edges": edges,
        },
        "evidence": evidence,
        "execution": {
            "pipeline": _pipeline_steps(final_state),
            "cypher": final_state.get("cypher") or "",
            "retrievalFlow": _retrieval_flow(final_state),
        },
        "graphSnapshot": graph_snapshot or {"nodes": {}, "relationships": {}},
    }
    return payload


def _question_label(label: str | None) -> str:
    return {
        "relational": "Relational graph question",
        "qualitative": "Qualitative synthesis",
        "global": "Global structure summary",
        "factual": "Factual lookup",
    }.get(label or "", label or "Unknown")


def export_question(question: str, *, graph=None, report_id: str | None = None) -> dict[str, Any]:
    """Run the live agent for ``question`` and return a report payload."""
    owns_graph = graph is None
    graph = graph or get_neo4j_graph()
    try:
        final_state = build_agent(graph).invoke({"question": question})
        snapshot = _graph_snapshot(graph)
        return build_report_payload(final_state, graph_snapshot=snapshot, report_id=report_id)
    finally:
        if owns_graph:
            graph.close()


def _write_stdout(text: str) -> None:
    """Write UTF-8 reliably on Windows consoles whose default encoding is cp949."""
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one GraphRAG question and export research-report.v1 JSON."
    )
    parser.add_argument("question", help="Natural-language question to run through the agent")
    parser.add_argument("--out", type=Path, help="Output JSON path. Prints to stdout when omitted.")
    parser.add_argument("--html-out", type=Path, help="Output standalone HTML report path.")
    parser.add_argument(
        "--template",
        type=Path,
        default=TEMPLATE_PATH,
        help="Report HTML template path.",
    )
    args = parser.parse_args()

    payload = export_question(args.question)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    if args.html_out:
        args.html_out.parent.mkdir(parents=True, exist_ok=True)
        args.html_out.write_text(render_report_html(payload, args.template), encoding="utf-8")
    if not args.out and not args.html_out:
        _write_stdout(text + "\n")


if __name__ == "__main__":
    main()
