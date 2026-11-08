"""One claim/dispatch/snapshot/publication coordinator for two fixed profiles.

No agent registry, agent-domain imports, dispatch retry, session creation or provider I/O.
The authenticated caller owns the session; profile supplies domain-specific rules.
"""
import asyncio
from datetime import timedelta
import hashlib
import hmac
import secrets
from uuid import UUID,uuid4
from sqlalchemy import select,func
from db.models.common.stock import Stock
from src.modules.auth.application.session_service import AuthenticationRequired,Principal,validate_principal
from src.modules.analysis.application.ports import AnalysisAdapter,AnalysisProfile
from src.shared.infrastructure.clients.ai_client import AIContractError,AIValidationError

class AnalysisCoordinator:
    def __init__(self,session,*,principal,client,profile:AnalysisProfile):
        self.session,self.principal,self.client=session,principal,client
        self.profile=profile

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
        known=None
        try:
            body=self.profile.parse(body)
            await self._authorize()
            key=hashlib.sha256(body.idempotency_key.encode()).digest()
            normalized=self.profile.normalized(body);fingerprint=hashlib.sha256(normalized.encode()).hexdigest()
            row=await self.profile.repository.by_key(self.session,self.principal.user_id,key)
            winner=False;token=None
            if row is None:
                stock=await self.session.scalar(select(Stock).where(Stock.stock_code==body.ticker))
                if stock is None or not stock.stock_name or not stock.stock_name.strip():raise self._error('INPUT_INVALID')
                name=stock.stock_name.strip()
                if len(name)>256 or any(ord(c)<32 for c in name):raise self._error('INPUT_INVALID')
                stamp=await self.session.scalar(select(func.clock_timestamp()));token=secrets.token_bytes(32)
                row=await self.profile.repository.admit(self.session,dict(id=uuid4(),owner_user_id=self.principal.user_id,
                    operation=self.profile.operation,key_digest=key,input_fingerprint=fingerprint,admission_request_id=request_id,
                    attempt_id=uuid4(),ticker=body.ticker,stock_name=name,**self.profile.input_clock(body,stamp),
                    request_json=normalized,spec_json=self.profile.spec_json(),claim_digest=hashlib.sha256(token).digest(),
                    started_at=stamp,deadline_at=stamp+timedelta(seconds=self.profile.deadline_seconds),state='running'))
                winner=row is not None
                if row is None:row=await self.profile.repository.by_key(self.session,self.principal.user_id,key)
            if row is None:raise self._error('SERVICE_UNAVAILABLE')
            known=row.id
            if row.input_fingerprint!=fingerprint:raise self._error('IDEMPOTENCY_CONFLICT',known)
            if row.state=='deleted':raise self._error('RESOURCE_NOT_FOUND',known)
            await self.profile.repository.expire(self.session,row)
            if row.state=='result_ready':return await self._publish(row)
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
        if not dispatch:return view
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

    async def _receive(self,id,token,response):
        try:
            row=await self._locked(id);await self.profile.repository.expire(self.session,row)
            if not hmac.compare_digest(row.claim_digest,hashlib.sha256(token).digest()):raise self._error('RESULT_CONTRACT_INVALID',id)
            if row.state!='running':
                view=self._view(row);await self.session.commit();return view
            try:
                adapter:AnalysisAdapter=self._adapter(row)
                frozen=adapter.validate_and_freeze(response)
            except self.profile.contract_errors:
                row.state='failed';row.error_code='RESULT_CONTRACT_INVALID'
                view=self._view(row);await self.session.commit();return view
            try:
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
            confirmed_conflict=self.profile.confirmed_conflict(error)
            await self._rollback()
            row=await self._locked(analysis_id)
            existing=await self.profile.report_exists(self.session,report_id)
            if row.state=='result_ready' and (confirmed_conflict or existing):
                row.state='failed';row.error_code='RESULT_CONFLICT'
                await self.session.commit()
                raise self._error('RESULT_CONFLICT',analysis_id) from None
            raise self._error('SERVICE_UNAVAILABLE',analysis_id) from None
        row.state='stored'
        await self.session.flush()
        view=self._view(row)
        await self.session.commit() # Root/children/index/stored are one transaction.
        return view

    async def get(self,id):
        try:
            row=await self._locked(id);await self.profile.repository.expire(self.session,row)
            view=self._view(row);await self.session.commit();return view # Never publish or call AI.
        except self.profile.preserved_errors:
            await self._rollback();raise
        except Exception:
            await self._rollback();raise self._error('SERVICE_UNAVAILABLE',id) from None
