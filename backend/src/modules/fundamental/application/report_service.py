"""fundamental report 저장/조회/삭제 오케스트레이션."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import delete,select,func,literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.common.agent_report import AgentReport
from db.models.common.stock import Stock
from db.models.fundamental.fundamental_report import FundamentalReport
from db.models.fundamental.report_evidence import ReportEvidence
from db.models.fundamental.report_filing_snippet import ReportFilingSnippet
from db.models.fundamental.report_insight import ReportInsight
from db.models.fundamental.report_interpretation import FundamentalReportInterpretation
from db.models.fundamental.report_ratio import ReportRatio
from db.models.fundamental.report_verification import FundamentalReportVerification
from src.shared.infrastructure.clients.ai_client import AIClient, AIContractError
from src.modules.reports.infrastructure import agent_report_repository as agent_repo
from src.modules.fundamental.infrastructure import report_repository as fr_repo
from src.modules.reports.api.report_schemas import AgentReportListItem
from src.modules.fundamental.domain.ai_output import FundamentalAgentOutputMirror
from src.modules.fundamental.api.schemas import FundamentalReportCreateRequest, FundamentalReportEnvelope, FundamentalReportListResponse, FundamentalReportSaveRequest


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return None


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _model_dict(obj: object, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: getattr(obj, field) for field in fields}


_REPORT_FIELDS = (
    "id",
    "request_id",
    "stock_code",
    "corp_code",
    "bsns_year",
    "years",
    "fs_div",
    "report_mode",
    "reprt_code",
    "reprt_name",
    "period_label",
    "verdict_label",
    "verdict",
    "fin_score",
    "confidence",
    "data_status",
    "risk_flags",
    "score_breakdown",
    "report_html",
    "llm_provider",
    "llm_model",
    "llm_latency_ms",
    "dart_calls",
    "trace_id",
    "as_of",
    "created_at",
    "meta",
)
_RATIO_FIELDS = (
    "id",
    "report_id",
    "ratio_name",
    "label",
    "category",
    "fiscal_year",
    "fiscal_period",
    "value",
    "unit",
    "display_value",
    "status",
    "reason",
    "formula",
    "basis",
)
_EVIDENCE_FIELDS = (
    "id",
    "report_id",
    "ratio_id",
    "metric",
    "claim",
    "rcept_no",
    "bsns_year",
    "fiscal_period",
    "sj_div",
    "account_id",
    "account_nm",
    "amount",
    "unit",
    "display_value",
    "source_url",
    "role",
    "raw",
)
_INTERPRETATION_FIELDS = (
    "id",
    "report_id",
    "interpretation",
    "interpretation_source",
    "provider",
    "model",
    "prompt_meta",
)
_VERIFICATION_FIELDS = (
    "id",
    "report_id",
    "binding_passed",
    "consistency_passed",
    "verdict_stable",
    "outcome",
    "regen_count",
    "evidence_count",
    "guard_violations",
    "flags",
)
_INSIGHT_FIELDS = ("id", "report_id", "insight_type", "source_endpoint", "rcept_no", "payload")
_SNIPPET_FIELDS = (
    "id",
    "report_id",
    "rcept_no",
    "section_name",
    "snippet",
    "rank",
    "source_hash",
    "verified",
    "meta",
)


from src.modules.auth.application.session_service import Principal, AuthenticationRequired, validate_principal
from src.modules.analysis.domain.contracts import AnalysisContractError
from src.modules.fundamental.domain.analysis import stored_response,validate_response,decode
from db.models.fundamental.analysis_run import FundamentalAnalysisRun

class FundamentalStoredPayloadError(ValueError):
    pass

class FundamentalReportIdConflict(FundamentalStoredPayloadError):
    pass


def _projection(raw,principal,question,stock_name,now):
    """Same projection for write/read comparison; original JSON stays in the ledger."""
    ticker=raw['ticker'];erd_payload=raw['meta']['erd_payload'];root=erd_payload['fundamental_report']
    report_id=_uuid(root['id']);report_as_of=_parse_dt(root.get('as_of'))
    request_id=raw['request_id'];trace_id=raw['meta']['trace_id']
    report = FundamentalReport(
        id=report_id,
        owner_user_id=principal.user_id,
        request_id=root.get("request_id"),
        stock_code=root.get("stock_code"),
        corp_code=root.get("corp_code"),
        bsns_year=root.get("bsns_year"),
        years=root.get("years"),
        fs_div=root.get("fs_div"),
        report_mode=root.get("report_mode"),
        reprt_code=root.get("reprt_code"),
        reprt_name=root.get("reprt_name"),
        period_label=root.get("period_label"),
        verdict_label=root.get("verdict_label"),
        verdict=root.get("verdict"),
        fin_score=root.get("fin_score"),
        confidence=root.get("confidence"),
        data_status=root.get("data_status"),
        risk_flags=root.get("risk_flags"),
        score_breakdown=root.get("score_breakdown"),
        report_html=root.get("report_html"),
        llm_provider=root.get("llm_provider"),
        llm_model=root.get("llm_model"),
        llm_latency_ms=root.get("llm_latency_ms"),
        dart_calls=root.get("dart_calls"),
        trace_id=root.get("trace_id"),
        as_of=report_as_of,
        created_at=now,
        meta=root.get("meta"),
    )
    ratios = [
        ReportRatio(
            id=_uuid(item["id"]),
            report_id=_uuid(item["report_id"]),
            ratio_name=item.get("ratio_name"),
            label=item.get("label"),
            category=item.get("category"),
            fiscal_year=item.get("fiscal_year"),
            fiscal_period=item.get("fiscal_period"),
            value=_decimal(item.get("value")),
            unit=item.get("unit"),
            display_value=item.get("display_value"),
            status=item.get("status"),
            reason=item.get("reason"),
            formula=item.get("formula"),
            basis=item.get("basis"),
        )
        for item in erd_payload.get("report_ratios",[])
    ]
    evidence = [
        ReportEvidence(
            id=_uuid(item["id"]),
            report_id=_uuid(item["report_id"]),
            ratio_id=_uuid(item["ratio_id"]) if item.get("ratio_id") else None,
            metric=item.get("metric"),
            claim=item.get("claim"),
            rcept_no=item.get("rcept_no"),
            bsns_year=item.get("bsns_year"),
            fiscal_period=item.get("fiscal_period"),
            sj_div=item.get("sj_div"),
            account_id=item.get("account_id"),
            account_nm=item.get("account_nm"),
            amount=_decimal(item.get("amount")),
            unit=item.get("unit"),
            display_value=item.get("display_value"),
            source_url=item.get("source_url"),
            role=item.get("role"),
            raw=item.get("raw"),
        )
        for item in erd_payload.get("report_evidence",[])
    ]
    interp_payload = erd_payload["report_interpretation"]
    interpretation = FundamentalReportInterpretation(
        id=_uuid(interp_payload["id"]),
        report_id=_uuid(interp_payload["report_id"]),
        interpretation=interp_payload.get("interpretation"),
        interpretation_source=interp_payload.get("interpretation_source"),
        provider=interp_payload.get("provider"),
        model=interp_payload.get("model"),
        prompt_meta=interp_payload.get("prompt_meta"),
    )
    verification_payload = erd_payload["report_verification"]
    verification = FundamentalReportVerification(
        id=_uuid(verification_payload["id"]),
        report_id=_uuid(verification_payload["report_id"]),
        binding_passed=verification_payload.get("binding_passed"),
        consistency_passed=verification_payload.get("consistency_passed"),
        verdict_stable=verification_payload.get("verdict_stable"),
        outcome=verification_payload.get("outcome"),
        regen_count=verification_payload.get("regen_count"),
        evidence_count=verification_payload.get("evidence_count"),
        guard_violations=verification_payload.get("guard_violations"),
        flags=verification_payload.get("flags"),
    )
    insights = [
        ReportInsight(
            id=_uuid(item["id"]),
            report_id=_uuid(item["report_id"]),
            insight_type=item.get("insight_type"),
            source_endpoint=item.get("source_endpoint"),
            rcept_no=item.get("rcept_no"),
            payload=item.get("payload"),
        )
        for item in erd_payload.get("report_insights",[])
    ]
    snippets = [
        ReportFilingSnippet(
            id=_uuid(item["id"]),
            report_id=_uuid(item["report_id"]),
            rcept_no=item.get("rcept_no"),
            section_name=item.get("section_name"),
            snippet=item.get("snippet"),
            rank=item.get("rank"),
            source_hash=item.get("source_hash"),
            verified=item.get("verified"),
            meta=item.get("meta"),
        )
        for item in erd_payload.get("report_filing_snippets",[])
    ]

    agent_report = AgentReport(
        id=uuid4(),
        agent_type="fundamental",
        agent_report_id=report_id,
        request_id=request_id,
        client_session_id=None,
        owner_user_id=principal.user_id,
        owner_session_id=principal.session_id,
        stock_code=ticker,
        stock_name=stock_name,
        question=question,
        answer_text=raw['verdict'],
        data_status=root.get("data_status"),
        trace_id=trace_id,
        as_of=report_as_of,
        created_at=now,
        summary={
            "fin_score": raw['score'],
            "verdict_label": raw['verdict_label'],
            "period_label": root.get("period_label"),
        },
    )

    return report,ratios,evidence,interpretation,verification,insights,snippets,agent_report

class FundamentalReportService:
    def __init__(self,session,*,principal=None):
        self._session,self._principal=session,principal

    async def _authorize(self,lock=False):
        if not isinstance(self._principal,Principal):raise AuthenticationRequired()
        await validate_principal(self._session,self._principal,lock=lock)
        return self._principal

    async def create_report(self,*args,**kwargs):raise PermissionError('Public creation is disabled')
    async def save_report(self,*args,**kwargs):raise PermissionError('Public save is disabled')
    async def _persist(self,*args,**kwargs):raise PermissionError('Legacy persistence is disabled')
    async def delete_all_reports(self):raise PermissionError('Public bulk deletion is disabled')

    async def stage_report(self,raw,*,report_id,question,stock_name):
        principal=await self._authorize(lock=True)
        # The production adapter has already bound and validated this exact snapshot.
        # Stage also verifies its correlation/ERD before any write.
        from src.modules.fundamental.domain.analysis import validate_output
        rid,raw=validate_output(raw,dict(request_id=raw.get('request_id'),trace_id=raw.get('meta',{}).get('trace_id'),ticker=raw.get('ticker')))
        if rid!=report_id:raise AnalysisContractError()
        existing=await self._session.scalar(select(FundamentalReport).where(FundamentalReport.id==rid).with_for_update())
        if existing is not None or await fr_repo.get_agent_indexes(self._session,rid):raise FundamentalReportIdConflict('Result ID already claimed')
        stock=await self._session.get(Stock,raw['ticker'])
        if stock is None or type(stock_name) is not str or not stock_name.strip():raise AnalysisContractError()
        now=await self._session.scalar(select(func.clock_timestamp()))
        root,ratios,evidence,interp,verif,insights,snippets,index=_projection(raw,principal,question,stock_name,now)
        await fr_repo.add_report(self._session,report=root,ratios=ratios,evidence=evidence,interpretation=interp,verification=verif,insights=insights,filing_snippets=snippets)
        await agent_repo.add(self._session,index)
        await self._session.flush()
        return FundamentalReportEnvelope(report_id=rid,report=raw)

    async def get_report(self,report_id):
        principal=await self._authorize()
        root=await fr_repo.get_owned_report(self._session,report_id,owner_user_id=principal.user_id)
        if root is None:return None
        row=await self._session.scalar(select(FundamentalAnalysisRun).where(FundamentalAnalysisRun.adopted_report_id==report_id,FundamentalAnalysisRun.state=='stored',FundamentalAnalysisRun.owner_user_id==principal.user_id))
        if row is None:raise FundamentalStoredPayloadError('Stored association missing')
        try:
            _,_,result=validate_response(row,stored_response(row));raw=decode(result)
            indexes=await fr_repo.get_agent_indexes(self._session,report_id)
            if len(indexes)!=1 or indexes[0].owner_user_id!=principal.user_id:raise ValueError()
            # Preserve admission session in the index; a new valid session can read.
            index=indexes[0]
            if index.owner_session_id is None:raise ValueError()
            from types import SimpleNamespace
            expected=_projection(raw,SimpleNamespace(user_id=principal.user_id,session_id=index.owner_session_id),decode(row.request_json)['question'],row.stock_name,root.created_at)
            actual=(root,await fr_repo.list_ratios(self._session,report_id),await fr_repo.list_evidence(self._session,report_id),await fr_repo.get_interpretation(self._session,report_id),await fr_repo.get_verification(self._session,report_id),await fr_repo.list_insights(self._session,report_id),await fr_repo.list_filing_snippets(self._session,report_id),index)
            for got,want in zip(actual,expected):
                if isinstance(want,list):
                    got_by_id={item.id:item for item in got}
                    if len(got_by_id)!=len(want):raise ValueError()
                    for item in want:self._check_projection(got_by_id.get(item.id),item)
                else:self._check_projection(got,want)
            return FundamentalReportEnvelope(report_id=report_id,report=raw)
        except (ValueError,TypeError,KeyError,AttributeError) as error:
            raise FundamentalStoredPayloadError('Stored result is inconsistent') from None

    @staticmethod
    def _check_projection(actual,expected):
        if actual is None:raise ValueError()
        for column in expected.__table__.columns:
            key=column.key
            # Index UUID and persisted creation time are generated once, not part of AI JSON.
            if isinstance(expected,AgentReport) and key in {'id','created_at'}:continue
            a,b=getattr(actual,key),getattr(expected,key)
            if isinstance(a,Decimal) or isinstance(b,Decimal):
                if a is None or b is None or Decimal(str(a))!=Decimal(str(b)):raise ValueError()
            elif isinstance(a,datetime) and isinstance(b,datetime):
                if a!=b:raise ValueError()
            elif a!=b:raise ValueError()

    async def list_reports(self,*,stock_code=None,limit=20,offset=0):
        principal=await self._authorize()
        rows=await fr_repo.list_owned_indexes(self._session,owner_user_id=principal.user_id,stock_code=stock_code,limit=limit,offset=offset)
        for row in rows:
            if await self.get_report(row.agent_report_id) is None:raise FundamentalStoredPayloadError('Stored result missing')
        total=await fr_repo.list_owned_indexes(self._session,owner_user_id=principal.user_id,stock_code=stock_code,count=True)
        return FundamentalReportListResponse(items=[AgentReportListItem.model_validate(row) for row in rows],limit=limit,offset=offset,count=total)

    async def delete_report(self,report_id):
        try:return await self._delete_report(report_id)
        except Exception:
            await self._session.rollback();raise

    async def _delete_report(self,report_id):
        principal=await self._authorize(lock=True)
        discovered=(await self._session.execute(select(FundamentalReport.id,literal_column('fundamental_reports.xmin::text'),FundamentalAnalysisRun.id)
            .join(FundamentalAnalysisRun,(FundamentalAnalysisRun.adopted_report_id==FundamentalReport.id)&(FundamentalAnalysisRun.state=='stored')&(FundamentalAnalysisRun.owner_user_id==principal.user_id))
            .where(FundamentalReport.id==report_id,FundamentalReport.id.in_(fr_repo.eligible_ids(principal.user_id))))).one_or_none()
        if discovered is None:return False
        row=await self._session.scalar(select(FundamentalAnalysisRun).where(FundamentalAnalysisRun.id==discovered[2],FundamentalAnalysisRun.owner_user_id==principal.user_id).with_for_update().execution_options(populate_existing=True))
        if row is None or row.state!='stored' or row.adopted_report_id!=report_id:return False
        version=await self._session.scalar(select(literal_column('fundamental_reports.xmin::text')).select_from(FundamentalReport).where(FundamentalReport.id==report_id).with_for_update(of=FundamentalReport))
        if version!=discovered[1]:return False
        if await self.get_report(report_id) is None:return False
        row.state='deleted';row.deleted_at=await self._session.scalar(select(func.clock_timestamp()))
        row.request_json=row.stock_name=row.input_json=row.result_json=None
        await self._session.flush()
        await fr_repo.delete_agent_index(self._session,report_id)
        deleted=await fr_repo.delete_root(self._session,report_id)
        await self._session.commit()
        return deleted>0
