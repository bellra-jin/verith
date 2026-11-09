"""One owned-PG accounting check. Real sessions/ASGI; no providers or private env."""
import asyncio,copy,hashlib,json,sys
from contextlib import ExitStack
from datetime import UTC,datetime,timedelta
from types import SimpleNamespace as NS
from unittest.mock import patch
from uuid import UUID,uuid4
from scripts.cf003_admission_check import check,isolated_application


class InjectedUsageDDL(RuntimeError):pass


async def usage_migration(proof,target,*,downgrade=False,inject=False):
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine
    from alembic import command
    from alembic.config import Config
    from scripts.cf002_interactive_login import _BACKEND
    await proof.preflight();engine=create_async_engine(proof.url,connect_args=proof.connection_parameters());reached=[]
    try:
        async with engine.connect() as connection:
            await proof.attest_connection(connection)
            def apply(sync):
                def after(conn,cursor,statement,parameters,context,executemany):
                    if inject and statement.lstrip().upper().startswith('CREATE TABLE ANALYSIS_USAGE_PERIODS'):
                        reached.append(True);raise InjectedUsageDDL('fixed new accounting DDL injection')
                config=Config(str(_BACKEND/'alembic.ini'));config.set_main_option('script_location',str(_BACKEND/'db/migrations'))
                config.attributes.update(connection=sync,verified_test_mode=True)
                if inject:event.listen(sync,'after_cursor_execute',after)
                try:(command.downgrade if downgrade else command.upgrade)(config,target)
                finally:
                    if inject:event.remove(sync,'after_cursor_execute',after)
            try:await connection.run_sync(apply);await connection.commit()
            except InjectedUsageDDL:
                await connection.rollback();check(reached==[True],'CF018 exact new DDL hook');return
            except Exception:await connection.rollback();raise
        check(not inject,'CF018 DDL injection must execute')
    finally:await engine.dispose()


async def verify_usage(proof):
    with isolated_application(proof) as observed:
        try:result=await _verify(proof)
        except Exception as error:
            # Only exception classes/SQLSTATE, never DB text, parameters or Env.
            kinds={'ProgrammingError','DataError','IntegrityError','StatementError','VerificationFailure'}
            code=getattr(getattr(error,'orig',None),'sqlstate',None)
            if code is None:code=getattr(getattr(getattr(error,'orig',None),'__cause__',None),'sqlstate',None)
            from scripts.cf002_interactive_login import safe_print
            safe_print({'phase':'cf018_checker_failure','kind':type(error).__name__ if type(error).__name__ in kinds else 'UNKNOWN',
                'sqlstate':code if isinstance(code,str) and len(code)==5 and code.isascii() and code.isalnum() else 'UNKNOWN'})
            raise
        check(not any(observed.values()),'CF018 forbidden access')
        return result|{'observed_denials':dict(observed)}


async def _verify(proof):
    import httpx
    from sqlalchemy import select,text,insert,update
    from sqlalchemy.exc import IntegrityError
    from db.models.auth.models import AuthUser
    from db.models.common.stock import Stock
    from db.models.flow.analysis_run import FlowAnalysisRun
    from db.models.common.analysis_usage import AnalysisUsagePeriod as Period,AnalysisUsageReservation as Reservation,AnalysisProviderCall as Call
    from db.session import get_session
    from src.api.main import app
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    from src.modules.auth.application.session_service import issue_session,csrf_token,revoke_session
    from src.modules.flow.api import analysis_router
    from src.modules.flow.api.schemas import FlowReportSaveRequest
    from src.modules.flow.application.report_service import FlowReportService
    from src.modules.flow.application.analysis_service import AnalysisService,AnalysisError
    from src.modules.analysis.application.usage_service import FlowUsageControl
    from src.modules.analysis.domain import usage as u
    from src.modules.flow.domain import analysis as flow
    from scripts.cf002_interactive_login import owned_session,safe_print
    from scripts.cf012_analysis_check import flow_app,engine_result,zero_call_usage
    from tests.fixtures.flow_payload import make_flow_payload
    groups=[];dispatch={};captured={};mode='normal';commit_mode=None;clock_offset=timedelta();rejections=0;sql_rejections=0
    held=asyncio.Event();release=asyncio.Event();current_session=None
    def phase(name):safe_print({'phase':'cf018_check','label':name,'status':'started'})
    def mark(name):groups.append(name);safe_print({'phase':'cf018_check','label':name,'status':'passed'})
    async def sql(statement,params=None):
        async with owned_session(proof) as session:return await session.scalar(text(statement),params or {})
    async def user():
        async with owned_session(proof) as session:
            value=AuthUser(id=uuid4());session.add(value);await session.flush();token,principal=await issue_session(session,value);await session.commit()
            return token,principal
    async def request_session():
        async with owned_session(proof) as session:
            original=session.commit;original_scalar=session.scalar;number=0;failure=commit_mode;offset=clock_offset;admission_clock_shifted=False
            async def commit():
                nonlocal number
                number+=1
                if failure and number==failure[0]:
                    if failure[1]=='ack':await original()
                    raise OSError('fixed synthetic commit boundary')
                await original()
            async def scalar(statement,*args,**kwargs):
                nonlocal admission_clock_shifted
                result=await original_scalar(statement,*args,**kwargs)
                columns=list(getattr(statement,'selected_columns',[]))
                if offset and not admission_clock_shifted and len(columns)==1 and getattr(columns[0],'name',None)=='clock_timestamp':
                    admission_clock_shifted=True;return result-offset
                return result
            session.commit=commit;session.scalar=scalar
            yield session
    def body(**changes):return dict(ticker='005930',question='합성 한도 검증',as_of='2026-11-08T00:00:00Z',idempotency_key=str(uuid4()),allow_analysis=True)|changes
    async def call(method,path='/api/flow/analyses',*,value=None,identity=None,headers=None):
        token,principal=identity or primary
        h={'origin':'http://localhost:3200','cookie':auth.SESSION_COOKIE+'='+token,'x-csrf-token':csrf_token(principal)}|(headers or {})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8200') as client:
            return await client.request(method,path,json=value,headers=h)
    def response(value,status,code=None):
        nonlocal rejections
        if value.status_code!=status:
            safe_print({'phase':'cf018_response_failure','expected_status':status,'actual_status':value.status_code})
        check(value.status_code==status,'CF018 exact HTTP status')
        check(value.headers.get('cache-control')=='private, no-store' and {'cookie','origin'}<={v.strip().lower() for v in value.headers.get('vary','').split(',')},'CF018 private headers')
        result=value.json();UUID(result['request_id']);check(set(result)=={'request_id','data','error'},'CF018 envelope')
        if code:check(result['data'] is None and result['error']['code']==code,'CF018 fixed error');rejections+=1
        else:check(result['error'] is None,'CF018 success')
        return result['data']
    async def ledger(key):
        async with owned_session(proof) as session:return await session.scalar(select(FlowAnalysisRun).where(FlowAnalysisRun.key_digest==hashlib.sha256(key.encode()).digest()))
    async def accounting(id):
        async with owned_session(proof) as session:return await session.get(Reservation,UUID(str(id)))
    async def totals():return tuple([await sql('SELECT count(*) FROM '+table) for table in ('flow_analysis_runs','analysis_usage_reservations','analysis_provider_calls')])
    async def old_bytes():
        return [await sql("SELECT coalesce(jsonb_agg(to_jsonb(r)-'budget_reservation_id' ORDER BY id)::text,'[]') FROM "+table+' r') for table in ('flow_analysis_runs','flow_reports','agent_reports')]
    async def observe_original(self,row,grant,envelope):
        captured[str(row.id)]=(copy.copy(row),grant,copy.deepcopy(envelope))
        return await original_observe(self,row,grant,envelope)
    def engine(request,context):
        result=engine_result(request,context)
        if mode=='unavailable':raise ValueError('synthetic provider unavailable')
        if mode!='zero':
            identity=context.begin_call('openai','completion',input_bytes=100)
            metadata=None if mode in {'missing','anomaly'} else {'input_tokens':100,'output_tokens':10,'total_tokens':110}
            context.openai_observed(identity,NS(usage_metadata=metadata,response_metadata={'model_name':'other-model' if mode=='anomaly' else 'gpt-5.4-mini'}))
        if mode=='invalid_payload':result['payload']['meta']['ticker']='000001'
        return result
    ai=flow_app(engine);original_client=analysis_router.AIClient
    def client(*args,**kwargs):
        value=original_client(*args,**kwargs,transport=httpx.ASGITransport(app=ai));original=value.analyze_flow
        async def analyze(payload):
            selected=mode;id=payload['analysis_id'];dispatch[id]=dispatch.get(id,0)+1;check(dispatch[id]==1,'CF018 dispatch once')
            if selected in {'cancel','same_key'}:held.set();await release.wait()
            result=await original(payload)
            if selected=='revoke':
                async with owned_session(proof) as session:await revoke_session(session,current_session[1])
            if selected=='late':await asyncio.sleep(.45)
            return result
        value.analyze_flow=analyze;return value

    phase('migration_rollback_legacy_and_empty_downgrade')
    check(await sql('SELECT version_num FROM alembic_version')=='c15001a7e0001','CF018 exact parent revision')
    primary=await user();other=await user()
    async with owned_session(proof) as session:
        session.add(Stock(stock_code='005930',stock_name='합성 종목'));await session.commit()
    legacy_keys=[];legacy_stored_id=None
    for state in ('stored','result_ready'):
        token,principal=primary;payload=make_flow_payload();payload['meta'].update(ticker='005930',stock_name='합성 종목')
        key=str(uuid4());legacy_keys.append(key);stamp=await sql('SELECT clock_timestamp()');as_of=datetime(2026,11,8,tzinfo=UTC)
        normalized=flow.canonical({'ticker':'005930','question':'합성 한도 검증','as_of':as_of.isoformat()});id,attempt,admission=uuid4(),uuid4(),uuid4()
        row=NS(id=id,attempt_id=attempt,admission_request_id=admission,input_fingerprint=flow.sha(normalized),ticker='005930',stock_name='합성 종목',request_json=normalized,
            as_of=as_of,candidate_date=flow.candidate(as_of),deadline_at=stamp+timedelta(seconds=120),spec_json=flow.canonical(flow.LEGACY_SPEC))
        request=flow.ai_request(row);day=payload['meta']['base_date'];frames={n:[{k:day if k=='date' else 0 for k in units}] for n,units in flow.UNITS.items()}
        snapshot={'schema_version':1,'request':request,'source':'kis.boundary.frames.v1','observed_at':stamp.isoformat(),'confirmed_date':day,'units':flow.UNITS,'frames':frames}
        async with owned_session(proof) as session:
            values=dict(id=id,owner=principal.user_id,key=hashlib.sha256(key.encode()).digest(),fp=row.input_fingerprint,admission=admission,attempt=attempt,stamp=stamp,
                as_of=as_of,candidate=row.candidate_date,request=normalized,spec=row.spec_json,claim=b'x'*32)
            # Typed Core INSERT deliberately omits the post-parent budget column.
            # A separate typed deadline avoids ambiguous raw timestamp+interval binds.
            await session.execute(FlowAnalysisRun.__table__.insert().values(id=id,owner_user_id=principal.user_id,operation='flow.analysis.v1',
                key_digest=values['key'],input_fingerprint=row.input_fingerprint,admission_request_id=admission,attempt_id=attempt,
                ticker='005930',stock_name='합성 종목',as_of=as_of,candidate_date=row.candidate_date,request_json=normalized,
                spec_json=row.spec_json,claim_digest=values['claim'],started_at=stamp,deadline_at=stamp+timedelta(seconds=120),state='running'))
            await session.execute(text("""UPDATE flow_analysis_runs SET state='result_ready',adopted_report_id=:report,input_json=:input,result_json=:result,input_sha256=:ih,result_sha256=:rh,accepted_at=:stamp WHERE id=:id"""),
                dict(id=id,report=UUID(payload['report_id']),input=flow.canonical(snapshot),result=flow.canonical(payload),ih=flow.sha(flow.canonical(snapshot)),rh=flow.sha(flow.canonical(payload)),stamp=stamp))
            if state=='stored':
                legacy_stored_id=id
                await FlowReportService(session,principal=principal).stage_report(FlowReportSaveRequest(payload=payload,question='합성 이전 자료'))
                await session.execute(text("UPDATE flow_analysis_runs SET state='stored' WHERE id=:id"),{'id':id})
            await session.commit()
    legacy_frozen=await sql("SELECT jsonb_build_array(id,input_json,result_json,input_sha256,result_sha256,adopted_report_id)::text FROM flow_analysis_runs WHERE id=:id",{'id':legacy_stored_id})
    before=await old_bytes();await usage_migration(proof,'c18001a7e0001',inject=True)
    check(await sql("SELECT to_regclass('analysis_usage_periods')") is None and await old_bytes()==before,'CF018 DDL rollback preserves legacy')
    await usage_migration(proof,'c18001a7e0001');check(await old_bytes()==before,'CF018 upgrade preserves exact legacy bytes')
    check(await sql('SELECT count(*) FROM flow_analysis_runs WHERE budget_reservation_id IS NOT NULL')==0,'CF018 no legacy backfill')
    await usage_migration(proof,'c15001a7e0001',downgrade=True);check(await old_bytes()==before,'CF018 empty downgrade preserves legacy')
    await usage_migration(proof,'c18001a7e0001');mark('migration_rollback_legacy_and_empty_downgrade')

    original_observe=FlowUsageControl.observe
    app.dependency_overrides[get_session]=request_session
    with ExitStack() as stack:
        for name,value in {'FLOW_ANALYSIS_ENABLED':True,'AI_SERVICE_URL':'http://synthetic.invalid','FLOW_SERVICE_TOKEN':TOKEN,
            'FLOW_USAGE_LIMITS_ENABLED':'true','FLOW_SUPPORTED_TICKERS':'005930','FLOW_USER_DAILY_REQUEST_LIMIT':'2','FLOW_SERVICE_DAILY_REQUEST_LIMIT':'100','FLOW_SERVICE_DAILY_BUDGET_USD':'10'}.items():stack.enter_context(patch.object(settings,name,value))
        stack.enter_context(patch.object(analysis_router,'AIClient',client));stack.enter_context(patch.object(FlowUsageControl,'observe',observe_original))
        stack.enter_context(patch.dict('os.environ',{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':TOKEN}))
        phase('closed_defaults_legacy_and_auth_no_charge')
        with patch.object(settings,'FLOW_USAGE_LIMITS_ENABLED',{'malformed':True}),patch.object(settings,'FLOW_SERVICE_DAILY_BUDGET_USD',float('nan')):
            for key in legacy_keys:
                data=response(await call('POST',value=body(idempotency_key=key)),200);check(data['state']=='stored','CF018 old snapshot replay without settings')
            response(await call('POST',value=body()),403,'FEATURE_UNAVAILABLE')
        check(await sql('SELECT count(*) FROM analysis_usage_reservations')==0,'CF018 denied no reservation')
        response(await call('POST',value=body(ticker='000001')),403,'FEATURE_UNAVAILABLE')
        response(await call('POST',value=body(),headers={'cookie':''}),401,'AUTH_REQUIRED')
        response(await call('POST',value=body(),headers={'x-csrf-token':'invalid'}),401,'AUTH_REQUIRED')
        mark('closed_defaults_legacy_and_auth_no_charge')

        phase('same_key_user_and_service_races')
        first=body();held.clear();release.clear();mode='same_key'
        before_count=await totals()
        winner=asyncio.create_task(call('POST',value=first))
        await asyncio.wait_for(held.wait(),10) # Claim ACK committed; dispatch held before AI.
        loser=response(await call('POST',value=first),202)
        first_row=await ledger(first['idempotency_key']);first_res=await accounting(first_row.id)
        check(loser['analysis_id']==str(first_row.id) and loser['state']=='running','CF018 loser observes same committed claim')
        check(await totals()==tuple(n+d for n,d in zip(before_count,(1,1,9))),'CF018 race one run/reservation/slots')
        check(dispatch[str(first_row.id)]==1 and first_res.remaining_nano==u.RUN_RESERVE,'CF018 race single dispatch held')
        for bucket in (first_res.user_period_id,first_res.service_period_id):
            check(await sql('SELECT request_count FROM analysis_usage_periods WHERE id=:id',{'id':bucket})==1,'CF018 race one counter increment')
        release.set();first_view=response(await winner,200);mode='normal'
        final=response(await call('GET','/api/flow/analyses/'+str(first_row.id)),200)
        first_res=await accounting(first_row.id)
        check(first_view==final and final['state']=='stored' and dispatch[str(first_row.id)]==1 and first_res.remaining_nano==0,'CF018 race final GET convergence')
        count_before=await totals();response(await call('GET','/api/flow/analyses/'+str(first_row.id),identity=other),404,'RESOURCE_NOT_FOUND')
        response(await call('POST',value=first|{'question':'different'}),409,'IDEMPOTENCY_CONFLICT')
        check(await totals()==count_before,'CF018 owner/conflict no charge')
        race=[body(),body()];result=await asyncio.gather(*(call('POST',value=b) for b in race))
        check(sorted(r.status_code for r in result)==[200,429],'CF018 user boundary race')
        response(next(r for r in result if r.status_code==429),429,'USAGE_LIMIT_EXCEEDED')
        check(sum([await ledger(b['idempotency_key']) is not None for b in race])==1,'CF018 refused race has no run')
        # A different admission period is a controlled server-clock fixture, not as_of.
        clock_offset=timedelta(days=1)
        with patch.object(settings,'FLOW_SERVICE_DAILY_REQUEST_LIMIT','1'):
            c,d=await user(),await user();request_c,request_d=body(),body()
            result=await asyncio.gather(call('POST',value=request_c,identity=c),call('POST',value=request_d,identity=d))
            check(sorted(r.status_code for r in result)==[202,429],'CF018 service period boundary race')
            response(next(r for r in result if r.status_code==429),429,'USAGE_LIMIT_EXCEEDED')
        clock_offset=timedelta();mark('same_key_user_and_service_races')

        phase('claim_settlement_snapshot_publication_ACK_and_cancel')
        for commit_no in (1,2,3,4):
            identity=await user();request=body();commit_mode=(commit_no,'ack')
            response(await call('POST',value=request,identity=identity),503,'SERVICE_UNAVAILABLE');commit_mode=None
            saved=await ledger(request['idempotency_key']);res=await accounting(saved.id);prior_count=dispatch.get(str(saved.id),0)
            restored=response(await call('POST',value=request,identity=identity),202 if commit_no<3 else 200)
            check(dispatch.get(str(saved.id),0)==prior_count,'CF018 ACK replay no dispatch')
            if commit_no==1:check(prior_count==0 and res.remaining_nano==u.RUN_RESERVE,'CF018 uncertain claim hold')
            if commit_no==2:
                old_spend=res.estimated_spend_nano;source,grant,envelope=captured[str(saved.id)]
                async with owned_session(proof) as session:await original_observe(FlowUsageControl(session,AnalysisError),source,grant,envelope)
                check((await accounting(saved.id)).estimated_spend_nano==old_spend,'CF018 settlement ACK exact retry once')
            if commit_no>=3:check(restored['state']=='stored' and res.remaining_nano==0,'CF018 snapshot/publication restore no charge')
        identity=await user();request=body();before_count=await totals();commit_mode=(1,'rollback')
        response(await call('POST',value=request,identity=identity),503,'SERVICE_UNAVAILABLE');commit_mode=None
        check(await totals()==before_count and await ledger(request['idempotency_key']) is None,'CF018 confirmed rollback leaves zero')
        response(await call('POST',value=request,identity=identity),200)
        identity=await user();request=body();mode='cancel';held.clear();release.clear()
        task=asyncio.create_task(call('POST',value=request,identity=identity));await asyncio.wait_for(held.wait(),10);task.cancel()
        try:await task
        except asyncio.CancelledError:pass
        release.set();mode='normal';saved=await ledger(request['idempotency_key'])
        check((await accounting(saved.id)).remaining_nano==u.RUN_RESERVE,'CF018 cancelled request retains reservation')
        mark('claim_settlement_snapshot_publication_ACK_and_cancel')

        phase('usage_before_invalid_result_auth_and_late_publication')
        for selected in ('invalid_payload','revoke','late','missing'):
            identity=await user();current_session=identity;request=body();mode=selected
            if selected=='late':clock_offset=timedelta(seconds=119.7)
            raw=await call('POST',value=request,identity=identity);clock_offset=timedelta();mode='normal'
            if selected=='revoke':response(raw,401,'AUTH_REQUIRED')
            else:
                data=response(raw,202 if selected=='late' else 200)
                safe_print({'phase':'cf018_result_case','case':selected,'state':data['state'] if data['state'] in {'running','result_ready','stored','failed','unknown'} else 'UNKNOWN'})
                check(data['state']==('failed' if selected=='invalid_payload' else 'unknown' if selected=='late' else 'stored'),'CF018 result/auth/deadline kept')
            saved=await ledger(request['idempotency_key']);res=await accounting(saved.id)
            check(res.estimated_spend_nano==(0 if selected=='missing' else 120000),'CF018 independent usage settlement')
            check(res.remaining_nano==(u.CALL_RESERVE if selected=='missing' else 0),'CF018 missing usage is not zero cost')
            if selected=='missing':unknown_row=saved
        mark('usage_before_invalid_result_auth_and_late_publication')

        phase('attempt_monotonicity_and_first_confirmation')
        source,grant,original=captured[str(unknown_row.id)];before=await accounting(source.id)
        contrary=copy.deepcopy(original);contrary['input_snapshot']['provider_usage']['calls'][0]=zero_call_usage(NS(**flow.ai_request(source)))['calls'][0]
        try:
            async with owned_session(proof) as session:await original_observe(FlowUsageControl(session,AnalysisError),source,grant,contrary)
        except u.UsageConflict:pass
        else:check(False,'CF018 contradictory not_called must fail')
        check((await accounting(source.id)).remaining_nano==before.remaining_nano,'CF018 contradiction retains hold')
        # Exercise the DB's attempted monotonic guard while state is still unknown,
        # not merely the older final-evidence immutability branch.
        for attempted in ('FALSE','NULL'):
            async with owned_session(proof) as session:
                try:
                    await session.execute(text("UPDATE analysis_provider_calls SET attempted="+attempted+" WHERE reservation_id=:id AND provider='openai' AND ordinal=1"),{'id':source.id});await session.commit()
                except IntegrityError as error:
                    await session.rollback();check((getattr(error.orig,'sqlstate',None) or getattr(getattr(error.orig,'__cause__',None),'sqlstate',None))=='23514','CF018 unknown attempted monotonic SQLSTATE');sql_rejections+=1
                else:check(False,'CF018 attempted TRUE reversal must fail')
        confirmed=copy.deepcopy(original);confirmed['input_snapshot']['provider_usage']['calls'][0].update(state='observed',input_tokens=100,output_tokens=10,response_model='gpt-5.4-mini')
        for _ in range(2):
            async with owned_session(proof) as session:await original_observe(FlowUsageControl(session,AnalysisError),source,grant,confirmed)
        after=await accounting(source.id);check(after.remaining_nano==0 and after.estimated_spend_nano==120000,'CF018 first confirmation and duplicate no-op')
        mark('attempt_monotonicity_and_first_confirmation')

        phase('deletion_preserves_accounting_and_legacy_bytes')
        before=await accounting(first_row.id);response(await call('GET','/api/flow/analyses/'+str(first_row.id)),200)
        deleted=await call('DELETE','/api/flow/reports/'+first_view['report_id']);check(deleted.status_code==204,'CF018 owner deletion')
        response(await call('POST',value=first),404,'RESOURCE_NOT_FOUND')
        after=await accounting(first_row.id);check(after.estimated_spend_nano==before.estimated_spend_nano and after.remaining_nano==before.remaining_nano,'CF018 deletion not refund')
        check(await sql('SELECT request_json IS NULL AND input_json IS NULL AND result_json IS NULL FROM flow_analysis_runs WHERE id=:id',{'id':first_row.id}),'CF018 tombstone bodies removed')
        mark('deletion_preserves_accounting_and_legacy_bytes')

        phase('budget_cap_and_anomaly_blocks')
        # Fill only the remaining capacity with bounded injected unavailability;
        # each unique admission is a necessary real budget-boundary observation.
        mode='unavailable';last_identity=None
        for _ in range(16):
            last_identity=await user();raw=await call('POST',value=body(),identity=last_identity)
            if raw.status_code==429:response(raw,429,'USAGE_LIMIT_EXCEEDED');break
            data=response(raw,202);check(data['state']=='unknown','CF018 transport/provider loss hold')
        else:check(False,'CF018 bounded budget must stop new admission')
        mode='normal'
        # Independent anomaly checks use owned historical server-clock fixtures
        # so blocking one period cannot suppress the other required regressions.
        for day,anomaly in ((2,'model'),(3,'cap'),(4,'valid')):
            identity=await user();stamp=await sql('SELECT clock_timestamp()')-timedelta(days=day)
            value=NS(id=uuid4(),owner_user_id=identity[1].user_id,operation='flow.analysis.v1',attempt_id=uuid4(),admission_request_id=uuid4(),ticker='005930',stock_name='합성 종목',
                as_of=datetime(2026,11,8,tzinfo=UTC),candidate_date=flow.candidate(datetime(2026,11,8,tzinfo=UTC)),started_at=stamp,deadline_at=stamp+timedelta(seconds=120),state='running',
                key_digest=hashlib.sha256(str(uuid4()).encode()).digest(),spec_json=flow.canonical(flow.SPEC),request_json=flow.canonical({'ticker':'005930','question':'합성 한도 검증','as_of':datetime(2026,11,8,tzinfo=UTC).isoformat()}))
            value.input_fingerprint=flow.sha(value.request_json);grant=b'owned-synthetic-usage-grant';value.claim_digest=hashlib.sha256(grant).digest();value.budget_reservation_id=value.id
            async with owned_session(proof) as session:
                stored=FlowAnalysisRun(**vars(value));session.add(stored);await session.flush()
                control=FlowUsageControl(session,AnalysisError,settings);control.new_values(NS(ticker='005930'),{'id':value.id});await control.reserve(stored,stamp);await session.commit()
            req=sys.modules['_cf012_flow.api.schemas'].FlowAnalysisInput.model_validate(flow.ai_request(value))
            result=engine_result(req,None);trace=result['input_snapshot']['provider_usage'];trace['calls'][0].update(attempted=True,state='observed' if anomaly=='valid' else 'unknown',response_model='unapproved' if anomaly=='model' else 'gpt-5.4-mini',input_tokens=400001 if anomaly=='cap' else 100,cached_tokens=None if anomaly=='valid' else True,output_tokens=10 if anomaly=='valid' else None)
            envelope={'input_snapshot':result['input_snapshot']}
            if anomaly=='valid':
                from src.modules.analysis.infrastructure import usage_repository
                before_res=await accounting(value.id)
                old_ids=[before_res.service_period_id,before_res.user_period_id]
                now=await sql('SELECT clock_timestamp()');start,end=u.period(now)
                check(now>=u.period(stamp)[1],'CF018 receipt arrives after original day')
                async with owned_session(proof) as session:
                    next_service=await usage_repository.period(session,'service',None,start,end,request_limit=100,budget_limit=10000000000,user_request_limit=2)
                    next_user=await usage_repository.period(session,'user',value.owner_user_id,start,end,request_limit=next_service.user_request_limit,budget_limit=None)
                    new_ids=[next_service.id,next_user.id];await session.commit()
                async def bucket_values(ids):
                    return [await sql('SELECT jsonb_build_array(request_count,held_nano,estimated_spend_nano,blocked)::text FROM analysis_usage_periods WHERE id=:id',{'id':id}) for id in ids]
                old_before=[json.loads(v) for v in await bucket_values(old_ids)]
                new_before=await bucket_values(new_ids)
            async with owned_session(proof) as session:await original_observe(FlowUsageControl(session,AnalysisError),value,grant,envelope)
            res=await accounting(value.id)
            if anomaly=='valid':
                old_after=[json.loads(v) for v in await bucket_values(old_ids)]
                check(await bucket_values(new_ids)==new_before,'CF018 late receipt never mutates current-day buckets')
                check(all(after==[before[0],before[1]-u.RUN_RESERVE,before[2]+120000,before[3]] for before,after in zip(old_before,old_after)),'CF018 late receipt settles only original two buckets')
            if anomaly=='valid':
                check(res.state=='settled' and res.remaining_nano==0 and res.estimated_spend_nano==120000,'CF018 historical receipt settled once')
                check(await sql('SELECT period_start FROM analysis_usage_periods WHERE id=:id',{'id':res.service_period_id})==u.period(stamp)[0],'CF018 usage attributed to original period')
                async with owned_session(proof) as session:
                    view=await AnalysisService(session,principal=identity[1],client=None)._receive(value.id,grant,envelope)
                    check(view.state=='unknown' and view.report_id is None,'CF018 late accounting does not publish late result')
            else:
                check(res.state=='blocked' and res.remaining_nano==u.CALL_RESERVE and res.estimated_spend_nano==0,'CF018 independent anomaly blocked commit and hold')
                check(await sql('SELECT blocked FROM analysis_usage_periods WHERE id=:id',{'id':res.service_period_id}),'CF018 service bucket blocked')
                check(not u.valid_complete_usage(value,envelope),'CF018 anomalous usage cannot publish')
        mark('budget_cap_and_anomaly_blocks')

        phase('database_constraints_and_nonempty_downgrade')
        async def reject(statement,params=None,expected=('23514',)):
            nonlocal sql_rejections
            async with owned_session(proof) as session:
                try:await session.execute(text(statement),params or {});await session.commit()
                except IntegrityError as error:
                    await session.rollback();code=getattr(error.orig,'sqlstate',None) or getattr(getattr(error.orig,'__cause__',None),'sqlstate',None)
                    check(code in expected,'CF018 expected SQLSTATE');sql_rejections+=1
                else:check(False,'CF018 invalid SQL must fail')
        await reject('UPDATE analysis_usage_periods SET request_count=-1 WHERE id=:id',{'id':first_res.service_period_id})
        await reject('UPDATE analysis_usage_periods SET request_limit=request_limit+1 WHERE id=:id',{'id':first_res.service_period_id})
        await reject("UPDATE analysis_usage_reservations SET price_id='wrong' WHERE id=:id",{'id':first_row.id})
        await reject('UPDATE analysis_usage_reservations SET remaining_nano=-1 WHERE id=:id',{'id':first_row.id})
        await reject('UPDATE flow_analysis_runs SET budget_reservation_id=NULL WHERE id=:id',{'id':first_row.id})
        await reject('DELETE FROM analysis_usage_reservations WHERE id=:id',{'id':first_row.id})
        # Final observed slots are immutable, including true -> false / NULL.
        for attempted in ('FALSE','NULL'):
            await reject('UPDATE analysis_provider_calls SET attempted='+attempted+' WHERE reservation_id=:id AND provider=\'openai\' AND ordinal=1',{'id':unknown_row.id})
        async def reject_rows(objects,expected=('23514',)):
            nonlocal sql_rejections
            async with owned_session(proof) as session:
                try:session.add_all(objects);await session.commit()
                except IntegrityError as error:
                    await session.rollback();code=getattr(error.orig,'sqlstate',None) or getattr(getattr(error.orig,'__cause__',None),'sqlstate',None)
                    check(code in expected,'CF018 deferred relationship SQLSTATE');sql_rejections+=1
                else:check(False,'CF018 invalid relationship must fail')
        async with owned_session(proof) as session:
            template=await session.get(FlowAnalysisRun,unknown_row.id)
            run_template={c.key:getattr(template,c.key) for c in FlowAnalysisRun.__table__.columns}
            res_template=await session.get(Reservation,unknown_row.id)
            res_values={c.key:getattr(res_template,c.key) for c in Reservation.__table__.columns}
            bucket=await session.get(Period,res_template.service_period_id)
            bucket_values={c.key:getattr(bucket,c.key) for c in Period.__table__.columns}
            original_call=await session.scalar(select(Call).where(Call.reservation_id==unknown_row.id,Call.provider=='openai',Call.ordinal==1))
            call_values={c.key:getattr(original_call,c.key) for c in Call.__table__.columns}
        def linked(*,missing_run=False,missing_reservation=False,wrong_owner=False,wrong_scope=False,wrong_period=False):
            identity,attempt=uuid4(),uuid4();claim=b'n'*32;stamp=run_template['started_at']
            run_values=run_template|dict(id=identity,attempt_id=attempt,key_digest=uuid4().bytes*2,budget_reservation_id=identity,
                state='running',input_json=None,result_json=None,input_sha256=None,result_sha256=None,adopted_report_id=None,accepted_at=None,error_code=None,claim_digest=claim)
            reservation=res_values|dict(id=identity,attempt_id=attempt,claim_digest=claim,state='held',remaining_nano=u.RUN_RESERVE,estimated_spend_nano=0)
            if wrong_owner:reservation['owner_user_id']=other[1].user_id
            if wrong_scope:reservation['user_period_id'],reservation['service_period_id']=reservation['service_period_id'],reservation['user_period_id']
            if wrong_period:run_values['started_at']=stamp-timedelta(days=1);run_values['deadline_at']=run_values['started_at']+timedelta(seconds=120)
            return ([] if missing_run else [FlowAnalysisRun(**run_values)])+([] if missing_reservation else [Reservation(**reservation)])
        await reject_rows(linked(missing_run=True),('23503','23514'))
        await reject_rows(linked(missing_reservation=True),('23503','23514'))
        await reject_rows(linked(wrong_owner=True),('23503','23514'))
        await reject_rows(linked(wrong_scope=True))
        await reject_rows(linked(wrong_period=True))
        no_reference=linked(missing_reservation=True)[0];no_reference.budget_reservation_id=None
        await reject_rows([no_reference])
        await reject_rows([Period(**(bucket_values|{'id':uuid4()}))],('23505',))
        async with owned_session(proof) as session:
            for changed,expected in (({},'23505'),({'id':uuid4()},'23514'),({'state':None},'23502')):
                try:await session.execute(insert(Call).values(call_values|changed));await session.commit()
                except IntegrityError as error:
                    await session.rollback();code=getattr(error.orig,'sqlstate',None) or getattr(getattr(error.orig,'__cause__',None),'sqlstate',None)
                    check(code==expected,'CF018 call UNIQUE identity NOT NULL SQLSTATE');sql_rejections+=1
                else:check(False,'CF018 call constraint must fail')
        check(await sql("SELECT jsonb_build_array(id,input_json,result_json,input_sha256,result_sha256,adopted_report_id)::text FROM flow_analysis_runs WHERE id=:id",{'id':legacy_stored_id})==legacy_frozen,'CF018 final requery legacy snapshot ID and bytes unchanged')
        try:await usage_migration(proof,'c15001a7e0001',downgrade=True)
        except RuntimeError as error:check(type(error).__name__=='NonemptyUsageHistory','CF018 exact nonempty downgrade refusal')
        else:check(False,'CF018 nonempty downgrade must fail')
        check(await sql('SELECT version_num FROM alembic_version')=='c18001a7e0001','CF018 failed downgrade unchanged revision')
        mark('database_constraints_and_nonempty_downgrade')
    app.dependency_overrides.clear()
    check(all(n==1 for n in dispatch.values()),'CF018 final dispatch bound')
    return {'groups':groups,'public_dispatches':sum(dispatch.values()),'dispatch_max':max(dispatch.values(),default=0),'rejections':rejections,'sql_rejections':sql_rejections}


TOKEN='cf018-synthetic-service-token-32bytes'
