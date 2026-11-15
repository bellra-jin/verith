"""One durable start per consumed Technical grant; observe never authorizes work."""
import asyncio
import hashlib
import hmac
import time
from uuid import UUID
from sqlalchemy.exc import SQLAlchemyError
from src.modules.auth.application.session_service import Principal,validate_principal,AuthenticationRequired
from src.modules.technical.domain import provider_execution as P
from src.modules.technical.domain.execution_admission import TechnicalAdmissionError
from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService
from src.modules.technical.infrastructure import execution_authority_repository as repo,execution_admission_repository as admission

class AuthorityUnavailable(ValueError):
    def __init__(self):super().__init__('Technical execution unavailable')

class AuthorityConflict(ValueError):
    def __init__(self):super().__init__('Technical observation conflict')

class TechnicalExecutionAuthority:
    def __init__(self,session,*,configuration=None):self.session=session;self.configuration=configuration

    @staticmethod
    def _input(body,grant,observe=False):
        P.shape(body,{'schema_version','analysis_id','control_sha256','executor_id','start_sha256','evidence','evidence_sha256'} if observe else {'schema_version','analysis_id','control_sha256','executor_id'})
        if body['schema_version']!=P.SCHEMA:raise P.ExecutionInvalid()
        P.uid(body['analysis_id']);P.uid(body['executor_id']);P.digest(body['control_sha256']);P.digest(grant)
        return P.decode(P.canonical(body),16384 if observe else 8192),hashlib.sha256(grant.encode('ascii')).digest()

    async def _mutate(self,action):
        if self.session.new or self.session.dirty or self.session.deleted:raise AuthorityUnavailable()
        try:
            result,bound=await action()
            await self.session.flush();await self.session.commit()
            if bound is not None and time.monotonic()>=bound:result={**result,'newly_started':False}
            return result
        except asyncio.CancelledError:
            # The callback caller must treat this as unknown; never retry start.
            raise
        except BaseException as error:
            try:await self.session.rollback()
            except Exception:pass
            if isinstance(error,(AuthorityConflict,AuthorityUnavailable,P.ExecutionInvalid,AuthenticationRequired,TechnicalAdmissionError)):raise
            raise AuthorityUnavailable() from None

    async def start(self,body,grant):
        body,grant_hash=self._input(body,grant)
        if type(self.configuration) is not P.Configuration:raise AuthorityUnavailable()
        configuration=P.Configuration(self.configuration.text)
        async def action():
            hint=await repo.hint(self.session,UUID(body['analysis_id']),grant_hash)
            if hint is None:raise AuthorityUnavailable()
            original=await repo.original_session(self.session,hint)
            if original is None:raise AuthorityUnavailable()
            principal=Principal(admission.database_uuid(hint.owner_user_id),admission.database_uuid(hint.admission_session_id),original.expires_at,bytes(original.token_digest))
            await validate_principal(self.session,principal,lock=True)
            row,period=await repo.locked(self.session,hint)
            if row is None:raise AuthorityUnavailable()
            run=TechnicalAdmissionService._receipt(row,period)
            if (run.spec_sha256!=P.SPEC_SHA256 or not hmac.compare_digest(row.execution_grant_digest,grant_hash)
                    or row.execution_control_sha256!=body['control_sha256']):raise AuthorityUnavailable()
            if row.execution_started_at is not None:
                value=P.decode(row.execution_start_json,8192)
                return dict(schema_version=P.SCHEMA,newly_started=False,**value),None
            if row.state!='claimed' or row.accepted_at is not None or period.blocked or row.execution_configuration_json!=configuration.text:raise AuthorityUnavailable()
            stock=await admission.stock(self.session,row.ticker)
            if stock is None or P.canonical({'stock_code':stock.stock_code,'stock_name':stock.stock_name,'market':stock.market})!=row.stock_json:raise AuthorityUnavailable()
            boundary=P.boundary_for(run,P.decode(row.intent_json),P.decode(row.stock_json,4096))
            expected=P.control_for(run,boundary,configuration)
            if row.execution_control_json!=P.canonical(expected['control']) or row.execution_control_sha256!=expected['control_sha256']:raise AuthorityUnavailable()
            base=time.monotonic();stamp=await admission.clock(self.session)
            if stamp>=row.deadline_at:raise AuthorityUnavailable()
            receipt=P.start_receipt(row.execution_control_sha256,body['executor_id'],stamp.isoformat())
            started=await repo.start(self.session,row,executor_id=UUID(body['executor_id']),stamp=stamp,
                start_json=P.canonical(receipt),start_sha256=receipt['start_sha256'])
            if started is None:raise AuthorityUnavailable()
            return dict(schema_version=P.SCHEMA,newly_started=True,**receipt),base+(row.deadline_at-stamp).total_seconds()
        return await self._mutate(action)

    async def observe(self,body,grant):
        body,grant_hash=self._input(body,grant,True)
        P.digest(body['start_sha256']);P.digest(body['evidence_sha256'])
        raw=P.canonical(body['evidence'])
        if P.sha(raw)!=body['evidence_sha256']:raise P.ExecutionInvalid()
        async def action():
            hint=await repo.hint(self.session,UUID(body['analysis_id']),grant_hash)
            if hint is None:raise AuthorityUnavailable()
            # Record-only: original session expiry/revocation must not erase
            # evidence for an already consumed start. No fresh execution here.
            row,period=await repo.locked(self.session,hint)
            if row is None:raise AuthorityUnavailable()
            TechnicalAdmissionService._receipt(row,period)
            if (row.spec_sha256!=P.SPEC_SHA256 or row.execution_started_at is None
                    or not hmac.compare_digest(row.execution_grant_digest,grant_hash)
                    or row.execution_control_sha256!=body['control_sha256']
                    or str(row.execution_executor_id)!=body['executor_id'] or row.execution_start_sha256!=body['start_sha256']):raise AuthorityUnavailable()
            cfg=P.Configuration(row.execution_configuration_json);control=P.decode(row.execution_control_json,8192);start=P.decode(row.execution_start_json,8192)
            P.evidence(body['evidence'],cfg,control,start)
            if row.execution_evidence_json is not None:
                if row.execution_evidence_json!=raw or row.execution_evidence_sha256!=body['evidence_sha256']:raise AuthorityConflict()
            else:
                if await repo.observe(self.session,row,body=raw,sha256=body['evidence_sha256'],stamp=await admission.clock(self.session)) is None:raise AuthorityUnavailable()
            return {'schema_version':P.SCHEMA,'recorded':True,'analysis_id':body['analysis_id'],'evidence_sha256':body['evidence_sha256']},None
        return await self._mutate(action)
