"""Synthetic contract tests. No database, principal verification, or external AI."""

from __future__ import annotations

import copy
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from src.modules.flow.domain.execution import CommonResponse, ContractViolation, DataObservation, ErrorCode, ExecutionContext, FlowRunRequest, FlowRunState, IdempotencyReference, SafeError, bind_flow_result, validate_result_binding
from src.modules.flow.domain.payload import FlowPayloadV1, validate_flow_payload
from src.modules.flow.api.schemas import FlowReportSaveRequest
from src.modules.flow.application import report_service as service_module
from src.modules.flow.application.report_service import (
    PAYLOAD_SNAPSHOT_KEY,
    STORAGE_FORMAT_KEY,
    FlowPayloadError,
    FlowReportService,
    FlowStoredPayloadError,
)
from tests.fixtures.flow_payload import make_flow_payload


CANONICAL_RELOCATED_EXPORTS = {'src.agents.flow.api.payload': ['PAYLOAD_VERSION', 'derive_data_status', 'build_payload', 'to_json'], 'agents.flow.api.payload': ['PAYLOAD_VERSION', 'derive_data_status', 'build_payload', 'to_json'], 'src.agents.flow.domain.models': ['AgentInput', 'GateResult', 'SupplyDemandState', 'AgentOutput'], 'agents.flow.domain.models': ['AgentInput', 'GateResult', 'SupplyDemandState', 'AgentOutput'], 'src.shared.http.access_boundary': ['PUBLIC_ROUTES', 'AccessBoundary'], 'src.modules.auth.infrastructure.google_oidc': ['ISSUER', 'DISCOVERY', 'ENDPOINTS', 'LoginFailed', 'GoogleConfig', 'Attempt', 'Attempts', 'GoogleOIDC'], 'src.shared.infrastructure.clients.ai_client': ['_ANALYZE_PATH', '_FUNDAMENTAL_ANALYZE_PATH', '_INDUSTRY_ANALYZE_PATH', '_INDUSTRY_RENDER_PATH', 'AIClientError', 'AITimeoutError', 'AIUnavailableError', 'AIValidationError', 'AIContractError', 'AIClient'], 'src.modules.stocks.infrastructure.dart_corp_code_client': ['_DEFAULT_TIMEOUT', '_DEFAULT_MAX_BYTES', '_MEMBER_NAME', 'DartCorpCodeError', 'DartCorpCodeClient'], 'src.modules.stocks.infrastructure.kis_master_client': ['_URL', '_MST_NAME', '_DEFAULT_TIMEOUT', '_DEFAULT_MAX_BYTES', 'KisMasterError', 'KisMasterClient'], 'src.shared.config': ['_BACKEND_ROOT', '_ENV_FILE', 'Settings', '_load_settings', 'settings'], 'src.modules.news.domain.importance_rules': ['IMPORTANCE_W_VOLUME', 'IMPORTANCE_W_PUBLISHER', 'IMPORTANCE_W_SENTIMENT', 'IMPORTANCE_VOLUME_MODE', 'IMPORTANCE_PUBLISHER_WEIGHTS', 'IMPORTANCE_DEFAULT_PUBLISHER_WEIGHT'], 'src.modules.stocks.domain.constants.kis_master': ['FRONT_CODE', 'FRONT_STD', 'FRONT_NAME_START', 'KOSPI_TAIL', 'KOSDAQ_TAIL', 'KOSPI_FIELDS', 'KOSDAQ_FIELDS', 'MARKET_KOSPI', 'MARKET_KOSDAQ', 'FLAG_VALUE_SEMANTICS_VERIFIED', 'GROUP_CODE_STOCK', '_FLAG_SET_VALUES_PROVISIONAL', 'spac_flag_set', 'etp_flag_set'], 'src.modules.stocks.domain.constants.stock_aliases': ['ALIAS_SEED', 'REPRESENTATIVE_ALIAS_SEED'], 'src.modules.stocks.domain.constants.stock_match': ['JOSA_SUFFIXES', 'CONTEXT_SUFFIXES', 'SHORT_NAME_MAX_LEN'], 'src.modules.stocks.domain.constants.stocks': ['SUPPORTED_STOCKS', 'STOCK_NAMES', 'allowlist_name', 'REPRESENTATIVE_STOCKS'], 'src.modules.reports.infrastructure.agent_report_repository': ['count_reports', 'add', 'list_reports', 'delete_all_for_type', 'delete_for_technical', 'delete_all_technical'], 'src.modules.stocks.infrastructure.corp_code_repository': ['get_corp_code', 'get_all_corp_codes'], 'src.modules.flow.infrastructure.report_repository': ['ensure_stock', 'add_report', 'get_report', 'get_interpretation', 'get_verification', 'get_agent_indexes', 'get_report_parts', 'delete_agent_index', 'delete_root', 'eligible_flow_ids', 'get_owned_report', 'list_owned_indexes'], 'src.modules.fundamental.infrastructure.report_repository': ['ensure_stock', 'add_report', 'get_report', 'list_reports_by_stock', 'list_ratios', 'list_evidence', 'get_interpretation', 'get_verification', 'list_insights', 'list_filing_snippets', 'delete_agent_index', 'delete_root'], 'src.modules.industry.infrastructure.report_repository': ['add_report', 'get_report', 'list_reports', 'delete_agent_index', 'delete_root'], 'src.modules.news.infrastructure.news_graph_repository': ['_NEWSREF', '_identity', 'merge_graph', 'get_events_by_companies', 'get_events_by_ids', 'get_shared_events', 'companies_exist', 'cleanup_graph'], 'src.modules.news.infrastructure.report_repository': ['add_report', 'get_report', 'delete_root', 'delete_agent_index'], 'src.modules.news.infrastructure.news_repository': ['_UPSERT_UPDATE_COLS', 'upsert_articles', 'get_existing_urls', 'get_articles_by_event', 'get_events_near_embedding', 'get_event_article_stats', 'get_event_aggregates', 'get_daily_article_counts', 'delete_articles_before', 'get_articles_for_importance', 'get_event_centroid_inputs'], 'src.modules.stocks.infrastructure.stock_repository': ['get_all_stocks', 'get_all_aliases'], 'src.modules.technical.infrastructure.report_repository': ['ensure_stock', 'add_report', 'get_report', 'get_stock', 'list_followups', 'add_followup', 'count_followups', 'followup_counts_for', 'list_technical_reports', 'count_technical_reports', 'get_stocks', 'get_interpretation', 'delete_root', 'delete_all_roots'], 'src.modules.auth.api.router': ['router', 'SESSION_COOKIE', 'CORRELATION_COOKIE', 'PRIVATE', 'get_oidc', 'configured', 'secure_cookie', 'unique_cookie', 'validate_local_auth_host', 'request_principal', 'login', 'callback', 'session_info', 'logout'], 'src.modules.flow.api.router': ['FlowContractRoute', 'router', 'get_flow_report_service', 'save_flow_report', 'list_flow_reports', 'get_flow_report', 'delete_all_flow_reports', 'delete_flow_report'], 'src.modules.fundamental.api.router': ['router', 'get_fundamental_report_service', 'create_fundamental_report', 'save_fundamental_report', 'list_fundamental_reports', 'get_fundamental_report', 'delete_all_fundamental_reports', 'delete_fundamental_report'], 'src.modules.industry.api.router': ['router', 'get_industry_report_service', 'create_industry_report', 'list_industry_reports', 'get_industry_report', 'get_industry_report_html', 'delete_all_industry_reports', 'delete_industry_report'], 'src.modules.news.api.router': ['router', 'save_batch', 'existing_urls', 'cleanup', 'get_event_stats', 'get_event_articles', 'query_subject', 'query_shared', 'events_recent', 'events_merge_candidates', 'create_report', 'get_report', 'delete_all_reports', 'delete_report'], 'src.modules.reports.api.router': ['router', 'list_report_archive', 'list_reports'], 'src.modules.stocks.api.router': ['logger', 'router', 'resolve_stock'], 'src.modules.technical.api.router': ['router', 'create_technical_report', 'list_technical_reports', 'get_technical_report', 'get_technical_report_trace', 'create_technical_report_followup', 'get_technical_report_followups', 'delete_all_technical_reports', 'delete_technical_report'], 'src.modules.reports.api.report_schemas': ['AgentReportListItem', 'ReportsListResponse'], 'src.modules.fundamental.domain.ai_output': ['_Lenient', 'FundamentalErdPayloadMirror', 'FundamentalMetaMirror', 'FundamentalAgentOutputMirror'], 'src.modules.technical.domain.ai_output': ['_Lenient', 'MirrorRegime', 'MirrorSignalSummary', 'MirrorTechnicalSignal', 'MirrorRiskItem', 'MirrorRisk', 'MirrorChart', 'MirrorInterpretation', 'MirrorVerification', 'TechnicalAgentOutputMirror'], 'src.modules.flow.domain.execution': ['ContractModel', 'NonBlank', 'FlowRunRequest', 'ExecutionReference', 'ExecutionContext', 'FlowResultReference', 'ErrorCode', 'ERRORS', 'SafeError', 'ContractViolation', 'T', 'CommonResponse', 'FlowRunState', 'DataObservation', 'IdempotencyReference', 'bind_flow_result', 'validate_result_binding'], 'src.modules.flow.domain.payload': ['_iso_date', '_uuid_string', 'ISODate', 'UUIDString', 'Ticker', 'Number', 'PayloadPart', 'FlowMeta', 'FlowStrength', 'FlowConsecutive', 'FlowPersistence', 'FlowDaily', 'FlowOwnership', 'FlowPriceDaily', 'FlowSignals', 'FlowGate', 'FlowVerification', 'FlowInterpretationMeta', 'FlowPayloadV1', 'validate_flow_payload', '_check_json_types', 'validate_storage_string', 'projection_values_equal'], 'src.modules.flow.api.schemas': ['FlowReportSaveRequest', 'FlowReportEnvelope', 'FlowReportListResponse'], 'src.modules.fundamental.api.schemas': ['FundamentalReportCreateRequest', 'FundamentalReportSaveRequest', 'FundamentalReportEnvelope', 'FundamentalReportListResponse'], 'src.modules.industry.api.schemas': ['IndustryReportCreateRequest', 'IndustryReportEnvelope', 'IndustryReportListResponse'], 'src.modules.news.api.schemas': ['SentimentLabel', 'ArticleIn', 'NodeLabel', 'RelType', 'GraphNode', 'GraphRelationship', 'GraphBatch', 'NewsBatchSaveRequest', 'SaveResponse', 'ExistingUrlsRequest', 'ExistingUrlsResponse', 'CleanupResponse', 'ArticleRef', 'EventArticleStats', 'CandidateEvent', 'MergeCandidateQuery', 'SentimentGauge', 'Event', 'EventWithArticles', 'DailyCount', 'SubjectQueryResponse'], 'src.modules.news.api.report_schemas': ['NewsReportCreateRequest', 'NewsReportEnvelope'], 'src.modules.reports.api.archive_schemas': ['ArchiveCardStock', 'ArchiveCard', 'ArchiveCardStatus', 'ArchiveCardMeta', 'ArchiveItem', 'ArchiveListResponse'], 'src.modules.stocks.api.schemas': ['MatchType', 'ResolveStatus', 'ResolveReason', 'StockResolveRequest', 'ResolvedStock', 'StockCandidate', 'StockResolveResponse'], 'src.modules.technical.api.schemas': ['TechnicalReportCreateRequest', 'StockBlock', 'MetaBlock', 'SummaryBlock', 'InterpretationBlock', 'DriversBlock', 'SignalItem', 'SignalsBlock', 'RiskItemBlock', 'RisksBlock', 'ChartItem', 'ChartsBlock', 'VerificationBlock', 'GenerationPathBlock', 'DataQualityBlock', 'VerificationSummaryBlock', 'StabilityBlock', 'TraceFlagsBlock', 'TraceSummaryBlock', 'SignalQualityBlock', 'VerificationGateBlock', 'SourceLinkageBlock', 'TrustSummaryBlock', 'AnnotationBrief', 'IndicatorCalcBasis', 'IndicatorCard', 'TechnicalReportReadModel', 'ChartItemFull', 'TechnicalChartsReadModel', 'TraceStepItem', 'TraceOverallBlock', 'TechnicalTraceDetailReadModel', 'FollowupContextBlock', 'FollowupCreateRequest', 'FollowupItem', 'FollowupReportSummary', 'ListSummaryBlock', 'ListStatusBlock', 'ListEngagementBlock', 'ListMetaBlock', 'TechnicalReportListItem', 'TechnicalReportListResponse', 'TechnicalReportFollowupsReadModel'], 'src.modules.auth.application.session_service': ['AuthenticationRequired', 'Principal', 'token_digest', 'link_verified_identity', 'issue_session', 'authenticate', 'validate_principal', 'revoke_session', 'csrf_token', 'verify_csrf'], 'src.modules.stocks.application.corp_code_sync_service': ['_DEFAULT_MIN', 'CorpCodeSyncError', 'CorpCodeSyncSummary', 'sync_corp_codes'], 'src.modules.stocks.domain.dart_corp_code_parser': ['CorpCodeParseError', 'CorpCodeRecord', 'CorpCodeParseResult', '_text', '_valid_modify_date', 'parse_corp_code'], 'src.modules.flow.application.report_service': ['PAYLOAD_SNAPSHOT_KEY', 'STORAGE_FORMAT_KEY', 'STORAGE_FORMAT', 'FlowPayloadError', 'FlowStoredPayloadError', 'FlowReportService'], 'src.modules.fundamental.application.report_service': ['_parse_dt', '_uuid', '_decimal', '_model_dict', '_REPORT_FIELDS', '_RATIO_FIELDS', '_EVIDENCE_FIELDS', '_INTERPRETATION_FIELDS', '_VERIFICATION_FIELDS', '_INSIGHT_FIELDS', '_SNIPPET_FIELDS', 'FundamentalReportService'], 'src.modules.news.domain.importance': ['_VOLUME_TRANSFORMS', '_DEFAULT_VOLUME_MODE', '_WS_RE', '_ArticleLike', '_normalize_publisher', '_volume_transform', 'publisher_weight', 'sentiment_magnitude', 'compute_importance'], 'src.modules.industry.application.report_service': ['_parse_dt', '_d', '_require_str', '_validate_payload', '_answer_text', '_headline', 'IndustryReportService'], 'src.modules.news.application.cleanup_service': ['logger', '_ROLLING_HOURS', 'NewsCleanupService'], 'src.modules.news.application.graph_query_service': ['_REP_ARTICLE_LIMIT', '_centroid', '_as_uuid', 'NewsGraphQueryService'], 'src.modules.news.application.query_service': ['NewsQueryService'], 'src.modules.news.application.report_service': ['_parse_dt', 'NewsReportService'], 'src.modules.news.application.ingest_service': ['logger', '_to_row', 'NewsService'], 'src.modules.stocks.domain.stock_master_parser': ['_CODE_RE', '_market_spec', 'StockRecord', 'ParseResult', '_tail_field', 'inspect_rows', 'parse_master'], 'src.modules.stocks.application.resolver_service': ['_CODE_RE', '_TOKEN_RE', '_MAX_RUN', '_MATCH_PRIORITY', '_MAX_CANDIDATES', '_CONTEXT_SET', '_STRIP_SUFFIXES', 'EmptyQueryError', '_Entry', '_Match', '_Cand', 'StockResolverService'], 'src.modules.stocks.application.stock_sync_service': ['_DEFAULT_MIN', 'StockSyncError', 'SyncSummary', 'sync_stocks'], 'src.modules.technical.application.report_service': ['_parse_dt', '_d', '_list', 'build_read_model', '_SNAPSHOT_REGIME_KEYS', '_SNAPSHOT_BIAS_KEYS', '_SNAPSHOT_STATUS_KEYS', '_SNAPSHOT_SCORE_KEYS', '_SNAPSHOT_ASOF_KEYS', '_first', '_followup_context', '_followup_item', '_SNAPSHOT_VERSION', '_parent_context_snapshot', 'build_followups_read_model', '_CONSENSUS_LABELS', 'build_charts_read_model', 'build_trace_detail', '_INDICATOR_TITLE', '_SIGNAL_LABEL', '_INDICATOR_ANNOTATION_KINDS', '_PATTERN_CANDIDATE_KINDS', '_NUM_RE', '_MA_ROWS', '_RSI_POINTS', '_VOL_BARS', '_metric_num', '_annotation_briefs', '_daily_chart_data', '_ma_series', '_calc_basis', 'build_indicator_cards', '_derive_status', 'build_list_item', '_ARCHIVE_TYPE_LABEL', '_ARCHIVE_DETAIL_BASE', '_clip', '_archive_tone', 'build_archive_item', 'TechnicalReportService'], 'src.modules.stocks.domain.text_normalize': ['_DISALLOWED', 'normalize_stock_text']}

LEGACY_PUBLIC_DIGESTS = {
    "openapi": "dbec0f00b8c57c5a906639c7763e83e38f7c847e1ee5a4116342450a2195bc24",
    "payload": "a60b8618350693c42cebdf75b72d22163b2145f77857b7285dc614262d72af5a",
    "schemas": "91065e01c38b32b5a39a8746b8dc8ca216f471580eb2c59f0d5262065e20772b",
}
CF003_ENUM_ADDITIONS = ["FEATURE_UNAVAILABLE", "AUTH_REQUEST_INVALID", "SERVICE_UNAVAILABLE"]
LEGACY_ERROR_CODES = ["AUTH_REQUIRED", "RESOURCE_NOT_FOUND", "IDEMPOTENCY_CONFLICT", "RESULT_CONFLICT",
                      "INPUT_INVALID", "UNSUPPORTED_VERSION", "RESULT_CONTRACT_INVALID", "DATA_INSUFFICIENT"]
CF003_COMPONENTS = {"FlowAdmissionRequest", "FlowRunState", "SafeError", "ErrorCode", "CommonResponse_FlowRunState_"}


def public_contract_capture(monkeypatch):
    from pydantic import BaseModel
    from src.api import main
    from src.modules.flow.domain import execution as flow_execution, payload as flow_payload
    from src.modules.flow.api import schemas as flow_report
    from tests.fixtures import flow_payload as fixture_module
    monkeypatch.setattr(fixture_module, "uuid4", lambda: UUID("00000000-0000-4000-8000-000000000001"))
    schemas = {}
    for module in (flow_execution, flow_payload, flow_report):
        for name, value in vars(module).items():
            if (not name.startswith("_") and name != "AgentReportListItem" and isinstance(value, type)
                    and issubclass(value, BaseModel) and value is not BaseModel):
                schemas[name] = value.model_json_schema()
    return {"openapi": main.app.openapi(), "schemas": schemas, "payload": make_flow_payload()}


def project_cf008_exact_additions(api):
    """Independently inspect the three exact new components, never prefix-filter."""
    from src.modules.flow.api.synthetic_demo_schemas import DemoRequest, DemoRunView, DemoResponse, DEMO_PATH
    from fastapi.encoders import jsonable_encoder
    from fastapi.openapi.models import Schema
    components=api['components']['schemas']
    names={'DemoRequest','DemoRunView','CommonResponse_DemoRunView_'}
    request=components['DemoRequest'];view=components['DemoRunView']
    assert request['additionalProperties'] is False
    assert set(request['properties'])==set(request['required'])=={'idempotency_key','as_of','allow_fake'}
    assert request['properties']['as_of']['format']=='date-time'
    assert request['properties']['idempotency_key']['type']=='string'
    assert request['properties']['allow_fake']['type']=='boolean' and request['properties']['allow_fake']['const'] is True
    fields={'version','synthetic','mode','run_id','request_id','attempt_id','input_snapshot_id','execution_id','stage','deadline_at','finished_at','result_stored','result','result_sha256','failure_code'}
    assert set(view['properties'])==fields and view['additionalProperties'] is False
    assert view['properties']['version']['const']==1 and view['properties']['synthetic']['const'] is True
    assert view['properties']['mode']['const']=='synthetic_demo'
    assert view['properties']['stage']['enum']==['admitted','prepared','running','succeeded','failed','timed_out']
    assert view['properties']['result_stored']['type']=='boolean'
    for field in ('run_id','request_id','attempt_id'):assert view['properties'][field]['format']=='uuid'
    for path,method in ((DEMO_PATH,'post'),(DEMO_PATH+'/{run_id}','get')):
        operation=api['paths'][path];assert set(operation)=={method}
        assert operation[method]['responses']['200']['content']['application/json']['schema']=={'$ref':'#/components/schemas/CommonResponse_DemoRunView_'}
    assert api['paths'][DEMO_PATH]['post']['responses']['202']['content']['application/json']['schema']=={'$ref':'#/components/schemas/CommonResponse_DemoRunView_'}
    assert api['paths'][DEMO_PATH]['post']['requestBody']['content']['application/json']['schema']=={'$ref':'#/components/schemas/DemoRequest'}
    assert api['paths'][DEMO_PATH+'/{run_id}']['get']['parameters']==[{'name':'run_id','in':'path','required':True,'schema':{'type':'string','format':'uuid','title':'Run Id'}}]
    expected={}
    for model in (DemoRequest,DemoRunView,DemoResponse):
        schema=model.model_json_schema(ref_template='#/components/schemas/{model}',mode='validation' if model is DemoRequest else 'serialization')
        expected.update(schema.pop('$defs',{}));expected[{DemoRequest:'DemoRequest',DemoRunView:'DemoRunView',DemoResponse:'CommonResponse_DemoRunView_'}[model]]=schema
    for name in names:
        assert components[name]==jsonable_encoder(Schema.model_validate(expected[name]),by_alias=True,exclude_none=True),name
    for name in names:del components[name]
    del api['paths'][DEMO_PATH];del api['paths'][DEMO_PATH+'/{run_id}']


def project_cf012_exact_additions(api):
    """Validate approved paths/fields before projecting only their exact pointers."""
    from src.modules.flow.api.analysis_schemas import PATH,AnalysisRequest,AnalysisView,AnalysisResponse
    from fastapi.encoders import jsonable_encoder
    from fastapi.openapi.models import Schema
    components=api['components']['schemas']
    assert set(components['AnalysisRequest']['properties'])==set(components['AnalysisRequest']['required'])=={'ticker','question','as_of','idempotency_key','allow_analysis'}
    assert components['AnalysisRequest']['additionalProperties'] is False
    assert components['AnalysisRequest']['properties']['allow_analysis']['const'] is True
    fields={'analysis_id','admission_request_id','attempt_id','state','deadline_at','report_id','report_url','error'}
    assert set(components['AnalysisView']['properties'])==fields
    assert components['AnalysisView']['properties']['state']['enum']==['running','result_ready','stored','failed','unknown']
    for path,method in ((PATH,'post'),(PATH+'/{analysis_id}','get')):
        assert set(api['paths'][path])=={method}
        for status in ('200','202'):
            assert api['paths'][path][method]['responses'][status]['content']['application/json']['schema']=={'$ref':'#/components/schemas/CommonResponse_AnalysisView_'}
    assert api['paths'][PATH]['post']['requestBody']['content']['application/json']['schema']=={'$ref':'#/components/schemas/AnalysisRequest'}
    assert api['paths'][PATH+'/{analysis_id}']['get']['parameters']==[{'name':'analysis_id','in':'path','required':True,'schema':{'type':'string','format':'uuid','title':'Analysis Id'}}]
    expected={}
    for model,name in ((AnalysisRequest,'AnalysisRequest'),(AnalysisView,'AnalysisView'),(AnalysisResponse,'CommonResponse_AnalysisView_')):
        value=model.model_json_schema(ref_template='#/components/schemas/{model}',mode='validation' if model is AnalysisRequest else 'serialization')
        expected.update(value.pop('$defs',{}));expected[name]=value
    for name in ('AnalysisRequest','AnalysisView','CommonResponse_AnalysisView_'):
        assert components[name]==jsonable_encoder(Schema.model_validate(expected[name]),by_alias=True,exclude_none=True)
        del components[name]
    del api['paths'][PATH];del api['paths'][PATH+'/{analysis_id}']


def project_cf015_exact_additions(api):
    """Validate exact new financial DTOs/paths; preserve the old Flow baseline."""
    from src.modules.fundamental.api.analysis_schemas import PATH,FundamentalAnalysisRequest,FundamentalAnalysisView,FundamentalAnalysisResponse
    from fastapi.encoders import jsonable_encoder
    from fastapi.openapi.models import Schema
    components=api['components']['schemas'];expected={}
    names=('FundamentalAnalysisRequest','FundamentalAnalysisView','CommonResponse_FundamentalAnalysisView_')
    request=components[names[0]]
    assert request['additionalProperties'] is False
    assert set(request['properties'])==set(request['required'])=={'ticker','question','idempotency_key','allow_analysis'}
    assert request['properties']['allow_analysis']['const'] is True
    assert request['properties']['ticker']['pattern']=='^[0-9]{6}$'
    assert components[names[1]]['properties']['state']['enum']==['running','result_ready','stored','failed','unknown']
    for model,name in zip((FundamentalAnalysisRequest,FundamentalAnalysisView,FundamentalAnalysisResponse),names):
        value=model.model_json_schema(ref_template='#/components/schemas/{model}',mode='validation' if name==names[0] else 'serialization')
        expected.update(value.pop('$defs',{}));expected[name]=value
    for name in names:
        assert components[name]==jsonable_encoder(Schema.model_validate(expected[name]),by_alias=True,exclude_none=True)
        del components[name]
    for path,method in ((PATH,'post'),(PATH+'/{analysis_id}','get')):
        assert set(api['paths'][path])=={method}
        for status in ('200','202'):assert api['paths'][path][method]['responses'][status]['content']['application/json']['schema']=={'$ref':'#/components/schemas/'+names[2]}
    assert api['paths'][PATH]['post']['requestBody']['content']['application/json']['schema']=={'$ref':'#/components/schemas/'+names[0]}
    del api['paths'][PATH];del api['paths'][PATH+'/{analysis_id}']
    # Approved owned list adds an optional ticker filter; only this parameter changes.
    parameters=api['paths']['/api/fundamental/reports']['get']['parameters']
    stock=next(p for p in parameters if p['name']=='stock_code')
    assert stock=={'name':'stock_code','in':'query','required':False,'schema':{'anyOf':[{'type':'string','pattern':'^[0-9]{6}$'},{'type':'null'}],'title':'Stock Code'}}
    stock['required']=True;stock['schema']={'type':'string','pattern':r'^\d{6}$','title':'Stock Code'}


def project_cf036_exact_additions(api):
    """Check exactly the two owned GET operations before legacy projection."""
    for path, summary, operation_id in (
        ('/api/technical/owned-reports','Listing','listing_api_technical_owned_reports_get'),
        ('/api/technical/owned-reports/{report_id}','Detail','detail_api_technical_owned_reports__report_id__get'),
    ):
        assert api['paths'][path] == {'get': {
            'tags':['technical-owned-read'], 'summary':summary, 'operationId':operation_id,
            'responses':{'200':{'description':'Successful Response',
                'content':{'application/json':{'schema':{}}}}},
        }}
        del api['paths'][path]
    # Unknown paths/components deliberately remain for the unchanged digest check.


def project_cf023_exact_additions(api):
    """Only the three preparation operations and explicitly reviewed schema deltas."""
    from fastapi import FastAPI
    from src.modules.supervisor.api.router import router
    app=FastAPI();app.include_router(router);expected=app.openapi()
    routes={'/api/supervisor/core/preparations':{'post'},'/api/supervisor/core/preparations/{preparation_id}':{'get','delete'}}
    for path,methods in routes.items():
        assert set(api['paths'][path])==methods
        assert api['paths'][path]==expected['paths'][path]
        del api['paths'][path]
    schemas=api['components']['schemas']
    names={'CorePreparationRequest','CorePreparationView','CoreEnvelope_CorePreparationView_'}
    for name in names:
        assert schemas[name]==expected['components']['schemas'][name]
        del schemas[name]
    assert set(expected['components']['schemas']['CorePreparationRequest']['properties'])=={'prepare_key','draft','parent_preparation_id'}
    assert set(expected['components']['schemas']['CorePreparationView']['properties'])=={'preparation_id','state','plan','created_at','expires_at','meaning_status','consumed_binding_id'}
    assert expected['components']['schemas']['CorePreparationRequest']['additionalProperties'] is False
    assert expected['components']['schemas']['CorePreparationView']['additionalProperties'] is False
    confirm=schemas['CoreConfirm']
    field=confirm['properties'].pop('preparation_id')
    assert field=={'anyOf':[{'type':'string','pattern':'^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$'},{'type':'null'}],'title':'Preparation Id'}
    assert 'preparation_id' not in confirm.get('required',[])
    policy=schemas['CorePlan']['properties']['policy_version']
    assert policy=={'type':'string','enum':['supervisor.flow-core.1','supervisor.flow-core.2'],'title':'Policy Version'}
    schemas['CorePlan']['properties']['policy_version']={'type':'string','const':'supervisor.flow-core.1','title':'Policy Version'}
    codes=schemas['CoreSafeError']['properties']['code']['enum']
    extra=['PREPARATION_EXPIRED','PREPARATION_DELETED','PREPARATION_CONSUMED','MEANING_LIMIT_EXCEEDED']
    assert codes[-4:]==extra
    del codes[-4:]


def project_cf054_exact_additions(api):
    """Verify the three exact Technical wires and strict model closure before projection."""
    from fastapi import FastAPI
    from src.modules.supervisor.api.router import router
    from src.modules.supervisor.domain import technical_core_contracts as C
    isolated=FastAPI();isolated.include_router(router);expected=isolated.openapi()
    paths={'/api/supervisor/core/technical/prepare':{'post'},'/api/supervisor/core/technical/requests':{'post'},'/api/supervisor/core/technical/requests/{supervisor_id}':{'get'}}
    for path,methods in paths.items():
        assert set(api['paths'][path])==methods
        assert api['paths'][path]==expected['paths'][path]
    confirm=C.Confirm.model_json_schema()
    assert set(confirm['properties'])=={'client_key','draft','expected_plan_hash','consent'} and confirm['additionalProperties'] is False
    assert set(C.Consent.model_json_schema()['properties'])=={'allow_technical','allow_partial','waived_conditions'}
    assert C.Reference.model_json_schema()['properties']['report_url']=={'default':None,'title':'Report Url','type':'null'}
    shared={'CoreDraft','CoreAnswer','CoreMeaningFrame','CoreMention','CoreEvidence','CoreCondition','CoreResolution','CoreStock','CoreCandidate'}
    names={'TechnicalConfirm','TechnicalConsent','TechnicalContext','TechnicalPlan','TechnicalProfile','TechnicalReference','TechnicalEffectiveScope','TechnicalOutcome','TechnicalSafeError','TechnicalEnvelope_TechnicalPlan_','TechnicalEnvelope_TechnicalOutcome_'}
    assert shared <= set(expected['components']['schemas'])
    for name in names:
        assert api['components']['schemas'][name]==expected['components']['schemas'][name]
        assert api['components']['schemas'][name].get('additionalProperties') is False
    for path in paths:del api['paths'][path]
    for name in names:del api['components']['schemas'][name]


def project_cf022_exact_additions(api):
    from fastapi import FastAPI
    from src.modules.supervisor.api.router import router
    isolated=FastAPI();isolated.include_router(router);expected=isolated.openapi()
    project_cf054_exact_additions(expected)
    project_cf023_exact_additions(expected)
    paths={'/api/supervisor/core/prepare','/api/supervisor/core/requests','/api/supervisor/core/requests/{supervisor_id}'}
    assert set(expected['paths'])==paths
    names={'CoreAnswer','CoreDraft','CoreEvidence','CoreMention','CoreCondition','CoreMeaningFrame','CoreStock','CoreCandidate','CoreResolution','CoreCapability','CorePlan','CoreConsent','CoreConfirm','CoreViewOutcome','CoreFlowReference','CoreEffectiveScope','CoreOutcome','CoreSafeError','CoreEnvelope_CorePlan_','CoreEnvelope_CoreOutcome_'}
    assert set(expected['components']['schemas'])-{'HTTPValidationError','ValidationError'}==names
    for path in paths:assert api['paths'][path]==expected['paths'][path];del api['paths'][path]
    for name in names:assert api['components']['schemas'][name]==expected['components']['schemas'][name];del api['components']['schemas'][name]


def project_cf020_exact_additions(api):
    """Validate this one path and exact model definitions before projection."""
    from src.modules.flow.api.query_plan_schemas import QueryPlanRequest,QueryPlanResponse
    from fastapi.encoders import jsonable_encoder
    from fastapi.openapi.models import Schema
    components=api['components']['schemas'];path='/api/flow/plans'
    assert set(api['paths'][path])=={'post'}
    operation=api['paths'][path]['post']
    assert operation['requestBody']['content']['application/json']['schema']=={'$ref':'#/components/schemas/QueryPlanRequest'}
    assert operation['responses']['200']['content']['application/json']['schema']=={'$ref':'#/components/schemas/QueryPlanResponse'}
    assert not operation.get('parameters')
    request=components['QueryPlanRequest']
    assert set(request['properties'])=={'query','selected_ticker','candidate_ref'} and request['required']==['query']
    assert request['additionalProperties'] is False and request['properties']['query']['maxLength']==300
    expected={}
    for model in (QueryPlanRequest,QueryPlanResponse):
        schema=model.model_json_schema(ref_template='#/components/schemas/{model}',mode='validation' if model is QueryPlanRequest else 'serialization')
        expected.update(schema.pop('$defs',{}));expected[model.__name__]=schema
    names={'QueryPlanRequest','QueryPlanResponse','QueryPlanSafeError','PlanView','CanonicalResolution','StockReference','StockOption'}
    assert set(expected)==names
    for name in names:
        assert components[name]==jsonable_encoder(Schema.model_validate(expected[name]),by_alias=True,exclude_none=True)
    for name in names:del components[name]
    del api['paths'][path]


def assert_public_contract_compatibility(values):
    """Validate exact additions first, then remove only reviewed JSON pointers from a copy."""
    import hashlib
    from src.modules.flow.api.run_schemas import FlowAdmissionRequest, RunResponse
    from src.modules.flow.domain.execution import CommonResponse, FlowRunState
    from fastapi.encoders import jsonable_encoder
    from fastapi.openapi.models import Schema
    projected = copy.deepcopy(values)
    api = projected["openapi"]
    project_cf054_exact_additions(api)
    project_cf036_exact_additions(api)
    project_cf023_exact_additions(api)
    project_cf022_exact_additions(api)
    project_cf020_exact_additions(api)
    project_cf015_exact_additions(api)
    from src.modules.fundamental.api.analysis_schemas import FundamentalAnalysisResponse
    if "CommonResponse[FundamentalAnalysisView]" in projected["schemas"]:
        assert projected["schemas"]["CommonResponse[FundamentalAnalysisView]"]==FundamentalAnalysisResponse.model_json_schema()
        del projected["schemas"]["CommonResponse[FundamentalAnalysisView]"]
    project_cf012_exact_additions(api)
    from src.modules.flow.api.analysis_schemas import AnalysisResponse
    if "CommonResponse[AnalysisView]" in projected["schemas"]:
        assert projected["schemas"]["CommonResponse[AnalysisView]"]==AnalysisResponse.model_json_schema()
        del projected["schemas"]["CommonResponse[AnalysisView]"]
    project_cf008_exact_additions(api)
    from src.modules.flow.api.synthetic_demo_schemas import DemoResponse
    if 'CommonResponse[DemoRunView]' in projected['schemas']:
        assert projected['schemas']['CommonResponse[DemoRunView]']==DemoResponse.model_json_schema()
        del projected['schemas']['CommonResponse[DemoRunView]']
    components = api["components"]["schemas"]
    assert list(ErrorCode) == [ErrorCode(value) for value in LEGACY_ERROR_CODES + CF003_ENUM_ADDITIONS + ["USAGE_LIMIT_EXCEEDED"]]
    assert components["ErrorCode"]["enum"] == LEGACY_ERROR_CODES + CF003_ENUM_ADDITIONS + ["USAGE_LIMIT_EXCEEDED"]
    for path, method, status in [("/api/flow/runs", "post", "202"), ("/api/flow/runs/{run_id}", "get", "200")]:
        operation = api["paths"][path]
        assert set(operation) == {method}
        assert operation[method]["responses"][status]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/CommonResponse_FlowRunState_"}
    assert api["paths"]["/api/flow/runs"]["post"]["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/FlowAdmissionRequest"}
    assert api["paths"]["/api/flow/runs/{run_id}"]["get"]["parameters"] == [{
        "name": "run_id", "in": "path", "required": True,
        "schema": {"type": "string", "format": "uuid", "title": "Run Id"}}]
    request_schema = components["FlowAdmissionRequest"]
    assert set(request_schema["properties"]) == set(request_schema["required"]) == {"ticker", "question", "as_of", "idempotency_key"}
    assert request_schema["additionalProperties"] is False
    assert request_schema["properties"]["question"]["maxLength"] == 2000
    assert request_schema["properties"]["question"]["pattern"] == r"\S"
    assert request_schema["properties"]["ticker"]["pattern"] == r"^[0-9]{6}$"
    assert request_schema["properties"]["as_of"]["format"] == "date-time"
    assert RunResponse.__pydantic_generic_metadata__["origin"] is CommonResponse
    assert RunResponse.__pydantic_generic_metadata__["args"] == (FlowRunState,)
    expected_components = {}
    for model in (FlowAdmissionRequest, RunResponse):
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}",
                                         mode="validation" if model is FlowAdmissionRequest else "serialization")
        definitions = schema.pop("$defs", {})
        expected_components.update(definitions)
        expected_components["FlowAdmissionRequest" if model is FlowAdmissionRequest else "CommonResponse_FlowRunState_"] = schema
    assert set(expected_components) == CF003_COMPONENTS
    for name in CF003_COMPONENTS:
        # The installed FastAPI OpenAPI encoder omits None-valued Schema defaults.
        # Apply its encoder only to these five independently checked new components.
        expected_schema = jsonable_encoder(Schema.model_validate(expected_components[name]), by_alias=True, exclude_none=True)
        assert components[name] == expected_schema, name
        del components[name]
    del api["paths"]["/api/flow/runs"]
    del api["paths"]["/api/flow/runs/{run_id}"]
    # Exact possible generic map key, created by Pydantic; never filter by prefix.
    generic_name = "CommonResponse[FlowRunState]"
    if generic_name in projected["schemas"]:
        assert projected["schemas"][generic_name] == RunResponse.model_json_schema()
        del projected["schemas"][generic_name]
    # Inspect the one approved CF-018 enum addition before projecting to the old baseline.
    from src.modules.flow.domain.execution import ERRORS
    assert ERRORS[ErrorCode.USAGE_LIMIT_EXCEEDED] == (429, "분석 사용 한도에 도달했습니다. 기존 결과는 조회할 수 있습니다.")
    # All other values/fields remain exact; an unapproved value or pointer fails.
    for name in ("CommonResponse", "SafeError", "FlowRunState"):
        enum = projected["schemas"][name]["$defs"]["ErrorCode"]["enum"]
        assert enum == LEGACY_ERROR_CODES + CF003_ENUM_ADDITIONS + ["USAGE_LIMIT_EXCEEDED"]
        projected["schemas"][name]["$defs"]["ErrorCode"]["enum"] = LEGACY_ERROR_CODES[:]
    digests = {name: hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
               for name, value in projected.items()}
    assert digests == LEGACY_PUBLIC_DIGESTS


def test_relocation_public_contract_baseline(monkeypatch):
    assert_public_contract_compatibility(public_contract_capture(monkeypatch))


@pytest.mark.parametrize("change", ["path", "component", "legacy_field", "fourth_enum", "request_field", "legacy_method", "legacy_response", "legacy_enum", "demo_method", "demo_stage", "demo_extra", "owned_method", "owned_metadata", "owned_response", "owned_parameter", "owned_path", "owned_schema"])
def test_cf003_snapshot_projection_rejects_unapproved_changes(monkeypatch, change):
    values = copy.deepcopy(public_contract_capture(monkeypatch))
    if change == "path":
        values["openapi"]["paths"]["/api/flow/unapproved"] = {}
    elif change == "component":
        values["openapi"]["components"]["schemas"]["Unapproved"] = {"type": "string"}
    elif change == "legacy_field":
        values["schemas"]["FlowRunRequest"]["properties"]["ticker"]["type"] = "integer"
    elif change == "fourth_enum":
        values["openapi"]["components"]["schemas"]["ErrorCode"]["enum"].append("UNAPPROVED")
    elif change == "legacy_method":
        values["openapi"]["paths"]["/health"]["post"] = {}
    elif change == "legacy_response":
        values["openapi"]["paths"]["/health"]["get"]["responses"]["200"]["description"] = "unexpected mutation"
    elif change == "legacy_enum":
        values["schemas"]["SafeError"]["$defs"]["ErrorCode"]["enum"].append("UNAPPROVED")
    elif change == "demo_method":
        values['openapi']['paths']['/api/flow/synthetic-demo/runs']['delete']={}
    elif change == "demo_stage":
        values['openapi']['components']['schemas']['DemoRunView']['properties']['stage']['enum'].append('unapproved')
    elif change == "demo_extra":
        values['openapi']['components']['schemas']['DemoUnapproved']={'type':'string'}
    elif change == 'owned_method':
        values['openapi']['paths']['/api/technical/owned-reports']['post']={}
    elif change == 'owned_metadata':
        values['openapi']['paths']['/api/technical/owned-reports']['get']['summary']='unapproved'
    elif change == 'owned_response':
        values['openapi']['paths']['/api/technical/owned-reports/{report_id}']['get']['responses']['200']['content']['application/json']['schema']={'type':'string'}
    elif change == 'owned_parameter':
        values['openapi']['paths']['/api/technical/owned-reports']['get']['parameters']=[{'name':'owner','in':'query'}]
    elif change == 'owned_path':
        values['openapi']['paths']['/api/technical/owned-reports/unapproved']={}
    elif change == 'owned_schema':
        values['openapi']['components']['schemas']['OwnedUnapproved']={'type':'string'}
    else:
        values["openapi"]["components"]["schemas"]["FlowAdmissionRequest"]["properties"]["owner"] = {"type": "string"}
    with pytest.raises(AssertionError):
        assert_public_contract_compatibility(values)


@pytest.fixture
def payload():
    return make_flow_payload()


def changed(payload, path, value):
    result = copy.deepcopy(payload)
    node = result
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return result


INVALID_VALUES = [
    (("meta",), []),
    (("meta",), "bad"),
    (("meta",), 7),
    (("meta",), None),
    (("signals",), []),
    (("signals",), "bad"),
    (("verification",), []),
    (("verification", "gate1"), "bad"),
    (("verification", "gate1", "passed"), "true"),
    (("verification", "gate1", "checks"), "bad"),
    (("verification", "gate1", "failures"), [1]),
    (("verification", "gate1", "gate"), 2),
    (("verification", "gate1", "gate"), True),
    (("verification", "regen_count"), -1),
    (("interpretation_meta",), 12),
    (("report_id",), "bad"),
    (("report_id",), None),
    (("report_id",), 123),
    (("meta", "ticker"), "5930"),
    (("meta", "ticker"), 5930),
    (("meta", "ticker"), "００５９３０"),
    (("meta", "base_date"), "2026-02-30"),
    (("meta", "base_date"), "2026-11-05T00:00:00"),
    (("meta", "base_date"), "20261105"),
    (("meta", "base_date"), ""),
    (("meta", "base_date"), 1793836800),
    (("signals", "daily", 0, "date"), "2026-13-01"),
    (("signals", "price_daily", 0, "date"), "2026-02-29"),
    (("signals", "ownership", 0, "date"), "yesterday"),
    (("signals", "strength", "외국인", "ratio"), "0"),
    (("signals", "strength", "외국인", "ratio"), None),
    (("signals", "strength", "외국인", "ratio"), True),
    (("signals", "strength", "외국인", "ratio"), float("nan")),
    (("signals", "price_daily", 0, "close"), float("inf")),
    (("signals", "consecutive", "외국인", "days"), -1),
    (("signals", "persistence", "외국인"), {}),
    (("signals", "daily", 0, "기관"), None),
    (("signals", "inst_detail"), {"증권": None}),
    (("signals", "ownership", 0, "ratio"), False),
    (("version",), 2),
    (("version",), "1"),
    (("version",), True),
    (("version",), 1.0),
    (("version",), None),
    (("data_status",), "normal"),
    (("data_status",), "data_limited"),
    (("verification", "outcome"), "fact_only"),
    (("verification", "gate3", "passed"), False),
    (("interpretation_meta", "source"), "fallback"),
]


@pytest.fixture
def memory(monkeypatch):
    from src.modules.auth.application.session_service import Principal
    from datetime import UTC, datetime, timedelta

    principal = Principal(
        uuid4(), uuid4(), datetime.now(UTC) + timedelta(hours=1), b"x" * 32
    )
    monkeypatch.setattr(service_module, "validate_principal", AsyncMock())
    rows = SimpleNamespace(
        report=None, interpretation=None, verification=None, index=None
    )

    async def store(session, **values):
        for key, value in values.items():
            setattr(rows, key, value)
        # Simulate a JSON serializer roundtrip, never real persistence.
        rows.report.signals = json.loads(json.dumps(rows.report.signals))
        rows.verification.checks = json.loads(json.dumps(rows.verification.checks))

    async def store_index(session, index):
        rows.index = index

    mocks = {}
    for name in (
        "ensure_stock",
        "add_report",
        "get_owned_report",
        "get_report",
        "get_interpretation",
        "get_verification",
        "get_agent_indexes",
        "get_report_parts",
    ):
        method = AsyncMock()
        mocks[name] = method
        monkeypatch.setattr(service_module.flow_repo, name, method)
    mocks["get_owned_report"].side_effect = lambda *args, **kwargs: rows.report
    mocks["add_report"].side_effect = store
    for name in ("report", "interpretation", "verification"):
        mocks[f"get_{name}"].side_effect = lambda *args, name=name: getattr(rows, name)
    mocks["index"] = AsyncMock(side_effect=store_index)
    mocks["get_agent_indexes"].side_effect = lambda *args, **kwargs: (
        [rows.index] if rows.index else []
    )
    mocks["get_report_parts"].side_effect = lambda *args, **kwargs: (
        [rows.report] if rows.report else [],
        [rows.interpretation] if rows.interpretation else [],
        [rows.verification] if rows.verification else [],
        [rows.index] if rows.index else [],
    )
    monkeypatch.setattr(service_module.agent_repo, "add", mocks["index"])
    monkeypatch.setattr(
        service_module.agent_repo,
        "list_reports",
        AsyncMock(
            side_effect=lambda *args, **kwargs: [rows.index] if rows.index else []
        ),
    )
    monkeypatch.setattr(
        service_module.flow_repo,
        "list_owned_indexes",
        service_module.agent_repo.list_reports,
    )
    session = SimpleNamespace(
        commit=AsyncMock(), flush=AsyncMock(), scalar=AsyncMock(return_value=None), rollback=AsyncMock()
    )
    return SimpleNamespace(
        service=FlowReportService(session, principal=principal),
        session=session,
        mocks=mocks,
        rows=rows,
    )


@pytest.fixture
async def client(memory):
    # Load settings only after isolated_environment and no_network are active.
    from src.modules.flow.api.router import get_flow_report_service, router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_flow_report_service] = lambda: memory.service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://unit"
    ) as client:
        yield client


def assert_no_writes(memory):
    for name in ("ensure_stock", "add_report", "index"):
        memory.mocks[name].assert_not_awaited()
    memory.session.commit.assert_not_awaited()


@pytest.mark.parametrize("path,value", INVALID_VALUES)
async def test_invalid_nested_payload_returns_safe_422_before_any_write(
    client, memory, payload, path, value
):
    bad = changed(payload, path, value)
    # Non-finite numbers cannot be sent by httpx's strict JSON serializer.
    if isinstance(value, float) and value != value or value == float("inf"):
        with pytest.raises(ValidationError):
            FlowReportSaveRequest(payload=bad, question="질문")
    else:
        response = await client.post(
            "/api/flow/reports/save", json={"payload": bad, "question": "질문"}
        )
        assert response.status_code == 422
        expected = "UNSUPPORTED_VERSION" if path == ("version",) else "INPUT_INVALID"
        assert response.json() == {
            "detail": SafeError(code=expected).model_dump(mode="json")
        }
    assert_no_writes(memory)


@pytest.mark.parametrize(
    "field",
    ["version", "report_id", "meta", "signals", "verification", "interpretation"],
)
async def test_missing_required_field_rejected(client, memory, payload, field):
    del payload[field]
    response = await client.post(
        "/api/flow/reports/save", json={"payload": payload, "question": "질문"}
    )
    assert response.status_code == 422
    assert_no_writes(memory)


@pytest.mark.parametrize("value", [[], "bad", None, 12])
async def test_service_revalidates_mutated_request_before_writing(
    memory, payload, value
):
    request = FlowReportSaveRequest(payload=payload, question="질문")
    request.payload["meta"] = value
    with pytest.raises(FlowPayloadError):
        await memory.service.save_report(request)
    assert_no_writes(memory)


async def test_current_producer_payload_roundtrip_preserves_identity_values_periods_and_checks(
    client, memory, payload
):
    original = copy.deepcopy(payload)
    response = await client.post(
        "/api/flow/reports/save", json={"payload": payload, "question": "질문"}
    )
    assert response.status_code == 201, response.text
    assert response.json()["report"] == original
    report_id = UUID(original["report_id"])
    assert (
        memory.rows.report.id
        == memory.rows.interpretation.report_id
        == memory.rows.verification.report_id
        == report_id
    )
    assert (
        memory.rows.report.ticker
        == memory.rows.report.stock_code
        == memory.rows.index.stock_code
        == "005930"
    )
    assert memory.rows.report.base_date == date(2026, 11, 5)
    assert (
        memory.rows.index.owner_user_id
        == memory.rows.report.owner_user_id
        == memory.service._principal.user_id
    )  # legacy, not authenticated ownership
    result = await client.get(f"/api/flow/reports/{report_id}")
    assert result.status_code == 200
    assert result.json() == {"report_id": str(report_id), "report": original}
    assert payload == original


async def test_additive_v1_fields_and_omissions_are_preserved(memory, payload):
    for field in ("trace_id", "data_status", "interpretation_meta"):
        payload.pop(field)
    payload["verification"].pop("outcome")
    payload["verification"].pop("regen_count")
    payload["meta"]["future_metadata"] = {
        "unit": "백만원",
        "period": ["2026-11-01", "2026-11-05"],
    }
    payload["future_flag"] = False
    payload["trace_id"] = "legacy-trace-string"
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    result = await memory.service.get_report(UUID(payload["report_id"]))
    assert result.report == payload


async def test_data_limited_missing_is_distinct_from_real_zero(memory, payload):
    payload["signals"]["price_daily"] = None
    payload["data_status"] = "data_limited"
    payload["verification"]["gate3"] = None
    payload["verification"]["outcome"] = "fact_only"
    payload["interpretation"] = None
    payload["interpretation_meta"] = {
        "source": "fallback",
        "provider": None,
        "model": None,
    }
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    result = await memory.service.get_report(UUID(payload["report_id"]))
    assert result.report == payload
    assert result.report["signals"]["strength"]["외국인"]["ratio"] == 0
    assert result.report["signals"]["price_daily"] is None


async def test_explicit_null_base_date_and_signals_not_replaced(memory, payload):
    payload.update(
        signals=None,
        interpretation=None,
        verification=None,
        interpretation_meta=None,
        data_status="data_limited",
    )
    payload["meta"]["base_date"] = None
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    assert memory.rows.report.signals is None
    assert (
        await memory.service.get_report(UUID(payload["report_id"]))
    ).report == payload


async def test_explicit_legacy_v1_adapter(memory, payload):
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    del memory.rows.verification.checks[PAYLOAD_SNAPSHOT_KEY]
    del memory.rows.verification.checks[STORAGE_FORMAT_KEY]
    del memory.rows.index.summary[STORAGE_FORMAT_KEY]
    result = await memory.service.get_report(UUID(payload["report_id"]))
    assert result.report == payload


@pytest.mark.parametrize(
    "field,value", [("version", 2), ("report_id", str(uuid4())), ("meta", [])]
)
async def test_invalid_stored_snapshot_is_safe_error_not_relabelled(
    client, memory, payload, field, value
):
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    snapshot = memory.rows.verification.checks[PAYLOAD_SNAPSHOT_KEY]
    snapshot[field] = value
    result = await client.get(f"/api/flow/reports/{payload['report_id']}")
    assert result.status_code == 502
    assert result.json()["detail"]["code"] == "RESULT_CONTRACT_INVALID"
    assert snapshot[field] == value


@pytest.mark.parametrize("checks", [["bad"], [], "bad", 0])
def test_invalid_legacy_checks_never_raise_attribute_error(checks):
    report = SimpleNamespace()
    with pytest.raises(FlowStoredPayloadError):
        FlowReportService._reconstruct_payload(
            report, None, SimpleNamespace(checks=checks)
        )


@pytest.mark.parametrize(
    "extension", [{1: "bad-key"}, {"bad": (1, 2)}, {"bad": float("nan")}]
)
def test_extensions_must_be_finite_native_json(payload, extension):
    payload["extension"] = extension
    with pytest.raises(ValueError):
        validate_flow_payload(payload)


@pytest.fixture
def public_input():
    return {
        "ticker": "005930",
        "question": "분석",
        "as_of": "2026-11-06T00:00:00Z",
        "idempotency_key": "fixture-key",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_user_id", str(uuid4())),
        ("owner", "spoof"),
        ("payload", {}),
        ("passed", True),
        ("client_session_id", "not-auth"),
        ("run_id", str(uuid4())),
    ],
)
def test_public_input_cannot_assert_internal_context(public_input, field, value):
    with pytest.raises(ValidationError):
        FlowRunRequest(**public_input, **{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("question", "  "),
        ("as_of", "2026-02-30T00:00:00Z"),
        ("as_of", "2026-11-06T00:00:00"),
        ("as_of", 123),
        ("as_of", "123"),
        ("as_of", "1793923200.0"),
        ("ticker", "123"),
        ("idempotency_key", " "),
    ],
)
def test_public_input_rejects_invalid_fields(public_input, field, value):
    public_input[field] = value
    with pytest.raises(ValidationError):
        FlowRunRequest(**public_input)


def test_owner_scoped_idempotency_contract(public_input):
    request = FlowRunRequest(**public_input)
    owner, run = uuid4(), uuid4()
    stored = IdempotencyReference(
        owner_user_id=owner,
        key=request.idempotency_key,
        input_fingerprint=request.input_fingerprint(),
        run_id=run,
    )
    assert stored.validate_replay(owner, request) == run
    public_input["as_of"] = "2026-11-06T09:00:00+09:00"
    assert stored.validate_replay(owner, FlowRunRequest(**public_input)) == run
    public_input["question"] = "다른 입력"
    with pytest.raises(ContractViolation) as error:
        stored.validate_replay(owner, FlowRunRequest(**public_input))
    assert error.value.error.http_status == 409
    with pytest.raises(ContractViolation) as error:
        stored.validate_replay(uuid4(), request)
    assert error.value.error.http_status == 404


def test_result_id_attempt_content_and_deletion_contract(payload):
    context = ExecutionContext(
        owner_user_id=uuid4(), request_id=uuid4(), run_id=uuid4(), attempt_id=uuid4()
    )
    result = bind_flow_result(context, payload)
    assert str(result.report_id) == payload["report_id"]
    validate_result_binding(
        context, bind_flow_result(context, copy.deepcopy(payload)), existing=result
    )
    for mutation in ({"report_id": str(uuid4())}, {"interpretation": "다른 최종 해석"}):
        other = bind_flow_result(context, {**payload, **mutation})
        with pytest.raises(ContractViolation) as error:
            validate_result_binding(context, other, existing=result)
        assert error.value.error.http_status == 409
    with pytest.raises(ContractViolation) as error:
        validate_result_binding(context, result, deleted=True)
    assert error.value.error.http_status == 404
    with pytest.raises(ContractViolation) as error:
        validate_result_binding(
            context.model_copy(update={"attempt_id": uuid4()}), result
        )
    assert error.value.error.code == ErrorCode.RESULT_CONTRACT_INVALID
    with pytest.raises(ContractViolation) as error:
        bind_flow_result(context, {**payload, "version": 99})
    assert error.value.error.code == ErrorCode.RESULT_CONTRACT_INVALID


def test_common_response_safe_errors_roundtrip_and_state_axes():
    for code in ErrorCode:
        error = SafeError(code=code)
        response = CommonResponse[dict](request_id=uuid4(), error=error)
        assert (
            CommonResponse[dict].model_validate_json(response.model_dump_json())
            == response
        )
    with pytest.raises(ValidationError):
        SafeError(code=ErrorCode.INPUT_INVALID, message="secret raw exception")
    for values in ({}, {"data": {}, "error": SafeError(code=ErrorCode.INPUT_INVALID)}):
        with pytest.raises(ValidationError):
            CommonResponse[dict](request_id=uuid4(), **values)
    refs = {"request_id": uuid4(), "run_id": uuid4(), "attempt_id": uuid4()}
    for state in ("pending", "running", "succeeded", "failed", "unknown"):
        FlowRunState(
            **refs,
            execution_status=state,
            storage_status="not_stored",
            error=SafeError(code=ErrorCode.RESULT_CONTRACT_INVALID)
            if state == "failed"
            else None,
        )
    with pytest.raises(ValidationError):
        FlowRunState(**refs, execution_status="running", storage_status="stored")


@pytest.mark.parametrize(
    "value,reason,valid",
    [
        (0, None, True),
        (None, "미수집", True),
        (None, None, False),
        (0, "미수집", False),
        (True, None, False),
        (float("inf"), None, False),
    ],
)
def test_observation_value_missing_unit_and_period(value, reason, valid):
    values = dict(
        source="synthetic",
        as_of="2026-11-06",
        period_start="2026-11-01",
        period_end="2026-11-05",
        unit="백만원",
        value=value,
        missing_reason=reason,
    )
    if valid:
        assert DataObservation(**values).value == value
    else:
        with pytest.raises(ValidationError):
            DataObservation(**values)
    for mutation in (
        {"unit": " "},
        {"source": ""},
        {"period_start": "2026-11-07"},
        {"as_of": "2026-11-04"},
        {"period_end": "2026-02-30"},
    ):
        with pytest.raises(ValidationError):
            DataObservation(**{**values, **mutation})


def test_version_schema_and_payload_validation_do_not_change_input(payload):
    assert FlowPayloadV1.model_json_schema()["properties"]["version"]["const"] == 1
    original = copy.deepcopy(payload)
    assert validate_flow_payload(payload) is payload
    assert payload == original
    assert FlowReportSaveRequest.model_json_schema()["properties"]["payload"][
        "$ref"
    ].endswith("/FlowPayloadV1")


@pytest.mark.parametrize("field", ["owner_user_id", "run_id", "passed"])
async def test_legacy_save_rejects_extra_internal_claims(
    client, memory, payload, field
):
    response = await client.post(
        "/api/flow/reports/save",
        json={
            "payload": payload,
            "question": "질문",
            field: "spoofed",
        },
    )
    assert response.status_code == 422
    assert_no_writes(memory)


@pytest.mark.parametrize("field", ["source", "provider", "model"])
def test_missing_interpretation_has_no_false_provenance(payload, field):
    payload["interpretation"] = None
    payload["verification"]["gate3"] = None
    payload["verification"]["outcome"] = "fact_only"
    payload["interpretation_meta"] = {
        "source": "fallback",
        "provider": None,
        "model": None,
    }
    payload["interpretation_meta"][field] = (
        "llm" if field == "source" else "false-provenance"
    )
    with pytest.raises(ValidationError):
        FlowReportSaveRequest(payload=payload, question="질문")


@pytest.mark.parametrize("stock_code", ["００５９３０", "5930", "005930 "])
async def test_list_ticker_filter_is_canonical_ascii(client, memory, stock_code):
    response = await client.get("/api/flow/reports", params={"stock_code": stock_code})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INPUT_INVALID"
    assert_no_writes(memory)


@pytest.mark.parametrize(
    "damage",
    [
        "root",
        "signals",
        "interpretation",
        "verification",
        "gate",
        "summary",
        "index",
        "missing_snapshot",
        "missing_format",
        "unknown_format",
        "empty_checks",
        "no_interpretation",
        "no_verification",
        "no_index",
        "duplicate_index",
        "missing_index_marker",
    ],
)
async def test_new_snapshot_projection_damage_is_rejected_without_legacy_fallback(
    memory, payload, damage
):
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    rows = memory.rows
    if damage == "root":
        rows.report.stock_name = "different"
    elif damage == "signals":
        rows.report.signals["strength"]["외국인"]["ratio"] = 123
    elif damage == "interpretation":
        rows.interpretation.interpretation = "different"
    elif damage == "verification":
        rows.verification.gate2_passed = False
    elif damage == "gate":
        rows.verification.checks["gate2"]["checks"] = ["different"]
    elif damage == "summary":
        rows.index.summary["base_date"] = "2026-11-01"
    elif damage == "index":
        rows.index.answer_text = "different"
    elif damage == "missing_snapshot":
        del rows.verification.checks[PAYLOAD_SNAPSHOT_KEY]
    elif damage == "missing_format":
        del rows.verification.checks[STORAGE_FORMAT_KEY]
    elif damage == "unknown_format":
        rows.verification.checks[STORAGE_FORMAT_KEY] = "unknown"
    elif damage == "empty_checks":
        rows.verification.checks = {}
    elif damage == "no_interpretation":
        rows.interpretation = None
    elif damage == "no_verification":
        rows.verification = None
    elif damage == "no_index":
        rows.index = None
    elif damage == "duplicate_index":
        memory.mocks["get_agent_indexes"].side_effect = lambda *args: [
            rows.index,
            rows.index,
        ]
    elif damage == "missing_index_marker":
        del rows.index.summary[STORAGE_FORMAT_KEY]
    with pytest.raises(FlowStoredPayloadError):
        await memory.service.get_report(UUID(payload["report_id"]))


@pytest.mark.parametrize(
    "endpoint", ["/api/flow/reports", "/api/reports", "/api/reports/archive"]
)
async def test_all_flow_list_paths_reject_inconsistent_snapshot(
    memory, payload, endpoint
):
    from src.modules.flow.api.router import get_flow_report_service
    from src.modules.flow.api.router import router as flow_router
    from src.modules.reports.api.router import router as common_router

    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    # Even a removed index format marker cannot bypass list validation.
    del memory.rows.index.summary[STORAGE_FORMAT_KEY]
    memory.rows.index.answer_text = "different"
    app = FastAPI()
    app.include_router(flow_router)
    app.include_router(common_router)
    app.dependency_overrides[get_flow_report_service] = lambda: memory.service
    app.dependency_overrides[get_flow_report_service] = lambda: memory.service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://unit"
    ) as client:
        response = await client.get(endpoint)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "RESULT_CONTRACT_INVALID"


@pytest.mark.parametrize("bad", ["\x00", "\ud800", "\udfff"])
@pytest.mark.parametrize(
    "location", ["known_value", "nested_value", "nested_key", "root_key"]
)
async def test_jsonb_unrepresentable_strings_are_rejected_before_writes(
    client, memory, payload, bad, location
):
    if location == "known_value":
        payload["meta"]["stock_name"] = "fixture" + bad
    elif location == "nested_value":
        payload["extension"] = {"nested": [{"text": "fixture" + bad}]}
    elif location == "nested_key":
        payload["extension"] = {"nested": [{"fixture" + bad: 0}]}
    else:
        payload["fixture" + bad] = 0
    original = copy.deepcopy(payload)
    with pytest.raises(ValidationError):
        FlowReportSaveRequest(payload=payload, question="질문")
    response = await client.post(
        "/api/flow/reports/save",
        content=json.dumps({"payload": payload, "question": "질문"}, ensure_ascii=True),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": SafeError(code=ErrorCode.INPUT_INVALID).model_dump(mode="json")
    }
    assert payload == original
    assert_no_writes(memory)


@pytest.mark.parametrize(
    "damage", ["number_to_bool", "bool_to_number", "gate_number_to_bool"]
)
async def test_snapshot_projection_distinguishes_json_boolean_and_number(
    memory, payload, damage
):
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    if damage == "number_to_bool":
        memory.rows.report.signals["strength"]["외국인"]["ratio"] = False
    elif damage == "bool_to_number":
        memory.rows.report.signals["strength"]["외국인"]["strong"] = 0
    else:
        memory.rows.verification.checks["gate1"]["gate"] = True
    with pytest.raises(FlowStoredPayloadError):
        await memory.service.get_report(UUID(payload["report_id"]))
    with pytest.raises(FlowStoredPayloadError):
        await memory.service.list_reports(stock_code=None, limit=20, offset=0)


@pytest.mark.parametrize("bad", ["\x00", "\ud800", "\udfff"])
@pytest.mark.parametrize("field", ["question", "client_session_id"])
async def test_non_payload_storage_text_rejected_before_writes(
    client, memory, payload, bad, field
):
    body = {"payload": payload, "question": "질문", field: "fixture" + bad}
    response = await client.post(
        "/api/flow/reports/save",
        content=json.dumps(body, ensure_ascii=True),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert_no_writes(memory)


def test_valid_unicode_and_literal_escape_sequences_are_preserved(payload):
    payload["extension"] = {"한글😀": ["e\u0301", r"\u0000", r"\ud800"]}
    original = copy.deepcopy(payload)
    request = FlowReportSaveRequest(payload=payload, question="질문😀")
    assert request.payload == original


@pytest.mark.parametrize(
    "old_name,new_name,names",
    [('src.api.schemas.flow_payload',
      'src.modules.flow.domain.payload',
      ['_iso_date',
       '_uuid_string',
       'ISODate',
       'UUIDString',
       'Ticker',
       'Number',
       'PayloadPart',
       'FlowMeta',
       'FlowStrength',
       'FlowConsecutive',
       'FlowPersistence',
       'FlowDaily',
       'FlowOwnership',
       'FlowPriceDaily',
       'FlowSignals',
       'FlowGate',
       'FlowVerification',
       'FlowInterpretationMeta',
       'FlowPayloadV1',
       'validate_flow_payload',
       '_check_json_types',
       'validate_storage_string',
       'projection_values_equal']),
     ('src.api.schemas.flow_execution',
      'src.modules.flow.domain.execution',
      ['ContractModel',
       'NonBlank',
       'FlowRunRequest',
       'ExecutionReference',
       'ExecutionContext',
       'FlowResultReference',
       'ErrorCode',
       'ERRORS',
       'SafeError',
       'ContractViolation',
       'T',
       'CommonResponse',
       'FlowRunState',
       'DataObservation',
       'IdempotencyReference',
       'bind_flow_result',
       'validate_result_binding']),
     ('src.api.schemas.flow_report',
      'src.modules.flow.api.schemas',
      ['FlowReportSaveRequest', 'FlowReportEnvelope', 'FlowReportListResponse']),
     ('src.api.routes.flow_reports',
      'src.modules.flow.api.router',
      ['FlowContractRoute',
       'router',
       'get_flow_report_service',
       'save_flow_report',
       'list_flow_reports',
       'get_flow_report',
       'delete_all_flow_reports',
       'delete_flow_report']),
     ('agents.flow.schemas',
      'agents.flow.domain.models',
      ['AgentInput', 'GateResult', 'SupplyDemandState', 'AgentOutput']),
     ('agents.flow.export.to_json',
      'agents.flow.api.payload',
      ['PAYLOAD_VERSION', 'derive_data_status', 'build_payload', 'to_json'])],
)
def test_relocated_exports_have_canonical_origin_without_shims(old_name, new_name, names):
    import importlib
    from pathlib import Path

    canonical = importlib.import_module(new_name)
    backend = Path(__file__).resolve().parents[2]
    source_root = backend.parent / "ai/src" if new_name.startswith("agents.") else backend
    expected = source_root.joinpath(*new_name.split(".")).with_suffix(".py")
    removed = source_root.joinpath(*old_name.split(".")).with_suffix(".py")
    assert Path(canonical.__spec__.origin).resolve() == expected
    assert expected.is_file()
    assert not removed.exists()
    for name in names:
        value = getattr(canonical, name)
        if callable(value) and getattr(value, "__name__", None) == name:
            assert value.__module__ == new_name
    if hasattr(canonical, "router"):
        from src.api.main import app
        # Installed FastAPI represents include_router with a lazy wrapper;
        # leaf APIRoutes are not flattened into app.routes.
        registered = [item for item in app.routes
                      if getattr(item, "original_router", None) is canonical.router]
        assert len(registered) == 1
        paths = app.openapi()["paths"]
        for route in canonical.router.routes:
            for method in route.methods:
                assert method.lower() in paths[route.path]


def test_relocated_flow_service_repository_use_canonical_patch_namespace(monkeypatch):
    from src.modules.flow.application import report_service as canonical_service
    from src.modules.flow.infrastructure import report_repository as canonical_repository

    assert service_module is canonical_service
    assert canonical_service.FlowReportService.__module__ == canonical_service.__name__
    assert canonical_repository.get_owned_report.__module__ == canonical_repository.__name__
    assert canonical_service.flow_repo is canonical_repository
    sentinel = object()
    monkeypatch.setattr(canonical_service, "validate_principal", sentinel)
    assert canonical_service.FlowReportService.save_report.__globals__["validate_principal"] is sentinel
    monkeypatch.setattr(canonical_repository, "get_owned_report", sentinel)
    assert canonical_service.flow_repo.get_owned_report is sentinel


@pytest.mark.parametrize(
    "legacy_name,canonical_name",
    [('src.api.clients.dart_corp_code_client',
      'src.modules.stocks.infrastructure.dart_corp_code_client'),
     ('src.api.clients.kis_master_client', 'src.modules.stocks.infrastructure.kis_master_client'),
     ('src.api.constants.kis_master', 'src.modules.stocks.domain.constants.kis_master'),
     ('src.api.constants.stock_aliases', 'src.modules.stocks.domain.constants.stock_aliases'),
     ('src.api.constants.stock_match', 'src.modules.stocks.domain.constants.stock_match'),
     ('src.api.constants.stocks', 'src.modules.stocks.domain.constants.stocks'),
     ('src.api.repositories.corp_code_repository',
      'src.modules.stocks.infrastructure.corp_code_repository'),
     ('src.api.repositories.stock_repository',
      'src.modules.stocks.infrastructure.stock_repository'),
     ('src.api.routes.stocks', 'src.modules.stocks.api.router'),
     ('src.api.schemas.stock_resolve', 'src.modules.stocks.api.schemas'),
     ('src.api.services.corp_code_sync_service',
      'src.modules.stocks.application.corp_code_sync_service'),
     ('src.api.services.dart_corp_code_parser', 'src.modules.stocks.domain.dart_corp_code_parser'),
     ('src.api.services.stock_master_parser', 'src.modules.stocks.domain.stock_master_parser'),
     ('src.api.services.stock_resolver_service',
      'src.modules.stocks.application.resolver_service'),
     ('src.api.services.stock_sync_service', 'src.modules.stocks.application.stock_sync_service'),
     ('src.api.text_normalize', 'src.modules.stocks.domain.text_normalize')],
)
def test_stocks_canonical_exports_origins_without_shims(legacy_name, canonical_name):
    import importlib
    from pathlib import Path

    canonical = importlib.import_module(canonical_name)
    backend = Path(__file__).resolve().parents[2]
    source_root = backend.parent / "ai/src" if canonical_name.startswith("agents.") else backend
    expected = source_root.joinpath(*canonical_name.split(".")).with_suffix(".py")
    removed = source_root.joinpath(*legacy_name.split(".")).with_suffix(".py")
    assert Path(canonical.__spec__.origin).resolve() == expected
    assert expected.is_file()
    assert not removed.exists()
    for name in CANONICAL_RELOCATED_EXPORTS[canonical_name]:
        value = getattr(canonical, name)
        if callable(value) and getattr(value, "__name__", None) == name:
            assert value.__module__ == canonical_name


@pytest.mark.parametrize(
    "legacy_name,canonical_name",
    [('src.api.repositories.technical_report_repository',
      'src.modules.technical.infrastructure.report_repository'),
     ('src.api.routes.technical_reports', 'src.modules.technical.api.router'),
     ('src.api.schemas.ai_technical_output', 'src.modules.technical.domain.ai_output'),
     ('src.api.schemas.technical_report', 'src.modules.technical.api.schemas'),
     ('src.api.services.technical_report_service',
      'src.modules.technical.application.report_service')],
)
def test_technical_canonical_exports_origins_without_shims(legacy_name, canonical_name):
    import importlib
    from pathlib import Path

    canonical = importlib.import_module(canonical_name)
    backend = Path(__file__).resolve().parents[2]
    source_root = backend.parent / "ai/src" if canonical_name.startswith("agents.") else backend
    expected = source_root.joinpath(*canonical_name.split(".")).with_suffix(".py")
    removed = source_root.joinpath(*legacy_name.split(".")).with_suffix(".py")
    assert Path(canonical.__spec__.origin).resolve() == expected
    assert expected.is_file()
    assert not removed.exists()
    for name in CANONICAL_RELOCATED_EXPORTS[canonical_name]:
        value = getattr(canonical, name)
        if callable(value) and getattr(value, "__name__", None) == name:
            assert value.__module__ == canonical_name


@pytest.mark.parametrize(
    "legacy_name,canonical_name",
    [('src.api.repositories.fundamental_report_repository',
      'src.modules.fundamental.infrastructure.report_repository'),
     ('src.api.routes.fundamental_reports', 'src.modules.fundamental.api.router'),
     ('src.api.schemas.ai_fundamental_output', 'src.modules.fundamental.domain.ai_output'),
     ('src.api.schemas.fundamental_report', 'src.modules.fundamental.api.schemas'),
     ('src.api.services.fundamental_report_service',
      'src.modules.fundamental.application.report_service')],
)
def test_fundamental_canonical_exports_origins_without_shims(legacy_name, canonical_name):
    import importlib
    from pathlib import Path

    canonical = importlib.import_module(canonical_name)
    backend = Path(__file__).resolve().parents[2]
    source_root = backend.parent / "ai/src" if canonical_name.startswith("agents.") else backend
    expected = source_root.joinpath(*canonical_name.split(".")).with_suffix(".py")
    removed = source_root.joinpath(*legacy_name.split(".")).with_suffix(".py")
    assert Path(canonical.__spec__.origin).resolve() == expected
    assert expected.is_file()
    assert not removed.exists()
    for name in CANONICAL_RELOCATED_EXPORTS[canonical_name]:
        value = getattr(canonical, name)
        if callable(value) and getattr(value, "__name__", None) == name:
            assert value.__module__ == canonical_name


@pytest.mark.parametrize("status_code", [200, 422, 504, 503])
async def test_fundamental_adapter_contract_with_memory_transport(status_code):
    import httpx
    from src.shared.infrastructure.clients.ai_client import AIClient, AITimeoutError, AIUnavailableError, AIValidationError

    seen = []
    token = "synthetic-fundamental-contract-token-32bytes"
    payload = {"request_id": "synthetic", "ticker": "005930"}
    def respond(request):
        assert request.headers["X-Fundamental-Service-Token"] == token
        seen.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(status_code, json={"synthetic": True})
    client = AIClient("http://memory.invalid", 1, service_token=token, transport=httpx.MockTransport(respond))
    if status_code == 200:
        assert await client.analyze_fundamental(payload) == {"synthetic": True}
    else:
        expected = {422: AIValidationError, 504: AITimeoutError, 503: AIUnavailableError}[status_code]
        with pytest.raises(expected):
            await client.analyze_fundamental(payload)
    assert seen == [("POST", "/internal/fundamental/analyze", payload)]


@pytest.mark.parametrize(
    "legacy_name,canonical_name",
    [('src.api.repositories.industry_report_repository',
      'src.modules.industry.infrastructure.report_repository'),
     ('src.api.routes.industry_reports', 'src.modules.industry.api.router'),
     ('src.api.schemas.industry_report', 'src.modules.industry.api.schemas'),
     ('src.api.services.industry_report_service',
      'src.modules.industry.application.report_service')],
)
def test_industry_canonical_exports_origins_without_shims(legacy_name, canonical_name):
    import importlib
    from pathlib import Path

    canonical = importlib.import_module(canonical_name)
    backend = Path(__file__).resolve().parents[2]
    source_root = backend.parent / "ai/src" if canonical_name.startswith("agents.") else backend
    expected = source_root.joinpath(*canonical_name.split(".")).with_suffix(".py")
    removed = source_root.joinpath(*legacy_name.split(".")).with_suffix(".py")
    assert Path(canonical.__spec__.origin).resolve() == expected
    assert expected.is_file()
    assert not removed.exists()
    for name in CANONICAL_RELOCATED_EXPORTS[canonical_name]:
        value = getattr(canonical, name)
        if callable(value) and getattr(value, "__name__", None) == name:
            assert value.__module__ == canonical_name


@pytest.mark.parametrize("method,path,is_html", [
    ("analyze_industry", "/internal/industry/analyze", False),
    ("render_industry_html", "/internal/industry/render", True),
])
@pytest.mark.parametrize("status_code", [200, 422, 504, 503])
async def test_industry_adapter_contract_with_memory_transport(method, path, is_html, status_code):
    import httpx
    from src.shared.infrastructure.clients.ai_client import AIClient, AITimeoutError, AIUnavailableError, AIValidationError

    seen = []
    payload = {"request_id": "synthetic", "ticker": "005930"}
    def respond(request):
        seen.append((request.method, request.url.path, json.loads(request.content)))
        if is_html:
            return httpx.Response(status_code, text="<html>synthetic</html>")
        return httpx.Response(status_code, json={"synthetic": True})
    client = AIClient("http://memory.invalid", 1, transport=httpx.MockTransport(respond))
    if status_code == 200:
        result = await getattr(client, method)(payload)
        assert result == ("<html>synthetic</html>" if is_html else {"synthetic": True})
    else:
        expected = {422: AIValidationError, 504: AITimeoutError, 503: AIUnavailableError}[status_code]
        with pytest.raises(expected):
            await getattr(client, method)(payload)
    assert seen == [("POST", path, payload)]


@pytest.mark.parametrize(
    "legacy_name,canonical_name",
    [('src.api.constants.importance', 'src.modules.news.domain.importance_rules'),
     ('src.api.repositories.news_graph_repository',
      'src.modules.news.infrastructure.news_graph_repository'),
     ('src.api.repositories.news_report_repository',
      'src.modules.news.infrastructure.report_repository'),
     ('src.api.repositories.news_repository', 'src.modules.news.infrastructure.news_repository'),
     ('src.api.routes.news', 'src.modules.news.api.router'),
     ('src.api.schemas.news', 'src.modules.news.api.schemas'),
     ('src.api.schemas.news_report', 'src.modules.news.api.report_schemas'),
     ('src.api.services.importance', 'src.modules.news.domain.importance'),
     ('src.api.services.news_cleanup_service', 'src.modules.news.application.cleanup_service'),
     ('src.api.services.news_graph_query_service',
      'src.modules.news.application.graph_query_service'),
     ('src.api.services.news_query_service', 'src.modules.news.application.query_service'),
     ('src.api.services.news_report_service', 'src.modules.news.application.report_service'),
     ('src.api.services.news_service', 'src.modules.news.application.ingest_service')],
)
def test_news_canonical_exports_origins_without_shims(legacy_name, canonical_name):
    import importlib
    from pathlib import Path

    canonical = importlib.import_module(canonical_name)
    backend = Path(__file__).resolve().parents[2]
    source_root = backend.parent / "ai/src" if canonical_name.startswith("agents.") else backend
    expected = source_root.joinpath(*canonical_name.split(".")).with_suffix(".py")
    removed = source_root.joinpath(*legacy_name.split(".")).with_suffix(".py")
    assert Path(canonical.__spec__.origin).resolve() == expected
    assert expected.is_file()
    assert not removed.exists()
    for name in CANONICAL_RELOCATED_EXPORTS[canonical_name]:
        value = getattr(canonical, name)
        if callable(value) and getattr(value, "__name__", None) == name:
            assert value.__module__ == canonical_name


@pytest.mark.parametrize(
    "legacy_name,canonical_name",
    [('src.api.repositories.agent_report_repository',
      'src.modules.reports.infrastructure.agent_report_repository'),
     ('src.api.routes.reports', 'src.modules.reports.api.router'),
     ('src.api.schemas.agent_report', 'src.modules.reports.api.report_schemas'),
     ('src.api.schemas.report_archive', 'src.modules.reports.api.archive_schemas')],
)
def test_reports_canonical_exports_origins_without_shims(legacy_name, canonical_name):
    import importlib
    from pathlib import Path

    canonical = importlib.import_module(canonical_name)
    backend = Path(__file__).resolve().parents[2]
    source_root = backend.parent / "ai/src" if canonical_name.startswith("agents.") else backend
    expected = source_root.joinpath(*canonical_name.split(".")).with_suffix(".py")
    removed = source_root.joinpath(*legacy_name.split(".")).with_suffix(".py")
    assert Path(canonical.__spec__.origin).resolve() == expected
    assert expected.is_file()
    assert not removed.exists()
    for name in CANONICAL_RELOCATED_EXPORTS[canonical_name]:
        value = getattr(canonical, name)
        if callable(value) and getattr(value, "__name__", None) == name:
            assert value.__module__ == canonical_name


@pytest.mark.parametrize(
    "legacy_name,canonical_name",
    [('src.api.auth.google', 'src.modules.auth.infrastructure.google_oidc'),
     ('src.api.routes.auth', 'src.modules.auth.api.router'),
     ('src.api.services.auth_service', 'src.modules.auth.application.session_service')],
)
def test_auth_canonical_exports_origins_without_shims(legacy_name, canonical_name):
    import importlib
    from pathlib import Path

    canonical = importlib.import_module(canonical_name)
    backend = Path(__file__).resolve().parents[2]
    source_root = backend.parent / "ai/src" if canonical_name.startswith("agents.") else backend
    expected = source_root.joinpath(*canonical_name.split(".")).with_suffix(".py")
    removed = source_root.joinpath(*legacy_name.split(".")).with_suffix(".py")
    assert Path(canonical.__spec__.origin).resolve() == expected
    assert expected.is_file()
    assert not removed.exists()
    for name in CANONICAL_RELOCATED_EXPORTS[canonical_name]:
        value = getattr(canonical, name)
        if callable(value) and getattr(value, "__name__", None) == name:
            assert value.__module__ == canonical_name


@pytest.mark.parametrize(
    "legacy_name,canonical_name",
    [('src.api.access_boundary', 'src.shared.http.access_boundary'),
     ('src.api.clients.ai_client', 'src.shared.infrastructure.clients.ai_client'),
     ('src.api.config', 'src.shared.config')],
)
def test_shared_canonical_exports_origins_without_shims(legacy_name, canonical_name):
    import importlib
    from pathlib import Path

    canonical = importlib.import_module(canonical_name)
    backend = Path(__file__).resolve().parents[2]
    source_root = backend.parent / "ai/src" if canonical_name.startswith("agents.") else backend
    expected = source_root.joinpath(*canonical_name.split(".")).with_suffix(".py")
    removed = source_root.joinpath(*legacy_name.split(".")).with_suffix(".py")
    assert Path(canonical.__spec__.origin).resolve() == expected
    assert expected.is_file()
    assert not removed.exists()
    for name in CANONICAL_RELOCATED_EXPORTS[canonical_name]:
        value = getattr(canonical, name)
        if callable(value) and getattr(value, "__name__", None) == name:
            assert value.__module__ == canonical_name


def test_relocated_settings_root_singleton_and_dependencies():
    from pathlib import Path
    from src.shared import config as canonical_config
    from src.api import main
    from db import session
    from src.modules.auth.api import router as auth_router

    backend = Path(__file__).resolve().parents[2]
    assert canonical_config._BACKEND_ROOT == backend
    assert canonical_config._ENV_FILE == backend / ".env"
    assert main.settings is canonical_config.settings
    assert auth_router.settings is canonical_config.settings
    assert session.settings is canonical_config.settings
    assert auth_router.get_session is session.get_session


def test_current_copied_python_consumers_have_no_removed_module_imports():
    import ast
    from pathlib import Path

    backend = Path(__file__).resolve().parents[2]
    removed = set()
    for feature in CANONICAL_RELOCATED_EXPORTS:
        # Deleted paths are explicit metadata in parametrized origin cases.
        assert feature.startswith(("src.modules.", "src.shared.", "src.agents.flow.", "agents.flow."))
    tree = ast.parse(Path(__file__).read_text())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.endswith("without_shims"):
            cases = node.decorator_list[0].args[1]
            for case in ast.literal_eval(cases):
                removed.add(case[0])
    assert len(removed) == 59  # Includes AI two; Flow service/repository use live globals below.
    removed.update({"src.api.services.flow_report_service", "src.api.repositories.flow_report_repository"})
    assert len(removed) == 61
    for source in sorted((backend / "src").rglob("*.py")) + sorted((backend / "db").rglob("*.py")) + [backend / "tests/fixtures/flow_payload.py"]:
        package = list(source.relative_to(backend).with_suffix("").parts[:-1])
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Import):
                assert all(alias.name not in removed for alias in node.names), source
            elif isinstance(node, ast.ImportFrom):
                base = ".".join(package[:len(package)-node.level+1] + (node.module.split(".") if node.module else [])) if node.level else node.module
                assert base not in removed, source
                assert all((base + "." + alias.name) not in removed for alias in node.names), source

@pytest.mark.parametrize('mutation',['path','schema','existing','enum'])
def test_cf012_projection_rejects_unapproved_delta(monkeypatch,mutation):
    values=public_contract_capture(monkeypatch)
    if mutation=='path':values['openapi']['paths']['/api/flow/unapproved']={}
    elif mutation=='schema':values['openapi']['components']['schemas']['Unapproved']={'type':'object'}
    elif mutation=='existing':values['openapi']['components']['schemas']['FlowAdmissionRequest']['properties']['question']['maxLength']=2001
    else:values['openapi']['components']['schemas']['ErrorCode']['enum'].append('UNAPPROVED')
    with pytest.raises(AssertionError):assert_public_contract_compatibility(values)

@pytest.mark.parametrize('change',['method','body','response','metadata','parameter','unknown_schema','consent','url'])
def test_cf054_public_projection_rejects_unknown_or_changed_wire(monkeypatch,change):
    values=copy.deepcopy(public_contract_capture(monkeypatch));api=values['openapi'];path='/api/supervisor/core/technical/requests'
    if change=='method':api['paths'][path]['delete']={}
    elif change=='body':api['paths'][path]['post']['requestBody']['content']['application/json']['schema']={'type':'object'}
    elif change=='response':api['paths'][path]['post']['responses']['200']['description']='changed'
    elif change=='metadata':api['paths'][path]['post']['operationId']='changed'
    elif change=='parameter':api['paths'][path]['post']['parameters']=[{'name':'owner','in':'query'}]
    elif change=='unknown_schema':api['components']['schemas']['UnapprovedTechnical']={'type':'object'}
    elif change=='consent':api['components']['schemas']['TechnicalConsent']['properties']['allow_flow']={'type':'boolean'}
    else:api['components']['schemas']['TechnicalReference']['properties']['report_url']={'type':'string'}
    with pytest.raises(AssertionError):assert_public_contract_compatibility(values)
