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
CF004_INPUTS = {"ai/src/agents/flow/infrastructure/token_cache.py": "3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f"}
NEW.update(CF004_INPUTS)
NEW.add("backend/tests/unit/test_cf004_kis_token_cache.py")
FLOW_INPUTS = {'ai/src/agents/flow/api/payload.py': 'e3076a97d9c4c5cc6159f0488f351b07613353dbe67371a001ff6ee995479fc2', 'ai/src/agents/flow/domain/models.py': '5d3e2c5a243a0faed6f638f2af802a138d338e5bc324ebab3b2573810162fd12'}
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
    return p not in REMOVED_SOURCES and not private_path(p) and (p in EXTRA or p in FLOW_INPUTS or p in CF004_INPUTS or p in NEW
        or p in {"backend/"+u for u in UNIT}
        or p.startswith(("backend/src/", "backend/db/")) and p.endswith(".py")
        or p.startswith("backend/tests/") and p.endswith("/__init__.py"))


def selected_sources(repo):
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
    required = EXTRA | FLOW_INPUTS.keys() | CF004_INPUTS.keys() | {"backend/"+u for u in UNIT}
    if not required <= selected | NEW: raise UnsafeCheck("required selected source missing from index or exact new inputs")
    return sorted(selected | NEW)


def execute(repo, modes):
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
    for name in ("pytest", "pytest_asyncio", "pydantic_settings", "asyncpg", "authlib"):
        if not (site / name).is_dir(): raise UnsafeCheck("required installed dependency missing")
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
        for p in selected_sources(repo):
            data = regular_bytes(repo, p)
            if p in (FLOW_INPUTS | CF004_INPUTS) and hashlib.sha256(data).hexdigest() != (FLOW_INPUTS | CF004_INPUTS)[p]:
                raise UnsafeCheck("reviewed pure Flow input changed; source review required")
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
                   "tests": list(UNIT)}
            capfile = owned.path / "capability.json"
            capfile.write_text(json.dumps(cap))
            worker = checkout / "backend/scripts/safe_checks_bootstrap.py"
            status, output = run_child(["/usr/bin/sandbox-exec", "-f", str(policy), str(executable),
                                       "-I", "-S", str(worker), str(capfile)], owned.path, cap["lifetime"], children)
            print(output[-10000:], end="")
            if status: raise UnsafeCheck(f"{mode} worker failed (exit {status})")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig, handler in old_handlers.items(): signal.signal(sig, handler)
        if children:
            raise UnsafeCheck("child exit unconfirmed; owned root retained")
        owned.close()
        print("Owned temporary root removed; no existing resource cleanup")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("mode", nargs="?", choices=("list", *MODES))
    values = list(sys.argv[1:] if argv is None else argv)
    if values not in [[], ["--help"], ["list"], ["self-test"], ["unit"]]:
        parser.error("unsupported mode or extra arguments")
    args = parser.parse_args(values)
    if args.mode == "list":
        print("self-test: synthetic guards only\nunit: fixed six complete files plus audited pure stock/technical files (no DB/external)")
        return 0
    try:
        execute(Path(__file__).resolve().parents[2], MODES if args.mode is None else (args.mode,))
    except (UnsafeCheck, OSError, subprocess.SubprocessError) as exc:
        print(f"SAFE_CHECK_BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
