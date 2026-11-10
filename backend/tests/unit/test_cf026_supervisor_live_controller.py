"""Fixed controller collection; no Docker/provider/key/config on import."""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib.abc
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS
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
    expected=root.parent/'verith/backend'/'.env'
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
            with pytest.raises(C.ControllerError,match='AGGREGATE_EXPIRED'):await C.aggregate_authorized(permission)
            h['expires_at']=(C.AGGREGATE_END+timedelta(seconds=1)).isoformat()
            with pytest.raises(C.ControllerError,match='AGGREGATE_SCOPE'):C.aggregate_header(permission)
        assert not permission.path.exists()
    with patch.object(C,'datetime',Future):asyncio.run(run())
