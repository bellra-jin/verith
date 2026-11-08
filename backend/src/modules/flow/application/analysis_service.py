"""Authenticated one-dispatch analysis; snapshot and publication are distinct commits."""
import asyncio
from datetime import UTC,datetime,timedelta
import hashlib
import hmac
import secrets
from uuid import UUID,uuid4
from sqlalchemy import select,func
from db.models.common.stock import Stock
from src.modules.auth.application.session_service import AuthenticationRequired,Principal,validate_principal
from src.modules.flow.api.analysis_schemas import AnalysisRequest,AnalysisView
from src.modules.flow.domain.execution import ContractViolation,ErrorCode,SafeError
from src.modules.flow.domain.analysis import OPERATION,SPEC,canonical,candidate,sha
from src.modules.flow.infrastructure import analysis_repository as repository
from src.modules.flow.application.report_service import FlowReportIdConflict
from src.modules.analysis.application.ports import AnalysisAdapter
from src.modules.flow.application.analysis_adapter import FlowAnalysisAdapter
from src.modules.flow.infrastructure import report_repository
from db.models.flow.flow_report import FlowReport
from sqlalchemy.exc import IntegrityError
from src.shared.infrastructure.clients.ai_client import AIContractError,AIValidationError


class AnalysisError(ValueError):
    def __init__(self,code,analysis_id=None):
        self.code,self.analysis_id=code,analysis_id
        super().__init__('Flow analysis failed')


class AnalysisService:
    def __init__(self,session,*,principal,client):
        self.session,self.principal,self.client=session,principal,client

    def _adapter(self,row)->FlowAnalysisAdapter:
        return FlowAnalysisAdapter(row,owner_user_id=self.principal.user_id)

    async def _authorize(self):
        if not isinstance(self.principal,Principal):raise AuthenticationRequired()
        await validate_principal(self.session,self.principal,lock=True)

    async def _locked(self,id):
        if not isinstance(id,UUID):raise AnalysisError(ErrorCode.INPUT_INVALID)
        await self._authorize()
        row=await repository.owned(self.session,id,self.principal.user_id)
        if row is None or row.state=='deleted':raise AnalysisError(ErrorCode.RESOURCE_NOT_FOUND)
        return row

    def _view(self,row):
        if row.state=='deleted':raise AnalysisError(ErrorCode.RESOURCE_NOT_FOUND)
        stored=row.state=='stored'
        return AnalysisView(analysis_id=row.id,admission_request_id=row.admission_request_id,
            attempt_id=row.attempt_id,state=row.state,deadline_at=row.deadline_at,
            report_id=row.adopted_report_id if stored else None,
            report_url=f'/reports/flow/{row.adopted_report_id}' if stored else None,
            error=SafeError(code=ErrorCode(row.error_code)) if row.error_code else None)

    async def _rollback(self):
        try:await self.session.rollback()
        except Exception:pass # Never infer that a previous ambiguous commit did not happen.

    async def post(self,body,request_id):
        known=None
        try:
            body=AnalysisRequest.model_validate(body.model_dump() if isinstance(body,AnalysisRequest) else body)
            if body.as_of>datetime.now(UTC):raise AnalysisError(ErrorCode.INPUT_INVALID)
            await self._authorize()
            key=hashlib.sha256(body.idempotency_key.encode()).digest()
            normalized=canonical(body.normalized_input());fingerprint=sha(normalized)
            row=await repository.by_key(self.session,self.principal.user_id,key)
            winner=False;token=None
            if row is None:
                stock=await self.session.scalar(select(Stock).where(Stock.stock_code==body.ticker))
                if stock is None or not stock.stock_name or not stock.stock_name.strip():raise AnalysisError(ErrorCode.INPUT_INVALID)
                name=stock.stock_name.strip()
                if len(name)>256 or any(ord(c)<32 for c in name):raise AnalysisError(ErrorCode.INPUT_INVALID)
                stamp=await self.session.scalar(select(func.clock_timestamp()));token=secrets.token_bytes(32)
                row=await repository.admit(self.session,dict(id=uuid4(),owner_user_id=self.principal.user_id,
                    operation=OPERATION,key_digest=key,input_fingerprint=fingerprint,admission_request_id=request_id,
                    attempt_id=uuid4(),ticker=body.ticker,stock_name=name,as_of=body.as_of,candidate_date=candidate(body.as_of),
                    request_json=normalized,spec_json=canonical(SPEC),claim_digest=hashlib.sha256(token).digest(),
                    started_at=stamp,deadline_at=stamp+timedelta(seconds=120),state='running'))
                winner=row is not None
                if row is None:row=await repository.by_key(self.session,self.principal.user_id,key)
            if row is None:raise AnalysisError(ErrorCode.SERVICE_UNAVAILABLE)
            known=row.id
            if row.input_fingerprint!=fingerprint:raise AnalysisError(ErrorCode.IDEMPOTENCY_CONFLICT,known)
            if row.state=='deleted':raise AnalysisError(ErrorCode.RESOURCE_NOT_FOUND,known)
            await repository.expire(self.session,row)
            if row.state=='result_ready':return await self._publish(row)
            view=self._view(row);dispatch=winner and row.state=='running'
            request=None
            if dispatch:
                adapter:AnalysisAdapter=self._adapter(row)
                request=adapter.build_request()
            await self.session.commit() # An ambiguous ACK must never dispatch.
        except asyncio.CancelledError:
            await self._rollback();raise
        except (AnalysisError,AuthenticationRequired,ContractViolation):
            await self._rollback();raise
        except Exception:
            await self._rollback();raise AnalysisError(ErrorCode.SERVICE_UNAVAILABLE,known) from None
        if not dispatch:return view
        try:
            response=await self.client.analyze_flow(request)
        except asyncio.CancelledError:
            # The grant remains; later owner GET can expire it without redispatch.
            raise
        except AIContractError:
            return await self._failed(known,token,'failed',ErrorCode.RESULT_CONTRACT_INVALID)
        except AIValidationError:
            return await self._failed(known,token,'failed',ErrorCode.DATA_INSUFFICIENT)
        except Exception:
            return await self._failed(known,token,'unknown',ErrorCode.SERVICE_UNAVAILABLE)
        return await self._receive(known,token,response)

    async def _failed(self,id,token,state,code):
        try:
            row=await self._locked(id)
            await repository.expire(self.session,row)
            if row.state=='running' and hmac.compare_digest(row.claim_digest,hashlib.sha256(token).digest()):
                row.state=state;row.error_code=code.value
            view=self._view(row);await self.session.commit();return view
        except (AuthenticationRequired,AnalysisError):
            await self._rollback();raise
        except Exception:
            await self._rollback();raise AnalysisError(ErrorCode.SERVICE_UNAVAILABLE,id) from None

    async def _receive(self,id,token,response):
        try:
            row=await self._locked(id);await repository.expire(self.session,row)
            if not hmac.compare_digest(row.claim_digest,hashlib.sha256(token).digest()):raise AnalysisError(ErrorCode.RESULT_CONTRACT_INVALID,id)
            if row.state!='running':
                view=self._view(row);await self.session.commit();return view
            try:
                adapter:AnalysisAdapter=self._adapter(row)
                frozen=adapter.validate_and_freeze(response)
            except ContractViolation:
                row.state='failed';row.error_code=ErrorCode.RESULT_CONTRACT_INVALID.value
                view=self._view(row);await self.session.commit();return view
            row=await repository.accept(self.session,row,hashlib.sha256(token).digest(),report_id=frozen.report_id,
                input_json=frozen.input_json,input_sha256=frozen.input_sha256,result_json=frozen.result_json,result_sha256=frozen.result_sha256)
            if row is None:
                row=await self._locked(id);await repository.expire(self.session,row)
                view=self._view(row);await self.session.commit();return view
            await self.session.commit() # Durable snapshot; a lost ACK is recovered by owner replay.
        except asyncio.CancelledError:
            await self._rollback();raise
        except (AuthenticationRequired,AnalysisError):
            await self._rollback();raise
        except Exception:
            await self._rollback();raise AnalysisError(ErrorCode.SERVICE_UNAVAILABLE,id) from None
        try:
            row=await self._locked(id)
            return await self._publish(row)
        except (AuthenticationRequired,AnalysisError):
            await self._rollback();raise
        except Exception:
            await self._rollback();raise AnalysisError(ErrorCode.SERVICE_UNAVAILABLE,id) from None

    async def _publish(self,row):
        if row.state!='result_ready':
            view=self._view(row);await self.session.commit();return view
        flow=self._adapter(row)
        adapter:AnalysisAdapter=flow
        frozen=flow.from_stored(row)
        analysis_id,report_id=row.id,frozen.report_id
        try:
            await adapter.stage(self.session,self.principal,frozen)
        except (FlowReportIdConflict,IntegrityError) as error:
            # A legacy/concurrent publisher owns that UUID. Preserve its data and
            # terminally reject this publication: deleting the old report must not
            # make a later replay eligible to recreate it under the same UUID.
            # Exact PostgreSQL root PK violation also establishes the collision, even
            # if the concurrent winner deletes its root before this rollback ends.
            cause=getattr(getattr(error,'orig',None),'__cause__',None)
            confirmed_conflict=isinstance(error,FlowReportIdConflict) or (
                getattr(cause,'sqlstate',None)=='23505' and getattr(cause,'constraint_name',None)=='pk_flow_reports')
            await self._rollback()
            row=await self._locked(analysis_id)
            existing=await self.session.scalar(select(FlowReport.id).where(FlowReport.id==report_id))
            indexes=await report_repository.get_agent_indexes(self.session,report_id)
            if row.state=='result_ready' and (confirmed_conflict or existing is not None or indexes):
                row.state='failed';row.error_code=ErrorCode.RESULT_CONFLICT.value
                await self.session.commit()
                raise AnalysisError(ErrorCode.RESULT_CONFLICT,analysis_id) from None
            raise AnalysisError(ErrorCode.SERVICE_UNAVAILABLE,analysis_id) from None
        row.state='stored'
        await self.session.flush()
        view=self._view(row)
        await self.session.commit() # Root/children/index/stored are one transaction.
        return view

    async def get(self,id):
        try:
            row=await self._locked(id);await repository.expire(self.session,row)
            view=self._view(row);await self.session.commit();return view # Never publish or call AI.
        except (AnalysisError,AuthenticationRequired):
            await self._rollback();raise
        except Exception:
            await self._rollback();raise AnalysisError(ErrorCode.SERVICE_UNAVAILABLE,id) from None
