"""One Technical SQL admission/claim owner. No engine or provider dispatch."""
import asyncio
from dataclasses import fields, replace
from datetime import timedelta
import hashlib
import hmac
import secrets
import time
from uuid import UUID, uuid4
from types import SimpleNamespace
from sqlalchemy.exc import SQLAlchemyError
from src.modules.auth.application.session_service import Principal, validate_principal
from src.modules.technical.domain.execution_admission import (
    AdmissionReceipt, ClaimReceipt, Intent, Policy, RunReceipt, TechnicalAdmissionError,
    OPERATION, REASONS, SPEC_JSON, SPEC_SHA256, canonical, decode, integer, sha, uid,
    COMPLETION_FIELDS, CompletionReceipt, ProviderClaim, utc,
)
from src.modules.technical.infrastructure import execution_admission_repository as repo
from src.modules.technical.domain import provider_execution as P


class _ReplayRace(Exception):
    """Only a known losing SQL insert; never a provider or commit-ACK retry."""


class TechnicalAdmissionService:
    def __init__(self, session, *, principal, policy=None):
        self.session, self.principal, self.policy = session, principal, policy

    def _principal(self):
        p = self.principal
        if (type(p) is not Principal or not isinstance(p.user_id, UUID)
                or not isinstance(p.session_id, UUID) or type(p.token_digest) is not bytes or len(p.token_digest) != 32):
            raise TechnicalAdmissionError('INPUT_INVALID')
        return Principal(p.user_id,p.session_id,p.expires_at,bytes(p.token_digest))

    def _policy_text(self):
        value = getattr(self.policy, 'text', None) if type(self.policy) is Policy else None
        return value if type(value) is str else None

    @staticmethod
    def _key(key):
        if type(key) is not str or not 1 <= len(key) <= 128 or not key.strip() or '\x00' in key:
            raise TechnicalAdmissionError()
        try:
            return hashlib.sha256(key.encode('utf-8')).digest()
        except UnicodeError:
            raise TechnicalAdmissionError() from None

    async def _mutation(self, action):
        if self.session.new or self.session.dirty or self.session.deleted:
            raise TechnicalAdmissionError('CONTEXT_DIRTY')
        committing = False
        try:
            result, authority_deadline = await action()
            await self.session.flush()
            committing = True
            await self.session.commit()
            # A delayed ACK cannot extend the fixed DB deadline or confer a new
            # execution opportunity. The committed reservation/claim stays used.
            if authority_deadline is not None and time.monotonic() >= authority_deadline:
                if type(result) is AdmissionReceipt:
                    return replace(result,newly_admitted=False,claim_token=None)
                if type(result) is ClaimReceipt:
                    return replace(result,newly_claimed=False,intent_json=None)
                if type(result) is ProviderClaim:
                    return replace(result,newly_claimed=False,execution_json=None,grant=None)
            return result
        except BaseException as error:
            try:
                await self.session.rollback()
            except asyncio.CancelledError:
                raise
            except BaseException:
                pass
            if isinstance(error, asyncio.CancelledError):
                raise
            if committing:
                raise TechnicalAdmissionError('ACK_UNKNOWN') from None
            if isinstance(error, (SQLAlchemyError, OSError, TimeoutError)):
                raise TechnicalAdmissionError('UNAVAILABLE') from None
            raise

    @staticmethod
    def _period_policy(period):
        if period is None:
            raise TechnicalAdmissionError('STORED_INVALID')
        policy = Policy(period.policy_json)
        value = policy.enabled()
        if (period.operation != OPERATION or period.policy_sha256 != policy.fingerprint
                or any(getattr(period,column) != value[key] for column,key in (
                    ('user_request_limit','user_daily_limit'),('request_limit','service_daily_limit'),
                    ('budget_limit_nano','daily_budget_nano'),('attempt_reserve_nano','attempt_reserve_nano')))
                or not 0 <= period.request_count <= period.request_limit
                or not 0 <= period.reserved_nano <= period.budget_limit_nano):
            raise TechnicalAdmissionError('STORED_INVALID')
        day,start,end = repo.kst_period(period.period_start)
        if (period.kst_date,period.period_start,period.period_end) != (day,start,end):
            raise TechnicalAdmissionError('STORED_INVALID')
        return policy

    @classmethod
    def _receipt(cls, row, period):
        policy = cls._period_policy(period)
        stock = decode(row.stock_json,4096)
        if (row.operation != OPERATION or row.period_id != period.id
                or row.policy_sha256 != policy.fingerprint or row.reserved_nano != period.attempt_reserve_nano
                or row.started_at != row.as_of or row.started_at < period.period_start or row.deadline_at > period.period_end
                or row.deadline_at-row.started_at > timedelta(seconds=policy.data()['deadline_seconds'])
                or row.ticker not in policy.data()['supported_tickers']
                or (row.spec_json,row.spec_sha256) not in {(SPEC_JSON,SPEC_SHA256),(P.SPEC_JSON,P.SPEC_SHA256)}
                or row.stock_sha256 != sha(row.stock_json) or type(stock) is not dict
                or set(stock) != {'stock_code','stock_name','market'} or stock['stock_code'] != row.ticker
                or type(stock['stock_name']) is not str or not stock['stock_name'].strip()
                or len(stock['stock_name']) > 200 or (stock['market'] is not None and type(stock['market']) is not str)
                or type(row.key_digest) is not bytes or len(row.key_digest) != 32
                or type(row.claim_digest) is not bytes or len(row.claim_digest) != 32):
            raise TechnicalAdmissionError('STORED_INVALID')
        if row.intent_json is not None:
            intent = Intent(row.intent_json)
            if intent.fingerprint != row.intent_sha256 or intent.data()['ticker'] != row.ticker:
                raise TechnicalAdmissionError('STORED_INVALID')
        elif row.state not in {'unknown','stored','failed'}:
            raise TechnicalAdmissionError('STORED_INVALID')
        result=RunReceipt(analysis_id=repo.database_uuid(row.id),admission_request_id=repo.database_uuid(row.admission_request_id),
            attempt_id=repo.database_uuid(row.attempt_id),report_id=repo.database_uuid(row.planned_report_id),
            boundary_request_id=repo.database_uuid(row.boundary_request_id),trace_id=repo.database_uuid(row.trace_id),
            admission_session_id=repo.database_uuid(row.admission_session_id),period_id=repo.database_uuid(row.period_id),
            intent_sha256=row.intent_sha256,policy_sha256=row.policy_sha256,spec_sha256=row.spec_sha256,
            as_of=row.as_of,deadline_at=row.deadline_at,state=row.state,reserved_nano=row.reserved_nano,held_nano=row.held_nano,
            claim_consumed_at=row.claim_consumed_at,redacted_at=row.redacted_at,unknown_reason=row.unknown_reason)
        if row.spec_sha256==P.SPEC_SHA256:
            try:
                cfg=P.Configuration(row.execution_configuration_json)
                if cfg.fingerprint!=row.execution_configuration_sha256 or cfg.policy_sha256!=row.policy_sha256:raise P.ExecutionInvalid()
                if row.claim_consumed_at is not None:
                    if type(row.execution_grant_digest) is not bytes or len(row.execution_grant_digest)!=32:raise P.ExecutionInvalid()
                    control=P.decode(row.execution_control_json,8192);P.shape(control,P.CONTROL_FIELDS)
                    if any(control[k]!=str(getattr(result,k)) for k in ('analysis_id','admission_request_id','attempt_id','report_id','boundary_request_id','trace_id')):raise P.ExecutionInvalid()
                    if control['configuration_sha256']!=cfg.fingerprint or control['policy_sha256']!=row.policy_sha256 or control['spec_sha256']!=P.SPEC_SHA256 or control['intent_sha256']!=row.intent_sha256 or control['stock_sha256']!=row.stock_sha256 or control['reserved_nano']!=row.reserved_nano or control['started_at']!=row.started_at.isoformat() or control['deadline_at']!=row.deadline_at.isoformat():raise P.ExecutionInvalid()
                    P.digest(row.execution_control_sha256)
                if getattr(row,'execution_started_at',None) is not None:
                    start=P.decode(row.execution_start_json,8192)
                    if start!=P.start_receipt(row.execution_control_sha256,str(row.execution_executor_id),row.execution_started_at.isoformat()) or start['start_sha256']!=row.execution_start_sha256:raise P.ExecutionInvalid()
                if getattr(row,'execution_evidence_json',None) is not None:
                    body=P.decode(row.execution_evidence_json,16384)
                    if P.sha(row.execution_evidence_json)!=row.execution_evidence_sha256:raise P.ExecutionInvalid()
                    P.evidence(body,cfg,control,start)
            except (P.ExecutionInvalid,AttributeError,TypeError,ValueError):raise TechnicalAdmissionError('STORED_INVALID') from None
        CompletionReceipt(result,**{key:getattr(row,key,None) for key in COMPLETION_FIELDS})
        return result

    async def _locked(self, principal, analysis_id):
        hint = await repo.owned(self.session,principal.user_id,analysis_id)
        if hint is None:
            raise TechnicalAdmissionError('NOT_FOUND')
        period = await repo.period(self.session,hint.period_id)
        row = await repo.owned(self.session,principal.user_id,analysis_id,lock=True)
        if row is None or row.period_id != hint.period_id:
            raise TechnicalAdmissionError('STORED_INVALID')
        self._receipt(row,period)
        return row,period

    @staticmethod
    def _expire(row, stamp):
        if row.state in {'admitted','claimed'} and stamp >= row.deadline_at:
            row.state='unknown';row.intent_json=None;row.redacted_at=stamp;row.unknown_reason='EXPIRED'
            return True
        return False

    async def admit_provider(self,key,intent,configuration,*,admission_before=None):
        if type(configuration) is not P.Configuration or self._policy_text()!=P.canonical(configuration.data()['policy']):
            raise TechnicalAdmissionError('POLICY_UNAVAILABLE')
        return await self.admit(key,intent,_execution_configuration=configuration,**({'_admission_before':admission_before} if admission_before is not None else {}))

    async def admit(self, key, intent, *, _execution_configuration=None,_admission_before=None):
        principal = self._principal();key_digest = self._key(key)
        admission_before=utc(_admission_before) if _admission_before is not None else None
        if type(intent) is not Intent:
            raise TechnicalAdmissionError()
        frozen_intent = Intent(intent.text)
        policy_text = self._policy_text()  # immutable text captured before first await
        config_text=_execution_configuration.text if type(_execution_configuration) is P.Configuration else None
        wanted_spec=P.SPEC_SHA256 if config_text is not None else SPEC_SHA256

        async def replay(row):
            row,period = await self._locked(principal,repo.database_uuid(row.id))
            if row.intent_sha256 != frozen_intent.fingerprint or row.spec_sha256!=wanted_spec or config_text is not None and getattr(row,'execution_configuration_json',None)!=config_text:
                raise TechnicalAdmissionError('IDEMPOTENCY_CONFLICT')
            self._expire(row,await repo.clock(self.session))
            return AdmissionReceipt(self._receipt(row,period),False),None

        async def action():
            await validate_principal(self.session,principal,lock=True)
            previous = await repo.by_key(self.session,principal.user_id,key_digest)
            if previous is not None:
                return await replay(previous)
            if policy_text is None:
                raise TechnicalAdmissionError('POLICY_UNAVAILABLE')
            policy = Policy(policy_text);limits = policy.enabled();data = frozen_intent.data()
            if data['ticker'] not in limits['supported_tickers']:
                raise TechnicalAdmissionError('POLICY_UNAVAILABLE')
            stamp = await repo.clock(self.session)
            period = await repo.admit_period(self.session,stamp,policy)
            # Recheck the key after the single service-period lock, before any
            # run ID/token generation, counters or new reservation.
            previous = await repo.by_key(self.session,principal.user_id,key_digest)
            if previous is not None:
                if previous.period_id != period.id:
                    raise _ReplayRace()
                return await replay(previous)
            if self._period_policy(period).text != policy.text or period.blocked:
                raise TechnicalAdmissionError('POLICY_UNAVAILABLE')
            if (period.request_count >= period.request_limit
                    or await repo.user_count(self.session,period.id,principal.user_id) >= period.user_request_limit
                    or period.reserved_nano > period.budget_limit_nano-period.attempt_reserve_nano):
                raise TechnicalAdmissionError('LIMIT_EXCEEDED')
            stock = await repo.stock(self.session,data['ticker'])
            if stock is None or type(stock.stock_name) is not str or not stock.stock_name.strip() or len(stock.stock_name)>200:
                raise TechnicalAdmissionError('INPUT_INVALID')
            stock_json=canonical({'stock_code':stock.stock_code,'stock_name':stock.stock_name,'market':stock.market})
            base=time.monotonic();stamp=await repo.clock(self.session)
            deadline=min(stamp+timedelta(seconds=limits['deadline_seconds']),period.period_end)
            if stamp < period.period_start or stamp >= deadline or admission_before is not None and stamp>=admission_before:
                raise TechnicalAdmissionError('POLICY_UNAVAILABLE')
            token=secrets.token_bytes(32)
            row=await repo.insert_run(self.session,dict(id=uuid4(),owner_user_id=principal.user_id,
                admission_session_id=principal.session_id,period_id=period.id,operation=OPERATION,key_digest=key_digest,
                intent_json=frozen_intent.text,intent_sha256=frozen_intent.fingerprint,policy_sha256=period.policy_sha256,
                spec_json=P.SPEC_JSON if config_text is not None else SPEC_JSON,spec_sha256=wanted_spec,stock_json=stock_json,stock_sha256=sha(stock_json),ticker=data['ticker'],
                admission_request_id=uuid4(),attempt_id=uuid4(),planned_report_id=uuid4(),boundary_request_id=uuid4(),trace_id=uuid4(),
                as_of=stamp,started_at=stamp,deadline_at=deadline,claim_digest=hashlib.sha256(token).digest(),claim_consumed_at=None,
                execution_configuration_json=config_text,execution_configuration_sha256=P.sha(config_text) if config_text is not None else None,
                reserved_nano=period.attempt_reserve_nano,held_nano=period.attempt_reserve_nano,state='admitted',unknown_reason=None,redacted_at=None),**({'before':admission_before} if admission_before is not None else {}))
            if row is None:
                raise _ReplayRace()
            period.request_count=integer(period.request_count+1)
            period.reserved_nano=integer(period.reserved_nano+period.attempt_reserve_nano)
            return AdmissionReceipt(self._receipt(row,period),True,token),base+((min(deadline,admission_before) if admission_before is not None else deadline)-stamp).total_seconds()

        try:
            return await self._mutation(action)
        except _ReplayRace:
            # Roll back the unused period transaction and lock only the original
            # winner's period. No second admission/ID/reservation/dispatch occurs.
            async def recover():
                await validate_principal(self.session,principal,lock=True)
                previous=await repo.by_key(self.session,principal.user_id,key_digest)
                if previous is None:
                    raise TechnicalAdmissionError('UNAVAILABLE')
                return await replay(previous)
            return await self._mutation(recover)

    async def get(self, analysis_id):
        principal=self._principal();uid(analysis_id)
        async def action():
            await validate_principal(self.session,principal,lock=True)
            row,period=await self._locked(principal,analysis_id)
            self._expire(row,await repo.clock(self.session))
            return self._receipt(row,period),None
        return await self._mutation(action)

    async def reconcile(self, key):
        principal=self._principal();key_digest=self._key(key)
        try:
            with self.session.no_autoflush:
                await validate_principal(self.session,principal)
                row=await repo.read_by_key(self.session,principal.user_id,key_digest)
                if row is None:
                    raise TechnicalAdmissionError('NOT_FOUND')
                period=await repo.read_period(self.session,row.period_id)
                return AdmissionReceipt(self._receipt(row,period),False)
        except (SQLAlchemyError,OSError,TimeoutError):
            raise TechnicalAdmissionError('UNAVAILABLE') from None

    async def dispatch_provider_claim(self,expected,claim_token,configuration):
        if type(configuration) is not P.Configuration:raise TechnicalAdmissionError('CLAIM_DENIED')
        return await self.dispatch_claim(expected,claim_token,_execution_configuration=configuration)

    async def dispatch_claim(self, expected, claim_token, *, _execution_configuration=None):
        principal=self._principal()
        if type(expected) is not RunReceipt or type(claim_token) is not bytes or len(claim_token)!=32:
            raise TechnicalAdmissionError('CLAIM_DENIED')
        expected=RunReceipt(**{f.name:getattr(expected,f.name) for f in fields(RunReceipt)})
        token=bytes(claim_token);policy_text=self._policy_text()
        cfg=P.Configuration(_execution_configuration.text) if type(_execution_configuration) is P.Configuration else None
        def negative(run):return ProviderClaim(run,False) if cfg is not None else ClaimReceipt(run,False)
        immutable=tuple(f.name for f in fields(RunReceipt) if f.name not in {'state','claim_consumed_at','redacted_at','unknown_reason'})
        async def action():
            await validate_principal(self.session,principal,lock=True)
            row,period=await self._locked(principal,expected.analysis_id)
            current=self._receipt(row,period)
            if (cfg is not None)!=(row.spec_sha256==P.SPEC_SHA256) or cfg is not None and (cfg.text!=row.execution_configuration_json or cfg.policy_sha256!=row.policy_sha256):raise TechnicalAdmissionError('CLAIM_DENIED')
            if any(getattr(current,key)!=getattr(expected,key) for key in immutable):
                raise TechnicalAdmissionError('CLAIM_DENIED')
            base=time.monotonic();stamp=await repo.clock(self.session)
            if self._expire(row,stamp) or row.state=='unknown':
                return negative(self._receipt(row,period)),None
            if row.state in {'result_ready','stored','failed'}:
                return negative(current),None
            if row.admission_session_id!=principal.session_id or not hmac.compare_digest(row.claim_digest,hashlib.sha256(token).digest()):
                raise TechnicalAdmissionError('CLAIM_DENIED')
            if row.state=='claimed':
                return negative(current),None
            if policy_text is None:
                raise TechnicalAdmissionError('POLICY_UNAVAILABLE')
            active=Policy(policy_text);active.enabled()
            if active.text!=period.policy_json or period.blocked:
                raise TechnicalAdmissionError('POLICY_UNAVAILABLE')
            stock=await repo.stock(self.session,row.ticker)
            if stock is None or canonical({'stock_code':stock.stock_code,'stock_name':stock.stock_name,'market':stock.market})!=row.stock_json:
                row.state='unknown';row.intent_json=None;row.redacted_at=stamp;row.unknown_reason='STOCK_CHANGED'
                return negative(self._receipt(row,period)),None
            bound=base+(row.deadline_at-stamp).total_seconds()
            if time.monotonic()>=bound:
                row.state='unknown';row.intent_json=None;row.redacted_at=stamp;row.unknown_reason='EXPIRED'
                return negative(self._receipt(row,period)),None
            row.state='claimed';row.claim_consumed_at=stamp
            if cfg is not None:
                run=self._receipt_for_new_grant(row,period)
                boundary=P.boundary_for(run,Intent(row.intent_json).data(),decode(row.stock_json,4096))
                execution=P.control_for(run,boundary,cfg);grant=secrets.token_hex(32)
                row.execution_grant_digest=hashlib.sha256(grant.encode('ascii')).digest()
                row.execution_control_json=P.canonical(execution['control']);row.execution_control_sha256=execution['control_sha256']
                return ProviderClaim(self._receipt(row,period),True,P.canonical(execution),grant),bound
            return ClaimReceipt(self._receipt(row,period),True,row.intent_json),bound
        return await self._mutation(action)

    @classmethod
    def _receipt_for_new_grant(cls,row,period):
        values={c.key:getattr(row,c.key,None) for c in repo.Run.__table__.columns}
        consumed=values['claim_consumed_at'];values.update(state='admitted',claim_consumed_at=None)
        return replace(cls._receipt(SimpleNamespace(**values),period),state='claimed',claim_consumed_at=consumed)

    async def close_unknown(self, analysis_id, reason):
        principal=self._principal();uid(analysis_id)
        if type(reason) is not str or reason not in REASONS:
            raise TechnicalAdmissionError()
        async def action():
            await validate_principal(self.session,principal,lock=True)
            row,period=await self._locked(principal,analysis_id)
            if row.state in {'stored','failed'}:
                return self._receipt(row,period),None
            stamp=await repo.clock(self.session)
            if not self._expire(row,stamp):
                if row.state=='unknown' and row.unknown_reason!=reason:
                    raise TechnicalAdmissionError('IDEMPOTENCY_CONFLICT')
                if row.state!='unknown':
                    row.state='unknown';row.intent_json=None;row.redacted_at=stamp;row.unknown_reason=reason
                    row.input_json=None;row.result_json=None
            return self._receipt(row,period),None
        return await self._mutation(action)
