"""One existing vector-search call with conservative known-company source scope."""
from __future__ import annotations

from ..domain.companies import COMPANIES
from ..domain.company_scope import (
    MAX_VECTOR_RESULTS, SURFACE_PRIORITY as _SURFACE_PRIORITY,
    plan_company_scope, retain_company_chunks,
)
from ..infrastructure.entity_normalization import normalize_lookup_key
from ..infrastructure.graph.vector_retrieve import vector_search


def _build_company_surfaces() -> list[tuple[str, str, str]]:
    surfaces = []
    for company in COMPANIES:
        surfaces.append((normalize_lookup_key(company.canonical), company.canonical, "canonical"))
        surfaces.extend((normalize_lookup_key(alias), company.canonical, "alias") for alias in company.aliases)
        if company.stock_code:
            surfaces.append((normalize_lookup_key(company.stock_code), company.canonical, "stock_code"))
    return surfaces


_COMPANY_SURFACES = _build_company_surfaces()


def _mentioned_company(question: str) -> str | None:
    plan = plan_company_scope(question, _COMPANY_SURFACES)
    return plan.companies[0] if len(plan.companies) == 1 and plan.reason != "ambiguous" else None


def requires_company_scope(question: str) -> bool:
    plan = plan_company_scope(question, _COMPANY_SURFACES)
    return plan.reason == "ambiguous" or len(plan.companies) == 2


def retrieve_company_chunks(state: dict, *, graph) -> dict:
    plan = plan_company_scope(state["question"], _COMPANY_SURFACES)
    if plan.reason == "ambiguous":
        return {"chunks": [], "company_scope": plan, "error": state.get("error", "")}
    company = plan.companies[0] if len(plan.companies) == 1 else None
    chunks = vector_search(state["question"], k=MAX_VECTOR_RESULTS, company=company, graph=graph)
    chunks, scope = retain_company_chunks(plan, chunks, _COMPANY_SURFACES, normalize_lookup_key)
    return {"chunks": chunks, "company_scope": scope, "error": state.get("error", "")}
