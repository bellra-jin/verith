"""Fixed CF036 owned-PG and authenticated ASGI read acceptance. No provider calls."""

async def verify_technical_owned_read(proof):
    from scripts.cf003_admission_check import isolated_application,check
    with isolated_application(proof) as observed:
        result=await _verify(proof)
        check(not any(observed.values()),'Technical read forbidden I/O')
        return result | {'observed_denials':dict(observed)}


async def _verify(proof):
    import copy
    from datetime import datetime,timedelta
    from uuid import uuid4
    from unittest.mock import patch
    import httpx
    from fastapi import FastAPI
    from sqlalchemy import select,update,delete,func,text
    from db.models.auth.models import AuthUser,AuthSession
    from db.models.common.stock import Stock
    from db.models.common.agent_report import AgentReport
    from db.models.technical.technical_report import TechnicalReport
    from db.models.technical.report_snapshot import TechnicalReportSnapshot
    from src.modules.auth.application.session_service import issue_session
    from src.modules.technical.application.owned_report_service import TechnicalOwnedReportService,projection
    from src.modules.technical.api import owned_report_router as router,owned_report_schemas as wire
    from src.shared.http.access_boundary import AccessBoundary
    from scripts.cf002_interactive_login import owned_session
    from scripts.cf003_admission_check import check
    from scripts.cf035_technical_owned_check import storage_fixture
    groups=[];reads=0;stage_calls=0;commits=0
    async with owned_session(proof) as session:
        a,b=AuthUser(id=uuid4()),AuthUser(id=uuid4());session.add_all([a,b]);await session.flush()
        ca,pa=await issue_session(session,a);ca2,pa2=await issue_session(session,a);cb,pb=await issue_session(session,b)
        expired,ep=await issue_session(session,a);revoked,rp=await issue_session(session,a)
        now=datetime.now(ep.expires_at.tzinfo)
        await session.execute(update(AuthSession).where(AuthSession.id==ep.session_id).values(created_at=now-timedelta(seconds=2),expires_at=now-timedelta(seconds=1)))
        await session.execute(update(AuthSession).where(AuthSession.id==rp.session_id).values(revoked_at=now))
        session.add(Stock(stock_code='005930',stock_name='synthetic canonical stock',market='KOSPI'));await session.commit()
    binding,frozen=storage_fixture(pa.user_id);rid=frozen.report_id
    async with owned_session(proof) as session:
        stage_calls+=1;await TechnicalOwnedReportService(session,principal=pa).stage(binding,frozen);await session.commit()
        stamp=await session.scalar(select(func.clock_timestamp()));legacy=projection(binding,frozen,pa,stamp)[0]
        legacy.id=uuid4();legacy.request_id='cf036-synthetic-legacy';legacy.owner_user_id=None
        session.add(legacy);await session.commit();legacy_id=legacy.id
    app=FastAPI();app.include_router(router.router);app.add_middleware(AccessBoundary)
    active=None
    async def no_commit(*args,**kwargs):
        nonlocal commits
        commits+=1;raise AssertionError('Owned read cannot commit')
    async def dependency():
        if active is not None:
            with patch.object(active,'commit',no_commit):yield active
        else:
            async with owned_session(proof) as session:
                with patch.object(session,'commit',no_commit):yield session
    app.dependency_overrides[router.session_dependency]=dependency
    async def call(path=wire.PATH,*,cookie=ca2,method='GET',host='localhost:8200',headers=None):
        nonlocal reads
        reads+=1
        base={'origin':'http://localhost:3200','x-forwarded-host':'localhost:3200'}
        if cookie is not None:base['cookie']='verith_session='+cookie
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://'+host) as client:
            return await client.request(method,path,headers=base|(headers or {}))
    def data(response,status):
        check(response.status_code==status,'owned read HTTP status')
        check(response.headers.get('cache-control')=='private, no-store' and response.headers.get('vary')=='Cookie, Origin','owned read private headers')
        body=response.json();check(set(body)=={'schema_version','request_id','data','error'} and body['schema_version']==wire.SCHEMA,'owned read envelope')
        check((body['data'] is None)==(status>=400) and (body['error'] is None)==(status<400),'owned read data error exclusion')
        if status>=400:check(body['error']['message']=='Technical result unavailable','owned read fixed safe error')
        return body['data']
    async def forbidden_stage(*args,**kwargs):raise AssertionError('Read restaged')
    with patch.object(TechnicalOwnedReportService,'stage',forbidden_stage):
        listed=data(await call(),200)
        check(len(listed['items'])==1 and listed['items'][0]['report_id']==str(rid),'A owned list')
        check(set(listed['items'][0])=={'report_id','stock','created_at','requested_as_of','execution_mode','cutoff_validation'},'owned cards disclose only read metadata')
        stored=data(await call(wire.PATH+'/'+str(rid)),200)
        check(stored['request_json']==frozen.input_json and stored['request_sha256']==frozen.input_sha256 and stored['result_json']==frozen.result_json and stored['result_sha256']==frozen.result_sha256,'stored byte hash preservation')
        check(data(await call(cookie=cb),200)['items']==[],'B empty owned list')
        data(await call(wire.PATH+'/'+str(rid),cookie=cb),404)
        data(await call(wire.PATH+'/'+str(legacy_id)),404)
        check(not data(await call(wire.PATH+'?stock_code=000660'),200)['items'],'canonical stock filter')
        data(await call(wire.PATH+'?limit=1&offset=0'),200)
        groups.append('actual_A_list_detail_B_isolation_raw_TEXT_SHA_new_session')
        for cookie in (None,expired,revoked,'forged',ca+'; verith_session='+ca):data(await call(cookie=cookie),401)
        data(await call(host='127.0.0.1:8200'),403)
        groups.append('actual_missing_expired_revoked_forged_duplicate_session_host')
        for suffix in ('?owner=x','?limit=0','?limit=21','?offset=10001','?limit=1&limit=2','?stock_code=１２３４５６'):
            data(await call(wire.PATH+suffix),422)
        data(await call(wire.PATH+'/bad'),422)
        data(await call(wire.PATH+'/'+str(rid)+'?limit=1'),422)
        data(await call(wire.PATH+'/'+str(rid)+'/trace'),403)
        for method in ('POST','PUT','PATCH','DELETE'):data(await call(method=method),403)
        check((await call('/api/technical/reports')).status_code==403,'legacy read remains closed')
        groups.append('exact_GET_query_UUID_method_legacy_boundary')
        # Each eligibility mutation exists only inside this owned transaction.
        for action in ('null_root','other_root','null_index','other_index','missing_index','duplicate_index','missing_snapshot'):
            async with owned_session(proof) as session:
                active=session
                if action in ('null_root','other_root'):
                    await session.execute(update(TechnicalReport).where(TechnicalReport.id==rid).values(owner_user_id=None if action=='null_root' else pb.user_id))
                elif action in ('null_index','other_index'):
                    await session.execute(update(AgentReport).where(AgentReport.agent_type=='technical',AgentReport.agent_report_id==rid).values(owner_user_id=None if action=='null_index' else pb.user_id))
                elif action=='missing_index':await session.execute(delete(AgentReport).where(AgentReport.agent_type=='technical',AgentReport.agent_report_id==rid))
                elif action=='duplicate_index':
                    session.add(AgentReport(id=uuid4(),agent_type='technical',agent_report_id=rid,owner_user_id=None));await session.flush()
                else:await session.execute(delete(TechnicalReportSnapshot).where(TechnicalReportSnapshot.report_id==rid))
                data(await call(wire.PATH+'/'+str(rid)),404)
                check(data(await call(),200)['items']==[],'ineligible list rows hidden')
                await session.rollback();active=None
        groups.append('SQL_root_snapshot_total_index_eligibility_404_not_empty_schema_errors')
        async with owned_session(proof) as session:
            active=session
            await session.execute(update(TechnicalReport).where(TechnicalReport.id==rid).values(stock_name='tampered'))
            data(await call(wire.PATH+'/'+str(rid)),502);data(await call(),502)
            await session.rollback();active=None
        # Existing read query must surface unavailable schema instead of empty list.
        async with owned_session(proof) as session:
            active=session
            await session.execute(text('ALTER TABLE technical_report_snapshots RENAME TO cf036_temporarily_unavailable'))
            data(await call(),503)
            await session.rollback();active=None
        groups.append('selected_projection_tamper_502_schema_unready_503_no_skip')
        check(stage_calls==1 and commits==0,'read stage commit zero')
        data(await call(wire.PATH+'/'+str(rid)),200)
    app.dependency_overrides.clear()
    return {'status':'passed','groups':groups,'asgi_read_calls':reads,'fixture_stage_calls':stage_calls,'read_stage_calls':0,'read_commit_calls':commits,'engine_calls':0,'provider_calls':0}
