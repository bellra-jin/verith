"""Flow public service facade over the shared fixed-profile coordinator."""
import asyncio,hashlib,hmac,time,math
from dataclasses import dataclass
from datetime import UTC,datetime
from types import SimpleNamespace
from src.modules.analysis.application.coordinator import AnalysisCoordinator
from src.modules.flow.api.analysis_schemas import AnalysisView
from src.modules.flow.domain.analysis import canonical,decode
from src.modules.auth.application.session_service import Principal
from src.modules.analysis.application.usage_service import FlowUsageControl
from src.modules.analysis.application.ports import CoordinatorError
from src.modules.flow.application.analysis_profile import FlowProfile
# Keep the original class/module references for existing focused callers.
from src.modules.flow.application.analysis_adapter import FlowAnalysisAdapter
from src.modules.flow.infrastructure import analysis_repository as repository,report_repository


class AnalysisError(CoordinatorError):
    def __init__(self,code,analysis_id=None):
        self.code,self.analysis_id=code,analysis_id
        super().__init__('Flow analysis failed')


class AnalysisService(AnalysisCoordinator):
    def __init__(self,session,*,principal,client):
        super().__init__(session,principal=principal,client=client,profile=FlowProfile(AnalysisError),usage_control=FlowUsageControl(session,AnalysisError))
        self._continuations={}

    def discard_continuations(self):
        self._continuations.clear()

    async def admit_only(self,body,request_id,*,admission_before,admission_deadline,total_deadline):
        """Composition-only admission. Existing public POST still executes inline.

        No replay publishes or mints a continuation. A slow/missing commit ACK
        retains the reservation but cannot confer a new execution opportunity.
        """
        if self.session.new or self.session.dirty or self.session.deleted:raise self._error('SERVICE_UNAVAILABLE')
        try:
            if (type(admission_before) is not datetime or admission_before.utcoffset()!=UTC.utcoffset(None)
                    or any(type(v) is not float or not math.isfinite(v) for v in (admission_deadline,total_deadline))
                    or not time.monotonic()<admission_deadline<=total_deadline):raise ValueError()
            captured=composition_client(self.client)
            principal=self.principal
            if type(principal) is not Principal:raise ValueError()
        except Exception:raise self._error('SERVICE_UNAVAILABLE') from None
        anchor=time.monotonic()
        row,view,winner,token,request=await self._admit(body,request_id,admission_before=admission_before,publish_ready=False)
        fresh=winner and time.monotonic()<admission_deadline
        receipt=FlowAdmission(view,bool(fresh))
        if fresh:
            from db.models.flow.analysis_run import FlowAnalysisRun
            frozen=SimpleNamespace(**{c.name:getattr(row,c.name) for c in FlowAnalysisRun.__table__.columns})
            native_deadline=min(total_deadline,anchor+(row.deadline_at-row.started_at).total_seconds())
            self._continuations[id(receipt)]=(receipt,frozen,token,canonical(request),principal,captured,native_deadline)
        return receipt

    async def execute_admitted_once(self,receipt):
        """Consume this object's invocation-local grant before any new await."""
        if self.session.new or self.session.dirty or self.session.deleted:raise self._error('SERVICE_UNAVAILABLE')
        entry=self._continuations.pop(id(receipt),None)
        if type(receipt) is not FlowAdmission or entry is None or entry[0] is not receipt:
            raise self._error('SERVICE_UNAVAILABLE')
        _,expected,token,request_json,principal,captured,total_deadline=entry
        if self.principal!=principal or receipt.newly_admitted is not True:raise self._error('SERVICE_UNAVAILABLE')
        self.client=captured  # Only the captured service-owned client may send.
        anchor=time.monotonic()
        try:
            row=await self._locked(expected.id)
            if (row.owner_user_id!=principal.user_id or row.key_digest!=expected.key_digest
                    or row.input_fingerprint!=expected.input_fingerprint or row.request_json!=expected.request_json
                    or row.as_of!=expected.as_of or row.deadline_at!=expected.deadline_at
                    or row.spec_json!=expected.spec_json or row.stock_name!=expected.stock_name
                    or row.admission_request_id!=expected.admission_request_id or row.attempt_id!=expected.attempt_id
                    or not hmac.compare_digest(bytes(row.claim_digest),hashlib.sha256(token).digest())):
                raise self._error('SERVICE_UNAVAILABLE',expected.id)
            await self.profile.repository.expire(self.session,row)
            if row.state!='running':
                view=self._view(row);await self.session.commit();return view
            from sqlalchemy import select,func
            stamp=await self.session.scalar(select(func.clock_timestamp()))
            deadline=min(total_deadline,anchor+(row.deadline_at-stamp).total_seconds())
            if canonical(self._adapter(row).build_request())!=request_json:raise self._error('SERVICE_UNAVAILABLE',expected.id)
            await self.session.commit()
        except asyncio.CancelledError:raise
        except self.profile.preserved_errors:
            await self._rollback();raise
        except Exception:
            await self._rollback();raise self._error('SERVICE_UNAVAILABLE',expected.id) from None
        remaining=deadline-time.monotonic()
        if remaining<=0:return await self._failed(expected.id,token,'unknown','SERVICE_UNAVAILABLE')
        try:
            async with asyncio.timeout(remaining):
                return await self._dispatch_admitted(expected,token,decode(request_json),deadline=deadline)
        except TimeoutError:
            # _failed changes only a still-running row; accepted/stored data and
            # independent usage survive a publication timeout.
            return await self._failed(expected.id,token,'unknown','SERVICE_UNAVAILABLE')


@dataclass(frozen=True,slots=True,repr=False)
class FlowAdmission:
    """A native view, not a serialized execution token."""
    view: AnalysisView
    newly_admitted: bool


def composition_client(client):
    """Capture the existing Flow client's explicit config before the first await."""
    from urllib.parse import urlsplit
    import httpx
    from src.shared.infrastructure.clients.ai_client import AIClient
    try:
        if type(client) is not AIClient:raise ValueError()
        base=client._base_url;token=client._flow_token;transport=client._transport
        target=urlsplit(base);httpx.URL(base);raw=token.encode('utf8')
        if (target.scheme not in {'http','https'} or not target.hostname or target.username or target.password
                or target.port==0 or target.path not in {'','/'} or target.query or target.fragment
                or len(raw)<32 or any(c<32 or c==127 for c in raw)
                or transport is not None and type(transport) is not httpx.ASGITransport):raise ValueError()
        return AIClient(base,client._timeout,transport,service_token=token)
    except Exception:raise AnalysisError('SERVICE_UNAVAILABLE') from None
