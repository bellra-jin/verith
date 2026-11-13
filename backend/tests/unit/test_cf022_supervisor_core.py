"""One focused protected collection. Pure semantics/ASGI/SQL definitions, no real DB."""
import asyncio,copy,hashlib,importlib.abc,json,sys,ast
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4
from unittest.mock import AsyncMock,patch
import httpx,pytest
from scripts.cf022_supervisor_core_check import load_core
ROOT=Path(__file__).resolve().parents[3]
ATTEMPTS=[]
class ImportBoundary(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname in {'src.api.dependencies','src.supervisor.config','src.agents.flow.config','openai','langchain_openai','redis','langgraph'} or fullname.startswith(('src.agents.technical','src.agents.news','src.agents.fundamental','src.supervisor.application.execution','src.supervisor.application.planning.rewrite','src.supervisor.domain.planning.fallback','src.agents.flow.application.agent')):
            ATTEMPTS.append(fullname);raise AssertionError('Forbidden core import')
IMPORT_GUARD=ImportBoundary();sys.meta_path.insert(0,IMPORT_GUARD);APP=load_core();M=sys.modules['src.supervisor.domain.meaning'];P=sys.modules['src.supervisor.application.planning.core_planner'];S=sys.modules['src.supervisor.application.meaning_service']
from src.modules.supervisor.domain import contracts as B
from src.modules.supervisor.domain.flow_projection import confirmed_plan,outcome,flow_body
from src.shared.infrastructure.clients.ai_client import AIClient,AIUnavailableError,AIContractError
TOKEN='cf022-synthetic-service-token-at-least32';SENTINEL='cf022-private-sentinel'
@pytest.fixture(autouse=True)
def env(monkeypatch):monkeypatch.setenv('FLOW_ANALYSIS_ENABLED','true');monkeypatch.setenv('FLOW_SERVICE_TOKEN',TOKEN)
def draft(query='삼성전자 수급',**kw):return M.Draft(original_query=query,answers=[],revision=0,**kw)
def resolution():return sys.modules['src.supervisor.domain.core_contracts'].Resolution(status='resolved',reason='exact_match',stock=dict(stock_code='005930',stock_name='삼성전자',market='KOSPI'),candidates=[])
async def prepared(d=None):
    d=d or draft();start=await P.start(d);assert start.action=='resolve_stock';return P.continuation(d,start.frame,resolution()).plan
FIXTURE=json.loads((ROOT/'frontend/tests/fixtures/cf022-supervisor-core.json').read_text())
@pytest.mark.parametrize('case',FIXTURE['cases'])
def test_explicit_meaning_preserves_conditions_negation_and_scope(case):
    value=draft(case['query']);frame=S.deterministic(value)
    B.MeaningFrame.model_validate(frame.model_dump(mode='json'))
    if 'views' in case:assert frame.requested_views==case['views']
    if 'slot' in case:assert case['slot'] in frame.unresolved_slots
    if 'condition_kind' in case:assert any(c.kind==case['condition_kind'] and c.disposition=='unsupported' for c in frame.conditions)
    assert frame.original_query==case['query'] and not ATTEMPTS
@pytest.mark.parametrize('query',['삼성전자 2023년 수급','삼성전자 어제 수급','삼성전자 지난3년 수급'])
async def test_unsupported_time_cannot_be_full_coverage(query):
    plan=await prepared(draft(query));assert plan.partial and plan.status=='scope_confirmation' and plan.required_waivers
    with pytest.raises(B.CoreInvalid):confirmed_plan(B.Plan.model_validate(plan.model_dump(mode='json')),B.Consent(allow_flow=True,allow_partial=False,waived_conditions=[]))
@pytest.mark.parametrize('mutation',['mention_removed','multi_slot_removed','span','condition_removed','canonical_injection'])
async def test_fake_model_cannot_drop_important_evidence_or_invent_canonical(mutation):
    d=draft('삼성전자와 SK하이닉스 어제 수급');frame=S.deterministic(d);v=frame.model_dump(mode='json');v['interpretation_source']='model_assisted'
    if mutation=='mention_removed':v['mentions']=v['mentions'][:1];v['unresolved_slots']=[]
    elif mutation=='multi_slot_removed':v['unresolved_slots']=[]
    elif mutation=='span':v['mentions'][0]['evidence']['text']=SENTINEL
    elif mutation=='condition_removed':v['conditions']=[]
    else:v['canonical_stock']={'stock_code':'005930'}
    gateway=NS(extract=AsyncMock(return_value=v));result=await S.understand(d,gateway)
    assert result.interpretation_source=='unavailable' and 'multi_stock' in result.unresolved_slots and len(result.mentions)==2;gateway.extract.assert_awaited_once()
async def test_bounded_clarification_answer_source_and_model_gateway_unavailable():
    d=draft('주식 정보');f=await S.understand(d);assert f.unresolved_slots and f.interpretation_source=='unavailable'
    answer=dict(answer_id=str(uuid4()),slot='stock',value='005930');d=M.Draft(original_query='수급이 궁금해',answers=[answer],revision=1);f=S.deterministic(d);assert f.mentions[0].evidence.source_kind=='clarification_answer' and f.mentions[0].evidence.answer_id==answer['answer_id']
    assert (await P.start(d)).action=='resolve_stock'
@pytest.mark.parametrize('bad',[{'revision':5},{'owner':'fake'},{'answers':[{'answer_id':str(uuid4()),'slot':'provider','value':'x'}]},{'original_query':True}])
def test_strict_draft_rejects_coercion_and_unknown_slots(bad):
    with pytest.raises(ValueError):M.Draft.model_validate(dict(original_query='수급',answers=[],revision=0)|bad)
async def test_actual_core_client_ASGI_start_continue_preserves_ids_and_raw_query():
    d=draft('  삼성전자 외국인 수급과 차트  ');rid=str(uuid4());trace=str(uuid4());client=AIClient('http://synthetic.invalid',8,transport=httpx.ASGITransport(app=APP),service_token=TOKEN)
    request=dict(schema_version=M.VERSION,request_id=rid,trace_id=trace,data=dict(phase='start',draft=d.model_dump(mode='json')),error=None)
    first=await client.plan_supervisor_core(request);assert first['request_id']==rid and first['trace_id']==trace and first['data']['action']=='resolve_stock'
    assert first['data']['lookup']=='삼성전자'
    cont=copy.deepcopy(request);cont['data'].update(phase='continue',frame=first['data']['frame'],resolution=resolution().model_dump(mode='json'));last=await client.plan_supervisor_core(cont);plan=last['data']['plan'];assert plan['frame']['original_query']==d.original_query and plan['partial'] and plan['selected_views']==['flow'];B.validate_plan(plan,B.Draft.model_validate(d.model_dump(mode='json')))
async def test_prepare_confirm_GET_projection_retains_original_and_explicit_effective_waivers():
    plan=await prepared(draft('삼성전자 어제 외국인 수급과 차트'));b=B.Plan.model_validate(plan.model_dump(mode='json'));consent=B.Consent(allow_flow=True,allow_partial=True,waived_conditions=b.required_waivers);saved=confirmed_plan(b,consent)
    binding=NS(id=uuid4(),redacted_at=None,plan_json=B.canonical(saved));view=NS(state='stored',model_dump=lambda **kw:dict(analysis_id=str(uuid4()),admission_request_id=str(uuid4()),attempt_id=str(uuid4()),state='stored',deadline_at='2026-11-09T00:00:00Z',report_id=None,report_url=None,error=None))
    result=outcome(binding,view);assert result['coverage']=='partial' and result['effective_scope']['waived_conditions']==b.required_waivers and result['plan']['frame']['conditions'][0]['disposition']=='unsupported'
    assert result['views'][1]['state']=='not_executed';binding.redacted_at=object();deleted=outcome(binding,view);assert deleted['plan'] is None and deleted['effective_scope'] is None and deleted['flow'] is None
@pytest.mark.parametrize('status',[301,401,403,422,500,502])
async def test_core_client_fixed_errors_and_no_redirect(status):
    seen=[]
    async def send(req):seen.append(req);return httpx.Response(status,json={'private':SENTINEL},headers={'location':'https://untrusted.invalid'})
    c=AIClient('http://synthetic.invalid',8,httpx.MockTransport(send),service_token=TOKEN)
    with pytest.raises(AIUnavailableError) as e:await c.plan_supervisor_core({'safe':True})
    assert len(seen)==1 and SENTINEL not in str(e.value)
async def test_AI_gate_auth_body_bound_and_legacy_closed():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),base_url='http://synthetic.invalid') as c:
        assert (await c.post('/internal/supervisor/analyze',json={'query':SENTINEL})).status_code==403
        assert (await c.post('/internal/supervisor/core/plan',content=b'bad')).status_code==401
        h={'content-type':'application/json','x-flow-service-token':TOKEN}
        assert (await c.post('/internal/supervisor/core/plan',content=b'x'*16385,headers=h)).status_code==422
        assert (await c.post('/internal/supervisor/core/plan',content=b'{"x":1,"x":2}',headers=h)).status_code==422
async def test_stream_overflow_stops_early():
    seen=[]
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):seen.append(1);yield b'x'*65537;seen.append(2);yield b'never'
    c=AIClient('http://synthetic.invalid',8,httpx.MockTransport(lambda req:httpx.Response(200,stream=Stream())),service_token=TOKEN)
    with pytest.raises(AIContractError):await c.plan_supervisor_core({'safe':True})
    assert seen==[1]
def test_public_contract_baseline_and_negative_projections(monkeypatch):
    assert not ATTEMPTS;sys.meta_path.remove(IMPORT_GUARD)
    try:
        from tests.unit.test_flow_contract import test_relocation_public_contract_baseline,test_cf003_snapshot_projection_rejects_unapproved_changes
        test_relocation_public_contract_baseline(monkeypatch)
        for key in ('path','component'):test_cf003_snapshot_projection_rejects_unapproved_changes(monkeypatch,key)
    finally:sys.meta_path.insert(0,IMPORT_GUARD)
def test_single_binding_model_and_original_coordinator_usage_source_boundaries():
    tree=ast.parse((ROOT/'backend/db/models/supervisor/request_binding.py').read_text());assert sum(isinstance(n,ast.ClassDef) for n in tree.body)==1
    service=(ROOT/'backend/src/modules/supervisor/application/service.py').read_text();assert 'Unknown commit ACK exits without Flow' in service and 'AnalysisService(self.session' in service
    projection=(ROOT/'backend/src/modules/supervisor/domain/flow_projection.py').read_text();assert "question=plan.frame.original_query" in projection
    migration=(ROOT/'backend/db/migrations/versions/20261109_c22001a7e0001_supervisor_binding.py').read_text();assert "down_revision='c18001a7e0001'" in migration and 'cf022_binding_guard' in migration

async def test_observation_cancel_rolls_back_and_does_not_map_to_service_error():
    from src.modules.supervisor.application.service import SupervisorService
    session=NS(rollback=AsyncMock())
    service=SupervisorService(session,principal=NS(user_id=uuid4()),client=NS())
    service.auth=AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):await service.get(uuid4())
    service.auth.assert_awaited_once();assert session.rollback.await_count==2

@pytest.mark.parametrize('query',['삼성전자 최근 3주 수급','삼성전자 오늘 수급','삼성전자 최근 두달 수급'])
async def test_all_explicit_time_clues_are_preserved_as_unsupported(query):
    plan=await prepared(draft(query))
    assert plan.partial and plan.required_waivers and any(c.kind in {'period','cutoff'} for c in plan.frame.conditions)

async def test_clarification_view_negation_remains_excluded():
    d=M.Draft(original_query='삼성전자 주식 정보',answers=[dict(answer_id=str(uuid4()),slot='views',value='수급 말고 차트')],revision=1)
    frame=S.deterministic(d);assert frame.requested_views==['technical'] and frame.negated_views==['flow']
    result=await P.start(d);assert result.action=='final' and result.plan.status=='unsupported' and not result.plan.selected_views

@pytest.mark.parametrize('query',['삼성전자와 SK하이닉스 수급','시장 전체 수급'])
async def test_single_stock_typed_answer_finishes_clarification_without_dropping_original_scope(query):
    d=M.Draft(original_query=query,answers=[dict(answer_id=str(uuid4()),slot='stock',value='삼성전자')],revision=1)
    first=await P.start(d);assert first.action=='resolve_stock' and first.lookup=='삼성전자'
    plan=P.continuation(d,first.frame,resolution()).plan
    assert plan.frame.original_query==query and not plan.frame.unresolved_slots
    if '시장' in query:assert plan.partial and plan.required_waivers


def test_missing_creation_receipt_is_not_reported_as_confirmed_cleanup(monkeypatch):
    import os,tempfile
    from unittest.mock import Mock
    from scripts import cf002_interactive_login as runner
    from scripts.runner_owned_database import OwnedDatabaseError
    records=[]
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as home:
        docker=NS(_config=NS(name=home),close=Mock())
        owner=NS(receipt=None,resource_id='synthetic-owned-name',metadata_failures=[],cleanup_receipt_path=None,create=Mock(side_effect=OwnedDatabaseError()),cleanup=Mock())
        with patch.object(runner,'LocalDocker',return_value=docker),patch.object(runner,'OwnedPostgres',return_value=owner),patch.object(runner,'safe_print',side_effect=records.append),patch.object(sys,'argv',['cf002','--verify-supervisor-core-db']):
            with pytest.raises(SystemExit) as e:runner.main()
        assert e.value.code==2 and any(x['phase']=='owned_db_cleanup_unverified' for x in records)
        assert not any(x['phase']=='owned_db_removed' for x in records)
        owner.cleanup.assert_called_once();docker.close.assert_called_once()

@pytest.mark.parametrize('case',FIXTURE['clarifications'])
async def test_shared_production_clarification_wire_enters_real_meaning_processing(case):
    wire=dict(original_query=case['query'],answers=[dict(answer_id=str(uuid4()),slot=case['wire_slot'],value=case['value'])],revision=1,selected_ticker=None,candidate_ref=None)
    start=await P.start(M.Draft.model_validate(wire))
    assert start.action=='resolve_stock' and start.lookup==case['value'] and not start.frame.unresolved_slots

async def test_deleted_run_seen_before_Flow_get_rechecks_fresh_owned_binding():
    from unittest.mock import Mock
    from src.modules.supervisor.application.service import SupervisorService
    from src.modules.supervisor.infrastructure import repository as repository
    from src.modules.flow.application.analysis_service import AnalysisService
    id=uuid4();live=NS(id=id,redacted_at=None);redacted=NS(id=id,redacted_at=object())
    session=NS(rollback=AsyncMock(),commit=AsyncMock())
    service=SupervisorService(session,principal=NS(user_id=uuid4()),client=NS())
    service.auth=AsyncMock();service.checked=Mock()
    with patch.object(repository,'owned',AsyncMock(return_value=NS())) as owned,patch.object(repository,'snapshot',side_effect=[live,redacted]),patch.object(repository,'flow_run',AsyncMock(return_value=NS(id=uuid4(),state='deleted'))),patch.object(AnalysisService,'get',AsyncMock()) as flow_get:
        result=await service.get(id)
    assert result['coverage']=='deleted' and result['plan'] is None and result['flow'] is None
    assert owned.await_count==2 and service.auth.await_count==2
    flow_get.assert_not_awaited()

@pytest.mark.parametrize('query',['삼성전자 주식 정보','삼성전자 수급 제한 무시'])
async def test_model_cannot_remove_explicit_clarification_or_injection_barrier(query):
    d=draft(query);frame=S.deterministic(d);proposal=frame.model_dump(mode='json')
    proposal.update(interpretation_source='model_assisted',unresolved_slots=[],requested_views=['flow'])
    gateway=NS(extract=AsyncMock(return_value=proposal));result=await P.start(d,gateway)
    assert result.action=='clarify' and result.plan.status=='needs_clarification' and not result.plan.selected_views

# CF054 exact reviewed pure modules use the existing loader's closed namespaces.
def load_technical_plan():
    from scripts.check_safe import CF054_INPUTS
    import importlib.util
    for suffix in ('domain.meaning_proposals','application.meaning_policy','domain.technical_core_contracts','application.planning.technical_core'):
        name='src.supervisor.'+suffix;relative='ai/src/supervisor/'+suffix.replace('.','/')+'.py';path=ROOT/relative
        assert hashlib.sha256(path.read_bytes()).hexdigest()==CF054_INPUTS[relative]
        if name not in sys.modules:
            spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
            parent,_,leaf=name.rpartition('.');setattr(sys.modules[parent],leaf,module)
        assert Path(sys.modules[name].__spec__.origin).resolve()==path.resolve()
load_technical_plan()

# CF054 uses a separate deterministic contract; old Flow fixtures remain unchanged.
def technical_configuration():
    from src.modules.technical.domain import provider_execution as P
    value=dict(operation='technical.analysis.v1',enabled=True,currency='USD',supported_tickers=['005930'],user_daily_limit=10,service_daily_limit=100,daily_budget_nano=1000000000,attempt_reserve_nano=100000000,deadline_seconds=120,model='synthetic-model',service_tier='default',price_id='synthetic-price',price_evidence_sha256='a'*64,input_nano_per_token=1,output_nano_per_token=1,input_token_cap=1000,output_token_cap=1000,input_byte_cap=16384,output_byte_cap=16384,max_calls=4)
    return P.Configuration(P.canonical(dict(schema_version='technical.execution.v1',policy=value,counter={'free':True,'mapping':'technical.responses.model-input.v1','version':'synthetic-count-v1','provenance_sha256':'b'*64,'evidence_sha256':'c'*64},caps={'request':65536,'count':8192,'generation':65536},ai_origin='https://ai.synthetic.invalid',authority_origin='https://backend.synthetic.invalid',cache_mode='none',trace_mode='none')))

def technical_context(cfg=None):
    from src.modules.supervisor.application.technical_service import TechnicalSupervisorService
    return TechnicalSupervisorService.context(cfg or technical_configuration())

def technical_plan(query='삼성전자 차트',*,answers=None,revision=0,resolved=None):
    from src.supervisor.domain import technical_core_contracts as C
    from src.supervisor.application.planning.technical_core import run
    data=C.InternalInput(phase='start',draft=M.Draft(original_query=query,answers=answers or [],revision=revision),context=C.Context.model_validate(technical_context().model_dump(mode='json')))
    first=run(data)
    if first.action!='resolve_stock':return data,first
    return data,run(C.InternalInput(phase='continue',draft=data.draft,context=data.context,frame=first.frame,resolution=resolved or resolution()))

@pytest.mark.parametrize('query',['삼성전자 차트','005930 차트','삼성전자 최근 3주 차트','삼성전자 외국인 제외 차트','삼성전자 5분봉 차트'])
def test_cf054_deterministic_single_view_conditions_and_fixed_support(query):
    from src.modules.supervisor.domain import technical_core_contracts as C
    from src.modules.supervisor.domain.technical_projection import confirmed_plan,intent_for
    value,last=technical_plan(query);plan=C.validate_plan(last.plan.model_dump(mode='json'),B.Draft.model_validate(value.draft.model_dump(mode='json')),technical_context())
    assert plan.selected_views==['technical'] and plan.support.periods==['3m','1y','5y']
    assert plan.support.cutoff=='unverified' and plan.support.source_as_of is None and plan.support.intraday=='unavailable'
    assert all(c.disposition!='honored' for c in plan.frame.conditions)
    saved=confirmed_plan(plan,C.Consent(allow_technical=True,allow_partial=plan.partial,waived_conditions=list(plan.required_waivers)))
    assert saved['effective_scope']['waived_conditions']==plan.required_waivers
    assert plan.frame.original_query==query and intent_for(plan).data()['original_query']==plan.execution_query=='005930 차트'
    assert saved['effective_scope']['execution_query']==plan.execution_query
    assert intent_for(plan).data()['conditions']=={'profile':'technical.multiframe.v1','periods':['3m','1y','5y']}
    assert plan.frame.interpretation_source=='deterministic' and not ATTEMPTS

@pytest.mark.parametrize('query',['삼성전자 수급과 차트','삼성전자 차트 말고 수급','삼성전자와 SK하이닉스 차트','시장 전체 차트','삼성전자 이익 두배 차트','현대건설 차트','삼성전자 주식 정보'])
def test_cf054_no_mixed_negative_residual_multi_or_unknown_name_promotion(query):
    _,last=technical_plan(query)
    assert last.plan.selected_views==[] and last.plan.status in {'needs_clarification','unsupported'}

def test_cf054_typed_stock_answer_and_exact_answer_source():
    answer=dict(answer_id=str(uuid4()),slot='stock',value='현대건설')
    data,last=technical_plan('차트',answers=[answer],revision=1)
    assert data.draft.answers[0].answer_id==answer['answer_id']
    assert last.plan.frame.mentions[0].evidence.answer_id==answer['answer_id']
    assert last.plan.selected_views==['technical']

@pytest.mark.parametrize('change',['waiver_missing','waiver_extra','partial_false','allow_flow','owner','preparation_id','context','plan_hash','selected_view'])
def test_cf054_consent_and_plan_shape_cannot_bypass_scope(change):
    from src.modules.supervisor.domain import technical_core_contracts as C
    from src.modules.supervisor.domain.technical_projection import confirmed_plan
    data,last=technical_plan('삼성전자 최근 3주 차트');plan=C.Plan.model_validate(last.plan.model_dump(mode='json'))
    consent=dict(allow_technical=True,allow_partial=True,waived_conditions=list(plan.required_waivers))
    if change=='waiver_missing':consent['waived_conditions']=[]
    if change=='waiver_extra':consent['waived_conditions']+=['invented']
    if change=='partial_false':consent['allow_partial']=False
    if change=='allow_flow':consent['allow_flow']=consent.pop('allow_technical')
    if change in {'owner','preparation_id'}:
        body=dict(client_key=str(uuid4()),draft=data.draft.model_dump(mode='json'),expected_plan_hash=plan.plan_hash,consent=consent);body[change]=str(uuid4())
        with pytest.raises(ValueError):C.Confirm.model_validate(body)
    elif change in {'context','plan_hash','selected_view'}:
        body=plan.model_dump(mode='json')
        if change=='context':body['context']['configuration_sha256']='f'*64
        elif change=='plan_hash':body['plan_hash']='f'*64
        else:body['selected_views']=['flow']
        with pytest.raises(ValueError):C.Plan.model_validate(body)
    else:
        with pytest.raises(ValueError):confirmed_plan(plan,C.Consent.model_validate(consent))

async def test_cf054_actual_AI_route_and_client_no_meaning_or_execution():
    from fastapi import FastAPI
    from src.supervisor.api.routes import make_router
    from src.modules.supervisor.application.technical_service import TechnicalSupervisorService
    cfg=technical_configuration();calls=[]
    app=FastAPI();app.include_router(make_router(technical=True));app.state.technical_execution_runtime=NS(service_token=TOKEN.encode(),readiness=lambda:{'ready':True,'configuration':cfg.data(),'spec_sha256':cfg.data() and technical_context(cfg).spec_sha256})
    async def send(request):calls.append(request.url.path);return await httpx.ASGITransport(app=app).handle_async_request(request)
    # The actual client accepts only an explicit ASGI transport for this opt-in path.
    client=AIClient('https://ai.synthetic.invalid',15,transport=httpx.ASGITransport(app=app),execution_token=TOKEN)
    d=B.Draft(original_query='삼성전자 차트',answers=[],revision=0)
    wire=dict(schema_version='supervisor.technical.v1',request_id=str(uuid4()),trace_id=str(uuid4()),data={'phase':'start','draft':d.model_dump(mode='json'),'context':TechnicalSupervisorService.context(cfg).model_dump(mode='json')},error=None)
    result=await client.plan_supervisor_technical(wire,cfg,remaining=15)
    assert result['data']['action']=='resolve_stock' and result['data']['lookup']=='삼성전자'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://ai.synthetic.invalid') as c:
        assert (await c.post('/internal/supervisor/core/technical-plan',content=b'bad')).status_code==401
        changed=copy.deepcopy(wire);changed['data']['context']['configuration_sha256']='f'*64
        assert (await c.post('/internal/supervisor/core/technical-plan',json=changed,headers={'x-technical-service-token':TOKEN})).status_code==422
        app.state.technical_execution_runtime=None
        assert (await c.post('/internal/supervisor/core/technical-plan',json=wire,headers={'x-technical-service-token':TOKEN})).status_code==403
    assert not ATTEMPTS

@pytest.mark.parametrize('negative_status',['resolved','not_found','ambiguous'])
async def test_cf054_negated_alias_requires_fresh_distinct_canonical_stock(monkeypatch,negative_status):
    from src.modules.supervisor.application import technical_service as T
    cfg=technical_configuration();cfg_data=cfg.data();cfg_data['policy']['supported_tickers']=['066570']
    from src.modules.technical.domain import provider_execution as P
    cfg=P.Configuration.parse(cfg_data)
    from fastapi import FastAPI
    app=FastAPI();app.include_router(sys.modules['src.supervisor.api.routes'].make_router(technical=True));app.state.technical_execution_runtime=NS(service_token=TOKEN.encode(),readiness=lambda:{'ready':True,'configuration':cfg.data(),'spec_sha256':P.SPEC_SHA256})
    positive=B.Resolution(status='resolved',reason='exact_match',stock=dict(stock_code='066570',stock_name='LG전자',market='KOSPI'),candidates=[])
    negative=positive if negative_status=='resolved' else B.Resolution(status=negative_status,reason='no_match' if negative_status=='not_found' else 'ambiguous_alias',stock=None,candidates=[])
    looked=[]
    async def resolve(value):looked.append(value);return positive if value=='066570' else negative
    session=NS(rollback=AsyncMock(),commit=AsyncMock())
    monkeypatch.setattr(T,'validate_principal',AsyncMock())
    service=T.TechnicalSupervisorService(session,principal=NS(),client=AIClient(cfg.data()['ai_origin'],15,transport=httpx.ASGITransport(app=app),execution_token=TOKEN),configuration=cfg,resolver_factory=lambda s:NS(resolve=resolve))
    value=B.Draft(original_query='엘지전자 말고 066570 차트',answers=[],revision=0)
    with pytest.raises(T.CoreError) as error:await service.prepare(value,uuid4(),deadline=asyncio.get_running_loop().time()+15)
    assert error.value.code=='INPUT_INVALID' and error.value.status==422 and looked==['066570','엘지전자']

def test_cf054_normal_main_selects_technical_router_but_flow_factory_default_is_unchanged():
    # Execute only the two reviewed pure composition nodes; no main/other AI imports.
    from fastapi import FastAPI
    from scripts.check_safe import CF054_INPUTS
    source=ROOT/'ai/src/main.py';assert hashlib.sha256(source.read_bytes()).hexdigest()==CF054_INPUTS['ai/src/main.py']
    tree=ast.parse(source.read_text())
    assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='supervisor_router' for t in n.targets))
    call=assignment.value
    assert isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='make_supervisor_router' and not call.args
    assert [k.arg for k in call.keywords]==['runtime'] and isinstance(call.keywords[0].value,ast.Lambda)
    mount=next(n for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id=='supervisor_router' and n.value.func.attr=='include_router')
    assert ast.unparse(mount)=='supervisor_router.include_router(make_technical_core_router())'
    routes=sys.modules['src.supervisor.api.routes'];scope={'make_supervisor_router':routes.make_router,'make_technical_core_router':routes.make_technical_core_router,'supervisor_meaning_runtime':None}
    exec(compile(ast.Module(body=[assignment,mount],type_ignores=[]),'<reviewed main composition>','exec'),scope)
    app=FastAPI();app.include_router(scope['supervisor_router'])
    assert '/internal/supervisor/core/technical-plan' in app.openapi()['paths']
    other=FastAPI();other.include_router(routes.make_router())
    assert '/internal/supervisor/core/technical-plan' not in other.openapi()['paths'] and not ATTEMPTS

@pytest.mark.parametrize('change',['method','body','response','metadata','parameter','unknown_schema','consent','url'])
def test_cf054_public_wire_negative_cases_are_in_the_protected_core_collection(monkeypatch,change):
    sys.meta_path.remove(IMPORT_GUARD)
    try:
        from tests.unit.test_flow_contract import test_cf054_public_projection_rejects_unknown_or_changed_wire
        test_cf054_public_projection_rejects_unknown_or_changed_wire(monkeypatch,change)
    finally:sys.meta_path.insert(0,IMPORT_GUARD)


# Fixed composition observation has no provider/SQL authority.
@pytest.mark.parametrize('first,second,closed,expected',[
 ('stored','stored',True,'fulfilled'),('stored','unknown',True,'partial'),
 ('stored','failed',True,'partial'),('stored','result_ready',True,'partial'),
 ('unknown','failed',True,'unknown'),('result_ready','failed',True,'pending'),
 ('failed','not_started',True,'unfulfilled'),('failed','not_started',False,'pending'),
 ('deleted','deleted',True,'deleted'),('stored','deleted',True,'partial')])
def test_composition_coverage_preserves_each_child_state(first,second,closed,expected):
    from src.modules.supervisor.domain.composition import ChildObservation,coverage
    def observed(view,state):return ChildObservation(view,state,state!='not_started',state not in {'not_started','unknown'})
    values=(observed('flow',first),observed('technical',second))
    assert coverage(values,dispatch_closed=closed)==expected
    assert (values[0].state,values[1].state)==(first,second)


def test_composition_fixed_keys_are_view_scoped_and_observation_is_strict():
    from uuid import UUID
    from src.modules.supervisor.domain.composition import fixed_child_key,ChildObservation,coverage,CompositionInvalid
    id=UUID('00000000-0000-0000-0000-000000000001')
    assert fixed_child_key(id,'flow',b'x'*32)==fixed_child_key(id,'flow',b'x'*32)
    assert fixed_child_key(id,'flow',b'x'*32)!=fixed_child_key(id,'technical',b'x'*32)
    for args in [('flow','stored',False,True),('flow','stored',True,False),('flow','not_started',True,False),('flow',[],True,False),('news','failed',True,True),('flow','unknown',1,True)]:
        with pytest.raises(CompositionInvalid):ChildObservation(*args)
    child=ChildObservation('flow','unknown',True,False)
    for values,closed in [([],True),((child,child),True),((child,),1)]:
        with pytest.raises(CompositionInvalid):coverage(values,dispatch_closed=closed)
    for value in ('news',None,[]):
        with pytest.raises(CompositionInvalid):fixed_child_key(id,value,b'x'*32)


def test_composition_child_keys_do_not_follow_public_parent_id_alone():
    from uuid import UUID
    from src.modules.supervisor.domain.composition import fixed_child_key,CompositionInvalid
    id=UUID(int=123)
    assert fixed_child_key(id,'flow',b'x'*32)!=fixed_child_key(id,'flow',b'y'*32)
    for seed in (None,b'',b'x'*31,'x'*32):
        with pytest.raises(CompositionInvalid):fixed_child_key(id,'flow',seed)


def composition_snapshot(query='삼성전자 수급과 차트',*,projected=False):
    from src.modules.supervisor.domain.composition import CompositionSnapshot,VERSION
    value=draft(query);frame=S.deterministic(value).model_dump(mode='json');views=[v for v in ('flow','technical') if v in frame['requested_views']]
    saved=dict(schema_version=VERSION,draft=value.model_dump(mode='json'),
        frame=frame,stock=resolution().stock.model_dump(mode='json'),selected_views=views,
        consent=dict(allow_views=views,allow_partial_results=len(views)==2,waived_conditions=[]),
        flow_policy=dict(supported_tickers=['005930'],user_limit=10,service_limit=100,budget=10000000000) if 'flow' in views else None,
        technical_configuration=technical_configuration().text if 'technical' in views else None)
    if projected:
        from src.modules.supervisor.domain.composition import PROJECTED_VERSION,projected_inputs
        saved.update(schema_version=PROJECTED_VERSION,child_inputs=projected_inputs(saved['stock'],query,views))
    return CompositionSnapshot(B.canonical(saved))


@pytest.mark.parametrize('query',['삼성전자 수급','삼성전자 차트','삼성전자 수급과 차트'])
def test_composition_snapshot_preserves_full_scope_and_policies(query):
    from src.modules.supervisor.application.composition_service import CompositionService
    saved=composition_snapshot(query);data=saved.data()
    assert data['draft']['original_query']==data['frame']['original_query']==query
    assert saved.text not in repr(saved)
    if 'technical' in data['selected_views']:
        assert CompositionService.technical_intent(saved).data()['original_query']==query
    data['consent']['allow_views']=[]
    assert saved.data()['consent']['allow_views']


@pytest.mark.parametrize('change',['consent','condition','unknown','ticker','disabled','clock','flow_budget','bool_limit','noncanonical'])
def test_composition_rejects_unresolved_or_unapproved_scope(change):
    from src.modules.supervisor.domain.composition import CompositionSnapshot,CompositionInvalid
    value=composition_snapshot().data()
    if change=='consent':value['consent']['allow_partial_results']=False
    if change=='condition':value['frame']=S.deterministic(draft('삼성전자 어제 수급과 차트')).model_dump(mode='json')
    if change=='unknown':value['frame']['unresolved_slots']=['meaning']
    if change=='ticker':value['stock']['stock_code']='000720'
    if change in {'disabled','clock'}:
        cfg=json.loads(value['technical_configuration']);cfg['policy']['enabled' if change=='disabled' else 'deadline_seconds']=False if change=='disabled' else 126
        value['technical_configuration']=B.canonical(cfg)
    if change=='flow_budget':value['flow_policy']['budget']=1
    if change=='bool_limit':value['flow_policy']['user_limit']=True
    text=B.canonical(value)
    if change=='noncanonical':text+=' '
    with pytest.raises(CompositionInvalid):CompositionSnapshot(text)


def composition_service_fixture(monkeypatch):
    from datetime import UTC,datetime,timedelta
    from src.modules.supervisor.application import composition_service as C
    now=datetime(2026,11,13,tzinfo=UTC);clock=NS(now=now,mono=100.0);rows={}
    principal=C.Principal(uuid4(),uuid4(),now+timedelta(days=1),b'a'*32)
    session=NS(new=set(),dirty=set(),deleted=set(),rollback=AsyncMock(),commit=AsyncMock())
    monkeypatch.setattr(C,'validate_principal',AsyncMock())
    monkeypatch.setattr(C.time,'monotonic',lambda:clock.mono)
    async def read(s,owner,*,id=None,key=None,lock=False):
        return next((r for r in rows.values() if r.owner_user_id==owner and (r.id==id if id else r.client_key_digest==key)),None)
    async def admit(s,values):
        row=NS(**dict(analysis_as_of=None,claimed_at=None,closed_at=None,flow_handoff_at=None,technical_handoff_at=None,flow_run_id=None,technical_run_id=None)|values);rows[row.id]=row;return row
    async def change(s,row,values):
        result=NS(**(vars(row)|values));rows[row.id]=result;return result
    monkeypatch.setattr(C.repo,'read',read);monkeypatch.setattr(C.repo,'admit',admit);monkeypatch.setattr(C.repo,'change',change)
    monkeypatch.setattr(C.repo,'clock',AsyncMock(side_effect=lambda s:clock.now))
    monkeypatch.setattr(C.repo,'stock',AsyncMock(return_value=resolution().stock))
    monkeypatch.setattr(C.repo,'native',AsyncMock(return_value=None))
    service=C.CompositionService(session,principal=principal,resolver_factory=lambda s:NS(resolve=AsyncMock(return_value=resolution())))
    return C,service,session,clock,rows


async def test_composition_replay_no_authority_A2_observation_and_close_fence(monkeypatch):
    from dataclasses import replace
    C,service,session,clock,rows=composition_service_fixture(monkeypatch)
    saved=composition_snapshot('삼성전자 수급');key=str(uuid4())
    first=await service.admit(key,saved,request_started_at=clock.now)
    replay=await service.admit(key,saved,request_started_at=clock.now)
    assert first.newly_admitted and not replay.newly_admitted and replay.token is None
    with pytest.raises(C.CompositionError):await service.start(replay)
    right=await service.start(first);assert right.newly_started
    assert not (await service.start(first)).newly_started
    await service.handoff(right,'flow')
    a2=C.CompositionService(session,principal=replace(service.principal,session_id=uuid4()))
    assert (await a2.get(first.id))['coverage']=='unknown'
    with pytest.raises(C.CompositionError):a2.take_handoff(right,'flow')
    # close must invalidate the ticket before its first await, including races.
    reached=asyncio.Event();release=asyncio.Event();normal=service._begin
    async def wait_begin(**kw):reached.set();await release.wait();await normal(**kw)
    monkeypatch.setattr(service,'_begin',wait_begin)
    task=asyncio.create_task(service.close(right));await reached.wait()
    with pytest.raises(C.CompositionError):service.take_handoff(right,'flow')
    release.set();await task
    with pytest.raises(C.CompositionError):service.take_handoff(right,'flow')
    assert rows[first.id].state=='closed'
    assert C.repo.native.await_count==1  # GET only; no native POST/execution exists.


@pytest.mark.parametrize('phase',['start','handoff'])
async def test_composition_delayed_commit_ACK_never_returns_execution_ticket(monkeypatch,phase):
    C,service,session,clock,rows=composition_service_fixture(monkeypatch)
    first=await service.admit(str(uuid4()),composition_snapshot('삼성전자 수급'),request_started_at=clock.now)
    right=None
    if phase=='handoff':right=await service.start(first)
    async def late_commit():clock.mono+=16
    session.commit.side_effect=late_commit
    if phase=='start':assert not (await service.start(first)).newly_started
    else:
        with pytest.raises(C.CompositionError) as error:await service.handoff(right,'flow')
        assert error.value.code=='EXPIRED'
        with pytest.raises(C.CompositionError):service.take_handoff(right,'flow')
    assert rows[first.id].state=='claimed'


async def test_composition_unknown_commit_no_reissued_authority_and_expiry_closed(monkeypatch):
    from datetime import timedelta
    C,service,session,clock,rows=composition_service_fixture(monkeypatch)
    first=await service.admit(str(uuid4()),composition_snapshot('삼성전자 수급'),request_started_at=clock.now)
    session.commit.side_effect=OSError(SENTINEL)
    with pytest.raises(C.CompositionError) as error:await service.start(first)
    assert error.value.code=='ACK_UNKNOWN' and SENTINEL not in str(error.value)
    session.commit.side_effect=None
    assert (await service.get(first.id))['state']=='claimed'
    with pytest.raises(C.CompositionError):await service.start(first)
    clock.now+=timedelta(seconds=141)
    result=await service.get(first.id)
    assert result['state']=='closed' and result['coverage']=='unfulfilled'
    assert result['views'][0]['state']=='not_started' and rows[first.id].flow_handoff_at is None
    assert 'claim_digest' not in json.dumps(result) and 'key_digest' not in json.dumps(result)


@pytest.mark.parametrize('status',['not_found','ambiguous','resolved'])
async def test_composition_rechecks_positive_canonical_stock_before_admission(monkeypatch,status):
    C,service,session,clock,rows=composition_service_fixture(monkeypatch)
    resolved=resolution().model_dump(mode='json');resolved['status']=status
    wrong=NS(status=status,stock=NS(model_dump=lambda **kw:dict(stock_code='000720')))
    service.resolver_factory=lambda s:NS(resolve=AsyncMock(return_value=wrong))
    with pytest.raises(C.CompositionError):await service.admit(str(uuid4()),composition_snapshot(),request_started_at=clock.now)
    assert not rows and session.commit.await_count==0


async def test_composition_dirty_caller_rejected_without_rollback_or_mutation(monkeypatch):
    C,service,session,clock,rows=composition_service_fixture(monkeypatch)
    pending=object();session.dirty.add(pending)
    with pytest.raises(C.CompositionError):await service.admit(str(uuid4()),composition_snapshot(),request_started_at=clock.now)
    assert session.dirty=={pending} and session.rollback.await_count==session.commit.await_count==0 and not rows


@pytest.mark.parametrize('same_stock',[True,False])
async def test_composition_negated_alias_canonical_proof_is_not_dropped(monkeypatch,same_stock):
    C,service,session,clock,rows=composition_service_fixture(monkeypatch)
    looked=[]
    async def resolve(text):
        looked.append(text)
        if text=='삼성전자' or same_stock:return resolution()
        return NS(status='resolved',stock=NS(stock_code='066570'))
    service.resolver_factory=lambda s:NS(resolve=resolve)
    snapshot=composition_snapshot('엘지전자 말고 삼성전자 수급과 차트')
    if same_stock:
        with pytest.raises(C.CompositionError):await service.admit(str(uuid4()),snapshot,request_started_at=clock.now)
        assert not rows
    else:assert (await service.admit(str(uuid4()),snapshot,request_started_at=clock.now)).newly_admitted
    assert looked==['삼성전자','엘지전자']


def test_composition_migration_exact_model_checks_and_single_statement_DDL(monkeypatch):
    import importlib.util
    from db.models.supervisor.composition import CHECKS,SupervisorComposition
    path=ROOT/'backend/db/migrations/versions/20261113_c60001_supervisor_composition.py'
    spec=importlib.util.spec_from_file_location('composition_migration_fixture',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert (module.revision,module.down_revision)==('c60001a7e0001','c54001a7e0001') and module.CHECKS==CHECKS
    commands=[];created=[]
    monkeypatch.setattr(module.op,'execute',lambda sql:commands.append(sql))
    monkeypatch.setattr(module.op,'create_table',lambda *args,**kw:created.append(args))
    module.upgrade()
    functions=[sql for sql in commands if sql.startswith('CREATE OR REPLACE FUNCTION')]
    assert len(functions)==2 and all(sql.count('CREATE OR REPLACE FUNCTION')==1 for sql in functions)
    assert created[0][0]=='supervisor_compositions'
    assert {c.name for c in SupervisorComposition.__table__.constraints if c.name and c.name.startswith('composition_')}=={'composition_'+k for k in CHECKS}
    assert all(c.ondelete=='RESTRICT' for c in SupervisorComposition.__table__.foreign_keys)


async def test_composition_flow_result_link_does_not_restart_admission_window(monkeypatch):
    from src.modules.flow.api.analysis_schemas import AnalysisView
    C,service,session,clock,rows=composition_service_fixture(monkeypatch)
    first=await service.admit(str(uuid4()),composition_snapshot('삼성전자 수급'),request_started_at=clock.now)
    right=await service.start(first);await service.handoff(right,'flow');service.take_handoff(right,'flow')
    clock.mono+=16  # Original admission window is closed; total window is not.
    child=NS(id=uuid4(),admission_request_id=uuid4(),attempt_id=uuid4(),state='unknown',deadline_at=rows[first.id].deadline_at)
    monkeypatch.setattr(service,'_native',AsyncMock(return_value=(child,None)))
    receipt=AnalysisView(analysis_id=child.id,admission_request_id=child.admission_request_id,attempt_id=child.attempt_id,state='unknown',deadline_at=child.deadline_at)
    await service.link(right,'flow',receipt)
    assert rows[first.id].flow_run_id==child.id
    with pytest.raises(C.CompositionError):await service.handoff(right,'flow')


@pytest.mark.parametrize('query,expected',[
    ('삼성전자 수급',['flow_admission','flow_execution']),
    ('삼성전자 차트',['technical_admission','technical_execution']),
    ('삼성전자 수급과 차트',['technical_admission','flow_admission','technical_execution','flow_execution']),
])
async def test_composition_runtime_admits_selected_children_before_any_execution(monkeypatch,query,expected):
    from datetime import timedelta
    from src.modules.supervisor.application import composition_runtime as R
    C,root,session,clock,rows=composition_service_fixture(monkeypatch);events=[];limits=[]
    snapshot=composition_snapshot(query,projected=True)
    class Technical:
        def __init__(self,*args,**kwargs):pass
        async def admit_provider_once(self,key,intent,cfg,**kw):
            events.append('technical_admission');limits.append(kw['admission_before']);clock.mono+=1
            assert intent.data()['original_query']=='005930 차트' and snapshot.data()['draft']['original_query']==query
            return NS(newly_admitted=True,run=NS(analysis_id=uuid4(),as_of=clock.now,deadline_at=clock.now+timedelta(seconds=120)),claim_token=b't'*32)
        async def execute_provider_once(self,*args):events.append('technical_execution')
    class Flow:
        def __init__(self,*args,**kw):self.usage_control=NS(settings=None)
        async def admit_only(self,body,rid,**kw):
            events.append('flow_admission');limits.append(kw['admission_before'])
            assert body['question']==query and kw['admission_deadline']==115.0 and kw['total_deadline']==240.0
            return NS(view=NS(analysis_id=uuid4()),newly_admitted=True)
        async def execute_admitted_once(self,*args):events.append('flow_execution')
        def discard_continuations(self):events.append('discard')
    monkeypatch.setattr(R,'FlowService',Flow);monkeypatch.setattr(R,'TechnicalExecutionRuntime',Technical)
    first=await root.admit(str(uuid4()),snapshot,request_started_at=clock.now)
    async def link(right,view,receipt):
        row=rows[right.id]
        if view=='technical':row.analysis_as_of=clock.now;row.technical_run_id=receipt.run.analysis_id
        else:row.flow_run_id=receipt.analysis_id
    monkeypatch.setattr(root,'link',link);monkeypatch.setattr(root,'get',AsyncMock(return_value={'observed':True}))
    cfg=technical_configuration()
    runtime=R.CompositionRuntime(session,principal=root.principal,flow_client=AIClient('https://flow.synthetic.invalid',125,service_token=TOKEN),
        technical_client=AIClient(cfg.data()['ai_origin'],125,execution_token=TOKEN),enabled=True);runtime.root=root
    timeouts=[];timeout_at=R.asyncio.timeout_at
    def bounded(deadline):timeouts.append(deadline);return timeout_at(deadline)
    monkeypatch.setattr(R.asyncio,'timeout_at',bounded)
    result=await runtime.execute_once(first)
    assert [e for e in events if e!='discard']==expected and result=={'observed':True}
    assert all(t==rows[first.id].admission_before for t in limits) and rows[first.id].state=='closed'
    assert not root._tickets and not root._taken
    if 'technical' in snapshot.data()['selected_views']:assert 220.0 in timeouts
    assert max(timeouts)==240.0


async def test_composition_runtime_replay_and_default_off_have_no_native_invocation(monkeypatch):
    from src.modules.supervisor.application.composition_runtime import CompositionRuntime
    C,root,session,clock,rows=composition_service_fixture(monkeypatch)
    first=await root.admit(str(uuid4()),composition_snapshot(),request_started_at=clock.now)
    runtime=CompositionRuntime(session,principal=root.principal)
    monkeypatch.setattr(runtime.root,'start',AsyncMock())
    with pytest.raises(C.CompositionError):await runtime.execute_once(first)
    assert runtime.root.start.await_count==0 and rows[first.id].state=='admitted'
    replay=C.Admission(first.id,False,None)
    monkeypatch.setattr(runtime.root,'get',AsyncMock(return_value={'observed':True}))
    assert await runtime.execute_once(replay)=={'observed':True}
    assert runtime.root.start.await_count==0


async def test_composition_admission_late_ACK_closes_local_authority(monkeypatch):
    C,root,session,clock,rows=composition_service_fixture(monkeypatch)
    async def late():clock.mono+=16
    session.commit.side_effect=late
    receipt=await root.admit(str(uuid4()),composition_snapshot(),request_started_at=clock.now)
    assert not receipt.newly_admitted and receipt.token is None and len(rows)==1
    with pytest.raises(C.CompositionError):await root.start(receipt)


@pytest.mark.parametrize('query',['삼성전자 수급','삼성전자 차트','삼성전자 수급과 차트'])
def test_composition_v2_explicit_inputs_preserve_parent_and_v1_native_fingerprints(query):
    from src.modules.supervisor.application.composition_service import CompositionService
    from src.modules.supervisor.domain.composition import VERSION,PROJECTED_VERSION
    old=composition_snapshot(query);new=composition_snapshot(query,projected=True)
    assert old.data()['schema_version']==VERSION and new.data()['schema_version']==PROJECTED_VERSION
    assert old.data()['draft']==new.data()['draft'] and old.data()['frame']==new.data()['frame']
    if 'technical' in old.data()['selected_views']:
        assert CompositionService.technical_intent(old).data()['original_query']==query
        assert CompositionService.technical_intent(new).data()['original_query']=='005930 차트'
        assert CompositionService.technical_intent(old).fingerprint!=CompositionService.technical_intent(new).fingerprint
    if 'flow' in new.data()['selected_views']:assert new.data()['child_inputs']['flow']['question']==query


@pytest.mark.parametrize('change',['technical_query','ticker','period','extra_view','flow_query','missing','v1_auto_conversion'])
def test_composition_v2_rejects_unconfirmed_native_input_projection(change):
    from src.modules.supervisor.domain.composition import CompositionSnapshot,CompositionInvalid,VERSION
    v=composition_snapshot(projected=True).data()
    if change=='technical_query':v['child_inputs']['technical']['original_query']='삼성전자 수급과 차트'
    if change=='ticker':v['child_inputs']['technical']['ticker']='000720'
    if change=='period':v['child_inputs']['technical']['conditions']['periods']=['3w']
    if change=='extra_view':v['child_inputs']['news']={}
    if change=='flow_query':v['child_inputs']['flow']['question']='수급만'
    if change=='missing':del v['child_inputs']
    if change=='v1_auto_conversion':v['schema_version']=VERSION
    with pytest.raises(CompositionInvalid):CompositionSnapshot(B.canonical(v))


async def test_composition_legacy_snapshot_read_is_not_new_projected_execution_authority(monkeypatch):
    from src.modules.supervisor.application.composition_runtime import CompositionRuntime
    C,root,session,clock,rows=composition_service_fixture(monkeypatch)
    old=await root.admit(str(uuid4()),composition_snapshot(),request_started_at=clock.now)
    runtime=CompositionRuntime(session,principal=root.principal,enabled=True);runtime.root=root
    monkeypatch.setattr(root,'start',AsyncMock())
    with pytest.raises(C.CompositionError) as error:await runtime.execute_once(old)
    assert error.value.code=='INVALID' and root.start.await_count==0 and rows[old.id].state=='admitted'
    assert (await root.get(old.id))['coverage']=='pending'


def test_composition_projection_revision_is_additive_and_populated_downgrade_closed(monkeypatch):
    import importlib.util
    path=ROOT/'backend/db/migrations/versions/20261113_c61001_supervisor_composition_projection.py'
    spec=importlib.util.spec_from_file_location('composition_projection_fixture',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert (module.revision,module.down_revision)==('c61001a7e0001','c60001a7e0001')
    assert "IN ('supervisor.composition.v1','supervisor.composition.v2')" in module.GUARD
    assert module.GUARD.count('Composition native projection invalid')==1
    assert 'native.intent_sha256=encode(digest' in module.GUARD
    commands=[];monkeypatch.setattr(module.op,'execute',lambda sql:commands.append(sql))
    module.upgrade()
    assert len(commands)==2 and commands[1]==module.GUARD and commands[1].count('CREATE OR REPLACE FUNCTION')==1
    commands.clear();monkeypatch.setattr(module.op,'get_bind',lambda:NS(execute=lambda q:NS(scalar=lambda:True)))
    with pytest.raises(RuntimeError,match='^Composition history retained$'):module.downgrade()
    assert len(commands)==1 and commands[0].startswith('LOCK TABLE')
