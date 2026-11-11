"""Private approval orchestration; import never loads credentials, apps or env."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from uuid import UUID


class ControllerError(RuntimeError):
    def __init__(self, stage="CONTROLLER_UNAVAILABLE"):
        allowed = {
            "CONTROLLER_UNAVAILABLE", "CONTROLLER_FAILED", "ACCOUNTING_ACK_UNKNOWN",
            "APPROVAL_ALREADY_USED", "APPROVAL_BUSY", "APPROVAL_EXPIRED",
            "APPROVAL_SCOPE", "APPROVAL_STORE_SCOPE", "APPROVAL_TIME_INVALID",
            "CLEANUP_UNCONFIRMED", "COUNTER_EVIDENCE_INVALID", "DUPLICATE_FIELD",
            "EPOCH_ACK_UNKNOWN", "EPOCH_ALREADY_EXISTS", "EPOCH_LOST",
            "EXTERNAL_APPROVAL_REQUIRED", "FILE_DRIFT", "FILE_IDENTITY_DENIED",
            "FINAL_LEDGER_UNCONFIRMED", "FIRST_SETTLEMENT_UNCONFIRMED",
            "INPUT_MAPPING_UNPROVED", "INVALID_PRIVATE_JSON", "ISOLATION_DENIAL",
            "KEY_SOURCE_DRIFT", "KEY_SOURCE_INVALID", "KEY_SOURCE_SCOPE",
            "KEY_SUPPLY_DENIED", "LIVE_GATE_CLOSED", "LOCK_DRIFT", "LOCK_REQUIRED",
            "PHASE_ORDER", "PHASE_SCOPE", "PRIVATE_DIRECTORY_DRIFT",
            "PRIVATE_DIRECTORY_INVALID", "PRIVATE_STATE_INVALID", "PRIVATE_STATE_LIMIT",
            "RESOURCE_CREATION_UNKNOWN", "RESOURCE_DEADLINE", "SETTLEMENT_UNCONFIRMED",
            "STATE_ACK_UNKNOWN", "STATE_TRANSITION_DENIED", "SYMLINK_DENIED",
            "SYNTHETIC_DIRECTORY_NOT_EMPTY", "SYNTHETIC_EXPECTATION", "SYNTHETIC_RESTART_NOT_BLOCKED",
            "DIAGNOSTIC_INVALID", "CANCELLED", "TIMED_OUT",
            "CONTINUATION_INVALID", "CONTINUATION_USED", "CONTINUATION_ANCESTRY",
            "CONTINUATION_PHASE", "CONTINUATION_LIMIT", "CONTINUATION_ACK_UNKNOWN",
            "AGGREGATE_SCOPE", "AGGREGATE_FROZEN", "AGGREGATE_HEAD", "AGGREGATE_ACK_UNKNOWN",
            "AGGREGATE_LIMIT", "AGGREGATE_USED", "AGGREGATE_EXPIRED", "AGGREGATE_HISTORY",
        }
        self.stage = stage if type(stage) is str and stage in allowed else "CONTROLLER_UNAVAILABLE"
        super().__init__(self.stage)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def failure_summary(error):
    if error is None:
        return None
    frames = []
    trace = error.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code.co_filename == __file__:
            frames.append(dict(function=trace.tb_frame.f_code.co_name, line=trace.tb_lineno))
        trace = trace.tb_next
    kinds = {"ControllerError", "CancelledError", "TimeoutError", "OSError", "OwnedDatabaseError", "IntegrityError", "AssertionError"}
    return dict(kind=type(error).__name__ if type(error).__name__ in kinds else "other", frames=frames[-8:])


VERIFIER_STAGES = frozenset({
    "preflight_verified", "claim_ACK_identity_verified", "count_reservation_ACK",
    "generation_reservation_ACK", "settlement_ACK", "hold_ACK", "preparation_owner_readback",
    "synthetic_key_supplied", "mock_count", "mock_generation",
})
MEANING_STATUSES = frozenset({
    "pending", "deterministic", "supplemented", "unavailable", "rejected", "incomplete",
    "unsupported", "counter_unavailable", "failed", "unknown", "expired", "deleted", "consumed",
})
SETTLEMENTS = frozenset({"observed", "hold", "unconfirmed", "not_called"})
SUPPLIER_STAGES = frozenset({
    "entered", "approval_checked", "source_read_entered", "source_read_returned",
    "failed", "cancelled", "timed_out",
})


def normalized_failure(error):
    if isinstance(error, asyncio.CancelledError):
        return "CANCELLED"
    if isinstance(error, TimeoutError):
        return "TIMED_OUT"
    if type(error) is ControllerError:
        code = ControllerError(error.stage).stage
        return code
    return "CONTROLLER_FAILED"


class AttemptObservation:
    """Closed labels only. Supplier recording never accepts key bytes/values."""
    def __init__(self, index):
        if type(index) is not int or not 0 <= index < 2:
            raise ControllerError("DIAGNOSTIC_INVALID")
        self.index = index
        self.verifier_returned = False
        self.verifier = None
        self.supplier_stages = []
        self.generation_authority = False
        self.error_code = None

    def supplier(self, stage):
        if type(stage) is not str or stage not in SUPPLIER_STAGES or len(self.supplier_stages) >= 5:
            self.error_code = "DIAGNOSTIC_INVALID"
            raise ControllerError("DIAGNOSTIC_INVALID")
        self.supplier_stages.append(stage)

    def failed(self, error):
        if self.error_code is None:
            self.error_code = normalized_failure(error)

    def returned(self, value):
        self.verifier_returned = True
        if type(value) is dict:
            stages, meaning, settlement = value.get("stages"), value.get("meaning_status"), value.get("settlement")
            if type(stages) is list and len(stages) <= 16 and all(type(label) is str and label in VERIFIER_STAGES for label in stages) and type(meaning) is str and meaning in MEANING_STATUSES and type(settlement) is str and settlement in SETTLEMENTS:
                self.verifier = dict(stages=list(stages), meaning_status=meaning, settlement=settlement)
                return
        self.error_code = "DIAGNOSTIC_INVALID"
        raise ControllerError("DIAGNOSTIC_INVALID")

    def snapshot(self):
        verifier = self.verifier or dict(stages=None, meaning_status=None, settlement=None)
        stages = verifier["stages"] or []
        supplied = self.supplier_stages
        if "generation_reservation_ACK" in stages:
            segment, evidence = "generation_reservation_observed", ["generation_reservation_ACK"]
        elif self.generation_authority:
            segment, evidence = "count_gate_passed_before_generation_reservation", ["generation_authority_verified"]
        elif "entered" in supplied and any(label in supplied for label in ("failed", "cancelled", "timed_out")):
            segment, evidence = "supplier_failure", list(supplied)
        elif "source_read_returned" in supplied:
            segment, evidence = "after_supplier_http_unknown", ["source_read_returned"]
        elif not supplied:
            segment, evidence = "before_supplier", ["supplier_not_entered"]
        else:
            segment, evidence = "unknown", list(supplied)
        return dict(index=self.index, verifier_returned=self.verifier_returned,
                    verifier=verifier, supplier_stages=list(supplied),
                    generation_authority_verified=self.generation_authority,
                    failure_code=self.error_code, segment=segment, segment_evidence=evidence,
                    count_http="unknown", generation_http="unknown")


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ControllerError("DUPLICATE_FIELD")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        raise ControllerError("INVALID_PRIVATE_JSON") from None


def no_links(path):
    path = Path(path).absolute()
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ControllerError("SYMLINK_DENIED")
    return path


def identity(info):
    return dict(dev=info.st_dev, ino=info.st_ino, uid=info.st_uid,
                mode=stat.S_IMODE(info.st_mode), nlink=info.st_nlink,
                size=info.st_size, mtime_ns=info.st_mtime_ns)


def regular(path, mode):
    info = no_links(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != mode:
        raise ControllerError("FILE_IDENTITY_DENIED")
    return identity(info)


def read_fixed(path, mode, expected=None, limit=65536):
    before = regular(path, mode)
    if expected is not None and before != expected or before["size"] > limit:
        raise ControllerError("FILE_DRIFT")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if identity(os.fstat(fd)) != before:
            raise ControllerError("FILE_DRIFT")
        raw = os.read(fd, limit + 1)
        if len(raw) > limit or len(raw) != before["size"] or identity(os.fstat(fd)) != before or regular(path, mode) != before:
            raise ControllerError("FILE_DRIFT")
        return raw, before
    finally:
        os.close(fd)


def single_key(raw):
    """Only exact KEY=value, optional matching quotes; no escape/interpolation.

    Other lines are not interpreted. Any duplicate target, long line, ambiguous
    target syntax, CR/NUL, non-ASCII key or multiline value fails closed.
    """
    if type(raw) is not bytes or len(raw) > 65536 or b"\x00" in raw or b"\r" in raw:
        raise ControllerError("KEY_SOURCE_INVALID")
    found = []
    for line in raw.split(b"\n"):
        if len(line) > 4096:
            raise ControllerError("KEY_SOURCE_INVALID")
        if line.lstrip().startswith(b"#"):
            continue
        if b"OPENAI_API_KEY" not in line:
            continue
        match = re.fullmatch(rb"OPENAI_API_KEY=(.*)", line)
        if match is None:
            raise ControllerError("KEY_SOURCE_INVALID")
        value = match[1]
        if value[:1] in (b"'", b'"'):
            if len(value) < 2 or value[-1:] != value[:1]:
                raise ControllerError("KEY_SOURCE_INVALID")
            value = value[1:-1]
        if not 1 <= len(value) <= 512 or any(c < 33 or c > 126 for c in value) or any(c in value for c in b"'\"\\$`#"):
            raise ControllerError("KEY_SOURCE_INVALID")
        found.append(value)
    if len(found) != 1:
        raise ControllerError("KEY_SOURCE_INVALID")
    return found[0].decode("ascii")


@dataclass(frozen=True, repr=False)
class ReviewedCodeRoot:
    """Explicit launcher provenance, never an environment/CLI discovery fallback."""
    path: Path
    directory_identity: tuple
    controller_sha256: str

    def check(self):
        path = no_links(self.path)
        info = path.lstat()
        if path.name != "verith-supervisor-live-controller" or (info.st_dev, info.st_ino, info.st_uid, info.st_mode) != self.directory_identity or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise ControllerError("KEY_SOURCE_SCOPE")
        # Code provenance is a separate bounded input, never a credential/state
        # size exception. Those retain read_fixed's64KiB default.
        original, _ = read_fixed(path / "backend/scripts/cf026_supervisor_live_controller.py", 0o644, limit=131072)
        copied, _ = read_fixed(Path(__file__), 0o644, limit=131072)
        if hashlib.sha256(original).hexdigest() != self.controller_sha256 or hashlib.sha256(copied).hexdigest() != self.controller_sha256:
            raise ControllerError("KEY_SOURCE_SCOPE")

    def scope(self):
        return dict(path=str(self.path), directory_identity=list(self.directory_identity), controller_sha256=self.controller_sha256)


@dataclass(frozen=True, repr=False)
class KeySource:
    path: Path = field(repr=False)
    stamp: dict = field(repr=False)
    synthetic: bool = False
    code_root: ReviewedCodeRoot | None = field(default=None, repr=False)

    def scope(self):
        return dict(path=str(self.path), identity=self.stamp, synthetic=self.synthetic,
                    code_root=self.code_root.scope() if self.code_root else None)

    def check(self):
        if not self.synthetic:
            if type(self.code_root) is not ReviewedCodeRoot:
                raise ControllerError("KEY_SOURCE_SCOPE")
            self.code_root.check()
            expected = self.code_root.path.parent / "verith" / "ai" / ".env"
            if self.path != expected:
                raise ControllerError("KEY_SOURCE_SCOPE")
        if regular(self.path, 0o644) != self.stamp:
            raise ControllerError("KEY_SOURCE_DRIFT")

    async def read(self):
        self.check()
        raw, _ = read_fixed(self.path, 0o644, self.stamp)
        try:
            return single_key(raw)
        finally:
            raw = None  # Reference release only, not a claim of memory erasure.


class PrivateStore:
    """Externally provisioned grant/state/lock. Never creates an issued state."""
    def __init__(self, directory):
        self.directory = no_links(directory)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ControllerError("PRIVATE_DIRECTORY_INVALID")
        self.directory_identity = (info.st_dev, info.st_ino, info.st_uid, info.st_mode)
        self.lock_fd = None
        self.lock_stamp = None
        self.grant = self.state = None
        self.grant_stamp = self.state_stamp = None

    def scope(self):
        return dict(path=str(self.directory), directory_identity=list(self.directory_identity),
                    lock_identity=regular(self.directory / "execution.lock", 0o600))

    def check_directory(self):
        info = no_links(self.directory).lstat()
        if (info.st_dev, info.st_ino, info.st_uid, info.st_mode) != self.directory_identity:
            raise ControllerError("PRIVATE_DIRECTORY_DRIFT")

    @contextmanager
    def locked(self):
        self.check_directory()
        path = self.directory / "execution.lock"
        self.lock_stamp = regular(path, 0o600)
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if identity(os.fstat(fd)) != self.lock_stamp:
                raise ControllerError("LOCK_DRIFT")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ControllerError("APPROVAL_BUSY") from None
            self.lock_fd = fd
            self.reload(first=True)
            yield self
        finally:
            self.lock_fd = None
            os.close(fd)

    def reload(self, *, first=False):
        if self.lock_fd is None:
            raise ControllerError("LOCK_REQUIRED")
        self.check_directory()
        if identity(os.fstat(self.lock_fd)) != self.lock_stamp or regular(self.directory / "execution.lock", 0o600) != self.lock_stamp:
            raise ControllerError("LOCK_DRIFT")
        raw, grant_stamp = read_fixed(self.directory / "grant.json", 0o600, None if first else self.grant_stamp)
        grant = decode(raw)
        raw, state_stamp = read_fixed(self.directory / "state.json", 0o600, None if first else self.state_stamp)
        state = decode(raw)
        if not isinstance(grant, dict) or not isinstance(state, dict) or set(state) != {"schema", "approval_id", "grant_sha256", "status", "journal"} or state["schema"] != "cf026.state.v1" or state["approval_id"] != grant.get("approval_id") or state["grant_sha256"] != digest(grant) or state["status"] not in {"issued", "claimed", "closed"} or type(state["journal"]) is not list:
            raise ControllerError("PRIVATE_STATE_INVALID")
        self.grant, self.state = grant, state
        self.grant_stamp, self.state_stamp = grant_stamp, state_stamp

    def persist(self, status, event):
        self.reload()
        allowed = {"issued": {"claimed"}, "claimed": {"claimed", "closed"}, "closed": set()}
        if status not in allowed[self.state["status"]] or len(self.state["journal"]) >= 24:
            raise ControllerError("STATE_TRANSITION_DENIED")
        # Preserve the existing24-event cap, reserving final accounting, closing
        # and cleanup receipts before any additional nonterminal work can start.
        if len(self.state["journal"]) >= 21 and event.get("phase") not in {"final_accounting", "closing", "cleanup_confirmed"}:
            raise ControllerError("PRIVATE_STATE_LIMIT")
        state = self.state | {"status": status, "journal": [*self.state["journal"], event]}
        raw = canonical(state).encode()
        if len(raw) > 65536:
            raise ControllerError("PRIVATE_STATE_LIMIT")
        path = self.directory / "state.pending"
        fd = None
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            offset = 0
            while offset < len(raw):
                size = os.write(fd, raw[offset:])
                if not size:
                    raise ControllerError("STATE_ACK_UNKNOWN")
                offset += size
            os.fsync(fd)
            os.close(fd)
            fd = None
            # Recheck the old inode before replacement, never replace drift.
            self.reload()
            os.replace(path, self.directory / "state.json")
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            self.state_stamp = regular(self.directory / "state.json", 0o600)
            self.reload()
            if self.state != state:
                raise ControllerError("STATE_ACK_UNKNOWN")
        except BaseException:
            # A pending file or replaced-but-unacknowledged state is evidence.
            raise ControllerError("STATE_ACK_UNKNOWN") from None
        finally:
            if fd is not None:
                os.close(fd)


@dataclass(frozen=True, repr=False)
class ExternalApproval:
    """A trusted coordinator supplies verification, not an approved=true flag."""
    scope_sha256: str
    issuer: str
    verify: object = field(repr=False)


def parse_expiry(value):
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is None:
            raise ValueError()
        return stamp
    except (ValueError, TypeError):
        raise ControllerError("APPROVAL_TIME_INVALID") from None


def validate_scope(grant, key_source, *, synthetic):
    from scripts.cf023_supervisor_meaning_check import load_meaning
    load_meaning()
    from src.modules.supervisor.domain.contracts import MEANING_SPEC, MEANING_SPEC_SHA256, PreparationRequest
    from src.supervisor.infrastructure.openai_meaning_gateway import rendered_request, INPUT_FIELDS, ORIGIN, COUNT_PATH, GENERATE_PATH, COUNT_DOCUMENTATION
    required = {"schema", "approval_id", "issuer", "not_before", "expires_at", "mode", "epoch_id", "requests", "semantic_sha256", "price_sha256", "model", "tier", "origin", "endpoints", "max_nano", "attempt_nano", "max_attempts", "input_cap", "output_cap", "source", "counter", "state_store"}
    if set(grant) != required or grant["schema"] != "cf026.grant.v1" or grant["mode"] != ("synthetic" if synthetic else "live") or type(key_source) is not KeySource or key_source.synthetic is not synthetic or grant["source"] != key_source.scope():
        raise ControllerError("APPROVAL_SCOPE")
    try:
        UUID(grant["approval_id"]); UUID(grant["epoch_id"])
    except (ValueError, TypeError, AttributeError):
        raise ControllerError("APPROVAL_SCOPE") from None
    if (grant["semantic_sha256"], grant["price_sha256"], grant["model"], grant["tier"], grant["origin"], grant["endpoints"], grant["max_nano"], grant["attempt_nano"], grant["max_attempts"], grant["input_cap"], grant["output_cap"]) != (MEANING_SPEC_SHA256, digest(MEANING_SPEC["price"]), MEANING_SPEC["model"], "default", ORIGIN, [COUNT_PATH, GENERATE_PATH], 100000000, 50000000, 2, 16384, 2048):
        raise ControllerError("APPROVAL_SCOPE")
    counter = grant["counter"]
    if type(counter) is not dict or set(counter) != {"documentation_url", "documentation_sha256", "free_evidence_sha256", "price_evidence_sha256", "fee_bound_nano"} or counter["documentation_url"] != COUNT_DOCUMENTATION or type(counter["fee_bound_nano"]) is not int or counter["fee_bound_nano"] != 0 or any(not isinstance(counter[k], str) or re.fullmatch(r"[a-f0-9]{64}", counter[k]) is None for k in ("documentation_sha256", "free_evidence_sha256", "price_evidence_sha256")):
        raise ControllerError("COUNTER_EVIDENCE_INVALID")
    if not isinstance(grant["issuer"], str) or not grant["issuer"] or type(grant["requests"]) is not list or len(grant["requests"]) != 2:
        raise ControllerError("APPROVAL_SCOPE")
    keys = set()
    for item in grant["requests"]:
        if type(item) is not dict or set(item) != {"prepare_body", "draft_sha256", "request_sha256", "projection_sha256"}:
            raise ControllerError("APPROVAL_SCOPE")
        body = PreparationRequest.model_validate(item["prepare_body"])
        if body.parent_preparation_id is not None or body.model_dump(mode="json") != item["prepare_body"] or body.prepare_key in keys:
            raise ControllerError("APPROVAL_SCOPE")
        keys.add(body.prepare_key)
        request = rendered_request(body.draft)
        if set(request) != set(INPUT_FIELDS) | {"service_tier", "store", "stream", "max_output_tokens"}:
            raise ControllerError("INPUT_MAPPING_UNPROVED")
        if (item["draft_sha256"], item["request_sha256"], item["projection_sha256"]) != (digest(body.draft.model_dump(mode="json")), digest(request), digest({k: request[k] for k in INPUT_FIELDS})):
            raise ControllerError("APPROVAL_SCOPE")


async def approval_gate(store, approval, key_source, *, synthetic):
    store.reload()
    grant = store.grant
    if type(approval) is not ExternalApproval or not callable(approval.verify) or approval.scope_sha256 != digest(grant) or approval.issuer != grant["issuer"]:
        raise ControllerError("EXTERNAL_APPROVAL_REQUIRED")
    now = datetime.now(timezone.utc)
    if not parse_expiry(grant["not_before"]) <= now < parse_expiry(grant["expires_at"]):
        raise ControllerError("APPROVAL_EXPIRED")
    validate_scope(grant, key_source, synthetic=synthetic)
    if grant["state_store"] != store.scope():
        raise ControllerError("APPROVAL_STORE_SCOPE")
    key_source.check()
    remaining = min(5, (parse_expiry(grant["expires_at"]) - now).total_seconds())
    async with asyncio.timeout(remaining):
        if await approval.verify(scope_sha256=digest(grant), issuer=grant["issuer"], mode=grant["mode"], counter=dict(grant["counter"])) is not True:
            raise ControllerError("EXTERNAL_APPROVAL_REQUIRED")
    store.reload()
    if digest(store.grant) != approval.scope_sha256 or store.grant != grant:
        raise ControllerError("APPROVAL_SCOPE")
    if datetime.now(timezone.utc) >= parse_expiry(grant["expires_at"]):
        raise ControllerError("APPROVAL_EXPIRED")


class ControllerAuthority:
    def __init__(self, store, approval, source, proof, binding, principal, item, deferred, observation=None):
        self.store, self.approval, self.source = store, approval, source
        self.proof, self.binding, self.principal = proof, binding, principal
        self.item, self.deferred = item, deferred
        self.phases = []
        self.observation = observation

    async def verify(self, **scope):
        await approval_gate(self.store, self.approval, self.source, synthetic=False)
        if self.store.state["status"] != "claimed" or scope.get("mode") != "live" or scope.get("proof_binding") is not self.binding or scope.get("principal") is not self.principal or scope.get("key_supplier") is not self.deferred or scope.get("key_source_capability") is not self.source or scope.get("draft_sha256") != self.item["draft_sha256"] or scope.get("semantic_sha256") != self.store.grant["semantic_sha256"]:
            raise ControllerError("PHASE_SCOPE")
        phase = scope.get("phase")
        expected = ["initial", "preflight", "count", "generation"]
        if len(self.phases) >= 4 or phase != expected[len(self.phases)]:
            raise ControllerError("PHASE_ORDER")
        if phase != "initial" and (scope.get("request_sha256"), scope.get("projection_sha256")) != (self.item["request_sha256"], self.item["projection_sha256"]):
            raise ControllerError("PHASE_SCOPE")
        agreement = scope.get("agreement")
        from src.supervisor.infrastructure.openai_meaning_gateway import CounterAgreement, INPUT_FIELDS
        if type(agreement) is not CounterAgreement or agreement.input_fields != INPUT_FIELDS or agreement.counting_fee_bound_nano != 0 or agreement.documentation_sha256 != self.store.grant["counter"]["documentation_sha256"]:
            raise ControllerError("PHASE_SCOPE")
        # Existing PhaseBudget separately validates actual preparation/attempt,
        # fresh SQL Principal and reservation on the same attested connection.
        self.phases.append(phase)
        if phase == "generation" and self.observation is not None:
            self.observation.generation_authority = True
        return parse_expiry(self.store.grant["expires_at"])


@contextmanager
def bounded_driver(driver, deadline):
    original = driver.call
    def call(*args, **kwargs):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ControllerError("RESOURCE_DEADLINE")
        kwargs["timeout"] = min(kwargs.get("timeout", 15), remaining)
        return original(*args, **kwargs)
    driver.call = call
    try:
        yield
    finally:
        driver.call = original


async def initialize_epoch(proof, principal, epoch_id, *, mode):
    """Exactly one explicit INSERT; unknown commit is never retried."""
    from sqlalchemy import select
    from scripts.cf002_interactive_login import owned_session
    from scripts.cf023_supervisor_meaning_check import OwnedEpochBinding, epoch_state
    from src.modules.auth.application.session_service import validate_principal
    from src.modules.supervisor.infrastructure.preparation_repository import clock
    from src.modules.supervisor.domain.contracts import MEANING_SPEC, MEANING_SPEC_SHA256
    from db.models.supervisor.preparation import SupervisorMeaningEpoch as Epoch
    async with owned_session(proof) as session:
        await validate_principal(session, principal, lock=True)
        if await session.scalar(select(Epoch.id)) is not None:
            raise ControllerError("EPOCH_ALREADY_EXISTS")
        row = Epoch(id=UUID(epoch_id), unit_id="CF023", currency="USD", max_nano=100000000,
                    attempt_reserve_nano=50000000, max_attempts=2, price_sha256=digest(MEANING_SPEC["price"]),
                    semantic_sha256=MEANING_SPEC_SHA256, reserved_nano=0, count_requests=0,
                    generation_requests=0, blocked=False, active_attempt_id=None,
                    attempts_json={}, created_at=await clock(session))
        session.add(row)
        await session.commit()
    async with owned_session(proof) as session:
        fresh = await session.scalar(select(Epoch).where(Epoch.id == UUID(epoch_id)))
        if fresh is None or fresh.created_at != row.created_at or epoch_state(fresh) != epoch_state(row):
            raise ControllerError("EPOCH_ACK_UNKNOWN")
        binding = OwnedEpochBinding(proof, proof._owner.receipt, fresh.id, fresh.created_at, digest(epoch_state(fresh)), mode)
        await session.commit()
    return binding


async def epoch_snapshot(proof, binding, principal):
    from sqlalchemy import select
    from scripts.cf002_interactive_login import owned_session
    from scripts.cf023_supervisor_meaning_check import epoch_state, proof_identity
    from src.modules.auth.application.session_service import validate_principal
    from db.models.supervisor.preparation import SupervisorMeaningEpoch as Epoch
    proof_identity(proof, binding, binding.mode)
    async with owned_session(proof) as session:
        await validate_principal(session, principal, lock=True)
        row = await session.scalar(select(Epoch).where(Epoch.id == binding.epoch_id).execution_options(populate_existing=True))
        if row is None or row.created_at != binding.epoch_created_at:
            raise ControllerError("EPOCH_LOST")
        result = epoch_state(row)
        await session.commit()
        return result


def normal_transition(state, item):
    if (state["count"], state["generation"], state["reserved"], state["blocked"], state["active"]) != (1, 1, 50000000, False, None) or len(state["attempts"]) != 1:
        raise ControllerError("FIRST_SETTLEMENT_UNCONFIRMED")
    attempt = next(iter(state["attempts"].values()))
    if attempt.get("request_sha256") != item["request_sha256"] or attempt.get("projection_sha256") != item["projection_sha256"] or attempt.get("observation", {}).get("state") != "observed":
        raise ControllerError("FIRST_SETTLEMENT_UNCONFIRMED")


class OwnedHooks:
    """Fixed resource/verifier composition, with synthetic mode explicitly separate."""
    def __init__(self, *, synthetic):
        self.synthetic = synthetic
        self.driver = self.owner = self.proof = self.home = None

    def create(self):
        from scripts.runner_owned_database import LocalDocker, OwnedPostgres
        from scripts.cf003_admission_check import owned_postgres_home
        self.driver = LocalDocker()
        self.home = owned_postgres_home(self.driver)
        self.home.__enter__()
        self.owner = OwnedPostgres(self.driver)
        return self.owner

    async def bootstrap(self, store):
        from scripts.cf002_interactive_login import migrate_owned, owned_session
        from scripts.cf003_admission_check import isolated_application
        from scripts.cf023_supervisor_meaning_check import load_meaning
        store.persist("claimed", {"phase": "resource_requested", "name": self.owner.name})
        self.proof = self.owner.create()
        store.persist("claimed", {"phase": "resource_created", "receipt_sha256": digest(self.proof.safe_receipt())})
        await migrate_owned(self.proof)
        self.application = isolated_application(self.proof)
        self.observed = self.application.__enter__()
        load_meaning()
        from db.models.auth.models import AuthUser
        from db.models.common.stock import Stock
        from src.modules.auth.application.session_service import issue_session
        from uuid import uuid4
        async with owned_session(self.proof) as session:
            user = AuthUser(id=uuid4())
            session.add(user)
            session.add(Stock(stock_code="000720", stock_name="\ud604\ub300\uac74\uc124", market="KOSPI"))
            await session.flush()
            _, principal = await issue_session(session, user)
            await session.commit()
        binding = await initialize_epoch(self.proof, principal, store.grant["epoch_id"], mode="synthetic" if self.synthetic else "live")
        if not self.synthetic:
            # Initialization is env-free and isolated. Do not run a live supplier
            # inside the synthetic .env/network denial context.
            self.application.__exit__(None, None, None)
            del self.application
            if any(self.observed.values()):
                raise ControllerError("ISOLATION_DENIAL")
        return self.proof, principal, binding

    async def verify(self, store, approval, source, proof, principal, binding, item, index, *, observation):
        from scripts.cf023_supervisor_meaning_check import run_meaning_assembly, verify_live, DeferredKeySource
        if self.synthetic:
            return await run_meaning_assembly(mode="synthetic", proof=proof, binding=binding, principal=principal,
                prepare_body=item["prepare_body"], scenario="success" if index == 0 else "missing_usage")
        from src.supervisor.infrastructure.openai_meaning_gateway import CounterAgreement, INPUT_FIELDS
        authority = None
        supplied = False
        async def supply():
            nonlocal supplied
            observation.supplier("entered")
            try:
                if supplied or authority.phases != ["initial", "preflight", "count"]:
                    raise ControllerError("KEY_SUPPLY_DENIED")
                supplied = True
                await approval_gate(store, approval, source, synthetic=False)
                observation.supplier("approval_checked")
                observation.supplier("source_read_entered")
                key = await source.read()
                observation.supplier("source_read_returned")
                return key
            except asyncio.CancelledError as error:
                observation.supplier("cancelled")
                observation.failed(error)
                raise
            except TimeoutError as error:
                observation.supplier("timed_out")
                observation.failed(error)
                raise
            except Exception as error:
                observation.supplier("failed")
                observation.failed(error)
                raise
        deferred = DeferredKeySource(supply, source)
        authority = ControllerAuthority(store, approval, source, proof, binding, principal, item, deferred, observation)
        agreement = CounterAgreement(store.grant["counter"]["documentation_url"], store.grant["counter"]["documentation_sha256"], INPUT_FIELDS, 0)
        return await verify_live(proof=proof, binding=binding, principal=principal, prepare_body=item["prepare_body"], authority=authority, counter_agreement=agreement, key_supplier=deferred)

    async def snapshot(self, proof, binding, principal):
        return await epoch_snapshot(proof, binding, principal)

    def preserve(self):
        """No disposal before final accounting ACK; retain exact cleanup proof."""
        try:
            if self.owner is not None and self.owner.receipt is not None:
                self.owner._preserve_cleanup_receipt(stage="cleanup", cleanup_result="not_attempted")
        finally:
            self.release()

    def release(self):
        if hasattr(self, "application"):
            self.application.__exit__(None, None, None)
            del self.application
        if self.home is not None:
            self.home.__exit__(None, None, None)
            self.home = None
        if self.driver is not None:
            self.driver.close()

    def cleanup(self):
        denied = False
        try:
            if hasattr(self, "application"):
                self.application.__exit__(None, None, None)
                del self.application
                denied = any(self.observed.values())
            if self.owner is not None:
                if self.owner.receipt is None:
                    raise ControllerError("RESOURCE_CREATION_UNKNOWN")
                self.owner.cleanup()
                if not self.owner._removed:
                    raise ControllerError("CLEANUP_UNCONFIRMED")
            if denied:
                raise ControllerError("ISOLATION_DENIAL")
        finally:
            self.release()


async def run_controller(store, *, approval=None, key_source=None, synthetic=False, hooks=None):
    """The entire entry, including preclaim IO/callbacks, has a fixed error surface."""
    try:
        return await _run_controller(store, approval=approval, key_source=key_source,
                                     synthetic=synthetic, hooks=hooks)
    except asyncio.CancelledError:
        raise
    except ControllerError:
        raise
    except Exception:
        raise ControllerError() from None


async def _run_controller(store, *, approval=None, key_source=None, synthetic=False, hooks=None):
    """No default approval/supplier. One claim, one resource, one epoch, two steps."""
    if not synthetic and hooks is not None or approval is None or key_source is None:
        raise ControllerError("LIVE_GATE_CLOSED")
    hooks = hooks or OwnedHooks(synthetic=synthetic)
    with store.locked():
        if store.state["status"] != "issued":
            raise ControllerError("APPROVAL_ALREADY_USED")
        await approval_gate(store, approval, key_source, synthetic=synthetic)
        store.persist("claimed", {"phase": "claim_ACK"})
        proof = principal = binding = None
        results = []
        observations = []
        diagnostic_ack_unknown = False
        error = None
        deadline = min(time.monotonic() + 240, time.monotonic() + (parse_expiry(store.grant["expires_at"]) - datetime.now(timezone.utc)).total_seconds())
        try:
            async with asyncio.timeout_at(deadline):
                await approval_gate(store, approval, key_source, synthetic=synthetic)
                hooks.create()
                with bounded_driver(hooks.driver, deadline):
                    proof, principal, binding = await hooks.bootstrap(store)
                    store.persist("claimed", {"phase": "epoch_ACK", "epoch": str(binding.epoch_id), "state_sha256": binding.epoch_state_sha256})
                    for index, item in enumerate(store.grant["requests"]):
                        observation = AttemptObservation(index)
                        observations.append(observation)
                        await approval_gate(store, approval, key_source, synthetic=synthetic)
                        result = await hooks.verify(store, approval, key_source, proof, principal, binding, item, index, observation=observation)
                        observation.returned(result)  # Fixed fields before any failure gate/snapshot.
                        snapshot = await hooks.snapshot(proof, binding, principal)
                        try:
                            store.persist("claimed", {"phase": "settlement_ACK", "index": index, "state": snapshot, "diagnostic": observation.snapshot()})
                        except BaseException:
                            diagnostic_ack_unknown = True
                            raise
                        results.append(dict(observation.verifier))
                        if index == 0:
                            if result.get("settlement") != "observed" or result.get("meaning_status") != "supplemented":
                                raise ControllerError("FIRST_SETTLEMENT_UNCONFIRMED")
                            normal_transition(snapshot, item)
                            from scripts.cf023_supervisor_meaning_check import OwnedEpochBinding
                            binding = OwnedEpochBinding(proof, binding.receipt, binding.epoch_id, binding.epoch_created_at, digest(snapshot), binding.mode)
                            store.persist("claimed", {"phase": "next_snapshot_ACK", "state_sha256": binding.epoch_state_sha256})
                    if any(result.get("settlement") not in {"observed", "hold"} for result in results):
                        raise ControllerError("SETTLEMENT_UNCONFIRMED")
        except asyncio.CancelledError as caught:
            error = caught
            if observations:
                observations[-1].failed(caught)
        except BaseException as caught:
            error = caught
            if observations:
                observations[-1].failed(caught)
        finally:
            # A failed/late verifier may already have spent or reserved funds.
            # Read under an independent bounded cleanup budget; never call the
            # verifier or key supplier again and never infer missing usage as0.
            accounting = dict(phase="final_accounting", observation="unconfirmed",
                              count_requests=None, generation_requests=None,
                              estimated_nano=None, conservative_hold_nano=100000000)
            if proof is not None and binding is not None and principal is not None:
                try:
                    async with asyncio.timeout(5):
                        with bounded_driver(hooks.driver, time.monotonic() + 5):
                            final_snapshot = await hooks.snapshot(proof, binding, principal)
                    accounting = dict(phase="final_accounting", observation="fresh_ledger",
                                      state=final_snapshot, state_sha256=digest(final_snapshot))
                except asyncio.CancelledError as caught:
                    error = caught
                    if observations:
                        observations[-1].failed(caught)
                except BaseException:
                    # The entire approval stays consumed even if the DB vanished.
                    error = error or ControllerError("FINAL_LEDGER_UNCONFIRMED")
                    if observations:
                        observations[-1].failed(error)
            accounting_ack = False
            try:
                accounting["diagnostics"] = [value.snapshot() for value in observations]
                accounting["diagnostic_ack_unknown"] = diagnostic_ack_unknown
                store.persist("claimed", accounting)
                store.persist("claimed", {"phase": "closing", "outcome": "failed" if error else "finished", "ledger_observation": "unknown" if error else "recorded", "unknown_hold_possible": error is not None, "diagnostic": failure_summary(error)})
                accounting_ack = not diagnostic_ack_unknown
            except BaseException as caught:
                error = error or caught
            if accounting_ack and getattr(store, "_aggregate_ack", None) is not None:
                try:
                    async with asyncio.timeout(5):await store._aggregate_ack(accounting)
                except BaseException as caught:
                    accounting_ack=False
                    error=caught if isinstance(caught,asyncio.CancelledError) else error or caught
            if accounting_ack:
                try:
                    cleanup_before = time.monotonic() + 30
                    if hooks.driver is not None:
                        with bounded_driver(hooks.driver, cleanup_before):
                            hooks.cleanup()
                    else:
                        hooks.cleanup()
                    store.persist("closed", {"phase": "cleanup_confirmed"})
                except BaseException as caught:
                    error = error or caught
            else:
                try:
                    hooks.preserve()
                except BaseException:
                    pass
                error = error or ControllerError("ACCOUNTING_ACK_UNKNOWN")
        if isinstance(error, asyncio.CancelledError):
            raise error
        if error is not None:
            raise ControllerError(error.stage if isinstance(error, ControllerError) else "CONTROLLER_FAILED") from None
        return {"mode": "synthetic" if synthetic else "live", "results": results, "resource_removed": True, "approval_closed": True}


def synthetic_requests(drafts):
    from uuid import uuid4
    from src.supervisor.infrastructure.openai_meaning_gateway import rendered_request,INPUT_FIELDS
    result=[]
    for draft in drafts:
        request=rendered_request(draft)
        body=dict(prepare_key=str(uuid4()),parent_preparation_id=None,draft=draft.model_dump(mode='json'))
        result.append(dict(prepare_body=body,draft_sha256=digest(body['draft']),request_sha256=digest(request),projection_sha256=digest({k:request[k] for k in INPUT_FIELDS})))
    return result


def synthetic_grant(source,requests,not_before,expires_at,child_id=None):
    from uuid import uuid4
    from src.modules.supervisor.domain.contracts import MEANING_SPEC,MEANING_SPEC_SHA256
    from src.supervisor.infrastructure.openai_meaning_gateway import ORIGIN,COUNT_PATH,GENERATE_PATH,COUNT_DOCUMENTATION
    return dict(schema='cf026.grant.v1',approval_id=child_id or str(uuid4()),issuer='synthetic-only',not_before=not_before,expires_at=expires_at,mode='synthetic',epoch_id=str(uuid4()),requests=requests,semantic_sha256=MEANING_SPEC_SHA256,price_sha256=digest(MEANING_SPEC['price']),model=MEANING_SPEC['model'],tier='default',origin=ORIGIN,endpoints=[COUNT_PATH,GENERATE_PATH],max_nano=100000000,attempt_nano=50000000,max_attempts=2,input_cap=16384,output_cap=2048,source=source.scope(),counter=dict(documentation_url=COUNT_DOCUMENTATION,documentation_sha256='a'*64,free_evidence_sha256='b'*64,price_evidence_sha256='c'*64,fee_bound_nano=0))


def provision_synthetic_fixture(directory):
    """Test-only fake grant. Its mode/source can never pass the live gate."""
    from datetime import timedelta
    from uuid import uuid4
    from scripts.cf023_supervisor_meaning_check import load_meaning
    load_meaning()
    from src.supervisor.domain.meaning import Draft
    directory = no_links(directory)
    if any(directory.iterdir()):
        raise ControllerError("SYNTHETIC_DIRECTORY_NOT_EMPTY")
    def create(name, raw, mode):
        fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        try:
            os.write(fd, raw)
            os.fsync(fd)
        finally:
            os.close(fd)
    create("synthetic-input.txt", b"OPENAI_API_KEY=cf026-unused-synthetic-source\n", 0o644)
    create("execution.lock", b"", 0o600)
    source = KeySource(directory / "synthetic-input.txt", regular(directory / "synthetic-input.txt", 0o644), True)
    requests=synthetic_requests([Draft(original_query="현대건설 수급",answers=[],revision=0) for _ in range(2)])
    now=datetime.now(timezone.utc)
    grant=synthetic_grant(source,requests,(now-timedelta(seconds=1)).isoformat(),(now+timedelta(minutes=6)).isoformat())
    grant["state_store"] = PrivateStore(directory).scope()
    create("grant.json", canonical(grant).encode(), 0o600)
    create("state.json", canonical(dict(schema="cf026.state.v1", approval_id=grant["approval_id"], grant_sha256=digest(grant), status="issued", journal=[])).encode(), 0o600)
    async def verify(**scope):
        return scope["mode"] == "synthetic" and scope["scope_sha256"] == digest(grant)
    return PrivateStore(directory), ExternalApproval(digest(grant), "synthetic-only", verify), source


async def verify_synthetic_database(directory):
    """One owned PG/epoch, success then unknown hold, closed replay refused."""
    store, approval, source = provision_synthetic_fixture(directory)
    hooks = OwnedHooks(synthetic=True)
    result = await run_controller(store, approval=approval, key_source=source, synthetic=True, hooks=hooks)
    journal = store.state["journal"]
    snapshots = [item["state"] for item in journal if item["phase"] == "settlement_ACK"]
    if len(snapshots) != 2 or result["results"][0]["settlement"] != "observed" or result["results"][1]["settlement"] != "hold":
        raise ControllerError("SYNTHETIC_EXPECTATION")
    final = snapshots[-1]
    if (final["count"], final["generation"], final["reserved"], final["blocked"]) != (2, 2, 100000000, True) or final["active"] is None or len(final["attempts"]) != 2 or sorted(a["observation"]["state"] for a in final["attempts"].values()) != ["observed", "unknown"]:
        raise ControllerError("SYNTHETIC_EXPECTATION")
    for fresh_store in (store, PrivateStore(directory)):
        try:
            await run_controller(fresh_store, approval=approval, key_source=source, synthetic=True, hooks=hooks)
        except ControllerError as error:
            if error.stage != "APPROVAL_ALREADY_USED":
                raise
        else:
            raise ControllerError("SYNTHETIC_RESTART_NOT_BLOCKED")
    if not hooks.owner._removed or any(hooks.observed.values()):
        raise ControllerError("CLEANUP_UNCONFIRMED")
    return dict(groups=5, count_requests=2, generation_requests=2, reservations=2,
                reserved_nano=100000000, unknown_hold=True, approval_closed=True,
                resource_removed=True, source_reads=0, real_provider_requests=0,
                replay_restart_blocked=True, observed_denials=dict(hooks.observed))


# v1.4 is a separate entry. It never relaxes run_controller's closed/replay rules.
CONTINUATION_SLOT = "continuation-once"
CONTINUATION_WITNESS = "continuation-once.pending"
_ISSUED_CONTINUATION = object()


def directory_identity(path):
    info = no_links(path).lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ControllerError("CONTINUATION_ANCESTRY")
    return [info.st_dev, info.st_ino, info.st_uid, info.st_mode]


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def exclusive_private_file(path, value):
    raw = canonical(value).encode()
    if len(raw) > 65536:
        raise ControllerError("PRIVATE_STATE_LIMIT")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(fd, raw[offset:])
            if not written:
                raise ControllerError("CONTINUATION_ACK_UNKNOWN")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)
    regular(path, 0o600)


@dataclass(frozen=True, repr=False)
class ParentAnchor:
    path: Path
    directory: list
    lock: dict
    files: dict

    @classmethod
    def capture(cls, path, *, evidence_names):
        """Explicit trusted preparation only; never searches for a parent."""
        path = no_links(path)
        names = {"grant.json", "state.json", *evidence_names}
        if not evidence_names or any(type(n) is not str or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\.json", n) is None for n in names):
            raise ControllerError("CONTINUATION_ANCESTRY")
        files = {}
        for name in sorted(names):
            raw, stamp = read_fixed(path / name, 0o600)
            files[name] = dict(identity=stamp, bytes_sha256=hashlib.sha256(raw).hexdigest())
        return cls(path, directory_identity(path), regular(path / "execution.lock", 0o600), files)

    def scope(self):
        return dict(path=str(self.path), directory=self.directory, lock=self.lock, files=self.files)

    def check(self, parent):
        if parent.directory != self.path or directory_identity(self.path) != self.directory or regular(self.path / "execution.lock", 0o600) != self.lock:
            raise ControllerError("CONTINUATION_ANCESTRY")
        parent.reload()
        for name, expected in self.files.items():
            raw, _ = read_fixed(self.path / name, 0o600, expected["identity"])
            if hashlib.sha256(raw).hexdigest() != expected["bytes_sha256"]:
                raise ControllerError("CONTINUATION_ANCESTRY")
        if parent.state["status"] != "closed" or parent.grant.get("state_store") != parent.scope() or parent.state["journal"][-1].get("phase") != "cleanup_confirmed":
            raise ControllerError("CONTINUATION_ANCESTRY")
        accounts = [e for e in parent.state["journal"] if e.get("phase") == "final_accounting"]
        if len(accounts) != 1 or accounts[0].get("observation") != "fresh_ledger":
            raise ControllerError("CONTINUATION_ANCESTRY")
        old = accounts[0].get("state")
        if type(old) is not dict or any(type(old.get(k)) is not int for k in ("count", "generation", "reserved")) or (old.get("count"), old.get("generation"), old.get("reserved"), old.get("blocked")) != (1, 0, 50000000, True) or old.get("blocked") is not True or type(old.get("active")) is not str or type(old.get("attempts")) is not dict or set(old["attempts"]) != {old["active"]} or old.get("id") != parent.grant["epoch_id"] or (parent.grant.get("max_nano"), parent.grant.get("attempt_nano"), parent.grant.get("max_attempts")) != (100000000, 50000000, 2):
            raise ControllerError("CONTINUATION_ANCESTRY")
        attempt = old["attempts"][old["active"]]
        first = parent.grant["requests"][0]
        if attempt.get("count_done") is not True or attempt.get("generation_done") is not False or (attempt.get("request_sha256"), attempt.get("projection_sha256")) != (first["request_sha256"], first["projection_sha256"]):
            raise ControllerError("CONTINUATION_ANCESTRY")
        observation = attempt.get("observation")
        if type(observation) is not dict or observation.get("state") != "unknown" or observation.get("estimated_nano") is not None:
            raise ControllerError("CONTINUATION_ANCESTRY")
        return old


@dataclass(frozen=True, repr=False)
class OneShotIssuanceAuthority:
    """External pre-provisioned observe/durable consume-CAS; no absent fallback."""
    identity_sha256: str
    mode: str
    observe: object = field(repr=False)
    consume_once: object = field(repr=False)


@dataclass(repr=False)
class ContinuationPermission:
    """Trusted current permission/evidence callback; not a new user budget."""
    anchor: ParentAnchor
    receipt_sha256: str
    issuer: str
    mode: str
    verify: object = field(repr=False)
    issuance: OneShotIssuanceAuthority | None = field(default=None, repr=False)
    issuance_attempted: bool = field(default=False, init=False)


@dataclass(frozen=True, repr=False)
class ContinuationCapability:
    seal: object = field(repr=False)
    permission: ContinuationPermission = field(repr=False)
    directory: list
    witness: dict
    receipt: dict
    issued_state: dict
    issuance_authority: OneShotIssuanceAuthority = field(repr=False)

    def __post_init__(self):
        if self.seal is not _ISSUED_CONTINUATION:
            raise ControllerError("CONTINUATION_INVALID")


def fixed_continuation_id(anchor):
    return digest(dict(parent=anchor.scope(), purpose="first-request-retry-1"))


def issuance_record(permission, receipt, state):
    authority = permission.issuance
    if type(authority) is not OneShotIssuanceAuthority or authority.mode != permission.mode or type(authority.identity_sha256) is not str or re.fullmatch(r"[a-f0-9]{64}", authority.identity_sha256) is None or receipt.get("issuance_authority_sha256") != authority.identity_sha256 or not callable(authority.observe) or not callable(authority.consume_once):
        raise ControllerError("EXTERNAL_APPROVAL_REQUIRED")
    return dict(schema="cf026.external-issuance.v1", authority_sha256=authority.identity_sha256,
                namespace_sha256=digest(permission.anchor.scope()),
                continuation_id=fixed_continuation_id(permission.anchor),
                receipt_sha256=digest(receipt), state=state)


async def external_issuance(permission, receipt, *, consume=False):
    """A lost/unknown external record is never interpreted as available."""
    available = issuance_record(permission, receipt, "available")
    consumed = issuance_record(permission, receipt, "consumed")
    authority = permission.issuance
    scope = {k: v for k, v in available.items() if k != "state"}
    remaining = min(5, (parse_expiry(receipt["expires_at"]) - datetime.now(timezone.utc)).total_seconds())
    async with asyncio.timeout(remaining):
        observed = await authority.observe(**scope)
        if consume:
            if observed == consumed:
                raise ControllerError("CONTINUATION_USED")
            if type(observed) is not dict or observed != available:
                raise ControllerError("EXTERNAL_APPROVAL_REQUIRED")
            ack = await authority.consume_once(**scope)
            if type(ack) is not dict or ack != consumed:
                raise ControllerError("CONTINUATION_ACK_UNKNOWN")
            observed = await authority.observe(**scope)
        if type(observed) is not dict or observed != consumed:
            raise ControllerError("CONTINUATION_ACK_UNKNOWN")


def validate_continuation_receipt(receipt, parent, permission, source):
    from scripts.cf023_supervisor_meaning_check import load_meaning
    load_meaning()
    from src.modules.supervisor.domain.contracts import PreparationRequest, MEANING_SPEC, MEANING_SPEC_SHA256
    from src.supervisor.infrastructure.openai_meaning_gateway import rendered_request, INPUT_FIELDS, ORIGIN, COUNT_PATH, GENERATE_PATH, COUNT_DOCUMENTATION
    keys = {"schema", "continuation_id", "parent", "root_approval_id", "issuer", "mode", "not_before", "expires_at", "runtime_sha256", "closure_evidence_sha256", "epoch_id", "requests", "source", "counter", "semantic_sha256", "price_sha256", "model", "tier", "origin", "endpoints", "inherited_hold_nano", "child_reserve_nano", "max_total_nano", "max_total_attempts", "max_child_attempts", "max_child_count", "max_child_generation", "input_cap", "output_cap", "issuance_authority_sha256"}
    if type(receipt) is not dict or set(receipt) != keys or type(permission) is not ContinuationPermission or permission.mode not in {"synthetic", "live"} or permission.anchor.path != parent.directory or receipt["schema"] != "cf026.continuation.v1" or receipt["continuation_id"] != fixed_continuation_id(permission.anchor) or receipt["parent"] != permission.anchor.scope() or receipt["root_approval_id"] != parent.grant["approval_id"] or receipt["issuer"] != permission.issuer or receipt["mode"] != permission.mode or receipt["mode"] != parent.grant["mode"] or digest(receipt) != permission.receipt_sha256:
        raise ControllerError("CONTINUATION_INVALID")
    if any(type(receipt[k]) is not str or re.fullmatch(r"[a-f0-9]{64}", receipt[k]) is None for k in ("runtime_sha256", "closure_evidence_sha256", "issuance_authority_sha256")):
        raise ControllerError("CONTINUATION_INVALID")
    limits = {"inherited_hold_nano": 50000000, "child_reserve_nano": 50000000, "max_total_nano": 100000000, "max_total_attempts": 2, "max_child_attempts": 1, "max_child_count": 1, "max_child_generation": 1, "input_cap": 16384, "output_cap": 2048}
    if any(type(receipt[k]) is not int or receipt[k] != value for k, value in limits.items()):
        raise ControllerError("CONTINUATION_LIMIT")
    if (receipt["semantic_sha256"], receipt["price_sha256"], receipt["model"], receipt["tier"], receipt["origin"], receipt["endpoints"]) != (MEANING_SPEC_SHA256, digest(MEANING_SPEC["price"]), MEANING_SPEC["model"], "default", ORIGIN, [COUNT_PATH, GENERATE_PATH]):
        raise ControllerError("CONTINUATION_INVALID")
    if any(parent.grant.get(k) != receipt[k] for k in ("semantic_sha256", "price_sha256", "model", "tier", "origin", "endpoints", "input_cap", "output_cap")):
        raise ControllerError("CONTINUATION_ANCESTRY")
    if type(receipt["requests"]) is not list or len(receipt["requests"]) != 1 or receipt["requests"][0] != parent.grant["requests"][0]:
        raise ControllerError("CONTINUATION_INVALID")
    item = receipt["requests"][0]
    body = PreparationRequest.model_validate(item["prepare_body"])
    draft = body.draft
    if body.parent_preparation_id is not None or draft.original_query != "\ud604\ub300\uac74\uc124 \uc678\uad6d\uc778 \ub9d0\uace0 3\uc8fc \uc218\uae09" or draft.answers or draft.revision != 0 or draft.selected_ticker is not None or draft.candidate_ref is not None or body.model_dump(mode="json") != item["prepare_body"]:
        raise ControllerError("CONTINUATION_INVALID")
    rendered = rendered_request(draft)
    if (item["draft_sha256"], item["request_sha256"], item["projection_sha256"]) != (digest(draft.model_dump(mode="json")), digest(rendered), digest({k: rendered[k] for k in INPUT_FIELDS})):
        raise ControllerError("CONTINUATION_INVALID")
    UUID(receipt["epoch_id"])
    if receipt["epoch_id"] == parent.grant["epoch_id"] or type(source) is not KeySource or source.synthetic != (receipt["mode"] == "synthetic") or receipt["source"] != source.scope():
        raise ControllerError("KEY_SOURCE_SCOPE")
    previous = parent.grant["source"]
    if previous["path"] != receipt["source"]["path"] or any(previous["identity"][k] != receipt["source"]["identity"][k] for k in ("uid", "dev", "ino", "mode", "nlink")):
        raise ControllerError("KEY_SOURCE_SCOPE")
    counter = receipt["counter"]
    if type(counter) is not dict or set(counter) != {"documentation_url", "documentation_sha256", "free_evidence_sha256", "price_evidence_sha256", "fee_bound_nano"} or counter["documentation_url"] != COUNT_DOCUMENTATION or type(counter["fee_bound_nano"]) is not int or counter["fee_bound_nano"] != 0 or any(type(counter[k]) is not str or re.fullmatch(r"[a-f0-9]{64}", counter[k]) is None for k in ("documentation_sha256", "free_evidence_sha256", "price_evidence_sha256")):
        raise ControllerError("COUNTER_EVIDENCE_INVALID")
    now = datetime.now(timezone.utc)
    if not parse_expiry(receipt["not_before"]) <= now < parse_expiry(receipt["expires_at"]):
        raise ControllerError("APPROVAL_EXPIRED")


async def continuation_permission(permission, parent, receipt, source, *, phase):
    permission.anchor.check(parent)
    validate_continuation_receipt(receipt, parent, permission, source)
    source.check()
    if phase != "issue":
        await external_issuance(permission, receipt)
    remaining = min(5, (parse_expiry(receipt["expires_at"]) - datetime.now(timezone.utc)).total_seconds())
    async with asyncio.timeout(remaining):
        if not callable(permission.verify) or await permission.verify(phase=phase, parent=permission.anchor.scope(), receipt_sha256=digest(receipt), mode=permission.mode, counter=dict(receipt["counter"]), closure_evidence_sha256=receipt["closure_evidence_sha256"]) is not True:
            raise ControllerError("EXTERNAL_APPROVAL_REQUIRED")
    permission.anchor.check(parent)
    validate_continuation_receipt(receipt, parent, permission, source)
    source.check()
    if datetime.now(timezone.utc) >= parse_expiry(receipt["expires_at"]):
        raise ControllerError("APPROVAL_EXPIRED")


async def issue_continuation(permission, receipt, source):
    """Trusted issuer only. Runtime never creates a slot or reconstructs a cap."""
    try:
        if type(permission) is not ContinuationPermission or permission.issuance_attempted:
            raise ControllerError("CONTINUATION_USED")
        permission.issuance_attempted = True
        anchor = permission.anchor
        parent = PrivateStore(anchor.path)
        with parent.locked():
            await continuation_permission(permission, parent, receipt, source, phase="issue")
            slot, witness = anchor.path / CONTINUATION_SLOT, anchor.path / CONTINUATION_WITNESS
            if slot.exists() or witness.exists() or slot.is_symlink() or witness.is_symlink():
                raise ControllerError("CONTINUATION_USED")
            await external_issuance(permission, receipt, consume=True)
            await continuation_permission(permission, parent, receipt, source, phase="issue")
            token = dict(schema="cf026.continuation.witness.v1", continuation_id=receipt["continuation_id"], parent=anchor.scope(), receipt_sha256=digest(receipt))
            exclusive_private_file(witness, token)
            fsync_directory(anchor.path)
            slot.mkdir(mode=0o700)
            fsync_directory(anchor.path)
            exclusive_private_file(slot / "receipt.json", receipt)
            issued = dict(schema="cf026.continuation.state.v1", receipt_sha256=digest(receipt), status="issued", claimed=False, rights=dict(count=0, generation=0), preparation=None, inherited_hold_nano=50000000, child_hold_nano=None, total_hold_nano=50000000, journal=[])
            exclusive_private_file(slot / "state.json", issued)
            fsync_directory(slot)
            snapshots = []
            for path in (witness, slot / "receipt.json", slot / "state.json"):
                raw, stamp = read_fixed(path, 0o600)
                snapshots.append(dict(identity=stamp, bytes_sha256=hashlib.sha256(raw).hexdigest()))
            if decode(read_fixed(witness, 0o600)[0]) != token or decode(read_fixed(slot / "receipt.json", 0o600)[0]) != receipt or decode(read_fixed(slot / "state.json", 0o600)[0]) != issued:
                raise ControllerError("CONTINUATION_ACK_UNKNOWN")
            anchor.check(parent)
            return ContinuationCapability(_ISSUED_CONTINUATION, permission, directory_identity(slot), *snapshots, permission.issuance)
    except asyncio.CancelledError:
        raise
    except ControllerError:
        raise
    except Exception:
        raise ControllerError("CONTINUATION_ACK_UNKNOWN") from None


class ContinuationStore:
    def __init__(self, capability, parent):
        if type(capability) is not ContinuationCapability or capability.seal is not _ISSUED_CONTINUATION:
            raise ControllerError("CONTINUATION_INVALID")
        self.capability, self.parent = capability, parent
        self.directory = capability.permission.anchor.path / CONTINUATION_SLOT
        self.state_stamp = capability.issued_state["identity"]
        self.reload()
        if self.state["status"] != "issued" or hashlib.sha256(read_fixed(self.directory / "state.json", 0o600)[0]).hexdigest() != capability.issued_state["bytes_sha256"]:
            raise ControllerError("CONTINUATION_USED")

    def reload(self):
        cap, anchor = self.capability, self.capability.permission.anchor
        if cap.permission.issuance is not cap.issuance_authority:
            raise ControllerError("EXTERNAL_APPROVAL_REQUIRED")
        anchor.check(self.parent)
        if directory_identity(self.directory) != cap.directory:
            raise ControllerError("CONTINUATION_ANCESTRY")
        for path, expected in ((anchor.path / CONTINUATION_WITNESS, cap.witness), (self.directory / "receipt.json", cap.receipt)):
            raw, _ = read_fixed(path, 0o600, expected["identity"])
            if hashlib.sha256(raw).hexdigest() != expected["bytes_sha256"]:
                raise ControllerError("CONTINUATION_ANCESTRY")
        self.grant = decode(read_fixed(self.directory / "receipt.json", 0o600, cap.receipt["identity"])[0])
        self.state = decode(read_fixed(self.directory / "state.json", 0o600, self.state_stamp)[0])
        expected = {"schema", "receipt_sha256", "status", "claimed", "rights", "preparation", "inherited_hold_nano", "child_hold_nano", "total_hold_nano", "journal"}
        state = self.state
        if type(state) is not dict or set(state) != expected or state["schema"] != "cf026.continuation.state.v1" or state["receipt_sha256"] != digest(self.grant) or state["status"] not in {"issued", "claimed", "closed"} or type(state["claimed"]) is not bool or state["claimed"] != (state["status"] != "issued") or type(state["rights"]) is not dict or set(state["rights"]) != {"count", "generation"} or any(type(v) is not int or v not in {0, 1} for v in state["rights"].values()) or state["rights"]["generation"] > state["rights"]["count"] or state["inherited_hold_nano"] != 50000000 or state["child_hold_nano"] != (50000000 if state["claimed"] else None) or state["total_hold_nano"] != (100000000 if state["claimed"] else 50000000) or type(state["journal"]) is not list or len(state["journal"]) > 24:
            raise ControllerError("CONTINUATION_INVALID")

    def persist(self, status, event, *, rights=None, preparation=None):
        self.reload()
        old = self.state
        if status not in {"issued": {"claimed"}, "claimed": {"claimed", "closed"}, "closed": set()}[old["status"]] or len(old["journal"]) >= 24:
            raise ControllerError("CONTINUATION_USED")
        if len(old["journal"]) >= 21 and event.get("phase") not in {"final_accounting", "closing", "cleanup_confirmed"}:
            raise ControllerError("PRIVATE_STATE_LIMIT")
        state = old | dict(status=status, claimed=True, child_hold_nano=50000000, total_hold_nano=100000000, journal=[*old["journal"], event])
        if rights is not None:
            if any(rights[k] < old["rights"][k] or type(rights[k]) is not int or rights[k] > 1 for k in ("count", "generation")) or rights["generation"] > rights["count"]:
                raise ControllerError("CONTINUATION_LIMIT")
            state["rights"] = rights
        if preparation is not None:
            if old["preparation"] is not None and old["preparation"] != preparation:
                raise ControllerError("CONTINUATION_PHASE")
            state["preparation"] = preparation
        raw = canonical(state).encode()
        if len(raw) > 65536:
            raise ControllerError("PRIVATE_STATE_LIMIT")
        path = self.directory / "state.pending"
        try:
            exclusive_private_file(path, state)
            self.reload()
            os.replace(path, self.directory / "state.json")
            fsync_directory(self.directory)
            self.state_stamp = regular(self.directory / "state.json", 0o600)
            self.reload()
            if self.state != state:
                raise ControllerError("CONTINUATION_ACK_UNKNOWN")
        except BaseException:
            raise ControllerError("CONTINUATION_ACK_UNKNOWN") from None

    def consume_phase(self, phase, local_before):
        self.reload()
        rights = dict(self.state["rights"])
        if self.state["status"] != "claimed" or self.state["preparation"] is None or phase not in {"count", "generation"} or rights[phase] or phase == "generation" and rights["count"] != 1:
            raise ControllerError("CONTINUATION_PHASE")
        rights[phase] = 1
        expected = dict(count=0, generation=0, reserved=0) if phase == "count" else dict(count=1, generation=0, reserved=50000000)
        if local_before != expected:
            raise ControllerError("CONTINUATION_PHASE")
        self.persist("claimed", dict(phase="root_" + phase + "_authority_ACK", local_before=local_before), rights=rights)


class ContinuationAuthority:
    """Durable root rights ACK precedes the unchanged PhaseBudget local ACK."""
    def __init__(self, store, source, proof, binding, principal, body, deferred, observation):
        self.store, self.source, self.proof, self.binding = store, source, proof, binding
        self.principal, self.body, self.deferred, self.observation = principal, body, deferred, observation
        self.phases = []
        self.deadline = asyncio.get_running_loop().time() + 60

    async def fresh_preparation(self):
        from sqlalchemy import select
        from db.models.supervisor.preparation import SupervisorMeaningPreparation as Preparation
        from scripts.cf002_interactive_login import owned_session
        from scripts.cf023_supervisor_meaning_check import proof_identity, existing_epoch
        from src.modules.auth.application.session_service import validate_principal
        from src.modules.supervisor.infrastructure.preparation_repository import clock
        from src.modules.supervisor.application.preparation_service import draft_identity
        from src.modules.supervisor.domain.contracts import MEANING_SPEC, MEANING_SPEC_SHA256
        proof_identity(self.proof, self.binding, self.binding.mode)
        async with owned_session(self.proof) as session:
            await validate_principal(session, self.principal, lock=True)
            row = await session.scalar(select(Preparation).where(Preparation.owner_user_id == self.principal.user_id, Preparation.prepare_key_digest == hashlib.sha256(self.body.prepare_key.encode()).digest(), Preparation.epoch_id == self.binding.epoch_id).execution_options(populate_existing=True).with_for_update())
            now = await clock(session)
            if row is None or row.parent_id is not None or row.root_id != row.id or row.state != "pending" or row.redacted_at is not None or row.expires_at <= now or row.semantic_sha256 != MEANING_SPEC_SHA256 or row.semantic_json != canonical(MEANING_SPEC) or row.request_digest != digest(self.body.model_dump(mode="json")) or row.draft_digest != digest(draft_identity(self.body.draft)) or row.draft_json != canonical(self.body.draft.model_dump(mode="json")):
                raise ControllerError("CONTINUATION_PHASE")
            epoch = await existing_epoch(session, self.binding)
            local_before = dict(count=epoch.count_requests, generation=epoch.generation_requests, reserved=epoch.reserved_nano)
            bound = dict(owner=str(self.principal.user_id), preparation=str(row.id), attempt=str(row.attempt_id), epoch=str(self.binding.epoch_id), prepare_key_sha256=hashlib.sha256(self.body.prepare_key.encode()).hexdigest())
            await session.commit()
        self.store.reload()
        if self.store.state["preparation"] is None:
            self.store.persist("claimed", dict(phase="preparation_binding_ACK"), preparation=bound)
        elif self.store.state["preparation"] != bound:
            raise ControllerError("CONTINUATION_PHASE")
        return local_before

    async def verify(self, **scope):
        store = self.store
        receipt = store.grant
        await continuation_permission(store.capability.permission, store.parent, receipt, self.source, phase=scope.get("phase"))
        store.reload()
        item = receipt["requests"][0]
        phase = scope.get("phase")
        expected = ["initial", "preflight", "count", "generation"]
        if store.state["status"] != "claimed" or len(self.phases) >= 4 or phase != expected[len(self.phases)] or scope.get("mode") != receipt["mode"] or scope.get("proof_binding") is not self.binding or scope.get("principal") is not self.principal or scope.get("key_supplier") is not self.deferred or scope.get("key_source_capability") is not self.source or scope.get("draft_sha256") != item["draft_sha256"] or scope.get("semantic_sha256") != receipt["semantic_sha256"]:
            raise ControllerError("CONTINUATION_PHASE")
        from src.supervisor.infrastructure.openai_meaning_gateway import CounterAgreement, INPUT_FIELDS
        agreement = scope.get("agreement")
        if type(agreement) is not CounterAgreement or agreement.documentation_sha256 != receipt["counter"]["documentation_sha256"] or agreement.documentation_url != receipt["counter"]["documentation_url"] or agreement.input_fields != INPUT_FIELDS or agreement.counting_fee_bound_nano != 0:
            raise ControllerError("CONTINUATION_PHASE")
        expiry = parse_expiry(receipt["expires_at"])
        local_before = None
        if phase != "initial":
            if (scope.get("request_sha256"), scope.get("projection_sha256")) != (item["request_sha256"], item["projection_sha256"]):
                raise ControllerError("CONTINUATION_PHASE")
            async with asyncio.timeout_at(min(self.deadline, asyncio.get_running_loop().time() + (expiry - datetime.now(timezone.utc)).total_seconds())):
                local_before = await self.fresh_preparation()
        store.reload()
        if datetime.now(timezone.utc) >= expiry:
            raise ControllerError("APPROVAL_EXPIRED")
        if phase in {"count", "generation"}:
            store.consume_phase(phase, local_before)
        self.phases.append(phase)
        if phase == "generation":
            self.observation.generation_authority = True
        return expiry


class ContinuationHooks(OwnedHooks):
    async def verify(self, store, source, proof, principal, binding, observation):
        from scripts import cf023_supervisor_meaning_check as verifier
        from src.modules.supervisor.domain.contracts import PreparationRequest
        from src.supervisor.infrastructure.openai_meaning_gateway import CounterAgreement, INPUT_FIELDS
        if store.grant["mode"] != ("synthetic" if self.synthetic else "live"):
            raise ControllerError("LIVE_GATE_CLOSED")
        body = PreparationRequest.model_validate(store.grant["requests"][0]["prepare_body"])
        stages = []
        authority = None
        supplied = False
        async def supplier():
            nonlocal supplied
            observation.supplier("entered")
            try:
                if supplied or authority.phases != ["initial", "preflight", "count"]:
                    raise ControllerError("KEY_SUPPLY_DENIED")
                supplied = True
                await continuation_permission(store.capability.permission, store.parent, store.grant, source, phase="supplier")
                store.reload()
                if store.state["rights"] != dict(count=1, generation=0):
                    raise ControllerError("CONTINUATION_PHASE")
                local = await epoch_snapshot(proof, binding, principal)
                if (local["count"], local["generation"], local["reserved"]) != (1, 0, 50000000):
                    raise ControllerError("CONTINUATION_PHASE")
                store.persist("claimed", dict(phase="local_count_ACK_before_supplier", count=1, generation=0, reserved=50000000))
                observation.supplier("approval_checked")
                observation.supplier("source_read_entered")
                key = await source.read()
                observation.supplier("source_read_returned")
                return key
            except asyncio.CancelledError as error:
                observation.supplier("cancelled");observation.failed(error);raise
            except TimeoutError as error:
                observation.supplier("timed_out");observation.failed(error);raise
            except Exception as error:
                observation.supplier("failed");observation.failed(error);raise
        deferred = verifier.DeferredKeySource(supplier, source)
        agreement = CounterAgreement(store.grant["counter"]["documentation_url"], store.grant["counter"]["documentation_sha256"], INPUT_FIELDS, 0)
        deadline = min(asyncio.get_running_loop().time() + 60, asyncio.get_running_loop().time() + (parse_expiry(store.grant["expires_at"]) - datetime.now(timezone.utc)).total_seconds())
        authority = ContinuationAuthority(store, source, proof, binding, principal, body, deferred, observation)
        if not self.synthetic:
            return await verifier.verify_live(proof=proof, binding=binding, principal=principal,
                prepare_body=body.model_dump(mode="json"), authority=authority,
                counter_agreement=agreement, key_supplier=deferred)
        return await synthetic_preparation_assembly(body=body,proof=proof,principal=principal,binding=binding,
            authority=authority,agreement=agreement,deferred=deferred,deadline=deadline,stages=stages)


async def synthetic_preparation_assembly(*, body, proof, principal, binding, authority, agreement, deferred, deadline, stages, scenario='success'):
    from scripts import cf023_supervisor_meaning_check as verifier
    from scripts.cf002_interactive_login import owned_session
    from src.modules.supervisor.application.preparation_service import PreparationService
    from src.modules.auth.application.session_service import validate_principal
    from src.shared.infrastructure.clients.ai_client import AIClient
    from src.supervisor.infrastructure.openai_meaning_gateway import OpenAIMeaningGateway
    from unittest.mock import patch
    import httpx
    if binding.mode!='synthetic':raise ControllerError('LIVE_GATE_CLOSED')
    budget = verifier.PhaseBudget(proof=proof, binding=binding, principal=principal, body=body, authority=authority, agreement=agreement, key_source=deferred, deadline=deadline, stages=stages)
    async with asyncio.timeout_at(deadline):
        await budget.lease("initial")
        async with owned_session(proof) as session:
            await validate_principal(session, principal, lock=True)
            await verifier.existing_epoch(session, binding, initial=True)
            await session.commit()
        stages.append("preflight_verified")
        transport = verifier.synthetic_provider(scenario, stages)
        gateway = OpenAIMeaningGateway(key_supplier=deferred, budget=budget, counter_agreement=agreement, transport=transport, preflight=budget.preflight, deadline=deadline)
        app = verifier.load_meaning(gateway=gateway)
        token = "cf026-asgi-synthetic-service-token-at-least32"
        client = AIClient("http://synthetic.invalid", 8, transport=httpx.ASGITransport(app=app), service_token=token)
        with patch.dict(os.environ, {"FLOW_ANALYSIS_ENABLED": "true", "FLOW_SERVICE_TOKEN": token}):
            async with owned_session(proof) as session:
                from uuid import uuid4
                result = await PreparationService(session, principal=principal, client=client, epoch_id=binding.epoch_id).post(body, uuid4())
            if gateway.settlement_uncertain or budget.uncertain:
                return dict(stages=stages, meaning_status="unavailable", settlement="unconfirmed")
            before = len(stages)
            async with owned_session(proof) as session:
                stored = await PreparationService(session, principal=principal, client=client, epoch_id=binding.epoch_id).get(UUID(result["preparation_id"]))
            if stored != result or len(stages) != before:
                raise ControllerError("CONTINUATION_INVALID")
            stages.append("preparation_owner_readback")
            return dict(stages=stages, meaning_status=result["meaning_status"], settlement="hold" if gateway.block_confirmed else "observed" if "settlement_ACK" in stages else "not_called")

def continuation_accounting(snapshot, observation, rights):
    if snapshot is None:
        local = dict(count=None, generation=None, reserved=None, estimated_nano=None)
    else:
        if any(type(snapshot.get(k)) is not int for k in ("count", "generation", "reserved")) or not 0 <= snapshot["generation"] <= snapshot["count"] <= 1 or snapshot["reserved"] != snapshot["count"] * 50000000 or snapshot["count"] > rights["count"] or snapshot["generation"] > rights["generation"]:
            raise ControllerError("CONTINUATION_LIMIT")
        local = snapshot
    return dict(phase="final_accounting", inherited_hold_nano=50000000,
                child_rights=dict(rights), child_ledger=local, child_conservative_hold_nano=50000000,
                total_hold_nano=100000000, total_attempts_consumed=2, total_estimated_nano=None,
                diagnostic=observation.snapshot(), count_http="unknown", generation_http="unknown")


async def run_continuation(capability, *, source=None, synthetic=False, hooks=None):
    """One original-lock child only. No CLI retry or new approval/store fallback."""
    try:
        if type(capability) is not ContinuationCapability or capability.seal is not _ISSUED_CONTINUATION or capability.permission.mode != ("synthetic" if synthetic else "live") or source is None or not synthetic and hooks is not None:
            raise ControllerError("LIVE_GATE_CLOSED")
        parent = PrivateStore(capability.permission.anchor.path)
        with parent.locked():
            store = ContinuationStore(capability, parent)
            await continuation_permission(capability.permission, parent, store.grant, source, phase="claim")
            store.persist("claimed", dict(phase="continuation_claim_ACK", total_hold_nano=100000000, attempts_consumed=2))
            return await _run_continuation_claimed(store, source, synthetic=synthetic, hooks=hooks)
    except asyncio.CancelledError:
        raise
    except ControllerError:
        raise
    except Exception:
        raise ControllerError("CONTINUATION_INVALID") from None


async def _run_continuation_claimed(store, source, *, synthetic, hooks):
    hooks = hooks or ContinuationHooks(synthetic=synthetic)
    proof = principal = binding = None
    observation = AttemptObservation(0)
    error = None
    result = None
    deadline = min(time.monotonic() + 240, time.monotonic() + (parse_expiry(store.grant["expires_at"]) - datetime.now(timezone.utc)).total_seconds())
    try:
        async with asyncio.timeout_at(deadline):
            await continuation_permission(store.capability.permission, store.parent, store.grant, source, phase="bootstrap")
            hooks.create()
            with bounded_driver(hooks.driver, deadline):
                proof, principal, binding = await hooks.bootstrap(store)
                store.persist("claimed", dict(phase="child_epoch_ACK", epoch=str(binding.epoch_id), state_sha256=binding.epoch_state_sha256))
                result = await hooks.verify(store, source, proof, principal, binding, observation)
                observation.returned(result)
                if result["settlement"] != "observed" or result["meaning_status"] != "supplemented":
                    raise ControllerError("FIRST_SETTLEMENT_UNCONFIRMED")
    except BaseException as caught:
        error = caught
        observation.failed(caught)
    finally:
        snapshot = None
        if proof is not None and binding is not None and principal is not None:
            try:
                async with asyncio.timeout(5):
                    with bounded_driver(hooks.driver, time.monotonic() + 5):
                        snapshot = await hooks.snapshot(proof, binding, principal)
            except asyncio.CancelledError as caught:
                error = caught;observation.failed(caught)
            except BaseException:
                error = error or ControllerError("FINAL_LEDGER_UNCONFIRMED")
                observation.failed(error)
        ack = False
        try:
            store.reload()
            account = continuation_accounting(snapshot, observation, store.state["rights"])
            store.persist("claimed", account)
            store.persist("claimed", dict(phase="closing", outcome="failed" if error else "finished", diagnostic=failure_summary(error)))
            ack = True
        except BaseException as caught:
            error = error or caught
        if ack:
            try:
                if hooks.driver is not None:
                    with bounded_driver(hooks.driver, time.monotonic() + 30):hooks.cleanup()
                else:hooks.cleanup()
                store.persist("closed", dict(phase="cleanup_confirmed"))
            except BaseException as caught:
                error = error or caught
                try:hooks.preserve()
                except BaseException:pass
        else:
            try:hooks.preserve()
            except BaseException:pass
    if isinstance(error, asyncio.CancelledError):raise error
    if error is not None:
        raise ControllerError(error.stage if type(error) is ControllerError else "CONTROLLER_FAILED") from None
    return dict(mode="synthetic" if synthetic else "live", diagnostic=observation.snapshot(), approval_closed=True, resource_removed=True)


def synthetic_issuance_authority(path, anchor, *, initialize_for_fixture=None):
    """Synthetic file/CAS provider; explicit setup only, never initialize on loss."""
    path = no_links(path)
    namespace = digest(anchor.scope())
    authority_id = digest(dict(synthetic_only=True, path=str(path), namespace=namespace))
    def check_scope(scope):
        if scope.get("authority_sha256") != authority_id or scope.get("namespace_sha256") != namespace or scope.get("continuation_id") != fixed_continuation_id(anchor):
            raise ControllerError("EXTERNAL_APPROVAL_REQUIRED")
    async def observe(**scope):
        check_scope(scope)
        value = decode(read_fixed(path, 0o600)[0])
        if type(value) is not dict or value not in (scope | dict(state="available"), scope | dict(state="consumed")):
            raise ControllerError("EXTERNAL_APPROVAL_REQUIRED")
        return value
    async def consume_once(**scope):
        if await observe(**scope) != scope | dict(state="available"):
            raise ControllerError("CONTINUATION_USED")
        value = scope | dict(state="consumed")
        pending = path.with_name(path.name + ".pending")
        exclusive_private_file(pending, value)
        os.replace(pending, path)
        fsync_directory(path.parent)
        if await observe(**scope) != value:
            raise ControllerError("CONTINUATION_ACK_UNKNOWN")
        return value
    authority = OneShotIssuanceAuthority(authority_id, "synthetic", observe, consume_once)
    if initialize_for_fixture is not None:
        receipt = initialize_for_fixture
        value = dict(schema="cf026.external-issuance.v1", authority_sha256=authority_id,
                     namespace_sha256=namespace, continuation_id=fixed_continuation_id(anchor),
                     receipt_sha256=digest(receipt), state="available")
        exclusive_private_file(path, value)
        fsync_directory(path.parent)
    else:
        read_fixed(path, 0o600)
    return authority


def synthetic_continuation_fixture(directory):
    """Own fake ancestry only. Never opens, edits or reissues an actual approval."""
    from datetime import timedelta
    from uuid import uuid4
    store, _, source = provision_synthetic_fixture(directory)
    from src.supervisor.domain.meaning import Draft
    from src.supervisor.infrastructure.openai_meaning_gateway import rendered_request, INPUT_FIELDS
    source.path.write_bytes(b"OPENAI_API_KEY=cf024-synthetic-key-only\n")
    source = KeySource(source.path, regular(source.path, 0o644), True)
    grant = decode(read_fixed(Path(directory) / "grant.json", 0o600)[0])
    draft = Draft(original_query="\ud604\ub300\uac74\uc124 \uc678\uad6d\uc778 \ub9d0\uace0 3\uc8fc \uc218\uae09", answers=[], revision=0)
    rendered = rendered_request(draft)
    body = grant["requests"][0]["prepare_body"] | dict(draft=draft.model_dump(mode="json"))
    grant["requests"][0] = dict(prepare_body=body, draft_sha256=digest(body["draft"]), request_sha256=digest(rendered), projection_sha256=digest({k: rendered[k] for k in INPUT_FIELDS}))
    grant["source"] = source.scope()
    grant["not_before"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    grant["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    (Path(directory) / "grant.json").write_text(canonical(grant))
    issued = decode(read_fixed(Path(directory) / "state.json", 0o600)[0])
    (Path(directory) / "state.json").write_text(canonical(issued | dict(grant_sha256=digest(grant))))
    attempt = str(uuid4())
    old = dict(id=grant["epoch_id"], count=1, generation=0, reserved=50000000, blocked=True, active=attempt,
               attempts={attempt: dict(request_sha256=grant["requests"][0]["request_sha256"], projection_sha256=grant["requests"][0]["projection_sha256"], count_done=True, generation_done=False, observation=dict(state="unknown", reason="UNOBSERVED", estimated_nano=None))})
    with store.locked():
        store.persist("claimed", dict(phase="synthetic_parent_claim"))
        store.persist("claimed", dict(phase="final_accounting", observation="fresh_ledger", state=old))
        store.persist("claimed", dict(phase="closing"))
        store.persist("closed", dict(phase="cleanup_confirmed"))
    evidence = dict(synthetic_only=True, resource_removed=True, source_copy_removed=True, recoverable_provider_handle=False)
    exclusive_private_file(Path(directory) / "failure.json", evidence)
    fsync_directory(directory)
    anchor = ParentAnchor.capture(directory, evidence_names=("failure.json",))
    now = datetime.now(timezone.utc)
    common = {k: grant[k] for k in ("counter", "semantic_sha256", "price_sha256", "model", "tier", "origin", "endpoints", "input_cap", "output_cap")}
    receipt = common | dict(schema="cf026.continuation.v1", continuation_id=fixed_continuation_id(anchor), parent=anchor.scope(), root_approval_id=grant["approval_id"], issuer="synthetic-continuation-only", mode="synthetic", not_before=(now-timedelta(seconds=1)).isoformat(), expires_at=(now+timedelta(minutes=6)).isoformat(), runtime_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), closure_evidence_sha256=anchor.files["failure.json"]["bytes_sha256"], epoch_id=str(uuid4()), requests=[grant["requests"][0]], source=source.scope(), inherited_hold_nano=50000000, child_reserve_nano=50000000, max_total_nano=100000000, max_total_attempts=2, max_child_attempts=1, max_child_count=1, max_child_generation=1)
    async def verify(**scope):
        return scope["mode"] == "synthetic" and scope["parent"] == anchor.scope() and scope["receipt_sha256"] == digest(receipt) and scope["closure_evidence_sha256"] == anchor.files["failure.json"]["bytes_sha256"]
    authority_path = Path(directory) / "synthetic-external-issuance.json"
    receipt["issuance_authority_sha256"] = digest(dict(synthetic_only=True, path=str(authority_path), namespace=digest(anchor.scope())))
    issuance = synthetic_issuance_authority(authority_path, anchor, initialize_for_fixture=receipt)
    permission = ContinuationPermission(anchor, digest(receipt), receipt["issuer"], "synthetic", verify, issuance)
    return permission, receipt, source


async def verify_synthetic_continuation_database(directory):
    """One actual new child epoch; the parent is immutable synthetic history."""
    permission, receipt, source = synthetic_continuation_fixture(directory)
    before = {name: read_fixed(permission.anchor.path / name, 0o600)[0] for name in permission.anchor.files}
    cap = await issue_continuation(permission, receipt, source)
    hooks = ContinuationHooks(synthetic=True)
    result = await run_continuation(cap, source=source, synthetic=True, hooks=hooks)
    raw = decode(read_fixed(permission.anchor.path / CONTINUATION_SLOT / "state.json", 0o600)[0])
    journal = raw["journal"]
    phases = [event["phase"] for event in journal]
    account = next(event for event in journal if event["phase"] == "final_accounting")
    local = account["child_ledger"]
    if raw["status"] != "closed" or raw["rights"] != dict(count=1, generation=1) or (local["count"], local["generation"], local["reserved"]) != (1, 1, 50000000) or account["total_hold_nano"] != 100000000 or account["total_estimated_nano"] is not None or len(local["attempts"]) != 1 or next(iter(local["attempts"].values()))["observation"]["state"] != "observed":
        raise ControllerError("SYNTHETIC_EXPECTATION")
    if not phases.index("root_count_authority_ACK") < phases.index("local_count_ACK_before_supplier") < phases.index("root_generation_authority_ACK") < phases.index("final_accounting") < phases.index("cleanup_confirmed"):
        raise ControllerError("SYNTHETIC_EXPECTATION")
    count_before = next(e["local_before"] for e in journal if e["phase"] == "root_count_authority_ACK")
    generation_before = next(e["local_before"] for e in journal if e["phase"] == "root_generation_authority_ACK")
    if count_before != dict(count=0, generation=0, reserved=0) or generation_before != dict(count=1, generation=0, reserved=50000000):
        raise ControllerError("SYNTHETIC_EXPECTATION")
    for _ in range(2):
        try:await run_continuation(cap, source=source, synthetic=True, hooks=hooks)
        except ControllerError:pass
        else:raise ControllerError("SYNTHETIC_RESTART_NOT_BLOCKED")
    for name, value in before.items():
        if read_fixed(permission.anchor.path / name, 0o600)[0] != value:
            raise ControllerError("CONTINUATION_ANCESTRY")
    if not hooks.owner._removed or any(hooks.observed.values()):
        raise ControllerError("CLEANUP_UNCONFIRMED")
    return dict(groups=5, parent_is_synthetic_history=True, child_count=1, child_generation=1,
                parent_hold_nano=50000000, child_hold_nano=50000000, total_hold_nano=100000000,
                total_attempts_consumed=2, total_estimated_nano=None, root_rights=raw["rights"],
                parent_unchanged=True, replay_restart_blocked=True, resource_removed=True,
                real_provider_requests=0, observed_denials=dict(hooks.observed),
                diagnostic=result["diagnostic"], journal_events=len(journal))


# v1.6 is a new approval aggregate, never a continuation/closed-grant override.
AGGREGATE_END = datetime(2026, 11, 10, 21, tzinfo=timezone.utc)
AGGREGATE_WINDOW = (datetime.fromisoformat('2026-11-11T00:49:56.734502+00:00'), datetime(2026,11,11,2,40,20,tzinfo=timezone.utc))
_AGGREGATE_SEAL = object()


@dataclass(frozen=True, repr=False)
class CoordinationHistory:
    """Existing private read/CAS history retains bootstrap, heads and uncertainty."""
    identity_sha256: str
    mode: str
    read: object = field(repr=False)
    compare_exchange: object = field(repr=False)


@dataclass(repr=False)
class AggregatePermission:
    path: Path
    header: dict = field(repr=False)
    history: CoordinationHistory = field(repr=False)
    verify: object = field(repr=False)
    code_root: ReviewedCodeRoot | None = field(default=None, repr=False)
    attempted: bool = field(default=False, init=False)


@dataclass(repr=False)
class AggregateCapability:
    seal: object = field(repr=False)
    permission: AggregatePermission = field(repr=False)
    binding: dict
    head: dict
    uncertain: bool = False
    cancelled: bool = False


def aggregate_header(permission):
    h = permission.header
    keys = {'schema','approval_event','mode','issuer','bootstrap_id','not_before','expires_at',
            'limit_nano','carry_nano','carry_hashes','runtime_sha256','coordination_sha256','source_sha256'}
    if type(h) is not dict or set(h) != keys or h['schema'] != 'cf026.aggregate.v1' or h['mode'] not in {'live','synthetic'} or not isinstance(h['approval_event'],str) or re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{1,80}',h['approval_event']) is None:
        raise ControllerError('AGGREGATE_SCOPE')
    for k in ('issuer','bootstrap_id','runtime_sha256','coordination_sha256','source_sha256'):
        if type(h[k]) is not str or re.fullmatch(r'[a-f0-9]{64}',h[k]) is None:
            raise ControllerError('AGGREGATE_SCOPE')
    if type(h['limit_nano']) is not int or h['limit_nano'] != 1000000000 or type(h['carry_nano']) is not int or h['carry_nano'] != 50000000 or type(h['carry_hashes']) is not dict or set(h['carry_hashes']) != {'grant','state','closure'} or any(type(v) is not str or re.fullmatch(r'[a-f0-9]{64}',v) is None for v in h['carry_hashes'].values()):
        raise ControllerError('AGGREGATE_SCOPE')
    history = permission.history
    if type(history) is not CoordinationHistory or history.mode != h['mode'] or history.identity_sha256 != h['coordination_sha256'] or not callable(history.read) or not callable(history.compare_exchange) or not callable(permission.verify):
        raise ControllerError('AGGREGATE_HISTORY')
    path = no_links(permission.path)
    if not path.is_absolute():raise ControllerError('AGGREGATE_SCOPE')
    if h['mode'] == 'live':
        if type(permission.code_root) is not ReviewedCodeRoot:raise ControllerError('AGGREGATE_SCOPE')
        permission.code_root.check()
        if path != permission.code_root.path.parent / '.cf026-openai-test-budget' / h['approval_event']:
            raise ControllerError('AGGREGATE_SCOPE')
    if h['runtime_sha256'] != hashlib.sha256(read_fixed(Path(__file__),0o644,limit=131072)[0]).hexdigest() or h['mode']=='live' and not AGGREGATE_WINDOW[0]<=parse_expiry(h['not_before'])<parse_expiry(h['expires_at'])<=AGGREGATE_WINDOW[1] or parse_expiry(h['not_before']) >= parse_expiry(h['expires_at']):
        raise ControllerError('AGGREGATE_SCOPE')
    return h


def aggregate_deadline(header):
    expiry=parse_expiry(header['expires_at'])
    return min(expiry,AGGREGATE_WINDOW[1]) if header['mode']=='live' else expiry


async def aggregate_authorized(permission, *, cleanup=False):
    h = aggregate_header(permission)
    if not cleanup:
        now = datetime.now(timezone.utc)
        if not parse_expiry(h['not_before']) <= now < aggregate_deadline(h):
            raise ControllerError('AGGREGATE_EXPIRED')
        async with asyncio.timeout(min(5,(parse_expiry(h['expires_at'])-now).total_seconds())):
            valid = await permission.verify(header_sha256=digest(h),event_sha256=digest(h['approval_event']),mode=h['mode'])
        if valid is not True:raise ControllerError('EXTERNAL_APPROVAL_REQUIRED')
        if datetime.now(timezone.utc) >= aggregate_deadline(h):raise ControllerError('AGGREGATE_EXPIRED')
    return h


def aggregate_history_initial(permission):
    return dict(schema='cf026.aggregate.history.v1',event_sha256=digest(permission.header['approval_event']),
                root=str(permission.path),bootstrap_id=permission.header['bootstrap_id'],header_sha256=digest(permission.header),
                phase='offered',binding=None,head=None,pending=None,frozen=False)


async def aggregate_history_read(permission):
    async with asyncio.timeout(5):value = await permission.history.read()
    base = aggregate_history_initial(permission)
    if type(value) is not dict or set(value) != set(base) or any(value[k] != base[k] for k in ('schema','event_sha256','root','bootstrap_id','header_sha256')):
        raise ControllerError('AGGREGATE_HISTORY')
    return value


async def aggregate_history_cas(permission, old, new):
    async with asyncio.timeout(5):
        ack = await permission.history.compare_exchange(expected=old,replacement=new)
        if type(ack) is not dict or ack != new or await aggregate_history_read(permission) != new:
            raise ControllerError('AGGREGATE_ACK_UNKNOWN')


def aggregate_head(path, state):
    raw,stamp = read_fixed(path,0o600)
    if decode(raw) != state:raise ControllerError('AGGREGATE_HEAD')
    return dict(sequence=state['sequence'],sha256=hashlib.sha256(raw).hexdigest(),identity=stamp)


async def bootstrap_aggregate(permission):
    """Coordinator-only once. Runtime never calls this or discovers a root."""
    attempted = None
    try:
        if type(permission) is not AggregatePermission or permission.attempted:raise ControllerError('AGGREGATE_USED')
        permission.attempted = True
        await aggregate_authorized(permission)
        offered = aggregate_history_initial(permission)
        if await aggregate_history_read(permission) != offered:raise ControllerError('AGGREGATE_USED')
        attempted = offered | dict(phase='attempted',pending={'transition':'bootstrap','identity':permission.header['bootstrap_id']})
        await aggregate_history_cas(permission,offered,attempted)
        await aggregate_authorized(permission)
        root = no_links(permission.path)
        root.mkdir(mode=0o700)
        fsync_directory(root.parent)
        exclusive_private_file(root/'execution.lock',{})
        exclusive_private_file(root/'header.json',permission.header)
        (root/'children').mkdir(mode=0o700)
        state = dict(schema='cf026.aggregate.state.v1',sequence=0,previous=None,total_reserved_nano=50000000,
                     cancelled=False,frozen=False,allocations={})
        exclusive_private_file(root/'state.json',state)
        fsync_directory(root)
        header_raw,header_stamp = read_fixed(root/'header.json',0o600)
        if decode(header_raw) != permission.header:raise ControllerError('AGGREGATE_ACK_UNKNOWN')
        binding = dict(directory=directory_identity(root),lock=regular(root/'execution.lock',0o600),
                       header=header_stamp,header_sha256=hashlib.sha256(header_raw).hexdigest(),children=directory_identity(root/'children'))
        head = aggregate_head(root/'state.json',state)
        initialized = attempted | dict(phase='initialized',binding=binding,head=head,pending=None)
        await aggregate_history_cas(permission,attempted,initialized)
        return AggregateCapability(_AGGREGATE_SEAL,permission,binding,head)
    except asyncio.CancelledError:raise
    except ControllerError:raise
    except Exception:raise ControllerError('AGGREGATE_ACK_UNKNOWN') from None


async def reopen_aggregate(permission, *, expected_binding, expected_head, confirm_restart=None):
    """Only independently retained bootstrap identity + confirmed head may reopen."""
    await aggregate_authorized(permission)
    if not callable(confirm_restart):raise ControllerError('AGGREGATE_FROZEN')
    async with asyncio.timeout(5):
        confirmed=await confirm_restart(bootstrap_id=permission.header['bootstrap_id'],binding_sha256=digest(expected_binding),head_sha256=digest(expected_head))
    if confirmed is not True:raise ControllerError('AGGREGATE_FROZEN')
    history = await aggregate_history_read(permission)
    if history['phase'] != 'initialized' or history['pending'] is not None or history['frozen'] or history['binding'] != expected_binding or history['head'] != expected_head:
        raise ControllerError('AGGREGATE_FROZEN')
    cap = AggregateCapability(_AGGREGATE_SEAL,permission,expected_binding,expected_head)
    async with AggregateSession(cap) as session:
        state=await session.check()
        if any(a['issue_consumed'] and (a['child'] is None or a['start_consumed'] and a['outcome'] is None) for a in state['allocations'].values()):
            raise ControllerError('AGGREGATE_FROZEN')
    return cap


class AggregateSession:
    """One allocator session holds root flock through child accounting/cleanup."""
    def __init__(self, cap):
        if type(cap) is not AggregateCapability or cap.seal is not _AGGREGATE_SEAL:raise ControllerError('AGGREGATE_SCOPE')
        self.cap,self.permission = cap,cap.permission
        self.fd = None
        self.mutations = asyncio.Lock()
        self.running = False

    async def __aenter__(self):
        root = self.permission.path
        if directory_identity(root) != self.cap.binding['directory']:raise ControllerError('AGGREGATE_HEAD')
        fd = os.open(root/'execution.lock',os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            if identity(os.fstat(fd)) != self.cap.binding['lock'] or regular(root/'execution.lock',0o600) != self.cap.binding['lock']:raise ControllerError('LOCK_DRIFT')
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise ControllerError('APPROVAL_BUSY') from None
            self.fd = fd
            await self.check()
            return self
        except BaseException:
            self.fd = None;os.close(fd);raise

    async def __aexit__(self,*_):
        if self.fd is not None:os.close(self.fd);self.fd = None

    async def check(self, *, cleanup=False):
        try:
            return await self._check(cleanup=cleanup)
        except ControllerError as error:
            if error.stage not in {'AGGREGATE_EXPIRED','AGGREGATE_FROZEN'}:self.cap.uncertain=True
            raise
        except BaseException:
            self.cap.uncertain=True
            raise

    async def _check(self, *, cleanup=False):
        cap,root = self.cap,self.permission.path
        if self.fd is None:raise ControllerError('LOCK_REQUIRED')
        if cap.uncertain:raise ControllerError('AGGREGATE_FROZEN')
        h = await aggregate_authorized(self.permission,cleanup=cleanup)
        b = cap.binding
        if directory_identity(root) != b['directory'] or directory_identity(root/'children') != b['children'] or identity(os.fstat(self.fd)) != b['lock'] or regular(root/'execution.lock',0o600) != b['lock']:
            raise ControllerError('AGGREGATE_HEAD')
        raw,_ = read_fixed(root/'header.json',0o600,b['header'])
        if hashlib.sha256(raw).hexdigest() != b['header_sha256'] or decode(raw) != h:raise ControllerError('AGGREGATE_HEAD')
        raw,_ = read_fixed(root/'state.json',0o600,cap.head['identity'])
        state = decode(raw)
        if hashlib.sha256(raw).hexdigest() != cap.head['sha256'] or state.get('sequence') != cap.head['sequence']:raise ControllerError('AGGREGATE_HEAD')
        if set(state) != {'schema','sequence','previous','total_reserved_nano','cancelled','frozen','allocations'} or state['schema'] != 'cf026.aggregate.state.v1' or type(state['allocations']) is not dict or len(state['allocations'])>9 or type(state['cancelled']) is not bool or type(state['frozen']) is not bool or state['total_reserved_nano'] != 50000000+sum(a['reserve_nano'] for a in state['allocations'].values()) or state['total_reserved_nano']>1000000000:
            raise ControllerError('AGGREGATE_HEAD')
        history = await aggregate_history_read(self.permission)
        if history['phase'] != 'initialized' or history['binding'] != b or history['head'] != cap.head or history['pending'] is not None or history['frozen']:
            cap.uncertain = True;raise ControllerError('AGGREGATE_FROZEN')
        if not cleanup and (state['cancelled'] or state['frozen'] or cap.cancelled):raise ControllerError('AGGREGATE_FROZEN')
        if not cleanup and datetime.now(timezone.utc)>=aggregate_deadline(h):raise ControllerError('AGGREGATE_EXPIRED')
        return state

    async def commit(self, state, transition, allocation=None, *, cleanup=False):
        old = await self.check(cleanup=cleanup)
        if old['sequence']>=100:raise ControllerError('PRIVATE_STATE_LIMIT')
        if set(state)!=set(old) or old['cancelled'] and not state['cancelled'] or old['frozen'] and not state['frozen'] or not set(old['allocations'])<=set(state['allocations']) or len(state['allocations'])>9:
            raise ControllerError('AGGREGATE_SCOPE')
        if state['total_reserved_nano']!=50000000+100000000*len(state['allocations']) or not old['total_reserved_nano']<=state['total_reserved_nano']<=1000000000:
            raise ControllerError('AGGREGATE_LIMIT')
        for aid,a in old['allocations'].items():
            b=state['allocations'][aid]
            if set(a)!=set(b) or any(a[k]!=b[k] for k in ('intent_sha256','child_id','reserve_nano','nonce')) or any(type(b[k]) is not bool or a[k] and not b[k] for k in ('issue_consumed','start_consumed')) or a['child'] is not None and a['child']!=b['child'] or a['outcome'] is not None and a['outcome']!=b['outcome'] or a['accounting'] is not None and a['accounting']!=b['accounting']:
                raise ControllerError('AGGREGATE_SCOPE')
            changed={k for k in a if a[k]!=b[k]}
            allowed={'issue':{'issue_consumed'},'bind':{'child'},'start':{'start_consumed'},'terminal':{'outcome'},'accounting':{'accounting'}}.get(transition,set())
            if changed and (aid!=allocation or changed!=allowed):raise ControllerError('AGGREGATE_SCOPE')
            if b['start_consumed'] and (not b['issue_consumed'] or b['child'] is None):raise ControllerError('AGGREGATE_SCOPE')
        added=set(state['allocations'])-set(old['allocations'])
        if added:
            if transition!='reserve' or added!={allocation}:raise ControllerError('AGGREGATE_SCOPE')
            a=state['allocations'][allocation]
            if (a['issue_consumed'],a['start_consumed'],a['child'],a['outcome'],a['accounting'],a['reserve_nano'])!=(False,False,None,None,None,100000000):raise ControllerError('AGGREGATE_SCOPE')
        state = state | dict(sequence=old['sequence']+1,previous=self.cap.head['sha256'])
        raw = canonical(state).encode()
        if len(raw)>65536:raise ControllerError('PRIVATE_STATE_LIMIT')
        history = await aggregate_history_read(self.permission)
        pending = history | dict(pending=dict(transition=transition,allocation=allocation,
            sequence=state['sequence'],sha256=hashlib.sha256(raw).hexdigest(),last_confirmed=self.cap.head))
        self.cap.uncertain = True
        try:
            await aggregate_history_cas(self.permission,history,pending)
            await aggregate_authorized(self.permission,cleanup=cleanup)
            path = self.permission.path/'state.pending'
            exclusive_private_file(path,state)
            previous,_ = read_fixed(self.permission.path/'state.json',0o600,self.cap.head['identity'])
            if hashlib.sha256(previous).hexdigest()!=self.cap.head['sha256']:raise ControllerError('AGGREGATE_HEAD')
            os.replace(path,self.permission.path/'state.json');fsync_directory(self.permission.path)
            head = aggregate_head(self.permission.path/'state.json',state)
            confirmed = pending | dict(head=head,pending=None)
            await aggregate_history_cas(self.permission,pending,confirmed)
            self.cap.head = head  # Only after both local and coordination ACK.
            self.cap.uncertain = False
        except asyncio.CancelledError:raise
        except Exception:raise ControllerError('AGGREGATE_ACK_UNKNOWN') from None

    def validate_intent(self, intent, source):
        keys = {'kind','allocation_id','child_id','child_path','nonce','reserve_nano','template'}
        if type(intent) is not dict or set(intent)!=keys or intent['kind']!='supervisor_batch' or type(intent['reserve_nano']) is not int or intent['reserve_nano']!=100000000:
            raise ControllerError('AGGREGATE_SCOPE')
        for k in ('allocation_id','child_id'):UUID(intent[k])
        if type(intent['nonce']) is not str or re.fullmatch(r'[a-f0-9]{64}',intent['nonce']) is None or Path(intent['child_path']) != self.permission.path/'children'/intent['child_id']:
            raise ControllerError('AGGREGATE_SCOPE')
        template = intent['template']
        if 'state_store' in template or template['approval_id']!=intent['child_id'] or parse_expiry(template['expires_at'])>parse_expiry(self.permission.header['expires_at']) or digest(source.scope())!=self.permission.header['source_sha256']:
            raise ControllerError('AGGREGATE_SCOPE')
        validate_scope(template|dict(state_store={}),source,synthetic=self.permission.header['mode']=='synthetic')
        queries=['현대건설 외국인 말고 3주 수급','현대건설 어제 말고 외국인 말고 기관 수급']
        for i,item in enumerate(template['requests']):
            d=item['prepare_body']['draft']
            answers=[] if i==0 else [dict(answer_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',slot='views',value='수급만')]
            if d != dict(original_query=queries[i],answers=answers,revision=i,selected_ticker=None,candidate_ref=None):raise ControllerError('AGGREGATE_SCOPE')
        source.check()

    async def authorize_intent(self,intent):
        async with asyncio.timeout(5):
            valid=await self.permission.verify(phase='allocation',header_sha256=digest(self.permission.header),event_sha256=digest(self.permission.header['approval_event']),mode=self.permission.header['mode'],intent_sha256=digest(intent))
        if valid is not True:raise ControllerError('EXTERNAL_APPROVAL_REQUIRED')

    async def allocate(self, intent, source):
        async with self.mutations:
            state = await self.check()
            if self.running:raise ControllerError('AGGREGATE_USED')
            amount = intent.get('reserve_nano') if type(intent) is dict else None
            if type(intent) is dict and intent.get('allocation_id') in state['allocations']:
                self.validate_intent(intent,source)
                existing=state['allocations'][intent['allocation_id']]
                if existing['intent_sha256']!=digest(intent):raise ControllerError('AGGREGATE_SCOPE')
                return decode(canonical(existing))
            if type(amount) is int and state['total_reserved_nano']+amount>1000000000:raise ControllerError('AGGREGATE_LIMIT')
            self.validate_intent(intent,source)
            await self.authorize_intent(intent)
            state=await self.check()
            if any(a['child_id']==intent['child_id'] for a in state['allocations'].values()):raise ControllerError('AGGREGATE_USED')
            aid=intent['allocation_id']
            if len(state['allocations'])>=9:raise ControllerError('AGGREGATE_LIMIT')
            entry=dict(intent_sha256=digest(intent),child_id=intent['child_id'],reserve_nano=100000000,issue_consumed=False,start_consumed=False,
                       child=None,outcome=None,accounting=None,nonce=intent['nonce'])
            state['allocations'][aid]=entry;state['total_reserved_nano']+=100000000
            await self.commit(state,'reserve',aid)
            return decode(canonical(entry))

    async def allocation(self, intent, source, *, cleanup=False):
        state=await self.check(cleanup=cleanup);self.validate_intent(intent,source)
        if not cleanup:
            await self.authorize_intent(intent)
            state=await self.check()
        entry=state['allocations'].get(intent['allocation_id'])
        if entry is None or entry['intent_sha256']!=digest(intent) or entry['nonce']!=intent['nonce']:raise ControllerError('AGGREGATE_SCOPE')
        return state,entry

    async def issue(self, intent, source):
        async with self.mutations:
            state,entry=await self.allocation(intent,source)
            if entry['issue_consumed']:raise ControllerError('AGGREGATE_USED')
            entry['issue_consumed']=True
            await self.commit(state,'issue',intent['allocation_id'])
            try:
                await self.check()
                root=no_links(Path(intent['child_path']));root.mkdir(mode=0o700);fsync_directory(root.parent)
                exclusive_private_file(root/'execution.lock',{})
                store=PrivateStore(root)
                grant=intent['template']|dict(state_store=store.scope())
                exclusive_private_file(root/'grant.json',grant)
                issued=dict(schema='cf026.state.v1',approval_id=grant['approval_id'],grant_sha256=digest(grant),status='issued',journal=[])
                exclusive_private_file(root/'state.json',issued);fsync_directory(root)
                raw,stamp=read_fixed(root/'grant.json',0o600)
                binding=dict(scope=store.scope(),grant_identity=stamp,grant_bytes_sha256=hashlib.sha256(raw).hexdigest(),
                             grant_sha256=digest(grant),issued=regular(root/'state.json',0o600),issued_sha256=digest(issued))
                state,entry=await self.allocation(intent,source)
                entry['child']=binding
                await self.commit(state,'bind',intent['allocation_id'])
                return binding
            except BaseException:
                self.cap.uncertain=True
                raise

    async def child(self,intent,source, *, initial=False,cleanup=False):
        _,entry=await self.allocation(intent,source,cleanup=cleanup)
        b=entry['child']
        if b is None:raise ControllerError('AGGREGATE_SCOPE')
        store=PrivateStore(Path(intent['child_path']))
        if store.scope()!=b['scope']:raise ControllerError('AGGREGATE_HEAD')
        raw,_=read_fixed(store.directory/'grant.json',0o600,b['grant_identity'])
        grant=decode(raw)
        if hashlib.sha256(raw).hexdigest()!=b['grant_bytes_sha256'] or digest(grant)!=b['grant_sha256'] or grant != intent['template']|dict(state_store=store.scope()):raise ControllerError('AGGREGATE_SCOPE')
        if initial:
            raw,_=read_fixed(store.directory/'state.json',0o600,b['issued'])
            value=decode(raw)
            if digest(value)!=b['issued_sha256'] or value['status']!='issued':raise ControllerError('AGGREGATE_USED')
        return store,entry

    async def start(self,intent,source, *, hooks=None):
        async with self.mutations:
            if self.running:raise ControllerError('AGGREGATE_USED')
            store,entry=await self.child(intent,source,initial=True)
            if entry['start_consumed']:raise ControllerError('AGGREGATE_USED')
            state,entry=await self.allocation(intent,source);entry['start_consumed']=True
            await self.commit(state,'start',intent['allocation_id'])
            await self.check()
            self.running=True
        active=object();ticket=active
        async def verify(**scope):
            if active is not ticket or not self.running:return False
            _,current=await self.child(intent,source)
            return current['start_consumed'] and current['nonce']==intent['nonce'] and scope['scope_sha256']==current['child']['grant_sha256']
        async def parent_accounting(account):
            async with self.mutations:
                state,current=await self.allocation(intent,source,cleanup=True)
                ledger=account.get('state',{})
                current['accounting']=dict(sha256=digest(account),count=ledger.get('count'),generation=ledger.get('generation'),http='unknown')
                await self.commit(state,'accounting',intent['allocation_id'],cleanup=True)
        store._aggregate_ack=parent_accounting
        approval=ExternalApproval(entry['child']['grant_sha256'],intent['template']['issuer'],verify)
        error=None;result=None
        try:
            result=await run_controller(store,approval=approval,key_source=source,
                synthetic=self.permission.header['mode']=='synthetic',hooks=hooks)
        except BaseException as caught:error=caught
        finally:
            active=None
            async with self.mutations:
                try:
                    async with asyncio.timeout(5):
                        state,current=await self.allocation(intent,source,cleanup=True)
                        outcome=dict(code=normalized_failure(error) if error else 'finished',child_state='unknown',accounting_sha256=None,cleanup_confirmed=False,count_requests=None,generation_requests=None,estimated_nano=None,http='unknown')
                        try:
                            child=PrivateStore(Path(intent['child_path']))
                            with child.locked():
                                account=[e for e in child.state['journal'] if e.get('phase')=='final_accounting']
                                outcome.update(child_state=child.state['status'],accounting_sha256=digest(account[-1]) if account else None,
                                               cleanup_confirmed=child.state['journal'][-1].get('phase')=='cleanup_confirmed')
                                ledger=account[-1].get('state') if account else None
                                if type(ledger) is dict:
                                    outcome.update(count_requests=ledger['count'],generation_requests=ledger['generation'])
                                    observations=[a.get('observation',{}) for a in ledger['attempts'].values()]
                                    if observations and all(type(o.get('estimated_nano')) is int for o in observations):outcome['estimated_nano']=sum(o['estimated_nano'] for o in observations)
                        except Exception:state['frozen']=True
                        current['outcome']=outcome
                        if error is not None:state['frozen']=True
                        await self.commit(state,'terminal',intent['allocation_id'],cleanup=True)
                except BaseException as caught:
                    self.cap.uncertain=True;error=caught if isinstance(caught,asyncio.CancelledError) else error or caught
                self.running=False
        if isinstance(error,asyncio.CancelledError):raise error
        if error is not None:raise ControllerError(normalized_failure(error)) from None
        return result

    async def cancel(self):
        self.cap.cancelled=True
        async with self.mutations:
            state=await self.check(cleanup=True);state['cancelled']=True
            await self.commit(state,'cancel',cleanup=True)


def aggregate_boundary(function):
    async def bounded(*args,**kwargs):
        try:return await function(*args,**kwargs)
        except asyncio.CancelledError:raise
        except ControllerError:raise
        except Exception:
            if args and isinstance(args[0],AggregateSession):args[0].cap.uncertain=True
            raise ControllerError('AGGREGATE_SCOPE') from None
    return bounded


bootstrap_aggregate=aggregate_boundary(bootstrap_aggregate)
reopen_aggregate=aggregate_boundary(reopen_aggregate)
for _method in ('__aenter__','allocate','issue','start','cancel'):
    setattr(AggregateSession,_method,aggregate_boundary(getattr(AggregateSession,_method)))


def synthetic_aggregate_fixture(directory):
    """Explicit fake coordinator history provisioning; never a runtime fallback."""
    from uuid import uuid4
    from datetime import timedelta
    from scripts.cf023_supervisor_meaning_check import load_meaning
    load_meaning()
    from src.supervisor.domain.meaning import Draft
    directory=no_links(directory)
    if any(directory.iterdir()):raise ControllerError('SYNTHETIC_DIRECTORY_NOT_EMPTY')
    path=directory/'coordination.json';lock=directory/'coordination.lock'
    external_id=digest(dict(synthetic_only=True,path=str(path)))
    exclusive_private_file(lock,{})
    stamp=regular(lock,0o600)
    async def read():return decode(read_fixed(path,0o600)[0])
    async def compare_exchange(*,expected,replacement):
        fd=os.open(lock,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            if identity(os.fstat(fd))!=stamp or regular(lock,0o600)!=stamp:raise ControllerError('AGGREGATE_HISTORY')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if await read()!=expected:raise ControllerError('AGGREGATE_HISTORY')
            pending=path.with_name('coordination.pending')
            exclusive_private_file(pending,replacement);os.replace(pending,path);fsync_directory(directory)
            return await read()
        finally:os.close(fd)
    history=CoordinationHistory(external_id,'synthetic',read,compare_exchange)
    raw=b'OPENAI_API_KEY=cf026-unused-synthetic-source\n'
    key_path=directory/'synthetic-input.txt'
    fd=os.open(key_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
    try:os.write(fd,raw);os.fsync(fd)
    finally:os.close(fd)
    source=KeySource(key_path,regular(key_path,0o644),True)
    now=datetime.now(timezone.utc);expiry=now+timedelta(minutes=6)
    header=dict(schema='cf026.aggregate.v1',approval_event='synthetic_'+uuid4().hex,mode='synthetic',issuer=digest('synthetic issuer'),
                bootstrap_id=digest(str(uuid4())),not_before=(now-timedelta(seconds=1)).isoformat(),expires_at=expiry.isoformat(),
                limit_nano=1000000000,carry_nano=50000000,carry_hashes=dict(grant='1'*64,state='2'*64,closure='3'*64),
                runtime_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),coordination_sha256=external_id,source_sha256=digest(source.scope()))
    approved=set()
    async def verify(**scope):
        base=dict(header_sha256=digest(header),event_sha256=digest(header['approval_event']),mode='synthetic')
        return scope==base or scope.get('intent_sha256') in approved and scope==base|dict(phase='allocation',intent_sha256=scope['intent_sha256'])
    permission=AggregatePermission(directory/'budget',header,history,verify)
    exclusive_private_file(path,aggregate_history_initial(permission));fsync_directory(directory)
    drafts=[]
    for i,query in enumerate(['현대건설 외국인 말고 3주 수급','현대건설 어제 말고 외국인 말고 기관 수급']):
        answers=[] if i==0 else [dict(answer_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',slot='views',value='수급만')]
        drafts.append(Draft(original_query=query,answers=answers,revision=i))
    child_id=str(uuid4())
    template=synthetic_grant(source,synthetic_requests(drafts),header['not_before'],header['expires_at'],child_id)
    intent=dict(kind='supervisor_batch',allocation_id=str(uuid4()),child_id=child_id,child_path=str(permission.path/'children'/child_id),nonce=digest(str(uuid4())),reserve_nano=100000000,template=template)
    approved.add(digest(intent))
    return permission,intent,source


class AggregateSyntheticHooks(OwnedHooks):
    """Exact approved drafts, existing DI and reviewed mock; never a live hook."""
    async def verify(self,store,approval,source,proof,principal,binding,item,index,*,observation):
        if not self.synthetic or binding.mode!='synthetic' or store.grant['mode']!='synthetic':raise ControllerError('LIVE_GATE_CLOSED')
        from scripts import cf023_supervisor_meaning_check as v
        from src.modules.supervisor.domain.contracts import PreparationRequest
        from src.supervisor.infrastructure.openai_meaning_gateway import CounterAgreement,INPUT_FIELDS,COUNT_DOCUMENTATION
        stages=[]
        async def key():
            await approval_gate(store,approval,source,synthetic=True)
            stages.append('synthetic_key_supplied')
            return 'cf024-synthetic-key-only'
        deferred=v.DeferredKeySource(key,object())
        deadline=min(asyncio.get_running_loop().time()+60,asyncio.get_running_loop().time()+(parse_expiry(store.grant['expires_at'])-datetime.now(timezone.utc)).total_seconds())
        delegate=v.SyntheticAuthority(parse_expiry(store.grant['expires_at']),deferred)
        class Authority:
            async def verify(self,**scope):
                await approval_gate(store,approval,source,synthetic=True)
                return await delegate.verify(**scope)
        return await synthetic_preparation_assembly(body=PreparationRequest.model_validate(item['prepare_body']),proof=proof,principal=principal,binding=binding,
            authority=Authority(),agreement=CounterAgreement(COUNT_DOCUMENTATION,v.SYNTHETIC_MAPPING_SHA,INPUT_FIELDS,1),deferred=deferred,deadline=deadline,stages=stages,scenario='success' if index==0 else 'missing_usage')


async def verify_synthetic_aggregate_database(directory):
    """One new aggregate allocation wraps the unchanged synthetic child runner."""
    permission,intent,source=synthetic_aggregate_fixture(directory)
    cap=await bootstrap_aggregate(permission)
    hooks=AggregateSyntheticHooks(synthetic=True)
    async with AggregateSession(cap) as session:
        await session.allocate(intent,source)
        await session.issue(intent,source)
        result=await session.start(intent,source,hooks=hooks)
        state=await session.check()
        entry=state['allocations'][intent['allocation_id']]
        if state['total_reserved_nano']!=150000000 or not entry['issue_consumed'] or not entry['start_consumed'] or not entry['outcome']['cleanup_confirmed'] or not result['approval_closed'] or not hooks.owner._removed:
            raise ControllerError('SYNTHETIC_EXPECTATION')
        excessive=dict(intent,kind='flow',allocation_id=str(__import__('uuid').uuid4()),reserve_nano=913500000)
        try:await session.allocate(excessive,source)
        except ControllerError as error:
            if error.stage!='AGGREGATE_LIMIT':raise
        else:raise ControllerError('SYNTHETIC_EXPECTATION')
        try:await session.start(intent,source,hooks=hooks)
        except ControllerError:pass
        else:raise ControllerError('SYNTHETIC_RESTART_NOT_BLOCKED')
    if any(hooks.observed.values()):raise ControllerError('ISOLATION_DENIAL')
    with PrivateStore(Path(intent['child_path'])).locked() as child:
        ledger=next(e['state'] for e in child.state['journal'] if e['phase']=='final_accounting')
        if (ledger['count'],ledger['generation'],ledger['reserved'],ledger['blocked'])!=(2,2,100000000,True):raise ControllerError('SYNTHETIC_EXPECTATION')
    return dict(groups=4,aggregate_reserved_nano=150000000,remaining_nano=850000000,aggregate_estimated_nano=None,
                issue_consumed=True,start_consumed=True,child_count=2,child_generation=2,child_unknown_hold=True,
                flow_over_limit_rejected=True,resource_removed=True,real_provider_requests=0,
                coordinator_history='synthetic file/CAS simulation',observed_denials=hooks.observed)
