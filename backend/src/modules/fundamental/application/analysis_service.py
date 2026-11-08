"""Financial facade over the same authenticated execution coordinator as Flow."""
from src.modules.analysis.application.coordinator import AnalysisCoordinator
from src.modules.analysis.application.ports import CoordinatorError
from src.modules.fundamental.application.analysis_profile import FundamentalProfile


class FundamentalAnalysisError(CoordinatorError):
    def __init__(self,code,analysis_id=None):
        self.code,self.analysis_id=code,analysis_id
        super().__init__('Financial analysis failed')


class FundamentalAnalysisService(AnalysisCoordinator):
    def __init__(self,session,*,principal,client):
        super().__init__(session,principal=principal,client=client,profile=FundamentalProfile(FundamentalAnalysisError))
