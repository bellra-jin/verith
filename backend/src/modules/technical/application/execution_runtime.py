"""Default-off, already-admitted run -> one synthetic boundary -> CF050.

No admission, provider permission, usage settlement, public route or retry.
The caller owns this clean SQL session and its lifetime/cancellation cleanup.
"""
import asyncio
from dataclasses import fields
from datetime import datetime,UTC
import math
import threading
import time
from uuid import UUID

from src.modules.auth.application.session_service import Principal,validate_principal
from src.modules.analysis.application.coordinator import AnalysisCoordinator
from src.modules.technical.domain.execution_admission import (
    Policy,RunReceipt,ClaimReceipt,CompletionReceipt,TechnicalCompletionError,TechnicalAdmissionError,decode,canonical,
)
from src.modules.technical.domain.execution_boundary import WAIT_SECONDS
from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService
from src.modules.technical.application.execution_completion import TechnicalCompletionProfile,binding_from_sql
from src.modules.technical.application.boundary_adapter import TechnicalBoundaryAdapter
from src.modules.technical.infrastructure import execution_completion_repository as completion
from src.modules.technical.infrastructure import execution_admission_repository as admission
from src.shared.infrastructure.clients.ai_client import AIClient,AITimeoutError

_DISPATCH=AIClient.technical_boundary
_CONFIGURE=AIClient._technical_boundary_configuration


def _same_method(method,owner,function):
    return getattr(method,'__self__',None) is owner and getattr(method,'__func__',None) is function


def _frozen_run(value):
    if type(value) is not RunReceipt:raise TechnicalCompletionError('SERVICE_UNAVAILABLE')
    return RunReceipt(**{f.name:UUID(int=getattr(value,f.name).int)
        if type(getattr(value,f.name)) is UUID else getattr(value,f.name) for f in fields(RunReceipt)})


class TechnicalExecutionRuntime:
    def __init__(self,session,*,principal,client=None,policy=None,enabled=False,
                 clock=time.monotonic,utcnow=None):
        self.session,self.principal,self.client=session,principal,client
        self.policy,self.enabled=policy,enabled
        self._clock=clock;self._utcnow=utcnow or (lambda:datetime.now(UTC))
        self._used=False;self._once=threading.Lock()

    def _preflight(self,expected,token):
        if (self.enabled is not True or type(self.policy) is not Policy or type(self.client) is not AIClient
                or type(token) is not bytes or len(token)!=32
                or self.session.new or self.session.dirty or self.session.deleted):
            raise TechnicalCompletionError('SERVICE_UNAVAILABLE')
        expected=_frozen_run(expected);policy=Policy(self.policy.text);policy.enabled()
        if expected.policy_sha256!=policy.fingerprint:raise TechnicalCompletionError('SERVICE_UNAVAILABLE')
        p=TechnicalAdmissionService(self.session,principal=self.principal)._principal()
        principal=Principal(UUID(int=p.user_id.int),UUID(int=p.session_id.int),p.expires_at,bytes(p.token_digest))
        client=self.client;dispatch=client.technical_boundary
        if not _same_method(dispatch,client,_DISPATCH) or not _same_method(client._technical_boundary_configuration,client,_CONFIGURE):
            raise TechnicalCompletionError('SERVICE_UNAVAILABLE')
        configuration=_CONFIGURE(client)
        anchor=self._clock();now=self._utcnow()
        if (type(anchor) not in (int,float) or not math.isfinite(anchor) or type(now) is not datetime
                or now.utcoffset()!=UTC.utcoffset(None) or now<expected.as_of):
            raise TechnicalCompletionError('SERVICE_UNAVAILABLE')
        left=min((expected.deadline_at-now).total_seconds(),(expected.deadline_at-expected.as_of).total_seconds())
        if left<=0:raise TechnicalCompletionError('SERVICE_UNAVAILABLE')
        return expected,bytes(token),policy,principal,client,dispatch,configuration,anchor+left

    def _remaining(self,run,deadline):
        now=self._utcnow();stamp=self._clock()
        if (type(now) is not datetime or now.utcoffset()!=UTC.utcoffset(None)
                or type(stamp) not in (int,float) or not math.isfinite(stamp)):
            raise TechnicalCompletionError('SERVICE_UNAVAILABLE',run.analysis_id)
        value=min(deadline-stamp,(run.deadline_at-now).total_seconds())
        if not math.isfinite(value) or value<=0:raise TechnicalCompletionError('SERVICE_UNAVAILABLE',run.analysis_id)
        return value

    @staticmethod
    def _configuration_unchanged(client,dispatch,configuration):
        if (not _same_method(client.technical_boundary,client,_DISPATCH)
                or not _same_method(dispatch,client,_DISPATCH)
                or not _same_method(client._technical_boundary_configuration,client,_CONFIGURE)
                or not configuration.same(_CONFIGURE(client))):
            raise TechnicalCompletionError('SERVICE_UNAVAILABLE')

    async def _fresh_request(self,run,token,principal,profile,deadline):
        try:
            await validate_principal(self.session,principal,lock=True)
            row=await completion.owned(self.session,run.analysis_id,principal.user_id)
            if row is None:raise TechnicalCompletionError('RESOURCE_NOT_FOUND')
            await completion.expire(self.session,row)
            await profile.check_receive(self.session,row,principal,run,token)
            if row.state!='claimed' or row.accepted_at is not None:
                await profile.validate_state(self.session,row,principal)
                view=profile.view(row);await self.session.commit()
                return None,view,deadline
            binding=binding_from_sql(row)
            request_text=canonical(TechnicalBoundaryAdapter(binding.boundary).build_request())
            anchor=self._clock();stamp=await admission.clock(self.session)
            deadline=min(deadline,anchor+(run.deadline_at-stamp).total_seconds())
            self._remaining(run,deadline)
            await self.session.commit()  # End all auth/period/run locks; ambiguous ACK sends nothing.
            return request_text,None,deadline
        except asyncio.CancelledError:raise
        except BaseException as error:
            try:await self.session.rollback()
            except Exception:pass
            if isinstance(error,profile.preserved_errors):raise
            raise TechnicalCompletionError('SERVICE_UNAVAILABLE',run.analysis_id) from None

    async def _client_failed(self,run,token,principal,policy,profile,reason):
        try:
            await validate_principal(self.session,principal,lock=True)
            row=await completion.owned(self.session,run.analysis_id,principal.user_id)
            if row is None:raise TechnicalCompletionError('RESOURCE_NOT_FOUND')
            await profile.check_receive(self.session,row,principal,run,token)
            if row.state!='claimed' or row.accepted_at is not None:
                await profile.validate_state(self.session,row,principal)
                view=profile.view(row);await self.session.commit();return view
            # Reuse the original closure while the same auth/period/run locks
            # remain held. No check-then-unlock gap can erase a ready result.
            closed=await TechnicalAdmissionService(self.session,principal=principal,policy=policy).close_unknown(run.analysis_id,reason)
            return CompletionReceipt(closed)
        except asyncio.CancelledError:raise
        except BaseException as error:
            try:await self.session.rollback()
            except Exception:pass
            if isinstance(error,profile.preserved_errors):raise
            raise TechnicalCompletionError('SERVICE_UNAVAILABLE',run.analysis_id) from None

    async def execute_admitted_once(self,expected,token):
        try:
            frozen=self._preflight(expected,token)
        except Exception:
            raise TechnicalCompletionError('SERVICE_UNAVAILABLE') from None
        with self._once:
            if self._used:raise TechnicalCompletionError('SERVICE_UNAVAILABLE')
            self._used=True
        run,token,policy,principal,client,dispatch,configuration,deadline=frozen
        service=TechnicalAdmissionService(self.session,principal=principal,policy=policy)
        profile=TechnicalCompletionProfile(policy=policy)
        coordinator=AnalysisCoordinator(self.session,principal=principal,client=None,profile=profile)
        # No caller-supplied/cached ClaimReceipt(True), second claim or retry.
        claim=await service.dispatch_claim(run,token)
        if type(claim) is not ClaimReceipt:raise TechnicalCompletionError('SERVICE_UNAVAILABLE',run.analysis_id)
        if not claim.newly_claimed:return await coordinator.get(run.analysis_id)
        run=_frozen_run(claim.run)
        request,view,deadline=await self._fresh_request(run,token,principal,profile,deadline)
        if view is not None:return view
        self._configuration_unchanged(client,dispatch,configuration)
        remaining=min(WAIT_SECONDS,self._remaining(run,deadline))
        # Only the client wait belongs to this failure closure. receive errors
        # may already have accepted/published and must never close_unknown.
        try:
            async with asyncio.timeout(remaining):
                response=await dispatch(decode(request),_configuration=configuration)
        except asyncio.CancelledError:
            # Consumed claim/hold remain; no SQL cleanup on a cancelling task.
            raise
        except (TimeoutError,AITimeoutError):
            return await self._client_failed(run,token,principal,policy,profile,'TIMEOUT')
        except Exception:
            return await self._client_failed(run,token,principal,policy,profile,'DISPATCH_UNCERTAIN')
        self._remaining(run,deadline)
        return await coordinator.receive(run,token,response)
