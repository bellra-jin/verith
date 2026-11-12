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
            return self.receipt(await self.stage_reserve(principal,account_id,binding))
        return await self.mutation(action)
    async def stage_reserve(self,principal,account_id,binding,*,locked_account=None):
        # Caller holds auth/preparation locks; no commit in this stage.
        frozen=binding.snapshot()
        account=locked_account if locked_account is not None else await repo.account(self.session,principal.user_id,account_id)
        if account is None: raise AccountingConflict()
        policy=self.policy(account)
        policy.require_current()
        if binding.semantic_sha256!=sha(policy.semantic_json) or binding.price_sha256!=sha(policy.price_json): raise AccountingConflict()
        old=await repo.by_preparation(self.session,binding.preparation_id)
        if old is not None:
            if old.account_id!=account_id or old.owner_user_id!=principal.user_id or old.binding_json!=frozen or old.reserved_nano!=policy.attempt_nano: raise AccountingConflict()
            return old
        now=await repo.clock(self.session)
        if account.blocked or not policy.starts_at<=now<policy.ends_at or binding.expires_at<=now or account.reserved_nano>policy.limit_nano-policy.attempt_nano or account.attempts>=policy.max_attempts: raise AccountingConflict()
        row=Reservation(id=uuid4(),account_id=account.id,owner_user_id=principal.user_id,owner_session_id=binding.session_id,preparation_id=binding.preparation_id,attempt_id=binding.attempt_id,binding_json=frozen,binding_sha256=sha(frozen),expires_at=binding.expires_at,reserved_nano=policy.attempt_nano,state='held')
        self.session.add(row)
        account.reserved_nano+=policy.attempt_nano
        account.attempts+=1
        await self.session.flush()
        return row
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
            row=await repo.reservation(self.session,owner_id,reservation_id)
            if row is None or row.account_id!=account_id or row.binding_sha256!=binding_sha256 or sha(row.binding_json)!=binding_sha256: raise AccountingConflict()
            return self.receipt(await self.stage_settle(account,row,evidence,fingerprint))
        return await self.mutation(action)
    async def stage_settle(self,account,row,evidence,fingerprint):
        # Same SQL/classification as public settle; caller commits the whole phase.
        policy=self.policy(account)
        state,amount=settlement(policy,evidence) if type(evidence) is dict else ('anomalous',None)
        binding=json.loads(row.binding_json)
        if state=='observed' and any(evidence[k]!=expected for k,expected in dict(request_sha256=binding['request_sha256'],projection_sha256=binding['projection_sha256'],binding_sha256=row.binding_sha256,semantic_sha256=sha(policy.semantic_json),price_sha256=sha(policy.price_json)).items()): state,amount='anomalous',None
        safe=evidence if state=='observed' else {'state':'unknown'} if evidence=={'state':'unknown'} else {'state':'anomalous','reason':'INVALID_OBSERVATION','evidence_sha256':fingerprint}
        raw=canonical(safe)
        if row.state!='held':
            if row.receipt_sha256!=sha(raw) or row.receipt_json!=raw: raise AccountingConflict()
            return row
        if state=='observed':
            integer(account.observed_nano+amount)
            account.observed_nano+=amount
        else: account.blocked=True
        row.state=state;row.receipt_json=raw;row.receipt_sha256=sha(raw);row.estimated_nano=amount
        await self.session.flush()
        return row
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

class MeaningRuntimeService(MeaningAccountingService):
    """Per-preparation metadata and atomic phase consumption; no provider I/O."""
    def __init__(self,session,*,runtime_policy=None):
        super().__init__(session)
        self.runtime_policy=runtime_policy

    @staticmethod
    def handle(value):
        import re
        from uuid import UUID
        if type(value) is not str or re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.[0-9a-f]{64}',value) is None: raise AccountingConflict()
        identity,nonce=value.split('.')
        return UUID(identity),sha(nonce)

    async def lookup(self,handle):
        identity,nonce=self.handle(handle)
        row=await repo.grant(self.session,identity)
        if row is None or row.nonce_sha256!=nonce: raise AccountingConflict()
        # A copy is required: populate_existing below must not rewrite the authority.
        from types import SimpleNamespace
        return SimpleNamespace(**{k:getattr(row,k) for k in ('id','owner_user_id','owner_session_id','preparation_id','attempt_id','account_id','nonce_sha256','principal_sha256','binding_json','binding_sha256','counter_json','counter_sha256','policy_sha256','scope_sha256','deadline_at')})

    async def fresh(self,frozen):
        from src.modules.supervisor.infrastructure import preparation_repository as preparations
        from src.modules.supervisor.domain.meaning_accounting import Binding,strict_json
        from datetime import datetime
        from uuid import UUID
        p=await repo.grant_principal(self.session,frozen)
        rows=await preparations.lineage(self.session,p.user_id,frozen.preparation_id)
        before=asyncio.get_running_loop().time()
        now=await repo.clock(self.session)
        if len(rows)!=1 or preparations.closure(rows,now)[0] is not None or rows[0].state!='pending' or rows[0].parent_id is not None: raise AccountingConflict()
        raw=strict_json(frozen.binding_json,16384)
        args={**raw,'preparation_id':UUID(raw['preparation_id']),'attempt_id':UUID(raw['attempt_id']),'session_id':UUID(raw['session_id']),'expires_at':datetime.fromisoformat(raw['expires_at'])}
        b=Binding(**args)
        await repo.preparation(self.session,p.user_id,b)
        if sha(frozen.binding_json)!=frozen.binding_sha256 or sha(frozen.counter_json)!=frozen.counter_sha256: raise AccountingConflict()
        account=await repo.account(self.session,p.user_id,frozen.account_id)
        if account is None: raise AccountingConflict()
        policy=self.policy(account);policy.require_current()
        self.check_policy(account,policy,p.user_id,frozen)
        from src.modules.supervisor.domain.contracts import Draft
        draft=Draft.model_validate(strict_json(rows[0].draft_json,16384))
        if rows[0].semantic_json!=policy.semantic_json or sha(canonical(draft.model_dump(mode='json',exclude={'selected_ticker','candidate_ref'})))!=b.draft_sha256 or canonical(draft.model_dump(mode='json'))!=rows[0].draft_json: raise AccountingConflict()
        end=min(frozen.deadline_at,account.ends_at,p.expires_at,*(r.expires_at for r in rows))
        deadline=before+max(0,(end-now).total_seconds())
        if now<account.starts_at or asyncio.get_running_loop().time()>=deadline: raise AccountingConflict()
        return p,rows[0],b,account,policy,deadline

    def check_policy(self,account,policy,owner,frozen=None):
        from src.modules.supervisor.domain.meaning_accounting import RuntimePolicy,maximum_reserve
        if type(self.runtime_policy) is not RuntimePolicy: raise AccountingConflict()
        identity,scope,expected,agreement=self.runtime_policy.select(owner)
        if account.id!=identity or account.scope_sha256!=scope or account.policy_sha256!=expected or policy.operation!='meaning' or account.blocked: raise AccountingConflict()
        maximum_reserve(policy,agreement)
        if frozen is not None and (frozen.policy_sha256!=expected or frozen.scope_sha256!=scope or frozen.counter_json!=agreement): raise AccountingConflict()
        return agreement

    async def issue(self,principal,preparation_id,*,deadline):
        """No automatic account creation and no cost reservation in this transaction."""
        import secrets,math
        from datetime import timedelta
        from uuid import UUID
        from db.models.supervisor.meaning_accounting import SupervisorMeaningGrant as Grant
        from src.modules.supervisor.infrastructure import preparation_repository as preparations
        from src.modules.supervisor.domain.meaning_accounting import Binding,RuntimePolicy,principal_fingerprint
        if type(self.runtime_policy) is not RuntimePolicy or not self.runtime_policy.active(): return None
        if type(deadline) not in {float,int} or not math.isfinite(deadline): raise AccountingConflict()
        # Invalid/missing policy disables only paid supplementation. A commit ACK
        # failure after metadata insertion, in contrast, must propagate and send0.
        try: account_id,_,_,_=self.runtime_policy.select(principal.user_id)
        except (AccountingConflict,ValueError,TypeError,KeyError): return None
        try:
            await validate_principal(self.session,principal,lock=True)
            rows=await preparations.lineage(self.session,principal.user_id,preparation_id)
            before=asyncio.get_running_loop().time();now=await repo.clock(self.session)
            if len(rows)!=1 or preparations.closure(rows,now)[0] is not None or rows[0].state!='pending': raise AccountingConflict()
            row=rows[0]
            account=await repo.account(self.session,principal.user_id,account_id)
            if account is None:
                await self.session.rollback();return None
            try:
                policy=self.policy(account);policy.require_current()
                agreement=self.check_policy(account,policy,principal.user_id)
            except AccountingConflict:
                await self.session.rollback();return None
            if not account.starts_at<=now<account.ends_at:
                await self.session.rollback();return None
            if await repo.by_preparation(self.session,preparation_id) is not None or await repo.grant_by_preparation(self.session,preparation_id) is not None: raise AccountingConflict()
            end=min(now+timedelta(seconds=max(0,deadline-asyncio.get_running_loop().time())),row.expires_at,account.ends_at,principal.expires_at)
            if end<=now: raise AccountingConflict()
            b=Binding(UUID(str(row.id)),UUID(str(row.attempt_id)),UUID(str(principal.session_id)),row.request_digest,row.draft_digest,repo.projection(row),row.semantic_sha256,sha(policy.price_json),row.expires_at)
            nonce=secrets.token_hex(32);identity=uuid4()
            grant=Grant(id=identity,owner_user_id=principal.user_id,owner_session_id=principal.session_id,preparation_id=row.id,attempt_id=row.attempt_id,account_id=account.id,reservation_id=None,principal_sha256=principal_fingerprint(principal),nonce_sha256=sha(nonce),policy_sha256=account.policy_sha256,scope_sha256=account.scope_sha256,binding_json=b.snapshot(),binding_sha256=sha(b.snapshot()),counter_json=agreement,counter_sha256=sha(agreement),created_at=now,deadline_at=end)
            self.session.add(grant);await self.session.flush()
            handle=str(identity)+'.'+nonce
            await self.session.commit()
            if asyncio.get_running_loop().time()>=min(deadline,before+(end-now).total_seconds()): raise TimeoutError()
            return handle
        except BaseException:
            await self.session.rollback();raise

    async def reconcile_phase(self,handle,value):
        from src.modules.supervisor.domain.meaning_accounting import strict_json
        if type(value) is not dict or set(value)!={'action','phase','attempt_id','request_sha256','projection_sha256'} or value['action']!='reconcile' or value['phase'] not in {'count','generation','settlement'}: raise AccountingConflict()
        with self.session.no_autoflush:
            frozen=await self.lookup(handle)
            row=await repo.grant(self.session,frozen.id)
            if row is None or value['attempt_id']!=str(frozen.attempt_id) or (row.provider_request_sha256,row.provider_projection_sha256)!=(value['request_sha256'],value['projection_sha256']): raise AccountingConflict()
            reservation=await repo.reservation(self.session,frozen.owner_user_id,row.reservation_id,lock=False) if row.reservation_id is not None else None
            if reservation is None or reservation.binding_sha256!=frozen.binding_sha256: raise AccountingConflict()
            phase=value['phase']
            receipt=row.count_receipt if phase=='count' else row.generation_receipt if phase=='generation' else None
            return {'newly_authorized':False,'phase':phase,'receipt':strict_json(receipt) if receipt is not None else None,'settlement':self.receipt(reservation),'terminal_ACK':row.terminal_sha256 is not None}

    async def authorize(self,handle,value):
        from src.modules.supervisor.domain.meaning_accounting import provider_identity,strict_json,maximum_reserve,wire,digest
        if type(value) is not dict or value.get('phase') not in {'count','generation'}: raise AccountingConflict()
        value=strict_json(wire(value))
        phase=value['phase'];required={'phase','attempt_id','request_sha256','projection_sha256','counter_sha256'}|({'rendered_request'} if phase=='count' else {'evidence'})
        if set(value)!=required: raise AccountingConflict()
        for k in ('request_sha256','projection_sha256','counter_sha256'): digest(value[k])
        async def action():
            frozen=await self.lookup(handle)
            p,prep,b,account,policy,deadline=await self.fresh(frozen)
            if value['attempt_id']!=str(b.attempt_id) or value['counter_sha256']!=frozen.counter_sha256: raise AccountingConflict()
            reservation=await repo.by_preparation(self.session,b.preparation_id)
            # Account serialization makes the immutable metadata lookup stable;
            # finish reservation SQL before acquiring the final grant lock.
            prior=await repo.grant(self.session,frozen.id)
            if prior is None or prior.nonce_sha256!=frozen.nonce_sha256: raise AccountingConflict()
            if phase=='count' and prior.count_receipt is None:
                if reservation is not None: raise AccountingConflict()
                if provider_identity(value['rendered_request'],prep.draft_json,policy.semantic_json)!=(value['request_sha256'],value['projection_sha256']): raise AccountingConflict()
                reservation=await self.stage_reserve(p,account.id,b,locked_account=account)
            row=await repo.grant(self.session,frozen.id,lock=True)
            if row is None or row.nonce_sha256!=frozen.nonce_sha256 or row.binding_json!=frozen.binding_json or row.terminal_sha256 is not None: raise AccountingConflict()
            hashes=(value['request_sha256'],value['projection_sha256'])
            if phase=='count':
                if provider_identity(value['rendered_request'],prep.draft_json,policy.semantic_json)!=hashes: raise AccountingConflict()
            elif (row.provider_request_sha256,row.provider_projection_sha256)!=hashes: raise AccountingConflict()
            receipt=getattr(row,'count_receipt' if phase=='count' else 'generation_receipt')
            if phase=='generation':
                if row.count_receipt is None or reservation is None or row.reservation_id!=reservation.id: raise AccountingConflict()
                e=value['evidence'];agreement=strict_json(frozen.counter_json)
                expected={'request_sha256':hashes[0],'projection_sha256':hashes[1],'model':policy.model,'price_sha256':sha(policy.price_json),'mapping_sha256':agreement['documentation_sha256'],'count_fee_bound_nano':agreement['counting_fee_bound_nano']}
                if type(e) is not dict or set(e)!=set(expected)|{'input_tokens'} or any(wire(e[k])!=wire(v) for k,v in expected.items()): raise AccountingConflict()
                maximum_reserve(policy,frozen.counter_json,e['input_tokens'])
            newly=receipt is None
            if newly:
                if phase=='count':
                    if reservation is None: raise AccountingConflict()
                    row.reservation_id=reservation.id
                    row.provider_request_sha256,row.provider_projection_sha256=hashes
                elif reservation.state!='held': raise AccountingConflict()
                receipt=canonical({'phase':phase,'reservation_id':str(reservation.id),'binding_sha256':frozen.binding_sha256,'request_sha256':hashes[0],'projection_sha256':hashes[1],'evidence_sha256':sha(wire(value.get('evidence')))})
                setattr(row,'count_receipt' if phase=='count' else 'generation_receipt',receipt)
                await self.session.flush()
            elif phase=='generation' and strict_json(receipt)['evidence_sha256']!=sha(wire(value['evidence'])): raise AccountingConflict()
            remaining=max(0,int((deadline-asyncio.get_running_loop().time())*1000))
            return {'newly_authorized':newly,'remaining_ms':remaining,'receipt':strict_json(receipt)},deadline
        result,deadline=await self.mutation(action)
        # A committed phase remains consumed even if its ACK arrives too late.
        remaining=max(0,int((deadline-asyncio.get_running_loop().time())*1000))
        result['remaining_ms']=min(result['remaining_ms'],remaining)
        result['newly_authorized']=result['newly_authorized'] and remaining>0
        return result

    async def finish(self,handle,value):
        from src.modules.supervisor.domain.meaning_accounting import strict_json,wire
        if type(value) is not dict or set(value)!={'attempt_id','request_sha256','projection_sha256','observation','blocked'} or type(value['blocked']) is not bool: raise AccountingConflict()
        value=strict_json(wire(value,8192),8192)
        o=value['observation']
        base={'state','reason','estimated_nano'}
        if type(o) is not dict or o.get('state') not in {'observed','unknown','anomalous'}: raise AccountingConflict()
        permitted=base|{'model_sha256'} if o['state']!='observed' else base|{'model_sha256','input_tokens','output_tokens','total_tokens','cached_tokens','price_sha256'}
        if not base<=set(o)<=permitted or o['reason'] not in {'UNOBSERVED','USAGE_UNAVAILABLE','MODEL_MISMATCH','CAP_EXCEEDED','USAGE_OBSERVED'}: raise AccountingConflict()
        if o['state']!='observed' and o['estimated_nano'] is not None: raise AccountingConflict()
        for k in ('model_sha256','price_sha256'):
            if k in o:
                from src.modules.supervisor.domain.meaning_accounting import digest
                digest(o[k])
        async def action():
            frozen=await self.lookup(handle)
            account=await repo.account(self.session,frozen.owner_user_id,frozen.account_id)
            if account is None: raise AccountingConflict()
            reservation=await repo.by_preparation(self.session,frozen.preparation_id)
            row=await repo.grant(self.session,frozen.id,lock=True)
            if row is None or row.nonce_sha256!=frozen.nonce_sha256 or reservation is None or row.reservation_id!=reservation.id or reservation.binding_sha256!=frozen.binding_sha256 or value['attempt_id']!=str(frozen.attempt_id) or (value['request_sha256'],value['projection_sha256'])!=(row.provider_request_sha256,row.provider_projection_sha256): raise AccountingConflict()
            policy=self.policy(account);observation=value['observation'];binding=strict_json(frozen.binding_json)
            evidence={'state':'unknown'}
            observed_fields={'state','reason','estimated_nano','model_sha256','input_tokens','output_tokens','total_tokens','cached_tokens','price_sha256'}
            if type(observation) is dict and observation.get('state')=='observed':
                if row.generation_receipt is None or set(observation)!=observed_fields or observation['reason']!='USAGE_OBSERVED' or observation['model_sha256']!=sha(policy.model) or observation['price_sha256']!=sha(policy.price_json):
                    evidence={'state':'anomalous'}
                else:
                    evidence=dict(state='observed',model=policy.model,tier=policy.tier,input=observation['input_tokens'],output=observation['output_tokens'],total=observation['total_tokens'],cached=observation['cached_tokens'],request_sha256=binding['request_sha256'],projection_sha256=binding['projection_sha256'],binding_sha256=frozen.binding_sha256,semantic_sha256=binding['semantic_sha256'],price_sha256=binding['price_sha256'])
            elif type(observation) is not dict or observation.get('state') not in {'unknown','anomalous'}: evidence={'state':'anomalous'}
            elif observation.get('state')=='anomalous': evidence={'state':'anomalous'}
            terminal=sha(wire(value))
            if row.terminal_sha256 is not None and row.terminal_sha256!=terminal: raise AccountingConflict()
            await self.stage_settle(account,reservation,evidence,sha(wire(evidence)))
            row.terminal_sha256=terminal
            await self.session.flush()
            return {'settlement':self.receipt(reservation)}
        return await self.mutation(action)
