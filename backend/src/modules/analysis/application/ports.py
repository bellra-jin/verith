"""Structural adapter only. Transaction/owner/state orchestration stays in caller."""
from typing import Protocol,runtime_checkable,Any,TYPE_CHECKING
from src.modules.analysis.domain.contracts import FrozenAnalysisResult,StagedReportReference
if TYPE_CHECKING:
    from src.modules.auth.application.session_service import Principal


@runtime_checkable
class AnalysisAdapter(Protocol):
    def build_request(self)->dict[str,Any]:...
    def validate_and_freeze(self,response:Any)->FrozenAnalysisResult:...
    async def stage(self,session:Any,principal:'Principal',frozen:FrozenAnalysisResult)->StagedReportReference:...
