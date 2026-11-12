"""One fixed successor attempt. No entry point, issuer, credential or DB on import.

The private coordinator must supply independently retained authority and file pins.
Synthetic callbacks exercise this boundary; they are never a live authority adapter.
"""
import asyncio
import ast
from contextlib import asynccontextmanager, contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import time
from uuid import UUID

from scripts import cf026_supervisor_live_controller as C


CODES = frozenset([
    'ACCOUNTING',
    'ALREADY_USED',
    'ANCESTRY_DRIFT',
    'ANCESTRY_SCOPE',
    'ANCESTRY_STATE',
    'AUTHORITY_ACK_UNKNOWN',
    'AUTHORITY_UNAVAILABLE',
    'CODE_DRIFT',
    'COUNTER_EVIDENCE',
    'DEFAULT_UNAVAILABLE',
    'DIAGNOSTIC_INVALID',
    'EPOCH_ACK_UNKNOWN',
    'EPOCH_ALREADY_EXISTS',
    'FINAL_LEDGER_UNCONFIRMED',
    'FIRST_REQUEST_ONLY',
    'FIRST_SETTLEMENT_UNCONFIRMED',
    'ISOLATION_DENIAL',
    'JOURNAL_ACK_UNKNOWN',
    'JOURNAL_DRIFT',
    'JOURNAL_LIMIT',
    'JOURNAL_SCOPE',
    'LEASE_DRIFT',
    'LEASE_EXPIRED',
    'LEASE_START',
    'LEDGER_LIMIT',
    'MEANING_REJECTED',
    'MEANING_NOT_SUPPLEMENTED',
    'NOT_STARTED',
    'PHASE_LIMIT',
    'PHASE_SCOPE',
    'PREPARATION_DRIFT',
    'REQUEST_DRIFT',
    'RETRY_EVIDENCE',
    'RETRY_SCOPE',
    'SCOPE',
    'SOURCE_SCOPE',
    'SUCCESSOR_CLOSED',
    'SUCCESSOR_FAILED',
    'SUPPLIER_ONCE',
])


class Closed(Exception):
    def __init__(self, code="SUCCESSOR_CLOSED"):
        self.code = code if type(code) is str and code in CODES else "SUCCESSOR_FAILED"
        super().__init__(self.code)


@dataclass(frozen=True, repr=False)
class Artifact:
    name: str
    path: Path
    stamp_json: str
    sha256: str

    def verify(self, base):
        path = C.no_links(self.path)
        if ".." in path.parts or not path.is_relative_to(base) or path.suffix != ".json" or ".env" in path.parts:
            raise Closed("ANCESTRY_SCOPE")
        raw, _ = C.read_fixed(path, 0o600, C.decode(self.stamp_json))
        if hashlib.sha256(raw).hexdigest() != self.sha256:
            raise Closed("ANCESTRY_DRIFT")
        return C.decode(raw)


@dataclass(frozen=True, repr=False)
class Authority:
    mode: str
    identity_sha256: str
    verify: object
    consume: object
    readback: object


@dataclass(frozen=True, repr=False)
class Scope:
    """Canonical reviewed bytes, not an approval by themselves."""
    document: str
    artifacts: tuple

    @property
    def data(self):
        return C.decode(self.document)

    @property
    def sha256(self):
        return hashlib.sha256(self.document.encode()).hexdigest()

    def check(self, source, authority, *, synthetic):
        d = self.data
        required = {"schema", "mode", "namespace", "predecessor_sha256", "invocation", "consent_at",
                    "predecessor", "artifacts", "request", "source", "counter", "semantic_sha256",
                    "price_sha256", "epoch_id", "authority_sha256", "module_sha256", "journal", "predecessor_bootstrap"}
        if set(d) not in (required, required | {"retry"}) or d["schema"] != "cf026.successor.scope.v1" or d["mode"] != ("synthetic" if synthetic else "live"):
            raise Closed("SCOPE")
        if (
            type(authority) is not Authority
            or authority.mode != d["mode"]
            or authority.identity_sha256 != d["authority_sha256"]
            or not all(callable(x) for x in (authority.verify, authority.consume, authority.readback))
        ):
            raise Closed("AUTHORITY_UNAVAILABLE")
        for key in ("namespace", "predecessor_sha256", "invocation", "authority_sha256", "module_sha256"):
            if type(d[key]) is not str or C.re.fullmatch(r"[a-f0-9]{64}", d[key]) is None:
                raise Closed("SCOPE")
        C.parse_expiry(d["consent_at"])
        UUID(d["epoch_id"])
        if type(source) is not C.KeySource or source.synthetic is not synthetic or source.scope() != d["source"]:
            raise Closed("SOURCE_SCOPE")
        source.check()
        module_hash = hashlib.sha256(C.read_fixed(Path(__file__), 0o644, limit=131072)[0]).hexdigest()
        if module_hash != d["module_sha256"]:
            raise Closed("CODE_DRIFT")
        base = source.path.parent if synthetic else source.code_root.path.parent
        if not synthetic:
            code_root = reviewed_execution_root(source, d, module_hash)
            original = code_root / "backend/scripts/cf026_successor.py"
            if hashlib.sha256(C.read_fixed(original, 0o644, limit=131072)[0]).hexdigest() != module_hash:
                raise Closed("CODE_DRIFT")
        names = {"header", "state", "child_grant", "child_state", "closure", "runtime",
                 "carry_grant", "carry_state", "carry_closure", "coordination"}
        if (
            type(self.artifacts) is not tuple
            or any(type(a) is not Artifact for a in self.artifacts)
            or len(self.artifacts) != len(names)
            or {a.name for a in self.artifacts} != names
        ):
            raise Closed("ANCESTRY_SCOPE")
        paths = {a.name: a.path for a in self.artifacts}
        root = paths["header"].parent
        carry_root = paths["carry_grant"].parent
        private_home = base / ".cf026-launcher-preparation-20261110"
        if (
            root.parent != base / ".cf026-openai-test-budget"
            or C.re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,80}", root.name) is None
            or C.digest(root.name) != d["namespace"]
            or carry_root.parent != base / ".cf026-live-approval"
            or C.re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,80}", carry_root.name) is None
        ):
            raise Closed("ANCESTRY_SCOPE")
        child_id = paths["child_grant"].parent.name
        UUID(child_id)
        if C.re.fullmatch(r"[a-f0-9]{64}", d["predecessor_bootstrap"]) is None:
            raise Closed("ANCESTRY_SCOPE")
        expected_paths = dict(header=root/"header.json", state=root/"state.json",
            child_grant=root/"children"/child_id/"grant.json", child_state=root/"children"/child_id/"state.json",
            closure=private_home/("outcome-"+d["predecessor_bootstrap"]+".json"),
            runtime=private_home/"reviewed-runtime.json", coordination=base/".cf026-live-coordination"/root.name/"state.json",
            carry_grant=carry_root/"grant.json", carry_state=carry_root/"state.json", carry_closure=carry_root/"failure.json")
        if paths != expected_paths:
            raise Closed("ANCESTRY_SCOPE")
        records = {a.name: a.verify(base) for a in self.artifacts}
        names = {"header", "state", "child_grant", "child_state", "closure", "runtime",
                 "carry_grant", "carry_state", "carry_closure", "coordination"}
        if len(records) != len(self.artifacts) or set(records) != names:
            raise Closed("ANCESTRY_SCOPE")
        pins = {a.name: a.sha256 for a in self.artifacts}
        if pins != d["artifacts"] or C.digest(pins) != d["predecessor_sha256"]:
            raise Closed("ANCESTRY_DRIFT")
        header, state = records["header"], records["state"]
        child, grant = records["child_state"], records["child_grant"]
        expected = dict(reserved_nano=150000000, carry_nano=50000000, allocation_nano=100000000,
                        count=1, generation=0, attempts=1, http="unknown", estimated_nano=None)
        if (
            d["predecessor"] != expected
            or any(type(d["predecessor"][k]) is not int for k in ("reserved_nano", "carry_nano", "allocation_nano", "count", "generation", "attempts"))
        ):
            raise Closed("ACCOUNTING")
        if (
            header.get("schema") != "cf026.aggregate.v1"
            or C.digest(header.get("approval_event")) != d["namespace"]
            or header.get("limit_nano") != 1000000000
            or header.get("carry_nano") != 50000000
            or header.get("carry_hashes") != {"grant": pins["carry_grant"], "state": pins["carry_state"], "closure": pins["carry_closure"]}
        ):
            raise Closed("ANCESTRY_STATE")
        allocations = state.get("allocations")
        if (
            state.get("schema") != "cf026.aggregate.state.v1"
            or state.get("frozen") is not True
            or state.get("total_reserved_nano") != 150000000
            or type(state.get("sequence")) is not int
            or type(allocations) is not dict
            or len(allocations) != 1
        ):
            raise Closed("ANCESTRY_STATE")
        allocation = next(iter(allocations.values()))
        if (
            allocation.get("reserve_nano") != 100000000
            or allocation.get("issue_consumed") is not True
            or allocation.get("start_consumed") is not True
            or allocation.get("child_id") != grant.get("approval_id")
            or allocation.get("child", {}).get("grant_bytes_sha256") != pins["child_grant"]
        ):
            raise Closed("ANCESTRY_STATE")
        if (
            child.get("status") != "closed"
            or child.get("grant_sha256") != pins["child_grant"]
            or child.get("approval_id") != grant.get("approval_id")
            or type(child.get("journal")) is not list
        ):
            raise Closed("ANCESTRY_STATE")
        accounts = [x for x in child["journal"] if x.get("phase") == "final_accounting"]
        outcome = allocation.get("outcome", {})
        if (
            len(accounts) != 1
            or not child["journal"]
            or child["journal"][-1].get("phase") != "cleanup_confirmed"
            or outcome.get("code") != "FIRST_SETTLEMENT_UNCONFIRMED"
            or outcome.get("cleanup_confirmed") is not True
        ):
            raise Closed("ANCESTRY_STATE")
        account = accounts[0]
        accounting_sha = C.digest(account)
        parent_account = allocation.get("accounting", {})
        if (
            outcome.get("accounting_sha256") != accounting_sha
            or parent_account != dict(sha256=accounting_sha, count=1, generation=0, http="unknown")
            or outcome.get("count_requests") != 1
            or outcome.get("generation_requests") != 0
        ):
            raise Closed("ACCOUNTING")
        ledger = account.get("state", {})
        diagnostics = account.get("diagnostics", [])
        if (
            any(type(ledger.get(k)) is not int for k in ("count", "generation", "reserved"))
            or account.get("observation") != "fresh_ledger"
            or (ledger.get("count"), ledger.get("generation"), ledger.get("reserved"), ledger.get("blocked")) != (1, 0, 50000000, True)
            or len(diagnostics) != 1
            or diagnostics[0].get("failure_code") != "KEY_SOURCE_INVALID"
            or diagnostics[0].get("count_http") != "unknown"
            or outcome.get("estimated_nano") is not None
            or outcome.get("http") != "unknown"
        ):
            raise Closed("ACCOUNTING")
        closure = records["closure"]
        if (
            closure.get("status") != "closed"
            or closure.get("journal_uncertain") is not False
            or closure.get("adapter_uncertain") is not False
            or records["carry_state"].get("status") != "closed"
            or records["carry_state"].get("grant_sha256") != pins["carry_grant"]
            or records["carry_state"].get("approval_id") != records["carry_grant"].get("approval_id")
        ):
            raise Closed("ANCESTRY_STATE")
        history = records["coordination"]
        if (
            d["predecessor_bootstrap"] != header.get("bootstrap_id")
            or history.get("bootstrap_id") != header.get("bootstrap_id")
            or history.get("header_sha256") != pins["header"]
            or history.get("head", {}).get("sha256") != pins["state"]
            or history.get("head", {}).get("sequence") != state["sequence"]
            or history.get("binding", {}).get("header_sha256") != pins["header"]
            or history.get("pending") is not None
            or history.get("phase") != "initialized"
            or closure.get("adapter_pin", {}).get("digest") != C.digest(history)
        ):
            raise Closed("ANCESTRY_STATE")
        paths = {a.name: a.path for a in self.artifacts}
        canonical_root = base / ".cf026-openai-test-budget" / header["approval_event"]
        if (
            paths["header"] != canonical_root / "header.json"
            or paths["state"] != canonical_root / "state.json"
            or paths["child_grant"] != canonical_root / "children" / allocation["child_id"] / "grant.json"
            or paths["child_state"] != canonical_root / "children" / allocation["child_id"] / "state.json"
        ):
            raise Closed("ANCESTRY_SCOPE")
        if (
            paths["coordination"] != base / ".cf026-live-coordination" / header["approval_event"] / "state.json"
            or history.get("root") != str(canonical_root)
        ):
            raise Closed("ANCESTRY_SCOPE")
        binding_pin = history["binding"]
        artifact_pins = {a.name: C.decode(a.stamp_json) for a in self.artifacts}
        if (
            binding_pin.get("directory") != C.directory_identity(canonical_root)
            or binding_pin.get("children") != C.directory_identity(canonical_root/"children")
            or binding_pin.get("lock") != C.regular(canonical_root/"execution.lock", 0o600)
            or binding_pin.get("header") != artifact_pins["header"]
            or history["head"].get("identity") != artifact_pins["state"]
        ):
            raise Closed("ANCESTRY_DRIFT")
        coordination_root = paths["coordination"].parent
        directory_pin = C.directory_identity(coordination_root)
        private_directory = directory_pin[:3] + [0o700]
        def private_stamp(value):
            return [value[k] for k in ("dev", "ino", "uid", "mode", "nlink", "size", "mtime_ns")]
        if (
            closure["adapter_pin"].get("directory") != private_directory
            or closure["adapter_pin"].get("lock") != private_stamp(C.regular(coordination_root/"lock", 0o600))
            or closure["adapter_pin"].get("state") != private_stamp(artifact_pins["coordination"])
        ):
            raise Closed("ANCESTRY_DRIFT")
        preparation_root = base / ".cf026-launcher-preparation-20261110"
        if (
            paths["runtime"] != preparation_root / "reviewed-runtime.json"
            or paths["closure"] != preparation_root / ("outcome-" + header["bootstrap_id"] + ".json")
        ):
            raise Closed("ANCESTRY_SCOPE")
        runtime = records["runtime"]
        old_carry = runtime.get("old_carry", {})
        if type(old_carry) is not dict or len(old_carry) != 3:
            raise Closed("ANCESTRY_STATE")
        retained = {(v.get("path"), v.get("sha256")) for v in old_carry.values()}
        if retained != {(str(paths[k]), pins[k]) for k in ("carry_grant", "carry_state", "carry_closure")}:
            raise Closed("ANCESTRY_STATE")
        original_source = grant.get("source", {})
        if (
            runtime.get("key_metadata") != original_source.get("identity")
            or runtime.get("source_manifest", {}).get("backend/scripts/cf026_supervisor_live_controller.py") != original_source.get("code_root", {}).get("controller_sha256")
            or grant.get("requests", [])[:1] != [historical_request(d, base)]
            or grant.get("semantic_sha256") != historical_semantic(d)
            or grant.get("price_sha256") != d["price_sha256"]
        ):
            raise Closed("ANCESTRY_STATE")
        # Source/invocation cannot select another one-shot slot for this frozen head.
        from scripts.cf023_supervisor_meaning_check import load_meaning
        load_meaning()
        from src.modules.supervisor.domain.contracts import MEANING_SPEC, MEANING_SPEC_SHA256, PreparationRequest
        from src.supervisor.infrastructure.openai_meaning_gateway import rendered_request, INPUT_FIELDS, COUNT_DOCUMENTATION
        body = PreparationRequest.model_validate(d["request"]["prepare_body"])
        if (
            body.parent_preparation_id is not None
            or body.draft.original_query != "현대건설 외국인 말고 3주 수급"
            or body.draft.answers
            or body.draft.revision != 0
            or body.draft.selected_ticker is not None
            or body.draft.candidate_ref is not None
        ):
            raise Closed("FIRST_REQUEST_ONLY")
        request = rendered_request(body.draft)
        item = d["request"]
        if (
            set(item) != {"prepare_body", "draft_sha256", "request_sha256", "projection_sha256"}
            or (item["draft_sha256"], item["request_sha256"], item["projection_sha256"], d["semantic_sha256"], d["price_sha256"]) != (C.digest(body.draft.model_dump(mode="json")), C.digest(request), C.digest({k: request[k] for k in INPUT_FIELDS}), MEANING_SPEC_SHA256, C.digest(MEANING_SPEC["price"]))
        ):
            raise Closed("REQUEST_DRIFT")
        counter = d["counter"]
        if (
            type(counter) is not dict
            or set(counter) != {"documentation_url", "documentation_sha256", "free_evidence_sha256", "price_evidence_sha256", "fee_bound_nano"}
            or counter["documentation_url"] != COUNT_DOCUMENTATION
            or type(counter["fee_bound_nano"]) is not int
            or counter["fee_bound_nano"] != 0
            or any(type(counter[k]) is not str
            or C.re.fullmatch(r"[a-f0-9]{64}", counter[k]) is None for k in counter if k.endswith("sha256"))
        ):
            raise Closed("COUNTER_EVIDENCE")
        if "retry" in d:
            check_retry(d, base)
        return d


def code_directory_identity(path):
    """Code directory metadata; private ancestry's 0700 rule stays separate."""
    path = C.no_links(path)
    info = path.lstat()
    if not C.stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise Closed("CODE_DRIFT")
    return [info.st_dev, info.st_ino, info.st_uid, info.st_mode]


def reviewed_execution_root(source, data, module_hash):
    code_root = source.code_root.path
    if data.get("retry", {}).get("ordinal") in {2,3,4}:
        code_root = code_root.parent / ("verith-supervisor-post-alignment-revalidation" if data["retry"]["ordinal"]==4 else "verith-supervisor-single-revalidation")
        expected = dict(path=str(code_root), directory=code_directory_identity(code_root), helper_sha256=module_hash)
        if data["retry"].get("current_code") != expected:
            raise Closed("CODE_DRIFT")
    return code_root


def once_identity(scope):
    d = scope.data
    # One opportunity for the original bootstrap; the final head is separately pinned.
    # Re-serializing or replacing projection hashes cannot mint another identity.
    value = {"namespace": d["namespace"], "predecessor_bootstrap": d["predecessor_bootstrap"]}
    if "retry" in d:
        value["retry_ordinal"] = d["retry"]["ordinal"]
    return C.digest(value)


def reservation_total(scope):
    retry = scope.data.get("retry")
    return 400000000 if retry and retry.get("ordinal") == 4 else 350000000 if retry and retry.get("ordinal") == 3 else 300000000 if retry and retry.get("ordinal") == 2 else 250000000 if retry else 200000000


def historical_semantic(data):
    if data.get("retry", {}).get("ordinal") not in {2,3,4}:
        return data["semantic_sha256"]
    # Only the reviewed provider5 -> provider55 change; every other semantic
    # input stays in the old hash. This never repins a historical artifact.
    from scripts.cf023_supervisor_meaning_check import load_meaning
    load_meaning()
    from src.modules.supervisor.domain.contracts import MEANING_SPEC
    if MEANING_SPEC["caps"]["provider_seconds"] != 55 or MEANING_SPEC["caps"]["verifier_seconds"] != 60:
        raise Closed("REQUEST_DRIFT")
    spec=MEANING_SPEC
    if data.get('retry',{}).get('ordinal')==4 or data['semantic_sha256']==PRE_ALIGNMENT_SEMANTIC:
        spec=MEANING_SPEC | {'prompt_sha256':PRE_ALIGNMENT_PROMPT}
        if C.digest(spec)!=PRE_ALIGNMENT_SEMANTIC:raise Closed('REQUEST_DRIFT')
    old = spec | {"caps": spec["caps"] | {"provider_seconds": 5}}
    return C.digest(old)


def check_retry(d, base):
    """One explicit retry of the retained pre-provider timeout, never a reissue.

    These pinned local records are inputs for the trusted external authority's
    independent history check. They do not mint authority or restore consumed rights.
    """
    retry = d["retry"]
    if type(retry) is dict and retry.get("ordinal") == 4:
        return check_retry4(d, base)
    if type(retry) is dict and retry.get("ordinal") == 3:
        return check_retry3(d, base)
    if type(retry) is dict and retry.get("ordinal") == 2:
        return check_retry2(d, base)
    keys = {"schema", "ordinal", "timeout", "timeout_manifest", "record_body", "record_body_sha256", "record_item_id", "record_turn_id",
            "consent_message_id", "carried_nano", "total_reserved_nano"}
    if (type(retry) is not dict or set(retry) != keys or retry["schema"] != "cf026.successor.retry1.v1"
        or type(retry["ordinal"]) is not int or retry["ordinal"] != 1
        or type(retry["carried_nano"]) is not int or retry["carried_nano"] != 200000000
        or type(retry["total_reserved_nano"]) is not int or retry["total_reserved_nano"] != 250000000
        or type(retry["consent_message_id"]) is not str
        or C.re.fullmatch(r"Sentinel_[a-f0-9]{32}", retry["consent_message_id"]) is None):
        raise Closed("RETRY_SCOPE")
    pin = retry["timeout"]
    expected = base / ".cf026-successor-timeout-review-20261111" / "actual-attempt.json"
    if (type(pin) is not dict or set(pin) != {"path", "stamp_json", "sha256"}
        or pin["path"] != str(expected)):
        raise Closed("RETRY_SCOPE")
    evidence = Artifact("timeout", expected, pin["stamp_json"], pin["sha256"]).verify(base)
    manifest_pin = retry["timeout_manifest"]
    manifest_path = expected.parent / "manifest.json"
    if (type(manifest_pin) is not dict or set(manifest_pin) != {"path", "stamp_json", "sha256"}
        or manifest_pin["path"] != str(manifest_path)):
        raise Closed("RETRY_SCOPE")
    manifest = Artifact("timeout_manifest", manifest_path, manifest_pin["stamp_json"], manifest_pin["sha256"]).verify(base)
    if (manifest.get("schema") != "cf026.successor.timeout-review-manifest.v1"
        or manifest.get("files", {}).get("actual-attempt.json") != pin["sha256"]
        or manifest.get("server_body_sha256") != retry["record_body_sha256"]
        or type(manifest.get("actual_server_hold_nano")) is not int or manifest["actual_server_hold_nano"] != 50000000
        or type(manifest.get("combined_reserved_nano")) is not int or manifest["combined_reserved_nano"] != 200000000):
        raise Closed("RETRY_EVIDENCE")
    record = evidence.get("reserve_record", {})
    original_once = C.digest({"namespace": d["namespace"], "predecessor_bootstrap": d["predecessor_bootstrap"]})
    required = {"schema", "additional_reserve_nano", "authority_sha256", "count_cap", "delegation",
                "generation_cap", "http_cap", "invocation", "issued_at", "namespace", "predecessor_sha256",
                "process_id", "retry_cap", "scope_sha256", "successor_once", "synthetic_only", "total_reserved_nano"}
    if (evidence.get("schema") != "cf026.successor.actual-timeout-evidence.v1"
        or type(record) is not dict or set(record) != required
        or record["schema"] != "cf026.successor.reserve-once.v1" or record["synthetic_only"] is not False
        or record["namespace"] != d["namespace"] or record["predecessor_sha256"] != d["predecessor_sha256"]
        or record["successor_once"] != original_once or record["invocation"] == d["invocation"]
        or record["delegation"] != "same-invocation-ordered-local-fsync"
        or type(record["process_id"]) is not int or record["process_id"] <= 0):
        raise Closed("RETRY_EVIDENCE")
    limits = dict(additional_reserve_nano=50000000, total_reserved_nano=200000000,
                  count_cap=1, generation_cap=1, http_cap=2, retry_cap=0)
    if any(type(record[k]) is not int or record[k] != v for k, v in limits.items()):
        raise Closed("RETRY_EVIDENCE")
    if any(type(record[k]) is not str or C.re.fullmatch(r"[a-f0-9]{64}", record[k]) is None
           for k in ("authority_sha256", "invocation", "scope_sha256")):
        raise Closed("RETRY_EVIDENCE")
    # Hash exact received UTF-8 bytes, never a re-serialized stand-in for the body.
    body = retry["record_body"]
    marker = "CF026_SUCCESSOR_RESERVE_ONCE\n"
    if (type(body) is not str or len(body.encode()) > 8192 or not body.startswith(marker)
        or C.canonical(C.decode(body[len(marker):])) != C.canonical(record)):
        raise Closed("RETRY_EVIDENCE")
    report = evidence.get("parent_reported", {})
    direct = evidence.get("direct_readonly_confirmed", {})
    if (hashlib.sha256(body.encode()).hexdigest() != retry["record_body_sha256"]
        or retry["record_item_id"] != report.get("server_record_item_id")
        or retry["record_turn_id"] != report.get("server_record_turn_id")
        or not all(type(retry[k]) is str and retry[k] for k in ("record_item_id", "record_turn_id"))
        or report.get("server_reservation_actually_consumed") is not True
        or report.get("stdin_not_sent") is not True or report.get("terminal_code") != "BRIDGE_TIMEOUT"
        or type(report.get("exit_code")) is not int or report["exit_code"] != 1
        or not all(type(report.get(k)) is int and report[k] == 0
                   for k in ("key_content_reads", "count_http", "generation_http", "db_created"))
        or report.get("source_copy_removed") is not True or report.get("entry_restored") is not True
        or not all(direct.get(k) is True for k in ("local_journal_contains_only_execution_lock", "journal_state_absent", "phase_state_absent"))
        or direct.get("entry_RELEASED") is not False
        or C.parse_expiry(d["consent_at"]) <= C.parse_expiry(record["issued_at"])):
        raise Closed("RETRY_EVIDENCE")
    accounting = evidence.get("accounting")
    expected_accounting = dict(historical_reservation_nano=150000000, new_consumed_server_hold_nano=50000000,
        combined_reserved_nano=200000000, billing_amount=None, refund_or_reissue_permitted=False,
        historical_http_unknown_unchanged=True)
    if (C.canonical(accounting) != C.canonical(expected_accounting)
        or evidence.get("same_record_or_invocation_reuse_permitted") is not False):
        raise Closed("RETRY_EVIDENCE")


def check_retry2(d, base):
    """Fixed next opportunity after the closed unknown retry1, not auto retry.

    Pinned local history is checked here; the parent-held authority must also
    authenticate the original server items and enforce the canonical once slot.
    """
    r = d["retry"]
    fields = {"schema", "ordinal", "prior_retry", "evidence", "record_body", "record_body_sha256",
              "record_item_id", "record_turn_id", "consent_message_id", "carried_nano", "total_reserved_nano", "current_code"}
    if (set(r) != fields or r["schema"] != "cf026.successor.retry2.v1"
        or type(r["ordinal"]) is not int or r["ordinal"] != 2
        or type(r["carried_nano"]) is not int or r["carried_nano"] != 250000000
        or type(r["total_reserved_nano"]) is not int or r["total_reserved_nano"] != 300000000
        or type(r["consent_message_id"]) is not str
        or C.re.fullmatch(r"Sentinel_[a-f0-9]{32}", r["consent_message_id"]) is None
        or type(r["prior_retry"]) is not dict or r["prior_retry"].get("ordinal") != 1):
        raise Closed("RETRY_SCOPE")
    check_retry(d | {"retry": r["prior_retry"]}, base)
    home = base / ".cf026-successor-retry-20261111"
    expected = dict(inputs=home/"reviewed-successor-inputs.json", journal=home/"successor-journal-retry-1"/"state.json",
                    phases=home/"successor-phases-retry-1.json",
                    result=base/".cf026-runtime-deadline-diagnostic-20261111"/"actual-result.json")
    if type(r["evidence"]) is not dict or set(r["evidence"]) != set(expected):
        raise Closed("RETRY_EVIDENCE")
    records = {}
    for name, path in expected.items():
        pin = r["evidence"][name]
        if type(pin) is not dict or set(pin) != {"path", "stamp_json", "sha256"} or pin["path"] != str(path):
            raise Closed("RETRY_EVIDENCE")
        records[name] = Artifact(name, path, pin["stamp_json"], pin["sha256"]).verify(base)
    prior = records["inputs"]["template"]["scope_template"]
    if (prior.get("retry") != r["prior_retry"] or prior.get("namespace") != d["namespace"]
        or prior.get("predecessor_bootstrap") != d["predecessor_bootstrap"]
        or prior.get("predecessor_sha256") != d["predecessor_sha256"]
        or prior.get("artifacts") != d["artifacts"] or prior.get("request") != d["request"]
        or prior.get("semantic_sha256") != historical_semantic(d)
        or prior.get("price_sha256") != d["price_sha256"]):
        raise Closed("RETRY_EVIDENCE")
    marker = "CF026_SUCCESSOR_RESERVE_ONCE\n"
    body = r["record_body"]
    if (type(body) is not str or not body.startswith(marker) or len(body.encode()) > 8192
        or hashlib.sha256(body.encode()).hexdigest() != r["record_body_sha256"]):
        raise Closed("RETRY_EVIDENCE")
    record = C.decode(body[len(marker):])
    required = {"schema", "additional_reserve_nano", "authority_sha256", "count_cap", "delegation", "generation_cap",
                "http_cap", "invocation", "issued_at", "namespace", "predecessor_sha256", "process_id", "retry_cap",
                "retry_ordinal", "retry_of_sha256", "scope_sha256", "successor_once", "synthetic_only", "total_reserved_nano"}
    if (set(record) != required or record["schema"] != "cf026.successor.reserve-once.v1"
        or record["synthetic_only"] is not False or record["namespace"] != d["namespace"]
        or record["predecessor_sha256"] != d["predecessor_sha256"] or record["invocation"] == d["invocation"]
        or record["successor_once"] != C.digest(dict(namespace=d["namespace"], predecessor_bootstrap=d["predecessor_bootstrap"], retry_ordinal=1))
        or record["retry_of_sha256"] != r["prior_retry"]["record_body_sha256"]
        or record["delegation"] != "same-invocation-ordered-local-fsync"
        or type(record["process_id"]) is not int or record["process_id"] <= 0):
        raise Closed("RETRY_EVIDENCE")
    for key, value in dict(additional_reserve_nano=50000000, total_reserved_nano=250000000,
                           retry_ordinal=1, count_cap=1, generation_cap=1, http_cap=2, retry_cap=0).items():
        if type(record[key]) is not int or record[key] != value:
            raise Closed("RETRY_EVIDENCE")
    for key in ("authority_sha256", "invocation", "scope_sha256"):
        if type(record[key]) is not str or C.re.fullmatch(r"[a-f0-9]{64}", record[key]) is None:
            raise Closed("RETRY_EVIDENCE")
    journal, phases, result = records["journal"], records["phases"], records["result"]
    events = journal.get("journal", [])
    accounts = [e for e in events if e.get("phase") == "final_accounting"]
    if (journal.get("schema") != "cf026.successor.journal.v1" or journal.get("status") != "closed"
        or journal.get("scope_sha256") != record["scope_sha256"]
        or journal.get("rights") != dict(count=1, generation=1) or len(accounts) != 1
        or not events or events[-1].get("phase") != "cleanup_confirmed"
        or len([e for e in events if e.get("phase") == "closing" and e.get("external_accounting_ACK") is True]) != 1):
        raise Closed("RETRY_EVIDENCE")
    account = accounts[0]
    expected_ledger = dict(count=1, generation=1, reserved=50000000, blocked=False,
                           attempts=[dict(state="unknown", estimated_nano=None)])
    if (account.get("reserved_nano") != 250000000 or account.get("ledger") != expected_ledger
        or account.get("estimated_nano") is not None or account.get("http") != "unknown"
        or account.get("observation") != "fresh_ledger"):
        raise Closed("ACCOUNTING")
    ordered = ["reserve", "issue", "start", "count", "generation", "accounting"]
    binding = {k: record[k] for k in record if k not in {"schema", "synthetic_only", "process_id", "authority_sha256", "delegation", "issued_at"}}
    ack = binding | dict(phase="accounting", authority_sha256=record["authority_sha256"], sequence=6,
                         issued_at=record["issued_at"], consumed=True, record_sha256=C.digest(account))
    if phases.get("binding") != binding or phases.get("ack") != ack or phases.get("phases") != ordered or phases.get("sequence") != 6:
        raise Closed("ACCOUNTING")
    direct, report = result.get("direct_readonly", {}), result.get("parent_reported", {})
    if (result.get("schema") != "cf026.retry1.actual-result-diagnostic.v1"
        or result.get("original_files") != {str(expected[n]): r["evidence"][n]["sha256"] for n in ("journal", "phases")}
        or direct.get("closed") is not True or direct.get("cleanup_recorded") is not True
        or direct.get("local_accounting_ack_matches_journal") is not True
        or direct.get("ledger") != expected_ledger or direct.get("total_reserved_nano") != 250000000
        or direct.get("estimated_nano") is not None or direct.get("phase_order") != ordered
        or report.get("exit_code") != 1 or report.get("terminal_code") != "SUCCESSOR_CLOSED"
        or report.get("source_copy_removed") is not True
        or report.get("server_record_item_id") != r["record_item_id"] or report.get("server_record_turn_id") != r["record_turn_id"]
        or report.get("issued_at") != record["issued_at"] or report.get("process_id") != record["process_id"]
        or C.parse_expiry(d["consent_at"]) <= C.parse_expiry(record["issued_at"])):
        raise Closed("RETRY_EVIDENCE")


@dataclass(frozen=True, repr=False, init=False)
class Lease:
    clock: object
    issued: datetime
    expires: datetime
    monotonic_end: float
    monotonic_start_end: float

    def __init__(self, issued_at, consent_at, clock, *, not_after=None):
        issued = C.parse_expiry(issued_at)
        now = clock.wall()
        if not C.parse_expiry(consent_at) <= issued <= now or (now - issued).total_seconds() > 120:
            raise Closed("LEASE_START")
        expires = issued + timedelta(seconds=600)
        if not_after is not None:
            expires = min(expires, C.parse_expiry(not_after))
        object.__setattr__(self, "clock", clock)
        object.__setattr__(self, "issued", issued)
        object.__setattr__(self, "expires", expires)
        object.__setattr__(self, "monotonic_end", clock.mono() + (expires - now).total_seconds())
        object.__setattr__(self, "monotonic_start_end", clock.mono() + 120 - (now - issued).total_seconds())

    def check(self, *, starting=False):
        now = self.clock.wall()
        if (
            now < self.issued
            or now >= self.expires
            or self.clock.mono() >= self.monotonic_end
            or starting
            and ((now - self.issued).total_seconds() > 120
            or self.clock.mono() > self.monotonic_start_end)
        ):
            raise Closed("LEASE_EXPIRED")
        return min((self.expires - now).total_seconds(), self.monotonic_end - self.clock.mono())


class Clock:
    @staticmethod
    def wall():
        return datetime.now(timezone.utc)

    @staticmethod
    def mono():
        return time.monotonic()


class Journal:
    """Already provisioned local evidence; not a budget or an authority issuer."""
    def __init__(self, path, state_pin, lock_pin, scope_sha256):
        self.path, self.pin, self.lock_pin, self.scope_sha256 = Path(path), state_pin, lock_pin, scope_sha256
        self.directory = C.directory_identity(self.path)
        self.fd = None
        self.uncertain = False
        self.grant = None

    def enter(self):
        fd = os.open(self.path / "execution.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if C.identity(os.fstat(fd)) != self.lock_pin or C.regular(self.path / "execution.lock", 0o600) != self.lock_pin:
                raise Closed("JOURNAL_DRIFT")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd = fd
            self.reload()
            if self.state["status"] != "offered":
                raise Closed("ALREADY_USED")
        except BaseException:
            self.fd = None
            os.close(fd)
            raise

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def reload(self):
        if (
            self.uncertain
            or self.fd is None
            or C.directory_identity(self.path) != self.directory
            or C.identity(os.fstat(self.fd)) != self.lock_pin
            or C.regular(self.path / "execution.lock", 0o600) != self.lock_pin
        ):
            raise Closed("JOURNAL_DRIFT")
        raw, _ = C.read_fixed(self.path / "state.json", 0o600, self.pin["identity"])
        if hashlib.sha256(raw).hexdigest() != self.pin["sha256"]:
            raise Closed("JOURNAL_DRIFT")
        state = C.decode(raw)
        if (
            set(state) != {"schema", "scope_sha256", "status", "rights", "preparation", "journal"}
            or state["schema"] != "cf026.successor.journal.v1"
            or state["scope_sha256"] != self.scope_sha256
            or state["status"] not in {"offered", "claimed", "closed"}
            or type(state["journal"]) is not list
            or len(state["journal"]) > 24
            or set(state["rights"]) != {"count", "generation"}
            or any(type(v) is not int
            or v not in (0, 1) for v in state["rights"].values())
            or state["rights"]["generation"] > state["rights"]["count"]
        ):
            raise Closed("JOURNAL_DRIFT")
        self.state = state

    def persist(self, status, event, *, rights=None, preparation=None):
        self.reload()
        old = self.state
        if (
            old["status"] == "closed"
            or status not in {"claimed", "closed"}
            or len(old["journal"]) >= (24 if event.get("phase") in {"final_accounting", "closing", "cleanup_confirmed"} else 21)
        ):
            raise Closed("JOURNAL_LIMIT")
        value = old | dict(status=status, journal=[*old["journal"], event])
        if rights is not None:
            if any(type(rights[k]) is not int or not old["rights"][k] <= rights[k] <= 1 for k in old["rights"]):
                raise Closed("PHASE_LIMIT")
            value["rights"] = rights
        if preparation is not None:
            if old["preparation"] not in (None, preparation):
                raise Closed("PREPARATION_DRIFT")
            value["preparation"] = preparation
        if len(C.canonical(value).encode()) > 65536:
            raise Closed("JOURNAL_LIMIT")
        try:
            C.exclusive_private_file(self.path / "state.pending", value)
            self.reload()
            os.replace(self.path / "state.pending", self.path / "state.json")
            C.fsync_directory(self.path)
            raw, identity = C.read_fixed(self.path / "state.json", 0o600)
            if C.decode(raw) != value:
                raise Closed("JOURNAL_ACK_UNKNOWN")
            self.pin = dict(identity=identity, sha256=hashlib.sha256(raw).hexdigest())
            self.reload()
        except BaseException:
            self.uncertain = True
            raise


class Session:
    def __init__(self, scope, source, authority, journal, synthetic, clock):
        self.scope, self.source, self.authority, self.journal = scope, source, authority, journal
        self.synthetic, self.clock = synthetic, clock
        self.lease = None
        self.sequence = 0
        self.phases = []
        self.reservation_attempted = False
        self.last_ack_sha256 = None

    def check(self):
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        self.scope.check(self.source, self.authority, synthetic=self.synthetic)
        self.journal.reload()
        if self.journal.state["status"] == "closed":
            raise Closed("ALREADY_USED")
        if self.lease is not None:
            self.lease.check()

    async def call(self, operation, *, consuming=False, cleanup=False, record=None):
        if not cleanup:
            self.check()
        args = dict(successor_once=once_identity(self.scope), scope_sha256=self.scope.sha256, namespace=self.scope.data["namespace"],
                    predecessor_sha256=self.scope.data["predecessor_sha256"],
                    invocation=self.scope.data["invocation"], phase=operation,
                    additional_reserve_nano=50000000, total_reserved_nano=reservation_total(self.scope),
                    count_cap=1, generation_cap=1, http_cap=2, retry_cap=0)
        if "retry" in self.scope.data:
            args.update(retry_ordinal=self.scope.data["retry"]["ordinal"], retry_of_sha256=self.scope.data["retry"]["record_body_sha256"])
        if record is not None:
            args["record_sha256"] = C.digest(record)
        timeout = 5 if cleanup or self.lease is None else min(5, self.lease.check())
        async with asyncio.timeout(timeout):
            if consuming:
                if operation == "reserve":
                    self.reservation_attempted = True
                ack = await self.authority.consume(**args)
                readback = await self.authority.readback(**args)
                if type(ack) is not dict or readback != ack:
                    raise Closed("AUTHORITY_ACK_UNKNOWN")
                required = set(args) | {"authority_sha256", "sequence", "issued_at", "consumed"}
                if (
                    set(ack) != required
                    or any(ack.get(k) != v for k, v in args.items())
                    or ack["authority_sha256"] != self.authority.identity_sha256
                    or ack["consumed"] is not True
                    or type(ack["sequence"]) is not int
                    or ack["sequence"] != self.sequence + 1
                ):
                    raise Closed("AUTHORITY_ACK_UNKNOWN")
                if self.lease is None:
                    ordinal=self.scope.data.get('retry',{}).get('ordinal')
                    end = ('2026-11-12T08:00:00+00:00' if ordinal==4 else '2026-11-11T21:00:00+00:00' if ordinal==3 else None) if not self.synthetic else None
                    self.lease = Lease(ack["issued_at"], self.scope.data["consent_at"], self.clock, not_after=end)
                elif C.parse_expiry(ack["issued_at"]) != self.lease.issued:
                    raise Closed("LEASE_DRIFT")
                self.sequence = ack["sequence"]
                self.last_ack_sha256 = C.digest(ack)
            elif await self.authority.verify(**args) is not True:
                raise Closed("AUTHORITY_UNAVAILABLE")
        if not cleanup:
            self.check()
        self.phases.append(operation)


class PhaseAuthority(C.ContinuationAuthority):
    """Reuse existing fresh Principal/preparation/attempt/epoch checks only."""
    def __init__(self, session, proof, binding, principal, body, deferred, observation):
        super().__init__(session.journal, session.source, proof, binding, principal, body, deferred, observation)
        self.session = session
        self.phase_lock = asyncio.Lock()

    async def verify(self, **scope):
        async with self.phase_lock:
            return await self._verify(**scope)

    async def _verify(self, **scope):
        session = self.session
        session.check()
        d, item = session.scope.data, session.scope.data["request"]
        phase = scope.get("phase")
        order = ["initial", "preflight", "count", "generation"]
        if (
            len(self.phases) >= 4
            or phase != order[len(self.phases)]
            or scope.get("mode") != d["mode"]
            or scope.get("proof_binding") is not self.binding
            or scope.get("principal") is not self.principal
            or scope.get("key_supplier") is not self.deferred
            or scope.get("key_source_capability") is not self.source
            or scope.get("draft_sha256") != item["draft_sha256"]
            or scope.get("semantic_sha256") != d["semantic_sha256"]
        ):
            raise Closed("PHASE_SCOPE")
        from src.supervisor.infrastructure.openai_meaning_gateway import CounterAgreement, INPUT_FIELDS
        agreement = scope.get("agreement")
        if (
            type(agreement) is not CounterAgreement
            or agreement.documentation_url != d["counter"]["documentation_url"]
            or agreement.documentation_sha256 != d["counter"]["documentation_sha256"]
            or agreement.input_fields != INPUT_FIELDS
            or agreement.counting_fee_bound_nano != 0
        ):
            raise Closed("COUNTER_EVIDENCE")
        if phase != "initial":
            if (scope.get("request_sha256"), scope.get("projection_sha256")) != (item["request_sha256"], item["projection_sha256"]):
                raise Closed("PHASE_SCOPE")
            async with asyncio.timeout(min(60, session.lease.check())):
                local = await self.fresh_preparation()
            session.check()
            if phase in {"count", "generation"}:
                expected = dict(count=0, generation=0, reserved=0) if phase == "count" else dict(count=1, generation=0, reserved=50000000)
                if local != expected or self.store.state["rights"][phase]:
                    raise Closed("PHASE_LIMIT")
                await session.call(phase, consuming=True)
                rights = self.store.state["rights"] | {phase: 1}
                self.store.persist("claimed", dict(phase=phase + "_authority_ACK"), rights=rights)
        else:
            await session.call("initial")
        session.check()
        self.phases.append(phase)
        if phase == "generation":
            self.observation.generation_authority = True
        return session.lease.expires



@contextmanager
def guarded_driver(driver, session):
    original = driver.call
    def call(*args, **kwargs):
        session.check()
        kwargs["timeout"] = min(kwargs.get("timeout", 15), session.lease.check())
        return original(*args, **kwargs)
    driver.call = call
    try:
        yield
    finally:
        driver.call = original


@asynccontextmanager
async def checked_connection(proof, session):
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine
    session.check()
    await proof.preflight()
    session.check()
    engine = create_async_engine(proof.url, connect_args=proof.connection_parameters())
    def guard(*_):
        session.check()
    event.listen(engine.sync_engine, "before_cursor_execute", guard)
    event.listen(engine.sync_engine, "commit", guard)
    try:
        async with engine.connect() as connection:
            await proof.attest_connection(connection)
            session.check()
            yield connection
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", guard)
        event.remove(engine.sync_engine, "commit", guard)
        await engine.dispose()


@asynccontextmanager
async def checked_session(proof, session):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with checked_connection(proof, session) as connection:
        async with AsyncSession(bind=connection, expire_on_commit=False) as database:
            yield database


async def initialize_checked_epoch(proof, principal, epoch_id, session):
    from sqlalchemy import select
    from scripts.cf023_supervisor_meaning_check import OwnedEpochBinding, epoch_state
    from src.modules.auth.application.session_service import validate_principal
    from src.modules.supervisor.infrastructure.preparation_repository import clock
    from src.modules.supervisor.domain.contracts import MEANING_SPEC, MEANING_SPEC_SHA256
    from db.models.supervisor.preparation import SupervisorMeaningEpoch as Epoch
    async with checked_session(proof, session) as database:
        await validate_principal(database, principal, lock=True)
        if await database.scalar(select(Epoch.id)) is not None:
            raise Closed("EPOCH_ALREADY_EXISTS")
        created = await clock(database)
        session.check()
        row = Epoch(id=UUID(epoch_id), unit_id="CF023", currency="USD", max_nano=100000000,
                    attempt_reserve_nano=50000000, max_attempts=2,
                    price_sha256=C.digest(MEANING_SPEC["price"]), semantic_sha256=MEANING_SPEC_SHA256,
                    reserved_nano=0, count_requests=0, generation_requests=0, blocked=False,
                    active_attempt_id=None, attempts_json={}, created_at=created)
        database.add(row)
        await database.commit()
    async with checked_session(proof, session) as database:
        fresh = await database.scalar(select(Epoch).where(Epoch.id == UUID(epoch_id)))
        if fresh is None or not isinstance(fresh.id, UUID) or fresh.created_at != row.created_at or epoch_state(fresh) != epoch_state(row):
            raise Closed("EPOCH_ACK_UNKNOWN")
        binding = OwnedEpochBinding(proof, proof._owner.receipt, UUID(str(fresh.id)), fresh.created_at,
                                    C.digest(epoch_state(fresh)), "live")
        await database.commit()
    return binding


class OwnedHooks(C.OwnedHooks):
    """Same owned setup with lease checks before each owned SQL dispatch/commit."""
    def __init__(self, session):
        super().__init__(synthetic=False)
        self.session = session

    async def bootstrap(self, store):
        from alembic import command
        from alembic.config import Config
        session = self.session
        session.check()
        store.persist("claimed", dict(phase="resource_requested", name=self.owner.name))
        session.check()
        self.proof = self.owner.create()
        store.persist("claimed", dict(phase="resource_created", receipt_sha256=C.digest(self.proof.safe_receipt())))
        # Existing attestation/migration pattern; hooks belong only to this engine.
        await self.proof.preflight()
        session.check()
        self.owner.sql("CREATE EXTENSION IF NOT EXISTS pgcrypto;\nCREATE EXTENSION IF NOT EXISTS vector;")
        async with checked_connection(self.proof, session) as connection:
            def upgrade(sync):
                session.check()
                config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
                config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "db/migrations"))
                config.attributes.update(connection=sync, verified_test_mode=True)
                command.upgrade(config, "head")
            await connection.run_sync(upgrade)
            session.check()
            await connection.commit()
        from scripts.cf003_admission_check import isolated_application
        from scripts.cf023_supervisor_meaning_check import load_meaning
        self.application = isolated_application(self.proof)
        self.observed = self.application.__enter__()
        load_meaning()
        from db.models.auth.models import AuthUser
        from db.models.common.stock import Stock
        from src.modules.auth.application.session_service import issue_session
        from uuid import uuid4
        async with checked_session(self.proof, session) as database:
            session.check()
            user = AuthUser(id=uuid4())
            database.add(user)
            database.add(Stock(stock_code="000720", stock_name="현대건설", market="KOSPI"))
            await database.flush()
            session.check()
            _, principal = await issue_session(database, user)
            session.check()
            await database.commit()
        session.check()
        binding = await initialize_checked_epoch(self.proof, principal, store.grant["epoch_id"], session)
        self.application.__exit__(None, None, None)
        del self.application
        if any(self.observed.values()):
            raise Closed("ISOLATION_DENIAL")
        return self.proof, principal, binding

async def verify_once(session, proof, binding, principal, observation):
    from scripts.cf023_supervisor_meaning_check import verify_live, DeferredKeySource
    from src.modules.supervisor.domain.contracts import PreparationRequest
    from src.supervisor.infrastructure.openai_meaning_gateway import CounterAgreement, INPUT_FIELDS
    if session.lease is None or "start" not in session.phases:
        raise Closed("NOT_STARTED")
    d = session.scope.data
    body = PreparationRequest.model_validate(d["request"]["prepare_body"])
    authority = None
    supplied = False

    async def supplier():
        nonlocal supplied
        observation.supplier("entered")
        try:
            session.check()
            if supplied or authority.phases != ["initial", "preflight", "count"]:
                raise Closed("SUPPLIER_ONCE")
            supplied = True
            await session.call("supplier")
            observation.supplier("approval_checked")
            observation.supplier("source_read_entered")
            key = await session.source.read()
            observation.supplier("source_read_returned")
            session.check()
            return key
        except BaseException as error:
            observation.supplier("cancelled" if isinstance(error, asyncio.CancelledError) else "timed_out" if isinstance(error, TimeoutError) else "failed")
            observation.failed(error)
            raise

    deferred = DeferredKeySource(supplier, session.source)
    authority = PhaseAuthority(session, proof, binding, principal, body, deferred, observation)
    agreement = CounterAgreement(d["counter"]["documentation_url"], d["counter"]["documentation_sha256"], INPUT_FIELDS, 0)
    session.check()
    from src.supervisor.infrastructure.openai_meaning_gateway import OpenAIMeaningGateway
    # Observe only the returned typed proposal, after the unchanged gateway's
    # usage validation/settlement. No HTTP/key/raw response interception.
    original = OpenAIMeaningGateway.propose
    async def capture(gateway, draft, **kwargs):
        candidate = await original(gateway, draft, **kwargs)
        session.quality = safe_quality(draft, candidate)
        return candidate
    from unittest.mock import patch
    with patch.object(OpenAIMeaningGateway, "propose", capture):
        return await verify_live(proof=proof, binding=binding, principal=principal,
                                 prepare_body=d["request"]["prepare_body"], authority=authority,
                                 counter_agreement=agreement, key_supplier=deferred)


def grounding_rejection(draft, candidate):
    """Bounded diagnostic replay of unchanged pure rules, never a second policy.

    Only the failed typed item and approved-question spans are projected. Free
    candidate strings, exception messages and full traceback are not retained.
    """
    from src.supervisor.application import meaning_policy as policy
    from src.supervisor.domain.meaning_proposals import MeaningProposal
    from unittest.mock import patch
    reasons = {("validate",97):"EVIDENCE_SOURCE_SPAN_TEXT_MISMATCH",
        ("negation",119):"NEGATION_EVIDENCE_MISMATCH",("negation",121):"NEGATION_EVIDENCE_MISSING",
        ("add_mention",132):"MENTION_NAME_SHAPE_REJECTED",("add_view",179):"VIEW_EVIDENCE_MISMATCH",
        ("add_view",183):"ACTOR_EXCLUSION_IS_NOT_VIEW",("add_condition",224):"CONDITION_DOMAIN_KIND_VALUE_MISMATCH",
        ("add_condition",227):"CONDITION_NEGATION_MISMATCH"}
    def evidence(value):
        if value is None:return None
        start,end=value.start,value.end
        valid=value.source_kind=="original_query" and value.answer_id is None and 0<=start<end<=len(draft.original_query)
        return dict(source_kind=value.source_kind,answer_id_present=value.answer_id is not None,
                    start=start if 0<=start<=len(draft.original_query) else None,end=end if 0<=end<=len(draft.original_query) else None,
                    supplied_text=value.text if value.text in draft.original_query else None,
                    supplied_text_length=len(value.text),expected_text=draft.original_query[start:end] if valid else None,
                    exact_source_match=valid and draft.original_query[start:end]==value.text)
    found = None
    schema_valid = False
    indexes = dict(mentions=0,views=0,conditions=0)
    def wrap(name,section):
        original=getattr(policy.Grounding,name)
        def traced(grounding,*args,**kwargs):
            nonlocal found
            if not kwargs.get("proposal"):
                return original(grounding,*args,**kwargs)
            index=indexes[section];indexes[section]+=1
            try:return original(grounding,*args,**kwargs)
            except (ValueError,TypeError) as error:
                location=("unknown",0);trace=error.__traceback__
                while trace is not None:
                    frame=trace.tb_frame
                    if frame.f_code.co_filename==policy.__file__ and (frame.f_code.co_name,trace.tb_lineno) in reasons:
                        location=(frame.f_code.co_name,trace.tb_lineno)
                    trace=trace.tb_next
                ev=args[0] if section=="mentions" else args[1] if section=="views" else args[3]
                neg=args[1] if section=="mentions" else args[2] if section=="views" else args[4]
                detail=dict(evidence=evidence(ev),negation=evidence(neg))
                if section=="views":detail["view"]=args[0]
                if section=="conditions":
                    detail.update(domain=args[0],kind=args[1],supplied_value=args[2] if args[2] in draft.original_query else None,
                                  supplied_value_length=len(args[2]),supplied_value_in_question=args[2] in draft.original_query)
                found=dict(stage="grounding",field=section,index=index,reason=reasons.get(location,"VALIDATOR_REJECTED"),
                           location=dict(function=location[0],line=location[1]),item=detail)
                raise
        return traced
    original_alignment=policy.align_model_proposal
    def alignment(draft_value,proposal_value):
        nonlocal found
        try:return original_alignment(draft_value,proposal_value)
        except (ValueError,TypeError) as error:
            trace=error.__traceback__
            while trace is not None:
                frame=trace.tb_frame
                if frame.f_code.co_filename==policy.__file__ and frame.f_code.co_name=='align_model_proposal' and trace.tb_lineno in (379,383):
                    section=frame.f_locals.get('section');item=frame.f_locals.get('item');data=frame.f_locals.get('data')
                    if section in indexes and type(item) is dict and type(data) is dict and item in data.get(section,[]):
                        from src.supervisor.domain.meaning import Evidence
                        detail=dict(evidence=evidence(Evidence.model_validate(item['evidence'])),negation=evidence(Evidence.model_validate(item['negation'])) if item['negation'] is not None else None)
                        if section=='views':detail['view']=item['view']
                        if section=='conditions':detail.update(domain=item['domain'],kind=item['kind'],supplied_value=item['value'] if item['value'] in draft.original_query else None,supplied_value_length=len(item['value']),supplied_value_in_question=item['value'] in draft.original_query)
                        found=dict(stage='alignment',field=section,index=data[section].index(item),reason='EVIDENCE_SOURCE_NOT_FOUND' if trace.tb_lineno==379 else 'EVIDENCE_TEXT_ABSENT_OR_AMBIGUOUS',location=dict(function='align_model_proposal',line=trace.tb_lineno),item=detail)
                trace=trace.tb_next
            raise
    try:
        proposal=MeaningProposal.model_validate(candidate)
        schema_valid = True
        with patch.object(policy,"align_model_proposal",alignment),\
             patch.object(policy.Grounding,"add_mention",wrap("add_mention","mentions")),\
             patch.object(policy.Grounding,"add_view",wrap("add_view","views")),\
             patch.object(policy.Grounding,"add_condition",wrap("add_condition","conditions")):
            policy.assess(draft,proposal,source="model_assisted")
    except (ValueError,TypeError):
        pass
    result=found or dict(stage="grounding" if schema_valid else "proposal_schema",field=None,index=None,
                        reason="VALIDATOR_STAGE_UNKNOWN" if schema_valid else "TYPED_PROPOSAL_REJECTED",location=None,item=None)
    if len(C.canonical(result).encode())>4096:
        return dict(stage="grounding",field=None,index=None,reason="DIAGNOSTIC_LIMIT",location=None,item=None)
    return result


def safe_quality(draft, candidate):
    """Existing grounded validator; only approved question spans are retained."""
    from src.supervisor.application.meaning_policy import assess
    if draft.original_query != "현대건설 외국인 말고 3주 수급" or draft.answers or draft.revision != 0:
        raise Closed("FIRST_REQUEST_ONLY")
    try:
        assessed = assess(draft, candidate, source="model_assisted")
    except (ValueError, TypeError):
        return dict(status="rejected", assessment=None, rejection=grounding_rejection(draft,candidate))
    frame = assessed.frame
    result = dict(status="validated", assessment=dict(
        mentions=[m.model_dump(mode="json") for m in frame.mentions],
        requested_views=frame.requested_views, negated_views=frame.negated_views,
        conditions=[c.model_dump(mode="json") for c in frame.conditions],
        unresolved_slots=frame.unresolved_slots, interpretation_source=frame.interpretation_source))
    if len(C.canonical(result).encode()) > 16384:
        return dict(status="rejected", assessment=None,rejection=dict(stage="projection",field=None,index=None,
                    reason="QUALITY_PROJECTION_LIMIT",location=None,item=None))
    for index,condition in enumerate(frame.conditions):
        if condition.value not in draft.original_query:
            return dict(status="rejected",assessment=None,rejection=dict(stage="projection",field="conditions",index=index,
                        reason="QUALITY_VALUE_NOT_IN_APPROVED_QUESTION",location=None,item=None))
    return result



def safe_ledger(snapshot, session):
    if snapshot is None:
        return None
    rights = session.journal.state["rights"]
    if (
        any(type(snapshot.get(k)) is not int for k in ("count", "generation", "reserved"))
        or not 0 <= snapshot["generation"] <= snapshot["count"] <= 1
        or snapshot["reserved"] != snapshot["count"] * 50000000
        or snapshot["count"] > rights["count"]
        or snapshot["generation"] > rights["generation"]
        or type(snapshot.get("blocked")) is not bool
        or type(snapshot.get("attempts")) is not dict
        or len(snapshot["attempts"]) != snapshot["count"]
    ):
        raise Closed("LEDGER_LIMIT")
    attempts = []
    for key, item in snapshot["attempts"].items():
        UUID(key)
        if (
            item.get("request_sha256") != session.scope.data["request"]["request_sha256"]
            or item.get("projection_sha256") != session.scope.data["request"]["projection_sha256"]
        ):
            raise Closed("LEDGER_LIMIT")
        observation = item.get("observation")
        if observation is None:
            state, estimate = "unknown", None
        elif type(observation) is dict and observation.get("state") in {"observed", "unknown", "anomalous"}:
            state, estimate = observation["state"], observation.get("estimated_nano")
            if estimate is not None and (type(estimate) is not int or not 0 <= estimate <= 50000000):
                raise Closed("LEDGER_LIMIT")
        else:
            raise Closed("LEDGER_LIMIT")
        retained = dict(state=state, estimated_nano=estimate)
        if type(observation) is dict and any(k in observation for k in ("input_tokens", "output_tokens", "total_tokens", "cached_tokens")):
            usage = {k: observation.get(k) for k in ("input_tokens", "output_tokens", "total_tokens", "cached_tokens")}
            from src.modules.supervisor.domain.contracts import MEANING_SPEC
            if (any(type(v) is not int or v < 0 for v in usage.values())
                or usage["input_tokens"] > 16384 or usage["output_tokens"] > 2048
                or usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]
                or usage["cached_tokens"] > usage["input_tokens"]
                or observation.get("price_sha256") != C.digest(MEANING_SPEC["price"])
                or observation.get("model_sha256") != hashlib.sha256(MEANING_SPEC["model"].encode()).hexdigest()):
                raise Closed("LEDGER_LIMIT")
            retained.update(usage=usage, model=MEANING_SPEC["model"])
        attempts.append(retained)
    return dict(count=snapshot["count"], generation=snapshot["generation"],
                reserved=snapshot["reserved"], blocked=snapshot["blocked"], attempts=attempts)


def safe_gateway_diagnostic(value):
    if value is None:
        return None
    from src.supervisor.infrastructure.openai_meaning_gateway import DIAGNOSTIC_STAGES
    if (type(value) is not dict or set(value) != {"events", "settlement_uncertain"}
        or type(value["settlement_uncertain"]) is not bool or type(value["events"]) is not list
        or len(value["events"]) > 16):
        raise Closed("DIAGNOSTIC_INVALID")
    events = []
    for event in value["events"]:
        if (type(event) is not dict or set(event) != {"stage", "elapsed_ms"}
            or event["stage"] not in DIAGNOSTIC_STAGES
            or type(event["elapsed_ms"]) is not int or not 0 <= event["elapsed_ms"] <= 120000):
            raise Closed("DIAGNOSTIC_INVALID")
        events.append(dict(event))
    return dict(events=events, settlement_uncertain=value["settlement_uncertain"])


def observe_failure(observation, error):
    # These are helper-local semantic gates, not controller or settlement errors.
    # Preserve only exact helper type and two fixed labels; never exception text.
    if type(error) is Closed and error.code in {"MEANING_REJECTED", "MEANING_NOT_SUPPLEMENTED"}:
        if observation.error_code is None:
            observation.error_code = error.code
        return
    observation.failed(C.ControllerError(error.code) if type(error) is Closed
        and error.code in {"FIRST_SETTLEMENT_UNCONFIRMED", "FINAL_LEDGER_UNCONFIRMED", "DIAGNOSTIC_INVALID"} else error)

async def _run(scope=None, *, source=None, authority=None, journal=None, synthetic=False, hooks=None, clock=None):
    """Private DI only. Missing authority/defaults never create resources or keys."""
    if (
        type(scope) is not Scope
        or type(journal) is not Journal
        or authority is None
        or source is None
        or synthetic
        and hooks is None
        or not synthetic
        and (hooks is not None
        or clock is not None)
    ):
        raise Closed("DEFAULT_UNAVAILABLE")
    clock = clock or Clock()
    scope.check(source, authority, synthetic=synthetic)
    journal_scope = dict(path=str(journal.path), directory=journal.directory, lock=journal.lock_pin)
    if journal.scope_sha256 != scope.sha256 or scope.data["journal"] != journal_scope:
        raise Closed("JOURNAL_SCOPE")
    journal.enter()
    session = Session(scope, source, authority, journal, synthetic, clock)
    observation = C.AttemptObservation(0)
    proof = principal = binding = None
    error = result = None
    gateway_diagnostic = None
    used_hooks = None
    try:
        await session.call("admission")
        await session.call("reserve", consuming=True)
        journal.persist("claimed", dict(phase="reserve_ACK", total_reserved_nano=reservation_total(scope),
                        authority_ack_sha256=session.last_ack_sha256, authority_sequence=session.sequence,
                        issued_at=session.lease.issued.isoformat(), expires_at=session.lease.expires.isoformat()))
        await session.call("issue", consuming=True)
        journal.persist("claimed", dict(phase="issue_ACK", authority_ack_sha256=session.last_ack_sha256, authority_sequence=session.sequence))
        session.lease.check(starting=True)
        await session.call("start", consuming=True)
        session.lease.check(starting=True)
        journal.persist("claimed", dict(phase="start_ACK", authority_ack_sha256=session.last_ack_sha256, authority_sequence=session.sequence))
        d = scope.data
        journal.grant = dict(epoch_id=d["epoch_id"], semantic_sha256=d["semantic_sha256"])
        used_hooks = hooks if synthetic else OwnedHooks(session)
        await session.call("resource")
        session.check()
        session.lease.check(starting=True)
        used_hooks.create()
        session.check()
        async with asyncio.timeout(min(240, session.lease.check())):
            with C.bounded_driver(used_hooks.driver, time.monotonic() + min(240, session.lease.check())), guarded_driver(used_hooks.driver, session):
                proof, principal, binding = await used_hooks.bootstrap(journal)
                session.check()
                result = await verify_once(session, proof, binding, principal, observation)
                observation.returned(result)
                gateway_diagnostic = safe_gateway_diagnostic(result.get("gateway_diagnostic"))
                session.check()
                if result["settlement"] != "observed":
                    raise Closed("FIRST_SETTLEMENT_UNCONFIRMED")
                if result["meaning_status"] != "supplemented":
                    raise Closed("MEANING_REJECTED" if result["meaning_status"] == "rejected" else "MEANING_NOT_SUPPLEMENTED")
    except BaseException as caught:
        error = caught
        observe_failure(observation, caught)
    finally:
        snapshot = None
        acked = False
        if used_hooks is not None:
            if proof is not None and binding is not None:
                try:
                    async with asyncio.timeout(5):
                        with C.bounded_driver(used_hooks.driver, time.monotonic() + 5):
                            snapshot = await used_hooks.snapshot(proof, binding, principal)
                except asyncio.CancelledError as caught:
                    error = caught
                except BaseException:
                    error = error or Closed("FINAL_LEDGER_UNCONFIRMED")
            try:
                try:
                    ledger = safe_ledger(snapshot, session)
                except Exception:
                    ledger = None
                    error = error or Closed("LEDGER_LIMIT")
                if snapshot is None:
                    error = error or Closed("FINAL_LEDGER_UNCONFIRMED")
                elif error is None:
                    try:
                        C.normal_transition(snapshot, scope.data["request"])
                    except Exception:
                        error = Closed("FIRST_SETTLEMENT_UNCONFIRMED")
                if error is not None:
                    # Late ledger rejection is classified before the durable
                    # accounting snapshot; keep an earlier supplier/cancel cause.
                    observe_failure(observation, error)
                account = dict(phase="final_accounting", ledger=ledger, observation="fresh_ledger" if ledger is not None else "unknown",
                               estimated_nano=None, http="unknown", reserved_nano=reservation_total(scope),
                               diagnostic=observation.snapshot(), gateway_diagnostic=gateway_diagnostic,
                               quality=getattr(session, "quality", None))
                journal.persist("claimed", account)
                await session.call("accounting", consuming=True, cleanup=True, record=account)
                journal.persist("claimed", dict(phase="closing", external_accounting_ACK=True))
                acked = True
            except asyncio.CancelledError as caught:
                error = caught
            except BaseException as caught:
                error = error or caught
            try:
                if acked:
                    with C.bounded_driver(used_hooks.driver, time.monotonic() + 30):
                        async with asyncio.timeout(30):
                            used_hooks.cleanup()
                    journal.persist("closed", dict(phase="cleanup_confirmed"))
                else:
                    from contextlib import nullcontext
                    boundary = C.bounded_driver(used_hooks.driver, time.monotonic() + 5) if used_hooks.driver is not None else nullcontext()
                    async with asyncio.timeout(5):
                        with boundary:
                            used_hooks.preserve()
            except asyncio.CancelledError as caught:
                error = caught
            except BaseException as caught:
                error = error or caught
        else:
            try:
                journal.persist("closed", dict(phase="closing", unknown_hold_nano=50000000 if session.reservation_attempted else None,
                    total_reserved_nano=reservation_total(scope), reservation_attempted=session.reservation_attempted, outcome="not_started"))
            except asyncio.CancelledError as caught:
                error = caught
            except BaseException as caught:
                error = error or caught
        journal.close()
    if error is not None:
        if isinstance(error, asyncio.CancelledError):
            raise error
        raise Closed(error.code if type(error) is Closed else "SUCCESSOR_FAILED") from None
    return dict(status="finished", diagnostic=observation.snapshot(), gateway_diagnostic=gateway_diagnostic, total_reserved_nano=reservation_total(scope),
                count_http="unknown", generation_http="unknown")


async def run(*args, **kwargs):
    try:
        return await _run(*args, **kwargs)
    except asyncio.CancelledError:
        raise
    except Closed:
        raise
    except Exception:
        raise Closed("SUCCESSOR_FAILED") from None


def check_retry3(d, base):
    """One newly approved diagnostic after observed, closed ordinal2 only."""
    r=d['retry']
    keys={'schema','ordinal','prior_retry','evidence','historical_code','readback_binding','record_body','record_body_sha256','record_item_id','record_turn_id',
          'consent_message_id','carried_nano','total_reserved_nano','current_code'}
    if (set(r)!=keys or r['schema']!='cf026.successor.retry3.v1' or type(r['ordinal']) is not int or r['ordinal']!=3
        or type(r['carried_nano']) is not int or r['carried_nano']!=300000000
        or type(r['total_reserved_nano']) is not int or r['total_reserved_nano']!=350000000
        or type(r['consent_message_id']) is not str or C.re.fullmatch(r'Sentinel_[a-f0-9]{32}',r['consent_message_id']) is None
        or type(r['prior_retry']) is not dict or r['prior_retry'].get('ordinal')!=2):
        raise Closed('RETRY_SCOPE')
    # Keep all old250m/unknown validation exactly as before.
    check_retry2(d|{'retry':r['prior_retry']},base)
    home=base/'.cf037-supervisor-single-revalidation-20261111'
    expected=dict(inputs=home/'reviewed-successor-inputs.json',journal=home/'successor-journal-retry-2'/'state.json',
        phases=home/'successor-phases-retry-2.json',runtime=home/'prepared-runtime-manifest.json',source=home/'runtime-source-manifest.json',
        manifest=home/'preissue-final-manifest.json',result=base/'.cf037-supervisor-observed-rejection-20261111'/'actual-result.json',
        readback=base/'.cf037-supervisor-grounding-diagnostic-20261111'/'prior-ordinal2-readback.json')
    if type(r['evidence']) is not dict or set(r['evidence'])!=set(expected):raise Closed('RETRY_EVIDENCE')
    records={}
    for name,path in expected.items():
        pin=r['evidence'][name]
        if type(pin) is not dict or set(pin)!={'path','stamp_json','sha256'} or pin['path']!=str(path):raise Closed('RETRY_EVIDENCE')
        records[name]=Artifact(name,path,pin['stamp_json'],pin['sha256']).verify(base)
    inputs=records['inputs'];prior=inputs['template']['scope_template']
    if (prior.get('retry')!=r['prior_retry'] or any(prior.get(k)!=d[k] for k in
        ('namespace','predecessor_bootstrap','predecessor_sha256','artifacts','request','semantic_sha256','price_sha256'))):
        raise Closed('RETRY_EVIDENCE')
    runtime=records['runtime'];manifest=records['manifest'];source=records['source']
    if (inputs.get('runtime')!=runtime or runtime.get('source_manifest')!=source.get('runtime_source_hashes')
        or runtime.get('source_count')!=281 or len(runtime.get('source_manifest',{}))!=281
        or runtime.get('successor_sha256')!=prior.get('module_sha256')
        or runtime.get('source_manifest',{}).get('backend/scripts/cf026_successor.py')!=prior.get('module_sha256')
        or manifest.get('inputs_sha256')!=r['evidence']['inputs']['sha256']
        or manifest.get('source_manifest_sha256')!=r['evidence']['source']['sha256']
        or manifest.get('private_active')!=inputs.get('private_code_sha256')):
        raise Closed('CODE_DRIFT')
    code_paths=dict(entry=home/'private_entry.py',helper=base/'.cf037-supervisor-observed-rejection-20261111'/'helper.py')
    if type(r['historical_code']) is not dict or set(r['historical_code'])!=set(code_paths):raise Closed('CODE_DRIFT')
    hashes={}
    for name,path in code_paths.items():
        pin=r['historical_code'][name]
        if type(pin) is not dict or set(pin)!={'path','stamp_json','sha256'} or pin['path']!=str(path):raise Closed('CODE_DRIFT')
        raw,_=C.read_fixed(path,0o600,C.decode(pin['stamp_json']),limit=131072)
        hashes[name]=hashlib.sha256(raw).hexdigest()
        if hashes[name]!=pin['sha256']:raise Closed('CODE_DRIFT')
        if name=='entry' and (raw.count(b'RELEASED = False\n')!=1 or b'RELEASED = True\n' in raw):raise Closed('CODE_DRIFT')
    if hashes['helper']!=prior['module_sha256'] or hashes['entry']!=manifest['private_inactive']['private_entry.py']:
        raise Closed('CODE_DRIFT')
    marker='CF026_SUCCESSOR_RESERVE_ONCE\n';body=r['record_body']
    if type(body) is not str or not body.startswith(marker) or len(body.encode())>8192 or hashlib.sha256(body.encode()).hexdigest()!=r['record_body_sha256']:
        raise Closed('RETRY_EVIDENCE')
    record=C.decode(body[len(marker):]);required={'schema','additional_reserve_nano','authority_sha256','count_cap','delegation','generation_cap',
        'http_cap','invocation','issued_at','namespace','predecessor_sha256','process_id','retry_cap','retry_ordinal','retry_of_sha256',
        'scope_sha256','successor_once','synthetic_only','total_reserved_nano'}
    if (set(record)!=required or record['schema']!='cf026.successor.reserve-once.v1' or record['synthetic_only'] is not False
        or record['namespace']!=d['namespace'] or record['predecessor_sha256']!=d['predecessor_sha256']
        or record['invocation']==d['invocation'] or type(record['process_id']) is not int or record['process_id']<=0
        or record['successor_once']!=C.digest(dict(namespace=d['namespace'],predecessor_bootstrap=d['predecessor_bootstrap'],retry_ordinal=2))
        or record['retry_of_sha256']!=r['prior_retry']['record_body_sha256']
        or record['delegation']!='same-invocation-ordered-local-fsync'
        or record['authority_sha256']!=inputs['authority_sha256']
        or C.parse_expiry(record['issued_at'])<C.parse_expiry(prior['consent_at'])):raise Closed('RETRY_EVIDENCE')
    for key,value in dict(additional_reserve_nano=50000000,total_reserved_nano=300000000,retry_ordinal=2,count_cap=1,generation_cap=1,http_cap=2,retry_cap=0).items():
        if type(record[key]) is not int or record[key]!=value:raise Closed('RETRY_EVIDENCE')
    for key in ('authority_sha256','invocation','scope_sha256'):
        if type(record[key]) is not str or C.re.fullmatch('[a-f0-9]{64}',record[key]) is None:raise Closed('RETRY_EVIDENCE')
    routing=r['readback_binding']
    if type(routing) is not dict or set(routing)!={'source_thread_id','destination_thread_id'}:raise Closed('RETRY_EVIDENCE')
    for value in routing.values():
        if type(value) is not str or str(UUID(value))!=value:raise Closed('RETRY_EVIDENCE')
    if routing['source_thread_id']==routing['destination_thread_id']:raise Closed('RETRY_EVIDENCE')
    readback=records['readback'];matches=[]
    if readback.get('thread',{}).get('id')!=routing['destination_thread_id']:raise Closed('RETRY_EVIDENCE')
    for turn in readback.get('turns',[]):
        for item in turn.get('items',[]):
            text=item.get('output',{}).get('text')
            if (item.get('type')=='functionCallOutput' and item.get('namespace')=='cloud_threads' and item.get('name')=='send_message'
                and item.get('output',{}).get('truncated') is False and type(text) is str):
                match=C.re.fullmatch(r'\s*<codex_delegation>\s*<source_thread_id>([^<>]+)</source_thread_id>\s*<input>([\s\S]*)</input>\s*</codex_delegation>\s*',text)
                if match and match[1]==routing['source_thread_id'] and match[2]==body:
                    matches.append((item.get('id'),turn.get('id')))
    if matches!=[(r['record_item_id'],r['record_turn_id'])]:raise Closed('RETRY_EVIDENCE')
    journal,phases,result=records['journal'],records['phases'],records['result'];events=journal.get('journal',[])
    accounts=[e for e in events if e.get('phase')=='final_accounting']
    if (journal.get('status')!='closed' or journal.get('schema')!='cf026.successor.journal.v1' or journal.get('scope_sha256')!=record['scope_sha256']
        or journal.get('rights')!=dict(count=1,generation=1) or len(accounts)!=1 or not events or events[-1].get('phase')!='cleanup_confirmed'
        or len([e for e in events if e.get('phase')=='closing' and e.get('external_accounting_ACK') is True])!=1):raise Closed('RETRY_EVIDENCE')
    account=accounts[0];ledger=account.get('ledger',{});attempts=ledger.get('attempts',[])
    if (account.get('reserved_nano')!=300000000 or account.get('observation')!='fresh_ledger' or len(attempts)!=1
        or any(type(ledger.get(k)) is not int or ledger[k]!=v for k,v in dict(count=1,generation=1,reserved=50000000).items())
        or ledger.get('blocked') is not False or attempts[0].get('state')!='observed'
        or account.get('diagnostic',{}).get('verifier',{}).get('meaning_status')!='rejected'
        or account.get('diagnostic',{}).get('verifier',{}).get('settlement')!='observed'
        or account.get('quality')!=dict(status='rejected',assessment=None)
        or account.get('gateway_diagnostic',{}).get('settlement_uncertain') is not False
        or 'settlement_ACK' not in [e.get('stage') for e in account.get('gateway_diagnostic',{}).get('events',[])]):raise Closed('ACCOUNTING')
    from src.modules.supervisor.domain.contracts import MEANING_SPEC
    usage=attempts[0].get('usage',{});price=MEANING_SPEC['price']
    if (set(usage)!={'input_tokens','output_tokens','total_tokens','cached_tokens'} or any(type(v) is not int or v<0 for v in usage.values())
        or usage['input_tokens']>16384 or usage['output_tokens']>2048 or usage['cached_tokens']>usage['input_tokens']
        or usage['total_tokens']!=usage['input_tokens']+usage['output_tokens'] or attempts[0].get('model')!=MEANING_SPEC['model']
        or type(attempts[0].get('estimated_nano')) is not int
        or attempts[0]['estimated_nano']!=(usage['input_tokens']-usage['cached_tokens'])*price['input_nano_per_token']+usage['cached_tokens']*price['cached_nano_per_token']+usage['output_tokens']*price['output_nano_per_token']):raise Closed('ACCOUNTING')
    binding={k:record[k] for k in record if k not in {'schema','synthetic_only','process_id','authority_sha256','delegation','issued_at'}}
    ack=binding|dict(phase='accounting',authority_sha256=record['authority_sha256'],sequence=6,issued_at=record['issued_at'],consumed=True,record_sha256=C.digest(account))
    if (phases.get('binding')!=binding or phases.get('ack')!=ack or phases.get('sequence')!=6
        or phases.get('phases')!=['reserve','issue','start','count','generation','accounting']):raise Closed('ACCOUNTING')
    direct=result.get('direct_readonly',{})
    if (result.get('schema')!='cf037.ordinal2.actual-result.v1' or direct.get('accounting')!=account
        or direct.get('journal_closed') is not True or direct.get('cleanup_confirmed') is not True
        or direct.get('local_accounting_ack_matches') is not True or direct.get('entry_RELEASED') is not False
        or direct.get('entry_sha256')!=hashes['entry'] or C.parse_expiry(d['consent_at'])<=C.parse_expiry(record['issued_at'])):
        raise Closed('RETRY_EVIDENCE')


# Exact pre-CF038 contract, used only to validate already-consumed history.
PRE_ALIGNMENT_SEMANTIC='c3cb325b4b4e92cf72b1ff62714dec6e12f8637220dcaa0b2d9443644b397251'
PRE_ALIGNMENT_PROMPT='519c74093fd260c424e68feb877c963c318815237d5177522054ce2b1d728f39'


def retry4_prior(data, base):
    r=data.get('retry')
    path=base/'.cf037-supervisor-grounding-diagnostic-20261111'/'reviewed-successor-inputs.json'
    pin=r.get('evidence',{}).get('inputs') if type(r) is dict else None
    if type(pin) is not dict or set(pin)!={'path','stamp_json','sha256'} or pin['path']!=str(path):raise Closed('RETRY_EVIDENCE')
    inputs=Artifact('inputs',path,pin['stamp_json'],pin['sha256']).verify(base)
    prior=inputs.get('template',{}).get('scope_template')
    if type(prior) is not dict or prior.get('retry',{}).get('ordinal')!=3:raise Closed('RETRY_EVIDENCE')
    return inputs,prior


def historical_request(data,base):
    if data.get('retry',{}).get('ordinal')==4:
        return retry4_prior(data,base)[1]['request']
    return data['request']


def check_retry4(d, base):
    """Today's one fixed run after observed, closed ordinal3; no general retry."""
    r=d['retry']
    keys={'schema','ordinal','prior_retry','evidence','historical_code','readback_binding','record_body','record_body_sha256','record_item_id','record_turn_id',
          'consent_message_id','carried_nano','total_reserved_nano','current_code'}
    if (type(r) is not dict or set(r)!=keys or r['schema']!='cf026.successor.retry4.v1'
        or type(r['ordinal']) is not int or r['ordinal']!=4 or type(r['carried_nano']) is not int or r['carried_nano']!=350000000
        or type(r['total_reserved_nano']) is not int or r['total_reserved_nano']!=400000000
        or type(r['consent_message_id']) is not str or C.re.fullmatch(r'Sentinel_[a-f0-9]{32}',r['consent_message_id']) is None):raise Closed('RETRY_SCOPE')
    inputs,prior=retry4_prior(d,base)
    if (prior.get('retry')!=r['prior_retry'] or any(prior.get(k)!=d[k] for k in ('namespace','predecessor_bootstrap','predecessor_sha256','artifacts','price_sha256'))
        or prior.get('semantic_sha256')!=PRE_ALIGNMENT_SEMANTIC
        or prior.get('request',{}).get('prepare_body')!=d['request'].get('prepare_body')
        or prior['request'].get('draft_sha256')!=d['request'].get('draft_sha256')):raise Closed('RETRY_EVIDENCE')
    # Old validators see the old scope, not the newly rendered prompt/hash.
    check_retry3(prior,base)
    home=base/'.cf037-supervisor-grounding-diagnostic-20261111'
    expected=dict(inputs=home/'reviewed-successor-inputs.json',journal=home/'successor-journal-retry-3'/'state.json',
        phases=home/'successor-phases-retry-3.json',runtime=home/'prepared-runtime-manifest.json',source=home/'runtime-source-manifest.json',
        manifest=home/'final-manifest.json',result=home/'actual-result.json',readback=home/'actual-ordinal3-readback.json')
    if type(r['evidence']) is not dict or set(r['evidence'])!=set(expected):raise Closed('RETRY_EVIDENCE')
    records={}
    for name,path in expected.items():
        pin=r['evidence'][name]
        if type(pin) is not dict or set(pin)!={'path','stamp_json','sha256'} or pin['path']!=str(path):raise Closed('RETRY_EVIDENCE')
        records[name]=Artifact(name,path,pin['stamp_json'],pin['sha256']).verify(base)
    runtime=records['runtime'];manifest=records['manifest'];source=records['source']
    if (records['inputs']!=inputs or inputs.get('runtime')!=runtime or runtime.get('source_manifest')!=source.get('runtime_source_hashes')
        or runtime.get('source_count')!=281 or len(runtime.get('source_manifest',{}))!=281
        or runtime.get('successor_sha256')!=prior.get('module_sha256')
        or runtime['source_manifest'].get('backend/scripts/cf026_successor.py')!=prior['module_sha256']
        or manifest.get('inputs_sha256')!=r['evidence']['inputs']['sha256']
        or manifest.get('source_manifest_sha256')!=r['evidence']['source']['sha256']
        or manifest.get('private_active')!=inputs.get('private_code_sha256')):raise Closed('CODE_DRIFT')
    oldroot=base/'verith-supervisor-single-revalidation'
    code_paths=dict(entry=(home/'private_entry.py',0o600),runtime=(home/'private_runtime.py',0o600),assembly=(home/'private_assembly.py',0o600),
        helper=(oldroot/'backend/scripts/cf026_successor.py',0o644),prompt=(oldroot/'ai/src/supervisor/prompts/meaning.txt',0o644),
        policy=(oldroot/'ai/src/supervisor/application/meaning_policy.py',0o644),semantic=(oldroot/'backend/src/modules/supervisor/domain/contracts.py',0o644))
    if type(r['historical_code']) is not dict or set(r['historical_code'])!=set(code_paths):raise Closed('CODE_DRIFT')
    raw_code={};hashes={}
    names=dict(helper='backend/scripts/cf026_successor.py',prompt='ai/src/supervisor/prompts/meaning.txt',policy='ai/src/supervisor/application/meaning_policy.py',semantic='backend/src/modules/supervisor/domain/contracts.py')
    for name,(path,mode) in code_paths.items():
        pin=r['historical_code'][name]
        if type(pin) is not dict or set(pin)!={'path','stamp_json','sha256'} or pin['path']!=str(path):raise Closed('CODE_DRIFT')
        raw,_=C.read_fixed(path,mode,C.decode(pin['stamp_json']),limit=131072)
        value=hashlib.sha256(raw).hexdigest();hashes[name]=value;raw_code[name]=raw
        if value!=pin['sha256']:raise Closed('CODE_DRIFT')
        expected_hash=runtime['source_manifest'].get(names[name]) if name in names else manifest['private_inactive'].get('private_'+name+'.py')
        if value!=expected_hash:raise Closed('CODE_DRIFT')
    if raw_code['entry'].count(b'RELEASED = False\n')!=1 or b'RELEASED = True\n' in raw_code['entry']:raise Closed('CODE_DRIFT')
    from src.modules.supervisor.domain.contracts import MEANING_SPEC,MEANING_SPEC_SHA256,PreparationRequest
    from src.supervisor.infrastructure.openai_meaning_gateway import rendered_request,INPUT_FIELDS
    tree=ast.parse(raw_code['semantic'])
    definitions=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='MEANING_SPEC' for x in n.targets)]
    if len(definitions)!=1:raise Closed('CODE_DRIFT')
    oldspec=ast.literal_eval(definitions[0].value)
    if (C.digest(oldspec)!=PRE_ALIGNMENT_SEMANTIC or oldspec.get('prompt_sha256')!=PRE_ALIGNMENT_PROMPT
        or hashes['prompt']!=PRE_ALIGNMENT_PROMPT or oldspec | {'prompt_sha256':MEANING_SPEC['prompt_sha256']}!=MEANING_SPEC
        or d['semantic_sha256']!=MEANING_SPEC_SHA256):raise Closed('REQUEST_DRIFT')
    body=PreparationRequest.model_validate(d['request']['prepare_body'])
    oldrender=rendered_request(body.draft);oldrender['instructions']=raw_code['prompt'].decode('utf8')
    if prior['request']['request_sha256']!=C.digest(oldrender) or prior['request']['projection_sha256']!=C.digest({k:oldrender[k] for k in INPUT_FIELDS}):raise Closed('REQUEST_DRIFT')
    marker='CF026_SUCCESSOR_RESERVE_ONCE\n';body=r['record_body']
    if type(body) is not str or not body.startswith(marker) or len(body.encode())>8192 or hashlib.sha256(body.encode()).hexdigest()!=r['record_body_sha256']:raise Closed('RETRY_EVIDENCE')
    record=C.decode(body[len(marker):]);required={'schema','additional_reserve_nano','authority_sha256','count_cap','delegation','generation_cap','http_cap','invocation','issued_at','namespace','predecessor_sha256','process_id','retry_cap','retry_ordinal','retry_of_sha256','scope_sha256','successor_once','synthetic_only','total_reserved_nano'}
    if (set(record)!=required or record['schema']!='cf026.successor.reserve-once.v1' or record['synthetic_only'] is not False
        or record['namespace']!=d['namespace'] or record['predecessor_sha256']!=d['predecessor_sha256'] or record['invocation']==d['invocation']
        or type(record['process_id']) is not int or record['process_id']<=0
        or record['successor_once']!=C.digest(dict(namespace=d['namespace'],predecessor_bootstrap=d['predecessor_bootstrap'],retry_ordinal=3))
        or record['retry_of_sha256']!=r['prior_retry']['record_body_sha256'] or record['authority_sha256']!=inputs['authority_sha256']
        or record['delegation']!='same-invocation-ordered-local-fsync' or C.parse_expiry(record['issued_at'])<C.parse_expiry(prior['consent_at'])):raise Closed('RETRY_EVIDENCE')
    for key,value in dict(additional_reserve_nano=50000000,total_reserved_nano=350000000,retry_ordinal=3,count_cap=1,generation_cap=1,http_cap=2,retry_cap=0).items():
        if type(record[key]) is not int or record[key]!=value:raise Closed('RETRY_EVIDENCE')
    routing=r['readback_binding'];readback=records['readback'];matches=[]
    if type(routing) is not dict or set(routing)!={'source_thread_id','destination_thread_id'}:raise Closed('RETRY_EVIDENCE')
    for value in routing.values():
        if type(value) is not str or str(UUID(value))!=value:raise Closed('RETRY_EVIDENCE')
    if routing['source_thread_id']==routing['destination_thread_id'] or readback.get('thread',{}).get('id')!=routing['destination_thread_id']:raise Closed('RETRY_EVIDENCE')
    for turn in readback.get('turns',[]):
        for item in turn.get('items',[]):
            text=item.get('output',{}).get('text')
            if item.get('type')=='functionCallOutput' and item.get('namespace')=='cloud_threads' and item.get('name')=='send_message' and item.get('output',{}).get('truncated') is False and type(text) is str:
                match=C.re.fullmatch(r'\s*<codex_delegation>\s*<source_thread_id>([^<>]+)</source_thread_id>\s*<input>([\s\S]*)</input>\s*</codex_delegation>\s*',text)
                if match and match[1]==routing['source_thread_id'] and match[2]==body:matches.append((item.get('id'),turn.get('id')))
    if matches!=[(r['record_item_id'],r['record_turn_id'])]:raise Closed('RETRY_EVIDENCE')
    journal,phases,result=records['journal'],records['phases'],records['result'];events=journal.get('journal',[])
    accounts=[e for e in events if e.get('phase')=='final_accounting']
    if (journal.get('schema')!='cf026.successor.journal.v1' or journal.get('status')!='closed' or journal.get('scope_sha256')!=record['scope_sha256']
        or journal.get('rights')!=dict(count=1,generation=1) or len(accounts)!=1 or not events or events[-1].get('phase')!='cleanup_confirmed'
        or len([e for e in events if e.get('phase')=='closing' and e.get('external_accounting_ACK') is True])!=1):raise Closed('RETRY_EVIDENCE')
    account=accounts[0];ledger=account.get('ledger',{});attempts=ledger.get('attempts',[])
    if (account.get('reserved_nano')!=350000000 or account.get('observation')!='fresh_ledger' or len(attempts)!=1
        or any(type(ledger.get(k)) is not int or ledger[k]!=v for k,v in dict(count=1,generation=1,reserved=50000000).items())
        or ledger.get('blocked') is not False or attempts[0].get('state')!='observed'
        or account.get('diagnostic',{}).get('verifier',{}).get('meaning_status')!='rejected'
        or account.get('diagnostic',{}).get('verifier',{}).get('settlement')!='observed'
        or account.get('quality',{}).get('status')!='rejected' or account['quality'].get('assessment') is not None
        or account.get('gateway_diagnostic',{}).get('settlement_uncertain') is not False
        or 'settlement_ACK' not in [e.get('stage') for e in account.get('gateway_diagnostic',{}).get('events',[])]):raise Closed('ACCOUNTING')
    usage=attempts[0].get('usage',{});price=oldspec['price']
    if (set(usage)!={'input_tokens','output_tokens','total_tokens','cached_tokens'} or any(type(v) is not int or v<0 for v in usage.values())
        or usage['input_tokens']>16384 or usage['output_tokens']>2048 or usage['cached_tokens']>usage['input_tokens']
        or usage['total_tokens']!=usage['input_tokens']+usage['output_tokens'] or attempts[0].get('model')!=oldspec['model']
        or type(attempts[0].get('estimated_nano')) is not int
        or attempts[0]['estimated_nano']!=(usage['input_tokens']-usage['cached_tokens'])*price['input_nano_per_token']+usage['cached_tokens']*price['cached_nano_per_token']+usage['output_tokens']*price['output_nano_per_token']):raise Closed('ACCOUNTING')
    binding={k:record[k] for k in record if k not in {'schema','synthetic_only','process_id','authority_sha256','delegation','issued_at'}}
    ack=binding|dict(phase='accounting',authority_sha256=record['authority_sha256'],sequence=6,issued_at=record['issued_at'],consumed=True,record_sha256=C.digest(account))
    if phases.get('binding')!=binding or phases.get('ack')!=ack or phases.get('sequence')!=6 or phases.get('phases')!=['reserve','issue','start','count','generation','accounting']:raise Closed('ACCOUNTING')
    pins=result.get('postexecution_pins',{})
    if (result.get('schema')!='cf037.b5.actual-result.v1' or result.get('accounting')!=account or result.get('journal_closed') is not True
        or result.get('cleanup_confirmed') is not True or result.get('entry_released') is not False or result.get('total_reserved_nano')!=350000000
        or result.get('frozen_inputs_sha256')!=r['evidence']['inputs']['sha256'] or result.get('frozen_source_manifest_sha256')!=r['evidence']['source']['sha256']
        or result.get('frozen_preissue_manifest_sha256')!=r['evidence']['manifest']['sha256'] or result.get('actual_record_readback_sha256')!=r['evidence']['readback']['sha256']
        or result.get('record_count')!=1
        or result.get('inactive_entry_sha256')!=hashes['entry'] or any(pins.get('private_'+k+'.py')!=hashes[k] for k in ('entry','runtime','assembly'))
        or pins.get('successor-journal-retry-3/state.json')!=r['evidence']['journal']['sha256']
        or pins.get('successor-phases-retry-3.json')!=r['evidence']['phases']['sha256']
        or C.parse_expiry(d['consent_at'])<=C.parse_expiry(record['issued_at'])):raise Closed('RETRY_EVIDENCE')
