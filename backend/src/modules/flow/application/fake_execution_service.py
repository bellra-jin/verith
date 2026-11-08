"""Explicit internal one-shot fake grant, terminal storage and owner retrieval."""
import asyncio
import hashlib
import hmac
import secrets
from uuid import UUID, uuid4
from src.modules.auth.application.session_service import AuthenticationRequired, Principal, validate_principal
from src.modules.flow.domain.input_snapshot import SnapshotError, read_seal, digest
from src.modules.flow.domain.fake_execution import FakeExecutionError, fake_engine, read_execution, result_text, validate_result
from src.modules.flow.infrastructure import input_snapshot_repository as inputs
from src.modules.flow.infrastructure import fake_execution_repository as repository


class FakeExecutionService:
    def __init__(self, session, *, principal):
        self.session, self.principal = session, principal

    async def _rollback(self):
        try:
            await self.session.rollback()
        except Exception:
            pass  # This cannot prove that an earlier commit did not happen.

    async def _locked(self, run_id):
        if not isinstance(run_id, UUID):
            raise FakeExecutionError("invalid")
        if not isinstance(self.principal, Principal):
            raise FakeExecutionError("auth_required")
        await validate_principal(self.session, self.principal, lock=True)
        run = await inputs.lock_run(self.session, run_id, self.principal.user_id)
        if run is None:
            raise FakeExecutionError("not_found")
        snapshot = await inputs.get_owned(self.session, run_id, self.principal.user_id)
        if snapshot is None:
            raise FakeExecutionError("not_found")
        return read_seal(snapshot, run)

    def _code(self, error):
        if isinstance(error, FakeExecutionError):
            return error.code
        if isinstance(error, AuthenticationRequired):
            return "auth_required"
        if isinstance(error, SnapshotError):
            return "corrupt"
        return "unavailable"

    async def _current(self, row, seal):
        value = read_execution(row, seal)
        if value.status == "running":
            expired = await repository.finalize(self.session, row, expired=True)
            if expired is not None:
                value = read_execution(expired, seal)
        return value

    async def execute_once(self, run_id, *, allow_fake):
        try:
            if type(allow_fake) is not bool or allow_fake is not True:
                raise FakeExecutionError("invalid")
            seal = await self._locked(run_id)
            row = await repository.get_owned(self.session, run_id, self.principal.user_id)
            if row is not None:
                result = await self._current(row, seal)
                await self.session.commit()
                return result
            token = secrets.token_bytes(32)
            claim_digest = hashlib.sha256(token).digest()
            row = await repository.claim(self.session, uuid4(), seal.id, claim_digest)
            if row is None:
                row = await repository.get_owned(self.session, run_id, self.principal.user_id)
                if row is None:
                    raise FakeExecutionError("unavailable")
                result = await self._current(row, seal)
                await self.session.commit()
                return result
            granted = read_execution(row, seal)
            await self.session.commit()  # Lost ACK means no engine call, even if granted.
        except asyncio.CancelledError:
            await self._rollback()
            raise
        except Exception as error:
            await self._rollback()
            raise FakeExecutionError(self._code(error)) from None
        # There are no DB locks or transaction while the bounded pure engine runs.
        try:
            value = await asyncio.wait_for(fake_engine(seal, granted.id), timeout=1)
            try:
                text = result_text(value, seal, granted.id)
                outcome = ("succeeded", text, None)
            except Exception:
                outcome = ("failed", None, "result_invalid")
        except asyncio.TimeoutError:
            outcome = ("timed_out", None, "coroutine_timeout")
        except Exception:
            outcome = ("failed", None, "fake_failed")
        return await self._finish(run_id, granted.id, token, outcome)

    async def _finish(self, run_id, execution_id, token, outcome):
        try:
            seal = await self._locked(run_id)
            row = await repository.get_owned(self.session, run_id, self.principal.user_id)
            if (row is None or row.id != execution_id or type(token) is not bytes or len(token) != 32
                    or not hmac.compare_digest(row.claim_digest, hashlib.sha256(token).digest())):
                raise FakeExecutionError("fence")
            result = read_execution(row, seal)
            if result.status == "running":
                expired = await repository.finalize(self.session, row, expired=True)
                if expired is None:
                    status, text, error = outcome
                    if status == "succeeded":
                        try:
                            validate_result(text, seal, execution_id)
                        except Exception:
                            status, text, error = "failed", None, "result_invalid"
                    elif (status, error) not in {("failed", "fake_failed"), ("failed", "result_invalid"), ("timed_out", "coroutine_timeout")}:
                        raise FakeExecutionError("invalid")
                    expired = await repository.finalize(self.session, row,
                        claim_digest=hashlib.sha256(token).digest(), status=status, result_json=text,
                        result_sha256=digest(text) if text is not None else None, error_code=error)
                    if expired is None:
                        expired = await repository.finalize(self.session, row, expired=True)
                    if expired is None:
                        raise FakeExecutionError("unavailable")
                result = read_execution(expired, seal)
            await self.session.commit()
            return result
        except asyncio.CancelledError:
            await self._rollback()
            raise
        except Exception as error:
            await self._rollback()
            raise FakeExecutionError(self._code(error)) from None

    async def get(self, run_id):
        try:
            seal = await self._locked(run_id)
            row = await repository.get_owned(self.session, run_id, self.principal.user_id)
            if row is None:
                raise FakeExecutionError("not_found")
            result = await self._current(row, seal)
            await self.session.commit()
            return result
        except asyncio.CancelledError:
            await self._rollback()
            raise
        except Exception as error:
            await self._rollback()
            raise FakeExecutionError(self._code(error)) from None
