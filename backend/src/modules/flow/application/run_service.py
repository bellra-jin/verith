"""CF-003 atomic admission, without AI, workers, stock writes or result storage."""

import hashlib
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.application.session_service import AuthenticationRequired, Principal, validate_principal
from src.modules.flow.api.run_schemas import FlowAdmissionRequest
from src.modules.flow.domain.execution import ContractViolation, ErrorCode, FlowRunState
from src.modules.flow.infrastructure import run_repository as repository


def run_state(row) -> FlowRunState:
    return FlowRunState(
        request_id=row.admission_request_id, run_id=row.id, attempt_id=row.attempt_id,
        execution_status=row.execution_status, storage_status=row.storage_status,
    )


class FlowRunService:
    def __init__(self, session: AsyncSession, *, principal: Principal | None):
        self.session, self.principal = session, principal

    async def authorize(self, *, lock=False):
        if self.principal is None:
            raise AuthenticationRequired()
        await validate_principal(self.session, self.principal, lock=lock)
        return self.principal

    async def admit(self, request: FlowAdmissionRequest, request_id: UUID) -> FlowRunState:
        try:
            try:
                source = request.model_dump() if isinstance(request, FlowAdmissionRequest) else request
                request = FlowAdmissionRequest.model_validate(source)
            except (ValidationError, ValueError, TypeError):
                raise ContractViolation(ErrorCode.INPUT_INVALID) from None
            principal = await self.authorize(lock=True)
            digest = hashlib.sha256(request.idempotency_key.encode("utf-8")).digest()
            normalized = request.normalized_input()
            fingerprint = request.input_fingerprint()
            row = await repository.insert_receipt(self.session, dict(
                id=uuid4(), owner_user_id=principal.user_id, operation="flow",
                request_contract_version=1, idempotency_key_digest=digest,
                input_fingerprint=fingerprint, request_input=normalized,
                admission_request_id=request_id, attempt_id=uuid4(), admission_mode="receipt_only",
                execution_status="pending", storage_status="not_stored",
            ))
            if row is None:
                row = await repository.find_key(self.session, principal.user_id, digest)
                if row is None:
                    raise ContractViolation(ErrorCode.SERVICE_UNAVAILABLE)
                if (row.request_contract_version != 1 or row.input_fingerprint != fingerprint
                        or row.request_input != normalized):
                    raise ContractViolation(ErrorCode.IDEMPOTENCY_CONFLICT)
            result = run_state(row)
            await self.session.commit()
            return result
        except (ContractViolation, AuthenticationRequired):
            await self.session.rollback()
            raise
        except Exception:
            try:
                await self.session.rollback()
            finally:
                raise ContractViolation(ErrorCode.SERVICE_UNAVAILABLE) from None

    async def get(self, run_id: UUID) -> FlowRunState:
        try:
            principal = await self.authorize()
            row = await repository.get_owned(self.session, run_id, principal.user_id)
            if row is None:
                raise ContractViolation(ErrorCode.RESOURCE_NOT_FOUND)
            return run_state(row)
        except (ContractViolation, AuthenticationRequired):
            await self.session.rollback()
            raise
        except Exception:
            try:
                await self.session.rollback()
            finally:
                raise ContractViolation(ErrorCode.SERVICE_UNAVAILABLE) from None
