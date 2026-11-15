"""One internal invocation: admit both fixed children, then execute serially.

No public route/planner, new ledger, claim recovery or provider authority. Native
services retain their own usage, result, replay and unknown-hold contracts.
"""
import asyncio
import logging
import time
import math
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from src.modules.auth.application.session_service import AuthenticationRequired
from src.modules.supervisor.application.composition_service import Admission,CompositionError,CompositionService
from src.modules.supervisor.domain.composition import PROJECTED_VERSION
from src.modules.flow.application.analysis_service import AnalysisService as FlowService,composition_client
from src.modules.technical.application.execution_runtime import TechnicalExecutionRuntime
from src.modules.technical.domain import provider_execution as P
from src.modules.technical.domain.execution_admission import Policy
from src.shared.infrastructure.clients.ai_client import AIClient

_LOG=logging.getLogger(__name__)
_CODES=frozenset({'ACK_UNKNOWN','UNAVAILABLE','SERVICE_UNAVAILABLE','FEATURE_UNAVAILABLE','EXPIRED',
    'CLOCK_UNKNOWN','SESSION_REQUIRED','INVALID','POLICY_UNAVAILABLE','LIMIT_EXCEEDED','INPUT_INVALID',
    'IDEMPOTENCY_CONFLICT','STORED_INVALID','RESOURCE_NOT_FOUND'})


def _diagnostic(phase,error):
    code=getattr(error,'code',None)
    code=code if type(code) is str and code in _CODES else 'UNAVAILABLE'
    # phase is a fixed call-site literal. No exception text/SQL/input/client data.
    _LOG.warning('composition phase=%s code=%s',phase,code)


class CompositionRuntime:
    def __init__(self,session,*,principal,flow_client=None,technical_client=None,enabled=False):
        self.session=session;self.principal=principal;self.flow_client=flow_client
        self.technical_client=technical_client;self.enabled=enabled
        self.root=CompositionService(session,principal=principal)

    async def _scope(self,admission):
        await self.root._begin()
        row=await self.root._locked(admission.id)
        self.root._token(row,admission.token)
        snapshot=self.root._checked(row)
        if snapshot is None:raise CompositionError('NOT_FOUND')
        if snapshot.data()['schema_version']!=PROJECTED_VERSION:raise CompositionError('INVALID')
        before=row.admission_before
        await self.session.rollback()
        return snapshot,before

    @staticmethod
    def _technical_client(client,cfg):
        if type(client) is not AIClient:raise CompositionError()
        captured=client._technical_execution_configuration(cfg)
        return AIClient(captured.origin,client._timeout,captured.transport,
            execution_token=captured.token.decode('ascii'),technical_tls_context=captured.owned_tls)

    async def execute_once(self,admission):
        """A replay is observation; only this start ACK may hand off/execute."""
        if type(admission) is not Admission:raise CompositionError('INVALID')
        if not admission.newly_admitted:return await self.root.get(admission.id)
        if self.enabled is not True:raise CompositionError()
        if (any(type(v) is not float or not math.isfinite(v) for v in (admission.deadline,admission.admission_deadline))
                or not time.monotonic()<admission.admission_deadline<=admission.deadline):raise CompositionError('EXPIRED')
        try:
            async with asyncio.timeout_at(admission.deadline):
                return await self._execute(admission)
        except TimeoutError:raise CompositionError('EXPIRED') from None

    async def _execute(self,admission):
        flow=None;right=None
        try:
            async with asyncio.timeout_at(admission.admission_deadline):
                snapshot,before=await self._scope(admission);data=snapshot.data();views=data['selected_views']
                # Capture explicit native configuration before root claim or outbound
                # readiness. No mutable caller client/settings are read afterwards.
                if 'flow' in views:
                    flow=FlowService(self.session,principal=self.principal,client=composition_client(self.flow_client))
                    limits=data['flow_policy']
                    flow.usage_control.settings=SimpleNamespace(FLOW_USAGE_LIMITS_ENABLED='true',
                        FLOW_SUPPORTED_TICKERS=','.join(limits['supported_tickers']),
                        FLOW_USER_DAILY_REQUEST_LIMIT=str(limits['user_limit']),FLOW_SERVICE_DAILY_REQUEST_LIMIT=str(limits['service_limit']),
                        FLOW_SERVICE_DAILY_BUDGET_USD=format(Decimal(limits['budget'])/Decimal(1000000000),'f'))
                technical=None;cfg=None
                if 'technical' in views:
                    cfg=P.Configuration(data['technical_configuration']);client=self._technical_client(self.technical_client,cfg)
                    technical=TechnicalExecutionRuntime(self.session,principal=self.principal,client=client,
                        policy=Policy(P.canonical(cfg.data()['policy'])),enabled=True)
                right=await self.root.start(admission)
                if not right.newly_started:return await self.root.get(admission.id)
            # This is the original fixed root clock. No child or failure starts
            # another full timeout, and timeout/cancellation does no SQL retry.
            async with asyncio.timeout_at(right.deadline):
                tech_admission=None;tech_deadline=None;flow_admission=None
                if technical is not None:
                    await self.root.handoff(right,'technical');key,_=self.root.take_handoff(right,'technical')
                    try:
                        anchor=time.monotonic()
                        async with asyncio.timeout_at(right.admission_deadline):
                            tech_admission=await technical.admit_provider_once(key,self.root.technical_intent(snapshot),cfg,admission_before=before)
                            if not tech_admission.newly_admitted:raise CompositionError('ACK_UNKNOWN')
                            tech_deadline=min(right.deadline,anchor+(tech_admission.run.deadline_at-tech_admission.run.as_of).total_seconds())
                            await self.root.link(right,'technical',tech_admission)
                    except AuthenticationRequired:raise
                    except asyncio.CancelledError:raise
                    except Exception as error:
                        _diagnostic('technical_admission',error)
                        return await self._finish(right)
                if flow is not None:
                    try:
                        await self.root.handoff(right,'flow');key,stamp=self.root.take_handoff(right,'flow')
                        async with asyncio.timeout_at(right.admission_deadline):
                            flow_admission=await flow.admit_only(dict(ticker=data['stock']['stock_code'],
                                question=data['child_inputs']['flow']['question'],as_of=stamp.isoformat(),idempotency_key=key,allow_analysis=True),uuid4(),
                                admission_before=before,admission_deadline=right.admission_deadline,total_deadline=right.deadline)
                            await self.root.link(right,'flow',flow_admission.view)
                    except AuthenticationRequired:raise
                    except asyncio.CancelledError:raise
                    except Exception as error:
                        # A confirmed Technical admission/as-of survives another
                        # child's missing ACK. Do not re-POST or re-admit Flow.
                        _diagnostic('flow_admission',error);flow_admission=None
                # Both admission phases have now ended. No handoff is attempted
                # after a model request; child native deadlines remain unchanged.
                if tech_admission is not None:
                    try:
                        async with asyncio.timeout_at(tech_deadline):
                            await technical.execute_provider_once(tech_admission.run,tech_admission.claim_token,cfg)
                    except AuthenticationRequired:raise
                    except asyncio.CancelledError:raise
                    except Exception as error:_diagnostic('technical_execution',error)
                if flow_admission is not None and flow_admission.newly_admitted:
                    try:await flow.execute_admitted_once(flow_admission)
                    except AuthenticationRequired:raise
                    except asyncio.CancelledError:raise
                    except Exception as error:_diagnostic('flow_execution',error)
                return await self._finish(right)
        except asyncio.CancelledError:
            # The caller's owning AsyncSession context releases locks. Never
            # attach SQL cleanup/re-admission to the cancelling task.
            self.root._poisoned=True;raise
        except TimeoutError:raise CompositionError('EXPIRED') from None
        except (AuthenticationRequired,CompositionError):
            if not (self.session.new or self.session.dirty or self.session.deleted):await self.root._rollback()
            raise
        except Exception:
            if not (self.session.new or self.session.dirty or self.session.deleted):await self.root._rollback()
            raise CompositionError() from None
        finally:
            self.root._tickets.clear();self.root._taken.clear()
            if flow is not None:flow.discard_continuations()

    async def _finish(self,right):
        if not self.root._poisoned:await self.root.close(right)
        return await self.root.get(right.id)
