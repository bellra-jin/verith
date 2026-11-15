"""Only the exact authenticated core prepare/confirm/observation contracts."""
from src.modules.supervisor.domain.contracts import Draft, Confirm, Plan, Outcome, Envelope, SafeError, PreparationRequest, PreparationView
PrepareResponse = Envelope[Plan]
RequestResponse = Envelope[Outcome]
PATH = '/api/supervisor/core'

PreparationResponse = Envelope[PreparationView]

from src.modules.supervisor.domain.technical_core_contracts import (
    Confirm as TechnicalConfirm,Envelope as TechnicalEnvelope,Plan as TechnicalPlan,Outcome as TechnicalOutcome,
)
TechnicalPrepareResponse=TechnicalEnvelope[TechnicalPlan]
TechnicalRequestResponse=TechnicalEnvelope[TechnicalOutcome]
