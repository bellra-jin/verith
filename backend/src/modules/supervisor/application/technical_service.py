"""One confirmed binding -> existing Technical admission/claim; replay is observation only."""
import asyncio
import hashlib
from datetime import timedelta
from uuid import uuid4
from src.modules.supervisor.domain import technical_core_contracts as C
from src.modules.supervisor.domain.technical_projection import confirmed_plan,intent_for,fixed_key,outcome
from src.modules.supervisor.infrastructure import repository as repo
from src.modules.supervisor.application.service import CoreError
from src.modules.stocks.application.resolver_service import StockResolverService
from src.modules.auth.application.session_service import validate_principal,AuthenticationRequired
from src.modules.technical.domain import provider_execution as P
from src.modules.technical.domain.execution_admission import Intent,Policy,TechnicalAdmissionError,TechnicalCompletionError
from src.modules.technical.application.execution_runtime import TechnicalExecutionRuntime
from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService
from src.modules.technical.infrastructure import execution_admission_repository as runs
from src.shared.infrastructure.clients.ai_client import AITimeoutError,AIContractError

class TechnicalSupervisorService:
    def __init__(self,session,*,principal,client,configuration,resolver_factory=StockResolverService):
        self.session,self.principal,self.client=session,principal,client
        self.configuration=configuration;self.resolver_factory=resolver_factory

    async def rollback(self):
        try:await self.session.rollback()
        except Exception:pass

    def configuration_snapshot(self):
        value=self.configuration() if callable(self.configuration) else self.configuration
        if type(value) is not P.Configuration:raise CoreError('FEATURE_UNAVAILABLE',403)
        cfg=P.Configuration(value.text);Policy(P.canonical(cfg.data()['policy'])).enabled()
        return cfg

    @staticmethod
    def context(cfg):
        return C.Context(configuration_sha256=cfg.fingerprint,policy_sha256=cfg.policy_sha256,spec_sha256=P.SPEC_SHA256,reserved_nano=cfg.data()['policy']['attempt_reserve_nano'])

    async def exchange(self,input,request_id,trace_id,cfg,deadline):
        left=deadline-asyncio.get_running_loop().time()
        if left<=0:raise TimeoutError()
        payload=dict(schema_version=C.VERSION,request_id=str(request_id),trace_id=str(trace_id),data=input,error=None)
        value=await self.client.plan_supervisor_technical(payload,cfg,remaining=left)
        result=C.Envelope[C.InternalOutput].model_validate(value)
        if result.request_id!=str(request_id) or result.trace_id!=str(trace_id) or result.error is not None:raise C.CoreInvalid()
        if asyncio.get_running_loop().time()>=deadline:raise TimeoutError()
        return result.data

    async def _prepare(self,draft,request_id,cfg,deadline):
        context=self.context(cfg);trace=uuid4();data=dict(draft=draft.model_dump(mode='json'),context=context.model_dump(mode='json'))
        first=await self.exchange(dict(data,phase='start'),request_id,trace,cfg,deadline)
        frame=first.frame
        if (frame.original_query!=draft.original_query or frame.answers!=draft.answers or frame.revision!=draft.revision
                or frame.interpretation_source!='deterministic'):raise C.CoreInvalid()
        if first.action!='resolve_stock':
            if first.lookup is not None or first.plan is None:raise C.CoreInvalid()
            plan=C.validate_plan(first.plan.model_dump(mode='json'),draft,context)
            if plan.selected_views or plan.resolution is not None:raise C.CoreInvalid()
            return plan
        active={m.text for m in frame.mentions if not m.negated}
        if (frame.unresolved_slots or frame.requested_views!=['technical'] or len(active)!=1
                or first.lookup not in active or first.plan is not None):raise C.CoreInvalid()
        await validate_principal(self.session,self.principal,lock=True)
        raw=await self.resolver_factory(self.session).resolve(first.lookup)
        raw=raw.model_dump(mode='json');raw['candidates']=[{k:v for k,v in c.items() if k!='matched_text'} for c in raw['candidates']]
        resolution=C.Resolution.model_validate(raw)
        possible={resolution.stock.stock_code} if resolution.stock is not None else {c.stock_code for c in resolution.candidates}
        # Negated aliases are canonical master lookups, never waived or removed by query projection.
        for mention in frame.mentions:
            if mention.negated:
                negative=await self.resolver_factory(self.session).resolve(mention.text)
                if negative.status!='resolved' or negative.stock is None or negative.stock.stock_code in possible:
                    raise CoreError('INPUT_INVALID',422)
        await self.session.commit()  # No resolver/auth lock survives either AI exchange.
        reference=C.candidate_ref(draft,resolution)
        if draft.selected_ticker is not None and (resolution.status!='ambiguous' or draft.selected_ticker not in {c.stock_code for c in resolution.candidates}):raise CoreError('INPUT_INVALID',422)
        last=await self.exchange(dict(data,phase='continue',frame=frame.model_dump(mode='json'),resolution=resolution.model_dump(mode='json')),request_id,trace,cfg,deadline)
        if last.action!='final' or last.lookup is not None or last.frame!=frame or last.plan is None:raise C.CoreInvalid()
        plan=C.validate_plan(last.plan.model_dump(mode='json'),draft,context)
        expected=resolution
        if draft.selected_ticker is not None and reference==draft.candidate_ref:
            candidate=next(c for c in resolution.candidates if c.stock_code==draft.selected_ticker)
            from src.modules.supervisor.domain.contracts import Stock
            expected=C.Resolution(status='resolved',reason='exact_match',stock=Stock(**candidate.model_dump(exclude={'match_type'})),candidates=[])
        if plan.resolution!=expected or plan.frame!=frame or plan.candidate_ref!=reference:raise C.CoreInvalid()
        if draft.selected_ticker is not None and reference!=draft.candidate_ref and plan.status!='selection_stale':raise C.CoreInvalid()
        if plan.selected_views and any(m.negated and m.text.casefold() in {expected.stock.stock_code.casefold(),expected.stock.stock_name.casefold()} for m in frame.mentions):raise C.CoreInvalid()
        return plan

    async def prepare(self,draft,request_id,*,deadline):
        try:
            draft=C.Draft.model_validate(C.decode(C.canonical(draft.model_dump(mode='json'))))
            cfg=self.configuration_snapshot();await self.session.rollback()
            async with asyncio.timeout_at(deadline):
                plan=await self._prepare(draft,request_id,cfg,deadline)
                await validate_principal(self.session,self.principal,lock=True);await self.session.commit()
                if asyncio.get_running_loop().time()>=deadline:raise TimeoutError()
                return plan
        except asyncio.CancelledError:raise
        except BaseException as error:return await self.fail(error)

    async def fail(self,error):
        await self.rollback()
        if isinstance(error,(CoreError,AuthenticationRequired)):raise error
        if isinstance(error,(TimeoutError,AITimeoutError)):raise CoreError('DEADLINE_EXCEEDED',504) from None
        if isinstance(error,(C.CoreInvalid,AIContractError)):raise CoreError('RESULT_CONTRACT_INVALID',502) from None
        if isinstance(error,TechnicalAdmissionError):
            code,status={'LIMIT_EXCEEDED':('USAGE_LIMIT_EXCEEDED',429),'IDEMPOTENCY_CONFLICT':('IDEMPOTENCY_CONFLICT',409),'NOT_FOUND':('RESOURCE_NOT_FOUND',404),'POLICY_UNAVAILABLE':('FEATURE_UNAVAILABLE',403)}.get(error.code,('SERVICE_UNAVAILABLE',503))
            raise CoreError(code,status) from None
        raise CoreError() from None

    def checked(self,row,digest=None):
        if row.target!='technical':raise CoreError('IDEMPOTENCY_CONFLICT' if digest is not None else 'RESOURCE_NOT_FOUND',409 if digest is not None else 404)
        if digest is not None and digest!=row.confirm_digest:raise CoreError('IDEMPOTENCY_CONFLICT',409)
        cfg=P.Configuration(row.technical_configuration_json)
        if (cfg.fingerprint!=row.technical_configuration_sha256 or cfg.policy_sha256!=row.technical_policy_sha256
                or row.technical_spec_sha256!=P.SPEC_SHA256
                or row.technical_key_digest!=hashlib.sha256(fixed_key(row.id).encode()).digest()
                or P.sha(row.technical_stock_json)!=row.technical_stock_sha256):raise C.CoreInvalid()
        if row.redacted_at is None:
            if P.sha(row.plan_json)!=row.plan_sha256:raise C.CoreInvalid()
            saved=C.decode(row.plan_json);plan=C.Plan.model_validate(saved['plan'])
            if (plan.context!=self.context(cfg) or intent_for(plan).text!=row.technical_intent_json
                    or Intent(row.technical_intent_json).fingerprint!=row.technical_intent_sha256
                    or P.canonical(plan.resolution.stock.model_dump(mode='json'))!=row.technical_stock_json):raise C.CoreInvalid()
            consent=C.Consent(allow_technical=True,allow_partial=saved['effective_scope']['partial_consent'],waived_conditions=saved['effective_scope']['waived_conditions'])
            if confirmed_plan(plan,consent)!=saved:raise C.CoreInvalid()
        return cfg

    @staticmethod
    def run_snapshot(run):
        return dict(analysis_id=str(run.analysis_id),admission_request_id=str(run.admission_request_id),attempt_id=str(run.attempt_id),report_id=str(run.report_id),boundary_request_id=str(run.boundary_request_id),trace_id=str(run.trace_id),as_of=run.as_of.isoformat(),deadline_at=run.deadline_at.isoformat())

    def match_run(self,binding,row,run):
        if (row is None or row.owner_user_id!=binding.owner_user_id or row.key_digest!=binding.technical_key_digest
                or row.intent_sha256!=binding.technical_intent_sha256 or row.spec_sha256!=binding.technical_spec_sha256
                or row.execution_configuration_json!=binding.technical_configuration_json
                or row.execution_configuration_sha256!=binding.technical_configuration_sha256
                or row.policy_sha256!=binding.technical_policy_sha256 or row.stock_json!=binding.technical_stock_json
                or row.admission_session_id!=binding.technical_confirmation_session_id
                or row.started_at<binding.confirmed_at or row.started_at>=binding.handoff_before
                or binding.technical_run_id is not None and row.id!=binding.technical_run_id
                or binding.technical_run_json is not None and C.canonical(self.run_snapshot(run))!=binding.technical_run_json):raise C.CoreInvalid()

    async def observe(self,row):
        self.checked(row)
        if row.redacted_at is not None:return outcome(row)
        service=TechnicalAdmissionService(self.session,principal=self.principal)
        raw=await runs.read_by_key(self.session,self.principal.user_id,row.technical_key_digest)
        if raw is None:
            if row.technical_run_id is not None:raise C.CoreInvalid()
            return outcome(row)
        recovered=await service.reconcile(fixed_key(row.id));self.match_run(row,raw,recovered.run)
        return outcome(row,recovered.run)

    async def get(self,id):
        try:
            await self.session.rollback()
            with self.session.no_autoflush:
                await validate_principal(self.session,self.principal)
                row=await repo.technical_read(self.session,self.principal.user_id,id=id)
                if row is None:raise CoreError('RESOURCE_NOT_FOUND',404)
                result=await self.observe(row)
            await self.session.rollback()  # Read-only; no expiry/link/publish repair.
            return result
        except asyncio.CancelledError:raise
        except BaseException as error:return await self.fail(error)

    async def post(self,body,request_id,*,planning_deadline):
        body=C.Confirm.model_validate(C.decode(C.canonical(body.model_dump(mode='json'))))
        digest=C.sha(body.model_dump(mode='json'));key=hashlib.sha256(body.client_key.encode()).digest()
        try:
            await self.session.rollback();await validate_principal(self.session,self.principal,lock=True)
            previous=await repo.technical_read(self.session,self.principal.user_id,key=key)
            if previous is not None:
                self.checked(previous,digest);result=await self.observe(previous);await self.session.rollback();return result
            await self.session.commit()
            cfg=self.configuration_snapshot()
            async with asyncio.timeout_at(planning_deadline):
                plan=await self._prepare(body.draft,request_id,cfg,planning_deadline)
            if plan.plan_hash!=body.expected_plan_hash:raise CoreError('PLAN_STALE',409)
            try:saved=confirmed_plan(plan,body.consent)
            except C.CoreInvalid:raise CoreError('INPUT_INVALID',422) from None
            intent=intent_for(plan);stock=P.canonical(plan.resolution.stock.model_dump(mode='json'))
            await validate_principal(self.session,self.principal,lock=True)
            stamp=await runs.clock(self.session);id=uuid4();text=C.canonical(saved)
            row=await repo.admit(self.session,dict(id=id,owner_user_id=self.principal.user_id,client_key_digest=key,confirm_digest=digest,target='technical',plan_json=text,plan_sha256=P.sha(text),flow_input_json=None,flow_sha256=None,flow_key_digest=None,confirmed_at=stamp,handoff_before=stamp+timedelta(seconds=120),technical_intent_json=intent.text,technical_intent_sha256=intent.fingerprint,technical_key_digest=hashlib.sha256(fixed_key(id).encode()).digest(),technical_configuration_json=cfg.text,technical_configuration_sha256=cfg.fingerprint,technical_policy_sha256=cfg.policy_sha256,technical_spec_sha256=P.SPEC_SHA256,technical_stock_json=stock,technical_stock_sha256=P.sha(stock),technical_confirmation_session_id=self.principal.session_id))
            if row is None:
                await self.session.rollback()
                previous=await repo.technical_read(self.session,self.principal.user_id,key=key)
                if previous is None:raise CoreError()
                self.checked(previous,digest);return await self.get(previous.id)
            binding_id=runs.database_uuid(row.id)
            await self.session.commit()  # Only a fresh, acknowledged binding can hand off.
            runtime=TechnicalExecutionRuntime(self.session,principal=self.principal,client=self.client,policy=Policy(P.canonical(cfg.data()['policy'])),enabled=True)
            receipt=await runtime.admit_provider_once(fixed_key(binding_id),intent,cfg)
            if not receipt.newly_admitted:return await self.get(binding_id)
            token=bytes(receipt.claim_token);run=receipt.run
            service=TechnicalAdmissionService(self.session,principal=self.principal)
            await validate_principal(self.session,self.principal,lock=True)
            runrow,period=await service._locked(self.principal,run.analysis_id)
            current=service._receipt(runrow,period)
            binding=await repo.technical_link_row(self.session,self.principal.user_id,binding_id)
            if binding is None:raise C.CoreInvalid()
            self.checked(binding,digest);self.match_run(binding,runrow,current)
            if (current!=run or run.state!='admitted' or binding.technical_run_id is not None
                    or await runs.clock(self.session)>=min(binding.handoff_before,run.deadline_at)):raise C.CoreInvalid()
            binding.technical_run_id=run.analysis_id;binding.technical_run_json=C.canonical(self.run_snapshot(run))
            await self.session.commit()  # Unknown ACK never executes or reconstructs the token.
            await runtime.execute_provider_once(run,token,cfg)
            return await self.get(binding_id)
        except asyncio.CancelledError:raise
        except BaseException as error:return await self.fail(error)
