"""No Docker/DB/Google: mutated creation receipts, early-stop and copy regressions."""

from datetime import UTC, datetime, timedelta
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import json

import pytest

from scripts.runner_owned_database import (
    CreationReceipt,
    OwnedDatabaseError,
    RunnerOwnedDatabase,
    verify_metadata,
    LocalDocker,
)


def fixture_metadata():
    now = datetime.now(UTC)
    receipt = CreationReceipt(
        "a" * 64,
        "synthetic-owned",
        "synthetic-nonce",
        now - timedelta(seconds=1),
        now + timedelta(seconds=1),
    )
    info = dict(
        Id="a" * 64,
        Created=now.isoformat(),
        Running=True,
        Status="running",
        Image="pgvector/pgvector:pg16",
        Labels={
            "verith.task": "CF-002-interactive",
            "verith.resource_id": "synthetic-owned",
            "verith.nonce": "synthetic-nonce",
        },
        Mounts=[],
        Readonly=True,
        Tmpfs={
            "/var/lib/postgresql/data": "rw",
            "/var/run/postgresql": "rw",
            "/tmp": "rw",
        },
        Network="bridge",
        Privileged=False,
        VolumesFrom=None,
        Binds=None,
        Links=None,
        PidMode="",
        IpcMode="private",
        PortBindings={"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": ""}]},
        Ports={"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "6550"}]},
    )
    return receipt, info


def test_created_receipt_and_recheck_are_exact():
    receipt, info = fixture_metadata()
    created, port = verify_metadata(receipt, info)
    assert port == 6550
    verify_metadata(replace(receipt, created_at=created, bound_port=port), info)


@pytest.mark.parametrize(
    "field,value",
    [
        ("Id", "b" * 64),
        ("Created", "2000-01-01T00:00:00Z"),
        ("Readonly", False),
        ("Privileged", True),
        ("Mounts", [{"Type": "bind"}]),
        ("Binds", ["/fake:/fake"]),
        ("VolumesFrom", ["old"]),
        ("Network", "host"),
        ("PidMode", "host"),
        ("IpcMode", "host"),
        ("Links", ["old"]),
        ("Image", "postgres:latest"),
        ("Tmpfs", {"/tmp": "rw"}),
        ("Running", False),
        ("Status", "exited"),
        ("PortBindings", {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "6550"}]}),
        ("Ports", {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "15432"}]}),
        ("Ports", {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "6550"}]}),
        (
            "Ports",
            {
                "5432/tcp": [
                    {"HostIp": "127.0.0.1", "HostPort": "6550"},
                    {"HostIp": "::1", "HostPort": "6550"},
                ]
            },
        ),
    ],
)
def test_bad_ownership_metadata_is_rejected(field, value):
    receipt, info = fixture_metadata()
    info[field] = value
    with pytest.raises(OwnedDatabaseError):
        verify_metadata(receipt, info)


@pytest.mark.parametrize("label", ["verith.task", "verith.resource_id", "verith.nonce"])
def test_marker_alone_is_not_ownership(label):
    receipt, info = fixture_metadata()
    info["Labels"][label] = "forged"
    with pytest.raises(OwnedDatabaseError):
        verify_metadata(receipt, info)


def test_existing_timestamp_or_changed_binding_rejected():
    receipt, info = fixture_metadata()
    with pytest.raises(OwnedDatabaseError):
        verify_metadata(replace(receipt, created_at="different"), info)
    with pytest.raises(OwnedDatabaseError):
        verify_metadata(replace(receipt, bound_port=6551), info)


def test_external_config_cannot_mint_proof():
    with pytest.raises(OwnedDatabaseError):
        RunnerOwnedDatabase(None, {"url": "fake", "nonce": "fake"})


@pytest.mark.parametrize(
    "endpoint",
    [
        "ssh://remote",
        "tcp://127.0.0.1:2375",
        "https://remote",
        "unix:///unapproved/forward.sock",
    ],
)
def test_remote_or_unknown_daemon_is_refused(endpoint):
    execute = Mock(
        return_value=SimpleNamespace(returncode=0, stdout=json.dumps(endpoint))
    )
    with pytest.raises(OwnedDatabaseError):
        LocalDocker(execute=execute)
    assert execute.call_count == 1


async def test_failed_readonly_preflight_precedes_engine_migration_or_apps(monkeypatch):
    from scripts.cf002_interactive_login import migrate_owned
    import sqlalchemy.ext.asyncio as sa

    create = Mock(side_effect=AssertionError("No engine before attestation"))
    monkeypatch.setattr(sa, "create_async_engine", create)
    proof = SimpleNamespace(preflight=AsyncMock(side_effect=OwnedDatabaseError()))
    with pytest.raises(OwnedDatabaseError):
        await migrate_owned(proof)
    create.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        "Cannot connect to the Docker daemon at unix:///fake/socket",
        "permission denied: fake-secret-do-not-log",
        "request timed out",
        "Error: No such object: another-id",
    ],
)
def test_inspect_failure_does_not_count_as_absence(error):
    docker = LocalDocker.__new__(LocalDocker)
    docker.call = Mock(
        return_value=SimpleNamespace(returncode=1, stdout="", stderr=error)
    )
    with pytest.raises(OwnedDatabaseError, match="unconfirmed") as caught:
        docker.absent("a" * 64)
    assert "fake-secret" not in str(caught.value)


def test_only_exact_not_found_confirms_absence():
    docker = LocalDocker.__new__(LocalDocker)
    docker.call = Mock(
        return_value=SimpleNamespace(
            returncode=1, stdout="", stderr="Error: No such object: " + "a" * 64
        )
    )
    assert docker.absent("a" * 64)


def test_stopped_owned_resource_cleanup_retry_and_idempotence():
    from scripts.runner_owned_database import OwnedPostgres

    receipt, info = fixture_metadata()
    receipt = replace(receipt, created_at=info["Created"], bound_port=6550)
    info.update(Running=False, Status="exited", Ports={"5432/tcp": None})
    docker = SimpleNamespace(
        absent=Mock(side_effect=[False, False, True]),
        inspect=Mock(return_value=info),
        call=Mock(),
    )
    owner = OwnedPostgres(docker)
    owner.receipt = receipt
    docker.call.side_effect = [OwnedDatabaseError(), None]
    with pytest.raises(OwnedDatabaseError):
        owner.cleanup()
    assert not owner._removed
    owner.cleanup()
    owner.cleanup()
    assert owner._removed
    assert docker.call.call_count == 2
    assert all(call.args[0] == "rm" for call in docker.call.call_args_list)


def test_cleanup_absence_error_keeps_receipt_and_retryable_state():
    from scripts.runner_owned_database import OwnedPostgres

    receipt, info = fixture_metadata()
    docker = SimpleNamespace(
        absent=Mock(
            side_effect=[
                False,
                OwnedDatabaseError("Owned resource absence is unconfirmed"),
            ]
        ),
        inspect=Mock(return_value=info),
        call=Mock(),
    )
    owner = OwnedPostgres(docker)
    owner.receipt = replace(receipt, created_at=info["Created"], bound_port=6550)
    with pytest.raises(OwnedDatabaseError):
        owner.cleanup()
    assert not owner._removed and owner.receipt.container_id == "a" * 64

# Preserve the unchanged worker's collection/exit origin invariant while selecting
# only this file. These already-pinned pure modules do not execute cache I/O.
import sys
from pathlib import Path
_AI_COPY = Path(__file__).resolve().parents[3] / 'ai/src'
sys.path.append(str(_AI_COPY))
try:
    from agents.flow.api import payload as _origin_payload
    from agents.flow.domain import models as _origin_models, observation_window as _origin_window
    from agents.flow.infrastructure import token_cache as _origin_cache
finally:
    sys.path.remove(str(_AI_COPY))


class SyntheticClock:
    def __init__(self):self.now=0;self.sleeps=[]
    def monotonic(self):return self.now
    def sleep(self,seconds):self.sleeps.append(seconds);self.now+=seconds


@pytest.fixture(autouse=True)
def owned_private_cleanup_evidence(tmp_path,monkeypatch):
    """All old/new failure tests keep private evidence in this owned test tmp."""
    import tempfile
    from scripts import runner_owned_database as module
    original=tempfile.mkdtemp;created=[]
    def owned_mkdtemp(*,prefix):
        value=original(prefix=prefix,dir=tmp_path);created.append(Path(value));return value
    monkeypatch.setattr(module,'tempfile',SimpleNamespace(mkdtemp=owned_mkdtemp,TemporaryDirectory=tempfile.TemporaryDirectory))
    yield
    for directory in created:
        if not directory.exists():continue
        for name in ('receipt.json','cleanup-failed.json','cleanup-confirmed_absent.json'):
            file=directory/name
            if file.exists():file.unlink()
        directory.rmdir()


def test_post_start_projection_settles_using_same_original_receipt(monkeypatch):
    import copy
    from scripts import runner_owned_database as module
    receipt, info = fixture_metadata()
    receipt = replace(receipt, created_at=info['Created'])
    pending = copy.deepcopy(info);pending['Ports'] = {'5432/tcp': None}
    docker = SimpleNamespace(inspect=Mock(side_effect=[pending, pending, info]), call=Mock())
    owner = module.OwnedPostgres(docker);owner.receipt = receipt
    seen=[];original=module.verify_metadata;clock=SyntheticClock()
    def checked(actual, metadata, **kwargs):
        seen.append(actual)
        return original(actual, metadata, **kwargs)
    monkeypatch.setattr(module, 'verify_metadata', checked)
    monkeypatch.setattr(module,'time',clock)
    assert owner._verify_post_start(info) == (info['Created'], 6550)
    assert len(seen)==4 and all(value is receipt for value in seen)
    assert owner.receipt is receipt and clock.sleeps == [2,2]
    docker.call.assert_not_called()


@pytest.mark.parametrize('mutation', ['nonce','Created','binding','readonly'])
def test_post_start_never_accepts_changed_ownership_or_widens_guard(monkeypatch,mutation):
    import copy
    from scripts import runner_owned_database as module
    receipt,info=fixture_metadata();receipt=replace(receipt,created_at=info['Created'])
    bad=copy.deepcopy(info)
    if mutation=='nonce':bad['Labels']['verith.nonce']='different'
    elif mutation=='Created':bad['Created']=(datetime.now(UTC)-timedelta(days=1)).isoformat()
    elif mutation=='binding':bad['Ports']['5432/tcp'][0]['HostIp']='0.0.0.0'
    else:bad['Readonly']=False
    docker=SimpleNamespace(inspect=Mock(return_value=bad),call=Mock())
    owner=module.OwnedPostgres(docker);owner.receipt=receipt
    monkeypatch.setattr(module,'time',SyntheticClock())
    with pytest.raises(OwnedDatabaseError):owner._verify_post_start(info)
    assert docker.inspect.call_count==1 and owner.receipt is receipt
    docker.call.assert_not_called()


def test_post_start_transport_error_is_not_retried(monkeypatch):
    from scripts import runner_owned_database as module
    receipt,info=fixture_metadata();docker=SimpleNamespace(inspect=Mock(side_effect=OwnedDatabaseError()),call=Mock())
    owner=module.OwnedPostgres(docker);owner.receipt=receipt
    clock=SyntheticClock();monkeypatch.setattr(module,'time',clock)
    with pytest.raises(OwnedDatabaseError):owner._verify_post_start(info)
    assert docker.inspect.call_count==1 and not clock.sleeps;docker.call.assert_not_called()


def test_post_start_scheduling_deadline_is_bounded(monkeypatch):
    from scripts import runner_owned_database as module
    receipt,info=fixture_metadata();info['Running']=False;info['Status']='created';info['Ports']={}
    docker=SimpleNamespace(inspect=Mock(return_value=info),call=Mock())
    owner=module.OwnedPostgres(docker);owner.receipt=receipt
    clock=SyntheticClock()
    def overrun(seconds):clock.sleeps.append(seconds);clock.now+=5
    clock.sleep=overrun;monkeypatch.setattr(module,'time',clock)
    with pytest.raises(OwnedDatabaseError):owner._verify_post_start(info)
    assert docker.inspect.call_count==1 and clock.sleeps==[2]


@pytest.mark.parametrize('stage', ['create','cleanup'])
def test_failure_preserves_original_private_receipt_without_credentials(stage):
    import stat
    from scripts import runner_owned_database as module
    receipt,info=fixture_metadata();receipt=replace(receipt,created_at=info['Created'],bound_port=6550)
    docker=SimpleNamespace(inspect=Mock(),call=Mock())
    owner=module.OwnedPostgres(docker);owner.receipt=receipt
    owner._password='synthetic-db-password-never-persist';owner._admin_password='synthetic-admin-password-never-persist'
    failed=Mock(side_effect=OwnedDatabaseError())
    setattr(owner,'_'+stage,failed)
    with pytest.raises(OwnedDatabaseError):getattr(owner,stage)()
    file=owner.cleanup_receipt_path
    assert stat.S_IMODE(file.stat().st_mode)==0o600 and stat.S_IMODE(file.parent.stat().st_mode)==0o700
    assert not file.is_symlink() and file.stat().st_nlink==1
    raw=file.read_text();value=json.loads(raw)
    assert value==dict(version=1,container_id=receipt.container_id,resource_id=receipt.resource_id,nonce=receipt.nonce,requested_at=receipt.requested_at.isoformat(),returned_at=receipt.returned_at.isoformat(),created_at=receipt.created_at,bound_port=receipt.bound_port,stage=stage,cleanup_result='failed' if stage=='cleanup' else 'not_attempted',complete=True)
    assert owner._password not in raw and owner._admin_password not in raw
    assert not {'password','database','role','url','Env'} & value.keys()
    first=(raw,file.stat().st_ino);owner._preserve_cleanup_receipt()
    assert (file.read_text(),file.stat().st_ino)==first and owner.receipt is receipt
    # Only the test's exact synthetic evidence is removed.
    for name in ('receipt.json','cleanup-failed.json','cleanup-confirmed_absent.json'):
        target=file.parent/name
        if target.exists():target.unlink()
    file.parent.rmdir()


def test_failure_before_minting_does_not_invent_receipt():
    from scripts import runner_owned_database as module
    owner=module.OwnedPostgres(SimpleNamespace())
    owner._create=Mock(side_effect=OwnedDatabaseError())
    with pytest.raises(OwnedDatabaseError):owner.create()
    assert owner.receipt is None and owner.cleanup_receipt_path is None


def test_post_start_three_reads_and_each_remaining_timeout(monkeypatch):
    from scripts import runner_owned_database as module
    import copy
    receipt,initial=fixture_metadata();pending=copy.deepcopy(initial);pending['Ports']={}
    docker=SimpleNamespace(inspect=Mock(return_value=pending),call=Mock())
    owner=module.OwnedPostgres(docker);owner.receipt=receipt
    clock=SyntheticClock();monkeypatch.setattr(module,'time',clock)
    with pytest.raises(OwnedDatabaseError):owner._verify_post_start(initial)
    assert docker.inspect.call_count==3 and clock.sleeps==[2,2]
    timeouts=[call.kwargs['timeout'] for call in docker.inspect.call_args_list]
    assert all(0<value<=5 for value in timeouts) and timeouts==sorted(timeouts,reverse=True)
    assert owner.receipt is receipt;docker.call.assert_not_called()


def test_slow_completed_inspect_is_not_accepted_after_five_seconds(monkeypatch):
    from scripts import runner_owned_database as module
    receipt,info=fixture_metadata();clock=SyntheticClock()
    def delayed(*args,**kwargs):clock.now=5;return info
    docker=SimpleNamespace(inspect=Mock(side_effect=delayed),call=Mock())
    owner=module.OwnedPostgres(docker);owner.receipt=receipt
    monkeypatch.setattr(module,'time',clock)
    with pytest.raises(OwnedDatabaseError):owner._verify_post_start(info)
    assert docker.inspect.call_count==1 and not clock.sleeps


@pytest.mark.parametrize('timeout',[0,-1,16,float('inf'),float('nan'),True])
def test_docker_timeout_never_exceeds_existing_limit(timeout):
    docker=LocalDocker.__new__(LocalDocker);docker._execute=Mock()
    with pytest.raises(OwnedDatabaseError):docker.call('inspect','synthetic',timeout=timeout)
    docker._execute.assert_not_called()


def test_original_receipt_tampering_rejects_before_any_inspect():
    from scripts import runner_owned_database as module
    receipt,info=fixture_metadata()
    for changed in (replace(receipt,nonce='forged'),replace(receipt,container_id='b'*64),replace(receipt,created_at='different'),replace(receipt,requested_at=receipt.requested_at+timedelta(days=1))):
        docker=SimpleNamespace(inspect=Mock(),call=Mock())
        owner=module.OwnedPostgres(docker);owner.receipt=changed
        with pytest.raises(OwnedDatabaseError):owner._verify_post_start(info)
        docker.inspect.assert_not_called();docker.call.assert_not_called()


def test_partial_cleanup_side_record_is_not_a_complete_outcome():
    import os
    from scripts import runner_owned_database as module
    receipt,_=fixture_metadata();owner=module.OwnedPostgres(SimpleNamespace());owner.receipt=receipt
    owner._preserve_cleanup_receipt()
    file=owner.cleanup_receipt_path.parent/'cleanup-failed.json'
    fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:output.write('{"stage":"cleanup"')
    before=file.read_bytes()
    with pytest.raises(OwnedDatabaseError):owner._record_cleanup_outcome('failed')
    assert file.read_bytes()==before


def test_complete_private_cleanup_outcomes_are_idempotent():
    import stat
    from scripts import runner_owned_database as module
    receipt,_=fixture_metadata();owner=module.OwnedPostgres(SimpleNamespace());owner.receipt=receipt
    owner._preserve_cleanup_receipt()
    for outcome in ('failed','confirmed_absent'):
        owner._record_cleanup_outcome(outcome)
        file=owner.cleanup_receipt_path.parent/('cleanup-'+outcome+'.json')
        assert json.loads(file.read_text())=={'stage':'cleanup','result':outcome,'complete':True}
        assert stat.S_IMODE(file.stat().st_mode)==0o600
        before=(file.read_bytes(),file.stat().st_ino)
        owner._record_cleanup_outcome(outcome)
        assert (file.read_bytes(),file.stat().st_ino)==before

@pytest.mark.parametrize('case,expected',[
    ('cid','CID'),('labels','LABELS'),('time','CREATED_WINDOW'),('created','CREATED_FIXED'),
    ('flags','CONTAINER_FLAGS'),('mounts','MOUNTS'),('namespace','NAMESPACE'),('tmpfs','TMPFS'),
    ('requested_layout','REQUESTED_BINDING_LAYOUT'),('requested_host','REQUESTED_BINDING_HOST'),
    ('running','RUNNING_STATUS'),('live_layout','LIVE_PORT_LAYOUT'),('live_cardinality','LIVE_PORT_CARDINALITY'),
    ('live_value','LIVE_PORT_VALUE'),('live_host','LIVE_BINDING'),('bound','BOUND_PORT_FIXED'),
    ('stopped_status','STOPPED_STATUS'),('stopped_layout','STOPPED_PORT_LAYOUT'),
    ('stopped_cardinality','STOPPED_PORT_CARDINALITY'),('stopped_binding','STOPPED_BINDING'),
    ('requested_port','REQUESTED_BINDING_PORT'),
])
def test_fixed_predicate_diagnostic_matches_original_guard_failure(case,expected):
    from scripts import runner_owned_database as module
    receipt,info=fixture_metadata();running=True
    sentinel='SYNTHETIC-SECRET-NEVER-LOG'
    if case=='cid':info['Id']=sentinel
    elif case=='labels':info['Labels']['verith.nonce']=sentinel
    elif case=='time':info['Created']='2000-01-01T00:00:00Z'
    elif case=='created':receipt=replace(receipt,created_at=sentinel)
    elif case=='flags':info['Readonly']=False
    elif case=='mounts':info['Mounts']=[sentinel]
    elif case=='namespace':info['Network']=sentinel
    elif case=='tmpfs':info['Tmpfs']={}
    elif case=='requested_layout':info['PortBindings']={}
    elif case=='requested_host':info['PortBindings']['5432/tcp'][0]['HostIp']=sentinel
    elif case=='running':info['Running']=False
    elif case=='live_layout':info['Ports']={}
    elif case=='live_cardinality':info['Ports']={'5432/tcp':None}
    elif case=='live_value':info['Ports']['5432/tcp'][0]['HostPort']=sentinel
    elif case=='live_host':info['Ports']['5432/tcp'][0]['HostIp']=sentinel
    elif case=='bound':receipt=replace(receipt,bound_port=6551)
    elif case=='requested_port':info['PortBindings']['5432/tcp'][0]['HostPort']=sentinel
    else:
        running=False;info.update(Running=False,Status='exited')
        if case=='stopped_status':info['Status']=sentinel
        elif case=='stopped_layout':info['Ports']={sentinel:None}
        elif case=='stopped_cardinality':info['Ports']={'5432/tcp':[{},{}]}
    with pytest.raises(OwnedDatabaseError) as caught:verify_metadata(receipt,info,require_running=running)
    result=module.metadata_failure_diagnostic(caught.value)
    assert result['predicate']==expected
    assert result['exception_kind'] in {'KeyError','ValueError','TypeError','AttributeError'}
    assert sentinel not in json.dumps(result) and set(result)=={'predicate','exception_kind'}


@pytest.mark.parametrize('internal_shift',[False,True])
def test_predicate_source_position_change_is_fail_closed(tmp_path,monkeypatch,internal_shift):
    import inspect
    from scripts import runner_owned_database as module
    original=inspect.getsource(module.verify_metadata)
    source=original.replace('    try:','    # inserted source line\n    try:',1) if internal_shift else '\n'*7+original
    file=tmp_path/'synthetic_verify.py';file.write_text(source)
    namespace=dict(vars(module));exec(compile(source,str(file),'exec'),namespace)
    changed=namespace['verify_metadata']
    monkeypatch.setattr(module,'verify_metadata',changed);monkeypatch.setattr(module,'_VERIFY_METADATA_FUNCTION',changed)
    receipt,info=fixture_metadata();info['Id']='synthetic-secret-not-a-CID'
    with pytest.raises(OwnedDatabaseError) as caught:changed(receipt,info)
    result=module.metadata_failure_diagnostic(caught.value)
    assert result['predicate']==('UNKNOWN' if internal_shift else 'CID')
    assert 'synthetic-secret' not in json.dumps(result)


def test_unknown_exception_and_message_never_become_diagnostic():
    from scripts import runner_owned_database as module
    try:raise RuntimeError('synthetic-private-message-nonce-env-time')
    except RuntimeError as error:result=module.metadata_failure_diagnostic(error)
    assert result=={'predicate':'UNKNOWN','exception_kind':'OTHER'}


def test_new_helper_frames_are_not_lost_and_never_expose_locals():
    import ast
    root=Path(__file__).resolve().parents[2]
    tree=ast.parse((root/'scripts/cf002_interactive_login.py').read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='cf003_failure_diagnostic')
    namespace={'_BACKEND':root}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'synthetic-diagnostic','exec'),namespace)
    synthetic={}
    exec(compile("def _create():\n    return _verify_post_start()\ndef _verify_post_start():\n    return verify_metadata()\ndef verify_metadata():\n    hidden='SYNTHETIC-SECRET-NEVER-LOG'\n    raise RuntimeError(hidden)\n",str(root/'scripts/runner_owned_database.py'),'exec'),synthetic)
    try:synthetic['_create']()
    except RuntimeError as error:result=namespace['cf003_failure_diagnostic'](error,'owned_creation')
    assert [v['function'] for v in result['frames']]==['_create','_verify_post_start','verify_metadata']
    assert 'SYNTHETIC-SECRET' not in json.dumps(result) and str(root) not in json.dumps(result)


def test_post_start_failure_records_safe_phase_attempt_and_predicate(monkeypatch):
    import copy
    from scripts import runner_owned_database as module
    receipt,initial=fixture_metadata();pending=copy.deepcopy(initial);pending['Ports']={'5432/tcp':None}
    owner=module.OwnedPostgres(SimpleNamespace(inspect=Mock(return_value=pending)))
    owner.receipt=receipt;monkeypatch.setattr(module,'time',SyntheticClock())
    with pytest.raises(OwnedDatabaseError):owner._verify_post_start(initial)
    assert owner.metadata_failures==[{'phase':'post_start_poll','attempt':number,'predicate':'LIVE_PORT_CARDINALITY','exception_kind':'TypeError','transient_eligible':True} for number in (1,2,3)]


def test_post_start_reads_are_distributed_at_zero_two_four(monkeypatch):
    import copy
    from scripts import runner_owned_database as module
    receipt,initial=fixture_metadata();pending=copy.deepcopy(initial);pending['Ports']={'5432/tcp':[]}
    clock=SyntheticClock();times=[];timeouts=[]
    def read(identifier,*,timeout):
        times.append(clock.now);timeouts.append(timeout)
        return initial if len(times)==3 else pending
    docker=SimpleNamespace(inspect=Mock(side_effect=read),call=Mock())
    owner=module.OwnedPostgres(docker);owner.receipt=receipt
    monkeypatch.setattr(module,'time',clock)
    assert owner._verify_post_start(initial)==(initial['Created'],6550)
    assert times==[0,2,4] and timeouts==[5,3,1] and clock.sleeps==[2,2]
    assert owner.receipt is receipt;docker.call.assert_not_called()


def test_post_start_IO_time_does_not_drift_absolute_targets(monkeypatch):
    import copy
    from scripts import runner_owned_database as module
    receipt,initial=fixture_metadata();pending=copy.deepcopy(initial);pending['Ports']={'5432/tcp':[]}
    clock=SyntheticClock();times=[]
    def read(identifier,*,timeout):
        times.append(clock.now);clock.now+=.3
        return initial if len(times)==3 else pending
    owner=module.OwnedPostgres(SimpleNamespace(inspect=Mock(side_effect=read)))
    owner.receipt=receipt;monkeypatch.setattr(module,'time',clock)
    owner._verify_post_start(initial)
    assert times==pytest.approx([0,2,4]) and clock.sleeps==pytest.approx([1.7,1.7])


def test_scheduled_projection_failure_preserves_receipt_and_refuses_cleanup(monkeypatch):
    import copy
    from scripts import runner_owned_database as module
    receipt,initial=fixture_metadata();receipt=replace(receipt,created_at=initial['Created'])
    pending=copy.deepcopy(initial);pending['Ports']={'5432/tcp':[]}
    clock=SyntheticClock();times=[]
    def read(*args,**kwargs):times.append(clock.now);return pending
    docker=SimpleNamespace(inspect=Mock(side_effect=read),absent=Mock(return_value=False),call=Mock())
    owner=module.OwnedPostgres(docker);owner.receipt=receipt
    owner._create=Mock(side_effect=lambda:owner._verify_post_start(initial))
    monkeypatch.setattr(module,'time',clock)
    with pytest.raises(OwnedDatabaseError):owner.create()
    assert times==[0,2,4]
    with pytest.raises(OwnedDatabaseError):owner.cleanup()
    assert owner.receipt is receipt and not owner._removed
    data=json.loads(owner.cleanup_receipt_path.read_text())
    assert data['nonce']==receipt.nonce and data['requested_at']==receipt.requested_at.isoformat()
    assert data['returned_at']==receipt.returned_at.isoformat() and data['created_at']==receipt.created_at
    assert json.loads((owner.cleanup_receipt_path.parent/'cleanup-failed.json').read_text())=={'stage':'cleanup','result':'failed','complete':True}
    docker.call.assert_not_called()
