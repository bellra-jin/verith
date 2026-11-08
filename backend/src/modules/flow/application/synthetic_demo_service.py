"""Sequential committed stages; never a fictitious all-or-nothing transaction."""
from src.modules.flow.api.synthetic_demo_schemas import DemoRequest, DemoRunView, TICKER, QUESTION
from src.modules.flow.domain.execution import ContractViolation, ErrorCode
from src.modules.flow.domain.input_snapshot import SnapshotError, receipt
from src.modules.flow.domain.fake_execution import FakeExecutionError
from src.modules.flow.application.run_service import FlowRunService
from src.modules.flow.application.input_preparation_service import InputPreparationService
from src.modules.flow.application.fake_execution_service import FakeExecutionService
from src.modules.flow.infrastructure.run_repository import get_owned
from src.modules.auth.application.session_service import AuthenticationRequired


class DemoError(ValueError):
    def __init__(self, code, run_id=None):
        self.code,self.run_id=code,run_id
        super().__init__('Synthetic demo request failed')


def safe_code(error):
    if isinstance(error, ContractViolation):return error.error.code
    if isinstance(error, AuthenticationRequired):return ErrorCode.AUTH_REQUIRED
    if isinstance(error, (SnapshotError,FakeExecutionError)):
        return {'invalid':ErrorCode.INPUT_INVALID,'auth_required':ErrorCode.AUTH_REQUIRED,
                'not_found':ErrorCode.RESOURCE_NOT_FOUND,'conflict':ErrorCode.RESULT_CONFLICT,
                'corrupt':ErrorCode.RESULT_CONTRACT_INVALID,'fence':ErrorCode.RESULT_CONTRACT_INVALID}.get(error.code,ErrorCode.SERVICE_UNAVAILABLE)
    return ErrorCode.SERVICE_UNAVAILABLE


class SyntheticDemoService:
    def __init__(self, session, *, principal):self.session,self.principal=session,principal

    def _view(self, run, seal=None, execution=None):
        try:return self._assemble(run,seal,execution)
        except Exception:raise DemoError(ErrorCode.RESULT_CONTRACT_INVALID) from None

    def _assemble(self, run, seal=None, execution=None):
        return DemoRunView(run_id=run.run_id,request_id=run.request_id,attempt_id=run.attempt_id,
            input_snapshot_id=None if seal is None else seal.id, execution_id=None if execution is None else execution.id,
            stage='admitted' if seal is None else 'prepared' if execution is None else execution.status,
            deadline_at=None if execution is None else execution.deadline_at, finished_at=None if execution is None else execution.finished_at,
            result_stored=execution is not None and execution.status=='succeeded',result=None if execution is None else execution.body,
            result_sha256=None if execution is None else execution.result_sha256,failure_code=None if execution is None else execution.error_code)

    async def post(self, body, request_id):
        known = None
        try:
            try:body=DemoRequest.model_validate(body.model_dump() if isinstance(body,DemoRequest) else body)
            except ValueError:raise DemoError(ErrorCode.INPUT_INVALID) from None
            run = await FlowRunService(self.session,principal=self.principal).admit(body.admission(),request_id)
            known = run.run_id
            seal = await InputPreparationService(self.session,principal=self.principal).prepare(known,'flow.synthetic.full20',1)
            execution = await FakeExecutionService(self.session,principal=self.principal).execute_once(known,allow_fake=True)
            return self._view(run,seal,execution)
        except DemoError:raise
        except Exception as error:raise DemoError(safe_code(error),known) from None

    async def get(self, run_id):
        try:
            run = await FlowRunService(self.session,principal=self.principal).get(run_id)
            row = await get_owned(self.session,run_id,self.principal.user_id)
            if row is None:raise DemoError(ErrorCode.RESOURCE_NOT_FOUND)
            source = receipt(row)
            if source['request']['ticker'] != TICKER or source['request']['question'] != QUESTION:
                raise DemoError(ErrorCode.RESOURCE_NOT_FOUND)
            try:seal = await InputPreparationService(self.session,principal=self.principal).get(run_id)
            except SnapshotError as error:
                if error.code == 'not_found':return self._view(run)
                raise
            fixture=seal.body['fixture']
            if fixture['id']!='flow.synthetic.full20' or type(fixture['version']) is not int or fixture['version']!=1:
                raise DemoError(ErrorCode.RESOURCE_NOT_FOUND)
            try:execution = await FakeExecutionService(self.session,principal=self.principal).get(run_id)
            except FakeExecutionError as error:
                if error.code == 'not_found':return self._view(run,seal)
                raise
            return self._view(run,seal,execution)
        except DemoError:raise
        except Exception as error:raise DemoError(safe_code(error)) from None
