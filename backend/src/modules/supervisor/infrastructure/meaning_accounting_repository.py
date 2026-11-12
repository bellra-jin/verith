"""SQL identity predicates and account-before-reservation locks."""
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from db.models.supervisor.meaning_accounting import SupervisorMeaningAccount as Account, SupervisorMeaningReservation as Reservation
from db.models.supervisor.preparation import SupervisorMeaningPreparation as Preparation
from src.modules.supervisor.domain.meaning_accounting import canonical,sha,AccountingConflict

async def clock(session): return await session.scalar(select(func.clock_timestamp()))
async def account(session, owner, identity, *, lock=True):
    q=select(Account).where(Account.id==identity,Account.owner_user_id==owner).execution_options(populate_existing=True)
    return await session.scalar(q.with_for_update() if lock else q)
async def reservation(session, owner, identity, *, lock=True):
    q=select(Reservation).where(Reservation.id==identity,Reservation.owner_user_id==owner).execution_options(populate_existing=True)
    return await session.scalar(q.with_for_update() if lock else q)
async def by_preparation(session, preparation):
    return await session.scalar(select(Reservation).where(Reservation.preparation_id==preparation).with_for_update().execution_options(populate_existing=True))

def projection(row):
    return sha(canonical({k:(str(getattr(row,k)) if getattr(row,k) is not None else None) for k in ('id','owner_user_id','attempt_id','request_digest','draft_digest','semantic_sha256','epoch_id','root_id','parent_id','depth','expires_at')}))
async def preparation(session,owner,binding):
    row=await session.scalar(select(Preparation).where(Preparation.id==binding.preparation_id,Preparation.owner_user_id==owner,Preparation.attempt_id==binding.attempt_id,Preparation.request_digest==binding.request_sha256,Preparation.draft_digest==binding.draft_sha256,Preparation.semantic_sha256==binding.semantic_sha256).execution_options(populate_existing=True))
    now=await clock(session)
    if row is None or row.redacted_at is not None or row.state not in ('pending','ready','clarification','unsupported') or row.expires_at!=binding.expires_at or row.expires_at<=now or projection(row)!=binding.projection_sha256: raise AccountingConflict()
    return row
async def create(session,values):
    await session.execute(insert(Account).values(**values).on_conflict_do_nothing(index_elements=['operation','owner_user_id','scope_sha256']))
    return await session.scalar(select(Account).where(Account.operation==values['operation'],Account.owner_user_id==values['owner_user_id'],Account.scope_sha256==values['scope_sha256']).with_for_update().execution_options(populate_existing=True))

async def grant(session,identity,*,lock=False):
    from db.models.supervisor.meaning_accounting import SupervisorMeaningGrant as Grant
    q=select(Grant).where(Grant.id==identity).execution_options(populate_existing=True,autoflush=False)
    with session.no_autoflush:
        return await session.scalar(q.with_for_update() if lock else q)

async def grant_by_preparation(session,identity):
    from db.models.supervisor.meaning_accounting import SupervisorMeaningGrant as Grant
    with session.no_autoflush:
        return await session.scalar(select(Grant).where(Grant.preparation_id==identity).execution_options(populate_existing=True,autoflush=False))

async def grant_principal(session,row):
    from db.models.auth.models import AuthSession
    from src.modules.auth.application.session_service import Principal,validate_principal
    from src.modules.supervisor.domain.meaning_accounting import principal_fingerprint
    auth=await session.scalar(select(AuthSession).where(AuthSession.id==row.owner_session_id,AuthSession.user_id==row.owner_user_id).with_for_update(read=True).execution_options(populate_existing=True))
    if auth is None: raise AccountingConflict()
    p=Principal(auth.user_id,auth.id,auth.expires_at,auth.token_digest)
    if principal_fingerprint(p)!=row.principal_sha256: raise AccountingConflict()
    await validate_principal(session,p,lock=True)
    return p
