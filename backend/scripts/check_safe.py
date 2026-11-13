"""ST-001 3-B controller. Public launch MUST use env -i and Python -I -S.

No application imports, dotenv discovery, dependency installation or DB fallback.
Unsupported OS protection is a hard failure, never a reason to run unconfined.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

UNIT = tuple(f"tests/unit/{name}.py" for name in (
    "test_flow_contract", "test_cf002_boundary", "test_cf002_google",
    "test_cf002_local_ports", "test_cf002_review_regressions",
    "test_cf002_session_failures",
))
AUDITED_STOCK_TESTS = (
    "tests/test_text_normalize.py", "tests/test_stock_master_parser.py",
    "tests/test_dart_corp_code_parser.py",
)
AUDITED_TECHNICAL_TESTS = ("tests/test_technical_read_model.py",)
AUDITED_CLIENT_TESTS = ("tests/test_ai_client.py",)
AUDITED_NEWS_TESTS = ("tests/test_importance.py",)
UNIT += AUDITED_STOCK_TESTS + AUDITED_TECHNICAL_TESTS + AUDITED_CLIENT_TESTS + AUDITED_NEWS_TESTS
UNIT += ("tests/unit/test_cf003_flow_runs.py",)
UNIT += ("tests/unit/test_cf004_kis_token_cache.py",)
UNIT += ("tests/unit/test_cf005_flow_observation.py",)
UNIT += ("tests/unit/test_cf006_flow_input_snapshot.py",)
UNIT += ("tests/unit/test_cf007_flow_fake_execution.py",)
UNIT += ("tests/unit/test_cf008_flow_synthetic_demo.py",)
NEW = {"backend/scripts/check_safe.py", "backend/scripts/safe_checks_bootstrap.py",
       "backend/tests/safe_checks/test_entry.py",
       "backend/src/modules/flow/domain/payload.py",
       "backend/src/modules/flow/domain/execution.py",
       "backend/src/modules/flow/api/schemas.py",
       "backend/src/modules/flow/api/router.py",
       "backend/src/modules/flow/application/report_service.py",
       "backend/src/modules/flow/infrastructure/report_repository.py",
       "backend/src/shared/http/access_boundary.py",
       "backend/src/shared/infrastructure/clients/ai_client.py",
       "backend/src/shared/config.py",
       "backend/src/modules/auth/infrastructure/google_oidc.py",
       "backend/src/modules/auth/api/router.py",
       "backend/src/modules/auth/application/session_service.py",
       "backend/src/modules/reports/infrastructure/agent_report_repository.py",
       "backend/src/modules/reports/api/router.py",
       "backend/src/modules/reports/api/report_schemas.py",
       "backend/src/modules/reports/api/archive_schemas.py",
       "backend/src/modules/news/domain/importance_rules.py",
       "backend/src/modules/news/infrastructure/news_graph_repository.py",
       "backend/src/modules/news/infrastructure/report_repository.py",
       "backend/src/modules/news/infrastructure/news_repository.py",
       "backend/src/modules/news/api/router.py",
       "backend/src/modules/news/api/schemas.py",
       "backend/src/modules/news/api/report_schemas.py",
       "backend/src/modules/news/domain/importance.py",
       "backend/src/modules/news/application/cleanup_service.py",
       "backend/src/modules/news/application/graph_query_service.py",
       "backend/src/modules/news/application/query_service.py",
       "backend/src/modules/news/application/report_service.py",
       "backend/src/modules/news/application/ingest_service.py",
       "backend/src/modules/industry/infrastructure/report_repository.py",
       "backend/src/modules/industry/api/router.py",
       "backend/src/modules/industry/api/schemas.py",
       "backend/src/modules/industry/application/report_service.py",
       "backend/src/modules/fundamental/infrastructure/report_repository.py",
       "backend/src/modules/fundamental/api/router.py",
       "backend/src/modules/fundamental/domain/ai_output.py",
       "backend/src/modules/fundamental/api/schemas.py",
       "backend/src/modules/fundamental/application/report_service.py",
       "backend/src/modules/technical/infrastructure/report_repository.py",
       "backend/src/modules/technical/api/router.py",
       "backend/src/modules/technical/domain/ai_output.py",
       "backend/src/modules/technical/api/schemas.py",
       "backend/src/modules/technical/application/report_service.py",
       "backend/src/modules/stocks/infrastructure/dart_corp_code_client.py",
       "backend/src/modules/stocks/infrastructure/kis_master_client.py",
       "backend/src/modules/stocks/domain/constants/kis_master.py",
       "backend/src/modules/stocks/domain/constants/stock_aliases.py",
       "backend/src/modules/stocks/domain/constants/stock_match.py",
       "backend/src/modules/stocks/domain/constants/stocks.py",
       "backend/src/modules/stocks/infrastructure/corp_code_repository.py",
       "backend/src/modules/stocks/infrastructure/stock_repository.py",
       "backend/src/modules/stocks/api/router.py",
       "backend/src/modules/stocks/api/schemas.py",
       "backend/src/modules/stocks/application/corp_code_sync_service.py",
       "backend/src/modules/stocks/domain/dart_corp_code_parser.py",
       "backend/src/modules/stocks/domain/stock_master_parser.py",
       "backend/src/modules/stocks/application/resolver_service.py",
       "backend/src/modules/stocks/application/stock_sync_service.py",
       "backend/src/modules/stocks/domain/text_normalize.py",
       "ai/src/agents/flow/domain/models.py",
       "ai/src/agents/flow/api/payload.py"}
FLOW_POLICY_SOURCES = frozenset(['ai/src/agents/flow/infrastructure/kis_client.py', 'ai/src/agents/flow/infrastructure/llm/explain.py', 'ai/devtools/flow/streamlit_flow_lab.py'])
NEW.update(FLOW_POLICY_SOURCES)  # Source-copy/AST policy inspection only; never import these modules.
CF003_SOURCES = frozenset({
    "backend/src/modules/flow/api/run_schemas.py",
    "backend/src/modules/flow/api/run_router.py",
    "backend/src/modules/flow/application/run_service.py",
    "backend/src/modules/flow/infrastructure/run_repository.py",
    "backend/db/models/flow/flow_run.py",
    "backend/db/migrations/versions/20261108_c3001a7e0001_flow_run_admission.py",
    "backend/tests/unit/test_cf003_flow_runs.py",
    "backend/scripts/cf002_interactive_login.py",
    "backend/scripts/cf003_admission_check.py",
})
NEW.update(CF003_SOURCES)
CF006_SOURCES = frozenset({'backend/src/modules/flow/infrastructure/input_snapshot_repository.py', 'backend/src/modules/flow/application/input_preparation_service.py', 'backend/scripts/cf006_input_snapshot_check.py', 'backend/src/modules/flow/domain/input_snapshot.py', 'backend/tests/unit/test_cf006_flow_input_snapshot.py', 'backend/db/models/flow/input_snapshot.py', 'backend/db/migrations/versions/20261108_c6001a7e0001_flow_input_snapshots.py'})
NEW.update(CF006_SOURCES)
CF007_SOURCES = frozenset({'backend/src/modules/flow/application/fake_execution_service.py', 'backend/scripts/cf007_fake_execution_check.py', 'backend/src/modules/flow/infrastructure/fake_execution_repository.py', 'backend/db/migrations/versions/20261108_c7001a7e0001_flow_fake_execution.py', 'backend/tests/unit/test_cf007_flow_fake_execution.py', 'backend/db/models/flow/fake_execution.py', 'backend/src/modules/flow/domain/fake_execution.py'})
NEW.update(CF007_SOURCES)
CF008_SOURCES = frozenset({'backend/src/modules/flow/api/synthetic_demo_router.py', 'backend/src/modules/flow/api/synthetic_demo_schemas.py', 'backend/scripts/cf008_synthetic_demo_check.py', 'backend/tests/unit/test_cf008_flow_synthetic_demo.py', 'backend/src/modules/flow/application/synthetic_demo_service.py'})
NEW.update(CF008_SOURCES)
CF012_SOURCES = frozenset({'backend/tests/unit/test_cf012_flow_analysis.py', 'backend/src/modules/flow/application/analysis_service.py', 'backend/src/modules/flow/api/analysis_schemas.py', 'backend/db/models/flow/analysis_run.py', 'backend/db/migrations/versions/20261108_c12001a7e0001_flow_analysis_runs.py', 'backend/src/modules/flow/domain/analysis.py', 'backend/src/modules/flow/api/analysis_router.py', 'backend/scripts/cf012_analysis_check.py', 'backend/src/modules/flow/infrastructure/analysis_repository.py'})
NEW.update(CF012_SOURCES)
CF012_INPUTS = {'ai/src/agents/flow/api/http.py': 'dc1c4c5fa28aec3ea8e7bb7813c61fbb107f2c5d5a6e53d7ff4d72d99d46bfb8', 'ai/src/agents/flow/api/schemas.py': 'cccacc7290ada82b5344b716f8c671907ffd4d9ad076d91dc0c444730139fb5d', 'ai/src/agents/flow/application/execution_runtime.py': '55e018f7b348a312d3eadb11eccdb281b7e2598a4eb286e0ff677588a0d7f524', 'ai/src/shared/runtime/deadline.py': '4a51cd138da3a37d158e03019e4b38c203bd276948a21987b0d07d35a68cb60e'}
NEW.update(CF012_INPUTS)
NEW.update({"backend/tests/unit/test_runner_owned_database.py", "backend/scripts/runner_owned_database.py", "backend/scripts/google_login_workspace.py"})
OWNED_TESTS = ("tests/unit/test_runner_owned_database.py",)
CF013_SOURCES = frozenset({
    "backend/src/modules/analysis/domain/contracts.py", "backend/src/modules/analysis/application/ports.py",
    "backend/src/modules/flow/application/analysis_adapter.py", "backend/examples/analysis/fundamental_adapter.py",
    "backend/examples/analysis/fundamental-response.v1.json", "backend/tests/unit/test_cf013_analysis_contracts.py",
    "backend/scripts/cf013_contract_check.py",
})
NEW.update(CF013_SOURCES)
CF013_TESTS = ("tests/unit/test_cf013_analysis_contracts.py",)
CF012_TESTS = ("tests/unit/test_cf012_flow_analysis.py", "tests/unit/test_flow_contract.py")
UNIT += ("tests/unit/test_cf012_flow_analysis.py",)
CF005_INPUTS = {"ai/src/agents/flow/domain/observation_window.py": 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27'}
CF005_SOURCE_ONLY = frozenset({
    "ai/src/agents/flow/domain/verification/signals.py",
    "ai/src/agents/flow/infrastructure/render/builder.py",
    "ai/src/agents/flow/prompts/explain.txt",
    "ai/src/agents/flow/infrastructure/render/templates/supply_demand.html",
    "frontend/tests/fixtures/cf005-observation-cases.json",
})
NEW.update(CF005_INPUTS)
NEW.update(CF005_SOURCE_ONLY)
NEW.add("backend/tests/unit/test_cf005_flow_observation.py")
CF004_INPUTS = {"ai/src/agents/flow/infrastructure/token_cache.py": '3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f'}
NEW.update(CF004_INPUTS)
NEW.add("backend/tests/unit/test_cf004_kis_token_cache.py")
FLOW_INPUTS = {'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894'}
CF014_INPUTS = {'ai/src/agents/flow/domain/verification/consecutive.py': '35c8e994f01aa8447b117c0ef9a4746fe66f8b4687091bfa2d042eb3eab2bede', 'ai/src/agents/flow/domain/interpretation_claims.py': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22', 'ai/src/agents/flow/domain/verification/signals.py': '3f4e26fabbb2b64163bb1f8c0a77665316cd61a70d9eb1458d201f6395f57aaa', 'ai/src/agents/flow/domain/verification/interpretation.py': '863adcb582b601eacadb3fe894e92d9669670fbfd6c5f712841a64ba1bcfdd60', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894', 'ai/src/agents/flow/application/workflow.py': '03816e283c8f5ba0718738b4b71b79fc48d82f0240159fc23d0bc5259838809b', 'ai/src/agents/flow/infrastructure/llm/explain.py': '14bb4cba44295fe577ec019ca0b8994a712e1c03e44d1fadf8aabb840653c10b', 'ai/src/agents/flow/prompts/explain.txt': '9e8a04b6d7d0f534d54552e78ed489cb74f3cc7160fbd379b030758ae891406c', 'ai/src/agents/flow/api/schemas.py': 'cccacc7290ada82b5344b716f8c671907ffd4d9ad076d91dc0c444730139fb5d', 'ai/src/agents/flow/application/execution_runtime.py': '55e018f7b348a312d3eadb11eccdb281b7e2598a4eb286e0ff677588a0d7f524', 'ai/src/agents/flow/domain/observation_window.py': 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27', 'ai/src/agents/flow/domain/signals.py': '15de1236f86a78a14e5d5106247d0329167e12eb390b29ebf97cd5cd012ae2be', 'ai/src/agents/flow/config.py': '91c95356110d0294051eb7871bfb06100ebd003ccb0f2da33c6add2b0594b637', 'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2'}
CF014_COMPAT = dict(CF004_INPUTS)  # Existing exact origin invariant, no cache operations.
CF014_TESTS = ("tests/unit/test_cf014_flow_quality.py",)
NEW.update(CF014_INPUTS)
NEW.add("backend/tests/unit/test_cf014_flow_quality.py")
REMOVED_SOURCES = frozenset(['backend/src/api/access_boundary.py', 'backend/src/api/auth/google.py', 'backend/src/api/clients/ai_client.py', 'backend/src/api/clients/dart_corp_code_client.py', 'backend/src/api/clients/kis_master_client.py', 'backend/src/api/config.py', 'backend/src/api/constants/importance.py', 'backend/src/api/constants/kis_master.py', 'backend/src/api/constants/stock_aliases.py', 'backend/src/api/constants/stock_match.py', 'backend/src/api/constants/stocks.py', 'backend/src/api/repositories/agent_report_repository.py', 'backend/src/api/repositories/corp_code_repository.py', 'backend/src/api/repositories/flow_report_repository.py', 'backend/src/api/repositories/fundamental_report_repository.py', 'backend/src/api/repositories/industry_report_repository.py', 'backend/src/api/repositories/news_graph_repository.py', 'backend/src/api/repositories/news_report_repository.py', 'backend/src/api/repositories/news_repository.py', 'backend/src/api/repositories/stock_repository.py', 'backend/src/api/repositories/technical_report_repository.py', 'backend/src/api/routes/auth.py', 'backend/src/api/routes/flow_reports.py', 'backend/src/api/routes/fundamental_reports.py', 'backend/src/api/routes/industry_reports.py', 'backend/src/api/routes/news.py', 'backend/src/api/routes/reports.py', 'backend/src/api/routes/stocks.py', 'backend/src/api/routes/technical_reports.py', 'backend/src/api/schemas/agent_report.py', 'backend/src/api/schemas/ai_fundamental_output.py', 'backend/src/api/schemas/ai_technical_output.py', 'backend/src/api/schemas/flow_execution.py', 'backend/src/api/schemas/flow_payload.py', 'backend/src/api/schemas/flow_report.py', 'backend/src/api/schemas/fundamental_report.py', 'backend/src/api/schemas/industry_report.py', 'backend/src/api/schemas/news.py', 'backend/src/api/schemas/news_report.py', 'backend/src/api/schemas/report_archive.py', 'backend/src/api/schemas/stock_resolve.py', 'backend/src/api/schemas/technical_report.py', 'backend/src/api/services/auth_service.py', 'backend/src/api/services/corp_code_sync_service.py', 'backend/src/api/services/dart_corp_code_parser.py', 'backend/src/api/services/flow_report_service.py', 'backend/src/api/services/fundamental_report_service.py', 'backend/src/api/services/importance.py', 'backend/src/api/services/industry_report_service.py', 'backend/src/api/services/news_cleanup_service.py', 'backend/src/api/services/news_graph_query_service.py', 'backend/src/api/services/news_query_service.py', 'backend/src/api/services/news_report_service.py', 'backend/src/api/services/news_service.py', 'backend/src/api/services/stock_master_parser.py', 'backend/src/api/services/stock_resolver_service.py', 'backend/src/api/services/stock_sync_service.py', 'backend/src/api/services/technical_report_service.py', 'backend/src/api/text_normalize.py', 'ai/src/agents/flow/schemas.py', 'ai/src/agents/flow/export/to_json.py'])
EXTRA = {"backend/tests/fixtures/kis_master.py", "backend/tests/fixtures/dart_corp_code.py","backend/tests/db_safety.py", "backend/tests/fixtures/flow_payload.py",
         "backend/tests/fixtures/ai_output.py", "backend/tests/conftest.py",
         "backend/tests/flow_integration/conftest.py", "backend/tests/unit/conftest.py",
         "backend/scripts/seed_stocks.py", "backend/scripts/seed_stock_aliases.py",
         "backend/scripts/seed_representative_stocks.py", "backend/scripts/export_news_graph.py",
         "backend/scripts/export_industry_graph.py", "ai/src/supervisor/config.py",
         "ai/src/agents/news/config.py", "ai/src/agents/fundamental/core/config.py"}
MODES = ("self-test", "unit")


class UnsafeCheck(RuntimeError):
    pass


def identity(path):
    s = path.lstat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns


def private_path(relative):
    blocked = {"private", "secret", "secrets", "key", "keys", "credential", "credentials", "dump", "dumps", "backup", "backups", "log", "logs"}
    return any(part.lower() in blocked or part.lower().startswith((".env", "credentials"))
               or any(mark in part.lower().split(".")[1:] for mark in ("key", "pem", "p12", "sql", "dump", "bak", "backup", "log")) for part in Path(relative).parts)


def regular_bytes(root, relative):
    """Check names/components before open; reject symlinks, hardlinks and races."""
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts or private_path(relative):
        raise UnsafeCheck("source path escape")
    forbidden = {".key", ".pem", ".p12", ".sql", ".log", ".backup", ".dump"}
    if any(p.startswith(".env") or p.lower().startswith("credentials") for p in relative.parts) or relative.suffix.lower() in forbidden:
        raise UnsafeCheck("private input name rejected before open")
    components = [root.joinpath(*relative.parts[:n]) for n in range(1, len(relative.parts)+1)]
    before = [identity(p) for p in components]
    if any(p.is_symlink() for p in components):
        raise UnsafeCheck("source symlink rejected")
    path = root / relative
    meta = path.lstat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
        raise UnsafeCheck("source metadata rejected before open")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as source:
        s = os.fstat(source.fileno())
        if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or (s.st_dev, s.st_ino) != before[-1][:2]:
            raise UnsafeCheck("source is not a unique regular file")
        data = source.read()
        if identity(path) != (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns):
            raise UnsafeCheck("source changed during read")
    if [identity(p) for p in components] != before:
        raise UnsafeCheck("source component changed during read")
    return data


class OwnedRoot:
    def __init__(self, parent="/tmp"):
        self.path = Path(tempfile.mkdtemp(prefix="st001-3b-", dir=parent)).resolve()
        self.path.chmod(0o700)
        self.inode = identity(self.path)[:2]
        self.parent = identity(self.path.parent)[:2]
        self.nonce = secrets.token_hex(24)
        (self.path / ".owner").write_text(self.nonce)

    def close(self):
        if (self.path.is_symlink() or identity(self.path)[:2] != self.inode
                or identity(self.path.parent)[:2] != self.parent
                or (self.path / ".owner").is_symlink()
                or (self.path / ".owner").read_text() != self.nonce):
            raise UnsafeCheck("cleanup ownership mismatch; resource retained")
        shutil.rmtree(self.path)
        if self.path.exists():
            raise UnsafeCheck("owned root cleanup incomplete")


def clean_env(root):
    return {"LANG": "en_US.UTF-8", "TZ": "UTC", "HOME": str(root),
            "TMPDIR": str(root), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def group_is_alive(child):
    try:
        os.killpg(child.pid, 0)
        return True
    except ProcessLookupError:
        return False


def run_child(argv, root, timeout, registry=None, group_alive=group_is_alive, native=False):
    """Track before unmasking signals; confirm group absence before root removal."""
    registry = set() if registry is None else registry
    with tempfile.TemporaryFile(dir=root) as output, tempfile.TemporaryFile(dir=root) as errors:
        child = None
        try:
            previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM, signal.SIGALRM})
            try:
                child = subprocess.Popen(argv, cwd=root, env=clean_env(root), start_new_session=True,
                                         stdin=subprocess.DEVNULL, stdout=output, stderr=errors if native else output)
                registry.add(child)
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, previous)
            deadline = time.monotonic() + timeout
            while child.poll() is None:
                if time.monotonic() >= deadline or output.tell() + errors.tell() > 2_000_000:
                    raise UnsafeCheck("child timeout or output limit")
                time.sleep(0.05)
            if output.tell() + errors.tell() > 2_000_000:
                raise UnsafeCheck("child output limit")
            output.seek(0)
            if native:
                errors.seek(0)
                return {"status": child.returncode, "signal": child.returncode < 0,
                        "stdout": output.read(2_000_000).decode(errors="replace"),
                        "stderr": errors.read(2_000_000).decode(errors="replace")}
            return child.returncode, output.read(2_000_000).decode(errors="replace")
        finally:
            if child is not None:
                if child.poll() is None:
                    if os.getpgid(child.pid) != child.pid:
                        raise UnsafeCheck("child process group identity mismatch")
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=3)
                if child.poll() is not None:
                    if group_alive(child):
                        raise UnsafeCheck("descendant group remains; receipt/root retained")
                    registry.discard(child)


def validate_dependency(path):
    canonical = path.resolve(strict=True)
    s = canonical.stat()
    if s.st_uid not in {0, os.getuid()} or s.st_mode & 0o022:
        raise UnsafeCheck("untrusted interpreter/dependency metadata")
    return canonical


def sandbox_profile(root, runtime, site, executable):
    # Explicit source copy only. No original repository/home read grant.
    def q(p): return json.dumps(str(p))
    reads = ["/System", "/usr/lib", "/private/var/db/dyld", runtime, site, root]
    return "\n".join([
        "(version 1)", "(deny default)", '(allow file-read* file-test-existence (literal "/"))', "(allow file-read-metadata)",
        "(allow sysctl-read)", "(allow mach-lookup)", "(allow process-fork)",
        f"(allow process-exec (literal {q(executable)}) (literal \"/bin/cat\") (literal \"/usr/bin/true\"))",
        "(allow file-read-data " + " ".join(f"(subpath {q(p)})" for p in reads)
        + ' (literal "/dev/null") (literal "/dev/urandom") (literal "/bin/cat") (literal "/usr/bin/true"))',
        f"(allow file-write* (subpath {q(root)}) (literal \"/dev/null\"))",
    ]) + "\n"


def valid_native_probe(stage, result, denied_path):
    if result.get("signal") or type(result.get("status")) is not int or result["status"] < 0:
        return False
    if stage in {"true", "allowed"}:
        expected = "" if stage == "true" else "SYNTHETIC-ALLOWED\n"
        return result["status"] == 0 and result.get("stdout") == expected and result.get("stderr") == ""
    expected_errors = {f"cat: {denied_path}: Operation not permitted\n", f"cat: {denied_path}: Permission denied\n"}
    return stage == "denied" and result["status"] == 1 and result.get("stdout") == "" and result.get("stderr") in expected_errors


def verify_native_sequence(stages, execute, denied_path):
    for stage, command in stages:
        result = execute(command)
        if not valid_native_probe(stage, result, denied_path):
            raise UnsafeCheck(f"OS canary {stage} failed (exit {result['status']}); no pytest/app worker started")


def prove_os_boundary(owned, executable, profile, registry):
    """true -> allowed native cat -> denied native cat; any earlier failure stops."""
    inside = owned.path / "inside-canary"
    inside.write_text("SYNTHETIC-ALLOWED\n")
    policy = owned.path / "policy.sb"
    policy.write_text(profile)
    fd, name = tempfile.mkstemp(prefix="st001-denied-", dir="/tmp")
    outside = Path(name).resolve()
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(b"SYNTHETIC-DENIED\n")
        stages = [("true", ["/usr/bin/true"]), ("allowed", ["/bin/cat", str(inside)]), ("denied", ["/bin/cat", str(outside)])]
        verify_native_sequence(stages, lambda command: run_child(
            ["/usr/bin/sandbox-exec", "-f", str(policy), *command], owned.path, 10, registry, native=True), str(outside))
    finally:
        outside.unlink()
        inside.unlink()
    return policy


def source_allowed(p):
    return p not in REMOVED_SOURCES and not private_path(p) and (p in EXTRA or p in FLOW_INPUTS or p in CF004_INPUTS or p in CF005_INPUTS or p in NEW
        or p in {"backend/"+u for u in UNIT}
        or p.startswith(("backend/src/", "backend/db/")) and p.endswith(".py")
        or p.startswith("backend/tests/") and p.endswith("/__init__.py"))


CF015_TESTS=("tests/unit/test_cf015_fundamental_analysis.py",)
CF015_INPUTS = {'ai/src/agents/fundamental/api/routes.py': 'fa8c60528abd98c16b83f9a30ad9a30f60ab5ee9848d8c0397904822e052b5f9', 'ai/src/agents/fundamental/api/analysis_schemas.py': '26e950f3dee2774db6c9d7dd02b49e7fb7c9cc59940559b6202fecd3609a8b8a', 'ai/src/agents/fundamental/api/execution.py': '198dc9cedf3b7fff2310ace28fa3cfad3a25507f15d5e083b9872f8081251475', 'ai/src/agents/fundamental/domain/contracts.py': 'acaa069f119dc88cc466d771c27ca6ca8ff498ab827ea7d6a3cedc9a39dc6f1c', 'ai/src/shared/runtime/deadline.py': '4a51cd138da3a37d158e03019e4b38c203bd276948a21987b0d07d35a68cb60e', 'ai/src/agents/flow/api/http.py': 'dc1c4c5fa28aec3ea8e7bb7813c61fbb107f2c5d5a6e53d7ff4d72d99d46bfb8', 'ai/src/agents/flow/api/schemas.py': 'cccacc7290ada82b5344b716f8c671907ffd4d9ad076d91dc0c444730139fb5d', 'ai/src/agents/flow/application/execution_runtime.py': '55e018f7b348a312d3eadb11eccdb281b7e2598a4eb286e0ff677588a0d7f524', 'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894', 'ai/src/agents/flow/domain/observation_window.py': 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27', 'ai/src/agents/flow/infrastructure/token_cache.py': '3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f', 'ai/src/agents/flow/domain/interpretation_claims.py': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22', 'ai/src/agents/flow/domain/verification/consecutive.py': '35c8e994f01aa8447b117c0ef9a4746fe66f8b4687091bfa2d042eb3eab2bede'}
CF015_SOURCES = frozenset({'backend/src/modules/flow/application/analysis_profile.py', 'backend/src/modules/fundamental/application/analysis_profile.py', 'backend/db/models/registry.py', 'backend/src/modules/fundamental/api/router.py', 'backend/db/migrations/versions/20261109_c15001a7e0001_fundamental_owned_analysis.py', 'backend/scripts/check_safe.py', 'backend/src/api/main.py', 'backend/src/shared/http/access_boundary.py', 'backend/tests/unit/test_flow_contract.py', 'backend/src/modules/analysis/application/ports.py', 'backend/src/shared/config.py', 'backend/src/modules/flow/application/analysis_service.py', 'backend/scripts/cf015_fundamental_check.py', 'backend/src/modules/fundamental/infrastructure/analysis_repository.py', 'backend/src/modules/fundamental/application/analysis_service.py', 'backend/src/modules/fundamental/infrastructure/report_repository.py', 'backend/scripts/cf002_interactive_login.py', 'backend/tests/safe_checks/test_entry.py', 'backend/db/models/common/agent_report.py', 'backend/db/models/fundamental/analysis_run.py', 'backend/src/modules/fundamental/api/analysis_schemas.py', 'backend/src/modules/fundamental/api/analysis_router.py', 'backend/src/shared/infrastructure/clients/ai_client.py', 'backend/src/modules/fundamental/domain/analysis.py', 'backend/tests/unit/test_cf015_fundamental_analysis.py', 'backend/tests/unit/test_cf013_analysis_contracts.py', 'backend/src/modules/analysis/application/coordinator.py', 'backend/src/modules/fundamental/application/report_service.py', 'backend/tests/unit/test_cf012_flow_analysis.py', 'backend/db/models/fundamental/fundamental_report.py', 'backend/src/modules/fundamental/application/analysis_adapter.py'})
NEW.update(CF015_INPUTS)
NEW.update(CF015_SOURCES)


CF017_TESTS = ("tests/unit/test_cf017_flow_error_classification.py",)
CF017_INPUTS = {'ai/src/agents/flow/api/http.py': 'dc1c4c5fa28aec3ea8e7bb7813c61fbb107f2c5d5a6e53d7ff4d72d99d46bfb8', 'ai/src/agents/flow/api/schemas.py': 'cccacc7290ada82b5344b716f8c671907ffd4d9ad076d91dc0c444730139fb5d', 'ai/src/agents/flow/application/execution_runtime.py': '55e018f7b348a312d3eadb11eccdb281b7e2598a4eb286e0ff677588a0d7f524', 'ai/src/shared/runtime/deadline.py': '4a51cd138da3a37d158e03019e4b38c203bd276948a21987b0d07d35a68cb60e', 'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894', 'ai/src/agents/flow/domain/observation_window.py': 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27', 'ai/src/agents/flow/infrastructure/token_cache.py': '3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f', 'ai/src/agents/flow/domain/interpretation_claims.py': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22', 'ai/src/agents/flow/domain/verification/consecutive.py': '35c8e994f01aa8447b117c0ef9a4746fe66f8b4687091bfa2d042eb3eab2bede', 'ai/src/agents/flow/infrastructure/kis_client.py': '7c0166467ae61ea20e9f3d6a5c4ca48e2b06edaac6479f18526c41e5b39318f1', 'ai/src/agents/flow/infrastructure/llm/explain.py': '14bb4cba44295fe577ec019ca0b8994a712e1c03e44d1fadf8aabb840653c10b'}
NEW.update(CF017_INPUTS)
NEW.add("backend/"+CF017_TESTS[0])


CF018_TESTS=("tests/unit/test_cf018_flow_usage_limits.py",)
CF018_INPUTS={'ai/src/agents/flow/api/http.py': 'dc1c4c5fa28aec3ea8e7bb7813c61fbb107f2c5d5a6e53d7ff4d72d99d46bfb8', 'ai/src/agents/flow/api/schemas.py': 'cccacc7290ada82b5344b716f8c671907ffd4d9ad076d91dc0c444730139fb5d', 'ai/src/agents/flow/application/execution_runtime.py': '55e018f7b348a312d3eadb11eccdb281b7e2598a4eb286e0ff677588a0d7f524', 'ai/src/shared/runtime/deadline.py': '4a51cd138da3a37d158e03019e4b38c203bd276948a21987b0d07d35a68cb60e', 'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894', 'ai/src/agents/flow/domain/observation_window.py': 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27', 'ai/src/agents/flow/infrastructure/token_cache.py': '3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f', 'ai/src/agents/flow/domain/interpretation_claims.py': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22', 'ai/src/agents/flow/domain/verification/consecutive.py': '35c8e994f01aa8447b117c0ef9a4746fe66f8b4687091bfa2d042eb3eab2bede', 'ai/src/agents/flow/infrastructure/kis_client.py': '7c0166467ae61ea20e9f3d6a5c4ca48e2b06edaac6479f18526c41e5b39318f1', 'ai/src/agents/flow/infrastructure/llm/explain.py': '14bb4cba44295fe577ec019ca0b8994a712e1c03e44d1fadf8aabb840653c10b'}
CF018_SOURCES=frozenset(['backend/db/models/common/analysis_usage.py', 'backend/db/migrations/versions/20261109_c18001a7e0001_flow_usage_limits.py', 'backend/src/modules/analysis/domain/usage.py', 'backend/src/modules/analysis/application/usage_service.py', 'backend/src/modules/analysis/infrastructure/usage_repository.py', 'backend/scripts/cf018_usage_check.py', 'backend/tests/unit/test_cf018_flow_usage_limits.py'])
NEW.update(CF018_INPUTS)
NEW.update(CF018_SOURCES)


CF019_TESTS=('tests/unit/test_cf019_flow_display_quality.py',)
CF019_INPUTS={'ai/src/agents/flow/domain/verification/consecutive.py': '35c8e994f01aa8447b117c0ef9a4746fe66f8b4687091bfa2d042eb3eab2bede', 'ai/src/agents/flow/domain/interpretation_claims.py': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22', 'ai/src/agents/flow/domain/verification/signals.py': '3f4e26fabbb2b64163bb1f8c0a77665316cd61a70d9eb1458d201f6395f57aaa', 'ai/src/agents/flow/domain/verification/interpretation.py': '863adcb582b601eacadb3fe894e92d9669670fbfd6c5f712841a64ba1bcfdd60', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894', 'ai/src/agents/flow/application/workflow.py': '03816e283c8f5ba0718738b4b71b79fc48d82f0240159fc23d0bc5259838809b', 'ai/src/agents/flow/infrastructure/llm/explain.py': '14bb4cba44295fe577ec019ca0b8994a712e1c03e44d1fadf8aabb840653c10b', 'ai/src/agents/flow/prompts/explain.txt': '9e8a04b6d7d0f534d54552e78ed489cb74f3cc7160fbd379b030758ae891406c', 'ai/src/agents/flow/api/schemas.py': 'cccacc7290ada82b5344b716f8c671907ffd4d9ad076d91dc0c444730139fb5d', 'ai/src/agents/flow/application/execution_runtime.py': '55e018f7b348a312d3eadb11eccdb281b7e2598a4eb286e0ff677588a0d7f524', 'ai/src/agents/flow/domain/observation_window.py': 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27', 'ai/src/agents/flow/domain/signals.py': '15de1236f86a78a14e5d5106247d0329167e12eb390b29ebf97cd5cd012ae2be', 'ai/src/agents/flow/config.py': '91c95356110d0294051eb7871bfb06100ebd003ccb0f2da33c6add2b0594b637', 'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/infrastructure/token_cache.py': '3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f', 'ai/src/agents/flow/infrastructure/render/builder.py': '4d3bf9c9bed2cbe9bf438f3314517f5dd27b917961f4be48b0eb105bd8369a7e', 'ai/src/agents/flow/infrastructure/render/templates/supply_demand.html': 'ddff99c015a419e488689b3d1a7906b83fe228149d29b1f2be8d0cd77ed8aa2f'}
CF019_SOURCES=frozenset({'backend/tests/unit/test_cf019_flow_display_quality.py','backend/tests/unit/test_cf014_flow_quality.py','frontend/tests/fixtures/cf019-flow-display-cases.json'})
NEW.update(CF019_INPUTS)
NEW.update(CF019_SOURCES)


CF020_TESTS=('tests/unit/test_cf020_supervisor_flow.py',)
CF020_INPUTS={'ai/src/agents/flow/api/http.py': 'dc1c4c5fa28aec3ea8e7bb7813c61fbb107f2c5d5a6e53d7ff4d72d99d46bfb8', 'ai/src/agents/flow/api/schemas.py': 'cccacc7290ada82b5344b716f8c671907ffd4d9ad076d91dc0c444730139fb5d', 'ai/src/agents/flow/application/execution_runtime.py': '55e018f7b348a312d3eadb11eccdb281b7e2598a4eb286e0ff677588a0d7f524', 'ai/src/shared/runtime/deadline.py': '4a51cd138da3a37d158e03019e4b38c203bd276948a21987b0d07d35a68cb60e', 'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894', 'ai/src/agents/flow/domain/observation_window.py': 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27', 'ai/src/agents/flow/infrastructure/token_cache.py': '3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f', 'ai/src/agents/flow/domain/interpretation_claims.py': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22', 'ai/src/agents/flow/domain/verification/consecutive.py': '35c8e994f01aa8447b117c0ef9a4746fe66f8b4687091bfa2d042eb3eab2bede', 'ai/src/agents/flow/infrastructure/kis_client.py': '7c0166467ae61ea20e9f3d6a5c4ca48e2b06edaac6479f18526c41e5b39318f1', 'ai/src/agents/flow/infrastructure/llm/explain.py': '14bb4cba44295fe577ec019ca0b8994a712e1c03e44d1fadf8aabb840653c10b', 'ai/src/supervisor/config.py': 'a05bdb4bd3874dd1849557581050aee8096a224519a56a670a00f9f14ac6ad88', 'ai/src/supervisor/api/routes.py': 'bf66c4e3f64c1587a0c76089907694753f243e56d56ad96fdb498dfab40e7bfd', 'ai/src/supervisor/application/runtime.py': '57254dbd09920cfa5292f84338a869cf2befa0f343fcfb0c3a1ed4a32ce56295', 'ai/src/supervisor/domain/models.py': '6555c53a388b4f38227af42f29ca43d92b2beb94170ba0592ca86d8811e9efcc', 'ai/src/supervisor/application/planning/planner.py': '309a680c29330c1686e96a6b3fefb51b4eb7ff3ea9f46906a6c41c30440921ae', 'ai/src/supervisor/application/execution/executor.py': '1d318cd58c8163484210b51755b06dfb7f1cefba68e6eddd58ba56d9b0c0f9a6', 'ai/src/supervisor/application/execution/adapters.py': '729bf74708c0fc16227989aa1de729066fbbd8d67118832bffd5b459eb683658', 'ai/src/supervisor/infrastructure/backend/resolve_client.py': 'd336434fe37c739e2290fd2f1931dee506c7c7d2ade764d017027d1f835662f9', 'ai/src/supervisor/domain/planning/interpret.py': '8898f9593d5db83cce7fec3e2cdae77cb66b53ff7735fc90047f23d8e8a0e7c0', 'ai/src/supervisor/domain/planning/policy.py': '57814eee7920dbadc78a57e77f9b46efd6389d64a3989f10eb69056b45894028'}
CF020_SOURCES=frozenset(['backend/src/modules/flow/api/query_plan_schemas.py', 'backend/src/modules/flow/api/query_plan_router.py', 'backend/src/modules/flow/application/query_plan_service.py', 'backend/src/modules/flow/domain/query_plan.py', 'backend/tests/unit/test_cf020_supervisor_flow.py', 'backend/scripts/cf020_supervisor_check.py'])
NEW.update(CF020_INPUTS)
NEW.update(CF020_SOURCES)


CF022_TESTS=("tests/unit/test_cf022_supervisor_core.py",)
CF022_INPUTS={'ai/src/agents/flow/api/http.py': 'dc1c4c5fa28aec3ea8e7bb7813c61fbb107f2c5d5a6e53d7ff4d72d99d46bfb8', 'ai/src/agents/flow/api/schemas.py': 'cccacc7290ada82b5344b716f8c671907ffd4d9ad076d91dc0c444730139fb5d', 'ai/src/agents/flow/application/execution_runtime.py': '55e018f7b348a312d3eadb11eccdb281b7e2598a4eb286e0ff677588a0d7f524', 'ai/src/shared/runtime/deadline.py': '4a51cd138da3a37d158e03019e4b38c203bd276948a21987b0d07d35a68cb60e', 'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894', 'ai/src/agents/flow/domain/observation_window.py': 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27', 'ai/src/agents/flow/infrastructure/token_cache.py': '3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f', 'ai/src/agents/flow/domain/interpretation_claims.py': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22', 'ai/src/agents/flow/domain/verification/consecutive.py': '35c8e994f01aa8447b117c0ef9a4746fe66f8b4687091bfa2d042eb3eab2bede', 'ai/src/agents/flow/infrastructure/kis_client.py': '7c0166467ae61ea20e9f3d6a5c4ca48e2b06edaac6479f18526c41e5b39318f1', 'ai/src/agents/flow/infrastructure/llm/explain.py': '14bb4cba44295fe577ec019ca0b8994a712e1c03e44d1fadf8aabb840653c10b', 'ai/src/supervisor/config.py': 'a05bdb4bd3874dd1849557581050aee8096a224519a56a670a00f9f14ac6ad88', 'ai/src/supervisor/api/routes.py': 'bf66c4e3f64c1587a0c76089907694753f243e56d56ad96fdb498dfab40e7bfd', 'ai/src/supervisor/application/runtime.py': '57254dbd09920cfa5292f84338a869cf2befa0f343fcfb0c3a1ed4a32ce56295', 'ai/src/supervisor/domain/models.py': '6555c53a388b4f38227af42f29ca43d92b2beb94170ba0592ca86d8811e9efcc', 'ai/src/supervisor/application/planning/planner.py': '309a680c29330c1686e96a6b3fefb51b4eb7ff3ea9f46906a6c41c30440921ae', 'ai/src/supervisor/application/execution/executor.py': '1d318cd58c8163484210b51755b06dfb7f1cefba68e6eddd58ba56d9b0c0f9a6', 'ai/src/supervisor/application/execution/adapters.py': '729bf74708c0fc16227989aa1de729066fbbd8d67118832bffd5b459eb683658', 'ai/src/supervisor/infrastructure/backend/resolve_client.py': 'd336434fe37c739e2290fd2f1931dee506c7c7d2ade764d017027d1f835662f9', 'ai/src/supervisor/domain/planning/interpret.py': '8898f9593d5db83cce7fec3e2cdae77cb66b53ff7735fc90047f23d8e8a0e7c0', 'ai/src/supervisor/domain/planning/policy.py': '57814eee7920dbadc78a57e77f9b46efd6389d64a3989f10eb69056b45894028', 'ai/src/supervisor/domain/meaning.py': '7161404a27d08f49518b394708044a2c59fb12b4d21e6337bc61255dcfaca9ea', 'ai/src/supervisor/domain/core_contracts.py': '9791f5ee0e7dba21c543b3ca63d25c1c1d339dade26a512fbec9b706aed63561', 'ai/src/supervisor/domain/capabilities.py': '178520b67bc06b648679036438f631d43050350ea602c1293a7206059ed1e3a2', 'ai/src/supervisor/application/meaning_service.py': '6d3927cf6f34cadfcdb39190d083c790790d058281a996544bbb9f92fcb57843', 'ai/src/supervisor/infrastructure/meaning_gateway.py': '90f2b859dbf8ec31d3b3b894d5d649b3cee211baac66314aa9e2676501b83e04', 'ai/src/supervisor/application/planning/core_planner.py': 'dc6bfffe0f8c81ebd928aa4f5dc5a56c5fafa1f4adb25f8b780e07a5c695595d'}
CF022_SOURCES=frozenset(['backend/src/modules/supervisor/domain/contracts.py', 'backend/src/modules/supervisor/api/schemas.py', 'backend/src/modules/supervisor/api/router.py', 'backend/src/modules/supervisor/application/service.py', 'backend/src/modules/supervisor/domain/flow_projection.py', 'backend/src/modules/supervisor/infrastructure/repository.py', 'backend/db/models/supervisor/request_binding.py', 'backend/db/models/registry.py', 'backend/db/migrations/versions/20261109_c22001a7e0001_supervisor_binding.py', 'backend/src/modules/flow/application/report_service.py', 'backend/src/shared/infrastructure/clients/ai_client.py', 'backend/src/shared/http/access_boundary.py', 'backend/src/api/main.py', 'backend/tests/unit/test_cf022_supervisor_core.py', 'backend/scripts/check_safe.py', 'backend/tests/safe_checks/test_entry.py', 'backend/tests/unit/test_flow_contract.py', 'backend/scripts/cf022_supervisor_core_check.py', 'backend/scripts/cf002_interactive_login.py', 'backend/docs/schema.md'])
CF022_FIXTURE="frontend/tests/fixtures/cf022-supervisor-core.json"
CF054_INPUTS={'ai/src/supervisor/domain/technical_core_contracts.py': '010190d11576f2611db2f0ba5a7e89a54e9a3921ce159b465a1f9653920da614', 'ai/src/supervisor/application/planning/technical_core.py': 'af0893259e93afc07de06d0da24fdcaf97e010157891691abb0abb02ce8eaf10', 'ai/src/supervisor/application/meaning_policy.py': 'f31ba42680ed4f6223fd215321cb427679d710e1456cc95d6b9a862e78b282b5', 'ai/src/supervisor/domain/meaning_proposals.py': 'e10ab671eab3a7071d8c00de31611242c1f6a6d369db5bacf2ad05bbdf54de94'}
CF054_INPUTS['ai/src/main.py']='48816ec096df577df65fe4485c1f0fede9d1486044092a8f2b36ca016c0e2fe1'
CF022_INPUTS.update(CF054_INPUTS)
CF022_SOURCES = CF022_SOURCES | frozenset(['backend/src/modules/supervisor/domain/technical_core_contracts.py', 'backend/src/modules/supervisor/domain/technical_projection.py', 'backend/src/modules/supervisor/application/technical_service.py', 'backend/db/migrations/versions/20261112_c54001a7e0001_supervisor_technical_handoff.py'])
# Fixed composition observation only; no extra source tree or runtime authority.
CF022_SOURCES = CF022_SOURCES | frozenset({
    'backend/src/modules/supervisor/domain/composition.py',
    'backend/src/modules/supervisor/application/composition_service.py',
    'backend/src/modules/supervisor/application/composition_runtime.py',
    'backend/src/modules/supervisor/infrastructure/composition_repository.py',
    'backend/db/models/supervisor/composition.py',
    'backend/db/migrations/versions/20261113_c60001_supervisor_composition.py',
    'backend/db/migrations/versions/20261113_c61001_supervisor_composition_projection.py',
})
NEW.update(CF022_INPUTS)
NEW.update(CF022_SOURCES)
NEW.add(CF022_FIXTURE)

CF023_TESTS=("tests/unit/test_cf023_supervisor_meaning.py",)
CF023_INPUTS={'ai/src/agents/flow/api/http.py': 'dc1c4c5fa28aec3ea8e7bb7813c61fbb107f2c5d5a6e53d7ff4d72d99d46bfb8', 'ai/src/agents/flow/api/schemas.py': 'cccacc7290ada82b5344b716f8c671907ffd4d9ad076d91dc0c444730139fb5d', 'ai/src/agents/flow/application/execution_runtime.py': '55e018f7b348a312d3eadb11eccdb281b7e2598a4eb286e0ff677588a0d7f524', 'ai/src/shared/runtime/deadline.py': '4a51cd138da3a37d158e03019e4b38c203bd276948a21987b0d07d35a68cb60e', 'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894', 'ai/src/agents/flow/domain/observation_window.py': 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27', 'ai/src/agents/flow/infrastructure/token_cache.py': '3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f', 'ai/src/agents/flow/domain/interpretation_claims.py': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22', 'ai/src/agents/flow/domain/verification/consecutive.py': '35c8e994f01aa8447b117c0ef9a4746fe66f8b4687091bfa2d042eb3eab2bede', 'ai/src/agents/flow/infrastructure/kis_client.py': '7c0166467ae61ea20e9f3d6a5c4ca48e2b06edaac6479f18526c41e5b39318f1', 'ai/src/agents/flow/infrastructure/llm/explain.py': '14bb4cba44295fe577ec019ca0b8994a712e1c03e44d1fadf8aabb840653c10b', 'ai/src/supervisor/config.py': 'a05bdb4bd3874dd1849557581050aee8096a224519a56a670a00f9f14ac6ad88', 'ai/src/supervisor/api/routes.py': 'bf66c4e3f64c1587a0c76089907694753f243e56d56ad96fdb498dfab40e7bfd', 'ai/src/supervisor/application/runtime.py': '57254dbd09920cfa5292f84338a869cf2befa0f343fcfb0c3a1ed4a32ce56295', 'ai/src/supervisor/domain/models.py': '6555c53a388b4f38227af42f29ca43d92b2beb94170ba0592ca86d8811e9efcc', 'ai/src/supervisor/application/planning/planner.py': '309a680c29330c1686e96a6b3fefb51b4eb7ff3ea9f46906a6c41c30440921ae', 'ai/src/supervisor/application/execution/executor.py': '1d318cd58c8163484210b51755b06dfb7f1cefba68e6eddd58ba56d9b0c0f9a6', 'ai/src/supervisor/application/execution/adapters.py': '729bf74708c0fc16227989aa1de729066fbbd8d67118832bffd5b459eb683658', 'ai/src/supervisor/infrastructure/backend/resolve_client.py': 'd336434fe37c739e2290fd2f1931dee506c7c7d2ade764d017027d1f835662f9', 'ai/src/supervisor/domain/planning/interpret.py': '8898f9593d5db83cce7fec3e2cdae77cb66b53ff7735fc90047f23d8e8a0e7c0', 'ai/src/supervisor/domain/planning/policy.py': '57814eee7920dbadc78a57e77f9b46efd6389d64a3989f10eb69056b45894028', 'ai/src/supervisor/domain/meaning.py': '7161404a27d08f49518b394708044a2c59fb12b4d21e6337bc61255dcfaca9ea', 'ai/src/supervisor/domain/core_contracts.py': '9791f5ee0e7dba21c543b3ca63d25c1c1d339dade26a512fbec9b706aed63561', 'ai/src/supervisor/domain/capabilities.py': '178520b67bc06b648679036438f631d43050350ea602c1293a7206059ed1e3a2', 'ai/src/supervisor/application/meaning_service.py': '6d3927cf6f34cadfcdb39190d083c790790d058281a996544bbb9f92fcb57843', 'ai/src/supervisor/infrastructure/meaning_gateway.py': '90f2b859dbf8ec31d3b3b894d5d649b3cee211baac66314aa9e2676501b83e04', 'ai/src/supervisor/application/planning/core_planner.py': 'dc6bfffe0f8c81ebd928aa4f5dc5a56c5fafa1f4adb25f8b780e07a5c695595d', 'ai/src/supervisor/domain/meaning_proposals.py': 'e10ab671eab3a7071d8c00de31611242c1f6a6d369db5bacf2ad05bbdf54de94', 'ai/src/supervisor/application/meaning_policy.py': 'f31ba42680ed4f6223fd215321cb427679d710e1456cc95d6b9a862e78b282b5', 'ai/src/supervisor/infrastructure/openai_meaning_gateway.py': 'a62df0a79e63584ce46378145fb3af4be77df15e0cad9de568cc0e9ab44966c6', 'ai/src/supervisor/prompts/meaning.txt': 'cb9c7cb759cffc1dd626680b93e66b6dbb27cd6734f65e4394fe5bf41f147d35'}
CF023_SOURCES=frozenset(['backend/src/modules/supervisor/domain/contracts.py', 'backend/src/modules/supervisor/application/service.py', 'backend/src/modules/supervisor/application/preparation_service.py', 'backend/src/modules/supervisor/infrastructure/repository.py', 'backend/src/modules/supervisor/infrastructure/preparation_repository.py', 'backend/src/modules/supervisor/api/schemas.py', 'backend/src/modules/supervisor/api/router.py', 'backend/db/models/supervisor/preparation.py', 'backend/db/models/supervisor/request_binding.py', 'backend/db/models/registry.py', 'backend/db/migrations/versions/20261110_c23001a7e0001_supervisor_meaning.py', 'backend/src/modules/flow/application/report_service.py', 'backend/src/shared/infrastructure/clients/ai_client.py', 'backend/src/shared/http/access_boundary.py', 'backend/tests/unit/test_cf023_supervisor_meaning.py', 'backend/scripts/check_safe.py', 'backend/tests/safe_checks/test_entry.py', 'backend/tests/unit/test_flow_contract.py', 'backend/scripts/cf023_supervisor_meaning_check.py', 'backend/scripts/cf002_interactive_login.py', 'backend/docs/schema.md'])
CF044_SOURCES=frozenset(['backend/db/models/supervisor/meaning_accounting.py', 'backend/db/migrations/versions/20261111_c44001a7e0001_supervisor_accounting.py', 'backend/src/modules/supervisor/domain/meaning_accounting.py', 'backend/src/modules/supervisor/infrastructure/meaning_accounting_repository.py', 'backend/src/modules/supervisor/application/meaning_accounting_service.py'])
CF023_SOURCES = CF023_SOURCES | CF044_SOURCES
CF045_INPUTS={'ai/src/supervisor/application/meaning_gateway_factory.py': 'cf0559833386db4cf9081a9c6d23a2d02f56cdc292f4002acbc483f4b02d0978', 'ai/src/supervisor/infrastructure/backend/meaning_budget_client.py': '593fb7f497725f26f6fcc40592d9e13f3afae9e7c0f7b6c98ad8ed1d4824783a', 'ai/src/main.py': '48816ec096df577df65fe4485c1f0fede9d1486044092a8f2b36ca016c0e2fe1'}
CF045_INPUTS['ai/src/supervisor/api/flow_app.py']='89ec533b6a02f9b3e2a3d202847beb53967e71fca42b72eb0be72d894f0180ad'
CF045_SOURCES=frozenset(['backend/src/modules/supervisor/api/meaning_phase_router.py', 'backend/db/migrations/versions/20261112_c45001a7e0001_supervisor_meaning_phase.py'])
CF023_SOURCES=CF023_SOURCES|CF045_SOURCES
NEW.update(CF045_INPUTS)
CF023_FIXTURE="frontend/tests/fixtures/cf023-supervisor-meaning.json"
CF023_INPUTS.update(CF054_INPUTS)
NEW.update(CF023_INPUTS)
NEW.update(CF023_SOURCES)
NEW.add(CF023_FIXTURE)

CF026_TESTS=("tests/unit/test_cf026_supervisor_live_controller.py",)
NEW.update({"backend/scripts/cf026_supervisor_live_controller.py", "backend/scripts/cf026_successor.py", "backend/tests/unit/test_cf026_supervisor_live_controller.py"})

CF024_TESTS=("tests/unit/test_cf024_supervisor_live_verifier.py",)
CF047_INPUTS = {
    "backend/scripts/google_login_bootstrap.py": "5937d610c482b1a5e92671b7bad8f496f4c0e292a8d451fc34347381df7df48c",
    "backend/scripts/google_login_inputs.py": "4fddb30281357a58b259872bf6cc87542fb41c65928357aab045134d8f155c95",
}
NEW.update(CF047_INPUTS)
NEW.add("backend/tests/unit/test_cf024_supervisor_live_verifier.py")

CF021_TESTS=("tests/unit/test_cf021_technical_boundary.py",)
CF021_INPUTS={'ai/src/agents/flow/api/http.py': 'dc1c4c5fa28aec3ea8e7bb7813c61fbb107f2c5d5a6e53d7ff4d72d99d46bfb8', 'ai/src/agents/flow/api/schemas.py': 'cccacc7290ada82b5344b716f8c671907ffd4d9ad076d91dc0c444730139fb5d', 'ai/src/agents/flow/application/execution_runtime.py': '55e018f7b348a312d3eadb11eccdb281b7e2598a4eb286e0ff677588a0d7f524', 'ai/src/shared/runtime/deadline.py': '4a51cd138da3a37d158e03019e4b38c203bd276948a21987b0d07d35a68cb60e', 'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894', 'ai/src/agents/flow/domain/observation_window.py': 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27', 'ai/src/agents/flow/infrastructure/token_cache.py': '3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f', 'ai/src/agents/flow/domain/interpretation_claims.py': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22', 'ai/src/agents/flow/domain/verification/consecutive.py': '35c8e994f01aa8447b117c0ef9a4746fe66f8b4687091bfa2d042eb3eab2bede', 'ai/src/agents/flow/infrastructure/kis_client.py': '7c0166467ae61ea20e9f3d6a5c4ca48e2b06edaac6479f18526c41e5b39318f1', 'ai/src/agents/flow/infrastructure/llm/explain.py': '14bb4cba44295fe577ec019ca0b8994a712e1c03e44d1fadf8aabb840653c10b', 'ai/src/agents/technical/domain/models/contracts.py': '6af8c7a005d5e128b2b2ec970c3bc6c4a1e4259e776b722422ac4b18f1fe082e', 'ai/src/agents/technical/domain/models/enums.py': 'af39859eacb6c0fb072f93877cced625f556db4060073e9cb869bc8ffb9c067f', 'ai/src/agents/technical/domain/models/chart.py': 'b95d11ae145edade454926590d0c16b44e7eb75631daac24307e2bf0cc3c9de8', 'ai/src/agents/technical/domain/models/intraday.py': 'd8d3af1ad8931046674d6263e399e40502dee4b394898f059fe3f039ed2cb9d0', 'ai/src/agents/technical/domain/models/ohlcv.py': '49fa1e171f9a20d2b76dc278cd90b580add1913d3ec4031d9caef5fb807282e7', 'ai/src/shared/contracts/agent_envelope.py': '94da2a6d4b68c29e7bd53c2ddf4e3b253a4592757e956e2239933ab232e31cd1', 'ai/src/agents/technical/domain/boundary_contracts.py': 'd5d3c1a428c836ace202cb8079ddc3e10b70125a7d3c2be6ef88fd0d37ff9ac4', 'ai/src/agents/technical/application/boundary_adapter.py': '03c811be7c5e61a9b0e73868ab2940f2003f82687e1b3dfd5156ce74655f9978', 'ai/src/agents/technical/application/boundary_runtime.py': 'baef46a6db3a4fd0e501e4da42ce1e137915a87cf88510987215ef59c9026d0b', 'ai/src/agents/technical/api/routes.py': 'deb797f25f6768b56265761958d4b83b0340b354edd78860f0961b5b910af418', 'ai/src/supervisor/application/planning/technical_boundary.py': 'de27e70200f6b76e17deb11642030770bf54fe4bfa51537e39ee03b96221bbd7', 'ai/src/supervisor/domain/planning/interpret.py': '8898f9593d5db83cce7fec3e2cdae77cb66b53ff7735fc90047f23d8e8a0e7c0', 'ai/src/agents/technical/application/agent.py': '45b4dc24f4e16ded311b9a630d4a21f78d3670ba622193a0048f63db63c4b830', 'ai/src/agents/technical/application/orchestration/technical_graph.py': '3047284aef93af07a6d4135900c6c6a0b70a73fe2623f996241935379b10fe19', 'ai/src/agents/technical/domain/intraday_limits.py': '27499058b141918eb8560b0f3eb6ecdc7839124f66160cf8f4ca06d53e374ff7', 'ai/src/agents/technical/config.py': '3a5f9d96f49d12d8d8db6898fcffda4f63fcec3a7b167ba72eea174f08522c49', 'ai/src/agents/technical/application/engine_bridge.py': '7a9caee1ae8c076c5adace793574b6f46b2cb09b030bd99caf2f6c864ed9de17'}
CF021_FIXED_INPUTS={'backend/src/modules/analysis/domain/contracts.py': 'dda0c043d02abb352f07a9947dbec006484f76f64e0260ea3360b4cecb567f2c', 'backend/src/modules/analysis/domain/agent_envelope.py': '94da2a6d4b68c29e7bd53c2ddf4e3b253a4592757e956e2239933ab232e31cd1', 'backend/src/modules/technical/domain/execution_boundary.py': 'b6d1ddb07a102be59f21f107bcbb4ff0d90a13b8e1790f40030424a5e4f70094', 'backend/src/modules/technical/domain/chart_contracts.py': 'bf0f12025a8ae69764e7f584a734705d0352ed906702ce83ef3599f45d09b96a', 'backend/src/modules/technical/application/boundary_adapter.py': 'ed78c0d4d96424fc87ba69e2f1eecbeca32cbff3e67ceead1cc8dbcc3fd8506b', 'backend/src/shared/infrastructure/clients/ai_client.py': 'a8081b4a85015f9f6bbe63aa0ad8ca7e502a8176a28472b170acf7de2ab990f2', 'frontend/src/features/technical/model/types.ts': '8d7cd828b1423731d30408611ae184bc174db202859e8fba203ef8bef7678459', 'frontend/src/features/technical/lib/chart.ts': 'a1817e28ec601fbbce46e90e434361e505fd414e278bb35fc90880c8cf6ee1dc', 'frontend/tests/fixtures/cf021-technical-boundary.json': 'c092c4dd80ce19945a2affb3e71bdbb6d6efa418729b8f98fe32c05b32e37665'}
NEW.update(CF021_INPUTS)
NEW.update(CF021_FIXED_INPUTS)
NEW.add("backend/tests/unit/test_cf021_technical_boundary.py")

CF031_TESTS=("tests/unit/test_cf031_technical_boundary_restore.py",)
CF031_INPUTS={'backend/src/modules/technical/application/boundary_restore.py': 'd81fb317f6c05ec37fa2284bac6c03aef85acce5d2d2087ab7f0146cdf89f491', 'frontend/tests/fixtures/cf031-technical-boundary-read.json': '46380ea4c998e3130cf1c447c278b93ed32288c42af9d62f84b90b7acabce5e0'}
NEW.update(CF031_INPUTS)
NEW.add("backend/"+CF031_TESTS[0])


CF035_COMPAT = {'ai/src/agents/flow/domain/observation_window.py': 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27', 'ai/src/agents/flow/domain/verification/consecutive.py': '35c8e994f01aa8447b117c0ef9a4746fe66f8b4687091bfa2d042eb3eab2bede', 'ai/src/agents/flow/domain/interpretation_claims.py': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894', 'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/infrastructure/token_cache.py': '3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f'}
NEW.update(CF035_COMPAT)
CF035_TESTS = ("tests/unit/test_cf035_technical_owned_storage.py",)
CF035_INPUTS = {'backend/src/modules/analysis/domain/contracts.py': 'dda0c043d02abb352f07a9947dbec006484f76f64e0260ea3360b4cecb567f2c', 'backend/src/modules/analysis/domain/agent_envelope.py': '94da2a6d4b68c29e7bd53c2ddf4e3b253a4592757e956e2239933ab232e31cd1', 'backend/src/modules/technical/domain/execution_boundary.py': 'b6d1ddb07a102be59f21f107bcbb4ff0d90a13b8e1790f40030424a5e4f70094', 'backend/src/modules/technical/domain/chart_contracts.py': 'bf0f12025a8ae69764e7f584a734705d0352ed906702ce83ef3599f45d09b96a', 'backend/src/modules/technical/domain/ai_output.py': '642693c6a6b75d7c5cf435560b7a0444048ef2993238c43f5d84c7ee5247849a', 'backend/src/modules/technical/application/boundary_adapter.py': 'ed78c0d4d96424fc87ba69e2f1eecbeca32cbff3e67ceead1cc8dbcc3fd8506b', 'backend/src/modules/technical/application/boundary_restore.py': 'd81fb317f6c05ec37fa2284bac6c03aef85acce5d2d2087ab7f0146cdf89f491', 'backend/src/modules/auth/application/session_service.py': 'b49082e0371a8880b1a3b2fb396035f4ca688693abf8bb2db90f3c8e8c2066f8', 'backend/db/models/auth/models.py': '905a0ad647f3a4680bef4e75f73aa0f089e0fd1947bfd0a99a2830c0ccb45f5e', 'backend/db/models/common/stock.py': 'f3f384af671a91a1726a7af60f482f7dc879229b5e71b4cd9e37edc1da576c5b', 'backend/db/models/technical/report_signal.py': '284062f38906967273ec9ba850bd9f647e6d117da8339c95e20f7d428a2c857f', 'backend/db/models/technical/report_chart.py': 'be61fd905fec956e69b82ade82c602b78fa61323b43f6e66f78f13f3b55bde9d', 'backend/db/models/technical/report_risk_note.py': '03b9019b4a77c6f221b94770b4d5107bc350ece7b2b0acf31eb18667747b5fb4', 'backend/db/models/technical/report_interpretation.py': '5028db7261d90f0a4368d74707ed280e88252232452ebf68cf33b57877c1e6a0', 'backend/db/models/technical/report_verification.py': '421d78e9a5cf861f03dc2593a16871ac34492735a706a99688ff95b8567adcb9', 'frontend/tests/fixtures/cf031-technical-boundary-read.json': '46380ea4c998e3130cf1c447c278b93ed32288c42af9d62f84b90b7acabce5e0'}
CF035_SOURCES = frozenset(['backend/db/models/technical/report_snapshot.py', 'backend/db/migrations/versions/20261111_c35001a7e0001_technical_owned_snapshot.py', 'backend/src/modules/technical/application/owned_report_service.py', 'backend/tests/unit/test_cf035_technical_owned_storage.py', 'backend/scripts/cf035_technical_owned_check.py'])
NEW.update(CF035_INPUTS)
NEW.update(CF035_SOURCES)

CF036_INPUTS = {'backend/src/modules/technical/api/owned_report_router.py': 'f78d43811d296a26211ad08a12a3cfc3d79b6e660dbb6f41b109eea1473eb343', 'backend/src/modules/technical/api/owned_report_schemas.py': '2a803cee4d21a9fb4c4abb2f708867a9346143f604a8a9f5faf743db376c65fe', 'backend/src/modules/technical/application/owned_report_service.py': 'a9a23012d1a9ef7b084580f62c9a19d11a6055460b723a840ce1bf25145ef202', 'backend/src/modules/technical/infrastructure/report_repository.py': 'd2312a4319795d0b1caeca94ef2d078f6607648dbd29ebb32d61c47f6e153e91', 'backend/src/shared/http/access_boundary.py': '6f10e26bb56c0a1fee2982ccd7bbed756a254bdab67029f747d86366f5d7d527', 'backend/src/api/main.py': '08d1b6709178145262d1ab9adfdd916fce5137ac02190a511159afd50e58cf4d', 'frontend/tests/fixtures/cf036-technical-owned-read.json': '897571692f0ed1838c4583e990dc48ab2359bd34684b06bc2c2eb5d0afa11fff'}
CF036_TESTS = ("tests/unit/test_cf036_technical_owned_read.py",)
CF036_SOURCES = frozenset({"backend/src/modules/technical/api/owned_report_router.py", "backend/src/modules/technical/api/owned_report_schemas.py", "backend/tests/unit/test_cf036_technical_owned_read.py", "backend/scripts/cf036_technical_owned_read_check.py", "frontend/tests/fixtures/cf036-technical-owned-read.json"})
NEW.update(CF036_SOURCES)

CF040_TESTS = ("tests/unit/test_cf040_technical_runtime_setup.py",)
CF040_COMPAT = dict(CF035_COMPAT)
CF040_INPUTS = {'ai/src/agents/technical/config.py': '3a5f9d96f49d12d8d8db6898fcffda4f63fcec3a7b167ba72eea174f08522c49', 'ai/src/api/dependencies.py': '5ffaa8909eee2cd3fe4f512cc839b7ba206d4fb27d314fe58b9cab31ab0f0dab', 'ai/src/agents/technical/domain/intraday_limits.py': '27499058b141918eb8560b0f3eb6ecdc7839124f66160cf8f4ca06d53e374ff7', 'ai/src/shared/runtime/deadline.py': '4a51cd138da3a37d158e03019e4b38c203bd276948a21987b0d07d35a68cb60e'}
CF040_SOURCES = frozenset({"backend/tests/unit/test_cf040_technical_runtime_setup.py", "backend/scripts/check_safe.py", "backend/tests/safe_checks/test_entry.py"})
CF040_INPUTS['ai/src/agents/technical/infrastructure/openai_llm_client.py']='b66e2d3a9c5474eb01f4645ea89f7dabd653f42d86e4b3e9e7e0ccab154bde8a'
# Explicit KIS injection: copied AST only, no module/env/network initialization.
CF040_INPUTS['ai/src/agents/technical/infrastructure/kis_client.py']='d64aaa35c4e6394b25a9bc25c0f3b2ade552e11221dc3b9bb717e27c3ffabc1c'
NEW.update(CF040_INPUTS)
NEW.update(CF040_SOURCES)

GRAPH_INPUTS = {'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/domain/interpretation_claims.py': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22', 'ai/src/agents/flow/domain/models.py': '41377f16336cc0401c82d390cde04727cc8aa2e53f6d114b025aa62d0de4f894', 'ai/src/agents/flow/domain/observation_window.py': 'acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27', 'ai/src/agents/flow/domain/verification/consecutive.py': '35c8e994f01aa8447b117c0ef9a4746fe66f8b4687091bfa2d042eb3eab2bede', 'ai/src/agents/flow/infrastructure/token_cache.py': '3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f', 'ai/src/agents/technical/api/charts/chart_builder.py': 'de537398f09a0bf11e80daa5f4a6cb431e16817d9820ce4987d134abece58774', 'ai/src/agents/technical/api/charts/intraday_chart_builder.py': '0d1df60612caddad72dba1fc9221e73c0e6e9274b9a5faeb5478cee9e433470e', 'ai/src/agents/technical/api/charts/intraday_context_builder.py': 'edb602b3d1ea962346f0ef0de9288dc7945b7f6c8a26442162da4a62348939ff', 'ai/src/agents/technical/application/agent.py': '45b4dc24f4e16ded311b9a630d4a21f78d3670ba622193a0048f63db63c4b830', 'ai/src/agents/technical/application/boundary_adapter.py': '03c811be7c5e61a9b0e73868ab2940f2003f82687e1b3dfd5156ce74655f9978', 'ai/src/agents/technical/application/boundary_runtime.py': 'baef46a6db3a4fd0e501e4da42ce1e137915a87cf88510987215ef59c9026d0b', 'ai/src/agents/technical/application/engine_bridge.py': '7a9caee1ae8c076c5adace793574b6f46b2cb09b030bd99caf2f6c864ed9de17', 'ai/src/agents/technical/application/nodes/chart_generate.py': '7789b6457adc81df2476c0202cd6bd50b7614203b45480336e1910c850c4ed92', 'ai/src/agents/technical/application/nodes/confidence_calculate.py': '3fb9ac05cf96cb2d0709b030c600a28d048c5a30d8c79125317d522ad58122b4', 'ai/src/agents/technical/application/nodes/data_collect.py': '8b70bc21ca4e780f0ff08c48a8b160e297bb6367bedb9be77604e21ed8440285', 'ai/src/agents/technical/application/nodes/focus_analysis.py': '0a455b0b0eab8790bf1106fb5f0d1772ef87ecc64862c813bb0887217436cfda', 'ai/src/agents/technical/application/nodes/indicator_calculate.py': '0fb4fe92da279e0d12bf73ff9bbe0f16bce014d5fe0eda50b0feacf9a1b6ecfd', 'ai/src/agents/technical/application/nodes/interpret_report.py': 'a7631c110faddead635b59698a35800b7c4964c0ffc86e54712b48623e651551', 'ai/src/agents/technical/application/nodes/normalize_question.py': '7d3bb4e9ecf0b47af9130b9707a31282e1e3a7f7f4f22e313780b59000dec327', 'ai/src/agents/technical/application/nodes/regime_classify.py': 'f0ed63dc764938f0a82d7f5e82348c630d005efb09d4141e3c464659f2c7039e', 'ai/src/agents/technical/application/nodes/risk_detect.py': '080487940e76f6a271ba3b3e6ed3aa35e3b4f100a30f584fbb4f40bfabf992ad', 'ai/src/agents/technical/application/nodes/signal_aggregate.py': 'e4eb3be5b2ca45aaa413b4382bacaa8469292cafe69da1af3bfc6164d9694386', 'ai/src/agents/technical/application/orchestration/langgraph_state.py': '67911bd88d95db720b7fec6650781c0c1e86c9c5938e09e855020383e21dab23', 'ai/src/agents/technical/application/orchestration/pipeline_steps.py': '1f3188b1e1e55ec9959da0483b352fcdbf431be87fab7f2cde86166d8ffb9630', 'ai/src/agents/technical/application/orchestration/technical_graph.py': '3047284aef93af07a6d4135900c6c6a0b70a73fe2623f996241935379b10fe19', 'ai/src/agents/technical/application/orchestration/technical_supervisor.py': 'bf2444eb48921ebec6da007b0f11a0e38f5752e8adefb08013a687497fe5a74c', 'ai/src/agents/technical/config.py': '3a5f9d96f49d12d8d8db6898fcffda4f63fcec3a7b167ba72eea174f08522c49', 'ai/src/agents/technical/domain/boundary_contracts.py': 'd5d3c1a428c836ace202cb8079ddc3e10b70125a7d3c2be6ef88fd0d37ff9ac4', 'ai/src/agents/technical/domain/indicators/moving_average.py': 'ba15898a8eb4e0f8e5fb74fe9fe074b215bfb0df0359f2d97af81044bdde0776', 'ai/src/agents/technical/domain/indicators/pattern.py': '514b95483e3202ece76e9772f71b201d20298bf0e7d065af48b8d992effe0e48', 'ai/src/agents/technical/domain/indicators/rsi.py': '1bbd24049c645bbdfbc8552b6ea2669c98056f2736b2e85fa2efdb61375c31e7', 'ai/src/agents/technical/domain/indicators/support_resistance.py': '9885cf9f66def8291cbc3cd856875795be11fc4c82af9a6395f42c77d8aba362', 'ai/src/agents/technical/domain/indicators/volume.py': 'ccc52611b6af78da6e89361457dfa6861d877a398d0b7737657adb622ac43d85', 'ai/src/agents/technical/domain/interpretation/keyword_rules.py': '16d563a3eb8a4fa1deb31cd6ac11b93f742571355d574011f960a8fba41b7671', 'ai/src/agents/technical/domain/interpretation/numeric_claims.py': 'a6d34dd122fa3efbace2c3646b806c79dcb43d1204f7fb5228110c56c5dde81f', 'ai/src/agents/technical/domain/interpretation/trajectory_eval.py': '6fcc13642c342f6a7330267ba6c7112d465ab6cb90dd8acfa5b0ebfeec72a49f', 'ai/src/agents/technical/domain/intraday_limits.py': '27499058b141918eb8560b0f3eb6ecdc7839124f66160cf8f4ca06d53e374ff7', 'ai/src/agents/technical/domain/models/chart.py': 'b95d11ae145edade454926590d0c16b44e7eb75631daac24307e2bf0cc3c9de8', 'ai/src/agents/technical/domain/models/contracts.py': '6af8c7a005d5e128b2b2ec970c3bc6c4a1e4259e776b722422ac4b18f1fe082e', 'ai/src/agents/technical/domain/models/enums.py': 'af39859eacb6c0fb072f93877cced625f556db4060073e9cb869bc8ffb9c067f', 'ai/src/agents/technical/domain/models/intraday.py': 'd8d3af1ad8931046674d6263e399e40502dee4b394898f059fe3f039ed2cb9d0', 'ai/src/agents/technical/domain/models/ohlcv.py': '49fa1e171f9a20d2b76dc278cd90b580add1913d3ec4031d9caef5fb807282e7', 'ai/src/agents/technical/domain/regime/multiframe.py': '131db385cf57290292fe51a1fb16e67e51a4d298a387f4a62220a28e997e0e05', 'ai/src/agents/technical/domain/regime/rules.py': '7765f0b2c432f4e399d5f2261311aafc29655f4bdf78fb41d8c9b5a47e30ae29', 'ai/src/agents/technical/domain/synthesis/confidence.py': '7a96e68f37c970ae753c0acd9d2086988cb0d059a78f6c9cd75da475d9845292', 'ai/src/agents/technical/domain/synthesis/intraday_adjustment.py': 'f4b21781f80b6a0f2398cb55fbaf719084003b5154c852852355596fd54afc3c', 'ai/src/agents/technical/domain/synthesis/intraday_alignment.py': '2af3efd0581e7d45882d472b50290fdca667d29c824450a462e49ac75bf47dbf', 'ai/src/agents/technical/domain/synthesis/risk.py': 'b0926e708d18584e525b44e6fa49e667634beb53fb64b28429206633da69ea2e', 'ai/src/agents/technical/domain/synthesis/signal_score.py': '18f5fd41307f78a1405795faab81d92a73f5ba7bb2f9cf76717f7d39e9e8479f', 'ai/src/agents/technical/infrastructure/cache_service.py': '10e29c5fac7e96cfa74052c9f51d43c32efbd982ac0cc216b7b9627d1a220a88', 'ai/src/agents/technical/infrastructure/kis_client.py': 'd64aaa35c4e6394b25a9bc25c0f3b2ade552e11221dc3b9bb717e27c3ffabc1c', 'ai/src/agents/technical/infrastructure/llm/utils.py': '8c70956d1a0ad02ace4be595e40224e181501e912717f6f36fd0a694ba6da7e5', 'ai/src/agents/technical/infrastructure/observability/trace_logger.py': '6bbd1f792911500434f8345ef6f7c351cac953a044fe43dab53a4fcbd1049680', 'ai/src/agents/technical/prompts/focus_analysis.md': '5e8da23b15c4ba797424932fd0a5543287dbc0e0eb782ca1373fbd1c8144480d', 'ai/src/agents/technical/prompts/interpret_report.md': '3d37f6f36ba23540c00002892e5ee1f12808543b087a8cb39e41ed1ab4c67ed6', 'ai/src/agents/technical/prompts/normalize_question.md': '1b3016f33f52aa6d69535d4f3f958b56a48eb807f935f14bcba30c357483228e', 'ai/src/agents/technical/prompts/regenerate_report.md': '4d898399fad39d753b1894ec9ffe2760209713b65866e7054624167264bb8bda', 'ai/src/shared/contracts/agent_envelope.py': '94da2a6d4b68c29e7bd53c2ddf4e3b253a4592757e956e2239933ab232e31cd1', 'ai/src/shared/runtime/deadline.py': '4a51cd138da3a37d158e03019e4b38c203bd276948a21987b0d07d35a68cb60e', 'ai/src/supervisor/application/planning/technical_boundary.py': 'de27e70200f6b76e17deb11642030770bf54fe4bfa51537e39ee03b96221bbd7', 'ai/src/supervisor/domain/planning/interpret.py': '8898f9593d5db83cce7fec3e2cdae77cb66b53ff7735fc90047f23d8e8a0e7c0', 'ai/tests/technical/test_technical_langgraph.py': '4272164dec440585abd731e95cac8558addff5828cc67e6ae60c6d4c72ca1165', 'ai/tests/technical/test_technical_supervisor.py': 'efc112659c7ee27a02e9a4f3c1e1408ea26c252973ba6ae7e1c6d5e5eb4e5de3', 'ai/uv.lock': '2e6cb9e9254209103e03f01df043baf5273f2bd62a0c72eb139606aeda372e59'}
GRAPH_TESTS = ("tests/unit/test_technical_compiled_bridge.py",)
GRAPH_INPUTS['ai/tests/technical/test_kis_client_mapping.py']='a002f419762f2ff6711da52d2925e24137a8674c1a722f04a17bab2c0cb610ad'
GRAPH_SOURCES = frozenset({"backend/scripts/check_safe.py", "backend/scripts/safe_checks_bootstrap.py", "backend/tests/safe_checks/test_entry.py", "backend/tests/unit/conftest.py", "backend/tests/unit/test_technical_compiled_bridge.py"})

GRAPH_SOURCES = GRAPH_SOURCES | frozenset({"backend/tests/unit/test_cf040_technical_runtime_setup.py"})
GRAPH_DISTRIBUTIONS = {'annotated-doc': '0.0.4', 'annotated-types': '0.7.0', 'anyio': '4.14.1', 'certifi': '2026.6.17', 'charset-normalizer': '3.4.7', 'click': '8.4.2', 'distro': '1.9.0', 'fastapi': '0.139.0', 'h11': '0.16.0', 'httpcore': '1.0.9', 'httptools': '0.8.0', 'httpx': '0.28.1', 'idna': '3.18', 'iniconfig': '2.3.0', 'jinja2': '3.1.6', 'jiter': '0.16.0', 'jsonpatch': '1.33', 'jsonpointer': '3.1.1', 'langchain-core': '1.4.8', 'langchain-openai': '1.3.3', 'langchain-protocol': '0.0.18', 'langgraph': '1.2.7', 'langgraph-checkpoint': '4.1.1', 'langgraph-prebuilt': '1.1.0', 'langgraph-sdk': '0.4.2', 'langsmith': '0.9.5', 'markupsafe': '3.0.3', 'numpy': '2.5.0', 'openai': '2.44.0', 'orjson': '3.11.9', 'ormsgpack': '1.12.2', 'packaging': '26.2', 'pandas': '2.3.3', 'pluggy': '1.6.0', 'pydantic': '2.13.4', 'pydantic-core': '2.46.4', 'pydantic-settings': '2.14.2', 'pygments': '2.20.0', 'pytest': '9.1.1', 'pytest-asyncio': '1.4.0', 'python-dateutil': '2.9.0.post0', 'python-dotenv': '1.2.2', 'pytz': '2026.2', 'pyyaml': '6.0.3', 'regex': '2026.6.28', 'requests': '2.34.2', 'requests-toolbelt': '1.0.0', 'six': '1.17.0', 'sniffio': '1.3.1', 'starlette': '1.3.1', 'tenacity': '9.1.4', 'tiktoken': '0.13.0', 'tqdm': '4.68.3', 'typing-extensions': '4.16.0', 'typing-inspection': '0.4.2', 'tzdata': '2026.2', 'urllib3': '2.7.0', 'uuid-utils': '0.16.2', 'uvicorn': '0.49.0', 'uvloop': '0.22.1', 'watchfiles': '1.2.0', 'websockets': '15.0.1', 'xxhash': '3.8.0', 'zstandard': '0.25.0'}

def graph_dependency_bytes(site, relative):
    # Installed library data (including public CA bundles/bytecode) is not source
    # intake. Verify every component before opening, with no symlink fallback.
    relative=Path(relative)
    if relative.is_absolute() or '..' in relative.parts or any(p.startswith('.env') for p in relative.parts):
        raise UnsafeCheck('graph dependency path rejected')
    components=[site.joinpath(*relative.parts[:n]) for n in range(1,len(relative.parts)+1)]
    before=[identity(p) for p in components]
    for path in components:
        if path.is_symlink():raise UnsafeCheck('graph dependency symlink rejected')
        validate_dependency(path)
    path=site/relative
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
        meta=os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink!=1 or (meta.st_dev,meta.st_ino)!=before[-1][:2]:
            raise UnsafeCheck('graph dependency metadata rejected')
        value=stream.read()
    if [identity(p) for p in components]!=before:
        raise UnsafeCheck('graph dependency changed during read')
    return value


def graph_dependency_snapshot(site):
    """Verify all components BEFORE metadata reads, including executable pyc."""
    import email.parser
    paths=sorted(site.rglob('*'))
    for path in paths:
        if path.is_symlink():raise UnsafeCheck('graph dependency symlink rejected')
        validate_dependency(path)
    files=[p for p in paths if p.is_file()]
    result={}
    distributions={}
    for path in files:
        relative=path.relative_to(site).as_posix()
        value=graph_dependency_bytes(site,relative)
        result[relative]=hashlib.sha256(value).hexdigest()
        if path.name=='METADATA' and path.parent.name.endswith('.dist-info'):
            fields=email.parser.Parser().parsestr(value.decode('utf-8'))
            distributions[fields['Name'].lower().replace('_','-')]=fields['Version']
    if distributions!=GRAPH_DISTRIBUTIONS or not result:
        raise UnsafeCheck('reviewed graph dependency versions differ')
    return result


CF048_SOURCES = frozenset({
    "backend/db/models/technical/execution_admission.py",
    "backend/db/models/registry.py",
    "backend/db/migrations/versions/20261112_c48001a7e0001_technical_execution_admission.py",
    "backend/db/migrations/versions/20261112_c50001a7e0001_technical_result_completion.py",
    "backend/src/modules/technical/domain/execution_admission.py",
    "backend/src/modules/technical/infrastructure/execution_admission_repository.py",
    "backend/src/modules/technical/application/execution_admission_service.py",
    "backend/src/modules/technical/infrastructure/execution_completion_repository.py",
    "backend/src/modules/technical/application/execution_completion.py",
    "backend/src/modules/technical/application/execution_runtime.py",
    "backend/tests/unit/test_cf048_technical_admission.py",
    "backend/scripts/cf035_technical_owned_check.py",
    ".github/workflows/pr-ci.yml",
})
CF048_TESTS = ("tests/unit/test_cf048_technical_admission.py",)
CF048_INPUTS = {p:CF035_INPUTS[p] for p in (
    "backend/src/modules/auth/application/session_service.py",
    "backend/db/models/auth/models.py", "backend/db/models/common/stock.py",
    "frontend/tests/fixtures/cf031-technical-boundary-read.json")}
CF048_COMPAT = dict(CF035_COMPAT)  # Existing worker Flow-origin sentinel, six pure files.
NEW.update(CF048_SOURCES)


CF053_INPUTS = {'ai/src/agents/technical/api/routes.py': 'deb797f25f6768b56265761958d4b83b0340b354edd78860f0961b5b910af418', 'ai/src/agents/technical/application/boundary_adapter.py': '03c811be7c5e61a9b0e73868ab2940f2003f82687e1b3dfd5156ce74655f9978', 'ai/src/agents/technical/application/boundary_runtime.py': 'baef46a6db3a4fd0e501e4da42ce1e137915a87cf88510987215ef59c9026d0b', 'ai/src/agents/technical/application/engine_bridge.py': '7a9caee1ae8c076c5adace793574b6f46b2cb09b030bd99caf2f6c864ed9de17', 'ai/src/agents/technical/application/execution_runtime.py': '2a51a70ed368fddeb9f1162d9a27cc0bd3a0b08cbc09885db156b0f252eb2990', 'ai/src/agents/technical/config.py': '3a5f9d96f49d12d8d8db6898fcffda4f63fcec3a7b167ba72eea174f08522c49', 'ai/src/agents/technical/domain/boundary_contracts.py': 'd5d3c1a428c836ace202cb8079ddc3e10b70125a7d3c2be6ef88fd0d37ff9ac4', 'ai/src/agents/technical/domain/execution_contracts.py': '7673ca1af2f5cba30390e3a0eb15f2878dafd61f52cd9a96c33728fe2fad2e6c', 'ai/src/agents/technical/domain/intraday_limits.py': '27499058b141918eb8560b0f3eb6ecdc7839124f66160cf8f4ca06d53e374ff7', 'ai/src/agents/technical/domain/models/chart.py': 'b95d11ae145edade454926590d0c16b44e7eb75631daac24307e2bf0cc3c9de8', 'ai/src/agents/technical/domain/models/contracts.py': '6af8c7a005d5e128b2b2ec970c3bc6c4a1e4259e776b722422ac4b18f1fe082e', 'ai/src/agents/technical/domain/models/enums.py': 'af39859eacb6c0fb072f93877cced625f556db4060073e9cb869bc8ffb9c067f', 'ai/src/agents/technical/domain/models/intraday.py': 'd8d3af1ad8931046674d6263e399e40502dee4b394898f059fe3f039ed2cb9d0', 'ai/src/agents/technical/domain/models/ohlcv.py': '49fa1e171f9a20d2b76dc278cd90b580add1913d3ec4031d9caef5fb807282e7', 'ai/src/agents/technical/infrastructure/execution_authority_client.py': '03c22133dd6707bfa163ebd9a473f55b90d86cb2e8c1f104c9bf5847a13d68b3', 'ai/src/agents/technical/infrastructure/openai_llm_client.py': 'b66e2d3a9c5474eb01f4645ea89f7dabd653f42d86e4b3e9e7e0ccab154bde8a', 'ai/src/api/dependencies.py': '5ffaa8909eee2cd3fe4f512cc839b7ba206d4fb27d314fe58b9cab31ab0f0dab', 'ai/src/shared/contracts/agent_envelope.py': '94da2a6d4b68c29e7bd53c2ddf4e3b253a4592757e956e2239933ab232e31cd1', 'ai/src/shared/runtime/deadline.py': '4a51cd138da3a37d158e03019e4b38c203bd276948a21987b0d07d35a68cb60e', 'ai/src/supervisor/application/planning/technical_boundary.py': 'de27e70200f6b76e17deb11642030770bf54fe4bfa51537e39ee03b96221bbd7', 'ai/src/supervisor/domain/planning/interpret.py': '8898f9593d5db83cce7fec3e2cdae77cb66b53ff7735fc90047f23d8e8a0e7c0'}
CF048_SOURCES = CF048_SOURCES | frozenset(['backend/db/migrations/versions/20261112_c53001a7e0001_technical_provider_execution.py', 'backend/src/modules/technical/api/execution_authority_router.py', 'backend/src/modules/technical/application/execution_authority_service.py', 'backend/src/modules/technical/domain/provider_execution.py', 'backend/src/modules/technical/infrastructure/execution_authority_repository.py'])
CF053_INPUTS.update(CF054_INPUTS)
CF053_INPUTS.update({p:CF022_INPUTS[p] for p in ('ai/src/supervisor/domain/meaning.py','ai/src/supervisor/domain/core_contracts.py','ai/src/supervisor/api/routes.py')})
NEW.update(CF053_INPUTS)
NEW.update(CF048_SOURCES)
GRAPH_INPUTS.update({p:v for p,v in CF053_INPUTS.items() if p.startswith("ai/")})
# Existing graph collector reuses CF040's copied AST fixtures, never KIS module import.
GRAPH_INPUTS['ai/src/agents/technical/infrastructure/kis_client.py']=CF040_INPUTS['ai/src/agents/technical/infrastructure/kis_client.py']


def selected_sources(repo, *, quality_only=False, fundamental_only=False, flow_errors_only=False, usage_only=False, display_only=False, supervisor_only=False, core_only=False, meaning_only=False, assembly_only=False, controller_only=False, technical_boundary_only=False, technical_read_only=False, technical_owned_only=False, technical_owned_read_only=False, technical_runtime_only=False, technical_graph_only=False, technical_admission_only=False):
    if technical_graph_only:
        return sorted(set(GRAPH_INPUTS) | GRAPH_SOURCES)
    raw = subprocess.check_output(["/usr/bin/git", "ls-files", "--stage", "-z"], cwd=repo,
                                  env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"})
    selected = set()
    for record in raw.decode().split("\0"):
        if not record: continue
        metadata, p = record.split("\t", 1)
        mode, _, stage = metadata.split()
        if source_allowed(p):
            if mode != "100644" or stage != "0": raise UnsafeCheck("unsupported source index metadata")
            selected.add(p)
    required = EXTRA | FLOW_INPUTS.keys() | CF004_INPUTS.keys() | CF005_INPUTS.keys() | {"backend/"+u for u in UNIT}
    if not required <= selected | NEW: raise UnsafeCheck("required selected source missing from index or exact new inputs")
    result = selected | NEW
    if not controller_only:
        result.discard("backend/scripts/cf026_successor.py")
    if quality_only:
        result = {p for p in result if not p.startswith("ai/") or p in CF014_INPUTS or p in CF014_COMPAT}
    if fundamental_only:
        result={p for p in result if not p.startswith("ai/") or p in CF015_INPUTS}
    if flow_errors_only:
        result={p for p in result if not p.startswith("ai/") or p in CF017_INPUTS}
    if usage_only:
        result={p for p in result if not p.startswith("ai/") or p in CF018_INPUTS}
    if display_only:
        result={p for p in result if not p.startswith("ai/") or p in CF019_INPUTS}
    if supervisor_only:
        result={p for p in result if not p.startswith("ai/") or p in CF020_INPUTS}
    if core_only:result={p for p in result if not p.startswith("ai/") or p in CF022_INPUTS}
    if meaning_only or assembly_only or controller_only:result={p for p in result if not p.startswith("ai/") or p in CF023_INPUTS or p in CF045_INPUTS}
    if technical_boundary_only or technical_read_only:
        result={p for p in result if (not p.startswith("ai/") or p in CF021_INPUTS) and (not p.startswith("frontend/") or p in CF021_FIXED_INPUTS or technical_read_only and p in CF031_INPUTS)}
    if technical_owned_only or technical_owned_read_only:
        result = {p for p in result if not p.startswith(('ai/', 'frontend/')) or p in CF035_INPUTS or p in CF035_COMPAT or technical_owned_read_only and p in CF036_SOURCES}
        result.discard('backend/scripts/cf026_supervisor_live_controller.py')
        result.discard('backend/tests/unit/test_cf026_supervisor_live_controller.py')
    if technical_admission_only:
        result = {p for p in result if not p.startswith(('ai/', 'frontend/')) or p in CF048_COMPAT or p in CF048_INPUTS or p in CF053_INPUTS}
        result.discard('backend/scripts/cf026_supervisor_live_controller.py')
        result.discard('backend/tests/unit/test_cf026_supervisor_live_controller.py')
    if technical_runtime_only:
        result = {p for p in result if not p.startswith(('ai/', 'frontend/')) or p in CF040_INPUTS or p in CF040_COMPAT or p in CF053_INPUTS}
        result.discard('backend/scripts/cf026_supervisor_live_controller.py')
        result.discard('backend/tests/unit/test_cf026_supervisor_live_controller.py')
    return sorted(result)


def execute(repo, modes, *, analysis_only=False, owned_only=False, adapter_only=False, quality_only=False, fundamental_only=False, flow_errors_only=False, usage_only=False, display_only=False, supervisor_only=False, core_only=False, meaning_only=False, assembly_only=False, controller_only=False, technical_boundary_only=False, technical_read_only=False, technical_owned_only=False, technical_owned_read_only=False, technical_runtime_only=False, technical_graph_only=False, technical_admission_only=False):
    if not sys.flags.isolated or not sys.flags.no_site:
        raise UnsafeCheck("use the documented clean env -i Python -I -S launch")
    if set(os.environ) - {"LANG", "TZ", "LC_CTYPE", "__CF_USER_TEXT_ENCODING"}:
        raise UnsafeCheck("caller environment is not the documented empty allowlist")
    python = repo / "backend/.venv/bin/python"
    if Path(sys.executable).absolute() != python:
        raise UnsafeCheck("unexpected Python interpreter")
    executable = validate_dependency(python)
    runtime = validate_dependency(executable.parent.parent)
    site = validate_dependency(repo / f"backend/.venv/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")
    names = (("pytest", "pytest_asyncio", "pydantic_settings", "langgraph") if "unit" in modes else ("pytest", "pytest_asyncio", "pydantic_settings")) if technical_graph_only else ("pytest", "pytest_asyncio", "pydantic_settings", "asyncpg", "authlib")
    for name in names:
        if not (site / name).is_dir(): raise UnsafeCheck("required installed dependency missing")
    dependency_before = graph_dependency_snapshot(site) if technical_graph_only and "unit" in modes else None
    owned = OwnedRoot()
    old_handlers = {}
    children = set()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGALRM):
            old_handlers[sig] = signal.signal(sig, lambda *_: (_ for _ in ()).throw(UnsafeCheck("controller interrupted")))
        signal.setitimer(signal.ITIMER_REAL, 480)
        policy = prove_os_boundary(owned, executable, sandbox_profile(owned.path, runtime, site, executable), children)
        checkout = owned.path / "checkout"
        fingerprints = {}
        for p in selected_sources(repo, quality_only=quality_only, fundamental_only=fundamental_only, flow_errors_only=flow_errors_only, usage_only=usage_only, display_only=display_only, supervisor_only=supervisor_only,core_only=core_only,meaning_only=meaning_only,assembly_only=assembly_only,controller_only=controller_only,technical_boundary_only=technical_boundary_only,technical_read_only=technical_read_only,technical_owned_only=technical_owned_only,technical_owned_read_only=technical_owned_read_only,technical_runtime_only=technical_runtime_only,technical_graph_only=technical_graph_only,technical_admission_only=technical_admission_only):
            data = regular_bytes(repo, p)
            if p in (FLOW_INPUTS | CF004_INPUTS | CF005_INPUTS | CF012_INPUTS | CF014_INPUTS | CF015_INPUTS | CF017_INPUTS | CF018_INPUTS | CF019_INPUTS | CF020_INPUTS | CF022_INPUTS | CF023_INPUTS | CF021_INPUTS | CF021_FIXED_INPUTS | CF031_INPUTS | CF036_INPUTS | CF040_INPUTS | CF045_INPUTS | CF047_INPUTS | CF048_INPUTS | CF048_COMPAT | CF053_INPUTS) and hashlib.sha256(data).hexdigest() != (FLOW_INPUTS | CF004_INPUTS | CF005_INPUTS | CF012_INPUTS | CF014_INPUTS | CF015_INPUTS | CF017_INPUTS | CF018_INPUTS | CF019_INPUTS | CF020_INPUTS | CF022_INPUTS | CF023_INPUTS | CF021_INPUTS | CF021_FIXED_INPUTS | CF031_INPUTS | CF036_INPUTS | CF040_INPUTS | CF045_INPUTS | CF047_INPUTS | CF048_INPUTS | CF048_COMPAT | CF053_INPUTS)[p]:
                raise UnsafeCheck("reviewed pure Flow input changed; source review required")
            if technical_graph_only and p in GRAPH_INPUTS and hashlib.sha256(data).hexdigest() != GRAPH_INPUTS[p]:
                raise UnsafeCheck("reviewed graph source changed")
            target = checkout / p
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            fingerprints[p] = hashlib.sha256(data).hexdigest()
        for p, h in fingerprints.items():
            if hashlib.sha256(regular_bytes(repo, p)).hexdigest() != h:
                raise UnsafeCheck("source changed after copy")
        (owned.path / "source-hashes.json").write_text(json.dumps(fingerprints))
        for mode in modes:
            cap = {"root": str(owned.path), "source": str(checkout / "backend"),
                   "site": str(site), "runtime": str(runtime), "mode": mode,
                   "parent_pid": os.getpid(), "lifetime": 90 if mode == "self-test" else 300,
                   "tests": list(CF048_TESTS if technical_admission_only else GRAPH_TESTS if technical_graph_only else CF040_TESTS if technical_runtime_only else CF036_TESTS if technical_owned_read_only else CF035_TESTS if technical_owned_only else CF031_TESTS if technical_read_only else CF021_TESTS if technical_boundary_only else CF026_TESTS if controller_only else CF024_TESTS if assembly_only else CF023_TESTS if meaning_only else CF022_TESTS if core_only else CF020_TESTS if supervisor_only else CF019_TESTS if display_only else CF018_TESTS if usage_only else CF017_TESTS if flow_errors_only else CF015_TESTS if fundamental_only else CF014_TESTS if quality_only else CF013_TESTS if adapter_only else OWNED_TESTS if owned_only else CF012_TESTS if analysis_only else UNIT), "cf012_self_only": analysis_only, "cf013_self_only": adapter_only, "cf014_self_only": quality_only, "cf015_self_only":fundamental_only, "cf017_self_only":flow_errors_only, "cf018_self_only":usage_only, "cf019_self_only":display_only,"cf020_self_only":supervisor_only,"cf022_self_only":core_only,"cf023_self_only":meaning_only,"cf024_self_only":assembly_only,"cf026_self_only":controller_only,"cf021_self_only":technical_boundary_only,"cf031_self_only":technical_read_only,"cf035_self_only":technical_owned_only,"cf036_self_only":technical_owned_read_only,"cf040_self_only":technical_runtime_only,"technical_graph_self_only":technical_graph_only,"cf048_self_only":technical_admission_only}
            capfile = owned.path / "capability.json"
            capfile.write_text(json.dumps(cap))
            worker = checkout / "backend/scripts/safe_checks_bootstrap.py"
            status, output = run_child(["/usr/bin/sandbox-exec", "-f", str(policy), str(executable),
                                       "-I", "-S", str(worker), str(capfile)], owned.path, cap["lifetime"], children)
            print(output[-10000:], end="")
            if status: raise UnsafeCheck(f"{mode} worker failed (exit {status})")
            if dependency_before is not None and graph_dependency_snapshot(site) != dependency_before:
                raise UnsafeCheck("graph dependency changed during protected check")
            if technical_graph_only:
                for p,h in fingerprints.items():
                    if hashlib.sha256(regular_bytes(repo,p)).hexdigest() != h:
                        raise UnsafeCheck("graph source changed during protected check")
                print("Graph source pre-post provenance matched")
                if dependency_before is not None:
                    print("Graph dependency files="+str(len(dependency_before))+" snapshot_sha256="+hashlib.sha256(json.dumps(dependency_before,sort_keys=True,separators=(",",":")).encode()).hexdigest())
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig, handler in old_handlers.items(): signal.signal(sig, handler)
        if children:
            raise UnsafeCheck("child exit unconfirmed; owned root retained")
        owned.close()
        print("Owned temporary root removed; no existing resource cleanup")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("mode", nargs="?", choices=("list", *MODES, "analysis-self", "analysis-unit", "owned-unit", "adapter-self", "adapter-unit", "quality-self", "quality-unit", "fundamental-self", "fundamental-unit", "flow-errors-self", "flow-errors-unit", "usage-self", "usage-unit", "display-self", "display-unit", "supervisor-self", "supervisor-unit", "core-self", "core-unit", "meaning-self", "meaning-unit", "meaning-assembly-self", "meaning-assembly-unit", "live-controller-self", "live-controller-unit", "technical-boundary-self", "technical-boundary-unit", "technical-read-self", "technical-read-unit", "technical-owned-self", "technical-owned-unit", "technical-owned-read-self", "technical-owned-read-unit", "technical-runtime-self", "technical-runtime-unit", "technical-graph-self", "technical-graph-unit", "technical-admission-self", "technical-admission-unit"))
    values = list(sys.argv[1:] if argv is None else argv)
    if values not in [[], ["--help"], ["list"], ["self-test"], ["unit"], ["analysis-self"], ["analysis-unit"], ["owned-unit"], ["adapter-self"], ["adapter-unit"], ["quality-self"], ["quality-unit"], ["fundamental-self"], ["fundamental-unit"], ["flow-errors-self"], ["flow-errors-unit"], ["usage-self"], ["usage-unit"], ["display-self"], ["display-unit"], ["supervisor-self"], ["supervisor-unit"], ["core-self"], ["core-unit"], ["meaning-self"], ["meaning-unit"], ["meaning-assembly-self"], ["meaning-assembly-unit"], ["live-controller-self"], ["live-controller-unit"], ["technical-boundary-self"], ["technical-boundary-unit"], ["technical-read-self"], ["technical-read-unit"], ["technical-owned-self"], ["technical-owned-unit"], ["technical-owned-read-self"], ["technical-owned-read-unit"], ["technical-runtime-self"], ["technical-runtime-unit"], ["technical-graph-self"], ["technical-graph-unit"], ["technical-admission-self"], ["technical-admission-unit"]]:
        parser.error("unsupported mode or extra arguments")
    args = parser.parse_args(values)
    if args.mode == "list":
        print("self-test: synthetic guards only\nunit: fixed six complete files plus audited pure stock/technical files (no DB/external)")
        return 0
    try:
        if args.mode in {"technical-admission-self", "technical-admission-unit"}:
            execute(Path(__file__).resolve().parents[2], ("self-test" if args.mode.endswith("self") else "unit",), technical_admission_only=True)
            return 0
        if args.mode in {"technical-graph-self", "technical-graph-unit"}:
            execute(Path(__file__).resolve().parents[2], ("self-test" if args.mode.endswith("self") else "unit",), technical_graph_only=True)
            return 0
        execute(Path(__file__).resolve().parents[2], ("self-test" if args.mode in {"analysis-self","adapter-self","quality-self","fundamental-self","flow-errors-self","usage-self","display-self","supervisor-self","core-self","meaning-self","meaning-assembly-self","live-controller-self","technical-boundary-self","technical-read-self","technical-owned-self","technical-owned-read-self","technical-runtime-self"} else "unit",) if args.mode in {"analysis-self","analysis-unit","owned-unit","adapter-self","adapter-unit","quality-self","quality-unit","fundamental-self","fundamental-unit","flow-errors-self","flow-errors-unit","usage-self","usage-unit","display-self","display-unit","supervisor-self","supervisor-unit","core-self","core-unit","meaning-self","meaning-unit","meaning-assembly-self","meaning-assembly-unit","live-controller-self","live-controller-unit","technical-boundary-self","technical-boundary-unit","technical-read-self","technical-read-unit","technical-owned-self","technical-owned-unit","technical-owned-read-self","technical-owned-read-unit","technical-runtime-self","technical-runtime-unit"} else MODES if args.mode is None else (args.mode,), analysis_only=args.mode in {"analysis-self","analysis-unit"}, owned_only=args.mode=="owned-unit", adapter_only=args.mode in {"adapter-self","adapter-unit"}, quality_only=args.mode in {"quality-self","quality-unit"}, fundamental_only=args.mode in {"fundamental-self","fundamental-unit"}, flow_errors_only=args.mode in {"flow-errors-self","flow-errors-unit"}, usage_only=args.mode in {"usage-self","usage-unit"}, display_only=args.mode in {"display-self","display-unit"}, supervisor_only=args.mode in {"supervisor-self","supervisor-unit"},core_only=args.mode in {"core-self","core-unit"},meaning_only=args.mode in {"meaning-self","meaning-unit"},assembly_only=args.mode in {"meaning-assembly-self","meaning-assembly-unit"},controller_only=args.mode in {"live-controller-self","live-controller-unit"},technical_boundary_only=args.mode in {"technical-boundary-self","technical-boundary-unit"},technical_read_only=args.mode in {"technical-read-self","technical-read-unit"},technical_owned_only=args.mode in {"technical-owned-self","technical-owned-unit"},technical_owned_read_only=args.mode in {"technical-owned-read-self","technical-owned-read-unit"},technical_runtime_only=args.mode in {"technical-runtime-self","technical-runtime-unit"})
    except (UnsafeCheck, OSError, subprocess.SubprocessError) as exc:
        print(f"SAFE_CHECK_BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
