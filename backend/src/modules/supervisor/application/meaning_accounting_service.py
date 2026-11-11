"""Explicit internal durable accounting. No dispatch authority or policy defaults."""
from uuid import uuid4
import asyncio
import json
from src.modules.auth.application.session_service import validate_principal
from src.modules.supervisor.domain.meaning_accounting import Policy,Binding,AccountingConflict,canonical,sha,uid,settlement,integer
from src.modules.supervisor.infrastructure import meaning_accounting_repository as repo
from db.models.supervisor.meaning_accounting import SupervisorMeaningReservation as Reservation

class MeaningAccountingService:
    def __init__(self,session): self.session=session
    async def mutation(self,action):
        try:
            result=await action()
            await self.session.commit()
            return result
        except BaseException:
            try:
                await self.session.rollback()
            except asyncio.CancelledError:
                raise
            except BaseException:
                # An ACK/rollback failure never replaces the original cancellation.
                pass
            raise
    @staticmethod
    def receipt(row):
        return {'reservation_id':str(row.id),'account_id':str(row.account_id),'binding_sha256':row.binding_sha256,'state':row.state,'reserved_nano':row.reserved_nano,'estimated_nano':row.estimated_nano,'receipt_sha256':row.receipt_sha256}
    async def create_account(self,principal,policy,*,account_id):
        if type(policy) is not Policy: raise AccountingConflict()
        uid(account_id)
        policy.require_current()
        snapshot=policy.snapshot()
        async def action():
            await validate_principal(self.session,principal)
            row=await repo.create(self.session,dict(id=account_id,owner_user_id=principal.user_id,operation=policy.operation,scope_json=policy.scope,scope_sha256=sha(policy.scope),policy_json=snapshot,policy_sha256=sha(snapshot),starts_at=policy.starts_at,ends_at=policy.ends_at,limit_nano=policy.limit_nano,attempt_nano=policy.attempt_nano,max_attempts=policy.max_attempts,reserved_nano=0,attempts=0,observed_nano=0,blocked=False))
            if row is None or row.scope_json!=policy.scope or row.policy_json!=snapshot or row.policy_sha256!=sha(snapshot): raise AccountingConflict()
            return str(row.id)
        return await self.mutation(action)
    async def reserve(self,principal,account_id,binding):
        uid(account_id)
        if type(binding) is not Binding or binding.session_id!=principal.session_id: raise AccountingConflict()
        frozen=binding.snapshot()
        async def action():
            await validate_principal(self.session,principal)
            await repo.preparation(self.session,principal.user_id,binding)
            account=await repo.account(self.session,principal.user_id,account_id)
            if account is None: raise AccountingConflict()
            policy=self.policy(account)
            policy.require_current()
            if binding.semantic_sha256!=sha(policy.semantic_json) or binding.price_sha256!=sha(policy.price_json): raise AccountingConflict()
            old=await repo.by_preparation(self.session,binding.preparation_id)
            if old is not None:
                if old.account_id!=account_id or old.owner_user_id!=principal.user_id or old.binding_json!=frozen or old.reserved_nano!=policy.attempt_nano: raise AccountingConflict()
                return self.receipt(old)
            now=await repo.clock(self.session)
            if account.blocked or not policy.starts_at<=now<policy.ends_at or binding.expires_at<=now or account.reserved_nano>policy.limit_nano-policy.attempt_nano or account.attempts>=policy.max_attempts: raise AccountingConflict()
            row=Reservation(id=uuid4(),account_id=account.id,owner_user_id=principal.user_id,owner_session_id=binding.session_id,preparation_id=binding.preparation_id,attempt_id=binding.attempt_id,binding_json=frozen,binding_sha256=sha(frozen),expires_at=binding.expires_at,reserved_nano=policy.attempt_nano,state='held')
            self.session.add(row)
            account.reserved_nano+=policy.attempt_nano
            account.attempts+=1
            await self.session.flush()
            return self.receipt(row)
        return await self.mutation(action)
    @staticmethod
    def policy(account):
        if sha(account.policy_json)!=account.policy_sha256: raise AccountingConflict()
        p=json.loads(account.policy_json)
        from datetime import datetime
        p.pop('currency')
        p['starts_at']=datetime.fromisoformat(p['starts_at']);p['ends_at']=datetime.fromisoformat(p['ends_at'])
        policy=Policy(**p)
        if policy.snapshot()!=account.policy_json or policy.scope!=account.scope_json or sha(account.scope_json)!=account.scope_sha256 or any(getattr(account,k)!=getattr(policy,k) for k in ('operation','starts_at','ends_at','limit_nano','attempt_nano','max_attempts')): raise AccountingConflict()
        return policy
    async def settle(self,*,owner_id,account_id,reservation_id,binding_sha256,evidence):
        for v in (owner_id,account_id,reservation_id): uid(v)
        from src.modules.supervisor.domain.meaning_accounting import digest
        digest(binding_sha256)
        # Freeze bounded input without retaining free strings in the journal.
        import hashlib
        try:
            raw_input=json.dumps(evidence,sort_keys=True,ensure_ascii=False,separators=(',',':'))
            fingerprint=hashlib.sha256(raw_input.encode()).hexdigest()
            evidence=json.loads(raw_input) if len(raw_input.encode())<=16384 else None
        except (ValueError,TypeError,OverflowError,RecursionError):
            fingerprint=sha('non-json');evidence=None
        async def action():
            account=await repo.account(self.session,owner_id,account_id)
            if account is None: raise AccountingConflict()
            policy=self.policy(account)
            row=await repo.reservation(self.session,owner_id,reservation_id)
            if row is None or row.account_id!=account_id or row.binding_sha256!=binding_sha256 or sha(row.binding_json)!=binding_sha256: raise AccountingConflict()
            state,amount=settlement(policy,evidence) if type(evidence) is dict else ('anomalous',None)
            binding=json.loads(row.binding_json)
            if state=='observed' and any(evidence[k]!=expected for k,expected in dict(request_sha256=binding['request_sha256'],projection_sha256=binding['projection_sha256'],binding_sha256=row.binding_sha256,semantic_sha256=sha(policy.semantic_json),price_sha256=sha(policy.price_json)).items()): state,amount='anomalous',None
            safe=evidence if state=='observed' else {'state':'unknown'} if evidence=={'state':'unknown'} else {'state':'anomalous','reason':'INVALID_OBSERVATION','evidence_sha256':fingerprint}
            raw=canonical(safe)
            if row.state!='held':
                if row.receipt_sha256!=sha(raw) or row.receipt_json!=raw: raise AccountingConflict()
                return self.receipt(row)
            if state=='observed':
                integer(account.observed_nano+amount)
                account.observed_nano+=amount
            else: account.blocked=True
            row.state=state;row.receipt_json=raw;row.receipt_sha256=sha(raw);row.estimated_nano=amount
            await self.session.flush()
            return self.receipt(row)
        return await self.mutation(action)
    async def reconcile(self,*,owner_id,account_id,binding,reservation_id=None):
        # Caller-known binding survives a lost first commit ACK; no hidden UUID.
        for v in (owner_id,account_id): uid(v)
        if type(binding) is not Binding: raise AccountingConflict()
        with self.session.no_autoflush:
            account=await repo.account(self.session,owner_id,account_id,lock=False)
            from sqlalchemy import select
            row=await self.session.scalar(select(Reservation).where(Reservation.account_id==account_id,Reservation.owner_user_id==owner_id,Reservation.preparation_id==binding.preparation_id,Reservation.attempt_id==binding.attempt_id).execution_options(populate_existing=True,autoflush=False))
        if account is None or row is None or row.binding_json!=binding.snapshot() or row.binding_sha256!=sha(binding.snapshot()) or (reservation_id is not None and row.id!=reservation_id): raise AccountingConflict()
        return self.receipt(row)
