"""Fixed read-only collection: production DTO/router/service/SQL, synthetic session I/O."""
import ast
import asyncio
import copy
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
import hashlib
import importlib.abc
import importlib.util
import importlib.machinery
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
ATTEMPTS = []
class Imports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('src.agents.', 'src.supervisor.', 'src.api.main')) or fullname in {'openai','redis','langgraph','langchain_openai'}:
            ATTEMPTS.append(fullname)
            raise AssertionError('Read cannot load an engine or application bootstrap')
GUARD = Imports(); sys.meta_path.insert(0,GUARD)


def load_readonly():
    from scripts.check_safe import CF035_COMPAT, CF035_INPUTS, CF036_INPUTS
    ai = ROOT/'ai/src'
    for name in ('agents','agents.flow','agents.flow.api','agents.flow.domain','agents.flow.domain.verification','agents.flow.infrastructure'):
        if name not in sys.modules:
            module = ModuleType(name)
            module.__spec__ = importlib.machinery.ModuleSpec(name,None,is_package=True)
            module.__spec__.submodule_search_locations = [str(ai.joinpath(*name.split('.')))]
            module.__path__ = []
            sys.modules[name] = module
    for relative, expected in CF035_COMPAT.items():
        path = ROOT/relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        name = relative.removeprefix('ai/src/').removesuffix('.py').replace('/','.')
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name,path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module; spec.loader.exec_module(module)
        assert isinstance(sys.modules[name].__spec__.loader,importlib.machinery.SourceFileLoader)
        assert Path(sys.modules[name].__spec__.origin).resolve() == path.resolve()
    for relative, expected in (CF035_INPUTS | CF036_INPUTS).items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == expected


load_readonly()
# Configuration and the dependency's DB factory are explicit synthetic seams set
# before auth/router collection. Actual request_principal and owner service execute.
settings = SimpleNamespace(GOOGLE_CLIENT_ID='synthetic.apps.googleusercontent.com',GOOGLE_CLIENT_SECRET='synthetic-only',
    AUTH_REDIRECT_URI='http://localhost:3200/api/auth/callback',AUTH_ORIGINS='http://localhost:3200',AUTH_ALLOW_LOCAL_HTTP=True)
configuration = ModuleType('src.shared.config'); configuration.settings = settings
async def unused_session():
    raise AssertionError('Uninjected session dependency')
    yield
session_module = ModuleType('db.session'); session_module.get_session = unused_session
sys.modules['src.shared.config'] = configuration; sys.modules['db.session'] = session_module
from fastapi import FastAPI
from sqlalchemy.dialects import postgresql
from scripts.cf035_technical_owned_check import storage_fixture
from src.modules.auth.api import router as auth
from src.modules.auth.application.session_service import Principal, AuthenticationRequired
from src.modules.technical.api import owned_report_router as router, owned_report_schemas as wire
from src.modules.technical.application import owned_report_service as service
from src.modules.technical.infrastructure import report_repository as repo
from src.shared.http.access_boundary import AccessBoundary
from db.models.technical.report_snapshot import TechnicalReportSnapshot

FIXTURE = json.loads((ROOT/'frontend/tests/fixtures/cf036-technical-owned-read.json').read_text())
PRIVATE = 'cf036-private-error-sentinel'

class Session:
    def __init__(self):
        self.no_autoflush = nullcontext()
        self.commit = AsyncMock(side_effect=AssertionError('Read cannot commit'))
        self.flush = AsyncMock(side_effect=AssertionError('Read cannot stage'))
        self.rollback = AsyncMock()


def principal(): return Principal(uuid4(),uuid4(),datetime.now(UTC)+timedelta(hours=1),b'x'*32)


def prepare(monkeypatch):
    p = principal(); session = Session(); binding, frozen = storage_fixture(p.user_id)
    stamp = datetime.now(UTC); rows = service.projection(binding,frozen,p,stamp)
    snapshot = TechnicalReportSnapshot(**service.snapshot_values(binding,frozen,stamp,p.session_id))
    monkeypatch.setattr(service,'validate_principal',AsyncMock())
    monkeypatch.setattr(repo,'get_owned_storage',AsyncMock(return_value=(rows[0],snapshot)))
    monkeypatch.setattr(repo,'technical_indexes',AsyncMock(return_value=[rows[-1]]))
    monkeypatch.setattr(repo,'storage_children',AsyncMock(return_value=[rows[1],rows[2],rows[3],[rows[4]],[rows[5]]]))
    monkeypatch.setattr(repo,'owned_ids',AsyncMock(return_value=[frozen.report_id]))
    async def authenticate(s, token, **kwargs):
        assert s is session
        if token != 'synthetic-owner-cookie': raise AuthenticationRequired()
        return p
    monkeypatch.setattr(auth,'authenticate',authenticate)
    async def dependency():
        try: yield session
        finally: await session.rollback()
    app = FastAPI(); app.include_router(router.router); app.add_middleware(AccessBoundary)
    app.dependency_overrides[router.session_dependency] = dependency
    return app,p,session,binding,frozen,rows


async def call(app, path=wire.PATH, *, method='GET', cookie='synthetic-owner-cookie', host='localhost:8200'):
    headers = {'origin':'http://localhost:3200','x-forwarded-host':'localhost:3200'}
    if cookie is not None: headers['cookie']='verith_session='+cookie
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://'+host) as client:
        return await client.request(method,path,headers=headers)


def check_response(response,status):
    assert response.status_code == status, response.text
    assert response.headers['cache-control']=='private, no-store'
    assert response.headers['vary']=='Cookie, Origin'
    value=response.json()
    assert set(value)=={'schema_version','request_id','data','error'}
    assert value['schema_version']==wire.SCHEMA and str(UUID(value['request_id']))==value['request_id']
    assert (value['data'] is None) == (status>=400)
    assert (value['error'] is None) == (status<400)
    assert PRIVATE not in response.text
    return value


async def test_production_router_service_raw_text_and_card_projection(monkeypatch):
    app,p,s,b,f,rows=prepare(monkeypatch)
    listed=check_response(await call(app),200)['data']
    assert listed['items'][0]['report_id']==str(f.report_id)
    assert set(listed['items'][0])=={'report_id','stock','created_at','requested_as_of','execution_mode','cutoff_validation'}
    detail=check_response(await call(app,wire.PATH+'/'+str(f.report_id)),200)['data']
    assert detail['request_json']==f.input_json and detail['request_sha256']==f.input_sha256
    assert detail['result_json']==f.result_json and detail['result_sha256']==f.result_sha256
    assert detail['report_id']==str(f.report_id)
    s.commit.assert_not_awaited(); s.flush.assert_not_awaited(); assert not ATTEMPTS


@pytest.mark.parametrize('query',['?owner=x','?session=x','?limit=','?limit=0','?limit=21','?limit=-1','?offset=10001','?limit=1&limit=2','?stock_code=１２３４５６','?stock_code=12345','?stock_code=005930&unknown=1','?limit=true','?limit=1.0'])
async def test_query_closed_before_service(monkeypatch,query):
    app,*_=prepare(monkeypatch)
    check_response(await call(app,wire.PATH+query),422)
    repo.owned_ids.assert_not_awaited()


@pytest.mark.parametrize('path,method,status',[
    (wire.PATH,'POST',403),(wire.PATH,'DELETE',403),(wire.PATH+'/bad','GET',422),
    (wire.PATH+'/00000000-0000-4000-8000-000000000006?limit=1','GET',422),
    (wire.PATH+'/00000000-0000-4000-8000-000000000006/trace','GET',403),
    ('/api/technical/reports','GET',403),('/api/technical/analyze','POST',403),
])
async def test_exact_gets_and_legacy_closed(monkeypatch,path,method,status):
    app,*_=prepare(monkeypatch)
    response=await call(app,path,method=method)
    assert response.status_code==status
    if path.startswith(wire.PATH):check_response(response,status)


@pytest.mark.parametrize('cookie',[None,'forged','synthetic-owner-cookie; verith_session=synthetic-owner-cookie'])
async def test_actual_unique_cookie_auth_no_result(monkeypatch,cookie):
    app,*_=prepare(monkeypatch)
    check_response(await call(app,cookie=cookie),401)
    repo.owned_ids.assert_not_awaited()


async def test_auth_unconfigured_and_local_host_fail_closed(monkeypatch):
    app,*_=prepare(monkeypatch)
    check_response(await call(app,host='127.0.0.1:8200'),403)
    monkeypatch.setattr(auth,'configured',lambda:False)
    check_response(await call(app),401)
    repo.owned_ids.assert_not_awaited()


async def test_missing_eligibility_and_payload_errors_do_not_leak(monkeypatch):
    app,p,s,b,f,_=prepare(monkeypatch)
    monkeypatch.setattr(repo,'get_owned_storage',AsyncMock(return_value=None))
    check_response(await call(app,wire.PATH+'/'+str(f.report_id)),404)
    monkeypatch.setattr(repo,'get_owned_storage',AsyncMock(side_effect=RuntimeError(PRIVATE)))
    check_response(await call(app,wire.PATH+'/'+str(f.report_id)),503)
    monkeypatch.setattr(repo,'get_owned_storage',AsyncMock(side_effect=service.TechnicalStoredPayloadError()))
    check_response(await call(app,wire.PATH+'/'+str(f.report_id)),502)


async def test_list_limit_plus_one_validates_every_selected_row(monkeypatch):
    app,p,s,b,f,_=prepare(monkeypatch)
    ids=[uuid4(),uuid4()]; monkeypatch.setattr(repo,'owned_ids',AsyncMock(return_value=ids))
    known=service.TechnicalStoredReport(f,{'stock':{'stock_code':'005930','stock_name':'삼성전자','market':'KOSPI'}},{},datetime.now(UTC))
    read=AsyncMock(return_value=known); monkeypatch.setattr(service.TechnicalOwnedReportService,'read',read)
    data=await service.TechnicalOwnedReportService(s,principal=p).list_owned(stock_code='005930',limit=1,offset=2)
    assert data['has_more'] is True and len(data['items'])==1 and read.await_count==2
    repo.owned_ids.assert_awaited_once_with(s,p.user_id,stock_code='005930',limit=1,offset=2)
    read.side_effect=[known,None]
    with pytest.raises(service.TechnicalStoredPayloadError):await service.TechnicalOwnedReportService(s,principal=p).list_owned(limit=1)
    s.commit.assert_not_awaited();s.flush.assert_not_awaited()


@pytest.mark.parametrize('query',[{'limit':True},{'limit':21},{'offset':-1},{'offset':10001},{'stock_code':'１２３４５６'},{'stock_code':'005930x'}])
async def test_service_internal_query_validation(query):
    with pytest.raises(service.TechnicalStorageInputError):await service.TechnicalOwnedReportService(Session(),principal=principal()).list_owned(**query)


def test_sql_preserves_total_index_owner_and_fixed_order():
    p=uuid4();sql=str(repo.owned_ids_statement(p,stock_code='005930',limit=20,offset=7).compile(dialect=postgresql.dialect(),compile_kwargs={'literal_binds':True}))
    assert 'technical_reports.owner_user_id =' in sql and 'technical_report_snapshots.owner_user_id =' in sql
    assert 'count(*) = 1' in sql and 'count(*) FILTER (WHERE agent_reports.owner_user_id =' in sql
    assert 'ORDER BY technical_reports.created_at DESC, technical_reports.id DESC' in sql and 'LIMIT 21 OFFSET 7' in sql
    assert "technical_reports.stock_code = '005930'" in sql


@pytest.mark.parametrize('key',['detail','second_detail'])
def test_shared_wire_exact_original_text_hash_and_independent_request(key):
    from src.modules.analysis.domain.contracts import strict_json,canonical_json,json_hash
    from src.modules.technical.domain.execution_boundary import validate_response
    data=FIXTURE[key]['data'];request=strict_json(data['request_json']);response=strict_json(data['result_json'])
    assert canonical_json(request)==data['request_json'] and canonical_json(response)==data['result_json']
    assert json_hash(data['request_json'])==data['request_sha256'] and json_hash(data['result_json'])==data['result_sha256']
    assert data['report_id']==request['data']['context']['report_id']
    validate_response(response,request)
    wire.response({},data,detail=True)


def test_wire_size_unicode_and_fixed_error_contract():
    assert wire.DETAIL_CAP==4259840 and wire.LIST_CAP==65536
    response=wire.response({},FIXTURE['detail']['data'],detail=True)
    assert '삼성전자'.encode() in response.body and b'\\u' not in response.body
    for field,limit in [('request_json',16384),('result_json',2097152)]:
        changed=copy.deepcopy(FIXTURE['detail']['data']);changed[field]='x'*(limit+1)
        with pytest.raises(ValueError):wire.response({},changed,detail=True)
    response=wire.error({},'not-known')
    assert response.status_code==503 and json.loads(response.body)['error']=={'code':'SERVICE_UNAVAILABLE','message':'Technical result unavailable'}


async def test_service_timeout_exception_maps_to_fixed_error(monkeypatch):
    app,*_=prepare(monkeypatch)
    async def delayed(*args,**kwargs):raise TimeoutError(PRIVATE)
    monkeypatch.setattr(service.TechnicalOwnedReportService,'list_owned',delayed)
    check_response(await call(app),504)


def test_source_registration_only_and_no_hidden_mutations():
    tree=ast.parse((ROOT/'backend/src/api/main.py').read_text())
    assert any(isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and ast.unparse(n.value)=='app.include_router(technical_owned_reports.router)' for n in tree.body)
    source=Path(router.__file__).read_text()
    assert 'asyncio.timeout(15)' in source and 'mutation=False' in source
    for forbidden in ('AIClient','stage(','commit('):assert forbidden not in source
    assert not ATTEMPTS


async def test_actual_timeout_cancels_await_and_cleans_function_dependency(monkeypatch):
    app,p,session,*_=prepare(monkeypatch)
    entered=asyncio.Event();cancelled=asyncio.Event();requested=[]
    async def delayed(*args,**kwargs):
        entered.set()
        try:await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
    original_timeout=asyncio.timeout
    def accelerated(seconds):
        requested.append(seconds)
        return original_timeout(.005)
    monkeypatch.setattr(service.TechnicalOwnedReportService,'list_owned',delayed)
    monkeypatch.setattr(router.asyncio,'timeout',accelerated)
    check_response(await call(app),504)
    assert entered.is_set() and cancelled.is_set() and requested==[15]
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited();session.flush.assert_not_awaited()
