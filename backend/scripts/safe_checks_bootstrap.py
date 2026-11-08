"""Fresh -I -S worker: install protection BEFORE pytest/application imports."""
from __future__ import annotations
import json
import os
from pathlib import Path
import runpy
import socket
import sys
import threading
import time

SYSTEM_METADATA = "/System/Library/CoreServices/SystemVersion.plist"


def read_allowed(path, root, site, runtime):
    return (any(path.is_relative_to(p) for p in (root, site, runtime))
            or str(path) in {"/dev/null", "/dev/urandom"}
            or sys.platform == "darwin" and str(path) == SYSTEM_METADATA)


def read_diagnostic(path, root, site, runtime):
    """Metadata only; never echo arbitrary filenames or open the denied target."""
    def label(value):
        parts = value.parts[2:] if value.parts[:2] == ("/", "private") else value.parts
        if any(p.startswith(".env") or p.lower() in {"private", "secret", "secrets", "key", "keys", "credential", "credentials"} for p in parts):
            return "private-path-redacted"
        for name, parent in (("owned", root), ("dependency", site), ("runtime", runtime)):
            if value.is_relative_to(parent): return name + ":" + value.relative_to(parent).as_posix()
        if str(value) in {"/etc/localtime", "/etc/mime.types", "/etc/termcap", SYSTEM_METADATA}: return "system:" + str(value)
        return "outside-target-redacted"
    callers = []
    frame = sys._getframe(1)
    for _ in range(8):
        if frame is None: break
        filename = frame.f_code.co_filename
        callers.append(label(Path(filename)) + ":" + str(frame.f_lineno) if Path(filename).is_absolute() else "generated-code")
        frame = frame.f_back
    return "target=" + label(path) + ";callers=" + ",".join(callers)


def install(cap):
    root = Path(cap["root"]).resolve(strict=True)
    source = Path(cap["source"]).resolve(strict=True)
    site = Path(cap["site"]).resolve(strict=True)
    runtime = Path(cap["runtime"]).resolve(strict=True)
    if not source.is_relative_to(root): raise RuntimeError("invalid source capability")
    os.environ.clear()
    os.environ.update({"LANG": "en_US.UTF-8", "TZ": "UTC", "HOME": str(root), "TMPDIR": str(root),
                       "PATH": "/usr/bin:/bin", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                       "PYTHONDONTWRITEBYTECODE": "1"})
    sys.dont_write_bytecode = True
    sys.path[:] = [str(source), str(site), *[p for p in sys.path if p and Path(p).is_relative_to(runtime)]]
    os.chdir(source)
    violations = []

    def denied(kind):
        violations.append(kind)
        raise PermissionError("safe check denied " + kind)

    def audit(event, args):
        if event == "open" and not isinstance(args[0], int):
            path = Path(os.fsdecode(args[0])).resolve()
            write = isinstance(args[1], str) and any(c in args[1] for c in "wax+")
            write = write or isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
            if any(p.startswith(".env") for p in path.parts): denied("private file")
            if write and not path.is_relative_to(root): denied("write outside owned root")
            if not read_allowed(path, root, site, runtime):
                denied("read outside capability [" + read_diagnostic(path, root, site, runtime) + "]")
        if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto", "socket.bind"}:
            denied("network/DB")
        if event in {"subprocess.Popen", "os.system", "os.exec", "os.fork", "os.posix_spawn", "pty.spawn"}:
            denied("process execution")
    sys.addaudithook(audit)

    def blocked(*_args, **_kwargs): denied("network/DB")
    for name in ("connect", "connect_ex", "sendto", "sendmsg"):
        if hasattr(socket.socket, name): setattr(socket.socket, name, blocked)
    for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "create_connection"):
        setattr(socket, name, blocked)
    # Import trusted dependency only after file/network/process guards exist.
    import dotenv
    dotenv.load_dotenv = lambda *_a, **_k: False
    dotenv.dotenv_values = lambda *_a, **_k: {}
    dotenv.find_dotenv = lambda *_a, **_k: ""
    from pydantic_settings.sources import DotEnvSettingsSource
    DotEnvSettingsSource._read_env_files = lambda self: {}

    def watchdog():
        deadline = time.monotonic() + cap["lifetime"]
        while os.getppid() == cap["parent_pid"] and time.monotonic() < deadline:
            time.sleep(0.2)
        os._exit(79)
    threading.Thread(target=watchdog, daemon=True).start()
    return violations


def valid_results(status, collected, passed, bad, violations):
    return not status and collected > 0 and passed == collected and not bad and not violations


def valid_flow_origins(source, modules):
    ai = (source.parent / "ai/src").resolve()
    for name in ("agents", "agents.flow", "agents.flow.api", "agents.flow.domain"):
        spec = getattr(modules.get(name), "__spec__", None)
        locations = getattr(spec, "submodule_search_locations", None)
        if getattr(spec, "origin", "invalid") is not None or locations is None:
            return False
        if [Path(p).resolve() for p in locations] != [ai.joinpath(*name.split("."))]:
            return False
    for name, relative in (("agents.flow.api.payload", "agents/flow/api/payload.py"),
                           ("agents.flow.domain.models", "agents/flow/domain/models.py")):
        spec = getattr(modules.get(name), "__spec__", None)
        origin = getattr(spec, "origin", None)
        if not origin or Path(origin).resolve() != ai / relative:
            return False
    return True


def main():
    if len(sys.argv) != 2 or not sys.flags.isolated or not sys.flags.no_site:
        raise SystemExit(78)
    cap = json.loads(Path(sys.argv[1]).read_text())
    violations = install(cap)
    if cap["mode"] == "self-test":
        runpy.run_path(str(Path(cap["source"]) / "tests/safe_checks/test_entry.py"), run_name="__main__")
        return 0
    import pytest

    class Results:
        collected = 0
        passed = 0
        bad = False
        def pytest_collection_modifyitems(self, items):
            self.collected = len(items)
            # Root stock parser files are pure; their ancestor DB conftest must
            # remain excluded by confcutdir, never registered as a fixture plugin.
            expected_conftest = Path(cap["source"]) / "tests/unit/conftest.py"
            loaded = {Path(module.__file__).resolve() for module in items[0].config.pluginmanager._conftest_plugins} if items else set()
            if loaded - {expected_conftest.resolve()}:
                raise pytest.UsageError("unexpected automatic conftest outside unit boundary")
            files = {str(i.path.relative_to(Path(cap["source"]))) for i in items}
            if files != set(cap["tests"]): self.bad = True
            if not valid_flow_origins(Path(cap["source"]), sys.modules): self.bad = True
        def pytest_sessionfinish(self):
            if not valid_flow_origins(Path(cap["source"]), sys.modules): self.bad = True
        def pytest_runtest_logreport(self, report):
            if report.when == "call" and report.passed: self.passed += 1
            if report.skipped or hasattr(report, "wasxfail"): self.bad = True
    result = Results()
    config = Path(cap["root"]) / "pytest.ini"
    config.write_text("[pytest]\nasyncio_mode=auto\nasyncio_default_fixture_loop_scope=function\nlog_file="+str(Path(cap["root"])/"pytest.log")+"\n")
    status = pytest.main(["-c", str(config), "--confcutdir="+str(Path(cap["source"])/"tests/unit"),
                          "-p", "pytest_asyncio.plugin", "-q", *cap["tests"]], plugins=[result])
    print(f"Selected files={len(cap["tests"])} collected={result.collected} passed={result.passed} guard_violations={len(violations)} kinds={violations}")
    return int(not valid_results(status, result.collected, result.passed, result.bad, violations))


if __name__ == "__main__":
    raise SystemExit(main())
