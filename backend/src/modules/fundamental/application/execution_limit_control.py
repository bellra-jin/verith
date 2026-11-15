"""Fundamental count-only control on the existing admission transaction."""
from src.modules.fundamental.domain.execution_limits import policy, AdmissionPolicyUnavailable
from src.modules.fundamental.infrastructure import analysis_repository as repo
from src.modules.flow.domain.execution import ErrorCode


class FundamentalExecutionLimitControl:
    def __init__(self,session,error_type,settings=None):
        self.session,self.error_type,self.settings=session,error_type,settings
        self._policy=None

    def new_values(self,body,values):
        if self.settings is None:
            from src.shared.config import settings
        else:settings=self.settings
        try:self._policy=policy(settings)
        except AdmissionPolicyUnavailable:
            raise self.error_type(ErrorCode.FEATURE_UNAVAILABLE) from None
        return {}  # No reservation ID, money or provider accounting columns.

    async def reserve(self,row,stamp):
        if self._policy is None:raise self.error_type(ErrorCode.FEATURE_UNAVAILABLE)
        try:service_count,owner_count=await repo.admission_counts(self.session,row.owner_user_id,stamp)
        except repo.AdmissionCountUnavailable:
            raise self.error_type(ErrorCode.SERVICE_UNAVAILABLE) from None
        # The winning INSERT is already in this transaction and counts too.
        if service_count>self._policy.service_limit or owner_count>self._policy.user_limit:
            raise self.error_type(ErrorCode.USAGE_LIMIT_EXCEEDED)

    async def observe(self,row,grant,envelope):
        """Count-only: no SQL, provider usage, money, refund or settlement ACK."""
        return None
