"""Immutable composition admission/one-time handoff journal.

No child admission/claim/dispatch or money mutation is performed here. The caller
must use the native services once and supply their acknowledged receipts. A replay
only observes fixed keys. Root rights never cross the original confirmation session.
"""
import asyncio,hashlib,hmac,secrets,time,math
from dataclasses import dataclass,field
from datetime import UTC,datetime,timedelta
from uuid import UUID,uuid4
from src.modules.auth.application.session_service import Principal,AuthenticationRequired,validate_principal
from src.modules.supervisor.domain.composition import (
    CompositionSnapshot,CompositionInvalid,ChildObservation,coverage,fixed_child_key,
)
from src.modules.supervisor.infrastructure import composition_repository as repo
from src.modules.stocks.application.resolver_service import StockResolverService
from src.modules.technical.infrastructure.execution_admission_repository import database_uuid


class CompositionError(RuntimeError):
    def __init__(self,code='UNAVAILABLE'):
        self.code=code if type(code) is str and code in {'UNAVAILABLE','ACK_UNKNOWN','INVALID','NOT_FOUND','CONFLICT','EXPIRED','SESSION_REQUIRED','CLOCK_UNKNOWN'} else 'UNAVAILABLE'
        super().__init__('Supervisor composition unavailable')


@dataclass(frozen=True,slots=True)
class Admission:
    id:UUID
    newly_admitted:bool
    token:bytes|None=field(repr=False)


@dataclass(frozen=True,slots=True)
class Start:
    id:UUID
    owner_user_id:UUID
    confirmation_session_id:UUID
    newly_started:bool
    token:bytes|None=field(repr=False)
    deadline:float|None=field(default=None,repr=False)
    admission_deadline:float|None=field(default=None,repr=False)
    _issuer:object=field(default=None,repr=False)


class CompositionService:
    def __init__(self,session,*,principal,resolver_factory=StockResolverService):
        self.session,self.principal=session,principal
        self.resolver_factory=resolver_factory
        self._issuer=object();self._poisoned=False;self._tickets={};self._closed_roots=set();self._taken=set()

    async def _rollback(self):
        try:await self.session.rollback()
        except Exception:pass

    async def _commit(self):
        try:await self.session.commit()
        except asyncio.CancelledError:
            self._poisoned=True;self._tickets.clear();raise
        except Exception:
            self._poisoned=True;self._tickets.clear()
            raise CompositionError('ACK_UNKNOWN') from None

    async def _begin(self,*,lock=False,observation=False):
        if self._poisoned and not observation:raise CompositionError('ACK_UNKNOWN')
        if self.session.new or self.session.dirty or self.session.deleted:
            raise CompositionError()
        await self.session.rollback()
        if type(self.principal) is not Principal:raise AuthenticationRequired()
        await validate_principal(self.session,self.principal,lock=lock)

    @staticmethod
    def _stamp(value):
        if type(value) is not datetime or value.utcoffset() is None:raise CompositionInvalid()
        return value.astimezone(UTC)

    def _checked(self,row,snapshot=None):
        if row is None:raise CompositionError('NOT_FOUND')
        if database_uuid(row.owner_user_id)!=self.principal.user_id:raise CompositionError('NOT_FOUND')
        database_uuid(row.id);database_uuid(row.confirmation_session_id)
        if row.confirm_digest!=row.snapshot_sha256:raise CompositionInvalid()
        if snapshot is not None and snapshot.fingerprint!=row.snapshot_sha256:raise CompositionError('CONFLICT')
        if row.state=='redacted':return None
        saved=CompositionSnapshot(row.snapshot_json)
        if saved.fingerprint!=row.snapshot_sha256 or row.confirm_digest!=saved.fingerprint:
            raise CompositionInvalid()
        if snapshot is not None and snapshot.text!=saved.text:raise CompositionError('CONFLICT')
        for view in ('flow','technical'):
            expected=hashlib.sha256(fixed_child_key(database_uuid(row.id),view,bytes(row.claim_digest)).encode()).digest() if view in saved.data()['selected_views'] else None
            if getattr(row,view+'_key_digest')!=expected:raise CompositionInvalid()
        return saved

    async def _fail(self,error):
        # Reject a caller's pending ORM changes without discarding them. This
        # service writes only Core statements after the clean-session check.
        if not (self.session.new or self.session.dirty or self.session.deleted):
            await self._rollback()
        if isinstance(error,CompositionError):raise CompositionError(error.code) from None
        if isinstance(error,AuthenticationRequired):raise error
        if isinstance(error,CompositionInvalid):raise CompositionError('INVALID') from None
        raise CompositionError() from None

    async def admit(self,key,snapshot,*,request_started_at):
        try:
            if (type(snapshot) is not CompositionSnapshot or type(key) is not str
                    or str(UUID(key))!=key):raise CompositionInvalid()
            snapshot=CompositionSnapshot(snapshot.text)
            started=self._stamp(request_started_at);digest=hashlib.sha256(key.encode()).digest()
            await self._begin(lock=True)
            prior=await repo.read(self.session,self.principal.user_id,key=digest)
            if prior is not None:
                self._checked(prior,snapshot);await self.session.rollback()
                return Admission(database_uuid(prior.id),False,None)
            now=self._stamp(await repo.clock(self.session))
            if not started<=now<started+timedelta(seconds=15):raise CompositionError('EXPIRED')
            data=snapshot.data()
            lookup=next(m['text'] for m in data['frame']['mentions'] if m['negated'] is False)
            resolver=self.resolver_factory(self.session)
            resolved=await resolver.resolve(lookup)
            if (data['draft']['selected_ticker'] is not None or resolved.status!='resolved'
                    or resolved.stock is None or resolved.stock.model_dump(mode='json')!=data['stock']):
                raise CompositionError('INVALID')
            for mention in data['frame']['mentions']:
                if mention['negated']:
                    excluded=await resolver.resolve(mention['text'])
                    if excluded.status!='resolved' or excluded.stock is None or excluded.stock.stock_code==resolved.stock.stock_code:
                        raise CompositionError('INVALID')
            stock=await repo.stock(self.session,data['stock']['stock_code'])
            if stock is None or any(getattr(stock,k)!=data['stock'][k] for k in ('stock_code','stock_name','market')):
                raise CompositionError('INVALID')
            now=self._stamp(await repo.clock(self.session))
            if now>=started+timedelta(seconds=15):raise CompositionError('EXPIRED')
            id=uuid4();token=secrets.token_bytes(32)
            row=await repo.admit(self.session,dict(id=id,owner_user_id=self.principal.user_id,
                confirmation_session_id=self.principal.session_id,client_key_digest=digest,
                confirm_digest=snapshot.fingerprint,snapshot_json=snapshot.text,snapshot_sha256=snapshot.fingerprint,
                claim_digest=hashlib.sha256(token).digest(),request_started_at=started,confirmed_at=now,
                admission_before=started+timedelta(seconds=15),deadline_at=started+timedelta(seconds=140),
                state='admitted',analysis_as_of=None if 'technical' in data['selected_views'] else now,
                **{view+'_key_digest':hashlib.sha256(fixed_child_key(id,view,hashlib.sha256(token).digest()).encode()).digest()
                   if view in data['selected_views'] else None for view in ('flow','technical')}))
            if row is None:
                await self.session.rollback();prior=await repo.read(self.session,self.principal.user_id,key=digest)
                self._checked(prior,snapshot);await self.session.rollback()
                return Admission(database_uuid(prior.id),False,None)
            self._checked(row,snapshot)
            await self._commit()  # Only this ACK returns the ephemeral admission token.
            return Admission(database_uuid(row.id),True,token)
        except asyncio.CancelledError:
            self._poisoned=True;self._tickets.clear();raise
        except Exception as error:return await self._fail(error)

    async def _locked(self,id):
        if type(id) is not UUID:raise CompositionInvalid()
        row=await repo.read(self.session,self.principal.user_id,id=id,lock=True)
        self._checked(row)
        return row

    def _token(self,row,token):
        if (type(token) is not bytes or len(token)!=32
                or not hmac.compare_digest(hashlib.sha256(token).digest(),bytes(row.claim_digest))):
            raise CompositionError('SESSION_REQUIRED')
        if database_uuid(row.confirmation_session_id)!=self.principal.session_id:
            raise CompositionError('SESSION_REQUIRED')

    async def start(self,admission):
        try:
            if type(admission) is not Admission or not admission.newly_admitted or admission.token is None:
                raise CompositionError('SESSION_REQUIRED')
            await self._begin(lock=True);row=await self._locked(admission.id);self._token(row,admission.token)
            anchor=time.monotonic();now=self._stamp(await repo.clock(self.session))
            local_deadline=anchor+(row.deadline_at-now).total_seconds()
            admission_deadline=anchor+(row.admission_before-now).total_seconds()
            if row.state!='admitted' or now>=row.admission_before or now>=row.deadline_at:
                await self.session.rollback()
                return Start(admission.id,self.principal.user_id,self.principal.session_id,False,None)
            await repo.change(self.session,row,dict(state='claimed',claimed_at=now))
            await self._commit()  # Unknown ACK cannot return a fresh Start right.
            if time.monotonic()>=min(local_deadline,admission_deadline):
                return Start(admission.id,self.principal.user_id,self.principal.session_id,False,None)
            return Start(admission.id,self.principal.user_id,self.principal.session_id,True,admission.token,local_deadline,admission_deadline,self._issuer)
        except asyncio.CancelledError:
            self._poisoned=True;self._tickets.clear();raise
        except Exception as error:return await self._fail(error)

    async def _right(self,right):
        if (type(right) is not Start or right.newly_started is not True or right.token is None
                or right._issuer is not self._issuer or self._poisoned or right.id in self._closed_roots
                or type(right.deadline) is not float or not math.isfinite(right.deadline)
                or type(right.admission_deadline) is not float or not math.isfinite(right.admission_deadline)
                or right.admission_deadline>right.deadline or time.monotonic()>=right.deadline):
            raise CompositionError('SESSION_REQUIRED')
        row=await self._locked(right.id);self._token(row,right.token)
        if (right.owner_user_id!=self.principal.user_id or right.confirmation_session_id!=self.principal.session_id
                or row.state!='claimed'):raise CompositionError('SESSION_REQUIRED')
        if self._stamp(await repo.clock(self.session))>=row.deadline_at:raise CompositionError('EXPIRED')
        return row

    async def handoff(self,right,view):
        """Persist consumption BEFORE the single native call, without calling it."""
        try:
            if type(view) is not str or view not in ('flow','technical'):raise CompositionInvalid()
            await self._begin(lock=True);row=await self._right(right);snapshot=self._checked(row)
            if view not in snapshot.data()['selected_views']:raise CompositionInvalid()
            if getattr(row,view+'_handoff_at') is not None:raise CompositionError('CONFLICT')
            if view=='flow' and row.analysis_as_of is None:raise CompositionError('CLOCK_UNKNOWN')
            now=self._stamp(await repo.clock(self.session))
            if now>=row.admission_before or time.monotonic()>=right.admission_deadline:raise CompositionError('EXPIRED')
            await repo.change(self.session,row,{view+'_handoff_at':now});await self._commit()
            if time.monotonic()>=min(right.deadline,right.admission_deadline):raise CompositionError('EXPIRED')
            self._tickets[(right.id,view)]=(fixed_child_key(right.id,view,hashlib.sha256(right.token).digest()),row.analysis_as_of,min(right.deadline,right.admission_deadline))
        except asyncio.CancelledError:
            self._poisoned=True;self._tickets.clear();raise
        except Exception as error:return await self._fail(error)

    async def close(self,right):
        try:
            if (type(right) is not Start or right._issuer is not self._issuer or right.newly_started is not True
                    or right.owner_user_id!=self.principal.user_id or right.confirmation_session_id!=self.principal.session_id):raise CompositionError('SESSION_REQUIRED')
            self._closed_roots.add(right.id)
            self._tickets={key:value for key,value in self._tickets.items() if key[0]!=right.id}
            await self._begin(lock=True);row=await self._locked(right.id);self._token(row,right.token)
            if row.state in ('admitted','claimed'):
                await repo.change(self.session,row,dict(state='closed',closed_at=self._stamp(await repo.clock(self.session))))
                await self._commit()
            else:await self.session.rollback()
        except asyncio.CancelledError:
            self._poisoned=True;self._tickets.clear();raise
        except Exception as error:return await self._fail(error)


    def take_handoff(self,right,view):
        if (type(right) is not Start or right._issuer is not self._issuer
                or right.newly_started is not True or self._poisoned or right.id in self._closed_roots
                or right.owner_user_id!=self.principal.user_id or right.confirmation_session_id!=self.principal.session_id):
            raise CompositionError('SESSION_REQUIRED')
        if type(view) is not str or view not in ('flow','technical'):raise CompositionError('INVALID')
        ticket=self._tickets.pop((right.id,view),None)
        if ticket is None:raise CompositionError('SESSION_REQUIRED')
        key,as_of,deadline=ticket
        if time.monotonic()>=deadline:raise CompositionError('EXPIRED')
        self._taken.add((right.id,view))
        return key,as_of


    @staticmethod
    def technical_intent(snapshot):
        """Full original question; no dropped conditions or mixed-query rewriting."""
        from src.modules.technical.domain.execution_admission import Intent
        data=snapshot.data()
        if 'technical' not in data['selected_views']:raise CompositionInvalid()
        return Intent.parse(dict(operation='technical.analysis.v1',ticker=data['stock']['stock_code'],
            original_query=data['draft']['original_query'],requested_views=['technical'],
            conditions=dict(profile='technical.multiframe.v1',periods=['3m','1y','5y'])))

    @staticmethod
    def _flow_fingerprint(snapshot,as_of,key):
        from src.modules.flow.api.analysis_schemas import AnalysisRequest
        from src.modules.supervisor.domain.contracts import canonical
        body=AnalysisRequest(ticker=snapshot.data()['stock']['stock_code'],
            question=snapshot.data()['draft']['original_query'],as_of=as_of,
            idempotency_key=key,allow_analysis=True)
        return hashlib.sha256(canonical(body.normalized_input()).encode()).hexdigest()

    async def _native(self,row,snapshot,view):
        """Validate native identity without refreshing any caller ORM instance."""
        data=snapshot.data();key=fixed_child_key(database_uuid(row.id),view,bytes(row.claim_digest))
        child=await repo.native(self.session,self.principal.user_id,view,hashlib.sha256(key.encode()).digest())
        reference=getattr(row,view+'_run_id');handoff=getattr(row,view+'_handoff_at')
        if child is None:
            if reference is not None:raise CompositionInvalid()
            return None
        if (handoff is None or database_uuid(child.owner_user_id)!=self.principal.user_id
                or reference is not None and database_uuid(reference)!=database_uuid(child.id)
                or child.key_digest!=getattr(row,view+'_key_digest')
                or child.operation!=view+'.analysis.v1' or child.ticker!=data['stock']['stock_code']
                or not handoff<=self._stamp(child.started_at)<row.admission_before
                or not child.started_at<child.deadline_at<=row.deadline_at):raise CompositionInvalid()
        if view=='technical':
            from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService
            from src.modules.technical.domain import provider_execution as P
            from src.modules.supervisor.domain.contracts import canonical
            cfg=P.Configuration(data['technical_configuration'])
            receipt=TechnicalAdmissionService._receipt(child,await repo.technical_period(self.session,child.period_id))
            if (database_uuid(child.admission_session_id)!=database_uuid(row.confirmation_session_id)
                    or child.stock_json!=canonical(data['stock'])
                    or child.execution_configuration_json!=cfg.text or child.policy_sha256!=cfg.policy_sha256
                    or child.intent_sha256!=self.technical_intent(snapshot).fingerprint
                    or row.analysis_as_of is not None and child.as_of!=row.analysis_as_of):raise CompositionInvalid()
            return child,receipt
        if (row.analysis_as_of is None or child.as_of!=row.analysis_as_of
                or child.budget_reservation_id is None or database_uuid(child.budget_reservation_id)!=database_uuid(child.id)
                or child.input_fingerprint!=self._flow_fingerprint(snapshot,row.analysis_as_of,key)
                or child.state not in {'running','result_ready','stored','failed','unknown','deleted'}
                or child.state!='deleted' and child.stock_name!=data['stock']['stock_name']):raise CompositionInvalid()
        policy=await repo.flow_policy(self.session,child.id)
        if (policy is None or any(getattr(policy,k)!=data['flow_policy'][k] for k in ('user_limit','service_limit','budget'))
                or policy.service_user_limit!=data['flow_policy']['user_limit']):raise CompositionInvalid()
        return child,None

    async def link(self,right,view,receipt):
        """Link a directly acknowledged native receipt. Never admit/execute a child.

        The exact actor must have consumed its handoff in this invocation. A
        readback after lost ACK may be observed, but cannot confer the missing
        admission ACK or establish the shared clock for a new Flow handoff.
        """
        try:
            if type(view) is not str or view not in ('flow','technical'):raise CompositionInvalid()
            if (right.id,view) not in self._taken:raise CompositionError('SESSION_REQUIRED')
            await self._begin(lock=True);row=await self._right(right);snapshot=self._checked(row)
            if getattr(row,view+'_run_id') is not None:raise CompositionError('CONFLICT')
            if view=='technical' and time.monotonic()>=right.admission_deadline:raise CompositionError('EXPIRED')
            found=await self._native(row,snapshot,view)
            if found is None:raise CompositionInvalid()
            child,native_receipt=found
            if view=='technical':
                from src.modules.technical.domain.execution_admission import AdmissionReceipt
                if type(receipt) is not AdmissionReceipt:raise CompositionInvalid()
                receipt.__post_init__()
                if (receipt.newly_admitted is not True or receipt.run!=native_receipt
                        or not hmac.compare_digest(hashlib.sha256(receipt.claim_token).digest(),bytes(child.claim_digest))):
                    raise CompositionInvalid()
                change=dict(technical_run_id=child.id,analysis_as_of=child.as_of)
            else:
                from src.modules.flow.api.analysis_schemas import AnalysisView
                if (type(receipt) is not AnalysisView or receipt.analysis_id!=database_uuid(child.id)
                        or receipt.admission_request_id!=database_uuid(child.admission_request_id)
                        or receipt.attempt_id!=database_uuid(child.attempt_id)
                        or receipt.state!=child.state or receipt.deadline_at!=child.deadline_at
                        or receipt.report_id!=(database_uuid(child.adopted_report_id) if child.state=='stored' else None)):
                    raise CompositionInvalid()
                change=dict(flow_run_id=child.id)
            await repo.change(self.session,row,change);await self._commit()
            self._taken.discard((right.id,view))
        except asyncio.CancelledError:
            self._poisoned=True;self._tickets.clear();raise
        except Exception as error:return await self._fail(error)

    async def get(self,id):
        """Owner observation only, including A2/restart/uncertain ACK recovery.

        An expired journal closes unstarted dispatch permanently. This method
        never updates a native run, republishes a report, or returns capabilities.
        Cancellation cleanup belongs to the caller's owning session context.
        """
        try:
            await self._begin(observation=True);row=await self._locked(id);snapshot=self._checked(row)
            now=self._stamp(await repo.clock(self.session))
            if row.state in {'admitted','claimed'} and (now>=row.deadline_at or row.state=='admitted' and now>=row.admission_before):
                row=await repo.change(self.session,row,dict(state='closed',closed_at=now))
                await self._commit()
            if snapshot is None:
                await self.session.rollback()
                return dict(composition_id=str(id),state='redacted',coverage='deleted',views=[])
            children=[];items=[]
            for view in snapshot.data()['selected_views']:
                consumed=getattr(row,view+'_handoff_at') is not None
                found=await self._native(row,snapshot,view)
                if found is None:
                    state='unknown' if consumed else 'not_started'
                    children.append(ChildObservation(view,state,consumed,False))
                    items.append(dict(view=view,state=state,analysis_id=None,report_id=None,receipt_confirmed=False))
                    continue
                child,_=found;state=child.state
                # A native unfinished run after its own deadline is uncertain,
                # not a license to call its POST or to release its reservation.
                if state in {'admitted','claimed','running'} and now>=child.deadline_at:state='unknown'
                children.append(ChildObservation(view,state,True,True))
                report=child.planned_report_id if view=='technical' else child.adopted_report_id
                items.append(dict(view=view,state=state,native_state=child.state,
                    analysis_id=str(database_uuid(child.id)),report_id=str(database_uuid(report)) if state=='stored' else None,
                    receipt_confirmed=True))
            await validate_principal(self.session,self.principal)
            result=dict(composition_id=str(id),state=row.state,analysis_as_of=row.analysis_as_of.isoformat() if row.analysis_as_of else None,
                coverage=coverage(tuple(children),dispatch_closed=row.state=='closed'),views=items)
            await self.session.rollback()
            return result
        except asyncio.CancelledError:
            self._poisoned=True;self._tickets.clear();raise
        except Exception as error:return await self._fail(error)
