"""Mandatory Flow control. Publication/auth are separate from accounting receipt."""
import hashlib,hmac
from db.models.common.analysis_usage import AnalysisUsageReservation as Reservation,AnalysisProviderCall as Call
from src.modules.analysis.domain.usage import (policy,period,PolicyUnavailable,UsageConflict,MAX_INT,RUN_RESERVE,CALL_RESERVE,PRICE_ID,USAGE_SPEC,SLOTS,call_id,canonical,receipt)
from src.modules.analysis.infrastructure import usage_repository as repo


class FlowUsageControl:
    def __init__(self,session,error_type,settings=None):
        self.session,self.error_type,self.settings=session,error_type,settings
        self._policy=None

    def new_values(self,body,values):
        from src.modules.flow.domain.execution import ErrorCode
        if self.settings is None:
            from src.shared.config import settings
        else:settings=self.settings
        try:self._policy=policy(settings)
        except PolicyUnavailable:raise self.error_type(ErrorCode.FEATURE_UNAVAILABLE) from None
        if body.ticker not in self._policy.tickers:raise self.error_type(ErrorCode.FEATURE_UNAVAILABLE)
        return {'budget_reservation_id':values['id']}

    async def reserve(self,row,stamp):
        from src.modules.flow.domain.execution import ErrorCode
        value=self._policy
        if value is None:raise RuntimeError('Flow admission policy missing')
        start,end=period(stamp)
        service=await repo.period(self.session,'service',None,start,end,request_limit=value.service_limit,budget_limit=value.budget,user_request_limit=value.user_limit)
        user=await repo.period(self.session,'user',row.owner_user_id,start,end,request_limit=service.user_request_limit,budget_limit=None)
        # The first period values stay fixed across subsequent setting changes.
        if (service.blocked or user.blocked or service.request_count>=service.request_limit or user.request_count>=user.request_limit
            or service.estimated_spend_nano+service.held_nano+RUN_RESERVE>service.budget_limit_nano
            or max(user.held_nano,service.held_nano)+RUN_RESERVE>MAX_INT):
            raise self.error_type(ErrorCode.USAGE_LIMIT_EXCEEDED)
        for bucket in (service,user):bucket.request_count+=1;bucket.held_nano+=RUN_RESERVE
        reservation=Reservation(id=row.id,owner_user_id=row.owner_user_id,operation=row.operation,attempt_id=row.attempt_id,
            claim_digest=row.claim_digest,user_period_id=user.id,service_period_id=service.id,currency='USD',price_id=PRICE_ID,
            policy_json=canonical(USAGE_SPEC),max_nano=RUN_RESERVE,remaining_nano=RUN_RESERVE,estimated_spend_nano=0,state='held')
        self.session.add(reservation);await self.session.flush()
        for provider,action,ordinal in SLOTS:
            self.session.add(Call(id=call_id(row.id,row.attempt_id,provider,action,ordinal),reservation_id=row.id,
                provider=provider,action=action,ordinal=ordinal,reserved_nano=CALL_RESERVE if provider=='openai' else 0,
                released_nano=0,attempted=None,state='unknown',reason='UNOBSERVED'))
        await self.session.flush() # Same caller transaction as admission; no commit here.

    async def observe(self,row,grant,envelope):
        reservation_id=getattr(row,'budget_reservation_id',None)
        if reservation_id is None:return # Legacy snapshot/replay is not re-accounted.
        evidence=receipt(row,envelope)
        if evidence is None:return # Body absent/unverifiable: original maximum remains held.
        locked=await repo.accounting(self.session,reservation_id)
        if locked is None:raise UsageConflict('Accounting identity unavailable')
        service,user,reservation,calls=locked
        if (reservation.id!=row.id or reservation.owner_user_id!=row.owner_user_id or reservation.operation!=row.operation
            or reservation.attempt_id!=row.attempt_id or not hmac.compare_digest(reservation.claim_digest,hashlib.sha256(grant).digest())):
            raise UsageConflict('Accounting identity mismatch')
        existing={call.id:call for call in calls}
        if len(existing)!=9:raise UsageConflict('Accounting slots unavailable')
        released=spent=0;blocked=reservation.state=='blocked'
        for value in evidence:
            call=existing[value.id]
            if call.attempted is True and value.attempted is not True:raise UsageConflict('Provider attempt cannot be reversed')
            if call.state in {'observed','not_called','anomalous'}:
                if call.evidence_sha256!=value.hash:raise UsageConflict('Provider evidence conflict')
                continue
            if value.state=='unknown':
                # Unknown is not final; preserve attempted truth without invented zeros.
                pass
            before=call.released_nano
            known=value.state=='not_called' or value.estimated_nano is not None
            release=call.reserved_nano if known else 0
            estimate=value.estimated_nano or 0
            # Overflow is anomalous, not a capped or fabricated spend amount.
            if max(service.estimated_spend_nano,user.estimated_spend_nano,reservation.estimated_spend_nano)+spent+estimate>MAX_INT:
                blocked=True;release=0;estimate=0
                call.attempted=value.attempted;call.state='anomalous';call.reason='ACCOUNTING_OVERFLOW';call.evidence_sha256=value.hash
                for field in ('input_tokens','cached_tokens','output_tokens','input_bytes','output_bytes','response_model','model_sha256','http_status'):
                    setattr(call,field,getattr(value,field))
                continue
            for field in ('attempted','state','input_tokens','cached_tokens','output_tokens','input_bytes','output_bytes','response_model','model_sha256','http_status','reason'):
                setattr(call,field,getattr(value,field))
            call.estimated_nano=value.estimated_nano;call.evidence_sha256=value.hash;call.released_nano=release
            released+=release-before;spent+=estimate
            blocked|=value.state=='anomalous'
        for bucket in (service,user):
            bucket.held_nano-=released;bucket.estimated_spend_nano+=spent;bucket.blocked|=blocked
        reservation.remaining_nano-=released;reservation.estimated_spend_nano+=spent
        reservation.state='blocked' if blocked else 'settled' if reservation.remaining_nano==0 and all(c.state!='unknown' for c in calls) else 'unknown'
        await self.session.flush()
        await self.session.commit() # Accounting ACK is independent of result/auth/publication.
