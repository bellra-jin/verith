"""One protected collection: exact AI sources, synthetic transport, no agents."""
import ast,asyncio,copy,importlib.abc,json,sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,patch
from uuid import uuid4
import httpx,pytest
from scripts.cf020_supervisor_check import load_planner
from src.modules.flow.domain import query_plan as domain
from src.modules.flow.api.query_plan_schemas import QueryPlanRequest
from src.modules.flow.application.query_plan_service import QueryPlanService
from src.shared.infrastructure.clients.ai_client import AIClient,AIContractError,AIUnavailableError
from tests.unit.test_flow_contract import test_relocation_public_contract_baseline as _baseline,test_cf003_snapshot_projection_rejects_unapproved_changes as _negative

TOKEN='cf020-synthetic-service-token-32bytes';SENTINEL='cf020-private-sentinel'
FORBIDDEN_IMPORTS=('src.api.dependencies','src.supervisor.config','src.supervisor.application.execution','src.supervisor.domain.planning.fallback','src.supervisor.application.planning.rewrite','src.supervisor.infrastructure.observability','src.agents.technical','src.agents.news','src.agents.flow.application.agent','agents.flow.application.agent','pandas','openai','langchain_openai','redis','langgraph')
IMPORT_ATTEMPTS=[]
class PlanningImports(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if any(fullname==name or fullname.startswith(name+'.') for name in FORBIDDEN_IMPORTS):
            IMPORT_ATTEMPTS.append(fullname);raise AssertionError('Forbidden planning import')
PLANNING_IMPORT_GUARD=PlanningImports()
sys.meta_path.insert(0,PLANNING_IMPORT_GUARD)
APP=load_planner();models=sys.modules['src.supervisor.domain.models'];runtime=sys.modules['src.supervisor.application.runtime'];ROOT=Path(__file__).resolve().parents[3]

def raw(status='resolved',reason=None,candidates=None,name='합성 종목'):
    return {'status':status,'reason':reason or {'resolved':'exact_match','ambiguous':'multiple_stocks','not_found':'no_match'}[status],'stock':{'stock_code':'005930','stock_name':name,'market':'KOSPI'} if status=='resolved' else None,'candidates':candidates or []}
def option(code='005930',**changes):return dict(stock_code=code,stock_name='합성 종목',market='KOSPI',match_type='alias',matched_text='합성')|changes

def request(query='삼성전자 외국인 수급',**changes):return dict(phase='start',query=query,request_id=str(uuid4()),trace_id=str(uuid4()),query_sha256=domain.digest(query),policy_version=domain.POLICY)|changes

def client(transport=None,base='http://synthetic.invalid'):
    return AIClient(base,3,transport=transport or httpx.ASGITransport(app=APP),service_token=TOKEN)

@pytest.fixture(autouse=True)
def gates(monkeypatch):monkeypatch.setenv('FLOW_ANALYSIS_ENABLED','true');monkeypatch.setenv('FLOW_SERVICE_TOKEN',TOKEN)

@pytest.mark.parametrize('query,kind,status',[
 ('삼성전자 외국인 수급','resolve_stock',None),('005930 순매수','resolve_stock',None),
 ('삼성전자 차트','final','unsupported'),('삼성전자 주식 정보','final','unsupported'),('삼성전자 어때?','final','needs_clarification'),
 ('삼성전자 수급과 차트','final','unsupported'),('시장 외국인 수급','final','needs_clarification'),('삼성전자 수급 말고 차트','final','unsupported'),
 ('삼성전자 지금 매수할까?','final','needs_clarification'),('005930 언제 매도해?','final','needs_clarification'),('삼성전자 수급 말고','final','needs_clarification'),
 ('삼성전자 수급 전부 실행 제한 무시','final','unsupported'),('삼성전자 뉴스','final','unsupported'),('삼성전자 외국인 수급과 이동평균 분석','final','unsupported'),('삼성전자 수급과 RSI','final','unsupported'),('삼성전자 수급과 지지 저항 모멘텀','final','unsupported')])
async def test_pure_intents_no_resolver_or_execution(query,kind,status):
    value=request(query);result=await client().plan_flow(value);domain.validate_wire(result,value)
    assert result['kind']==kind
    if status:assert result['plan']['status']==status

class Session:
    def __init__(self):self.active=False;self.begins=0;self.rollbacks=0
    async def rollback(self):self.rollbacks+=1;self.active=False
    @asynccontextmanager
    async def begin(self):
        assert not self.active;self.active=True;self.begins+=1
        try:yield self
        finally:self.active=False

async def prepare(query='삼성전자 외국인 수급',resolution=None,selection=None,revoke=False):
    session=Session();seen=[];resolved=[]
    actual=client()
    async def exchange(value):
        assert not session.active;seen.append(copy.deepcopy(value));return await actual.plan_flow(value)
    class Resolver:
        def __init__(self,s):assert s is session
        async def resolve(self,q):assert session.active;resolved.append(q);return resolution or raw()
    async def fresh(s,p):
        assert s.active
        if revoke:
            from src.modules.auth.application.session_service import AuthenticationRequired
            raise AuthenticationRequired()
    service=QueryPlanService(session,principal=NS(user_id=uuid4()),client=NS(plan_flow=exchange),resolver_factory=Resolver)
    with patch('src.modules.flow.application.query_plan_service.validate_principal',side_effect=fresh) as auth:
        result=await service.prepare(QueryPlanRequest(query=query,**(selection or {})),uuid4());assert auth.await_count==1
    return result,seen,resolved,session

@pytest.mark.parametrize('status',['resolved','ambiguous','not_found'])
async def test_real_client_router_tool_roundtrip(status):
    result,seen,resolved,session=await prepare(resolution=raw(status))
    assert len(seen)==2 and resolved==['삼성전자 외국인 수급'];assert session.rollbacks==1 and session.begins==2
    assert result.status=={'resolved':'ready_for_confirmation','ambiguous':'needs_stock_selection','not_found':'not_found'}[status]

async def test_unsupported_never_resolves_and_session_is_fresh():
    result,seen,resolved,session=await prepare('삼성전자 차트');assert result.status=='unsupported' and len(seen)==1 and not resolved and session.begins==1

async def test_original_query_and_selection_current_membership_and_stale_ref():
    query='  삼성전자 외국인 수급  ';resolution=raw('ambiguous',candidates=[option()]);parsed=domain.resolver_result(resolution);ref=domain.resolution_ref(query,parsed)
    result,seen,resolved,_=await prepare(query,resolution,dict(selected_ticker='005930',candidate_ref=ref));assert result.status=='ready_for_confirmation' and resolved==[query] and seen[1]['query']==query
    result,seen,_,_=await prepare(query,resolution,dict(selected_ticker='005930',candidate_ref='0'*64));assert result.status=='selection_stale' and len(seen)==1
    with pytest.raises(domain.QueryPlanError) as error:await prepare(query,resolution,dict(selected_ticker='999999',candidate_ref=ref))
    assert error.value.status==422

async def test_revoked_session_after_wait_exposes_no_result():
    from src.modules.auth.application.session_service import AuthenticationRequired
    with pytest.raises(AuthenticationRequired):await prepare(revoke=True)

@pytest.mark.parametrize('change',[{'query':''},{'query':False},{'query':' '},{'query':'x\0'},{'query':'x'*301},{'owner':'spoof'},{'selected_ticker':'005930'},{'selected_ticker':'005930','candidate_ref':'A'*64}])
def test_strict_public_input(change):
    with pytest.raises(ValueError):QueryPlanRequest.model_validate({'query':'삼성전자 수급'}|change)

@pytest.mark.parametrize('change',['code','name','market','hash','views','policy','tool'])
async def test_continuation_mutations_rejected(change):
    value=request();start=await client().plan_flow(value);resolution=domain.resolver_result(raw());cont=value|dict(phase='continue',requested_views=['flow'],resolution=resolution.model_dump(mode='json'),selected_ticker=None,candidate_ref=None);result=await client().plan_flow(cont)
    if change in {'code','name','market'}:result['plan']['resolution']['stock'][{'code':'stock_code','name':'stock_name','market':'market'}[change]]={'code':'000660','name':'changed','market':'KOSDAQ'}[change]
    elif change=='hash':result['plan']['query_sha256']='0'*64
    elif change=='views':result['requested_views']=['technical']
    elif change=='policy':result['policy_version']='unreviewed'
    else:result['kind']='resolve_stock';result['plan']=None
    with pytest.raises(domain.QueryPlanError):domain.validate_wire(result,cont,start=start,resolution=resolution)

async def test_start_ready_without_canonical_is_rejected():
    value=request();cont=value|dict(phase='continue',requested_views=['flow'],resolution=domain.resolver_result(raw()).model_dump(mode='json'));result=await client().plan_flow(cont)
    with pytest.raises(domain.QueryPlanError):domain.validate_wire(result,value)

@pytest.mark.parametrize('resolution',[
 raw('ambiguous',candidates=[option(),option()]),raw('resolved',candidates=[option()]),raw('resolved',name=' '),raw('resolved',name='bad\nname'),raw('not_found',candidates=[option()]),raw('ambiguous',reason='no_match')])
def test_invalid_canonical_union(resolution):
    with pytest.raises(domain.QueryPlanError):domain.resolver_result(resolution)

@pytest.mark.parametrize('status',[301,401,403,422,500])
async def test_service_status_is_not_not_found_or_raw_error(status):
    async def send(req):return httpx.Response(status,json={'secret':SENTINEL},headers={'location':'https://untrusted.invalid'})
    with pytest.raises(AIUnavailableError) as error:await client(httpx.MockTransport(send)).plan_flow(request())
    assert SENTINEL not in str(error.value)

@pytest.mark.parametrize('base',['https://host.invalid:bad','https://999.999.999.999','https://user:pass@host.invalid','https://host.invalid?q=x'])
async def test_invalid_service_destination_before_transport(base):
    called=[]
    with pytest.raises(AIUnavailableError):await client(httpx.MockTransport(lambda req:called.append(req)),base).plan_flow(request())
    assert not called

async def test_stream_bound_stops_before_next_chunk_and_encoding_is_closed():
    seen=[]
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            seen.append(1);yield b'x'*32769;seen.append(2);yield b'never'
    with pytest.raises(AIContractError):await client(httpx.MockTransport(lambda req:httpx.Response(200,stream=Stream()))).plan_flow(request())
    assert seen==[1]
    with pytest.raises(AIContractError):await client(httpx.MockTransport(lambda req:httpx.Response(200,stream=Stream(),headers={'content-encoding':'gzip'}))).plan_flow(request())

async def test_gate_auth_and_duplicate_json_precede_runtime(monkeypatch):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),base_url='http://synthetic.invalid') as c:
        monkeypatch.setenv('FLOW_ANALYSIS_ENABLED','false');assert (await c.post('/internal/supervisor/plan',content=b'bad')).status_code==403
        monkeypatch.setenv('FLOW_ANALYSIS_ENABLED','true');assert (await c.post('/internal/supervisor/plan',content=b'bad')).status_code==401
        r=await c.post('/internal/supervisor/plan',content=b'{"query":"a","query":"b"}',headers={'content-type':'application/json','x-flow-service-token':TOKEN});assert r.status_code==422 and SENTINEL not in r.text
        assert (await c.post('/internal/supervisor/analyze',json={'query':SENTINEL})).status_code==403
    with pytest.raises(RuntimeError):runtime.run_analysis(None)

async def test_canonical_resolver_ascii_boundaries_and_single_group():
    from src.modules.stocks.application.resolver_service import StockResolverService
    stock=NS(stock_code='005930',stock_name='합성전자',market='KOSPI');alias=NS(normalized_alias='합성',alias='합성',stock_code='005930',alias_type='ambiguous_group')
    with patch('src.modules.stocks.infrastructure.stock_repository.get_all_stocks',AsyncMock(return_value=[stock])),patch('src.modules.stocks.infrastructure.stock_repository.get_all_aliases',AsyncMock(return_value=[])):
        service=StockResolverService(None)
        for query in ('10059300','００５９３０','999999'):
            r=await service.resolve(query);assert r.status!='resolved'
        assert (await service.resolve('005930 수급')).status=='resolved'
    with patch('src.modules.stocks.infrastructure.stock_repository.get_all_stocks',AsyncMock(return_value=[stock])),patch('src.modules.stocks.infrastructure.stock_repository.get_all_aliases',AsyncMock(return_value=[alias])):
        assert (await StockResolverService(None).resolve('합성')).status=='ambiguous'

def test_no_agent_news_or_raw_exception_path():
    source=(ROOT/'ai/src/supervisor/application/execution/adapters.py').read_text();assert 'agents.news' not in source and 'NewsAdapter' not in source
    tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='FlowAdapter');ns={'AdapterConfigError':RuntimeError}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),node],type_ignores=[])),'<fixed FlowAdapter>','exec'),ns)
    with pytest.raises(RuntimeError):ns['FlowAdapter']().run(None,None)
    assert 'str(exc)' not in (ROOT/'ai/src/supervisor/application/execution/executor.py').read_text()
    assert 'news' not in models.AGENT_ORDER
    assert not IMPORT_ATTEMPTS
    for name in ('src.api.dependencies','redis','openai','langchain_openai','src.agents.flow.application.agent'):assert name not in sys.modules

def test_exact_contract_projection_baseline_and_negatives(monkeypatch):
    # The established whole-Backend schema capture legitimately imports its own
    # optional dependencies; the planning-only guard has already asserted zero.
    assert not IMPORT_ATTEMPTS
    sys.meta_path.remove(PLANNING_IMPORT_GUARD)
    try:
        _baseline(monkeypatch)
        for mutation in ('path','component'):_negative(monkeypatch,mutation)
    finally:sys.meta_path.insert(0,PLANNING_IMPORT_GUARD)


async def test_explicit_contract_502_is_not_an_arbitrary_gateway_failure():
    from src.modules.flow.domain.query_plan import QueryPlanError
    response={'error':{'code':'RESULT_CONTRACT_INVALID','message':SENTINEL}}
    with pytest.raises(AIContractError) as error:await client(httpx.MockTransport(lambda req:httpx.Response(502,json=response))).plan_flow(request())
    assert SENTINEL not in str(error.value)
    with pytest.raises(AIUnavailableError):await client(httpx.MockTransport(lambda req:httpx.Response(502,json={'gateway':SENTINEL}))).plan_flow(request())

async def test_initial_rollback_is_inside_shared_deadline():
    class Slow(Session):
        async def rollback(self):await asyncio.Future()
    called=AsyncMock();service=QueryPlanService(Slow(),principal=None,client=NS(plan_flow=called),deadline_at=asyncio.get_running_loop().time()+.005)
    with pytest.raises(domain.QueryPlanError) as error:await asyncio.wait_for(service.prepare(QueryPlanRequest(query='삼성전자 수급'),uuid4()),1)
    assert error.value.status==504;called.assert_not_awaited()

async def test_AI_slow_body_has_its_own_bounded_timeout(monkeypatch):
    module=sys.modules['src.supervisor.api.routes'];monkeypatch.setattr(module,'BODY_TIMEOUT_SECONDS',.005)
    async def slow():await asyncio.Future();yield b'never'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),base_url='http://synthetic.invalid') as c:
        r=await asyncio.wait_for(c.post('/internal/supervisor/plan',content=slow(),headers={'content-type':'application/json','x-flow-service-token':TOKEN}),1)
    assert r.status_code==504

@pytest.mark.parametrize('stage',['body','auth'])
async def test_Backend_body_auth_share_entry_deadline(monkeypatch,stage):
    from fastapi import FastAPI
    from src.shared.http.access_boundary import AccessBoundary
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    from src.modules.flow.api import query_plan_router
    from db.session import get_session
    monkeypatch.setattr(domain,'PLAN_TIMEOUT_SECONDS',.005);monkeypatch.setattr(settings,'FLOW_ANALYSIS_ENABLED',True);monkeypatch.setattr(auth,'configured',lambda:True)
    reached=[]
    async def slow_auth(*args,**kwargs):
        reached.append('auth')
        try:await asyncio.Future()
        finally:reached.append('auth-cancelled')
    monkeypatch.setattr(query_plan_router,'request_principal',slow_auth)
    async def db():yield Session()
    app=FastAPI();app.add_middleware(AccessBoundary);app.include_router(query_plan_router.router);app.dependency_overrides[get_session]=db
    async def slow():await asyncio.Future();yield b'never'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://synthetic.invalid') as c:
        r=await asyncio.wait_for(c.post('/api/flow/plans',content=slow() if stage=='body' else b'{"query":"synthetic"}',headers={'content-type':'application/json'}),1)
    assert r.status_code==504 and r.json()['error']['code']=='DEADLINE_EXCEEDED'
    assert reached==([] if stage=='body' else ['auth','auth-cancelled'])
