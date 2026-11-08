"""Flow public service facade over the shared fixed-profile coordinator."""
from src.modules.analysis.application.coordinator import AnalysisCoordinator
from src.modules.analysis.application.ports import CoordinatorError
from src.modules.flow.application.analysis_profile import FlowProfile
# Keep the original class/module references for existing focused callers.
from src.modules.flow.application.analysis_adapter import FlowAnalysisAdapter
from src.modules.flow.infrastructure import analysis_repository as repository,report_repository


class AnalysisError(CoordinatorError):
    def __init__(self,code,analysis_id=None):
        self.code,self.analysis_id=code,analysis_id
        super().__init__('Flow analysis failed')


class AnalysisService(AnalysisCoordinator):
    def __init__(self,session,*,principal,client):
        super().__init__(session,principal=principal,client=client,profile=FlowProfile(AnalysisError))
