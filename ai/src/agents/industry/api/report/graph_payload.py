"""Pure graph/evidence projection for research-report.v1; no graph execution."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


MAX_TAGS = 8


RELATION_TARGET_TYPES = {
    "BELONGS_TO": "Industry",
    "BENEFITS_FROM": "Policy",
}


KIND_BY_TYPE = {
    "Company": "customer",
    "Industry": "industry",
    "Policy": "policy",
    "Aggregate": "aggregate",
    "Product": "aggregate",
    "Person": "aggregate",
}


def _slug(text: Any) -> str:
    value = str(text or "unknown").strip().lower()
    out: list[str] = []
    prev_dash = False
    for char in value:
        if char.isalnum():
            out.append(char)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    slug = "".join(out).strip("-")
    return slug or "unknown"


def _node_id(label: str, node_type: str) -> str:
    return f"{node_type.lower()}:{_slug(label)}"


def _edge_source_metadata(origins: list[Any], quote: str | None) -> tuple[str, str, str]:
    """Best-effort source name and URL for graph evidence.

    The provenance utilities live in ``retrieve.py`` because answer generation
    already needs them. Import lazily so pure tests can use this module without
    loading filing metadata unless graph evidence actually asks for it.
    """
    try:
        from ...application.retrieval import _deeplink, _load_filing_meta, _pick_origin

        code = _pick_origin(origins, quote)
        if code is None:
            return "", "", ""
        info = _load_filing_meta().get(str(code), {})
        source_url = info.get("source_url") or ""
        report_nm = info.get("report_nm") or ""
        return report_nm, _deeplink(source_url, quote) if source_url else "", code
    except Exception:
        return "", "", ""


def _edge_display_source_url(origins: list[Any], quote: str | None) -> tuple[str, str]:
    """Compatibility view of the same selected source; code is available internally."""
    name, url, _code = _edge_source_metadata(origins, quote)
    return name, url


def _iter_evidence_edges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for edge in row.get("evidence_edges") or []:
            if isinstance(edge, dict):
                edges.append(edge)
    return edges


def _iter_overview_edges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert structural-overview aggregate rows into report graph edges."""
    edges: list[dict[str, Any]] = []

    def representative(record: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        for edge in record.get("evidence_edges") or []:
            if isinstance(edge, dict) and (edge.get("evidences") or edge.get("origins")):
                return {
                    **fallback,
                    "evidences": edge.get("evidences") or fallback.get("evidences") or [],
                    "origins": edge.get("origins") or fallback.get("origins") or [],
                }
        return fallback

    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for record in row.get("공급_허브") or []:
            if not isinstance(record, dict) or not record.get("supplier"):
                continue
            supplier = str(record["supplier"])
            deg = record.get("deg", 0)
            edges.append(representative(record, {
                "source": supplier,
                "relation": "SUPPLY_HUB",
                "target": "공급 허브",
                "evidences": [f"{supplier}는 {deg}개 기업과 공급 관계를 가진 공급 허브입니다."],
                "origins": [],
            }))
        for record in row.get("경쟁_상위") or []:
            if not isinstance(record, dict) or not record.get("company"):
                continue
            company = str(record["company"])
            deg = record.get("deg", 0)
            edges.append(representative(record, {
                "source": company,
                "relation": "COMPETITION_HUB",
                "target": "경쟁 중심",
                "evidences": [f"{company}는 {deg}개 경쟁 연결을 가진 경쟁 중심 기업입니다."],
                "origins": [],
            }))
        for record in row.get("산업별_소속") or []:
            if not isinstance(record, dict) or not record.get("industry"):
                continue
            industry = str(record["industry"])
            sample = [str(item) for item in record.get("sample") or [] if item]
            n = record.get("n", len(sample))
            evidence_by_source = {
                str(edge.get("source")): edge
                for edge in record.get("evidence_edges") or []
                if isinstance(edge, dict) and edge.get("source")
            }
            for company in sample[:6]:
                edges.append(representative(evidence_by_source.get(company, {}), {
                    "source": company,
                    "relation": "BELONGS_TO",
                    "target": industry,
                    "evidences": [f"{industry}에는 {n}개 기업이 속하며, 표본 기업에 {company}가 포함됩니다."],
                    "origins": [],
                }))
    return edges


def _infer_node_type(name: str, relation: str, *, is_target: bool) -> str:
    if relation in {"SUPPLY_HUB", "COMPETITION_HUB"} and is_target:
        return "Aggregate"
    if is_target:
        return RELATION_TARGET_TYPES.get(relation, "Company")
    return "Company"


def _node_kind(node_type: str, depth: int | None = None) -> str:
    if node_type == "Company":
        if depth == 0:
            return "upstream"
        if depth == 1:
            return "midstream"
        if depth is not None and depth >= 3:
            return "downstream"
    return KIND_BY_TYPE.get(node_type, "aggregate")


def build_graph_and_evidence(
    rows: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build report graph nodes/edges and evidence from agent rows/chunks."""
    node_types: dict[str, str] = {}
    edge_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    evidence: list[dict[str, Any]] = []

    graph_edges = _iter_evidence_edges(rows) + _iter_overview_edges(rows)
    for raw_edge in graph_edges:
        source = str(raw_edge.get("source") or "?")
        target = str(raw_edge.get("target") or "?")
        relation = str(raw_edge.get("relation") or "RELATED_TO")
        source_type = _infer_node_type(source, relation, is_target=False)
        target_type = _infer_node_type(target, relation, is_target=True)
        source_id = _node_id(source, source_type)
        target_id = _node_id(target, target_type)
        node_types.setdefault(source_id, source_type)
        node_types.setdefault(target_id, target_type)

        key = (source_id, relation, target_id)
        if key not in edge_map:
            edge_id = f"edge:g{len(edge_map) + 1}"
            edge_map[key] = {
                "id": edge_id,
                "source": source_id,
                "target": target_id,
                "relation": relation,
                "label": _relation_label(relation),
                "style": "solid",
                "evidenceIds": [],
                "_sourceLabel": source,
                "_targetLabel": target,
            }
        edge = edge_map[key]
        quote = _first(raw_edge.get("evidences"))
        origins = [o for o in raw_edge.get("origins") or [] if o]
        source_name, source_url, source_code = _edge_source_metadata(origins, quote)
        ref = f"G{len([ev for ev in evidence if ev['kind'] == 'graph']) + 1}"
        evidence_id = f"ev:{ref}"
        edge["evidenceIds"].append(evidence_id)
        evidence.append({
            "id": evidence_id,
            "ref": ref,
            "kind": "graph",
            "edgeId": edge["id"],
            "relation": relation,
            "title": f"{source} -> {target}",
            "quote": quote or "",
            "source": {
                # The report renders name and reportName side by side, so only name the
                # source when the filing itself is unidentified.
                "name": "" if source_name else ("DART filing" if origins else "Neo4j aggregate result"),
                "publisher": "DART" if origins else "",
                "reportName": source_name,
                "stockCode": source_code,
                "url": source_url,
                "textFragmentUrl": source_url,
            },
        })

    for idx, chunk in enumerate(chunks or [], 1):
        ref = f"V{idx}"
        evidence.append({
            "id": f"ev:{ref}",
            "ref": ref,
            "kind": "vector",
            "edgeId": "",
            "relation": "",
            "title": _chunk_title(chunk),
            "quote": str(chunk.get("text") or ""),
            "score": chunk.get("score"),
            "source": {
                "name": str(chunk.get("company") or ""),
                "publisher": "DART" if chunk.get("source_url") else "",
                "reportName": str(chunk.get("report_nm") or ""),
                "stockCode": str(chunk.get("stock_code") or ""),
                "section": str(chunk.get("section") or ""),
                "bsnsYear": str(chunk.get("bsns_year") or ""),
                "url": str(chunk.get("source_url") or ""),
                "textFragmentUrl": str(chunk.get("source_url") or ""),
            },
        })

    edges = [{k: v for k, v in edge.items() if not k.startswith("_")} for edge in edge_map.values()]
    labels = _node_labels_from_edges(edge_map.values())
    depths = _node_depths(edges)
    positions = _layout_positions(list(node_types), depths)
    nodes = [
        {
            "id": node_id,
            "label": labels.get(node_id, node_id.split(":", 1)[-1]),
            "type": node_type,
            "role": _node_role(node_type, depths.get(node_id)),
            "kind": _node_kind(node_type, depths.get(node_id)),
            "position": positions[node_id],
        }
        for node_id, node_type in node_types.items()
    ]
    return nodes, edges, evidence


def _first(values: Any) -> str:
    if isinstance(values, list):
        return str(values[0]) if values else ""
    return str(values or "")


def _relation_label(relation: str) -> str:
    return {
        "SUPPLIES": "공급",
        "COMPETES_WITH": "경쟁",
        "OWNS_STAKE": "지분",
        "BELONGS_TO": "소속",
        "BENEFITS_FROM": "정책 수혜",
        "SUPPLY_HUB": "공급 허브",
        "COMPETITION_HUB": "경쟁 중심",
    }.get(relation, relation)


def _chunk_title(chunk: dict[str, Any]) -> str:
    parts = [chunk.get("company"), chunk.get("section"), chunk.get("report_nm")]
    return " · ".join(str(part) for part in parts if part) or "Vector evidence"


def _node_labels_from_edges(edges: Any) -> dict[str, str]:
    labels: dict[str, str] = {}
    for edge in edges:
        labels[edge["source"]] = edge.get("_sourceLabel", edge["source"])
        labels[edge["target"]] = edge.get("_targetLabel", edge["target"])
    return labels


def _node_depths(edges: list[dict[str, Any]]) -> dict[str, int]:
    node_ids = {edge["source"] for edge in edges} | {edge["target"] for edge in edges}
    if not node_ids:
        return {}

    incoming = defaultdict(int)
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        outgoing[edge["source"]].append(edge["target"])
        incoming[edge["target"]] += 1
        incoming.setdefault(edge["source"], incoming.get(edge["source"], 0))

    roots = sorted(node for node in node_ids if incoming[node] == 0) or sorted(node_ids)
    depths = {root: 0 for root in roots}
    queue = deque(roots)
    while queue:
        node = queue.popleft()
        for target in outgoing.get(node, []):
            next_depth = depths[node] + 1
            if target not in depths or next_depth < depths[target]:
                depths[target] = next_depth
                queue.append(target)

    for node in sorted(node_ids):
        depths.setdefault(node, 0)
    return depths


def _layout_positions(node_ids: list[str], depths: dict[str, int]) -> dict[str, dict[str, int]]:
    if not node_ids:
        return {}
    by_depth: dict[int, list[str]] = defaultdict(list)
    for node_id in node_ids:
        by_depth[depths.get(node_id, 0)].append(node_id)
    max_depth = max(by_depth) if by_depth else 0
    x_min, x_max = 115, 805
    x_step = (x_max - x_min) / max(max_depth, 1)
    positions: dict[str, dict[str, int]] = {}
    for depth, ids in sorted(by_depth.items()):
        ids.sort()
        spacing = 420 / (len(ids) + 1)
        for index, node_id in enumerate(ids, 1):
            positions[node_id] = {
                "x": round(x_min + depth * x_step),
                "y": round(70 + index * spacing),
            }
    return positions


def _node_role(node_type: str, depth: int | None) -> str:
    if node_type == "Policy":
        return "정책"
    if node_type == "Industry":
        return "산업"
    if node_type == "Aggregate":
        return "집계"
    if depth == 0:
        return "출발 노드"
    if depth == 1:
        return "1차 연결"
    if depth is not None and depth >= 2:
        return f"{depth}홉 연결"
    return node_type


def _extract_tags(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    by_id = {node["id"]: node for node in nodes}
    ordered_ids: list[str] = []
    for edge in edges:
        for node_id in (edge["source"], edge["target"]):
            if node_id not in ordered_ids:
                ordered_ids.append(node_id)
    if not ordered_ids:
        ordered_ids = [node["id"] for node in nodes]
    return [by_id[node_id]["label"] for node_id in ordered_ids[:MAX_TAGS] if node_id in by_id]
