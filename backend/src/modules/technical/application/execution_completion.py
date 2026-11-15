"""Concrete receive-only profile. No admission/claim/engine/settlement fallback."""
from dataclasses import fields,replace
import hashlib
import hmac
from uuid import UUID
from sqlalchemy.exc import SQLAlchemyError
from src.modules.auth.application.session_service import AuthenticationRequired,validate_principal
from src.modules.analysis.domain.contracts import AnalysisContext,FrozenAnalysisResult,AnalysisContractError,canonical_json,json_hash,strict_json
from src.modules.analysis.domain.agent_envelope import BoundaryInvalid,SCHEMA_VERSION
from src.modules.technical.domain.execution_admission import (
    Intent,Policy,RunReceipt,CompletionReceipt,COMPLETION_FIELDS,TechnicalAdmissionError,TechnicalCompletionError,decode,
)
from src.modules.technical.domain.execution_boundary import OPERATION as B_OPERATION,fingerprint,RESPONSE_LIMIT
from src.modules.technical.application.boundary_adapter import TechnicalBoundaryBinding
from src.modules.technical.application.boundary_restore import TechnicalReadBinding
from src.modules.technical.application.owned_report_service import (
    TechnicalOwnedReportService,TechnicalStorageInputError,TechnicalStoredPayloadError,TechnicalReportConflict,OPERATION as S_OPERATION,
)
from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService
from src.modules.technical.infrastructure import execution_completion_repository as repository,execution_admission_repository as admission,report_repository


def run_receipt(row):
    return TechnicalAdmissionService._receipt(row,row._completion_period)


def completion_receipt(row):
    return CompletionReceipt(run_receipt(row),**{k:getattr(row,k,None) for k in COMPLETION_FIELDS})


def binding_from_intent(row,intent):
    """Independent E -> B -> S from retained SQL identity, not response fields."""
    run=run_receipt(row);data=intent.data()
    if intent.fingerprint!=run.intent_sha256 or data['ticker']!=row.ticker:
        raise TechnicalAdmissionError('STORED_INVALID')
    stock=decode(row.stock_json,4096)
    request_data=dict(operation=B_OPERATION,original_query=data['original_query'],stock=stock,
        requested_views=data['requested_views'],requested_as_of=run.as_of.isoformat(),conditions=data['conditions'])
    b_fingerprint=fingerprint(request_data)
    request_data['context']=dict(analysis_id=str(run.analysis_id),admission_request_id=str(run.admission_request_id),
        attempt_id=str(run.attempt_id),report_id=str(run.report_id),input_fingerprint=b_fingerprint)
    request=dict(schema_version=SCHEMA_VERSION,request_id=str(run.boundary_request_id),trace_id=str(run.trace_id),data=request_data,error=None)
    context=AnalysisContext(run.analysis_id,run.admission_request_id,run.attempt_id,admission.database_uuid(row.owner_user_id),
        B_OPERATION,b_fingerprint,run.as_of,run.deadline_at)
    execution_json=None
    from src.modules.technical.domain import provider_execution as P
    if run.spec_sha256==P.SPEC_SHA256:
        if row.execution_started_at is None:raise TechnicalAdmissionError('STORED_INVALID')
        execution=P.control_for(run,request,P.Configuration(row.execution_configuration_json))
        if P.canonical(execution['control'])!=row.execution_control_json or execution['control_sha256']!=row.execution_control_sha256:raise TechnicalAdmissionError('STORED_INVALID')
        execution_json=P.canonical(dict(execution=execution,start=P.decode(row.execution_start_json)))
    boundary=TechnicalBoundaryBinding(context,run.report_id,run.boundary_request_id,run.trace_id,canonical_json(request),execution_json)
    caller_text=canonical_json(dict(operation=S_OPERATION,boundary_request=request))
    caller_context=replace(context,operation=S_OPERATION,input_fingerprint=json_hash(caller_text))
    return TechnicalReadBinding(caller_context,caller_text,boundary)


def binding_from_sql(row):
    if row.intent_json is None:raise TechnicalAdmissionError('STORED_INVALID')
    return binding_from_intent(row,Intent(row.intent_json))


def binding_from_report(row,frozen):
    request=strict_json(frozen.input_json);data=request['data']
    intent=Intent.parse(dict(operation='technical.analysis.v1',ticker=data['stock']['stock_code'],
        original_query=data['original_query'],requested_views=data['requested_views'],conditions=data['conditions']))
    binding=binding_from_intent(row,intent)
    if binding.boundary.input_json!=frozen.input_json:raise TechnicalAdmissionError('STORED_INVALID')
    binding.restore(frozen)
    return binding


def checked_saved(row,frozen):
    receipt=completion_receipt(row)
    if receipt.accepted_at is None or (frozen.input_sha256,frozen.result_sha256,frozen.binding_sha256)!=(
            receipt.input_sha256,receipt.result_sha256,receipt.binding_sha256):
        raise TechnicalAdmissionError('STORED_INVALID')
    binding_from_report(row,frozen)
    return frozen


class TechnicalCompletionAdapter:
    def __init__(self,binding):self.binding=binding
    def validate_and_freeze(self,response):
        if type(response) is str:
            if len(response.encode('utf-8'))>RESPONSE_LIMIT:raise BoundaryInvalid()
            parsed=strict_json(response)
            if canonical_json(parsed)!=response:raise BoundaryInvalid()
            response=parsed
        return self.binding.compose(response)
    async def stage(self,session,principal,frozen):
        return await TechnicalOwnedReportService(session,principal=principal).stage(self.binding,frozen)


class TechnicalCompletionProfile:
    operation='technical.analysis.v1'
    receiving_state='claimed'
    repository=repository
    preserved_errors=(TechnicalCompletionError,TechnicalAdmissionError,AuthenticationRequired)
    contract_errors=(BoundaryInvalid,AnalysisContractError,TechnicalStorageInputError)
    publish_errors=(TechnicalReportConflict,TechnicalStorageInputError,TechnicalStoredPayloadError,SQLAlchemyError,OSError,TimeoutError)
    snapshot_conflicts=()
    def __init__(self,*,policy=None):
        # A new receipt needs the explicit current policy. Owner recovery does
        # not require a new execution policy or create one on demand.
        self._policy_text=policy.text if type(policy) is Policy else None
    def error(self,code,analysis_id=None):return TechnicalCompletionError(code,analysis_id)
    def view(self,row):return completion_receipt(row)
    def adapter(self,row,owner):
        if row.owner_user_id!=owner:raise AuthenticationRequired()
        return TechnicalCompletionAdapter(binding_from_sql(row))
    def from_stored(self,adapter,row):
        frozen=adapter.validate_and_freeze(row.result_json)
        if frozen.input_json!=row.input_json:raise TechnicalAdmissionError('STORED_INVALID')
        return checked_saved(row,frozen)
    def freeze_received(self,expected,response):
        if type(expected) is not RunReceipt:raise self.error('INPUT_INVALID')
        expected=RunReceipt(**{f.name:(UUID(int=getattr(expected,f.name).int)
            if type(getattr(expected,f.name)) is UUID else getattr(expected,f.name)) for f in fields(RunReceipt)})
        try:
            raw=canonical_json(response)
            if len(raw.encode('utf-8'))>RESPONSE_LIMIT:raise AnalysisContractError()
        except (ValueError,TypeError,UnicodeError,RecursionError):
            # Freeze invalid input as an invalid value too. Only the subsequent
            # fresh owner/token/expected check may close a legitimate claim.
            raw='null'
        return expected,raw
    async def check_dispatch(self,session,row,principal,expected,token):
        current=run_receipt(row)
        changed={'state','claim_consumed_at','redacted_at','unknown_reason'}
        if (type(token) is not bytes or len(token)!=32 or any(getattr(expected,f.name)!=getattr(current,f.name)
                for f in fields(RunReceipt) if f.name not in changed)
                or expected.claim_consumed_at is None or expected.claim_consumed_at!=current.claim_consumed_at
                or not hmac.compare_digest(row.claim_digest,hashlib.sha256(token).digest())):
            raise self.error('RESULT_CONTRACT_INVALID',current.analysis_id)
        if row.state!='claimed':return
        if row.admission_session_id!=principal.session_id:raise self.error('RESULT_CONTRACT_INVALID',current.analysis_id)
        if self._policy_text is None:raise TechnicalAdmissionError('POLICY_UNAVAILABLE')
        active=Policy(self._policy_text);active.enabled()
        if active.text!=row._completion_period.policy_json or row._completion_period.blocked:
            raise TechnicalAdmissionError('POLICY_UNAVAILABLE')
        stock=await admission.stock(session,row.ticker)
        if stock is None or canonical_json(dict(stock_code=stock.stock_code,stock_name=stock.stock_name,market=stock.market))!=row.stock_json:
            raise self.error('RESULT_CONTRACT_INVALID',current.analysis_id)
    async def check_receive(self,session,row,principal,expected,token):
        await self.check_dispatch(session,row,principal,expected,token)
        from src.modules.technical.domain import provider_execution as P
        if row.spec_sha256==P.SPEC_SHA256 and row.execution_started_at is None:
            raise self.error('RESULT_CONTRACT_INVALID',expected.analysis_id)

    async def verify_replay(self,session,row,principal,response):
        if row.state not in {'result_ready','stored'}:return
        if row.state=='stored':
            stored=await TechnicalOwnedReportService(session,principal=principal).read(admission.database_uuid(row.planned_report_id))
            if stored is None:raise TechnicalAdmissionError('STORED_INVALID')
            saved=checked_saved(row,stored.frozen);binding=binding_from_report(row,saved)
        else:
            adapter=self.adapter(row,principal.user_id);saved=self.from_stored(adapter,row);binding=adapter.binding
        try:incoming=TechnicalCompletionAdapter(binding).validate_and_freeze(response)
        except self.contract_errors:raise self.error('RESULT_CONTRACT_INVALID',admission.database_uuid(row.id)) from None
        if incoming!=saved:raise self.error('RESULT_CONFLICT',admission.database_uuid(row.id))
    async def accept_result(self,session,row,claim,frozen):return await repository.accept(session,row,claim,frozen)
    async def prepare_terminal(self,session,row,state,code=None):await repository.terminal(session,row,state,code)
    async def validate_state(self,session,row,principal):
        completion_receipt(row)
        if row.state=='stored':
            stored=await TechnicalOwnedReportService(session,principal=principal).read(admission.database_uuid(row.planned_report_id))
            if stored is None:raise TechnicalAdmissionError('STORED_INVALID')
            checked_saved(row,stored.frozen)
        elif row.state=='result_ready':self.from_stored(self.adapter(row,principal.user_id),row)
    async def publication_recovery(self,session,row,principal,frozen,error):
        try:
            service=TechnicalOwnedReportService(session,principal=principal)
            root=await report_repository.storage_root_for_update(session,frozen.report_id)
            stored=await service.read(frozen.report_id)
            if stored is not None:
                if stored.frozen!=frozen:return 'conflict'
                checked_saved(row,stored.frozen)
                return 'same'
            indexes=await report_repository.technical_indexes(session,frozen.report_id)
            # A completed owner query returned no valid stored report, and the
            # locked committed ID is occupied/incompatible. Query errors below
            # are unknown, never converted to conflicts by mere existence.
            return 'conflict' if root is not None or indexes else 'unknown'
        except TechnicalStoredPayloadError:return 'conflict'
        except AuthenticationRequired:raise
        except (SQLAlchemyError,OSError,TimeoutError,TechnicalAdmissionError,TechnicalStorageInputError):return 'unknown'


async def reconcile_completion(session,*,principal,analysis_id):
    """ACK-only SELECT reconciliation. No expiry, mutation, publication or commit."""
    if type(analysis_id) is not UUID:raise TechnicalCompletionError('INPUT_INVALID')
    if session.new or session.dirty or session.deleted:
        # CF035 intentionally refreshes ORM projections. Never overwrite a
        # caller's pending work; use a fresh clean session for ACK recovery.
        raise TechnicalAdmissionError('CONTEXT_DIRTY')
    with session.no_autoflush:
        await validate_principal(session,principal)
        row=await repository.read_owned(session,principal.user_id,analysis_id)
        if row is None:raise TechnicalCompletionError('RESOURCE_NOT_FOUND')
        await TechnicalCompletionProfile().validate_state(session,row,principal)
        return completion_receipt(row)
