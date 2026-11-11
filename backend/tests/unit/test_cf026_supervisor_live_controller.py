"""Fixed controller collection; no Docker/provider/key/config on import."""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib.abc
import os
from pathlib import Path
import sys
from types import MappingProxyType, SimpleNamespace as NS
from unittest.mock import patch
from uuid import uuid4

import pytest

IMPORTS = []
class Sentinel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"src.shared.config", "dotenv", "openai", "src.supervisor.config", "langchain_openai", "langgraph", "redis"}:
            IMPORTS.append(fullname)
            raise AssertionError("Controller import closure")

sentinel = Sentinel()
sys.meta_path.insert(0, sentinel)
from scripts import cf026_supervisor_live_controller as C
from scripts import cf023_supervisor_meaning_check as V
V.load_meaning()
from src.modules.supervisor.domain.contracts import MEANING_SPEC, MEANING_SPEC_SHA256
O = sys.modules["src.supervisor.infrastructure.openai_meaning_gateway"]
M = sys.modules["src.supervisor.domain.meaning"]
PRIVATE = "cf026-synthetic-key-sentinel"


def write(path, value, mode=0o600):
    path.write_bytes(value if isinstance(value, bytes) else C.canonical(value).encode())
    path.chmod(mode)


def inputs(tmp_path):
    root = tmp_path.resolve()
    root.chmod(0o700)
    source_file = root / "synthetic-input.txt"
    write(source_file, b"OTHER=untouched\nOPENAI_API_KEY=" + PRIVATE.encode() + b"\n", 0o644)
    source = C.KeySource(source_file, C.regular(source_file, 0o644), True)
    write(root / "execution.lock", b"")
    grant = synthetic_grant(source)
    grant["state_store"] = C.PrivateStore(root).scope()
    write(root / "grant.json", grant)
    write(root / "state.json", dict(schema="cf026.state.v1", approval_id=grant["approval_id"], grant_sha256=C.digest(grant), status="issued", journal=[]))
    async def verify(**scope):
        return scope["mode"] == "synthetic" and scope["scope_sha256"] == C.digest(grant)
    return C.PrivateStore(root), C.ExternalApproval(C.digest(grant), grant["issuer"], verify), source


def synthetic_grant(source):
    now = datetime.now(timezone.utc)
    requests = []
    for _ in range(2):
        draft = M.Draft(original_query="\ud604\ub300\uac74\uc124 \uc218\uae09", answers=[], revision=0)
        request = O.rendered_request(draft)
        body = dict(prepare_key=str(uuid4()), parent_preparation_id=None, draft=draft.model_dump(mode="json"))
        requests.append(dict(prepare_body=body, draft_sha256=C.digest(body["draft"]), request_sha256=C.digest(request), projection_sha256=C.digest({k: request[k] for k in O.INPUT_FIELDS})))
    return dict(schema="cf026.grant.v1", approval_id=str(uuid4()), issuer="synthetic-only", not_before=(now-timedelta(seconds=1)).isoformat(), expires_at=(now+timedelta(minutes=6)).isoformat(), mode="synthetic", epoch_id=str(uuid4()), requests=requests, semantic_sha256=MEANING_SPEC_SHA256, price_sha256=C.digest(MEANING_SPEC["price"]), model=MEANING_SPEC["model"], tier="default", origin=O.ORIGIN, endpoints=[O.COUNT_PATH,O.GENERATE_PATH], max_nano=100000000, attempt_nano=50000000, max_attempts=2, input_cap=16384, output_cap=2048, source=source.scope(), counter=dict(documentation_url=O.COUNT_DOCUMENTATION, documentation_sha256="a"*64, free_evidence_sha256="b"*64, price_evidence_sha256="c"*64, fee_bound_nano=0))


def test_import_is_lazy_and_live_closed():
    assert not IMPORTS
    with pytest.raises(C.ControllerError, match="LIVE_GATE_CLOSED"):
        asyncio.run(C.run_controller(None))
    assert "scripts.runner_owned_database" not in sys.modules


def test_claim_lock_replay_and_restart(tmp_path):
    store, _, _ = inputs(tmp_path)
    with store.locked():
        with pytest.raises(C.ControllerError, match="APPROVAL_BUSY"):
            with C.PrivateStore(tmp_path.resolve()).locked():
                pass
        store.persist("claimed", {"phase":"claim_ACK"})
    again=C.PrivateStore(tmp_path.resolve())
    with again.locked():
        assert again.state["status"] == "claimed"
        with pytest.raises(C.ControllerError, match="STATE_TRANSITION"):
            again.persist("issued", {})
        again.persist("closed", {"phase":"cleanup"})
        with pytest.raises(C.ControllerError, match="STATE_TRANSITION"):
            again.persist("claimed", {})


@pytest.mark.parametrize("fault", ["absent","mode","symlink","hardlink","state-drift","lock-drift","grant-drift"])
def test_private_files_fail_closed(tmp_path, fault):
    store, _, _ = inputs(tmp_path)
    with store.locked():
        path=tmp_path/('execution.lock' if fault=='lock-drift' else 'grant.json' if fault=='grant-drift' else 'state.json')
        if fault=='absent':path.unlink()
        elif fault=='mode':path.chmod(0o644)
        elif fault=='symlink':path.rename(tmp_path/'other');path.symlink_to(tmp_path/'other')
        elif fault=='hardlink':os.link(path,tmp_path/'other')
        else:path.write_bytes(path.read_bytes()+b' ')
        with pytest.raises((C.ControllerError,OSError)):
            store.reload()


@pytest.mark.parametrize("value", [b"",b"OPENAI_API_KEY=a\nOPENAI_API_KEY=b",b"export OPENAI_API_KEY=a",b"OPENAI_API_KEY=\"abc",b"OPENAI_API_KEY=${OTHER}",b"OPENAI_API_KEY=a\\b",b"OPENAI_API_KEY=a #comment",b"OPENAI_API_KEY=a\r\n",b"OPENAI_API_KEY="+b'a'*513,b"OTHER="+b'a'*4096])
def test_single_key_rejects_ambiguous_values(value):
    with pytest.raises(C.ControllerError,match="KEY_SOURCE_INVALID"):
        C.single_key(value)


@pytest.mark.parametrize("value", [b"token-123",b"'token-123'",b'"token-123"'])
def test_single_key_narrow_supported_syntax(value):
    assert C.single_key(b"OTHER=not interpreted\nOPENAI_API_KEY="+value+b"\n")=="token-123"


def test_source_identity_drift_and_no_mode_repair(tmp_path):
    _,_,source=inputs(tmp_path)
    assert asyncio.run(source.read())==PRIVATE
    source.path.chmod(0o600)
    with pytest.raises(C.ControllerError):asyncio.run(source.read())
    assert source.path.stat().st_mode&0o777==0o600


def test_live_source_uses_explicit_reviewed_origin_not_temporary_import_directory(tmp_path):
    root=tmp_path/'verith-supervisor-live-controller';script=root/'backend/scripts/cf026_supervisor_live_controller.py'
    script.parent.mkdir(parents=True);script.write_bytes(Path(C.__file__).read_bytes());script.chmod(0o644)
    info=root.stat();provenance=C.ReviewedCodeRoot(root,(info.st_dev,info.st_ino,info.st_uid,info.st_mode),C.hashlib.sha256(script.read_bytes()).hexdigest())
    expected=root.parent/'verith/ai'/'.env'
    source=C.KeySource(expected,{'synthetic_metadata_only':True},False,provenance)
    original=C.regular;checked=[]
    def metadata(path,mode):
        if path==expected:checked.append(path);assert mode==0o644;return source.stamp
        return original(path,mode)
    with patch.object(C,'regular',metadata):source.check()
    assert checked==[expected]
    assert source.scope()['code_root']['controller_sha256']==provenance.controller_sha256
    with pytest.raises(C.ControllerError,match='KEY_SOURCE_SCOPE'):
        C.KeySource(root/'backend'/'.env',source.stamp,False,provenance).check()
    with pytest.raises(C.ControllerError,match='KEY_SOURCE_SCOPE'):
        C.KeySource(expected,source.stamp,False).check()
    script.write_bytes(script.read_bytes()+b'\n')
    with pytest.raises(C.ControllerError,match='KEY_SOURCE_SCOPE'):provenance.check()


@pytest.mark.parametrize("relative_path", [
    "verith/backend/.env",
    "verith/frontend/.env",
    "verith-supervisor-live-controller/ai/.env",
    "verith-other/ai/.env",
    "verith/ai/other.env",
])
def test_live_source_rejects_other_service_paths_before_metadata_or_read(tmp_path, relative_path):
    provenance = C.ReviewedCodeRoot(
        tmp_path / "verith-supervisor-live-controller", (), "a" * 64,
    )
    source = C.KeySource(tmp_path / relative_path, {}, False, provenance)
    with patch.object(C.ReviewedCodeRoot, "check") as check_origin, patch.object(
        C, "regular", side_effect=AssertionError("No credential metadata access"),
    ) as read_metadata, patch.object(
        C, "read_fixed", side_effect=AssertionError("No credential content access"),
    ) as read_content:
        with pytest.raises(C.ControllerError, match="KEY_SOURCE_SCOPE"):
            source.check()
    check_origin.assert_called_once_with()
    read_metadata.assert_not_called()
    read_content.assert_not_called()


class Hooks:
    def __init__(self, fault=None):
        self.driver=NS(call=lambda *a,**k:None)
        self.fault=fault;self.created=0;self.steps=[];self.cleaned=0;self.preserved=0
    def create(self):
        self.created+=1
    async def bootstrap(self,store):
        if self.fault in {"setup","epoch-ack"}:raise OSError(PRIVATE)
        self.items=store.grant["requests"]
        self.binding=V.OwnedEpochBinding(object(),object(),uuid4(),datetime.now(timezone.utc),'a'*64,'synthetic')
        return self.binding.proof,object(),self.binding
    async def verify(self,*args,observation=None):
        self.steps.append(args[-1])
        if self.fault=='cancel':raise asyncio.CancelledError()
        return {'settlement':'hold' if self.fault=='unknown-first' or args[-1]==1 else 'observed','meaning_status':'supplemented','stages':['preflight_verified']}
    async def snapshot(self,*args):
        if self.fault=='snapshot':raise OSError(PRIVATE)
        item=self.items[0]
        return dict(count=1,generation=1,reserved=50000000,blocked=False,active=None,attempts={'a':dict(request_sha256=item['request_sha256'],projection_sha256=item['projection_sha256'],observation={'state':'observed'})})
    def cleanup(self):
        self.cleaned+=1
        if self.fault=='cleanup':raise OSError(PRIVATE)
    def preserve(self):
        self.preserved+=1


@pytest.mark.parametrize('fault',[None,'setup','epoch-ack','unknown-first','cancel','cleanup','snapshot'])
def test_controller_one_resource_order_unknown_cancel_and_cleanup(tmp_path,fault):
    store,approval,source=inputs(tmp_path);hooks=Hooks(fault)
    async def run():return await C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks)
    if fault:
        with pytest.raises(asyncio.CancelledError if fault=='cancel' else C.ControllerError) as caught:asyncio.run(run())
        assert PRIVATE not in str(caught.value)
    else:assert asyncio.run(run())['approval_closed']
    assert hooks.created==1 and hooks.cleaned==1
    assert hooks.steps==([] if fault in {'setup','epoch-ack'} else [0] if fault in {'unknown-first','cancel','snapshot'} else [0,1])
    accounting=next(event for event in store.state['journal'] if event['phase']=='final_accounting')
    if fault in {'setup','epoch-ack','snapshot'}:
        assert accounting['observation']=='unconfirmed' and accounting['estimated_nano'] is None
        assert accounting['count_requests'] is None and accounting['conservative_hold_nano']==100000000
    else:assert accounting['observation']=='fresh_ledger'
    with pytest.raises(C.ControllerError,match='APPROVAL_ALREADY_USED'):asyncio.run(run())
    assert hooks.created==1


def test_accounting_write_failure_retains_resource_and_claim(tmp_path):
    store,approval,source=inputs(tmp_path);hooks=Hooks('unknown-first');original=store.persist
    def persist(status,event):
        if event['phase']=='final_accounting':raise C.ControllerError('STATE_ACK_UNKNOWN')
        return original(status,event)
    with patch.object(store,'persist',persist):
        with pytest.raises(C.ControllerError):asyncio.run(C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks))
    assert hooks.cleaned==0 and hooks.preserved==1
    assert store.state['status']=='claimed'


@pytest.mark.parametrize('fault',['missing','malformed-request','callback','filesystem','cancel'])
def test_entire_public_preclaim_entry_has_fixed_error_surface(tmp_path,fault):
    store,approval,source=inputs(tmp_path);hooks=Hooks()
    if fault=='filesystem':source.path.unlink()
    elif fault in {'missing','malformed-request'}:
        grant=C.decode((tmp_path/'grant.json').read_bytes())
        if fault=='missing':del grant['issuer']
        else:grant['requests'][0]['prepare_body']={'private':PRIVATE}
        write(tmp_path/'grant.json',grant)
        state=C.decode((tmp_path/'state.json').read_bytes());state['grant_sha256']=C.digest(grant);write(tmp_path/'state.json',state)
        approval=C.ExternalApproval(C.digest(grant),grant.get('issuer','synthetic-only'),approval.verify)
    else:
        async def callback(**scope):
            if fault=='cancel':raise asyncio.CancelledError()
            raise RuntimeError(PRIVATE)
        approval=C.ExternalApproval(approval.scope_sha256,approval.issuer,callback)
    with pytest.raises(asyncio.CancelledError if fault=='cancel' else C.ControllerError) as caught:
        asyncio.run(C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks))
    assert PRIVATE not in str(caught.value) and hooks.created==0


def test_claim_ack_unknown_creates_nothing_and_is_not_reissued(tmp_path):
    store,approval,source=inputs(tmp_path);hooks=Hooks()
    original=os.fsync
    with patch.object(C.os,'fsync',side_effect=OSError(PRIVATE)):
        with pytest.raises(C.ControllerError,match='STATE_ACK_UNKNOWN'):
            asyncio.run(C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks))
    assert hooks.created==0
    assert (tmp_path/'state.pending').exists()
    assert original is os.fsync


def test_same_grant_copy_in_another_directory_cannot_reset_claim(tmp_path):
    original=tmp_path/'original';original.mkdir(mode=0o700)
    store,approval,source=inputs(original)
    copied=tmp_path/'copied';copied.mkdir(mode=0o700)
    for name in ['grant.json','state.json','execution.lock']:
        write(copied/name,(original/name).read_bytes())
    hooks=Hooks()
    with pytest.raises(C.ControllerError,match='APPROVAL_STORE_SCOPE'):
        asyncio.run(C.run_controller(C.PrivateStore(copied.resolve()),approval=approval,key_source=source,synthetic=True,hooks=hooks))
    assert hooks.created==0


@pytest.mark.parametrize('phase',['initial','preflight','count','generation'])
def test_actual_phase_authority_rechecks_identity_and_order(tmp_path,phase):
    store,approval,source=inputs(tmp_path)
    binding,principal,deferred=object(),object(),object()
    item=synthetic_grant(source)['requests'][0]
    with store.locked():
        store.persist('claimed',{'phase':'claim_ACK'})
        authority=C.ControllerAuthority(store,approval,source,object(),binding,principal,item,deferred)
        sequence=['initial','preflight','count','generation'];authority.phases=sequence[:sequence.index(phase)]
        scope=dict(mode='live',phase=phase,proof_binding=binding,principal=principal,key_supplier=deferred,key_source_capability=source,draft_sha256=item['draft_sha256'],semantic_sha256=MEANING_SPEC_SHA256,request_sha256=item['request_sha256'],projection_sha256=item['projection_sha256'],agreement=O.CounterAgreement(O.COUNT_DOCUMENTATION,'a'*64,O.INPUT_FIELDS,0))
        from unittest.mock import AsyncMock
        with patch.object(C,'approval_gate',new=AsyncMock()) as gate:
            bad=scope|{'key_supplier':object()}
            with pytest.raises(C.ControllerError,match='PHASE_SCOPE'):asyncio.run(authority.verify(**bad))
            assert authority.phases==sequence[:sequence.index(phase)]
            expiry=asyncio.run(authority.verify(**scope));assert expiry.tzinfo
            assert gate.await_count==2
            with pytest.raises(C.ControllerError,match='PHASE_ORDER'):asyncio.run(authority.verify(**scope))


def test_explicit_epoch_commit_ack_loss_is_not_retried():
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock
    from scripts import cf002_interactive_login as login
    from src.modules.auth.application import session_service as auth
    from src.modules.supervisor.infrastructure import preparation_repository as repo
    sessions=[];added=[]
    @asynccontextmanager
    async def owned(_proof):
        session=NS(scalar=AsyncMock(return_value=None),add=added.append,commit=AsyncMock(side_effect=OSError(PRIVATE)))
        sessions.append(session);yield session
    with patch.object(login,'owned_session',owned),patch.object(auth,'validate_principal',new=AsyncMock()),patch.object(repo,'clock',new=AsyncMock(return_value=datetime.now(timezone.utc))):
        with pytest.raises(OSError):asyncio.run(C.initialize_epoch(object(),object(),str(uuid4()),mode='synthetic'))
    assert len(sessions)==1 and len(added)==1 and sessions[0].commit.await_count==1


@pytest.mark.parametrize('fault',['active','unknown','request','projection','count'])
def test_next_binding_requires_exact_observed_first_settlement(fault):
    item={'request_sha256':'a'*64,'projection_sha256':'b'*64}
    state=dict(count=1,generation=1,reserved=50000000,blocked=False,active=None,attempts={'a':dict(request_sha256='a'*64,projection_sha256='b'*64,observation={'state':'observed'})})
    if fault=='active':state['active']=str(uuid4())
    elif fault=='count':state['count']=2
    elif fault=='unknown':state['attempts']['a']['observation']['state']='unknown'
    elif fault=='request':state['attempts']['a']['request_sha256']='x'*64
    else:state['attempts']['a']['projection_sha256']='x'*64
    with pytest.raises(C.ControllerError,match='FIRST_SETTLEMENT_UNCONFIRMED'):C.normal_transition(state,item)


@pytest.mark.parametrize('fault',['expiry','source','scope','issuer','refused'])
def test_preclaim_authority_failures_are_supplier_and_create_zero(tmp_path,fault):
    store,approval,source=inputs(tmp_path);hooks=Hooks()
    if fault=='source':source.path.write_text('changed')
    elif fault=='scope':approval=C.ExternalApproval('0'*64,approval.issuer,approval.verify)
    elif fault=='issuer':approval=C.ExternalApproval(approval.scope_sha256,'other',approval.verify)
    elif fault=='refused':
        async def refused(**scope):return False
        approval=C.ExternalApproval(approval.scope_sha256,approval.issuer,refused)
    else:
        grant=C.decode((tmp_path/'grant.json').read_bytes());grant['expires_at']='2000-01-01T00:00:00+00:00'
        write(tmp_path/'grant.json',grant)
        state=C.decode((tmp_path/'state.json').read_bytes());state['grant_sha256']=C.digest(grant);write(tmp_path/'state.json',state)
        approval=C.ExternalApproval(C.digest(grant),grant['issuer'],approval.verify)
    with pytest.raises(C.ControllerError):asyncio.run(C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks))
    assert hooks.created==0 and hooks.steps==[]


def test_two_candidate_preflight_uses_real_policy_gateway_and_fixed_frame():
    async def run():
        service=sys.modules['src.supervisor.application.meaning_service']
        policy=sys.modules['src.supervisor.application.meaning_policy']
        proposals=sys.modules['src.supervisor.domain.meaning_proposals']
        queries=["\ud604\ub300\uac74\uc124 \uc678\uad6d\uc778 \ub9d0\uace0 3\uc8fc \uc218\uae09","\ud604\ub300\uac74\uc124 \uc5b4\uc81c \ub9d0\uace0 \uc678\uad6d\uc778 \ub9d0\uace0 \uae30\uad00 \uc218\uae09"]
        for index,query in enumerate(queries):
            answers=[] if index==0 else [dict(answer_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',slot='views',value='\uc218\uae09\ub9cc')]
            draft=M.Draft(original_query=query,answers=answers,revision=index)
            calls=[]
            class Gateway:
                async def propose(self,value,*,attempt_id=None):
                    calls.append(value.model_dump(mode='json'))
                    return proposals.MeaningProposal.model_validate(dict(schema_version='supervisor.meaning.v1',mentions=[dict(evidence=dict(source_kind='original_query',answer_id=None,start=0,end=4,text=query[:4]),negation=None)],views=[],conditions=[]))
            frame,status=await service.understand_v2(draft,Gateway(),attempt_id=str(uuid4()))
            assert len(calls)==1 and status=='supplemented'
            policy.validate_fixed_frame(draft,frame)
            assert frame.answers==draft.answers and frame.original_query==query
            assert frame.requested_views==['flow'] and not frame.negated_views
            assert any(c.kind=='exclude' and c.value=='\uc678\uad6d\uc778' for c in frame.conditions)
            assert all(c.disposition!='honored' for c in frame.conditions)
            if index==0:assert any(c.value=='3\uc8fc' for c in frame.conditions)
            else:assert any(c.value=='\uc5b4\uc81c' for c in frame.conditions) and any(c.kind=='focus' and c.value=='\uae30\uad00' for c in frame.conditions)
    asyncio.run(run())


# v1.3: exercise the actual live supplier closure
KEY_SECRET="cf026-v13-key-sentinel"
ERROR_SECRET="cf026-v13-error-sentinel"
BODY_SECRET="cf026-v13-body-sentinel"
STAGE_SECRET="cf026-v13-stage-sentinel"
ENUM_SECRET="cf026-v13-enum-sentinel"

def assert_sanitized(text):
    for secret in [KEY_SECRET,ERROR_SECRET,BODY_SECRET,STAGE_SECRET,ENUM_SECRET,PRIVATE,'cf024-synthetic-key-only']:
        assert secret not in text
        assert C.hashlib.sha256(secret.encode()).hexdigest() not in text

# With only authority, source
# IO and existing verifier callbacks simulated. No real key/HTTP/PG is used.
class DiagnosticHooks(Hooks):
    def __init__(self, scenario):
        super().__init__()
        self.scenario=scenario;self.reads=0;self.supplier_calls=0

    async def verify(self,store,approval,source,proof,principal,binding,item,index,*,observation):
        from unittest.mock import AsyncMock
        self.steps.append(index)
        original_gate=C.approval_gate
        async def gate(*args,**kwargs):
            if kwargs['synthetic'] is False:
                if self.scenario=='approval':raise C.ControllerError('APPROVAL_EXPIRED')
                return
            return await original_gate(*args,**kwargs)
        async def read(_source):
            self.reads+=1
            if self.scenario=='read-failure':raise OSError(ERROR_SECRET)
            if self.scenario=='cancel':raise asyncio.CancelledError()
            if self.scenario=='timeout':raise TimeoutError(ERROR_SECRET)
            return KEY_SECRET
        async def verifier(**scope):
            if self.scenario=='before':raise RuntimeError(ERROR_SECRET)
            authority=scope['authority']
            # Simulate the pre-existing count reservation ACK. Testing that ACK
            # itself remains the responsibility of the unchanged verifier tests.
            authority.phases=['initial','preflight','count']
            self.supplier_calls+=1
            supplied=await scope['key_supplier']()
            assert supplied==KEY_SECRET
            if self.scenario=='generation-authority':
                await authority.verify(mode='live',phase='generation',proof_binding=binding,principal=principal,
                    draft_sha256=item['draft_sha256'],semantic_sha256=MEANING_SPEC_SHA256,
                    request_sha256=item['request_sha256'],projection_sha256=item['projection_sha256'],
                    agreement=scope['counter_agreement'],key_supplier=scope['key_supplier'],key_source_capability=source)
                raise OSError(ERROR_SECRET)
            stages=['preflight_verified','claim_ACK_identity_verified','count_reservation_ACK']
            if self.scenario in {'generation-reservation','success'}:stages.append('generation_reservation_ACK')
            good=self.scenario=='success' and index==0
            if good:stages.append('settlement_ACK')
            return dict(stages=stages,meaning_status='supplemented' if good else 'unavailable',settlement='observed' if good else 'hold',raw_body=BODY_SECRET)
        with patch.object(C,'approval_gate',gate),patch.object(C.KeySource,'read',read),patch.object(V,'verify_live',verifier):
            return await C.OwnedHooks(synthetic=False).verify(store,approval,source,proof,principal,binding,item,index,observation=observation)

    async def snapshot(self,*args):
        if self.scenario=='success' and len(self.steps)==1:return await super().snapshot(*args)
        count=len(self.steps)
        return dict(count=count,generation=count if self.scenario in {'generation-reservation','success'} else 0,
                    reserved=count*50000000,blocked=True,active='held',
                    attempts={'held':dict(observation=dict(state='unknown',estimated_nano=None))})


@pytest.mark.parametrize('scenario,segment,code',[
    ('before','before_supplier','CONTROLLER_FAILED'),
    ('approval','supplier_failure','APPROVAL_EXPIRED'),
    ('read-failure','supplier_failure','CONTROLLER_FAILED'),
    ('cancel','supplier_failure','CANCELLED'),
    ('timeout','supplier_failure','TIMED_OUT'),
    ('returned','after_supplier_http_unknown','FIRST_SETTLEMENT_UNCONFIRMED'),
    ('generation-authority','count_gate_passed_before_generation_reservation','CONTROLLER_FAILED'),
    ('generation-reservation','generation_reservation_observed','FIRST_SETTLEMENT_UNCONFIRMED'),
])
def test_v13_actual_supplier_and_failure_gate_diagnostics(tmp_path,capsys,scenario,segment,code):
    store,approval,source=inputs(tmp_path);hooks=DiagnosticHooks(scenario)
    with pytest.raises(asyncio.CancelledError if scenario=='cancel' else C.ControllerError) as caught:
        asyncio.run(C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks))
    accounting=next(e for e in store.state['journal'] if e['phase']=='final_accounting')
    observation=accounting['diagnostics'][0]
    assert observation['segment']==segment and observation['failure_code']==code
    assert observation['count_http']=='unknown' and observation['generation_http']=='unknown'
    assert accounting['state']['reserved']==50000000  # never a call/usage zero
    assert len(accounting['diagnostics'])==1 and hooks.steps==[0] and hooks.cleaned==1
    assert hooks.reads==(0 if scenario in {'before','approval'} else 1)
    if scenario in {'returned','generation-reservation'}:
        assert observation['verifier_returned'] and observation['verifier']['settlement']=='hold'
        earlier=next(e for e in store.state['journal'] if e['phase']=='settlement_ACK')
        assert earlier['diagnostic']['verifier']==observation['verifier']
    else:assert not observation['verifier_returned'] and observation['verifier']['stages'] is None
    if scenario=='generation-authority':
        assert observation['generation_authority_verified']
        assert accounting['state']['generation']==0  # valid authority is not reservation
    assert store.state['status']=='closed'
    captured=capsys.readouterr()
    durable=C.canonical(store.state)+str(caught.value)+captured.out+captured.err
    assert_sanitized(durable)


def test_v13_two_attempts_keep_only_fixed_result_and_bounded_diagnostics(tmp_path,capsys):
    store,approval,source=inputs(tmp_path);hooks=DiagnosticHooks('success')
    result=asyncio.run(C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks))
    accounting=next(e for e in store.state['journal'] if e['phase']=='final_accounting')
    assert [e['index'] for e in accounting['diagnostics']]==[0,1]
    assert hooks.steps==[0,1] and hooks.reads==2
    assert all(e['supplier_stages']==['entered','approval_checked','source_read_entered','source_read_returned'] for e in accounting['diagnostics'])
    assert len(store.state['journal'])<=24 and store.state['journal'][-1]['phase']=='cleanup_confirmed'
    text=C.canonical(store.state)+C.canonical(result)+capsys.readouterr().out
    assert_sanitized(text)


@pytest.mark.parametrize('fault',['stages','stage-type','stage-limit','meaning','settlement','not-dict'])
def test_v13_malformed_verifier_fields_are_nullable_not_secret_or_hash(tmp_path,capsys,fault):
    store,approval,source=inputs(tmp_path);hooks=Hooks()
    value=dict(stages=['preflight_verified'],meaning_status='supplemented',settlement='observed',body=BODY_SECRET)
    if fault=='stages':value['stages']=[STAGE_SECRET]
    elif fault=='stage-type':value['stages']=[{'secret':STAGE_SECRET}]
    elif fault=='stage-limit':value['stages']=['preflight_verified']*17
    elif fault=='meaning':value['meaning_status']=ENUM_SECRET
    elif fault=='settlement':value['settlement']=ENUM_SECRET
    else:value=BODY_SECRET
    async def verify(*args,**kwargs):hooks.steps.append(0);return value
    with patch.object(hooks,'verify',verify):
        with pytest.raises(C.ControllerError,match='DIAGNOSTIC_INVALID') as caught:
            asyncio.run(C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks))
    diagnostic=next(e for e in store.state['journal'] if e['phase']=='final_accounting')['diagnostics'][0]
    assert diagnostic['verifier_returned'] and diagnostic['verifier']==dict(stages=None,meaning_status=None,settlement=None)
    assert diagnostic['failure_code']=='DIAGNOSTIC_INVALID' and hooks.steps==[0]
    text=C.canonical(store.state)+str(caught.value)+capsys.readouterr().out
    assert_sanitized(text)


@pytest.mark.parametrize('phase',['settlement_ACK','final_accounting','closing'])
def test_v13_diagnostic_accounting_ack_failure_preserves_hold_proof_and_stops(tmp_path,phase):
    store,approval,source=inputs(tmp_path);hooks=DiagnosticHooks('returned');persist=store.persist
    def fail(status,event):
        if event['phase']==phase:raise C.ControllerError('STATE_ACK_UNKNOWN')
        return persist(status,event)
    with patch.object(store,'persist',fail):
        with pytest.raises(C.ControllerError):asyncio.run(C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks))
    assert hooks.steps==[0] and hooks.reads==1 and hooks.cleaned==0 and hooks.preserved==1
    assert store.state['status']=='claimed'
    if phase!='final_accounting':
        final=next(e for e in store.state['journal'] if e['phase']=='final_accounting')
        assert final['state']['reserved']==50000000


def test_v13_first_observed_result_diagnostic_ack_loss_alone_blocks_second_supplier(tmp_path):
    store,approval,source=inputs(tmp_path);hooks=DiagnosticHooks('success');persist=store.persist;failed=[]
    def lose_ack(status,event):
        if event['phase']=='settlement_ACK':
            # This first result and ledger permit continuation absent ACK loss.
            assert event['index']==0 and event['diagnostic']['verifier']['settlement']=='observed'
            assert event['diagnostic']['verifier']['meaning_status']=='supplemented'
            C.normal_transition(event['state'],store.grant['requests'][0])
            failed.append(event['phase'])
            raise C.ControllerError('STATE_ACK_UNKNOWN')
        return persist(status,event)
    with patch.object(store,'persist',lose_ack):
        with pytest.raises(C.ControllerError,match='STATE_ACK_UNKNOWN'):
            asyncio.run(C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks))
    assert failed==['settlement_ACK']
    assert hooks.steps==[0] and hooks.supplier_calls==1 and hooks.reads==1
    # No second verifier callback/dispatch or supplier can model a second send.
    assert sum(index==1 for index in hooks.steps)==0
    assert hooks.cleaned==0 and hooks.preserved==1 and store.state['status']=='claimed'
    final=next(e for e in store.state['journal'] if e['phase']=='final_accounting')
    assert final['diagnostic_ack_unknown'] and final['state']['reserved']==50000000
    assert final['state']['attempts']['a']['observation']['state']=='observed'
    assert final['diagnostics'][0]['verifier']['settlement']=='observed'


def test_v13_cancellation_is_rethrown_even_when_diagnostic_ack_fails(tmp_path):
    store,approval,source=inputs(tmp_path);hooks=DiagnosticHooks('cancel');persist=store.persist
    def fail(status,event):
        if event['phase']=='final_accounting':raise C.ControllerError('STATE_ACK_UNKNOWN')
        return persist(status,event)
    with patch.object(store,'persist',fail):
        with pytest.raises(asyncio.CancelledError):asyncio.run(C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks))
    assert hooks.preserved==1 and hooks.cleaned==0 and store.state['status']=='claimed'


def test_v13_actual_journal24_cap_reserves_three_terminal_records(tmp_path):
    store,_,_=inputs(tmp_path)
    with store.locked():
        store.persist('claimed',{'phase':'claim_ACK'})
        for _ in range(20):store.persist('claimed',{'phase':'synthetic_nonterminal'})
        assert len(store.state['journal'])==21
        with pytest.raises(C.ControllerError,match='PRIVATE_STATE_LIMIT'):
            store.persist('claimed',{'phase':'settlement_ACK'})
        diagnostics=[C.AttemptObservation(i).snapshot() for i in range(2)]
        store.persist('claimed',{'phase':'final_accounting','diagnostics':diagnostics})
        store.persist('claimed',{'phase':'closing'})
        store.persist('closed',{'phase':'cleanup_confirmed'})
        assert len(store.state['journal'])==24 and (tmp_path/'state.json').stat().st_size<=65536
        with pytest.raises(C.ControllerError):store.persist('closed',{'phase':'cleanup_confirmed'})


def test_v13_unknown_error_stage_and_supplier_label_never_hash_secret():
    observation=C.AttemptObservation(0)
    error=C.ControllerError();error.stage=STAGE_SECRET
    observation.failed(error)
    assert observation.snapshot()['failure_code']=='CONTROLLER_UNAVAILABLE'
    with pytest.raises(C.ControllerError,match='DIAGNOSTIC_INVALID'):observation.supplier(STAGE_SECRET)
    result=C.canonical(observation.snapshot())
    assert_sanitized(result)


def continuation_inputs(tmp_path):
    root=tmp_path.resolve();root.chmod(0o700)
    permission,receipt,source=C.synthetic_continuation_fixture(root)
    before={name:(root/name).read_bytes() for name in permission.anchor.files}
    return permission,receipt,source,before


def test_v14_code_provenance_bound_is_separate_from_key_state64k(tmp_path):
    root=tmp_path/'verith-supervisor-live-controller';code=root/'backend/scripts/cf026_supervisor_live_controller.py'
    code.parent.mkdir(parents=True);raw=b'#'+b'x'*70000+b'\n';code.write_bytes(raw);code.chmod(0o644)
    info=root.stat();cap=C.ReviewedCodeRoot(root,(info.st_dev,info.st_ino,info.st_uid,info.st_mode),C.hashlib.sha256(raw).hexdigest())
    with patch.object(C,'__file__',str(code)):
        cap.check()
        with pytest.raises(C.ControllerError,match='FILE_DRIFT'):C.read_fixed(code,0o644)
        code.write_bytes(b'#'+b'x'*131072)
        with pytest.raises(C.ControllerError,match='FILE_DRIFT'):cap.check()


def test_v14_issue_once_tombstone_and_parent_bytes_immutable(tmp_path):
    permission,receipt,source,before=continuation_inputs(tmp_path)
    cap=asyncio.run(C.issue_continuation(permission,receipt,source))
    assert cap.seal is C._ISSUED_CONTINUATION
    assert (tmp_path/C.CONTINUATION_WITNESS).stat().st_mode&0o777==0o600
    assert (tmp_path/C.CONTINUATION_SLOT).stat().st_mode&0o777==0o700
    assert C.fixed_continuation_id(permission.anchor)==receipt['continuation_id']
    for name,raw in before.items():assert (tmp_path/name).read_bytes()==raw
    with pytest.raises(C.ControllerError,match='CONTINUATION_USED'):asyncio.run(C.issue_continuation(permission,receipt,source))
    with pytest.raises(C.ControllerError,match='LIVE_GATE_CLOSED'):asyncio.run(C.run_continuation(cap,source=source))
    assert not (tmp_path/C.CONTINUATION_SLOT/'state.pending').exists()


@pytest.mark.parametrize('fault',['count','generation','hold','observation','closed','state','grant','lock','directory','copy','alias'])
def test_v14_parent_ancestry_drift_blocks_issue(tmp_path,fault):
    original=tmp_path/'original';original.mkdir(mode=0o700)
    permission,receipt,source,_=continuation_inputs(original)
    if fault in {'count','generation','hold','observation','closed'}:
        state=C.decode((original/'state.json').read_bytes())
        ledger=next(e['state'] for e in state['journal'] if e['phase']=='final_accounting')
        if fault=='count':ledger['count']=2
        elif fault=='generation':ledger['generation']=1
        elif fault=='hold':ledger['reserved']=0
        elif fault=='observation':next(iter(ledger['attempts'].values()))['observation']['estimated_nano']=1
        else:state['status']='claimed'
        write(original/'state.json',state)
    elif fault in {'state','grant','lock'}:
        path=original/('execution.lock' if fault=='lock' else fault+'.json');path.write_bytes(path.read_bytes()+b' ')
    elif fault=='directory':original.chmod(0o755)
    elif fault=='alias':
        alias=tmp_path/'alias';alias.symlink_to(original,target_is_directory=True)
        permission.anchor=C.ParentAnchor(alias,permission.anchor.directory,permission.anchor.lock,permission.anchor.files)
    else:
        import shutil
        copied=tmp_path/'copied';shutil.copytree(original,copied)
        permission.anchor=C.ParentAnchor.capture(copied,evidence_names=('failure.json',))
        receipt['parent']=permission.anchor.scope();receipt['continuation_id']=C.fixed_continuation_id(permission.anchor);permission.receipt_sha256=C.digest(receipt)
    with pytest.raises(C.ControllerError):asyncio.run(C.issue_continuation(permission,receipt,source))
    assert not (permission.anchor.path/C.CONTINUATION_SLOT).exists()


@pytest.mark.parametrize('fault',['two','second','question','prepare-key','model','spec','price','source','expired','epoch'])
def test_v14_receipt_scope_cannot_expand_first_payload_or_budget(tmp_path,fault):
    permission,receipt,source,_=continuation_inputs(tmp_path)
    if fault=='two':receipt['requests']*=2
    elif fault=='second':receipt['requests']=[C.decode((tmp_path/'grant.json').read_bytes())['requests'][1]]
    elif fault=='question':receipt['requests'][0]['prepare_body']['draft']['original_query']=BODY_SECRET
    elif fault=='prepare-key':receipt['requests'][0]['prepare_body']['prepare_key']=str(uuid4())
    elif fault=='model':receipt['model']='other'
    elif fault=='spec':receipt['semantic_sha256']='0'*64
    elif fault=='price':receipt['price_sha256']='0'*64
    elif fault=='source':receipt['source']['identity']['ino']+=1
    elif fault=='epoch':receipt['epoch_id']=C.decode((tmp_path/'grant.json').read_bytes())['epoch_id']
    else:receipt['expires_at']='2000-01-01T00:00:00+00:00'
    permission.receipt_sha256=C.digest(receipt)
    with pytest.raises(C.ControllerError):asyncio.run(C.issue_continuation(permission,receipt,source))
    assert not (tmp_path/C.CONTINUATION_SLOT).exists()


@pytest.mark.parametrize('fault',['tombstone-only','partial-receipt','state-ack','slot-deleted','witness-missing','witness-drift'])
def test_v14_partial_issuance_and_lost_slot_never_reissue(tmp_path,fault):
    permission,receipt,source,_=continuation_inputs(tmp_path)
    original=C.exclusive_private_file
    if fault in {'tombstone-only','partial-receipt','state-ack'}:
        def fail(path,value):
            if fault=='tombstone-only' and path.name=='receipt.json':raise OSError(ERROR_SECRET)
            if fault=='partial-receipt' and path.name=='state.json':raise OSError(ERROR_SECRET)
            original(path,value)
            if fault=='state-ack' and path.name=='state.json':raise OSError(ERROR_SECRET)
        with patch.object(C,'exclusive_private_file',fail):
            with pytest.raises(C.ControllerError):asyncio.run(C.issue_continuation(permission,receipt,source))
        assert (tmp_path/C.CONTINUATION_WITNESS).exists()
    else:
        cap=asyncio.run(C.issue_continuation(permission,receipt,source))
        if fault=='slot-deleted':
            import shutil
            shutil.rmtree(tmp_path/C.CONTINUATION_SLOT)
        elif fault=='witness-missing':(tmp_path/C.CONTINUATION_WITNESS).unlink()
        else:(tmp_path/C.CONTINUATION_WITNESS).write_bytes(b'{}')
        with pytest.raises(C.ControllerError):asyncio.run(C.run_continuation(cap,source=source,synthetic=True,hooks=Hooks()))
    # Even a fresh issuer object cannot treat absence/partial state as pristine.
    fresh=C.ContinuationPermission(permission.anchor,permission.receipt_sha256,permission.issuer,'synthetic',permission.verify,permission.issuance)
    with pytest.raises(C.ControllerError):asyncio.run(C.issue_continuation(fresh,receipt,source))


def test_v14_tombstone_fsync_failure_before_slot_blocks_restart(tmp_path):
    permission,receipt,source,_=continuation_inputs(tmp_path)
    original=C.fsync_directory
    def fail_local_tombstone(path):
        if (tmp_path/C.CONTINUATION_WITNESS).exists():raise OSError(ERROR_SECRET)
        return original(path)
    with patch.object(C,'fsync_directory',side_effect=fail_local_tombstone):
        with pytest.raises(C.ControllerError):asyncio.run(C.issue_continuation(permission,receipt,source))
    assert (tmp_path/C.CONTINUATION_WITNESS).exists() and not (tmp_path/C.CONTINUATION_SLOT).exists()
    fresh=C.ContinuationPermission(permission.anchor,permission.receipt_sha256,permission.issuer,'synthetic',permission.verify,permission.issuance)
    with pytest.raises(C.ControllerError,match='CONTINUATION_USED'):asyncio.run(C.issue_continuation(fresh,receipt,source))


class ContinuationUnitHooks(Hooks):
    def __init__(self,fault=None):
        super().__init__(fault);self.local=dict(count=0,generation=0,reserved=0);self.reads=0;self.order=[]
    async def verify(self,store,source,proof,principal,binding,observation):
        self.steps.append(0)
        from src.modules.supervisor.domain.contracts import PreparationRequest
        item=store.grant['requests'][0];body=PreparationRequest.model_validate(item['prepare_body'])
        deferred=object()
        authority=C.ContinuationAuthority(store,source,proof,binding,principal,body,deferred,observation)
        async def fresh():
            if store.state['preparation'] is None:store.persist('claimed',{'phase':'preparation_binding_ACK'},preparation={'attempt':'one'})
            return dict(self.local)
        authority.fresh_preparation=fresh
        scope=dict(mode='synthetic',proof_binding=binding,principal=principal,key_supplier=deferred,key_source_capability=source,
            draft_sha256=item['draft_sha256'],semantic_sha256=store.grant['semantic_sha256'],
            request_sha256=item['request_sha256'],projection_sha256=item['projection_sha256'],
            agreement=O.CounterAgreement(O.COUNT_DOCUMENTATION,store.grant['counter']['documentation_sha256'],O.INPUT_FIELDS,0))
        for phase in ['initial','preflight','count']:
            await authority.verify(**scope,phase=phase);self.order.append('root-'+phase)
        if self.fault=='local-ack':
            self.local=dict(count=1,generation=0,reserved=50000000);raise C.ControllerError('STATE_ACK_UNKNOWN')
        self.local=dict(count=1,generation=0,reserved=50000000);self.order.append('local-count-ACK')
        observation.supplier('entered');observation.supplier('approval_checked');observation.supplier('source_read_entered')
        if self.fault=='cancel':observation.supplier('cancelled');raise asyncio.CancelledError()
        if self.fault=='timeout':observation.supplier('timed_out');raise TimeoutError(ERROR_SECRET)
        self.reads+=1;assert await source.read()=='cf024-synthetic-key-only';self.order.append('supplier')
        observation.supplier('source_read_returned')
        if self.fault=='hold':return dict(stages=['count_reservation_ACK'],meaning_status='unavailable',settlement='hold')
        await authority.verify(**scope,phase='generation');self.order.append('root-generation')
        self.local=dict(count=1,generation=1,reserved=50000000);self.order.append('local-generation-ACK')
        return dict(stages=['count_reservation_ACK','generation_reservation_ACK','settlement_ACK'],meaning_status='supplemented',settlement='observed')
    async def snapshot(self,*args):
        if self.fault=='snapshot':raise OSError(ERROR_SECRET)
        return self.local|dict(attempts={'one':dict(observation={'state':'observed' if self.local['generation'] else 'unknown','estimated_nano':120000 if self.local['generation'] else None})})


@pytest.mark.parametrize('fault',[None,'hold','local-ack','cancel','timeout','snapshot','cleanup'])
def test_v14_actual_lock_slot_authority_and_one_child_lifecycle(tmp_path,fault):
    permission,receipt,source,before=continuation_inputs(tmp_path)
    cap=asyncio.run(C.issue_continuation(permission,receipt,source));hooks=ContinuationUnitHooks(fault)
    if fault:
        with pytest.raises(asyncio.CancelledError if fault=='cancel' else C.ControllerError):
            asyncio.run(C.run_continuation(cap,source=source,synthetic=True,hooks=hooks))
    else:assert asyncio.run(C.run_continuation(cap,source=source,synthetic=True,hooks=hooks))['approval_closed']
    assert hooks.created==1 and hooks.steps==[0] and hooks.reads<=1
    raw=C.decode((tmp_path/C.CONTINUATION_SLOT/'state.json').read_bytes())
    account=next(e for e in raw['journal'] if e['phase']=='final_accounting')
    assert account['total_hold_nano']==100000000 and account['total_estimated_nano'] is None
    assert account['inherited_hold_nano']==50000000 and account['total_attempts_consumed']==2
    assert raw['rights']['count']==1 and raw['rights']['generation']<=1
    assert len(raw['journal'])<=24
    for _ in range(2):
        with pytest.raises(C.ControllerError):asyncio.run(C.run_continuation(cap,source=source,synthetic=True,hooks=hooks))
    assert hooks.created==1
    for name,value in before.items():assert (tmp_path/name).read_bytes()==value
    assert_sanitized(C.canonical(raw))


@pytest.mark.parametrize('phase',['continuation_claim_ACK','root_count_authority_ACK','final_accounting','closing','cleanup_confirmed'])
def test_v14_claim_phase_accounting_ack_loss_never_resets_rights(tmp_path,phase):
    permission,receipt,source,_=continuation_inputs(tmp_path)
    cap=asyncio.run(C.issue_continuation(permission,receipt,source));hooks=ContinuationUnitHooks();persist=C.ContinuationStore.persist
    def lose(self,status,event,**kwargs):
        # Simulate a durable write whose ACK was lost. State remains consumed.
        result=persist(self,status,event,**kwargs)
        if event['phase']==phase:raise C.ControllerError('CONTINUATION_ACK_UNKNOWN')
        return result
    with patch.object(C.ContinuationStore,'persist',lose):
        with pytest.raises(C.ControllerError):asyncio.run(C.run_continuation(cap,source=source,synthetic=True,hooks=hooks))
    raw=C.decode((tmp_path/C.CONTINUATION_SLOT/'state.json').read_bytes())
    assert raw['claimed'] and raw['total_hold_nano']==100000000
    if phase=='continuation_claim_ACK':assert hooks.created==0
    if phase=='root_count_authority_ACK':assert hooks.reads==0
    if phase in {'final_accounting','closing'}:assert hooks.preserved==1 and hooks.cleaned==0
    with pytest.raises(C.ControllerError):asyncio.run(C.run_continuation(cap,source=source,synthetic=True,hooks=hooks))


def test_v14_phase_rights_are_durable_max1_and_before_local_ack(tmp_path):
    permission,receipt,source,_=continuation_inputs(tmp_path);cap=asyncio.run(C.issue_continuation(permission,receipt,source))
    with C.PrivateStore(tmp_path.resolve()).locked() as parent:
        store=C.ContinuationStore(cap,parent);store.persist('claimed',{'phase':'continuation_claim_ACK'})
        store.persist('claimed',{'phase':'preparation_binding_ACK'},preparation={'attempt':'one'})
        with pytest.raises(C.ControllerError):store.consume_phase('generation',dict(count=0,generation=0,reserved=0))
        store.consume_phase('count',dict(count=0,generation=0,reserved=0))
        with pytest.raises(C.ControllerError):store.consume_phase('count',dict(count=0,generation=0,reserved=0))
        with pytest.raises(C.ControllerError):store.consume_phase('generation',dict(count=0,generation=0,reserved=0))
        store.consume_phase('generation',dict(count=1,generation=0,reserved=50000000))
        with pytest.raises(C.ControllerError):store.consume_phase('generation',dict(count=1,generation=0,reserved=50000000))
        with pytest.raises(C.ControllerError):store.persist('claimed',{'phase':'preparation_binding_ACK'},preparation={'attempt':'different'})
        assert store.state['rights']=={'count':1,'generation':1}


def test_v14_existing_live_factory_is_dispatch_boundary_no_synthetic_transport(tmp_path):
    permission,receipt,source,_=continuation_inputs(tmp_path)
    async def run():
        observation=C.AttemptObservation(0);hooks=C.ContinuationHooks(synthetic=False)
        synthetic_store=NS(grant=receipt)
        with pytest.raises(C.ControllerError,match='LIVE_GATE_CLOSED'):
            await hooks.verify(synthetic_store,source,object(),object(),object(),observation)
        # Direct callback dispatch spy only: not a real issued live capability.
        live=dict(receipt,mode='live');store=NS(grant=live)
        captured=[]
        async def existing(**scope):captured.append(scope);return dict(stages=[],meaning_status='unavailable',settlement='not_called')
        with patch.object(V,'verify_live',existing):await hooks.verify(store,source,object(),object(),object(),observation)
        assert len(captured)==1 and 'transport' not in captured[0]
        assert type(captured[0]['authority']) is C.ContinuationAuthority
        assert type(captured[0]['key_supplier']) is V.DeferredKeySource
        assert type(captured[0]['counter_agreement']) is O.CounterAgreement
    asyncio.run(run())


def test_v14_concurrent_issuance_and_claim_have_one_lock_winner(tmp_path):
    permission,receipt,source,_=continuation_inputs(tmp_path)
    async def run():
        reached,release=asyncio.Event(),asyncio.Event();verify=permission.verify
        async def held(**scope):
            if scope['phase']=='issue':reached.set();await release.wait()
            return await verify(**scope)
        permission.verify=held
        winner=asyncio.create_task(C.issue_continuation(permission,receipt,source));await reached.wait()
        other=C.ContinuationPermission(permission.anchor,permission.receipt_sha256,permission.issuer,'synthetic',verify,permission.issuance)
        with pytest.raises(C.ControllerError,match='APPROVAL_BUSY'):await C.issue_continuation(other,receipt,source)
        release.set();cap=await winner
        reached.clear();release.clear()
        async def hold_claim(**scope):
            if scope['phase']=='claim':reached.set();await release.wait()
            return await verify(**scope)
        permission.verify=hold_claim;hooks=ContinuationUnitHooks()
        child=asyncio.create_task(C.run_continuation(cap,source=source,synthetic=True,hooks=hooks));await reached.wait()
        loser=ContinuationUnitHooks()
        with pytest.raises(C.ControllerError,match='APPROVAL_BUSY'):await C.run_continuation(cap,source=source,synthetic=True,hooks=loser)
        release.set();await child
        assert hooks.created==1 and loser.created==0
    asyncio.run(run())


def test_v14_historical_expiry_is_not_current_authority_expiry(tmp_path):
    permission,receipt,source,_=continuation_inputs(tmp_path)
    old=C.decode((tmp_path/'grant.json').read_bytes());assert C.parse_expiry(old['expires_at'])<datetime.now(timezone.utc)
    cap=asyncio.run(C.issue_continuation(permission,receipt,source))
    class Expired(datetime):
        @classmethod
        def now(cls,tz=None):return C.parse_expiry(receipt['expires_at'])+timedelta(seconds=1)
    hooks=ContinuationUnitHooks()
    with patch.object(C,'datetime',Expired):
        with pytest.raises(C.ControllerError,match='APPROVAL_EXPIRED'):asyncio.run(C.run_continuation(cap,source=source,synthetic=True,hooks=hooks))
    assert hooks.created==0 and hooks.reads==0


def test_v14_slot_journal_keeps24_cap_and_three_terminal_places(tmp_path):
    permission,receipt,source,_=continuation_inputs(tmp_path);cap=asyncio.run(C.issue_continuation(permission,receipt,source))
    with C.PrivateStore(tmp_path.resolve()).locked() as parent:
        store=C.ContinuationStore(cap,parent);store.persist('claimed',{'phase':'continuation_claim_ACK'})
        for _ in range(20):store.persist('claimed',{'phase':'synthetic-observation'})
        with pytest.raises(C.ControllerError,match='PRIVATE_STATE_LIMIT'):store.persist('claimed',{'phase':'root_count_authority_ACK'})
        store.persist('claimed',C.continuation_accounting(None,C.AttemptObservation(0),store.state['rights']))
        store.persist('claimed',{'phase':'closing'});store.persist('closed',{'phase':'cleanup_confirmed'})
        assert len(store.state['journal'])==24
        assert (tmp_path/C.CONTINUATION_SLOT/'state.json').stat().st_size<=65536


def fresh_continuation_permission(permission, *, issuance=None):
    return C.ContinuationPermission(permission.anchor, permission.receipt_sha256,
        permission.issuer, permission.mode, permission.verify,
        permission.issuance if issuance is None else issuance)


def test_v14_both_local_artifacts_lost_fresh_permission_and_issuer_restart_cannot_reissue(tmp_path):
    import shutil
    permission,receipt,source,before=continuation_inputs(tmp_path)
    asyncio.run(C.issue_continuation(permission,receipt,source))
    external=tmp_path/'synthetic-external-issuance.json'
    consumed=external.read_bytes()
    shutil.rmtree(tmp_path/C.CONTINUATION_SLOT)
    (tmp_path/C.CONTINUATION_WITNESS).unlink()
    restarted=C.synthetic_issuance_authority(external,permission.anchor)
    fresh=fresh_continuation_permission(permission,issuance=restarted)
    with pytest.raises(C.ControllerError,match='CONTINUATION_USED'):
        asyncio.run(C.issue_continuation(fresh,receipt,source))
    assert external.read_bytes()==consumed
    assert not (tmp_path/C.CONTINUATION_SLOT).exists()
    assert not (tmp_path/C.CONTINUATION_WITNESS).exists()
    for name,raw in before.items():assert (tmp_path/name).read_bytes()==raw


@pytest.mark.parametrize('fault',['absent-authority','missing','unknown','malformed','wrong-mode'])
def test_v14_external_authority_absence_or_uncertainty_is_not_first_issuance(tmp_path,fault):
    permission,receipt,source,_=continuation_inputs(tmp_path)
    external=tmp_path/'synthetic-external-issuance.json'
    if fault=='absent-authority':permission.issuance=None
    elif fault=='missing':external.unlink()
    elif fault=='unknown':write(external,{'state':'unknown'})
    elif fault=='malformed':external.write_bytes(b'not-json')
    else:
        a=permission.issuance
        permission.issuance=C.OneShotIssuanceAuthority(a.identity_sha256,'live',a.observe,a.consume_once)
    with pytest.raises(C.ControllerError):asyncio.run(C.issue_continuation(permission,receipt,source))
    assert not (tmp_path/C.CONTINUATION_SLOT).exists()
    assert not (tmp_path/C.CONTINUATION_WITNESS).exists()
    if fault=='missing':
        assert not external.exists()
        with pytest.raises(OSError):C.synthetic_issuance_authority(external,permission.anchor)


@pytest.mark.parametrize('fault',['ack-lost','ack-malformed','readback-lost','cancelled'])
def test_v14_external_consumption_ack_loss_precedes_local_writes_and_never_restores_right(tmp_path,fault):
    permission,receipt,source,_=continuation_inputs(tmp_path)
    original=permission.issuance;consumes=[];reads=[]
    async def consume(**scope):
        ack=await original.consume_once(**scope);consumes.append(True)
        if fault=='ack-lost':raise TimeoutError(ERROR_SECRET)
        if fault=='cancelled':raise asyncio.CancelledError()
        if fault=='ack-malformed':return {'state':'consumed'}
        return ack
    async def observe(**scope):
        reads.append(True)
        if fault=='readback-lost' and consumes:raise OSError(ERROR_SECRET)
        return await original.observe(**scope)
    permission.issuance=C.OneShotIssuanceAuthority(original.identity_sha256,'synthetic',observe,consume)
    expected=asyncio.CancelledError if fault=='cancelled' else C.ControllerError
    with pytest.raises(expected):asyncio.run(C.issue_continuation(permission,receipt,source))
    assert consumes==[True]
    assert not (tmp_path/C.CONTINUATION_SLOT).exists() and not (tmp_path/C.CONTINUATION_WITNESS).exists()
    fresh=fresh_continuation_permission(permission,issuance=original)
    with pytest.raises(C.ControllerError,match='CONTINUATION_USED'):
        asyncio.run(C.issue_continuation(fresh,receipt,source))
    assert C.decode((tmp_path/'synthetic-external-issuance.json').read_bytes())['state']=='consumed'
    assert_sanitized(C.canonical(receipt))


def test_v14_external_authority_is_rechecked_before_runtime_bootstrap(tmp_path):
    permission,receipt,source,_=continuation_inputs(tmp_path)
    cap=asyncio.run(C.issue_continuation(permission,receipt,source))
    (tmp_path/'synthetic-external-issuance.json').unlink()
    hooks=ContinuationUnitHooks()
    with pytest.raises(C.ControllerError):
        asyncio.run(C.run_continuation(cap,source=source,synthetic=True,hooks=hooks))
    assert hooks.created==0 and hooks.reads==0
    assert C.decode((tmp_path/C.CONTINUATION_SLOT/'state.json').read_bytes())['status']=='issued'


def test_v14_new_receipt_or_permission_cannot_reset_external_parent_namespace(tmp_path):
    import shutil
    permission,receipt,source,_=continuation_inputs(tmp_path)
    asyncio.run(C.issue_continuation(permission,receipt,source))
    shutil.rmtree(tmp_path/C.CONTINUATION_SLOT);(tmp_path/C.CONTINUATION_WITNESS).unlink()
    changed=C.decode(C.canonical(receipt));changed['epoch_id']=str(uuid4())
    fresh=C.ContinuationPermission(permission.anchor,C.digest(changed),permission.issuer,'synthetic',permission.verify,permission.issuance)
    async def current(**scope):return True
    fresh.verify=current
    with pytest.raises(C.ControllerError):asyncio.run(C.issue_continuation(fresh,changed,source))
    assert not (tmp_path/C.CONTINUATION_SLOT).exists()


def test_v14_different_authority_cannot_reissue_same_receipt_after_both_local_losses(tmp_path):
    import shutil
    permission,receipt,source,_=continuation_inputs(tmp_path)
    asyncio.run(C.issue_continuation(permission,receipt,source))
    shutil.rmtree(tmp_path/C.CONTINUATION_SLOT);(tmp_path/C.CONTINUATION_WITNESS).unlink()
    calls=[]
    async def false_first(**scope):calls.append(True);return scope|dict(state='available')
    other=C.OneShotIssuanceAuthority('d'*64,'synthetic',false_first,false_first)
    fresh=fresh_continuation_permission(permission,issuance=other)
    with pytest.raises(C.ControllerError,match='EXTERNAL_APPROVAL_REQUIRED'):
        asyncio.run(C.issue_continuation(fresh,receipt,source))
    assert calls==[] and not (tmp_path/C.CONTINUATION_SLOT).exists()


def aggregate_inputs(tmp_path):
    tmp_path.chmod(0o700)
    return C.synthetic_aggregate_fixture(tmp_path.resolve())


def extra_intent(permission,intent):
    value=C.decode(C.canonical(intent));child=str(uuid4())
    value.update(allocation_id=str(uuid4()),child_id=child,child_path=str(permission.path/'children'/child),nonce=C.digest(str(uuid4())))
    value['template']['approval_id']=child;value['template']['epoch_id']=str(uuid4())
    for item in value['template']['requests']:item['prepare_body']['prepare_key']=str(uuid4())
    return value


def approve_intents(permission, intents):
    original=permission.verify;allowed={C.digest(x) for x in intents}
    async def verify(**scope):
        if scope.get('phase')=='allocation':
            return scope==dict(phase='allocation',header_sha256=C.digest(permission.header),event_sha256=C.digest(permission.header['approval_event']),mode='synthetic',intent_sha256=scope['intent_sha256']) and scope['intent_sha256'] in allowed
        return await original(**scope)
    permission.verify=verify


class AggregateHooks(Hooks):
    def __init__(self,cap,intent,fault=None):super().__init__(fault);self.cap=cap;self.intent=intent
    def create(self):
        state=C.decode((self.cap.permission.path/'state.json').read_bytes())
        a=state['allocations'][self.intent['allocation_id']]
        assert a['issue_consumed'] and a['start_consumed'] and a['child']
        assert state['total_reserved_nano']==150000000
        super().create()
    async def verify(self,*args,observation=None):
        store,approval=args[:2]
        assert await approval.verify(scope_sha256=C.digest(store.grant),issuer=store.grant['issuer'],mode='synthetic',counter=store.grant['counter'])
        return await super().verify(*args,observation=observation)


def test_v16_reserve_issue_bind_start_actual_child_and_never_refund(tmp_path):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        cap=await C.bootstrap_aggregate(permission);hooks=AggregateHooks(cap,intent)
        async with C.AggregateSession(cap) as s:
            transitions=[];original=s.commit
            async def observed(state,phase,*a,**kw):
                await original(state,phase,*a,**kw);transitions.append(phase)
                if phase=='issue':assert not Path(intent['child_path']).exists()
                if phase=='start':assert hooks.created==0
            s.commit=observed
            await s.allocate(intent,source);await s.issue(intent,source);await s.start(intent,source,hooks=hooks)
            assert transitions==['reserve','issue','bind','start','accounting','terminal']
            state=await s.check();assert state['total_reserved_nano']==150000000
            assert hooks.created==1 and hooks.cleaned==1 and hooks.steps==[0,1]
            head=dict(cap.head);await s.allocate(intent,source);assert cap.head==head
            with pytest.raises(C.ControllerError):await s.issue(intent,source)
            with pytest.raises(C.ControllerError):await s.start(intent,source,hooks=hooks)
            assert hooks.created==1 and (await s.check())['total_reserved_nano']==150000000
    asyncio.run(run())


@pytest.mark.parametrize('fault',['absent','partial','bootstrap-ack','history-missing','copy-path','live-with-synthetic-history'])
def test_v16_bootstrap_is_once_with_attempt_ack_before_root_and_no_fallback(tmp_path,fault):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        if fault=='history-missing':(tmp_path/'coordination.json').unlink()
        elif fault=='partial':permission.path.mkdir(mode=0o700)
        elif fault=='bootstrap-ack':
            h=permission.history
            async def lost(**scope):await h.compare_exchange(**scope);raise OSError(ERROR_SECRET)
            permission.history=C.CoordinationHistory(h.identity_sha256,h.mode,h.read,lost)
        elif fault=='copy-path':permission.path=tmp_path/'other'
        elif fault=='live-with-synthetic-history':permission.header['mode']='live'
        else:
            cap=await C.bootstrap_aggregate(permission)
            import shutil
            shutil.rmtree(permission.path)
        fresh=C.AggregatePermission(permission.path,permission.header,permission.history,permission.verify)
        with pytest.raises(C.ControllerError):await C.bootstrap_aggregate(fresh)
        if fault in {'bootstrap-ack','history-missing','copy-path','live-with-synthetic-history'}:assert not permission.path.exists()
    asyncio.run(run())


def test_v16_confirmed_reopen_requires_independent_head_and_explicit_restart_attestation(tmp_path):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        cap=await C.bootstrap_aggregate(permission)
        async with C.AggregateSession(cap) as s:await s.allocate(intent,source)
        async def confirm(**scope):return scope==dict(bootstrap_id=permission.header['bootstrap_id'],binding_sha256=C.digest(cap.binding),head_sha256=C.digest(cap.head))
        with pytest.raises(C.ControllerError):await C.reopen_aggregate(permission,expected_binding=cap.binding,expected_head=cap.head)
        reopened=await C.reopen_aggregate(permission,expected_binding=cap.binding,expected_head=cap.head,confirm_restart=confirm)
        async with C.AggregateSession(reopened) as s:
            assert (await s.check())['total_reserved_nano']==150000000
        wrong=dict(cap.head,sequence=0)
        with pytest.raises(C.ControllerError):await C.reopen_aggregate(permission,expected_binding=cap.binding,expected_head=wrong,confirm_restart=confirm)
    asyncio.run(run())


@pytest.mark.parametrize('transition',['reserve','issue','bind','start','accounting','terminal'])
@pytest.mark.parametrize('edge',['prepare','confirm'])
def test_v16_each_ack_loss_freezes_preserves_last_confirmed_and_blocks_later_effects(tmp_path,transition,edge):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        cap=await C.bootstrap_aggregate(permission);hooks=AggregateHooks(cap,intent)
        async with C.AggregateSession(cap) as s:
            h=permission.history;triggered=[];confirmed=[]
            async def lost(*,expected,replacement):
                pending=replacement['pending'] if edge=='prepare' else expected['pending']
                if pending is not None and pending['transition']==transition:
                    confirmed.append(dict(cap.head));triggered.append(True)
                    await h.compare_exchange(expected=expected,replacement=replacement)
                    raise OSError(ERROR_SECRET)
                return await h.compare_exchange(expected=expected,replacement=replacement)
            permission.history=C.CoordinationHistory(h.identity_sha256,h.mode,h.read,lost)
            try:
                await s.allocate(intent,source);await s.issue(intent,source);await s.start(intent,source,hooks=hooks)
            except C.ControllerError as error:assert ERROR_SECRET not in str(error)
            else:pytest.fail('ACK loss must stop')
            assert triggered and cap.uncertain and cap.head==confirmed[0]
            with pytest.raises(C.ControllerError):await s.allocate(extra_intent(permission,intent),source)
            if transition in {'reserve','issue'}:assert not Path(intent['child_path']).exists()
            if transition in {'reserve','issue','bind','start'}:assert hooks.created==0
            else:assert hooks.created==1
            if transition=='accounting':assert hooks.cleaned==0 and hooks.preserved==1
            history=await h.read()
            if edge=='prepare':assert history['pending'] is not None and history['head']==confirmed[0]
        with pytest.raises(C.ControllerError):await C.reopen_aggregate(permission,expected_binding=cap.binding,expected_head=cap.head)
    asyncio.run(run())


@pytest.mark.parametrize('fault',['header','lock','directory','state-loss','old-state-same-inode','history-loss','history-pending','child-loss'])
def test_v16_loss_drift_and_rollback_never_reset_budget(tmp_path,fault):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        cap=await C.bootstrap_aggregate(permission);old=(permission.path/'state.json').read_bytes()
        async with C.AggregateSession(cap) as s:
            await s.allocate(intent,source)
            if fault=='child-loss':await s.issue(intent,source)
            if fault=='header':(permission.path/'header.json').write_bytes(b'{}')
            elif fault=='lock':(permission.path/'execution.lock').unlink();write(permission.path/'execution.lock',{})
            elif fault=='directory':permission.path.chmod(0o755)
            elif fault=='state-loss':(permission.path/'state.json').unlink()
            elif fault=='old-state-same-inode':(permission.path/'state.json').write_bytes(old)
            elif fault=='history-loss':(tmp_path/'coordination.json').unlink()
            elif fault=='history-pending':
                value=C.decode((tmp_path/'coordination.json').read_bytes());value['pending']={'transition':'uncertain'};write(tmp_path/'coordination.json',value)
            else:
                import shutil
                shutil.rmtree(intent['child_path'])
            with pytest.raises(C.ControllerError):
                if fault=='child-loss':await s.start(intent,source,hooks=AggregateHooks(cap,intent))
                else:await s.allocate(extra_intent(permission,intent),source)
            assert cap.uncertain
        fresh=C.AggregatePermission(permission.path,permission.header,permission.history,permission.verify)
        with pytest.raises(C.ControllerError):await C.bootstrap_aggregate(fresh)
    asyncio.run(run())


def test_v16_integer_limit9_explicit_allocations_flow_and_unintegrated_scope(tmp_path):
    permission,intent,source=aggregate_inputs(tmp_path)
    intents=[intent]+[extra_intent(permission,intent) for _ in range(9)]
    approve_intents(permission,intents)
    async def run():
        cap=await C.bootstrap_aggregate(permission)
        async with C.AggregateSession(cap) as s:
            await s.allocate(intent,source)
            flow=dict(intent,kind='flow',allocation_id=str(uuid4()),reserve_nano=913500000)
            with pytest.raises(C.ControllerError,match='AGGREGATE_LIMIT'):await s.allocate(flow,source)
            with pytest.raises(C.ControllerError):await s.allocate(dict(intent,kind='technical',allocation_id=str(uuid4())),source)
            for value in intents[1:9]:await s.allocate(value,source)
            assert (await s.check())['total_reserved_nano']==950000000
            head=dict(cap.head);await s.allocate(intent,source);assert cap.head==head
            with pytest.raises(C.ControllerError,match='AGGREGATE_LIMIT'):await s.allocate(intents[9],source)
    asyncio.run(run())


@pytest.mark.parametrize('fault',['payload','source','model','price','nonce','path','expiry','unapproved-intent'])
def test_v16_intent_scope_is_strict_and_requires_current_coordinator_authorization(tmp_path,fault):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        cap=await C.bootstrap_aggregate(permission)
        if fault=='payload':intent['template']['requests'][0]['prepare_body']['draft']['original_query']=BODY_SECRET
        elif fault=='source':intent['template']['source']={}
        elif fault=='model':intent['template']['model']='other'
        elif fault=='price':intent['template']['price_sha256']='0'*64
        elif fault=='nonce':intent['nonce']='invalid'
        elif fault=='path':intent['child_path']=str(tmp_path/'unapproved')
        elif fault=='expiry':intent['template']['expires_at']=(C.parse_expiry(permission.header['expires_at'])+timedelta(seconds=1)).isoformat()
        else:intent['allocation_id']=str(uuid4())
        async with C.AggregateSession(cap) as s:
            with pytest.raises(C.ControllerError):await s.allocate(intent,source)
            assert (await s.check())['total_reserved_nano']==50000000
            assert not Path(intent['child_path']).exists()
    asyncio.run(run())


@pytest.mark.parametrize('fault',['cancel','expiry','late-authorization','child-cancel','child-cleanup'])
def test_v16_shutdown_cancellation_late_callbacks_and_failure_never_refund(tmp_path,fault):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        cap=await C.bootstrap_aggregate(permission)
        async with C.AggregateSession(cap) as s:
            await s.allocate(intent,source)
            if fault=='cancel':
                await s.cancel()
                with pytest.raises(C.ControllerError):await s.issue(intent,source)
            elif fault=='expiry':
                class Expired(datetime):
                    @classmethod
                    def now(cls,tz=None):return C.parse_expiry(permission.header['expires_at'])+timedelta(seconds=1)
                with patch.object(C,'datetime',Expired):
                    with pytest.raises(C.ControllerError):await s.issue(intent,source)
            elif fault=='late-authorization':
                old=permission.verify
                async def late(**scope):
                    if scope.get('phase')=='allocation':cap.cancelled=True
                    return await old(**scope)
                permission.verify=late
                with pytest.raises(C.ControllerError):await s.issue(intent,source)
            else:
                await s.issue(intent,source)
                hooks=AggregateHooks(cap,intent,'cancel' if fault=='child-cancel' else 'cleanup')
                expected=asyncio.CancelledError if fault=='child-cancel' else C.ControllerError
                with pytest.raises(expected):await s.start(intent,source,hooks=hooks)
                assert hooks.created==1
            state=C.decode((permission.path/'state.json').read_bytes())
            assert state['total_reserved_nano']==150000000
    asyncio.run(run())


def test_v16_root_lock_concurrency_and_pending_bootstrap_attempt_have_one_winner(tmp_path):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        caps=await asyncio.gather(C.bootstrap_aggregate(permission),C.bootstrap_aggregate(permission),return_exceptions=True)
        assert sum(isinstance(x,C.AggregateCapability) for x in caps)==1
        cap=next(x for x in caps if isinstance(x,C.AggregateCapability))
        async with C.AggregateSession(cap) as s:
            with pytest.raises(C.ControllerError,match='APPROVAL_BUSY'):
                async with C.AggregateSession(cap):pass
            results=await asyncio.gather(s.allocate(intent,source),s.allocate(intent,source))
            assert results[0]==results[1] and (await s.check())['total_reserved_nano']==150000000
            await s.issue(intent,source)
            with pytest.raises(C.ControllerError):await s.issue(intent,source)
    asyncio.run(run())


def test_v16_grant_state_limits_and_sanitized_aggregate_survive_no_call_outcome(tmp_path):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        cap=await C.bootstrap_aggregate(permission)
        async with C.AggregateSession(cap) as s:
            await s.allocate(intent,source);await s.issue(intent,source)
            hooks=AggregateHooks(cap,intent,'setup')
            with pytest.raises(C.ControllerError):await s.start(intent,source,hooks=hooks)
        state=C.decode((permission.path/'state.json').read_bytes())
        assert state['total_reserved_nano']==150000000 and state['frozen']
        assert (permission.path/'state.json').stat().st_size<65536
        assert_sanitized(C.canonical(state))
        assert Path(C.__file__).stat().st_size<=131072
    asyncio.run(run())


@pytest.mark.parametrize('fault',['refund','remove','restore-issue','replace-child','clear-accounting','preconsumed'])
def test_v16_commit_rejects_refund_or_monotonic_rights_and_binding_regression(tmp_path,fault):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        cap=await C.bootstrap_aggregate(permission)
        async with C.AggregateSession(cap) as s:
            await s.allocate(intent,source)
            if fault in {'restore-issue','replace-child','clear-accounting'}:await s.issue(intent,source)
            if fault=='clear-accounting':await s.start(intent,source,hooks=AggregateHooks(cap,intent))
            state=await s.check();head=dict(cap.head);entry=state['allocations'][intent['allocation_id']]
            if fault=='refund':state['total_reserved_nano']=50000000
            elif fault=='remove':state['allocations']={};state['total_reserved_nano']=50000000
            elif fault=='restore-issue':entry['issue_consumed']=False
            elif fault=='replace-child':entry['child']={'replacement':True}
            elif fault=='clear-accounting':entry['accounting']=None
            else:
                new=str(uuid4());state['allocations'][new]=dict(entry,start_consumed=True);state['total_reserved_nano']+=100000000
            with pytest.raises(C.ControllerError):await s.commit(state,'reserve',intent['allocation_id'])
            assert cap.head==head and (await s.check())['total_reserved_nano']==150000000
    asyncio.run(run())


def test_v16_late_parent_ack_cancellation_overrides_prior_first_settlement_failure(tmp_path):
    store,approval,source=inputs(tmp_path);hooks=Hooks('unknown-first')
    async def cancel(_):raise asyncio.CancelledError()
    store._aggregate_ack=cancel
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(C.run_controller(store,approval=approval,key_source=source,synthetic=True,hooks=hooks))
    assert hooks.cleaned==0 and hooks.preserved==1 and store.state['status']=='claimed'


def test_v16_late_terminal_cancellation_overrides_prior_child_failure(tmp_path):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        cap=await C.bootstrap_aggregate(permission);hooks=AggregateHooks(cap,intent,'unknown-first')
        async with C.AggregateSession(cap) as s:
            await s.allocate(intent,source);await s.issue(intent,source)
            original=s.commit
            async def cancel(state,phase,*a,**kw):
                if phase=='terminal':raise asyncio.CancelledError()
                return await original(state,phase,*a,**kw)
            s.commit=cancel
            with pytest.raises(asyncio.CancelledError):await s.start(intent,source,hooks=hooks)
            assert hooks.created==1 and hooks.cleaned==1 and cap.uncertain
            assert C.decode((permission.path/'state.json').read_bytes())['total_reserved_nano']==150000000
    asyncio.run(run())


def test_v16_synthetic_di_passes_exact_two_drafts_and_cannot_dispatch_live(tmp_path):
    permission,intent,source=aggregate_inputs(tmp_path)
    async def run():
        cap=await C.bootstrap_aggregate(permission)
        async with C.AggregateSession(cap) as s:
            await s.allocate(intent,source);await s.issue(intent,source)
            store,_=await s.child(intent,source,initial=True)
            calls=[]
            async def assembly(**scope):
                calls.append(scope)
                return dict(stages=[],meaning_status='supplemented',settlement='observed')
            async def authorized(**_):return True
            approval=C.ExternalApproval(C.digest(intent['template']|dict(state_store=store.scope())),intent['template']['issuer'],authorized)
            hooks=C.AggregateSyntheticHooks(synthetic=True)
            with store.locked(),patch.object(C,'synthetic_preparation_assembly',assembly):
                for index,item in enumerate(intent['template']['requests']):
                    await hooks.verify(store,approval,source,object(),object(),NS(mode='synthetic'),item,index,observation=C.AttemptObservation(index))
                assert [v['body'].model_dump(mode='json') for v in calls]==[v['prepare_body'] for v in intent['template']['requests']]
                assert [v['scenario'] for v in calls]==['success','missing_usage']
                scope=calls[0]
                with pytest.raises(Exception):
                    await scope['authority'].verify(mode='live',agreement=scope['agreement'],key_supplier=scope['deferred'],key_source_capability=scope['deferred'].source_capability)
                with pytest.raises(C.ControllerError,match='LIVE_GATE_CLOSED'):
                    await hooks.verify(store,approval,source,object(),object(),NS(mode='live'),intent['template']['requests'][0],0,observation=C.AttemptObservation(0))
        with pytest.raises(C.ControllerError,match='LIVE_GATE_CLOSED'):
            await C.synthetic_preparation_assembly(body=None,proof=None,principal=None,binding=NS(mode='live'),authority=None,agreement=None,deferred=None,deadline=0,stages=[])
    asyncio.run(run())


@pytest.mark.parametrize('phase',['bootstrap','reserve-pending','issue','start'])
def test_v16_ack_returning_after_expiry_never_opens_next_side_effect(tmp_path,phase):
    permission,intent,source=aggregate_inputs(tmp_path)
    class Clock(datetime):
        expired=False
        @classmethod
        def now(cls,tz=None):return C.parse_expiry(permission.header['expires_at'])+timedelta(seconds=1) if cls.expired else datetime.now(tz)
    async def run():
        if phase=='bootstrap':
            h=permission.history
            async def delayed(**scope):
                result=await h.compare_exchange(**scope)
                if scope['replacement']['phase']=='attempted':Clock.expired=True
                return result
            permission.history=C.CoordinationHistory(h.identity_sha256,h.mode,h.read,delayed)
            with pytest.raises(C.ControllerError):await C.bootstrap_aggregate(permission)
            assert not permission.path.exists()
            return
        cap=await C.bootstrap_aggregate(permission);hooks=AggregateHooks(cap,intent)
        async with C.AggregateSession(cap) as s:
            if phase=='reserve-pending':
                h=permission.history
                async def delayed(**scope):
                    result=await h.compare_exchange(**scope)
                    if scope['replacement']['pending'] is not None:Clock.expired=True
                    return result
                permission.history=C.CoordinationHistory(h.identity_sha256,h.mode,h.read,delayed)
                with pytest.raises(C.ControllerError):await s.allocate(intent,source)
                assert cap.uncertain and C.decode((permission.path/'state.json').read_bytes())['total_reserved_nano']==50000000
            else:
                await s.allocate(intent,source)
                if phase=='start':await s.issue(intent,source)
                original=s.commit
                async def delayed(state,transition,*a,**kw):
                    await original(state,transition,*a,**kw)
                    if transition==phase:Clock.expired=True
                s.commit=delayed
                with pytest.raises(C.ControllerError):
                    if phase=='issue':await s.issue(intent,source)
                    else:await s.start(intent,source,hooks=hooks)
                assert hooks.created==0
            if phase!='start':assert not Path(intent['child_path']).exists()
    with patch.object(C,'datetime',Clock):asyncio.run(run())


@pytest.mark.parametrize('phase',['direct','issue','start'])
def test_v16_final_history_read_delay_rechecks_expiry_before_return_or_effect(tmp_path,phase):
    permission,intent,source=aggregate_inputs(tmp_path)
    class Clock(datetime):
        expired=False
        @classmethod
        def now(cls,tz=None):return C.parse_expiry(permission.header['expires_at'])+timedelta(seconds=1) if cls.expired else datetime.now(tz)
    async def run():
        cap=await C.bootstrap_aggregate(permission)
        async with C.AggregateSession(cap) as s:
            if phase!='direct':await s.allocate(intent,source)
            if phase=='start':await s.issue(intent,source)
            h=permission.history;armed=phase=='direct';reads=[];runners=[]
            async def delayed_read():
                value=await h.read()
                if armed:
                    await asyncio.sleep(0)
                    reads.append(True);Clock.expired=True
                return value
            permission.history=C.CoordinationHistory(h.identity_sha256,h.mode,delayed_read,h.compare_exchange)
            original=s.commit
            async def commit(state,transition,*a,**kw):
                nonlocal armed
                await original(state,transition,*a,**kw)
                if transition==phase:armed=True
            s.commit=commit
            async def runner(*a,**kw):runners.append(True);return {}
            with patch.object(C,'run_controller',runner):
                with pytest.raises(C.ControllerError,match='AGGREGATE_EXPIRED'):
                    if phase=='direct':await s.check()
                    elif phase=='issue':await s.issue(intent,source)
                    else:await s.start(intent,source)
            assert reads==[True] and runners==[]
            if phase=='issue':assert not Path(intent['child_path']).exists()
            state=C.decode((permission.path/'state.json').read_bytes())
            assert state['total_reserved_nano']==(50000000 if phase=='direct' else 150000000)
            if phase=='start':assert state['allocations'][intent['allocation_id']]['start_consumed']
            # Expiry closes new effects, while identity-valid cleanup remains possible.
            if phase=='direct':assert (await s.check(cleanup=True))['total_reserved_nano']==50000000
    with patch.object(C,'datetime',Clock):asyncio.run(run())


def test_v16_synthetic_replays_after_real_live_shutdown_without_live_extension(tmp_path):
    class Future(datetime):
        @classmethod
        def now(cls,tz=None):return C.AGGREGATE_END+timedelta(days=366)
    async def run():
        permission,intent,source=aggregate_inputs(tmp_path)
        assert C.parse_expiry(permission.header['expires_at'])>C.AGGREGATE_END
        assert C.aggregate_deadline(permission.header)==C.parse_expiry(permission.header['expires_at'])
        cap=await C.bootstrap_aggregate(permission)
        async with C.AggregateSession(cap) as s:
            await s.allocate(intent,source);await s.issue(intent,source)
            hooks=AggregateHooks(cap,intent)
            await s.start(intent,source,hooks=hooks)
            assert hooks.created==1 and hooks.cleaned==1
            assert (await s.check())['total_reserved_nano']==150000000
        # A synthetic receipt does not become a live approval by changing mode.
        permission.header['mode']='live'
        with pytest.raises(C.ControllerError):await C.bootstrap_aggregate(C.AggregatePermission(permission.path,permission.header,permission.history,permission.verify))
    with patch.object(C,'datetime',Future):asyncio.run(run())


def test_v16_live_deadline_stays_fixed_and_expired_after_shutdown(tmp_path):
    permission,intent,source=aggregate_inputs(tmp_path)
    h=permission.header;h['mode']='live'
    h['not_before']=(C.AGGREGATE_END-timedelta(minutes=10)).isoformat();h['expires_at']=C.AGGREGATE_END.isoformat()
    old=permission.history;permission.history=C.CoordinationHistory(old.identity_sha256,'live',old.read,old.compare_exchange)
    code_root=tmp_path/'verith-supervisor-live-controller'
    permission.code_root=C.ReviewedCodeRoot(code_root,(),h['runtime_sha256'])
    permission.path=code_root.parent/'.cf026-openai-test-budget'/h['approval_event']
    class Future(datetime):
        @classmethod
        def now(cls,tz=None):return C.AGGREGATE_END+timedelta(days=366)
    async def run():
        with patch.object(C.ReviewedCodeRoot,'check',lambda _:None):
            with pytest.raises(C.ControllerError,match='AGGREGATE_SCOPE'):await C.aggregate_authorized(permission)
            h['expires_at']=(C.AGGREGATE_END+timedelta(seconds=1)).isoformat()
            with pytest.raises(C.ControllerError,match='AGGREGATE_SCOPE'):C.aggregate_header(permission)
        assert not permission.path.exists()
    with patch.object(C,'datetime',Future):asyncio.run(run())


@pytest.mark.parametrize('case', ['before', 'start', 'end', 'late-approval', 'early-window', 'late-window', 'old-window', 'naive'])
def test_v18_fixed_live_window_is_closed_and_rechecked_after_authority(tmp_path, case):
    permission, _, _ = aggregate_inputs(tmp_path)
    start, end = C.AGGREGATE_WINDOW
    h = permission.header
    h.update(mode='live', not_before=start.isoformat(), expires_at=end.isoformat())
    history = permission.history
    permission.history = C.CoordinationHistory(history.identity_sha256, 'live', history.read, history.compare_exchange)
    code_root = tmp_path / 'verith-supervisor-live-controller'
    permission.code_root = C.ReviewedCodeRoot(code_root, (), h['runtime_sha256'])
    permission.path = code_root.parent / '.cf026-openai-test-budget' / h['approval_event']
    calls = []
    class Clock(datetime):
        current = start
        @classmethod
        def now(cls, tz=None):
            return cls.current
    async def approve(**scope):
        calls.append(scope)
        await asyncio.sleep(0)
        if case == 'late-approval':
            Clock.current = end
        return True
    permission.verify = approve
    if case == 'before':
        Clock.current = start - timedelta(microseconds=1)
    elif case == 'end':
        Clock.current = end
    elif case == 'early-window':
        h['not_before'] = (start - timedelta(microseconds=1)).isoformat()
    elif case == 'late-window':
        h['expires_at'] = (end + timedelta(seconds=1)).isoformat()
    elif case == 'old-window':
        h.update(not_before=(C.AGGREGATE_END-timedelta(minutes=1)).isoformat(), expires_at=C.AGGREGATE_END.isoformat())
    elif case == 'naive':
        h['not_before'] = start.replace(tzinfo=None).isoformat()
    async def run():
        with patch.object(C.ReviewedCodeRoot, 'check', lambda _: None):
            if case == 'start':
                assert await C.aggregate_authorized(permission) == h
                assert len(calls) == 1
            else:
                with pytest.raises(C.ControllerError):
                    await C.aggregate_authorized(permission)
                assert len(calls) == (1 if case == 'late-approval' else 0)
        assert not permission.path.exists()
    with patch.object(C, 'datetime', Clock):
        asyncio.run(run())


# Preparation-only contract prototype: never imported by a runtime entry.
def successor_plan_prototype(parent, proposal, *, expected_proofs, expected_requests, expected_namespace):
    """Test-only contract calculation; never verifies files or issues authority."""
    proof_names = {
        "original_root", "aggregate_header", "aggregate_state", "child_grant",
        "closure", "accounting", "execution_source", "execution_runtime", "carry",
    }
    parent_fields = {
        "proofs", "terminal", "cause", "frozen", "child_state", "issue_consumed",
        "start_consumed", "cleanup_confirmed", "reserved_nano", "limit_nano",
        "count_reserved", "generation_reserved", "http", "estimated_nano",
        "namespace_sha256", "history_scope", "attempts_reserved",
        "original_carry_reserved_nano", "closed_allocation_reserved_nano",
        "original_carry_count_reserved", "original_carry_http",
        "current_count_cap", "current_generation_cap", "current_attempt_cap",
    }
    if type(parent) is not dict or set(parent) != parent_fields:
        raise ValueError("PREDECESSOR_REQUIRED")
    if type(expected_proofs) is not dict or set(expected_proofs) != proof_names:
        raise ValueError("EXPECTED_WITNESS_REQUIRED")
    if type(expected_namespace) is not str or C.re.fullmatch(r"[a-f0-9]{64}", expected_namespace) is None:
        raise ValueError("EXPECTED_NAMESPACE_REQUIRED")
    if parent["namespace_sha256"] != expected_namespace or parent["history_scope"] != "current_v18_batch":
        raise ValueError("HISTORY_SCOPE")
    proofs = parent["proofs"]
    if type(proofs) is not dict or set(proofs) != proof_names or any(
        type(value) is not str or C.re.fullmatch(r"[a-f0-9]{64}", value) is None
        for value in expected_proofs.values()
    ) or proofs != expected_proofs:
        raise ValueError("PREDECESSOR_DRIFT")
    if parent["terminal"] != "FIRST_SETTLEMENT_UNCONFIRMED" or parent["cause"] != "KEY_SOURCE_INVALID":
        raise ValueError("PREDECESSOR_TERMINAL")
    if any(parent[key] is not True for key in (
        "frozen", "issue_consumed", "start_consumed", "cleanup_confirmed",
    )) or parent["child_state"] != "closed":
        raise ValueError("PREDECESSOR_UNCONFIRMED")
    for key, value in {
        "reserved_nano": 150000000, "limit_nano": 1000000000,
        "count_reserved": 1, "generation_reserved": 0, "attempts_reserved": 1,
        "original_carry_reserved_nano": 50000000,
        "closed_allocation_reserved_nano": 100000000,
        "original_carry_count_reserved": 1, "current_count_cap": 2,
        "current_generation_cap": 2, "current_attempt_cap": 2,
    }.items():
        if type(parent[key]) is not int or parent[key] != value:
            raise ValueError("PREDECESSOR_ACCOUNTING")
    if parent["http"] != "unknown" or parent["original_carry_http"] != "unknown" or parent["estimated_nano"] is not None:
        raise ValueError("UNOBSERVED_NOT_ZERO")
    fixed = {
        "model": "gpt-5.4-mini-2026-03-17", "tier": "default",
        "question_index": 0, "spec_sha256": MEANING_SPEC_SHA256,
        "price_sha256": C.digest(MEANING_SPEC["price"]),
        "origin": "https://api.openai.com",
        "endpoints": ["/v1/responses/input_tokens", "/v1/responses"],
        "source_relative": "verith/ai/.env", "input_cap": 16384,
        "output_cap": 2048, "count_cap": 1, "generation_cap": 1,
        "http_cap": 2, "retry_cap": 0, "reserve_nano": 50000000,
    }
    if type(proposal) is not dict or set(proposal) != set(fixed) | {"requests"}:
        raise ValueError("PROPOSAL_SCOPE")
    if any(type(proposal[key]) is not type(value) or proposal[key] != value for key, value in fixed.items()):
        raise ValueError("PROPOSAL_SCOPE")
    request_fields = {"draft_sha256", "request_sha256", "projection_sha256"}
    if type(expected_requests) is not list or len(expected_requests) != 2 or any(
        type(item) is not dict or set(item) != request_fields or any(
            type(value) is not str or C.re.fullmatch(r"[a-f0-9]{64}", value) is None
            for value in item.values()
        ) for item in expected_requests
    ) or proposal["requests"] != expected_requests[:1]:
        raise ValueError("REQUEST_BINDING")
    planned_reserved = parent["reserved_nano"] + proposal["reserve_nano"]
    return MappingProxyType({
        "schema": "cf026.successor.plan-only.v1", "execution_authorized": False,
        "preserved_reserved_nano": parent["reserved_nano"],
        "proposed_reserved_nano": proposal["reserve_nano"],
        "planned_total_nano": planned_reserved,
        "remaining_nano": parent["limit_nano"] - planned_reserved,
        "predecessor_count_reservations": parent["count_reserved"],
        "predecessor_generation_reservations": parent["generation_reserved"],
        "http": "unknown", "estimated_nano": None,
        "proposed_batch_count_cap": 1, "proposed_batch_generation_cap": 1,
        "proposed_batch_http_cap": 2, "new_source_bound": False,
        "explicit_reverification_required": True,
        "planned_current_batch_count": parent["count_reserved"] + 1,
        "planned_current_batch_attempts": parent["attempts_reserved"] + 1,
        "namespace_sha256": expected_namespace,
        "predecessor_proofs_sha256": C.digest(proofs),
        "first_request": tuple(sorted(expected_requests[0].items())),
        "blocked_by": ("EXPLICIT_FIRST_REQUEST_REVERIFICATION_AND_NEW_WINDOW_REQUIRED",
                       "INDEPENDENT_SINGLE_USE_WITNESS_REQUIRED",
                       "BOUND_AI_SOURCE_AND_EXECUTOR_REQUIRED"),
    })



def successor_contract_inputs():
    """Self-owned projections; these hashes are not real execution evidence."""
    names = ["original_root", "aggregate_header", "aggregate_state", "child_grant",
             "closure", "accounting", "execution_source", "execution_runtime", "carry"]
    proofs = {name: C.digest({"synthetic_only": name}) for name in names}
    drafts = [
        M.Draft(original_query="현대건설 외국인 말고 3주 수급", answers=[], revision=0),
        M.Draft(original_query="현대건설 어제 말고 외국인 말고 기관 수급", answers=[
            {"answer_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "slot": "views", "value": "수급만"},
        ], revision=1),
    ]
    requests = [{key: item[key] for key in (
        "draft_sha256", "request_sha256", "projection_sha256",
    )} for item in C.synthetic_requests(drafts)]
    parent = dict(
        proofs=proofs.copy(), terminal="FIRST_SETTLEMENT_UNCONFIRMED",
        cause="KEY_SOURCE_INVALID", frozen=True, child_state="closed",
        issue_consumed=True, start_consumed=True, cleanup_confirmed=True,
        reserved_nano=150000000, limit_nano=1000000000, count_reserved=1,
        generation_reserved=0, http="unknown", estimated_nano=None,
        namespace_sha256=C.digest({"synthetic_only": "canonical_namespace"}),
        history_scope="current_v18_batch", attempts_reserved=1,
        original_carry_reserved_nano=50000000, closed_allocation_reserved_nano=100000000,
        original_carry_count_reserved=1, original_carry_http="unknown",
        current_count_cap=2, current_generation_cap=2, current_attempt_cap=2,
    )
    proposal = dict(
        requests=[requests[0].copy()], model="gpt-5.4-mini-2026-03-17",
        tier="default", origin="https://api.openai.com", question_index=0,
        spec_sha256=MEANING_SPEC_SHA256, price_sha256=C.digest(MEANING_SPEC["price"]),
        endpoints=["/v1/responses/input_tokens", "/v1/responses"],
        source_relative="verith/ai/.env", input_cap=16384, output_cap=2048,
        count_cap=1, generation_cap=1, http_cap=2, retry_cap=0, reserve_nano=50000000,
    )
    return parent, proposal, proofs, requests


def test_successor_contract_plan_preserves_accounting_without_grant_or_io():
    parent, proposal, proofs, requests = successor_contract_inputs()
    before = C.canonical([parent, proposal, proofs, requests])
    with patch.object(C, "read_fixed", side_effect=AssertionError("No file reads")), patch.object(
        C, "exclusive_private_file", side_effect=AssertionError("No issuance"),
    ), patch.object(C.OwnedHooks, "create", side_effect=AssertionError("No resource")):
        result = successor_plan_prototype(
            parent, proposal, expected_proofs=proofs, expected_requests=requests,
            expected_namespace=C.digest({"synthetic_only": "canonical_namespace"}),
        )
    again = successor_plan_prototype(
        parent, proposal, expected_proofs=proofs, expected_requests=requests,
        expected_namespace=C.digest({"synthetic_only": "canonical_namespace"}),
    )
    assert result == again
    with pytest.raises(TypeError):
        result["execution_authorized"] = True
    with pytest.raises(TypeError):
        result["blocked_by"][0] = "ready"
    with pytest.raises(TypeError):
        result["first_request"][0][1] = "altered"
    assert result["execution_authorized"] is False
    assert result["new_source_bound"] is False
    assert result["preserved_reserved_nano"] == 150000000
    assert result["proposed_reserved_nano"] == 50000000
    assert result["planned_total_nano"] == 200000000
    assert result["remaining_nano"] == 800000000
    assert result["http"] == "unknown" and result["estimated_nano"] is None
    assert result["predecessor_count_reservations"] == 1
    assert result["proposed_batch_count_cap"] == 1
    assert result["planned_current_batch_count"] == 2
    assert result["planned_current_batch_attempts"] == 2
    assert result["explicit_reverification_required"] is True
    assert len(result["blocked_by"]) == 3
    assert C.canonical([parent, proposal, proofs, requests]) == before
    with pytest.raises(C.ControllerError):
        C.validate_scope(result, None, synthetic=False)


@pytest.mark.parametrize("fault", [
    "missing-parent", "missing-proof", "altered-proof", "missing-witness",
    "malformed-witness", "terminal", "cause", "not-frozen", "child-running",
    "issue-unconsumed", "start-unconsumed", "cleanup-unconfirmed", "under-carry",
    "double-carry", "refund", "new-limit", "count-refund", "unknown-count",
    "generation-bool", "http-zero", "usage-zero", "questions", "request-drift",
    "projection-drift", "draft-drift", "missing-expected-request", "model", "tier",
    "origin", "endpoints", "input-cap", "output-cap", "count-cap", "generation-cap",
    "http-cap", "retry", "reserve", "backend-source", "frontend-source",
    "other-worktree-source", "execution-flag", "namespace", "missing-namespace",
    "carry-history-scope", "attempt-refund", "attempt-unknown", "carry-count-refund",
    "carry-refund", "allocation-refund", "current-count-cap", "current-generation-cap",
    "current-attempt-cap", "second-index", "spec", "price", "two-questions",
])
def test_successor_contract_rejects_unbound_or_expanded_proposal(fault):
    parent, proposal, proofs, requests = successor_contract_inputs()
    expected_namespace = C.digest({"synthetic_only": "canonical_namespace"})
    if fault == "missing-parent": parent = None
    elif fault == "missing-proof": parent["proofs"].pop("closure")
    elif fault == "altered-proof": parent["proofs"]["aggregate_state"] = "f" * 64
    elif fault == "missing-witness": proofs = None
    elif fault == "malformed-witness": proofs["closure"] = "untrusted"
    elif fault == "questions": proposal["requests"] = [requests[1].copy()]
    elif fault == "two-questions": proposal["requests"] = requests
    elif fault == "missing-namespace": expected_namespace = None
    elif fault in {"request-drift", "projection-drift", "draft-drift"}:
        field = {"request-drift": "request_sha256", "projection-drift": "projection_sha256", "draft-drift": "draft_sha256"}[fault]
        proposal["requests"][0][field] = "f" * 64
    elif fault == "missing-expected-request": requests = []
    else:
        changes = {
            "terminal": (parent, "terminal", "KEY_SOURCE_INVALID"),
            "cause": (parent, "cause", "CONTROLLER_FAILED"),
            "not-frozen": (parent, "frozen", False),
            "child-running": (parent, "child_state", "claimed"),
            "issue-unconsumed": (parent, "issue_consumed", False),
            "start-unconsumed": (parent, "start_consumed", False),
            "cleanup-unconfirmed": (parent, "cleanup_confirmed", False),
            "under-carry": (parent, "reserved_nano", 50000000),
            "double-carry": (parent, "reserved_nano", 200000000),
            "refund": (parent, "reserved_nano", 0),
            "new-limit": (parent, "limit_nano", 2000000000),
            "count-refund": (parent, "count_reserved", 0),
            "unknown-count": (parent, "count_reserved", None),
            "generation-bool": (parent, "generation_reserved", False),
            "http-zero": (parent, "http", 0),
            "usage-zero": (parent, "estimated_nano", 0),
            "model": (proposal, "model", "other-model"),
            "tier": (proposal, "tier", "auto"),
            "origin": (proposal, "origin", "https://other.invalid"),
            "endpoints": (proposal, "endpoints", ["/v1/responses"]),
            "input-cap": (proposal, "input_cap", 16385),
            "output-cap": (proposal, "output_cap", 2049),
            "count-cap": (proposal, "count_cap", 3),
            "generation-cap": (proposal, "generation_cap", 3),
            "http-cap": (proposal, "http_cap", 5),
            "retry": (proposal, "retry_cap", 1),
            "reserve": (proposal, "reserve_nano", 100000000),
            "backend-source": (proposal, "source_relative", "verith/backend/.env"),
            "frontend-source": (proposal, "source_relative", "verith/frontend/.env"),
            "other-worktree-source": (proposal, "source_relative", "other/ai/.env"),
            "execution-flag": (proposal, "execution_authorized", True),
            "namespace": (parent, "namespace_sha256", "f" * 64),
            "carry-history-scope": (parent, "history_scope", "original_carry"),
            "attempt-refund": (parent, "attempts_reserved", 0),
            "attempt-unknown": (parent, "attempts_reserved", None),
            "carry-count-refund": (parent, "original_carry_count_reserved", 0),
            "carry-refund": (parent, "original_carry_reserved_nano", 0),
            "allocation-refund": (parent, "closed_allocation_reserved_nano", 0),
            "current-count-cap": (parent, "current_count_cap", 3),
            "current-generation-cap": (parent, "current_generation_cap", 3),
            "current-attempt-cap": (parent, "current_attempt_cap", 3),
            "second-index": (proposal, "question_index", 1),
            "spec": (proposal, "spec_sha256", "f" * 64),
            "price": (proposal, "price_sha256", "f" * 64),
        }
        target, key, value = changes[fault]
        target[key] = value
    with pytest.raises(ValueError) as caught:
        successor_plan_prototype(
            parent, proposal, expected_proofs=proofs, expected_requests=requests,
            expected_namespace=expected_namespace,
        )
    assert str(caught.value) in {
        "PREDECESSOR_REQUIRED", "EXPECTED_WITNESS_REQUIRED", "PREDECESSOR_DRIFT",
        "EXPECTED_NAMESPACE_REQUIRED", "HISTORY_SCOPE",
        "PREDECESSOR_TERMINAL", "PREDECESSOR_UNCONFIRMED", "PREDECESSOR_ACCOUNTING",
        "UNOBSERVED_NOT_ZERO", "PROPOSAL_SCOPE", "REQUEST_BINDING",
    }


from scripts import cf026_successor as S


class SuccessorClock:
    def __init__(self):
        self.now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.elapsed = 100.0

    def wall(self):
        return self.now

    def mono(self):
        return self.elapsed

    def advance(self, seconds, *, wall=True, mono=True):
        if wall:
            self.now += timedelta(seconds=seconds)
        if mono:
            self.elapsed += seconds


class SuccessorWitness:
    """Synthetic durable authority stand-in, not the actual external adapter."""
    def __init__(self, clock):
        self.clock = clock
        self.identity = C.digest({"synthetic_witness": True})
        self.once = None
        self.sequence = 0
        self.issued = None
        self.ack = None
        self.fail = None
        self.advance = None
        self.calls = []
        self.revoked = False

    async def verify(self, **args):
        self.calls.append(args["phase"])
        if self.revoked or args["phase"] == "admission" and self.once is not None:
            return False
        return True

    async def consume(self, **args):
        phase = args["phase"]
        if self.revoked or phase == "reserve" and self.once is not None:
            raise S.Closed("ALREADY_USED")
        if phase == "reserve":
            self.once = args["successor_once"]
            self.issued = self.clock.wall().isoformat()
        elif self.once != args["successor_once"]:
            raise S.Closed("AUTHORITY_UNAVAILABLE")
        self.sequence += 1
        self.calls.append(phase)
        self.ack = args | dict(authority_sha256=self.identity, sequence=self.sequence,
                               issued_at=self.issued, consumed=True)
        if self.advance == phase:
            self.clock.advance(601)
        if self.fail == phase:
            raise OSError(PRIVATE)
        if self.fail == phase + "-cancel":
            raise asyncio.CancelledError()
        return self.ack.copy()

    async def readback(self, **args):
        if self.fail == args["phase"] + "-readback":
            return {"approved": True}
        return self.ack.copy()

    def capability(self):
        return S.Authority("synthetic", self.identity, self.verify, self.consume, self.readback)


def successor_assembly_inputs(tmp_path, *, historical=False):
    base = tmp_path.resolve()
    base.chmod(0o700)
    clock = SuccessorClock()
    source_file = base / "synthetic-input.txt"
    write(source_file, b"OPENAI_API_KEY=cf026-synthetic-unused\n", 0o644)
    source = C.KeySource(source_file, C.regular(source_file, 0o644), True)
    witness = SuccessorWitness(clock)
    event, child_id = "SyntheticApproval", str(uuid4())
    root = base / ".cf026-openai-test-budget" / event
    runtime_home = base / ".cf026-launcher-preparation-20261110"
    bootstrap = "b" * 64
    root.mkdir(parents=True, mode=0o700)
    write(root / "execution.lock", {})
    runtime_home.mkdir(mode=0o700)
    child_dir = root / "children" / child_id
    child_dir.mkdir(parents=True, mode=0o700)
    (root / "children").chmod(0o700)
    carry = base / ".cf026-live-approval" / "HistoricalApproval"
    carry.mkdir(parents=True, mode=0o700)
    artifacts = []

    def artifact(name, path, value):
        write(path, value)
        raw = path.read_bytes()
        item = S.Artifact(name, path, C.canonical(C.regular(path, 0o600)), C.hashlib.sha256(raw).hexdigest())
        artifacts.append(item)
        return item.sha256

    carry_id = str(uuid4())
    carry_grant = artifact("carry_grant", carry / "grant.json", dict(approval_id=carry_id))
    carry_state = artifact("carry_state", carry / "state.json", dict(status="closed", approval_id=carry_id, grant_sha256=carry_grant))
    carry_closure = artifact("carry_closure", carry / "failure.json", dict(status="failed"))
    drafts = [M.Draft(original_query="현대건설 외국인 말고 3주 수급", answers=[], revision=0),
              M.Draft(original_query="현대건설 어제 말고 외국인 말고 기관 수급", answers=[
                  {"answer_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "slot": "views", "value": "수급만"}], revision=1)]
    requests = C.synthetic_requests(drafts)
    historical_source = dict(identity={"synthetic_original": True}, code_root={"controller_sha256": "d" * 64})
    grant = dict(approval_id=child_id, requests=requests, source=historical_source,
                 semantic_sha256=C.digest(MEANING_SPEC | {"caps": MEANING_SPEC["caps"] | {"provider_seconds": 5}}) if historical else MEANING_SPEC_SHA256,
                 price_sha256=C.digest(MEANING_SPEC["price"]))
    grant_sha = artifact("child_grant", child_dir / "grant.json", grant)
    diagnostic = dict(failure_code="KEY_SOURCE_INVALID", count_http="unknown")
    old_ledger = dict(count=1, generation=0, reserved=50000000, blocked=True)
    child = dict(status="closed", approval_id=child_id, grant_sha256=grant_sha, journal=[
        dict(phase="final_accounting", observation="fresh_ledger", state=old_ledger, diagnostics=[diagnostic]),
        dict(phase="closing"), dict(phase="cleanup_confirmed")])
    artifact("child_state", child_dir / "state.json", child)
    header = dict(schema="cf026.aggregate.v1", approval_event=event, bootstrap_id=bootstrap,
                  limit_nano=1000000000, carry_nano=50000000,
                  carry_hashes=dict(grant=carry_grant, state=carry_state, closure=carry_closure))
    artifact("header", root / "header.json", header)
    outcome = dict(code="FIRST_SETTLEMENT_UNCONFIRMED", cleanup_confirmed=True, estimated_nano=None, http="unknown",
                   accounting_sha256=C.digest(child["journal"][0]), count_requests=1, generation_requests=0)
    allocation = dict(reserve_nano=100000000, issue_consumed=True, start_consumed=True,
                      child_id=child_id, child=dict(grant_bytes_sha256=grant_sha), outcome=outcome,
                      accounting=dict(sha256=C.digest(child["journal"][0]), count=1, generation=0, http="unknown"))
    state_sha = artifact("state", root / "state.json", dict(schema="cf026.aggregate.state.v1", frozen=True,
             total_reserved_nano=150000000, sequence=6, allocations={str(uuid4()): allocation}))
    coordination = base / ".cf026-live-coordination" / event
    coordination.mkdir(parents=True, mode=0o700)
    write(coordination / "lock", {})
    history = dict(bootstrap_id=bootstrap, root=str(root), phase="initialized", pending=None,
                   header_sha256=next(a.sha256 for a in artifacts if a.name == "header"),
                   binding=dict(header_sha256=next(a.sha256 for a in artifacts if a.name == "header"),
                                directory=C.directory_identity(root), children=C.directory_identity(root/"children"),
                                lock=C.regular(root/"execution.lock", 0o600), header=C.regular(root/"header.json", 0o600)),
                   head=dict(sha256=state_sha, sequence=6, identity=C.regular(root/"state.json", 0o600)))
    artifact("coordination", coordination / "state.json", history)
    artifact("closure", runtime_home / ("outcome-" + bootstrap + ".json"), dict(status="closed", journal_uncertain=False, adapter_uncertain=False,
              adapter_pin=dict(digest=C.digest(history), directory=C.directory_identity(coordination)[:3]+[0o700],
                               lock=[C.regular(coordination/"lock", 0o600)[k] for k in ("dev","ino","uid","mode","nlink","size","mtime_ns")],
                               state=[C.regular(coordination/"state.json", 0o600)[k] for k in ("dev","ino","uid","mode","nlink","size","mtime_ns")])))
    old_carry = {a.name: dict(path=str(a.path), sha256=a.sha256) for a in artifacts if a.name.startswith("carry_")}
    artifact("runtime", runtime_home / "reviewed-runtime.json", dict(key_metadata=historical_source["identity"],
             source_manifest={"backend/scripts/cf026_supervisor_live_controller.py": "d" * 64}, old_carry=old_carry))
    journal_path = base / "successor-local-journal"
    journal_path.mkdir(mode=0o700)
    write(journal_path / "execution.lock", {})
    lock = C.regular(journal_path / "execution.lock", 0o600)
    pins = {a.name: a.sha256 for a in artifacts}
    document = dict(schema="cf026.successor.scope.v1", mode="synthetic", namespace=C.digest(event),
        predecessor_sha256=C.digest(pins), predecessor_bootstrap=bootstrap, invocation="a" * 64, consent_at=(clock.wall()-timedelta(seconds=1)).isoformat(),
        predecessor=dict(reserved_nano=150000000, carry_nano=50000000, allocation_nano=100000000,
                         count=1, generation=0, attempts=1, http="unknown", estimated_nano=None),
        artifacts=pins, request=requests[0], source=source.scope(), counter=dict(documentation_url=O.COUNT_DOCUMENTATION,
        documentation_sha256="a"*64, free_evidence_sha256="b"*64, price_evidence_sha256="c"*64, fee_bound_nano=0),
        semantic_sha256=MEANING_SPEC_SHA256, price_sha256=C.digest(MEANING_SPEC["price"]), epoch_id=str(uuid4()),
        authority_sha256=witness.identity, module_sha256=C.hashlib.sha256(Path(S.__file__).read_bytes()).hexdigest(),
        journal=dict(path=str(journal_path), directory=C.directory_identity(journal_path), lock=lock))
    scope = S.Scope(C.canonical(document), tuple(artifacts))
    state = dict(schema="cf026.successor.journal.v1", scope_sha256=scope.sha256,
                 status="offered", rights=dict(count=0, generation=0), preparation=None, journal=[])
    write(journal_path / "state.json", state)
    pin = dict(identity=C.regular(journal_path / "state.json", 0o600), sha256=C.hashlib.sha256((journal_path / "state.json").read_bytes()).hexdigest())
    journal = S.Journal(journal_path, pin, lock, scope.sha256)
    return scope, source, witness, journal, clock


class SuccessorHooks:
    def __init__(self):
        self.driver = NS(call=lambda *a, **kwargs: None)
        self.created = self.cleaned = self.preserved = 0
        self.proof, self.principal = object(), object()
        self.binding = NS(epoch_id=uuid4())
        self.snapshot_value = None

    def create(self):
        self.created += 1

    async def bootstrap(self, store):
        return self.proof, self.principal, self.binding

    async def snapshot(self, *_):
        return self.snapshot_value

    def cleanup(self):
        self.cleaned += 1

    def preserve(self):
        self.preserved += 1


async def successor_verifier_spy(*, proof, binding, principal, prepare_body, authority, counter_agreement, key_supplier):
    """Exercises actual new DI/phase/supplier functions, not actual PG or ASGI."""
    d = authority.session.scope.data
    assert prepare_body == d["request"]["prepare_body"]
    assert key_supplier.source_capability is authority.session.source
    async def fresh(self):
        self.store.reload()
        if self.store.state["preparation"] is None:
            self.store.persist("claimed", dict(phase="preparation_binding_ACK"), preparation={"synthetic_only": True})
        return dict(count=self.store.state["rights"]["count"], generation=0,
                    reserved=self.store.state["rights"]["count"] * 50000000)
    args = dict(mode="synthetic", proof_binding=binding, principal=principal, agreement=counter_agreement,
                key_supplier=key_supplier, key_source_capability=key_supplier.source_capability,
                draft_sha256=d["request"]["draft_sha256"], semantic_sha256=d["semantic_sha256"])
    with patch.object(S.PhaseAuthority, "fresh_preparation", fresh):
        await authority.verify(phase="initial", **args)
        args.update(request_sha256=d["request"]["request_sha256"], projection_sha256=d["request"]["projection_sha256"])
        await authority.verify(phase="preflight", **args)
        await authority.verify(phase="count", **args)
        assert await key_supplier.supplier() == "cf026-synthetic-unused"
        await authority.verify(phase="generation", **args)
    return dict(stages=["preflight_verified", "count_reservation_ACK", "generation_reservation_ACK", "settlement_ACK"],
                meaning_status="supplemented", settlement="observed")


def test_successor_actual_helper_di_journal_and_replay(tmp_path, capsys):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    before = {a.path: a.path.read_bytes() for a in scope.artifacts}
    hooks = SuccessorHooks()
    item = scope.data["request"]
    hooks.snapshot_value = dict(count=1, generation=1, reserved=50000000, blocked=False, active=None,
        attempts={str(uuid4()): dict(request_sha256=item["request_sha256"], projection_sha256=item["projection_sha256"],
                                   observation=dict(state="observed", estimated_nano=120000))})
    with patch.object(V, "verify_live", successor_verifier_spy):
        result = asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                                  synthetic=True, hooks=hooks, clock=clock))
    assert result["status"] == "finished" and result["total_reserved_nano"] == 200000000
    assert hooks.created == hooks.cleaned == 1 and hooks.preserved == 0
    assert journal.state["status"] == "closed" and journal.state["rights"] == dict(count=1, generation=1)
    assert [x for x in witness.calls if x in {"reserve", "issue", "start", "count", "generation", "accounting"}] == ["reserve", "issue", "start", "count", "generation", "accounting"]
    assert before == {a.path: a.path.read_bytes() for a in scope.artifacts}
    with pytest.raises(S.Closed):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    assert hooks.created == 1
    assert PRIVATE not in capsys.readouterr().out


@pytest.mark.parametrize("phase", ["reserve", "issue", "start", "reserve-readback", "issue-readback", "start-readback"])
def test_successor_authority_ack_loss_never_starts_resource(tmp_path, phase):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    witness.fail = phase
    hooks = SuccessorHooks()
    with pytest.raises(S.Closed):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    assert hooks.created == 0 and witness.once is not None


@pytest.mark.parametrize("phase", ["reserve", "issue", "start"])
def test_successor_delayed_ack_expiry_is_fail_closed(tmp_path, phase):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    witness.advance = phase
    hooks = SuccessorHooks()
    with pytest.raises(S.Closed):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    assert hooks.created == 0


@pytest.mark.parametrize("wall,mono", [(True, False), (False, True), (True, True)])
def test_successor_start_120s_and_expiry_600s_both_clocks(wall, mono):
    clock = SuccessorClock()
    lease = S.Lease(clock.wall().isoformat(), (clock.wall()-timedelta(seconds=1)).isoformat(), clock)
    clock.advance(120.001, wall=wall, mono=mono)
    with pytest.raises(S.Closed):
        lease.check(starting=True)
    lease.check()
    clock.advance(480, wall=wall, mono=mono)
    with pytest.raises(S.Closed):
        lease.check()


def test_successor_default_and_foreign_journal_are_closed(tmp_path):
    with pytest.raises(S.Closed, match="DEFAULT_UNAVAILABLE"):
        asyncio.run(S.run())
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    journal.scope_sha256 = "f" * 64
    with pytest.raises(S.Closed, match="JOURNAL_SCOPE"):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=SuccessorHooks(), clock=clock))
    assert not witness.calls and witness.once is None


def retry1_inputs(tmp_path, *, historical=False):
    """Self-owned synthetic timeout history, never an actual server witness."""
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path, historical=historical)
    d = scope.data
    record = dict(schema="cf026.successor.reserve-once.v1", additional_reserve_nano=50000000,
        authority_sha256="f"*64, count_cap=1, delegation="same-invocation-ordered-local-fsync",
        generation_cap=1, http_cap=2, invocation="b"*64, issued_at=(clock.wall()-timedelta(minutes=3)).isoformat(),
        namespace=d["namespace"], predecessor_sha256=d["predecessor_sha256"], process_id=7, retry_cap=0,
        scope_sha256=scope.sha256, successor_once=S.once_identity(scope), synthetic_only=False, total_reserved_nano=200000000)
    report = dict(server_reservation_actually_consumed=True, server_record_item_id="synthetic-item",
        server_record_turn_id="synthetic-turn", stdin_not_sent=True, terminal_code="BRIDGE_TIMEOUT", exit_code=1,
        key_content_reads=0, count_http=0, generation_http=0, db_created=0, source_copy_removed=True, entry_restored=True)
    timeout = dict(schema="cf026.successor.actual-timeout-evidence.v1", reserve_record=record, parent_reported=report,
        direct_readonly_confirmed=dict(local_journal_contains_only_execution_lock=True, journal_state_absent=True,
                                       phase_state_absent=True, entry_RELEASED=False),
        accounting=dict(historical_reservation_nano=150000000, new_consumed_server_hold_nano=50000000,
            combined_reserved_nano=200000000, billing_amount=None, refund_or_reissue_permitted=False,
            historical_http_unknown_unchanged=True), same_record_or_invocation_reuse_permitted=False)
    directory = tmp_path.resolve()/".cf026-successor-timeout-review-20261111"
    directory.mkdir(mode=0o700)
    path = directory/"actual-attempt.json"
    write(path, timeout)
    body_sha=C.hashlib.sha256(('CF026_SUCCESSOR_RESERVE_ONCE\n'+C.canonical(record)).encode()).hexdigest()
    manifest_path=directory/'manifest.json'
    write(manifest_path,dict(schema='cf026.successor.timeout-review-manifest.v1',
        files={'actual-attempt.json':C.hashlib.sha256(path.read_bytes()).hexdigest()},server_body_sha256=body_sha,
        actual_server_hold_nano=50000000,combined_reserved_nano=200000000))
    d["retry"] = dict(schema="cf026.successor.retry1.v1", ordinal=1,
        timeout=dict(path=str(path), stamp_json=C.canonical(C.regular(path,0o600)), sha256=C.hashlib.sha256(path.read_bytes()).hexdigest()),
        timeout_manifest=dict(path=str(manifest_path),stamp_json=C.canonical(C.regular(manifest_path,0o600)),sha256=C.hashlib.sha256(manifest_path.read_bytes()).hexdigest()),
        record_body='CF026_SUCCESSOR_RESERVE_ONCE\n'+C.canonical(record),
        record_body_sha256=C.hashlib.sha256(("CF026_SUCCESSOR_RESERVE_ONCE\n"+C.canonical(record)).encode()).hexdigest(),
        record_item_id=report["server_record_item_id"], record_turn_id=report["server_record_turn_id"],
        consent_message_id="Sentinel_"+"c"*32, carried_nano=200000000, total_reserved_nano=250000000)
    scope = S.Scope(C.canonical(d),scope.artifacts)
    state = dict(schema="cf026.successor.journal.v1",scope_sha256=scope.sha256,status="offered",
                 rights=dict(count=0,generation=0),preparation=None,journal=[])
    write(journal.path/"state.json",state)
    pin=dict(identity=C.regular(journal.path/"state.json",0o600),sha256=C.hashlib.sha256((journal.path/"state.json").read_bytes()).hexdigest())
    journal=S.Journal(journal.path,pin,journal.lock_pin,scope.sha256)
    return scope,source,witness,journal,clock


def test_successor_retry1_actual_helper_carries_200m_and_settles_250m(tmp_path):
    scope,source,witness,journal,clock=retry1_inputs(tmp_path)
    before={a.path:a.path.read_bytes() for a in scope.artifacts}
    timeout_path=Path(scope.data['retry']['timeout']['path']);timeout_before=timeout_path.read_bytes()
    hooks=SuccessorHooks();item=scope.data['request']
    hooks.snapshot_value=dict(count=1,generation=1,reserved=50000000,blocked=False,active=None,
        attempts={str(uuid4()):dict(request_sha256=item['request_sha256'],projection_sha256=item['projection_sha256'],
                                  observation=dict(state='observed',estimated_nano=120000))})
    with patch.object(V,'verify_live',successor_verifier_spy):
        result=asyncio.run(S.run(scope,source=source,authority=witness.capability(),journal=journal,
                               synthetic=True,hooks=hooks,clock=clock))
    assert result['total_reserved_nano']==250000000
    account=next(x for x in journal.state['journal'] if x['phase']=='final_accounting')
    assert account['reserved_nano']==250000000 and account['ledger']['reserved']==50000000
    assert witness.ack['total_reserved_nano']==250000000 and witness.ack['additional_reserve_nano']==50000000
    assert witness.ack['retry_ordinal']==1 and witness.ack['retry_of_sha256']==scope.data['retry']['record_body_sha256']
    assert before=={a.path:a.path.read_bytes() for a in scope.artifacts} and timeout_path.read_bytes()==timeout_before
    assert hooks.created==hooks.cleaned==1
    with pytest.raises(S.Closed):
        asyncio.run(S.run(scope,source=source,authority=witness.capability(),journal=journal,
                         synthetic=True,hooks=hooks,clock=clock))
    assert hooks.created==1


def test_successor_unconfirmed_result_keeps_gate_and_bounded_transport_diagnostic(tmp_path):
    scope,source,witness,journal,clock=retry1_inputs(tmp_path);item=scope.data['request']
    hooks=SuccessorHooks()
    hooks.snapshot_value=dict(count=1,generation=1,reserved=50000000,blocked=False,active=str(uuid4()),
        attempts={str(uuid4()):dict(request_sha256=item['request_sha256'],projection_sha256=item['projection_sha256'],observation=None)})
    trace=dict(events=[dict(stage='generation_dispatch_entered',elapsed_ms=100),
                       dict(stage='provider_timeout',elapsed_ms=55000),
                       dict(stage='settlement_unconfirmed',elapsed_ms=59000)],settlement_uncertain=True)
    async def unconfirmed(**args):
        value=await successor_verifier_spy(**args)
        return value|dict(meaning_status='unavailable',settlement='unconfirmed',gateway_diagnostic=trace)
    with patch.object(V,'verify_live',unconfirmed),pytest.raises(S.Closed,match='FIRST_SETTLEMENT_UNCONFIRMED'):
        asyncio.run(S.run(scope,source=source,authority=witness.capability(),journal=journal,
                         synthetic=True,hooks=hooks,clock=clock))
    account=next(x for x in journal.state['journal'] if x['phase']=='final_accounting')
    assert account['diagnostic']['failure_code']=='FIRST_SETTLEMENT_UNCONFIRMED'
    assert account['gateway_diagnostic']==trace and account['reserved_nano']==250000000
    assert account['ledger']['attempts'][0]['estimated_nano'] is None
    assert hooks.cleaned==1 and journal.state['status']=='closed'
    assert PRIVATE not in C.canonical(account)


def test_successor_late_ledger_rejection_is_classified_before_accounting(tmp_path):
    scope,source,witness,journal,clock=retry1_inputs(tmp_path);item=scope.data['request']
    hooks=SuccessorHooks()
    hooks.snapshot_value=dict(count=1,generation=1,reserved=50000000,blocked=True,active=str(uuid4()),
        attempts={str(uuid4()):dict(request_sha256=item['request_sha256'],projection_sha256=item['projection_sha256'],
                                  observation=dict(state='unknown',estimated_nano=None))})
    with patch.object(V,'verify_live',successor_verifier_spy),pytest.raises(S.Closed,match='FIRST_SETTLEMENT_UNCONFIRMED'):
        asyncio.run(S.run(scope,source=source,authority=witness.capability(),journal=journal,
                         synthetic=True,hooks=hooks,clock=clock))
    account=next(x for x in journal.state['journal'] if x['phase']=='final_accounting')
    assert account['diagnostic']['failure_code']=='FIRST_SETTLEMENT_UNCONFIRMED'
    assert account['diagnostic']['verifier']['settlement']=='observed'  # later ledger is independent evidence
    assert account['reserved_nano']==250000000 and hooks.cleaned==1


@pytest.mark.parametrize('bad',[{'events':[],'settlement_uncertain':True,'message':PRIVATE},
    {'events':[{'stage':PRIVATE,'elapsed_ms':1}],'settlement_uncertain':True},
    {'events':[{'stage':'provider_timeout','elapsed_ms':True}],'settlement_uncertain':True},
    {'events':[{'stage':'provider_timeout','elapsed_ms':1,'http_status':PRIVATE}],'settlement_uncertain':True}])
def test_successor_gateway_diagnostic_rejects_free_text_and_invalid_types(bad):
    with pytest.raises(S.Closed,match='DIAGNOSTIC_INVALID'):S.safe_gateway_diagnostic(bad)


@pytest.mark.parametrize('field,value',[('ordinal',2),('ordinal',True),('carried_nano',150000000),
    ('total_reserved_nano',200000000),('total_reserved_nano',1000000000),('record_body_sha256','a'*64),
    ('record_item_id','other-item'),('record_turn_id','other-turn'),('consent_message_id','approved')])
def test_successor_retry1_scope_drift_rejects_before_authority(tmp_path,field,value):
    scope,source,witness,journal,clock=retry1_inputs(tmp_path)
    data=scope.data;data['retry'][field]=value
    bad=S.Scope(C.canonical(data),scope.artifacts)
    hooks=SuccessorHooks()
    with pytest.raises(S.Closed):
        asyncio.run(S.run(bad,source=source,authority=witness.capability(),journal=journal,
                         synthetic=True,hooks=hooks,clock=clock))
    assert not witness.calls and hooks.created==0


@pytest.mark.parametrize('mutation',['missing','bytes','prior-invocation','prior-consent','counted','refund','different-namespace','raw-body','manifest-loss'])
def test_successor_retry1_bad_history_never_mints_right(tmp_path,mutation):
    scope,source,witness,journal,clock=retry1_inputs(tmp_path);data=scope.data
    pin=data['retry']['timeout'];p=Path(pin['path']);value=C.decode(p.read_bytes())
    if mutation=='missing':p.unlink()
    elif mutation=='bytes':p.write_bytes(b'{}')
    elif mutation=='manifest-loss':Path(data['retry']['timeout_manifest']['path']).unlink()
    elif mutation=='raw-body':
        data['retry']['record_body']+=' '
        data['retry']['record_body_sha256']=C.hashlib.sha256(data['retry']['record_body'].encode()).hexdigest()
    else:
        if mutation=='prior-invocation':data['invocation']=value['reserve_record']['invocation']
        if mutation=='prior-consent':data['consent_at']=value['reserve_record']['issued_at']
        if mutation=='counted':value['parent_reported']['count_http']=1
        if mutation=='refund':value['accounting']['combined_reserved_nano']=150000000
        if mutation=='different-namespace':value['reserve_record']['namespace']='0'*64
        write(p,value)
        pin.update(stamp_json=C.canonical(C.regular(p,0o600)),sha256=C.hashlib.sha256(p.read_bytes()).hexdigest())
        data['retry']['record_body_sha256']=C.hashlib.sha256(('CF026_SUCCESSOR_RESERVE_ONCE\n'+C.canonical(value['reserve_record'])).encode()).hexdigest()
        data['retry']['record_body']='CF026_SUCCESSOR_RESERVE_ONCE\n'+C.canonical(value['reserve_record'])
        # Re-pin a self-consistent synthetic wrapper so semantic violations are
        # rejected by their own checks, not hidden behind a stale manifest pin.
        mpin=data['retry']['timeout_manifest'];mp=Path(mpin['path']);mv=C.decode(mp.read_bytes())
        mv['files']['actual-attempt.json']=pin['sha256'];mv['server_body_sha256']=data['retry']['record_body_sha256']
        write(mp,mv)
        mpin.update(stamp_json=C.canonical(C.regular(mp,0o600)),sha256=C.hashlib.sha256(mp.read_bytes()).hexdigest())
    with pytest.raises((S.Closed,C.ControllerError,FileNotFoundError)):
        S.Scope(C.canonical(data),scope.artifacts).check(source,witness.capability(),synthetic=True)
    assert not witness.calls


def test_successor_retry1_identity_cannot_multiply_by_source_or_consent(tmp_path):
    scope,*_=retry1_inputs(tmp_path)
    identity=S.once_identity(scope);data=scope.data
    original=data.copy();original.pop('retry')
    assert identity!=S.once_identity(S.Scope(C.canonical(original),scope.artifacts))
    for key in ('invocation','authority_sha256','module_sha256','predecessor_sha256','consent_at'):
        altered=scope.data;altered[key]='different'
        assert S.once_identity(S.Scope(C.canonical(altered),scope.artifacts))==identity
    altered=scope.data;altered['retry']['record_body_sha256']='d'*64
    assert S.once_identity(S.Scope(C.canonical(altered),scope.artifacts))==identity


@pytest.mark.parametrize('phase',['reserve','issue','start'])
def test_successor_retry1_late_start_ack_holds_250m_without_resource(tmp_path,phase):
    scope,source,witness,journal,clock=retry1_inputs(tmp_path)
    saved={a.path:a.path.read_bytes() for a in scope.artifacts}
    consume=witness.consume
    async def delayed(**args):
        ack=await consume(**args)
        if args['phase']==phase:clock.advance(120.001)
        return ack
    authority=S.Authority('synthetic',witness.identity,witness.verify,delayed,witness.readback)
    hooks=SuccessorHooks()
    with pytest.raises(S.Closed):
        asyncio.run(S.run(scope,source=source,authority=authority,journal=journal,
                         synthetic=True,hooks=hooks,clock=clock))
    assert witness.once==S.once_identity(scope) and hooks.created==0
    assert journal.state['status']=='closed'
    assert journal.state['journal'][-1]['total_reserved_nano']==250000000
    assert journal.state['journal'][-1]['unknown_hold_nano']==50000000
    assert saved=={a.path:a.path.read_bytes() for a in scope.artifacts}


@pytest.mark.parametrize('seconds',[48.045,119.999,120,120.001])
def test_successor_120s_initial_delivery_boundary(seconds):
    clock=SuccessorClock();issued=clock.wall();clock.advance(seconds)
    if seconds>120:
        with pytest.raises(S.Closed,match='LEASE_START'):S.Lease(issued.isoformat(),(issued-timedelta(seconds=1)).isoformat(),clock)
    else:
        lease=S.Lease(issued.isoformat(),(issued-timedelta(seconds=1)).isoformat(),clock)
        lease.check(starting=True)
        assert lease.expires==issued+timedelta(seconds=600)


@pytest.mark.parametrize('wall,mono',[(True,False),(False,True),(True,True)])
@pytest.mark.parametrize('seconds',[119.999,120,120.001])
def test_successor_120s_start_wall_and_monotonic_boundaries(wall,mono,seconds):
    clock=SuccessorClock();lease=S.Lease(clock.wall().isoformat(),(clock.wall()-timedelta(seconds=1)).isoformat(),clock)
    clock.advance(seconds,wall=wall,mono=mono)
    if seconds>120:
        with pytest.raises(S.Closed):lease.check(starting=True)
    else:lease.check(starting=True)
    lease.check()


def successor_reseal_fixture(scope, journal, *, changed_name=None, mutate=None, document_change=None):
    """Synthetic-only re-pinning to exercise schema checks after valid hash checks."""
    artifacts = []
    for artifact in scope.artifacts:
        if artifact.name == changed_name:
            value = C.decode(artifact.path.read_bytes())
            mutate(value)
            write(artifact.path, value)
            artifact = S.Artifact(artifact.name, artifact.path, C.canonical(C.regular(artifact.path, 0o600)),
                                  C.hashlib.sha256(artifact.path.read_bytes()).hexdigest())
        artifacts.append(artifact)
    d = scope.data
    d["artifacts"] = {a.name: a.sha256 for a in artifacts}
    d["predecessor_sha256"] = C.digest(d["artifacts"])
    if document_change is not None:
        document_change(d)
    replacement = S.Scope(C.canonical(d), tuple(artifacts))
    state = C.decode((journal.path / "state.json").read_bytes())
    state["scope_sha256"] = replacement.sha256
    write(journal.path / "state.json", state)
    pin = dict(identity=C.regular(journal.path / "state.json", 0o600),
               sha256=C.hashlib.sha256((journal.path / "state.json").read_bytes()).hexdigest())
    return replacement, S.Journal(journal.path, pin, journal.lock_pin, replacement.sha256)


@pytest.mark.parametrize("fault", ["header", "state", "carry", "consumed", "child", "child-link", "ledger-bool", "runtime", "runtime-carry", "closure", "terminal", "cause", "second-question", "source", "namespace", "module", "consent"])
def test_successor_actual_schemas_and_scope_reject_self_consistent_projection(tmp_path, fault):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    mutations = {
        "header": ("header", lambda x: x.pop("approval_event")),
        "state": ("state", lambda x: x.update(total_reserved_nano=50000000)),
        "carry": ("header", lambda x: x["carry_hashes"].update(state="f"*64)),
        "consumed": ("state", lambda x: next(iter(x["allocations"].values())).update(start_consumed=False)),
        "child": ("child_state", lambda x: x.update(status="claimed")),
        "child-link": ("child_state", lambda x: x.update(approval_id=str(uuid4()))),
        "ledger-bool": ("child_state", lambda x: x["journal"][0]["state"].update(count=True)),
        "runtime": ("runtime", lambda x: x.update(key_metadata={})),
        "runtime-carry": ("runtime", lambda x: x.update(old_carry={})),
        "closure": ("closure", lambda x: x.update(journal_uncertain=True)),
        "terminal": ("state", lambda x: next(iter(x["allocations"].values()))["outcome"].update(code="KEY_SOURCE_INVALID")),
        "cause": ("child_state", lambda x: x["journal"][0]["diagnostics"][0].update(failure_code="FIRST_SETTLEMENT_UNCONFIRMED")),
    }
    if fault in mutations:
        name, mutate = mutations[fault]
        scope, journal = successor_reseal_fixture(scope, journal, changed_name=name, mutate=mutate)
    else:
        def change(d):
            if fault == "second-question":
                d["request"]["prepare_body"]["draft"]["original_query"] = "현대건설 어제 말고 외국인 말고 기관 수급"
            elif fault == "source":
                d["source"]["path"] = str(tmp_path / "other-input.txt")
            elif fault == "namespace":
                d["namespace"] = "f" * 64
            elif fault == "module":
                d["module_sha256"] = "f" * 64
            elif fault == "consent":
                d["consent_at"] = "2030-01-01T00:00:00"
        scope, journal = successor_reseal_fixture(scope, journal, document_change=change)
    hooks = SuccessorHooks()
    with pytest.raises(S.Closed):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    assert not witness.calls and hooks.created == 0


def test_successor_once_identity_ignores_new_source_and_invocation(tmp_path):
    scope, _, _, journal, _ = successor_assembly_inputs(tmp_path)
    d = scope.data
    d["invocation"] = "f" * 64
    d["source"] = {"synthetic_changed_source": True}
    assert S.once_identity(S.Scope(C.canonical(d), scope.artifacts)) == S.once_identity(scope)
    state_artifact = next(a for a in scope.artifacts if a.name == "state")
    alternate = state_artifact.path.with_name("projection.json")
    write(alternate, C.decode(state_artifact.path.read_bytes()))
    artifacts = tuple(S.Artifact(a.name, alternate, C.canonical(C.regular(alternate, 0o600)), a.sha256)
                      if a.name == "state" else a for a in scope.artifacts)
    assert S.once_identity(S.Scope(scope.document, artifacts)) == S.once_identity(scope)
    with pytest.raises(S.Closed, match="ANCESTRY_SCOPE"):
        S.Scope(scope.document, artifacts).check(C.KeySource(tmp_path / "synthetic-input.txt", scope.data["source"]["identity"], True),
                                               S.Authority("synthetic", scope.data["authority_sha256"], lambda: None, lambda: None, lambda: None), synthetic=True)


def test_successor_start_fsync_latency_cannot_create_resource(tmp_path):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    original = journal.persist
    def delayed(status, event, **kwargs):
        original(status, event, **kwargs)
        if event["phase"] == "start_ACK":
            clock.advance(121, wall=False)
    hooks = SuccessorHooks()
    with patch.object(journal, "persist", delayed), pytest.raises(S.Closed, match="LEASE_EXPIRED"):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    assert hooks.created == 0


@pytest.mark.parametrize("phase", ["count", "generation"])
def test_successor_phase_ack_expiry_never_supplies_after_count(tmp_path, phase):
    from unittest.mock import AsyncMock
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    witness.advance = phase
    hooks = SuccessorHooks()
    with patch.object(V, "verify_live", successor_verifier_spy), patch.object(C.KeySource, "read", new_callable=AsyncMock) as read:
        read.return_value = "cf026-synthetic-unused"
        with pytest.raises(S.Closed):
            asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                              synthetic=True, hooks=hooks, clock=clock))
    assert read.await_count == (0 if phase == "count" else 1)
    assert hooks.cleaned == 1 and hooks.preserved == 0


def test_successor_late_cancellation_preserves_prior_failure_account_and_proof(tmp_path):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    witness.fail = "accounting-cancel"
    hooks = SuccessorHooks()
    async def unavailable(**_):
        return dict(stages=[], meaning_status="unavailable", settlement="hold")
    with patch.object(V, "verify_live", unavailable), pytest.raises(asyncio.CancelledError):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    assert hooks.preserved == 1 and hooks.cleaned == 0
    assert any(x["phase"] == "final_accounting" for x in journal.state["journal"])
    assert journal.state["status"] == "claimed"


def test_successor_accounting_ack_loss_is_bounded_preserve_not_cleanup(tmp_path):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    witness.fail = "accounting-readback"
    hooks = SuccessorHooks()
    observed_timeouts = []
    original = lambda *args, **kwargs: observed_timeouts.append(kwargs.get("timeout"))
    hooks.driver.call = original
    def preserve():
        hooks.preserved += 1
        hooks.driver.call("synthetic-receipt-check", timeout=100)
    hooks.preserve = preserve
    async def unavailable(**_):
        return dict(stages=[], meaning_status="unavailable", settlement="hold")
    with patch.object(V, "verify_live", unavailable), pytest.raises(S.Closed):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    assert hooks.preserved == 1 and hooks.cleaned == 0
    assert observed_timeouts and 0 < observed_timeouts[0] <= 5
    assert hooks.driver.call is original
    assert any(x["phase"] == "final_accounting" for x in journal.state["journal"])


def test_successor_fresh_object_after_local_loss_cannot_reconsume(tmp_path):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    witness.fail = "issue"
    hooks = SuccessorHooks()
    with pytest.raises(S.Closed):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    witness.fail = None
    # Simulated loss/reset of only local evidence does not reset independent witness.
    offered = dict(schema="cf026.successor.journal.v1", scope_sha256=scope.sha256,
                   status="offered", rights=dict(count=0, generation=0), preparation=None, journal=[])
    write(journal.path / "state.json", offered)
    pin = dict(identity=C.regular(journal.path / "state.json", 0o600), sha256=C.hashlib.sha256((journal.path / "state.json").read_bytes()).hexdigest())
    fresh = S.Journal(journal.path, pin, journal.lock_pin, scope.sha256)
    calls = len(witness.calls)
    with pytest.raises(S.Closed):
        asyncio.run(S.run(S.Scope(scope.document, scope.artifacts), source=source, authority=witness.capability(),
                          journal=fresh, synthetic=True, hooks=hooks, clock=clock))
    assert witness.calls[calls:] == ["admission"] and hooks.created == 0


def test_successor_owned_sql_dispatch_guard_stops_epoch_write_after_await(tmp_path):
    # The real checked epoch helper is executed; DB objects are mocks, not real PG.
    from contextlib import asynccontextmanager
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    authority = witness.capability()
    journal.enter()
    session = S.Session(scope, source, authority, journal, True, clock)
    session.lease = S.Lease(clock.wall().isoformat(), scope.data["consent_at"], clock)
    adds = []
    class Database:
        async def scalar(self, *_):
            return None
        def add(self, row):
            adds.append(row)
        async def commit(self):
            raise AssertionError("Expired epoch must not commit")
    @asynccontextmanager
    async def database(*_):
        yield Database()
    async def principal(*_, **__):
        return None
    async def delayed_clock(_):
        clock.advance(601)
        return clock.wall()
    import src.modules.auth.application.session_service as A
    import src.modules.supervisor.infrastructure.preparation_repository as R
    try:
        with patch.object(S, "checked_session", database), patch.object(A, "validate_principal", principal), patch.object(R, "clock", delayed_clock):
            with pytest.raises(S.Closed, match="LEASE_EXPIRED"):
                asyncio.run(S.initialize_checked_epoch(object(), object(), str(uuid4()), session))
        assert not adds
    finally:
        journal.close()


def test_successor_checked_connection_rechecks_after_owned_preflight(tmp_path):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    journal.enter()
    session = S.Session(scope, source, witness.capability(), journal, True, clock)
    session.lease = S.Lease(clock.wall().isoformat(), scope.data["consent_at"], clock)
    class Proof:
        async def preflight(self):
            clock.advance(601)
    import sqlalchemy.ext.asyncio as SQL
    async def execute():
        async with S.checked_connection(Proof(), session):
            raise AssertionError("Expired connection must not open")
    try:
        with patch.object(SQL, "create_async_engine", side_effect=AssertionError("No engine")) as create:
            with pytest.raises(S.Closed, match="LEASE_EXPIRED"):
                asyncio.run(execute())
        create.assert_not_called()
    finally:
        journal.close()


def test_successor_scoped_sql_hooks_recheck_and_are_removed(tmp_path):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    journal.enter()
    session = S.Session(scope, source, witness.capability(), journal, True, clock)
    session.lease = S.Lease(clock.wall().isoformat(), scope.data["consent_at"], clock)
    listeners, removed = {}, []
    own_engine = object()
    class Connection:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            return None
    class Engine:
        sync_engine = own_engine
        disposed = False
        def connect(self):
            return Connection()
        async def dispose(self):
            self.disposed = True
    engine = Engine()
    class Proof:
        url = "synthetic://not-a-real-connection"
        async def preflight(self):
            return None
        def connection_parameters(self):
            return {}
        async def attest_connection(self, _):
            return None
    def listen(target, name, callback):
        assert target is own_engine
        listeners[name] = callback
    def remove(target, name, callback):
        assert target is own_engine and listeners[name] is callback
        removed.append(name)
    async def execute():
        async with S.checked_connection(Proof(), session):
            clock.advance(601)
            for name in ("before_cursor_execute", "commit"):
                with pytest.raises(S.Closed, match="LEASE_EXPIRED"):
                    listeners[name]()
    import sqlalchemy.ext.asyncio as SQL
    import sqlalchemy.event as E
    try:
        with patch.object(SQL, "create_async_engine", return_value=engine), patch.object(E, "listen", listen), patch.object(E, "remove", remove):
            asyncio.run(execute())
        assert engine.disposed and set(removed) == {"before_cursor_execute", "commit"}
    finally:
        journal.close()


def test_successor_concurrent_local_claim_is_one_winner(tmp_path):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    first_hooks, second_hooks = SuccessorHooks(), SuccessorHooks()
    second_journal = S.Journal(journal.path, journal.pin.copy(), journal.lock_pin, scope.sha256)
    async def unavailable(**_):
        return dict(stages=[], meaning_status="unavailable", settlement="hold")
    async def execute():
        started, release = asyncio.Event(), asyncio.Event()
        async def admission(**args):
            if args["phase"] == "admission":
                started.set()
                await release.wait()
            return await witness.verify(**args)
        authority = S.Authority("synthetic", witness.identity, admission, witness.consume, witness.readback)
        task = asyncio.create_task(S.run(scope, source=source, authority=authority, journal=journal,
                                        synthetic=True, hooks=first_hooks, clock=clock))
        try:
            async with asyncio.timeout(1):
                await started.wait()
            with pytest.raises(S.Closed):
                await S.run(scope, source=source, authority=witness.capability(), journal=second_journal,
                            synthetic=True, hooks=second_hooks, clock=clock)
        finally:
            release.set()
        result = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(result[0], S.Closed)
    with patch.object(V, "verify_live", unavailable):
        asyncio.run(execute())
    assert first_hooks.created == 1 and second_hooks.created == 0
    assert witness.calls.count("reserve") == 1


@pytest.mark.parametrize("ack", [True, {"approved": True}, "a"*64])
def test_successor_bool_or_hash_is_not_an_authority_consumption_ack(tmp_path, ack):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    async def forged(**_):
        return ack
    authority = S.Authority("synthetic", witness.identity, witness.verify, forged, forged)
    hooks = SuccessorHooks()
    with pytest.raises(S.Closed):
        asyncio.run(S.run(scope, source=source, authority=authority, journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    assert hooks.created == 0


def test_successor_consumed_witness_survives_changed_invocation_and_local_reset(tmp_path):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    witness.fail = "issue"
    hooks = SuccessorHooks()
    with pytest.raises(S.Closed):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    d = scope.data
    d["invocation"] = "f" * 64
    changed = S.Scope(C.canonical(d), scope.artifacts)
    assert S.once_identity(changed) == S.once_identity(scope)
    offered = dict(schema="cf026.successor.journal.v1", scope_sha256=changed.sha256,
                   status="offered", rights=dict(count=0, generation=0), preparation=None, journal=[])
    write(journal.path / "state.json", offered)
    fresh = S.Journal(journal.path, dict(identity=C.regular(journal.path/"state.json", 0o600),
                        sha256=C.hashlib.sha256((journal.path/"state.json").read_bytes()).hexdigest()), journal.lock_pin, changed.sha256)
    witness.fail = None
    with pytest.raises(S.Closed):
        asyncio.run(S.run(changed, source=source, authority=witness.capability(), journal=fresh,
                          synthetic=True, hooks=hooks, clock=clock))
    assert hooks.created == 0 and witness.calls.count("reserve") == 1


def test_successor_live_cannot_accept_synthetic_scope_or_callback_helpers(tmp_path):
    scope, source, witness, journal, _ = successor_assembly_inputs(tmp_path)
    with pytest.raises(S.Closed):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal))
    assert witness.once is None and not witness.calls


def test_successor_normalizes_secrets_and_preserves_unknown_ledger(tmp_path, capsys):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    hooks = SuccessorHooks()
    async def fail(**_):
        raise OSError(PRIVATE)
    with patch.object(V, "verify_live", fail), pytest.raises(S.Closed) as caught:
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    text = str(caught.value) + (journal.path / "state.json").read_text() + capsys.readouterr().out
    assert PRIVATE not in text and C.hashlib.sha256(PRIVATE.encode()).hexdigest() not in text
    accounting = next(x for x in journal.state["journal"] if x["phase"] == "final_accounting")
    assert accounting["ledger"] is None and accounting["estimated_nano"] is None
    assert accounting["reserved_nano"] == 200000000 and accounting["http"] == "unknown"
    assert str(S.Closed(PRIVATE)) == "SUCCESSOR_FAILED"


@pytest.mark.parametrize("phase", ["count-readback", "generation-readback"])
def test_successor_phase_ack_unknown_blocks_next_supplier_or_generation(tmp_path, phase):
    from unittest.mock import AsyncMock
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    witness.fail = phase
    hooks = SuccessorHooks()
    with patch.object(V, "verify_live", successor_verifier_spy), patch.object(C.KeySource, "read", new_callable=AsyncMock) as read:
        read.return_value = "cf026-synthetic-unused"
        with pytest.raises(S.Closed):
            asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                              synthetic=True, hooks=hooks, clock=clock))
    assert read.await_count == (0 if phase.startswith("count") else 1)
    assert hooks.cleaned == 0 and hooks.preserved == 1 and witness.calls.count("count") == 1
    assert witness.calls.count("generation") == (0 if phase.startswith("count") else 1)


def test_successor_phase_replay_is_rejected_after_one_verifier_call(tmp_path):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    hooks = SuccessorHooks()
    calls = []
    async def verified(**kwargs):
        calls.append(kwargs)
        result = await successor_verifier_spy(**kwargs)
        phase_authority = kwargs["authority"]
        with pytest.raises(S.Closed, match="PHASE_SCOPE"):
            await phase_authority.verify(phase="count")
        return result
    item = scope.data["request"]
    hooks.snapshot_value = dict(count=1, generation=1, reserved=50000000, blocked=False, active=None,
        attempts={str(uuid4()): dict(request_sha256=item["request_sha256"], projection_sha256=item["projection_sha256"],
                                   observation=dict(state="observed", estimated_nano=120000))})
    with patch.object(V, "verify_live", verified):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    assert len(calls) == 1 and witness.calls.count("count") == witness.calls.count("generation") == 1


def test_successor_lease_fields_cannot_be_renewed():
    from dataclasses import FrozenInstanceError
    clock = SuccessorClock()
    lease = S.Lease(clock.wall().isoformat(), clock.wall().isoformat(), clock)
    for field, value in [("expires", clock.wall()+timedelta(hours=1)), ("monotonic_end", 999999),
                         ("monotonic_start_end", 999999), ("issued", clock.wall()+timedelta(minutes=1))]:
        with pytest.raises(FrozenInstanceError):
            setattr(lease, field, value)


def test_successor_phase_verification_serializes_same_attempt(tmp_path):
    scope, source, witness, journal, clock = successor_assembly_inputs(tmp_path)
    hooks = SuccessorHooks()
    async def concurrent(**kwargs):
        phase_authority = kwargs["authority"]
        d = phase_authority.session.scope.data
        async def fresh(self):
            await asyncio.sleep(0)
            if self.store.state["preparation"] is None:
                self.store.persist("claimed", dict(phase="preparation_binding_ACK"), preparation={"synthetic_only": True})
            return dict(count=0, generation=0, reserved=0)
        args = dict(mode="synthetic", proof_binding=kwargs["binding"], principal=kwargs["principal"],
                    agreement=kwargs["counter_agreement"], key_supplier=kwargs["key_supplier"],
                    key_source_capability=source, draft_sha256=d["request"]["draft_sha256"], semantic_sha256=d["semantic_sha256"])
        with patch.object(S.PhaseAuthority, "fresh_preparation", fresh):
            await phase_authority.verify(phase="initial", **args)
            args.update(request_sha256=d["request"]["request_sha256"], projection_sha256=d["request"]["projection_sha256"])
            await phase_authority.verify(phase="preflight", **args)
            attempts = await asyncio.gather(phase_authority.verify(phase="count", **args),
                                             phase_authority.verify(phase="count", **args), return_exceptions=True)
        assert sum(isinstance(x, S.Closed) for x in attempts) == 1
        return dict(stages=[], meaning_status="unavailable", settlement="hold")
    with patch.object(V, "verify_live", concurrent), pytest.raises(S.Closed):
        asyncio.run(S.run(scope, source=source, authority=witness.capability(), journal=journal,
                          synthetic=True, hooks=hooks, clock=clock))
    assert witness.calls.count("count") == 1


def retry2_inputs(tmp_path):
    """Synthetic closed retry1 with unknown usage; never actual issuance."""
    scope, source, witness, journal, clock = retry1_inputs(tmp_path, historical=True)
    d = scope.data
    prior = C.decode(C.canonical(d))
    prior['semantic_sha256'] = S.historical_semantic(d | {'retry': {'ordinal': 2}})
    home = tmp_path.resolve()/'.cf026-successor-retry-20261111'
    home.mkdir(mode=0o700)
    (home/'successor-journal-retry-1').mkdir(mode=0o700)
    evidence = {}
    def pin(name, path, value):
        write(path, value)
        evidence[name] = dict(path=str(path), stamp_json=C.canonical(C.regular(path,0o600)),
                              sha256=C.hashlib.sha256(path.read_bytes()).hexdigest())
    pin('inputs',home/'reviewed-successor-inputs.json',dict(template=dict(scope_template=prior)))
    prior_once=C.digest(dict(namespace=d['namespace'], predecessor_bootstrap=d['predecessor_bootstrap'],retry_ordinal=1))
    record=dict(schema='cf026.successor.reserve-once.v1',additional_reserve_nano=50000000,authority_sha256='9'*64,
        count_cap=1,generation_cap=1,http_cap=2,retry_cap=0,invocation='8'*64,issued_at=(clock.wall()-timedelta(minutes=2)).isoformat(),
        namespace=d['namespace'],predecessor_sha256=d['predecessor_sha256'],process_id=8,retry_ordinal=1,
        retry_of_sha256=d['retry']['record_body_sha256'],scope_sha256='7'*64,successor_once=prior_once,
        synthetic_only=False,total_reserved_nano=250000000,delegation='same-invocation-ordered-local-fsync')
    ledger=dict(count=1,generation=1,reserved=50000000,blocked=False,attempts=[dict(state='unknown',estimated_nano=None)])
    account=dict(phase='final_accounting',ledger=ledger,observation='fresh_ledger',estimated_nano=None,http='unknown',reserved_nano=250000000)
    events=[account,dict(phase='closing',external_accounting_ACK=True),dict(phase='cleanup_confirmed')]
    pin('journal',home/'successor-journal-retry-1'/'state.json',dict(schema='cf026.successor.journal.v1',status='closed',
        scope_sha256=record['scope_sha256'],rights=dict(count=1,generation=1),journal=events))
    binding={k:record[k] for k in record if k not in {'schema','synthetic_only','process_id','authority_sha256','delegation','issued_at'}}
    ack=binding|dict(phase='accounting',authority_sha256=record['authority_sha256'],sequence=6,issued_at=record['issued_at'],consumed=True,record_sha256=C.digest(account))
    order=['reserve','issue','start','count','generation','accounting']
    pin('phases',home/'successor-phases-retry-1.json',dict(binding=binding,ack=ack,sequence=6,phases=order))
    diag=tmp_path.resolve()/'.cf026-runtime-deadline-diagnostic-20261111';diag.mkdir(mode=0o700)
    pin('result',diag/'actual-result.json',dict(schema='cf026.retry1.actual-result-diagnostic.v1',
        original_files={evidence[n]['path']:evidence[n]['sha256'] for n in ('journal','phases')},
        direct_readonly=dict(closed=True,cleanup_recorded=True,local_accounting_ack_matches_journal=True,
            ledger=ledger,total_reserved_nano=250000000,estimated_nano=None,phase_order=order),
        parent_reported=dict(exit_code=1,terminal_code='SUCCESSOR_CLOSED',source_copy_removed=True,
            server_record_item_id='synthetic-retry1-item',server_record_turn_id='synthetic-retry1-turn',
            issued_at=record['issued_at'],process_id=record['process_id'])))
    body='CF026_SUCCESSOR_RESERVE_ONCE\n'+C.canonical(record)
    d['retry']=dict(schema='cf026.successor.retry2.v1',ordinal=2,prior_retry=d['retry'],evidence=evidence,
        record_body=body,record_body_sha256=C.hashlib.sha256(body.encode()).hexdigest(),
        record_item_id='synthetic-retry1-item',record_turn_id='synthetic-retry1-turn',
        consent_message_id='Sentinel_'+'6'*32,carried_nano=250000000,total_reserved_nano=300000000,
        current_code=dict(path=str(Path(S.__file__).resolve().parents[2]),directory=[],helper_sha256=d['module_sha256']))
    scope,journal=successor_reseal_fixture(scope,journal,document_change=lambda value:value.update(d))
    return scope,source,witness,journal,clock


def retry2_success_hooks(scope):
    hooks=SuccessorHooks();item=scope.data['request']
    hooks.snapshot_value=dict(count=1,generation=1,reserved=50000000,blocked=False,active=None,
        attempts={str(uuid4()):dict(request_sha256=item['request_sha256'],projection_sha256=item['projection_sha256'],
                                  observation=dict(state='observed',estimated_nano=120000))})
    return hooks


def test_retry2_actual_helper_300m_once_and_historical_spec_unchanged(tmp_path):
    scope,source,witness,journal,clock=retry2_inputs(tmp_path)
    before={a.path:a.path.read_bytes() for a in scope.artifacts}
    before.update({Path(p['path']):Path(p['path']).read_bytes() for p in scope.data['retry']['evidence'].values()})
    hooks=retry2_success_hooks(scope)
    with patch.object(V,'verify_live',wraps=successor_verifier_spy) as verify,patch.object(C.KeySource,'read',wraps=source.read) as read:
        result=asyncio.run(S.run(scope,source=source,authority=witness.capability(),journal=journal,synthetic=True,hooks=hooks,clock=clock))
    assert result['total_reserved_nano']==300000000 and hooks.created==hooks.cleaned==1
    assert verify.call_count==read.call_count==1
    assert witness.ack['retry_ordinal']==2 and witness.ack['total_reserved_nano']==300000000
    assert witness.ack['retry_of_sha256']==scope.data['retry']['record_body_sha256']
    assert before=={p:p.read_bytes() for p in before}
    assert next(x for x in journal.state['journal'] if x['phase']=='final_accounting')['reserved_nano']==300000000
    with pytest.raises(S.Closed):asyncio.run(S.run(scope,source=source,authority=witness.capability(),journal=journal,synthetic=True,hooks=hooks,clock=clock))
    assert hooks.created==1


@pytest.mark.parametrize('field,value',[('ordinal',3),('ordinal',True),('carried_nano',200000000),
    ('total_reserved_nano',250000000),('schema','cf026.successor.retry1.v1'),('consent_message_id','invalid')])
def test_retry2_invalid_scope_mutates_nothing(tmp_path,field,value):
    scope,source,witness,journal,clock=retry2_inputs(tmp_path);d=scope.data;d['retry'][field]=value
    changed=S.Scope(C.canonical(d),scope.artifacts)
    with pytest.raises((S.Closed,C.ControllerError)):changed.check(source,witness.capability(),synthetic=True)
    assert not witness.calls


@pytest.mark.parametrize('name',['inputs','journal','phases','result'])
def test_retry2_missing_evidence_is_never_first_issue(tmp_path,name):
    scope,source,witness,journal,clock=retry2_inputs(tmp_path)
    Path(scope.data['retry']['evidence'][name]['path']).unlink()
    with pytest.raises((S.Closed,C.ControllerError,OSError)):scope.check(source,witness.capability(),synthetic=True)
    assert not witness.calls


@pytest.mark.parametrize('name,fault',[('journal','open'),('journal','refund'),('phases','ack'),
    ('result','cleanup'),('inputs','semantic'),('inputs','question'),('result','http')])
def test_retry2_resealed_history_still_rejects_invalid_schema(tmp_path,name,fault):
    scope,source,witness,journal,clock=retry2_inputs(tmp_path);d=scope.data
    pin=d['retry']['evidence'][name];p=Path(pin['path']);value=C.decode(p.read_bytes())
    if fault=='open':value['status']='offered'
    elif fault=='refund':value['journal'][0]['reserved_nano']=0
    elif fault=='ack':value['ack']['record_sha256']='f'*64
    elif fault=='cleanup':value['direct_readonly']['cleanup_recorded']=False
    elif fault=='semantic':value['template']['scope_template']['semantic_sha256']=MEANING_SPEC_SHA256
    elif fault=='question':value['template']['scope_template']['request']['prepare_body']['draft']['original_query']='다른 질문'
    else:value['direct_readonly']['estimated_nano']=0
    write(p,value);pin.update(stamp_json=C.canonical(C.regular(p,0o600)),sha256=C.hashlib.sha256(p.read_bytes()).hexdigest())
    with pytest.raises(S.Closed):S.Scope(C.canonical(d),scope.artifacts).check(source,witness.capability(),synthetic=True)
    assert not witness.calls


@pytest.mark.parametrize('phase',['reserve','reserve-readback','issue','start','count','generation','accounting','accounting-cancel'])
def test_retry2_ack_loss_preserves_total_and_no_extra_supplier(tmp_path,phase):
    scope,source,witness,journal,clock=retry2_inputs(tmp_path);witness.fail=phase;hooks=retry2_success_hooks(scope)
    with patch.object(V,'verify_live',wraps=successor_verifier_spy) as verify,patch.object(C.KeySource,'read',wraps=source.read) as read:
        with pytest.raises((S.Closed,asyncio.CancelledError)):
            asyncio.run(S.run(scope,source=source,authority=witness.capability(),journal=journal,synthetic=True,hooks=hooks,clock=clock))
    assert read.call_count<=1 and verify.call_count<=1
    assert witness.ack['total_reserved_nano']==300000000
    if phase in {'reserve','reserve-readback','issue','start'}:assert hooks.created==0
    if phase.startswith('accounting'):assert hooks.cleaned==0 and hooks.preserved==1


def test_retry2_identity_ignores_new_source_invocation_consent(tmp_path):
    scope,*_=retry2_inputs(tmp_path);d=scope.data;original=S.once_identity(scope)
    d.update(invocation='4'*64,consent_at='2030-01-01T00:00:00Z',source={})
    d['retry']['consent_message_id']='Sentinel_'+'9'*32
    assert S.once_identity(S.Scope(C.canonical(d),scope.artifacts))==original
    d['retry']['ordinal']=1
    assert S.once_identity(S.Scope(C.canonical(d),scope.artifacts))!=original


@pytest.mark.parametrize('mode',[0o700,0o755])
def test_retry2_actual_code_provenance_owned_directory_without_private_mode_rule(tmp_path,mode):
    original=tmp_path/'verith-supervisor-live-controller';original.mkdir(mode=0o755)
    current=tmp_path/'verith-supervisor-single-revalidation';current.mkdir(mode=mode)
    source=NS(code_root=NS(path=original))
    d={'retry':{'ordinal':2,'current_code':dict(path=str(current),directory=S.code_directory_identity(current),helper_sha256='a'*64)}}
    assert S.reviewed_execution_root(source,d,'a'*64)==current
    d['retry']['current_code']['directory'][1]+=1
    with pytest.raises(S.Closed,match='CODE_DRIFT'):S.reviewed_execution_root(source,d,'a'*64)
    current.chmod(0o777)
    with pytest.raises(S.Closed,match='CODE_DRIFT'):S.code_directory_identity(current)


def test_retry2_new_invocation_after_local_loss_still_consumed(tmp_path):
    scope,source,witness,journal,clock=retry2_inputs(tmp_path);hooks=retry2_success_hooks(scope)
    witness.fail='reserve'
    with pytest.raises(S.Closed):asyncio.run(S.run(scope,source=source,authority=witness.capability(),journal=journal,synthetic=True,hooks=hooks,clock=clock))
    d=scope.data;d['invocation']='3'*64;changed=S.Scope(C.canonical(d),scope.artifacts)
    offered=dict(schema='cf026.successor.journal.v1',scope_sha256=changed.sha256,status='offered',rights=dict(count=0,generation=0),preparation=None,journal=[])
    write(journal.path/'state.json',offered)
    pin=dict(identity=C.regular(journal.path/'state.json',0o600),sha256=C.hashlib.sha256((journal.path/'state.json').read_bytes()).hexdigest())
    fresh=S.Journal(journal.path,pin,journal.lock_pin,changed.sha256);witness.fail=None
    with pytest.raises(S.Closed):asyncio.run(S.run(changed,source=source,authority=witness.capability(),journal=fresh,synthetic=True,hooks=hooks,clock=clock))
    assert hooks.created==0


def approved_quality_candidate():
    from src.supervisor.domain.meaning_proposals import MeaningProposal
    q='현대건설 외국인 말고 3주 수급'
    def evidence(text):
        start=q.index(text)
        return dict(source_kind='original_query',answer_id=None,start=start,end=start+len(text),text=text)
    return MeaningProposal.model_validate(dict(schema_version='supervisor.meaning.v1',
        mentions=[dict(evidence=evidence('현대건설'),negation=None)],
        views=[dict(view='flow',evidence=evidence('수급'),negation=None)],
        conditions=[dict(domain='flow',kind='exclude',value='외국인',evidence=evidence('외국인'),negation=evidence('말고')),
                    dict(domain='flow',kind='period',value='3주',evidence=evidence('3주'),negation=None)]))


def test_retry2_quality_preserves_grounded_negation_period_and_rejects_free_text():
    draft=M.Draft(original_query='현대건설 외국인 말고 3주 수급',answers=[],revision=0)
    capture=S.safe_quality(draft,approved_quality_candidate())
    assert capture['status']=='validated'
    frame=capture['assessment']
    assert frame['mentions'][0]['text']=='현대건설' and frame['requested_views']==['flow']
    assert any(c['kind']=='exclude' and c['value']=='외국인' and any(e['text']=='말고' for e in c['evidence']) for c in frame['conditions'])
    assert any(c['kind']=='period' and c['value']=='3주' and c['disposition']=='unsupported' for c in frame['conditions'])
    bad=approved_quality_candidate().model_dump(mode='json');bad['conditions'][0]['value']=PRIVATE
    result=S.safe_quality(draft,bad)
    assert result['status']=='rejected' and PRIVATE not in C.canonical(result)


def test_retry2_capture_wraps_existing_typed_return_without_transport(tmp_path):
    scope,source,witness,journal,clock=retry2_inputs(tmp_path)
    session=NS(lease=NS(expires=clock.wall()+timedelta(minutes=2)),phases=['start'],scope=scope,
               source=source,journal=journal,check=lambda:None)
    from unittest.mock import AsyncMock
    candidate=approved_quality_candidate()
    async def verifier(**kwargs):
        draft=M.Draft.model_validate(kwargs['prepare_body']['draft'])
        return await O.OpenAIMeaningGateway().propose(draft,attempt_id='synthetic')
    with patch.object(O.OpenAIMeaningGateway,'propose',new_callable=AsyncMock,return_value=candidate) as propose,patch.object(V,'verify_live',verifier):
        result=asyncio.run(S.verify_once(session,object(),object(),object(),C.AttemptObservation(0)))
    assert result is candidate and propose.await_count==1
    assert session.quality['status']=='validated'


def test_retry2_usage_in_fresh_ledger_is_retained_without_inventing_missing_tokens(tmp_path):
    scope,source,witness,journal,clock=retry2_inputs(tmp_path);journal.state=dict(rights=dict(count=1,generation=1))
    session=NS(scope=scope,journal=journal);snapshot=retry2_success_hooks(scope).snapshot_value
    attempt=next(iter(snapshot['attempts'].values()));observation=attempt['observation']
    assert 'usage' not in S.safe_ledger(snapshot,session)['attempts'][0]
    observation.update(input_tokens=100,output_tokens=10,total_tokens=110,cached_tokens=2,
                       price_sha256=C.digest(MEANING_SPEC['price']),model_sha256=C.hashlib.sha256(MEANING_SPEC['model'].encode()).hexdigest())
    captured=S.safe_ledger(snapshot,session)['attempts'][0]
    assert captured['usage']==dict(input_tokens=100,output_tokens=10,total_tokens=110,cached_tokens=2)
    assert captured['model']==MEANING_SPEC['model']
    observation['input_tokens']=True
    with pytest.raises(S.Closed,match='LEDGER_LIMIT'):S.safe_ledger(snapshot,session)


@pytest.mark.parametrize('meaning,code',[('rejected','MEANING_REJECTED'),('incomplete','MEANING_NOT_SUPPLEMENTED'),('unavailable','MEANING_NOT_SUPPLEMENTED')])
def test_observed_settlement_semantic_failure_has_distinct_fixed_code(tmp_path,meaning,code):
    scope,source,witness,journal,clock=retry2_inputs(tmp_path);hooks=retry2_success_hooks(scope)
    async def semantic_failure(**kwargs):
        value=await successor_verifier_spy(**kwargs)
        return value|dict(meaning_status=meaning)
    with patch.object(V,'verify_live',wraps=semantic_failure) as verify,pytest.raises(S.Closed,match=code):
        asyncio.run(S.run(scope,source=source,authority=witness.capability(),journal=journal,synthetic=True,hooks=hooks,clock=clock))
    account=next(x for x in journal.state['journal'] if x['phase']=='final_accounting')
    assert account['diagnostic']['failure_code']==code
    assert account['diagnostic']['verifier']['settlement']=='observed'
    assert account['diagnostic']['verifier']['meaning_status']==meaning
    assert account['ledger']['attempts'][0]['state']=='observed'
    assert hooks.cleaned==1 and hooks.preserved==0 and journal.state['status']=='closed'
    assert verify.call_count==1 and witness.calls.count('generation')==1
    assert account['reserved_nano']==300000000


def test_semantic_gate_diagnostic_accepts_only_exact_helper_type():
    class Impostor(Exception):code='MEANING_REJECTED'
    class Derived(S.Closed):pass
    for error in (Impostor(PRIVATE),Derived('MEANING_REJECTED'),RuntimeError('MEANING_REJECTED '+PRIVATE)):
        observation=C.AttemptObservation(0);S.observe_failure(observation,error)
        assert observation.snapshot()['failure_code']=='CONTROLLER_FAILED'
        assert PRIVATE not in C.canonical(observation.snapshot())
    observation=C.AttemptObservation(0);S.observe_failure(observation,S.Closed('MEANING_REJECTED'))
    assert observation.snapshot()['failure_code']=='MEANING_REJECTED'
