"""CF-015 exact-source loaders and focused owned-PG integration. No provider I/O."""
import asyncio,hashlib,importlib.util,importlib.machinery,sys,types
from datetime import UTC,datetime
from pathlib import Path
from uuid import UUID,uuid4
from scripts.cf003_admission_check import check,isolated_application


def _module(name,relative):
    from scripts.check_safe import CF015_INPUTS
    root=Path(__file__).resolve().parents[2];path=root/relative
    check(hashlib.sha256(path.read_bytes()).hexdigest()==CF015_INPUTS[relative],'CF015 exact source pin')
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value)
    check(Path(value.__spec__.origin).resolve()==path.resolve(),'CF015 exact origin')
    parent,_,leaf=name.rpartition('.')
    if parent in sys.modules:setattr(sys.modules[parent],leaf,value)
    return value


def _package(name,location):
    if name in sys.modules:return
    value=types.ModuleType(name);value.__spec__=importlib.machinery.ModuleSpec(name,loader=None,is_package=True)
    value.__spec__.submodule_search_locations=[str(location)];value.__path__=[];sys.modules[name]=value


def load_origins():
    root=Path(__file__).resolve().parents[2]/'ai/src'
    for name in ('agents','agents.flow','agents.flow.api','agents.flow.domain','agents.flow.domain.verification','agents.flow.infrastructure'):_package(name,root.joinpath(*name.split('.')))
    for name in ('domain.observation_window','domain.verification.consecutive','domain.interpretation_claims','domain.models','api.payload','infrastructure.token_cache'):
        full='agents.flow.'+name
        if full not in sys.modules:_module(full,'ai/src/'+full.replace('.','/')+'.py')


def fundamental_app(engine):
    from fastapi import FastAPI
    load_origins();root=Path(__file__).resolve().parents[2]/'ai/src/agents/fundamental'
    for name in ('_cf015_fundamental','_cf015_fundamental.api','_cf015_fundamental.domain'):_package(name,root)
    for name,path in (('domain.contracts','domain/contracts.py'),('api.analysis_schemas','api/analysis_schemas.py'),('api.execution','api/execution.py'),('api.routes','api/routes.py')):
        full='_cf015_fundamental.'+name
        if full not in sys.modules:_module(full,'ai/src/agents/fundamental/'+path)
    app=FastAPI();app.include_router(sys.modules['_cf015_fundamental.api.routes'].make_router(engine));return app


def engine_result(request,*,report_id=None):
    rid=str(report_id or uuid4());req=request.request
    return dict(request_id=req.request_id,ticker=req.ticker,corp_name='합성 종목',verdict='자료 부족',verdict_label='보류',confidence=0.0,score=0,interpretation='합성 주입 결과',report_html='<script>not rendered</script>',ratios={'zero':0,'missing':None},extension={'integer':9007199254740993},
        meta=dict(trace_id=req.trace_id,erd_payload=dict(fundamental_report=dict(id=rid,stock_code=req.ticker,request_id=req.request_id,trace_id=req.trace_id,as_of=None,fin_score=0,confidence=0.0,data_status='insufficient',period_label=None),
            report_ratios=[dict(id=str(uuid4()),report_id=rid,ratio_name='synthetic',value=0,unit='ratio',status='insufficient')],report_evidence=[],
            report_interpretation=dict(id=str(uuid4()),report_id=rid,interpretation='합성 주입 결과',interpretation_source='synthetic'),
            report_verification=dict(id=str(uuid4()),report_id=rid,binding_passed=True,consistency_passed=True,verdict_stable=False,outcome='insufficient',regen_count=0),report_insights=[],report_filing_snippets=[])))


async def verify_fundamental(proof):
    with isolated_application(proof) as observed:
        try:result=await _verify(proof)
        except Exception as error:
            from scripts.cf002_interactive_login import safe_print
            tb=error.__traceback__;frames=[]
            while tb:
                if tb.tb_frame.f_code.co_filename==__file__:frames.append({'source':'fundamental_checker','line':tb.tb_lineno})
                tb=tb.tb_next
            safe_print({'phase':'cf015_checker_failure','type':type(error).__name__ if type(error).__name__ in {'VerificationFailure','RuntimeError','TimeoutError','IntegrityError'} else 'OTHER','frames':frames[-8:],'observed_denials':dict(observed)})
            raise
        check(not any(observed.values()),'CF015 forbidden access');result['observed_denials']=dict(observed);return result

# The integration implementation below runs only after owned preflight/migration.
async def _verify(proof):
    import httpx
    from fastapi import Request
    from contextlib import ExitStack
    from unittest.mock import patch
    from sqlalchemy import select,text,event
    from sqlalchemy.ext.asyncio import create_async_engine
    from alembic import command
    from alembic.config import Config
    from scripts.cf003_admission_check import migration
    from scripts.cf002_interactive_login import owned_session,safe_print,_BACKEND
    from db.session import get_session
    from db.models.auth.models import AuthUser
    from db.models.common.stock import Stock
    from db.models.fundamental.analysis_run import FundamentalAnalysisRun
    from src.api.main import app
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    from src.modules.auth.application.session_service import issue_session,csrf_token,revoke_session
    from src.modules.fundamental.api import analysis_router
    from src.modules.fundamental.application.analysis_adapter import FundamentalAnalysisAdapter
    from src.modules.fundamental.infrastructure import analysis_repository as repo
    from src.modules.fundamental.domain.analysis import canonical,sha,stored_response
    groups=[];calls={};mode='normal';chosen=None;commit_mode=None;fail_stage=False;rejections=0
    barrier_count=0;barrier=asyncio.Event();held=asyncio.Event();release=asyncio.Event();dispatch_lock=asyncio.Lock()
    TOKEN='cf015-public-synthetic-service-token-32bytes'
    def mark(label):groups.append(label);safe_print({'phase':'cf015_check','label':label,'status':'passed'})
    async def sql(statement,params=None):
        async with owned_session(proof) as session:return await session.scalar(text(statement),params or {})
    async def request_session(request:Request):
        async with owned_session(proof) as session:
            original=session.commit;n=0;selected=commit_mode
            async def commit():
                nonlocal n
                n+=1
                if mode=='replay_first' and request.method=='POST' and n==1:
                    held.set();await asyncio.wait_for(release.wait(),5)
                if selected and n==selected[0]:
                    if selected[1]=='ack':await original()
                    raise OSError('synthetic commit boundary')
                await original()
            session.commit=commit;yield session
    def engine(request):
        key=str(request.analysis_id);calls[key]=calls.get(key,0)+1
        check(calls[key]==1,'CF015 one engine per grant')
        if mode=='engine_failure':raise RuntimeError('synthetic engine failure')
        if mode=='invalid_output':return {'invalid':'synthetic'}
        result=engine_result(request,report_id=chosen)
        if mode=='cross_reference':result['meta']['erd_payload']['report_evidence']=[dict(id=str(uuid4()),report_id=result['meta']['erd_payload']['fundamental_report']['id'],ratio_id=str(uuid4()))]
        if mode=='omitted_lists':
            for name in ('report_ratios','report_evidence','report_insights','report_filing_snippets'):result['meta']['erd_payload'].pop(name,None)
        return result
    ai=fundamental_app(engine);client_type=analysis_router.AIClient
    def client(*args,**kwargs):
        value=client_type(*args,**kwargs,transport=httpx.ASGITransport(app=ai));original=value.analyze_fundamental
        async def analyze(request):
            nonlocal barrier_count
            async with dispatch_lock:result=await original(request)
            if mode=='revoke':
                async with owned_session(proof) as session:await revoke_session(session,pr)
            if mode=='race_report':
                barrier_count+=1
                if barrier_count==2:barrier.set()
                await asyncio.wait_for(barrier.wait(),5)
            return result
        value.analyze_fundamental=analyze;return value
    original_stage=FundamentalAnalysisAdapter.stage
    async def stage(adapter,session,principal,frozen):
        result=await original_stage(adapter,session,principal,frozen)
        if mode=='delete_finalize':held.set();await asyncio.wait_for(release.wait(),5)
        if fail_stage:raise RuntimeError('synthetic post-flush rollback')
        return result
    from src.modules.fundamental.infrastructure import report_repository as fr_repo
    from src.modules.reports.infrastructure import agent_report_repository as agent_repo
    original_add=fr_repo.add_report;original_index=agent_repo.add;original_delete=fr_repo.delete_agent_index
    async def add_report(session,**values):
        if mode=='publication_root_conflict':held.set();await asyncio.wait_for(release.wait(),5)
        return await original_add(session,**values)
    async def add_index(session,value):
        if mode=='publication_index_conflict' and value.agent_type=='fundamental':held.set();await asyncio.wait_for(release.wait(),5)
        return await original_index(session,value)
    async def delete_index(session,id):
        if mode=='delete_first':held.set();await asyncio.wait_for(release.wait(),5)
        return await original_delete(session,id)
    def body(**change):return dict(ticker='005930',question='합성 재무 경계',idempotency_key=str(uuid4()),allow_analysis=True)|change
    async def call(method,path='/api/fundamental/analyses',*,value=None,raw=None,other=False,revoked=False,headers=None):
        token,principal=(tr,pr) if revoked else (tb,pb) if other else (ta,pa)
        forwarded={'origin':'http://localhost:3200','cookie':auth.SESSION_COOKIE+'='+token,'x-csrf-token':csrf_token(principal)}|(headers or {})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8200') as client:
            return await client.request(method,path,json=value,content=raw,headers=forwarded)
    def response(value,status,code=None):
        nonlocal rejections
        check(value.status_code==status,'CF015 HTTP status')
        check(value.headers.get('cache-control')=='private, no-store' and {'cookie','origin'}<={v.strip().lower() for v in value.headers.get('vary','').split(',')},'CF015 private response')
        if code:
            rejections+=1;data=value.json();check(data['error']['code']==code and data['data'] is None,'CF015 safe error');return None
        return value.json()['data']
    async def ledger(key,owner=None):
        async with owned_session(proof) as session:return await repo.by_key(session,owner or pa.user_id,hashlib.sha256(key.encode()).digest())
    async def count_reports(id):return await sql('SELECT count(*) FROM fundamental_reports WHERE id=:id',{'id':UUID(str(id))})
    async def prior_rows():
        return [await sql("SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY id)::text,'[]') FROM "+table+' r') for table in ('fundamental_reports','agent_reports','flow_reports','flow_analysis_runs','flow_runs','flow_input_snapshots','flow_fake_executions')]
    check(await sql('SELECT version_num FROM alembic_version')=='c15001a7e0001','CF015 exact revision')
    await migration(proof,'c12001a7e0001',downgrade=True)
    async with owned_session(proof) as session:
        a,b=AuthUser(id=uuid4()),AuthUser(id=uuid4());session.add_all([a,b]);await session.flush()
        ta,pa=await issue_session(session,a);tb,pb=await issue_session(session,b);tr,pr=await issue_session(session,a)
        session.add(Stock(stock_code='005930',stock_name=' 합성 종목 '));await session.flush()
        legacy_id=uuid4();legacy_index=uuid4()
        await session.execute(text('INSERT INTO fundamental_reports(id,stock_code,created_at) VALUES(:id,\'005930\',clock_timestamp())'),{'id':legacy_id})
        await session.execute(text("INSERT INTO agent_reports(id,agent_type,agent_report_id,created_at) VALUES(:id,'fundamental',:rid,clock_timestamp())"),{'id':legacy_index,'rid':legacy_id})
        await session.commit()
    before=await prior_rows();injected=[]
    await proof.preflight();db=create_async_engine(proof.url,connect_args=proof.connection_parameters())
    try:
        async with db.connect() as connection:
            await proof.attest_connection(connection)
            def apply(sync):
                def fail(conn,cursor,statement,params,context,many):
                    if statement.lstrip().upper().startswith('CREATE TABLE FUNDAMENTAL_ANALYSIS_RUNS'):
                        injected.append(True);raise RuntimeError('CF015 exact DDL injection')
                config=Config(str(_BACKEND/'alembic.ini'));config.set_main_option('script_location',str(_BACKEND/'db/migrations'));config.attributes.update(connection=sync,verified_test_mode=True)
                event.listen(sync,'after_cursor_execute',fail)
                try:command.upgrade(config,'head')
                finally:event.remove(sync,'after_cursor_execute',fail)
            try:await connection.run_sync(apply)
            except RuntimeError:await connection.rollback()
            else:raise RuntimeError('CF015 expected rollback')
        check(injected==[True] and await sql("SELECT to_regclass('fundamental_analysis_runs')") is None,'CF015 exact DDL rollback')
    finally:await db.dispose()
    check(before==await prior_rows(),'CF015 old rows after rollback')
    await migration(proof,'head')
    # owner column is the only intentional old-row schema difference.
    check(await sql('SELECT owner_user_id FROM fundamental_reports WHERE id=:id',{'id':legacy_id}) is None,'CF015 legacy owner remains NULL')
    await migration(proof,'c12001a7e0001',downgrade=True);check(before==await prior_rows(),'CF015 empty downgrade preserves legacy');await migration(proof,'head')
    mark('migration_rollback_empty_downgrade_and_NULL_legacy')
    previous=dict(app.dependency_overrides);app.dependency_overrides[get_session]=request_session
    try:
      with ExitStack() as stack:
        for target,name,value in ((settings,'AI_SERVICE_URL','http://synthetic.invalid'),(settings,'FUNDAMENTAL_ANALYSIS_ENABLED',True),(settings,'FUNDAMENTAL_SERVICE_TOKEN',TOKEN),(analysis_router,'AIClient',client),(FundamentalAnalysisAdapter,'stage',stage)):stack.enter_context(patch.object(target,name,value))
        stack.enter_context(patch.object(fr_repo,'add_report',add_report));stack.enter_context(patch.object(agent_repo,'add',add_index));stack.enter_context(patch.object(fr_repo,'delete_agent_index',delete_index))
        stack.enter_context(patch.dict('os.environ',{'FUNDAMENTAL_ANALYSIS_ENABLED':'true','FUNDAMENTAL_SERVICE_TOKEN':TOKEN}))
        for change in ({'allow_analysis':1},{'as_of':'2026-01-01'},{'owner_user_id':str(pa.user_id)},{'ticker':'１２３４５６'}):response(await call('POST',value=body(**change)),422,'INPUT_INVALID')
        for raw in (b'['*1100+b']'*1100,b'{"ticker":"005930","ticker":"005930"}',b'{"x":NaN}',b'{"idempotency_key":"x\xff"}'):
            response(await call('POST',raw=raw,headers={'content-type':'application/json'}),422,'INPUT_INVALID')
        for headers,status,code in (({'cookie':''},401,'AUTH_REQUIRED'),({'x-csrf-token':'invalid'},401,'AUTH_REQUIRED'),({'origin':'https://external.invalid'},401,'AUTH_REQUIRED'),({'host':'127.0.0.1:8200'},403,'AUTH_REQUEST_INVALID')):response(await call('POST',value=body(),headers=headers),status,code)
        for method,path in (('POST','/api/fundamental/reports'),('POST','/api/fundamental/reports/save'),('DELETE','/api/fundamental/reports'),('GET','/api/fundamental/reports/'+str(legacy_id)+'/html')):response(await call(method,path,value={} if method=='POST' else None),403,'FEATURE_UNAVAILABLE')
        mark('strict_input_real_session_CSRF_and_closed_legacy')

        first_body=body();first=response(await call('POST',value=first_body),200);rid=UUID(first['report_id']);aid=first['analysis_id']
        check(first['state']=='stored' and calls[aid]==1,'CF015 stored engine1')
        original=await ledger(first_body['idempotency_key']);frozen=(original.input_json,original.result_json,original.input_sha256,original.result_sha256,original.as_of)
        check(response(await call('POST',value=first_body),200)==first,'CF015 replay same grant');check(response(await call('GET','/api/fundamental/analyses/'+aid),200)==first,'CF015 same URL')
        response(await call('POST',value=first_body|{'question':'different'}),409,'IDEMPOTENCY_CONFLICT')
        detail=await call('GET','/api/fundamental/reports/'+str(rid));check(detail.status_code==200 and detail.json()['report']==__import__('json').loads(original.result_json),'CF015 raw snapshot reader')
        check(detail.json()['report']['extension']['integer']==9007199254740993,'CF015 raw precision')
        for path in ('/api/fundamental/analyses/'+aid,'/api/fundamental/reports/'+str(rid),'/api/fundamental/reports/'+str(legacy_id)):
            response(await call('GET',path,other=True),404,'RESOURCE_NOT_FOUND')
        listing=await call('GET','/api/fundamental/reports?limit=1&offset=0');check(listing.status_code==200 and listing.json()['count']==1 and len(listing.json()['items'])==1,'CF015 SQL owner count before pagination')
        other=await call('GET','/api/fundamental/reports?limit=1&offset=0',other=True);check(other.status_code==200 and other.json()['count']==0,'CF015 other owner count0')
        response(await call('DELETE','/api/fundamental/reports/'+str(rid),other=True),404,'RESOURCE_NOT_FOUND')
        race=body();parallel=await asyncio.gather(call('POST',value=race),call('POST',value=race));check(all(v.status_code in {200,202} for v in parallel),'CF015 key race status')
        ids={v.json()['data']['analysis_id'] for v in parallel};check(len(ids)==1 and calls[next(iter(ids))]==1,'CF015 key winner1')
        mode='omitted_lists';omitted=response(await call('POST',value=body()),200);mode='normal'
        check((await call('GET','/api/fundamental/reports/'+omitted['report_id'])).status_code==200,'CF015 optional lists and frozen name')
        mark('stored_raw_owner_list_count_detail_key_race')

        for number,kind in ((1,'ack'),(2,'before'),(2,'ack'),(3,'before'),(3,'ack')):
            request=body();seen=sum(calls.values());commit_mode=(number,kind)
            response(await call('POST',value=request),503,'SERVICE_UNAVAILABLE');commit_mode=None
            saved=await ledger(request['idempotency_key']);unresolved=number==1 or number==2 and kind=='before'
            check(saved.state==('running' if unresolved else 'result_ready' if number==2 or kind=='before' else 'stored'),'CF015 durable boundary')
            restored=response(await call('POST',value=request),202 if unresolved else 200)
            check(sum(calls.values())==seen+(0 if number==1 else 1),'CF015 ACK recovery no redispatch')
            check(restored['state']==('running' if unresolved else 'stored'),'CF015 snapshot-only recovery')
        fail_stage=True;retry=body();response(await call('POST',value=retry),503,'SERVICE_UNAVAILABLE');fail_stage=False
        saved=await ledger(retry['idempotency_key']);check(saved.state=='result_ready' and await count_reports(saved.adopted_report_id)==0,'CF015 all stage writes rollback')
        check(response(await call('POST',value=retry),200)['state']=='stored' and calls[str(saved.id)]==1,'CF015 stage recovery AI0')
        mark('claim_snapshot_publish_ACK_and_flush_rollback')

        for mode,expected in (('engine_failure','unknown'),('invalid_output','failed'),('cross_reference','failed')):
            result=response(await call('POST',value=body()),202 if expected=='unknown' else 200)
            check(result['state']==expected and result['report_id'] is None,'CF015 engine error ledger classification')
        mode='normal'
        chosen=legacy_id;conflicting=body();response(await call('POST',value=conflicting),409,'RESULT_CONFLICT')
        conflict=await ledger(conflicting['idempotency_key']);check(conflict.state=='failed' and conflict.error_code=='RESULT_CONFLICT','CF015 legacy collision terminal')
        check(await count_reports(legacy_id)==1,'CF015 legacy root preserved');response(await call('POST',value=conflicting),200)
        chosen=uuid4();mode='race_report'
        one,two=body(),body()
        # Both independently dispatched responses meet before snapshot acceptance.
        results=await asyncio.gather(call('POST',value=one),call('POST',value=two,other=True));mode='normal'
        check(all(v.status_code==200 for v in results),'CF015 report race response')
        states=[v.json()['data']['state'] for v in results];check(sorted(states)==['failed','stored'],'CF015 named unique loser terminal')
        winner=next(v.json()['data'] for v in results if v.json()['data']['state']=='stored');winner_other=results[1].json()['data']['state']=='stored'
        check(await count_reports(chosen)==1,'CF015 report race root1')
        deleted=await call('DELETE','/api/fundamental/reports/'+str(chosen),other=winner_other);check(deleted.status_code==204,'CF015 race winner deletion')
        reused=response(await call('POST',value=body()),200);check(reused['state']=='failed' and reused['error']['code']=='RESULT_CONFLICT' and await count_reports(chosen)==0,'CF015 deleted ledger ID cannot be reused')
        chosen=None
        mark('engine_failure_cross_reference_and_report_UUID_races')

        for conflict_kind in ('publication_root_conflict','publication_index_conflict'):
            mode=conflict_kind;held.clear();release.clear();request=body();publishing=asyncio.create_task(call('POST',value=request));await asyncio.wait_for(held.wait(),5)
            report=await sql('SELECT adopted_report_id FROM fundamental_analysis_runs WHERE key_digest=:key',{'key':hashlib.sha256(request['idempotency_key'].encode()).digest()})
            async with owned_session(proof) as session:
                if conflict_kind=='publication_root_conflict':await session.execute(text('INSERT INTO fundamental_reports(id,created_at) VALUES(:id,clock_timestamp())'),{'id':report})
                else:
                    await session.execute(text("INSERT INTO agent_reports(id,agent_type,agent_report_id,owner_user_id,owner_session_id,created_at) VALUES(:id,'fundamental',:report,:owner,:session,clock_timestamp())"),{'id':uuid4(),'report':report,'owner':pb.user_id,'session':pb.session_id})
                await session.commit()
            release.set();response(await publishing,409,'RESULT_CONFLICT');mode='normal'
            saved=await ledger(request['idempotency_key']);check(saved.state=='failed' and saved.error_code=='RESULT_CONFLICT','CF015 publication unique collision terminal')
            response(await call('POST',value=request),200)
            check(await count_reports(report)==(1 if conflict_kind=='publication_root_conflict' else 0),'CF015 publication rollback preserves competing material')
        mark('publication_root_and_partial_index_uniqueness')

        for order in ('delete_first','replay_first'):
            request=body();stored=response(await call('POST',value=request),200);report=stored['report_id'];held.clear();release.clear();mode=order
            if order=='delete_first':
                primary=asyncio.create_task(call('DELETE','/api/fundamental/reports/'+report));await asyncio.wait_for(held.wait(),5)
                secondary=asyncio.create_task(call('POST',value=request));await asyncio.sleep(.03);check(not secondary.done(),'CF015 replay waits for delete run lock')
                release.set();check((await primary).status_code==204,'CF015 delete first');response(await secondary,404,'RESOURCE_NOT_FOUND')
            else:
                primary=asyncio.create_task(call('POST',value=request));await asyncio.wait_for(held.wait(),5)
                secondary=asyncio.create_task(call('DELETE','/api/fundamental/reports/'+report));await asyncio.sleep(.03);check(not secondary.done(),'CF015 delete waits for replay run lock')
                release.set();check(response(await primary,200)['state']=='stored','CF015 replay first');check((await secondary).status_code==204,'CF015 delete after replay')
            mode='normal';check(await count_reports(report)==0,'CF015 crossing deletion removed root')
            response(await call('POST',value=request),404,'RESOURCE_NOT_FOUND')
        mark('stored_delete_replay_lock_crossing_both_orders')

        mode='revoke';request=body();response(await call('POST',value=request,revoked=True),401,'AUTH_REQUIRED');mode='normal'
        revoked_row=await ledger(request['idempotency_key']);check(revoked_row.state=='running' and revoked_row.adopted_report_id is None,'CF015 revoked session cannot accept result')
        held.clear();release.clear();mode='delete_finalize';request=body();task=asyncio.create_task(call('POST',value=request));await asyncio.wait_for(held.wait(),5)
        pending_report=await sql('SELECT adopted_report_id FROM fundamental_analysis_runs WHERE key_digest=:key',{'key':hashlib.sha256(request['idempotency_key'].encode()).digest()})
        response(await call('DELETE','/api/fundamental/reports/'+str(pending_report)),404,'RESOURCE_NOT_FOUND')
        release.set();finished=response(await task,200);mode='normal'
        check(finished['state']=='stored','CF015 deletion-before-visible-publication cannot adopt root')
        check((await call('DELETE','/api/fundamental/reports/'+str(pending_report))).status_code==204,'CF015 stored deletion')
        deleted=await ledger(request['idempotency_key']);check(deleted.state=='deleted' and deleted.deleted_at is not None and deleted.request_json is deleted.stock_name is deleted.input_json is deleted.result_json is None,'CF015 scrubbed tombstone')
        response(await call('POST',value=request),404,'RESOURCE_NOT_FOUND');response(await call('GET','/api/fundamental/analyses/'+finished['analysis_id']),404,'RESOURCE_NOT_FOUND')
        check(await count_reports(pending_report)==0 and await sql("SELECT count(*) FROM stocks WHERE stock_code='005930'")==1,'CF015 no resurrection and shared stock preserved')
        mark('session_revocation_delete_finalize_and_tombstone')

        # The existing Flow adapter/profile uses this exact coordinator, real
        # principal and its original SQL. No previous complete suite is nested.
        from scripts.cf012_analysis_check import flow_app,engine_result as flow_result
        from src.modules.flow.api import analysis_router as flow_router
        flow_calls={};flow_chosen=None
        def flow_engine(request,context):
            key=str(request.analysis_id);flow_calls[key]=flow_calls.get(key,0)+1
            return flow_result(request,context,report_id=flow_chosen)
        flow=flow_app(flow_engine);original_client=flow_router.AIClient
        def flow_client(*args,**kwargs):return original_client(*args,**kwargs,transport=httpx.ASGITransport(app=flow))
        with patch.object(settings,'FLOW_ANALYSIS_ENABLED',True),patch.object(settings,'FLOW_SERVICE_TOKEN',TOKEN),patch.object(flow_router,'AIClient',flow_client),patch.dict('os.environ',{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':TOKEN}):
            flow_body=body()|{'as_of':'2026-11-08T00:00:00Z'}
            first_flow=response(await call('POST','/api/flow/analyses',value=flow_body),200)
            check(first_flow['state']=='stored' and flow_calls[first_flow['analysis_id']]==1,'CF015 Flow coordinator publication')
            check(response(await call('POST','/api/flow/analyses',value=flow_body),200)==first_flow,'CF015 Flow coordinator replay')
            flow_chosen=UUID(first_flow['report_id'])
            response(await call('POST','/api/flow/analyses',value=body()|{'as_of':'2026-11-08T00:00:00Z'}),503,'SERVICE_UNAVAILABLE')
            # Publication conflict is a legacy root with no analysis-ledger claim;
            # preserve the distinct existing Flow accept-UNIQUE error above.
            from tests.fixtures.flow_payload import make_flow_payload
            from src.modules.flow.application.report_service import FlowReportService
            from src.modules.flow.api.schemas import FlowReportSaveRequest
            legacy_flow=make_flow_payload();flow_chosen=UUID(legacy_flow['report_id'])
            async with owned_session(proof) as session:await FlowReportService(session,principal=pa).save_report(FlowReportSaveRequest(payload=legacy_flow,question='합성 기존 Flow root'))
            response(await call('POST','/api/flow/analyses',value=body()|{'as_of':'2026-11-08T00:00:00Z'}),409,'RESULT_CONFLICT')
            check((await call('DELETE','/api/flow/reports/'+first_flow['report_id'])).status_code==204,'CF015 Flow coordinator deletion')
            response(await call('POST','/api/flow/analyses',value=flow_body),404,'RESOURCE_NOT_FOUND')
        mark('Flow_fixed_profile_publication_replay_collision_deletion')
        # New ledger constraints reject invalid rows without retaining writes.
        from sqlalchemy import insert,update,cast,DateTime
        from sqlalchemy.exc import IntegrityError
        async with owned_session(proof) as session:
            template=await session.scalar(select(FundamentalAnalysisRun).where(FundamentalAnalysisRun.state=='running').limit(1))
            template_values={column.key:getattr(template,column.key) for column in FundamentalAnalysisRun.__table__.columns}
        for change,expected in (({'owner_user_id':None},'23502'),({'owner_user_id':uuid4()},'23503'),({'attempt_id':template.attempt_id},'23505'),({'state':'stored'},'23514'),({'deadline_at':text("'infinity'::timestamptz")},'23514'),({'input_fingerprint':'0'*64},'23514')):
            values=template_values|dict(id=uuid4(),attempt_id=uuid4(),key_digest=uuid4().bytes*2)|change
            async with owned_session(proof) as session:
                try:await session.execute(insert(FundamentalAnalysisRun).values(**values))
                except IntegrityError as error:
                    check(getattr(getattr(error.orig,'__cause__',None),'sqlstate',None)==expected,'CF015 exact constraint SQLSTATE');await session.rollback()
                else:raise RuntimeError('CF015 expected constraint refusal')
        async with owned_session(proof) as session:
            try:await session.execute(update(FundamentalAnalysisRun).where(FundamentalAnalysisRun.id==template.id).values(attempt_id=uuid4()))
            except IntegrityError as error:
                check(getattr(getattr(error.orig,'__cause__',None),'sqlstate',None)=='23514','CF015 immutable identity SQLSTATE');await session.rollback()
            else:raise RuntimeError('CF015 expected immutable identity refusal')
        try:await migration(proof,'c12001a7e0001',downgrade=True)
        except RuntimeError as error:check(type(error) is RuntimeError and error.args==('Nonempty live analysis ledger cannot be downgraded',),'CF015 exact nonempty downgrade refusal')
        else:raise RuntimeError('CF015 nonempty downgrade must refuse')
        check(await sql('SELECT version_num FROM alembic_version')=='c15001a7e0001','CF015 nonempty downgrade unchanged')
        mark('new_ledger_constraints_and_nonempty_downgrade')
        check(all(n==1 for n in calls.values()) and all(n==1 for n in flow_calls.values()),'CF015 dispatch bounds')
        check(await sql('SELECT count(*) FROM fundamental_reports WHERE id=:id AND owner_user_id IS NULL',{'id':legacy_id})==1,'CF015 legacy NULL preserved')
        final_original=await ledger(first_body['idempotency_key'])
        check((final_original.input_json,final_original.result_json,final_original.input_sha256,final_original.result_sha256,final_original.as_of)==frozen,'CF015 original frozen bytes unchanged')
        safe_print({'phase':'cf015_counts','analyses':len(calls),'dispatches':sum(calls.values()),'flow_analyses':len(flow_calls),'flow_dispatches':sum(flow_calls.values()),'rejections':rejections})
    finally:app.dependency_overrides.clear();app.dependency_overrides.update(previous)
    return {'groups':groups,'analyses':len(calls),'dispatches':sum(calls.values()),'rejections':rejections,'status':'passed'}
