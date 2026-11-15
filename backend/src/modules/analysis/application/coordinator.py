"""One claim/dispatch/snapshot/publication coordinator for two fixed profiles.

No agent registry, agent-domain imports, dispatch retry, session creation or provider I/O.
The authenticated caller owns the session; profile supplies domain-specific rules.
"""
import asyncio
from datetime import timedelta
import hashlib
import hmac
import secrets
import time
from uuid import UUID,uuid4
from sqlalchemy import select,func
from db.models.common.stock import Stock
from src.modules.auth.application.session_service import AuthenticationRequired,Principal,validate_principal
from src.modules.analysis.application.ports import AnalysisAdapter,AnalysisProfile,ResultCompletionProfile
from src.shared.infrastructure.clients.ai_client import AIContractError,AIValidationError

class AnalysisCoordinator:
    def __init__(self,session,*,principal,client,profile:AnalysisProfile,usage_control=None):
        self.session,self.principal,self.client=session,principal,client
        self.profile=profile
        self.usage_control=usage_control

    def _adapter(self,row):
        return self.profile.adapter(row,self.principal.user_id)

    def _error(self,code,analysis_id=None):
        return self.profile.error(code,analysis_id)

    async def _authorize(self):
        if not isinstance(self.principal,Principal):raise AuthenticationRequired()
        await validate_principal(self.session,self.principal,lock=True)

    async def _locked(self,id):
        if not isinstance(id,UUID):raise self._error('INPUT_INVALID')
        await self._authorize()
        row=await self.profile.repository.owned(self.session,id,self.principal.user_id)
        if row is None or row.state=='deleted':raise self._error('RESOURCE_NOT_FOUND')
        return row

    def _view(self,row):
        return self.profile.view(row)

    async def _rollback(self):
        try:await self.session.rollback()
        except Exception:pass # Never infer that a previous ambiguous commit did not happen.

    async def post(self,body,request_id):
        row,view,dispatch,token,request=await self._admit(body,request_id)
        if not dispatch:return view
        return await self._dispatch_admitted(row,token,request)

    async def _admit(self,body,request_id,*,admission_before=None,publish_ready=True):
        if isinstance(self.profile,ResultCompletionProfile):raise self._error('INPUT_INVALID')
        known=None
        try:
            body=self.profile.parse(body)
            await self._authorize()
            key=hashlib.sha256(body.idempotency_key.encode()).digest()
            normalized=self.profile.normalized(body);fingerprint=hashlib.sha256(normalized.encode()).hexdigest()
            row=await self.profile.repository.by_key(self.session,self.principal.user_id,key)
            winner=False;token=None
            if row is None:
                extra=self.usage_control.new_values(body,{'id':uuid4()}) if self.usage_control is not None else {}
                stock=await self.session.scalar(select(Stock).where(Stock.stock_code==body.ticker))
                if stock is None or not stock.stock_name or not stock.stock_name.strip():raise self._error('FEATURE_UNAVAILABLE' if self.usage_control is not None else 'INPUT_INVALID')
                name=stock.stock_name.strip()
                if len(name)>256 or any(ord(c)<32 for c in name):raise self._error('INPUT_INVALID')
                stamp=await self.session.scalar(select(func.clock_timestamp()));token=secrets.token_bytes(32)
                values=dict(id=extra['budget_reservation_id'] if extra else uuid4(),owner_user_id=self.principal.user_id,
                    operation=self.profile.operation,key_digest=key,input_fingerprint=fingerprint,admission_request_id=request_id,
                    attempt_id=uuid4(),ticker=body.ticker,stock_name=name,**self.profile.input_clock(body,stamp),
                    request_json=normalized,spec_json=self.profile.spec_json(),claim_digest=hashlib.sha256(token).digest(),
                    started_at=stamp,deadline_at=stamp+timedelta(seconds=self.profile.deadline_seconds),state='running')
                values.update(extra)
                if admission_before is None:
                    row=await self.profile.repository.admit(self.session,values)
                else:
                    # The concrete profile supplies its narrow bounded INSERT.
                    # Public POST and profiles without this opt-in are unchanged.
                    bounded_admit=getattr(self.profile,'admit_before',None)
                    if bounded_admit is None:raise self._error('INPUT_INVALID')
                    row=await bounded_admit(self.session,values,admission_before)
                winner=row is not None
                if winner and self.usage_control is not None:await self.usage_control.reserve(row,stamp)
                if row is None:row=await self.profile.repository.by_key(self.session,self.principal.user_id,key)
            if row is None:raise self._error('SERVICE_UNAVAILABLE')
            known=row.id
            if row.input_fingerprint!=fingerprint:raise self._error('IDEMPOTENCY_CONFLICT',known)
            if row.state=='deleted':raise self._error('RESOURCE_NOT_FOUND',known)
            await self.profile.repository.expire(self.session,row)
            if row.state=='result_ready' and publish_ready:return None,await self._publish(row),False,None,None
            view=self._view(row);dispatch=winner and row.state=='running'
            request=None
            if dispatch:
                adapter:AnalysisAdapter=self._adapter(row)
                request=adapter.build_request()
            await self.session.commit() # An ambiguous ACK must never dispatch.
        except asyncio.CancelledError:
            await self._rollback();raise
        except self.profile.admission_errors:
            await self._rollback();raise
        except Exception:
            await self._rollback();raise self._error('SERVICE_UNAVAILABLE',known) from None
        return row,view,dispatch,token,request

    async def _dispatch_admitted(self,row,token,request,*,deadline=None):
        known=row.id
        try:
            response=await self.profile.dispatch(self.client,request)
        except asyncio.CancelledError:
            # The grant remains; later owner GET can expire it without redispatch.
            raise
        except AIContractError:
            return await self._failed(known,token,'failed','RESULT_CONTRACT_INVALID')
        except AIValidationError:
            return await self._failed(known,token,'failed','DATA_INSUFFICIENT')
        except Exception:
            return await self._failed(known,token,'unknown','SERVICE_UNAVAILABLE')
        if self.usage_control is not None:
            try:await self.usage_control.observe(row,token,response)
            except asyncio.CancelledError:
                await self._rollback();raise
            except Exception:
                await self._rollback();raise self._error('SERVICE_UNAVAILABLE',known) from None
        if deadline is not None and time.monotonic()>=deadline:
            return await self._failed(known,token,'unknown','SERVICE_UNAVAILABLE')
        return await self._receive(known,token,response)

    async def _failed(self,id,token,state,code):
        try:
            row=await self._locked(id)
            await self.profile.repository.expire(self.session,row)
            if row.state=='running' and hmac.compare_digest(row.claim_digest,hashlib.sha256(token).digest()):
                row.state=state;row.error_code=code
            view=self._view(row);await self.session.commit();return view
        except self.profile.preserved_errors:
            await self._rollback();raise
        except Exception:
            await self._rollback();raise self._error('SERVICE_UNAVAILABLE',id) from None

    async def receive(self,expected,token,response):
        """Receive an already claimed run; never re-admit, re-claim or dispatch."""
        if not isinstance(self.profile,ResultCompletionProfile) or type(token) is not bytes or len(token)!=32:
            raise self._error('INPUT_INVALID')
        if self.session.new or self.session.dirty or self.session.deleted:raise self._error('SERVICE_UNAVAILABLE')
        expected,response=self.profile.freeze_received(expected,response)
        return await self._receive(expected.analysis_id,bytes(token),response,expected=expected)

    async def publish(self,id):
        """Explicit publication recovery only; GET remains non-publishing."""
        if not isinstance(self.profile,ResultCompletionProfile):raise self._error('INPUT_INVALID')
        if self.session.new or self.session.dirty or self.session.deleted:raise self._error('SERVICE_UNAVAILABLE',id)
        try:
            row=await self._locked(id)
            await self.profile.repository.expire(self.session,row)
            await self.profile.validate_state(self.session,row,self.principal)
            return await self._publish(row)
        except asyncio.CancelledError:
            await self._rollback();raise
        except self.profile.preserved_errors:
            await self._rollback();raise
        except Exception:
            await self._rollback();raise self._error('SERVICE_UNAVAILABLE',id) from None

    async def _receive(self,id,token,response,*,expected=None):
        completion=isinstance(self.profile,ResultCompletionProfile)
        if completion and expected is None:raise self._error('INPUT_INVALID',id)
        try:
            row=await self._locked(id);await self.profile.repository.expire(self.session,row)
            if completion:await self.profile.check_receive(self.session,row,self.principal,expected,token)
            if not hmac.compare_digest(row.claim_digest,hashlib.sha256(token).digest()):raise self._error('RESULT_CONTRACT_INVALID',id)
            if row.state!=(self.profile.receiving_state if completion else 'running'):
                if completion:await self.profile.verify_replay(self.session,row,self.principal,response)
                view=self._view(row);await self.session.commit();return view
            try:
                adapter:AnalysisAdapter=self._adapter(row)
                frozen=adapter.validate_and_freeze(response)
            except self.profile.contract_errors:
                if completion:await self.profile.prepare_terminal(self.session,row,'failed','RESULT_CONTRACT_INVALID')
                else:row.state='failed';row.error_code='RESULT_CONTRACT_INVALID'
                view=self._view(row);await self.session.commit();return view
            try:
                if completion:row=await self.profile.accept_result(self.session,row,hashlib.sha256(token).digest(),frozen)
                else:
                    row=await self.profile.repository.accept(self.session,row,hashlib.sha256(token).digest(),report_id=frozen.report_id,
                        input_json=frozen.input_json,input_sha256=frozen.input_sha256,result_json=frozen.result_json,result_sha256=frozen.result_sha256)
            except self.profile.snapshot_conflicts as error:
                if not self.profile.confirmed_snapshot_conflict(error):raise
                await self._rollback()
                return await self._failed(id,token,'failed','RESULT_CONFLICT')
            if row is None:
                row=await self._locked(id);await self.profile.repository.expire(self.session,row)
                view=self._view(row);await self.session.commit();return view
            await self.session.commit() # Durable snapshot; a lost ACK is recovered by owner replay.
        except asyncio.CancelledError:
            await self._rollback();raise
        except self.profile.preserved_errors:
            await self._rollback();raise
        except Exception:
            await self._rollback();raise self._error('SERVICE_UNAVAILABLE',id) from None
        try:
            row=await self._locked(id)
            return await self._publish(row)
        except asyncio.CancelledError:
            await self._rollback();raise
        except self.profile.preserved_errors:
            await self._rollback();raise
        except Exception:
            await self._rollback();raise self._error('SERVICE_UNAVAILABLE',id) from None

    async def _publish(self,row):
        if row.state!='result_ready':
            view=self._view(row);await self.session.commit();return view
        adapter:AnalysisAdapter=self._adapter(row)
        frozen=self.profile.from_stored(adapter,row)
        analysis_id,report_id=row.id,frozen.report_id
        try:
            await adapter.stage(self.session,self.principal,frozen)
        except self.profile.publish_errors as error:
            completion=isinstance(self.profile,ResultCompletionProfile)
            confirmed_conflict=False if completion else self.profile.confirmed_conflict(error)
            await self._rollback()
            row=await self._locked(analysis_id)
            if completion:
                disposition=await self.profile.publication_recovery(self.session,row,self.principal,frozen,error)
                if row.state=='result_ready' and disposition=='conflict':
                    await self.profile.prepare_terminal(self.session,row,'failed','RESULT_CONFLICT')
                    await self.session.commit()
                    raise self._error('RESULT_CONFLICT',analysis_id) from None
                # Same stored data or an uncertain lookup is not a conflict.
                # Preserve the durable ready snapshot for explicit recovery.
                raise self._error('SERVICE_UNAVAILABLE',analysis_id) from None
            existing=await self.profile.report_exists(self.session,report_id)
            if row.state=='result_ready' and (confirmed_conflict or existing):
                row.state='failed';row.error_code='RESULT_CONFLICT'
                await self.session.commit()
                raise self._error('RESULT_CONFLICT',analysis_id) from None
            raise self._error('SERVICE_UNAVAILABLE',analysis_id) from None
        row.state='stored'
        if isinstance(self.profile,ResultCompletionProfile):await self.profile.prepare_terminal(self.session,row,'stored')
        await self.session.flush()
        view=self._view(row)
        await self.session.commit() # Root/children/index/stored are one transaction.
        return view

    async def get(self,id):
        if isinstance(self.profile,ResultCompletionProfile) and (self.session.new or self.session.dirty or self.session.deleted):
            raise self._error('SERVICE_UNAVAILABLE',id)
        try:
            row=await self._locked(id);await self.profile.repository.expire(self.session,row)
            if isinstance(self.profile,ResultCompletionProfile):await self.profile.validate_state(self.session,row,self.principal)
            view=self._view(row);await self.session.commit();return view # Never publish or call AI.
        except self.profile.preserved_errors:
            await self._rollback();raise
        except Exception:
            await self._rollback();raise self._error('SERVICE_UNAVAILABLE',id) from None
