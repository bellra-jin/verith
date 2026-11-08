"""Internal synthetic preparation only; authenticates even internally supplied principals."""
from uuid import UUID, uuid4
from src.modules.auth.application.session_service import AuthenticationRequired, Principal, validate_principal
from src.modules.flow.domain.input_snapshot import SnapshotError, build, digest, fixture_selection, read_seal
from src.modules.flow.infrastructure import input_snapshot_repository as repository


class InputPreparationService:
    def __init__(self, session, *, principal):
        self.session, self.principal = session, principal

    async def _rollback(self):
        try:
            await self.session.rollback()
        except Exception:
            # Rollback failure cannot prove that a prior commit did not happen.
            pass

    async def _run(self, run_id):
        if not isinstance(run_id, UUID):
            raise SnapshotError("invalid")
        if not isinstance(self.principal, Principal):
            raise SnapshotError("auth_required")
        await validate_principal(self.session, self.principal, lock=True)
        row = await repository.lock_run(self.session, run_id, self.principal.user_id)
        if row is None:
            raise SnapshotError("not_found")
        return row

    async def prepare(self, run_id, fixture_id, version=1):
        try:
            fixture_selection(fixture_id, version)
            row = await self._run(run_id)
            text = build(row, fixture_id, version)
            snapshot = await repository.get_owned(self.session, run_id, self.principal.user_id)
            if snapshot is None:
                snapshot = await repository.insert_snapshot(self.session, dict(
                    id=uuid4(), run_id=run_id, owner_user_id=self.principal.user_id,
                    contract_version=1, mode="synthetic_only", input_json=text, input_sha256=digest(text)))
                if snapshot is None:
                    snapshot = await repository.get_owned(self.session, run_id, self.principal.user_id)
            if snapshot is None:
                raise SnapshotError("unavailable")
            result = read_seal(snapshot, row)
            if result.input_json != text:
                raise SnapshotError("conflict")
            await self.session.commit()
            return result
        except Exception as exc:
            await self._rollback()
            code = exc.code if isinstance(exc, SnapshotError) else "auth_required" if isinstance(exc, AuthenticationRequired) else "unavailable"
            raise SnapshotError(code) from None

    async def get(self, run_id):
        try:
            row = await self._run(run_id)
            snapshot = await repository.get_owned(self.session, run_id, self.principal.user_id)
            if snapshot is None:
                raise SnapshotError("not_found")
            result = read_seal(snapshot, row)
            await self.session.commit()
            return result
        except Exception as exc:
            await self._rollback()
            code = exc.code if isinstance(exc, SnapshotError) else "auth_required" if isinstance(exc, AuthenticationRequired) else "unavailable"
            raise SnapshotError(code) from None
