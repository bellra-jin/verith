"""Synthetic stdlib regressions; invoked ONLY after the OS/bootstrap gate."""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest


class EntryBoundary(unittest.TestCase):
    def test_cf004_exact_pin_and_namespace_boundary(self):
        import hashlib
        from scripts import check_safe as controller
        from scripts.safe_checks_bootstrap import valid_flow_origins
        from types import SimpleNamespace
        expected = "ai/src/agents/flow/infrastructure/token_cache.py"
        self.assertEqual(set(controller.CF004_INPUTS), {expected})
        self.assertEqual(controller.UNIT.count("tests/unit/test_cf004_kis_token_cache.py"), 1)
        checkout = Path(__file__).resolve().parents[3]
        data = controller.regular_bytes(checkout, expected)
        self.assertEqual(hashlib.sha256(data).hexdigest(), controller.CF004_INPUTS[expected])
        self.assertNotEqual(hashlib.sha256(data+b"\n# synthetic mutation").hexdigest(), controller.CF004_INPUTS[expected])
        self.assertFalse(controller.source_allowed("ai/src/agents/flow/infrastructure/adjacent.py"))
        source = Path(os.environ["TMPDIR"]) / "synthetic-checkout/backend"
        ai = source.parent / "ai/src"
        modules = {name: SimpleNamespace(__spec__=SimpleNamespace(origin=None, submodule_search_locations=[str(ai.joinpath(*name.split('.')))]))
                   for name in ("agents", "agents.flow", "agents.flow.api", "agents.flow.domain", "agents.flow.infrastructure")}
        for name, relative in (("agents.flow.api.payload", "agents/flow/api/payload.py"),
                               ("agents.flow.domain.models", "agents/flow/domain/models.py"),
                               ("agents.flow.infrastructure.token_cache", "agents/flow/infrastructure/token_cache.py")):
            modules[name] = SimpleNamespace(__spec__=SimpleNamespace(origin=str(ai / relative)))
        self.assertTrue(valid_flow_origins(source, modules))
        modules["agents.flow.infrastructure"].__spec__.submodule_search_locations.append("/synthetic/other")
        self.assertFalse(valid_flow_origins(source, modules))
        modules["agents.flow.infrastructure"].__spec__.submodule_search_locations.pop()
        modules["agents.flow.infrastructure.token_cache"].__spec__.origin = str(ai / "agents/flow/infrastructure/adjacent.py")
        self.assertFalse(valid_flow_origins(source, modules))

    def test_cf003_owned_home_is_scoped_without_tls_changes(self):
        from types import SimpleNamespace
        from scripts.cf003_admission_check import owned_postgres_home
        previous = os.environ.get("HOME")
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            root = Path(directory)
            docker = SimpleNamespace(_config=SimpleNamespace(name=str(root)))
            with owned_postgres_home(docker):
                self.assertEqual(Path.home(), root.resolve())
                self.assertNotIn("PGSSLMODE", os.environ)
            self.assertEqual(os.environ.get("HOME"), previous)
            root.chmod(0o755)
            with self.assertRaises(RuntimeError):
                with owned_postgres_home(docker):
                    self.fail("unsafe owned-home metadata accepted")
            root.chmod(0o700)

    def test_cf003_exact_source_and_fixed_unit_selection(self):
        from scripts import check_safe as controller
        expected = {
            "backend/src/modules/flow/api/run_schemas.py",
            "backend/src/modules/flow/api/run_router.py",
            "backend/src/modules/flow/application/run_service.py",
            "backend/src/modules/flow/infrastructure/run_repository.py",
            "backend/db/models/flow/flow_run.py",
            "backend/db/migrations/versions/20261108_c3001a7e0001_flow_run_admission.py",
            "backend/tests/unit/test_cf003_flow_runs.py",
            "backend/scripts/cf002_interactive_login.py",
            "backend/scripts/cf003_admission_check.py",
        }
        self.assertEqual(controller.CF003_SOURCES, expected)
        self.assertEqual(controller.UNIT.count("tests/unit/test_cf003_flow_runs.py"), 1)
        self.assertTrue(expected <= controller.NEW)
        for p in expected:
            self.assertTrue(controller.source_allowed(p))
        self.assertFalse(controller.source_allowed("backend/scripts/cf003_other.py"))

    def test_import_time_probe_is_blocked(self):
        # exec models collection-time module top-level code, before any fixture.
        probes = ["open('.env.synthetic', 'r')", "socket.getaddrinfo('synthetic.invalid', 1)",
                  "socket.socket().connect(('127.0.0.1', 1))",
                  "socket.socket().connect_ex(('127.0.0.1', 1))",
                  "socket.socket(type=socket.SOCK_DGRAM).sendto(b'x',('127.0.0.1',1))",
                  "subprocess.run(['/usr/bin/true'])"]
        for code in probes:
            with self.subTest(probe=code), self.assertRaises(PermissionError):
                exec(compile(code, "<synthetic-collection-probe>", "exec"),
                     {"socket": socket, "subprocess": subprocess})

    def test_parent_credentials_absent(self):
        self.assertFalse(set(os.environ) & {"GOOGLE_CLIENT_SECRET", "DATABASE_URL", "NODE_OPTIONS",
                                          "DYLD_INSERT_LIBRARIES", "PYTHONPATH", "PYTEST_PLUGINS"})

    def test_dotenv_is_disabled_before_collection(self):
        from dotenv import dotenv_values, load_dotenv
        self.assertEqual(dotenv_values(".env.synthetic"), {})
        self.assertFalse(load_dotenv(".env.synthetic"))

    def test_results_reject_zero_skip_failure_or_guard_violation(self):
        from scripts.safe_checks_bootstrap import valid_results, read_diagnostic, read_allowed, SYSTEM_METADATA
        self.assertTrue(valid_results(0, 4, 4, False, []))
        for values in [(0, 0, 0, False, []), (1, 4, 4, False, []), (0, 4, 3, False, []),
                       (0, 4, 4, True, []), (0, 4, 4, False, ["synthetic violation"])]:
            self.assertFalse(valid_results(*values))
        for target in ("/synthetic/.env.local", "/synthetic/credentials/token.json"):
            detail = read_diagnostic(Path(target), Path("/owned"), Path("/dependency"), Path("/runtime"))
            self.assertIn("target=private-path-redacted", detail)
            self.assertNotIn(target, detail)
        detail = read_diagnostic(Path("/synthetic/unapproved.txt"), Path("/owned"), Path("/dependency"), Path("/runtime"))
        self.assertIn("target=outside-target-redacted", detail)
        self.assertNotIn("unapproved.txt", detail)
        roots = (Path("/owned"), Path("/dependency"), Path("/runtime"))
        self.assertTrue(read_allowed(Path(SYSTEM_METADATA), *roots))
        for target in (SYSTEM_METADATA + ".backup", "/System/Library/CoreServices/other.plist", "/synthetic/private/file"):
            self.assertFalse(read_allowed(Path(target), *roots))

    def test_tracked_private_paths_are_rejected_before_open(self):
        from scripts.check_safe import regular_bytes, UnsafeCheck, private_path, source_allowed, FLOW_INPUTS, REMOVED_SOURCES
        self.assertEqual(len(FLOW_INPUTS), 2)
        for name in REMOVED_SOURCES:
            self.assertFalse(source_allowed(name))
        for name in FLOW_INPUTS:
            self.assertTrue(source_allowed(name))
        for name in ("ai/src/agents/flow/config.py", "ai/src/agents/flow/__init__.py",
                     "ai/src/agents/flow/export/other.py", "ai/src/agents/flow/graph.py"):
            self.assertFalse(source_allowed(name))
        from scripts.safe_checks_bootstrap import valid_flow_origins
        from types import SimpleNamespace
        source = Path(os.environ["TMPDIR"]) / "synthetic-checkout/backend"
        ai = source.parent / "ai/src"
        modules = {name: SimpleNamespace(__spec__=SimpleNamespace(origin=None, submodule_search_locations=[str(ai.joinpath(*name.split('.')))]))
                   for name in ("agents", "agents.flow", "agents.flow.api", "agents.flow.domain", "agents.flow.infrastructure")}
        for name, relative in (("agents.flow.api.payload", "agents/flow/api/payload.py"), ("agents.flow.domain.models", "agents/flow/domain/models.py"), ("agents.flow.infrastructure.token_cache", "agents/flow/infrastructure/token_cache.py")):
            modules[name] = SimpleNamespace(__spec__=SimpleNamespace(origin=str(ai / relative)))
        self.assertTrue(valid_flow_origins(source, modules))
        modules["agents"].__spec__.submodule_search_locations.append("/synthetic/unapproved")
        self.assertFalse(valid_flow_origins(source, modules))
        modules["agents"].__spec__.submodule_search_locations.pop()
        for name in ("agents.flow.api.payload", "agents.flow.domain.models", "agents.flow.infrastructure.token_cache"):
            old = modules[name].__spec__.origin
            modules[name].__spec__.origin = "/synthetic/unapproved/module.py"
            self.assertFalse(valid_flow_origins(source, modules))
            modules[name].__spec__.origin = old
        self.assertFalse(valid_flow_origins(source, {}))
        for name in ["src/secrets/token.py", "src/keys/fixture.py", "src/private/data.py",
                     "src/dumps/state.py", "src/backups/copy.py", "src/logs/data.py"]:
            self.assertTrue(private_path(name))
            with self.assertRaises(UnsafeCheck):
                regular_bytes(Path("/nonexistent-synthetic-root"), name)

    def test_relocated_inputs_are_exact_and_required(self):
        from scripts import check_safe as controller
        from unittest.mock import patch
        expected = {
            "backend/src/modules/flow/domain/payload.py", "backend/src/modules/flow/domain/execution.py",
            "backend/src/modules/flow/api/schemas.py", "backend/src/modules/flow/api/router.py",
            "ai/src/agents/flow/domain/models.py", "ai/src/agents/flow/api/payload.py",
        }
        self.assertTrue(expected <= controller.NEW)
        for name in expected:
            self.assertTrue(controller.source_allowed(name))
        for name in ("ai/src/agents/flow/domain/other.py", "ai/src/agents/flow/api/private.py",
                     "ai/src/agents/flow/api/__init__.py", "ai/src/agents/flow/domain/__init__.py"):
            self.assertFalse(controller.source_allowed(name))
        indexed = controller.EXTRA | (controller.FLOW_INPUTS.keys() - controller.NEW) | {"backend/"+u for u in controller.UNIT}
        raw = "".join("100644 synthetic 0\t"+name+"\0" for name in sorted(indexed)).encode()
        with patch.object(controller.subprocess, "check_output", return_value=raw):
            self.assertTrue(expected <= set(controller.selected_sources(Path("/synthetic"))))
        with patch.object(controller.subprocess, "check_output", return_value=b""):
            with self.assertRaises(controller.UnsafeCheck):
                controller.selected_sources(Path("/synthetic"))

    def test_owned_root_replacement_refuses_cleanup_and_preserves_sibling(self):
        from scripts.check_safe import OwnedRoot, UnsafeCheck
        import shutil
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            parent = Path(directory)
            sibling = parent / "sibling"
            sibling.mkdir()
            owned = OwnedRoot(parent)
            original = owned.path.with_name(owned.path.name + "-original")
            owned.path.rename(original)
            owned.path.mkdir()
            with self.assertRaises(UnsafeCheck):
                owned.close()
            self.assertTrue(sibling.exists())
            self.assertTrue(original.exists())
            shutil.rmtree(owned.path)
            shutil.rmtree(original)

    def test_child_failure_and_term_kill_are_not_swallowed(self):
        from scripts import check_safe as controller
        from unittest.mock import Mock, patch
        child = Mock(pid=123, returncode=7)
        child.poll.return_value = 7
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            with patch.object(controller.subprocess, "Popen", return_value=child):
                status, _ = controller.run_child(["synthetic"], Path(directory), 1, group_alive=lambda child: False)
            self.assertEqual(status, 7)
            child.poll.return_value = None
            child.wait.side_effect = [controller.subprocess.TimeoutExpired("synthetic", 3), 0]
            with patch.object(controller.subprocess, "Popen", return_value=child), patch.object(controller.os, "getpgid", return_value=123), patch.object(controller.os, "killpg") as kill:
                with self.assertRaises(controller.UnsafeCheck):
                    controller.run_child(["synthetic"], Path(directory), -1, group_alive=lambda child: False)
            self.assertEqual([c.args[1] for c in kill.call_args_list], [controller.signal.SIGTERM, controller.signal.SIGKILL])
            self.assertEqual(child.wait.call_count, 2)

    def test_native_denial_requires_positive_controls_and_exact_permission_error(self):
        from scripts.check_safe import valid_native_probe, verify_native_sequence, UnsafeCheck
        def result(status=0, stdout="", stderr="", signal=False):
            return dict(status=status, stdout=stdout, stderr=stderr, signal=signal)
        self.assertTrue(valid_native_probe("true", result(), "/synthetic"))
        self.assertTrue(valid_native_probe("allowed", result(stdout="SYNTHETIC-ALLOWED\n"), "/synthetic"))
        permission = "cat: /synthetic: Operation not permitted\n"
        self.assertTrue(valid_native_probe("denied", result(1, stderr=permission), "/synthetic"))
        for bad in [result(-6, signal=True), result(1), result(2, stderr=permission),
                    result(1, stdout="unexpected", stderr=permission), result(1, stderr="loader failed\n"),
                    result(1, stderr=permission, signal=True)]:
            self.assertFalse(valid_native_probe("denied", bad, "/synthetic"))
        self.assertFalse(valid_native_probe("allowed", result(1, stderr=permission), "/synthetic"))
        calls = []
        stages = [("true", "true"), ("allowed", "allowed"), ("denied", "denied")]
        def fail_first(command):
            calls.append(command)
            return result(-6, signal=True)
        with self.assertRaises(UnsafeCheck):
            verify_native_sequence(stages, fail_first, "/synthetic")
        self.assertEqual(calls, ["true"])
        calls.clear()
        def timeout(command):
            calls.append(command)
            raise TimeoutError("synthetic timeout")
        with self.assertRaises(TimeoutError):
            verify_native_sequence(stages, timeout, "/synthetic")
        self.assertEqual(calls, ["true"])

    def test_regular_source_rejects_unsafe_identity(self):
        filename = Path(__file__).parents[2] / "scripts/check_safe.py"
        spec = importlib.util.spec_from_file_location("safe_controller", filename)
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            root = Path(directory)
            (root / "source.py").write_text("synthetic = True")
            self.assertEqual(controller.regular_bytes(root, "source.py"), b"synthetic = True")
            (root / "alias.py").symlink_to(root / "source.py")
            os.link(root / "source.py", root / "hard.py")
            os.mkfifo(root / "pipe.py")
            for name in ("alias.py", "hard.py", "pipe.py", ".env.synthetic", "../escape.py"):
                with self.subTest(name=name), self.assertRaises((controller.UnsafeCheck, PermissionError)):
                    controller.regular_bytes(root, name)
            # Reject FIFO by metadata without opening it (opening could block).
            self.assertFalse((root / "pipe.py").is_file())


    def _flow_env_programs(self):
        import ast
        checkout = Path(__file__).resolve().parents[3]
        rows = (
            ("ai/src/agents/flow/infrastructure/kis_client.py", 4, "_load_credentials"),
            ("ai/src/agents/flow/infrastructure/llm/explain.py", 5, "explain"),
            ("ai/devtools/flow/streamlit_flow_lab.py", 2, None),
        )
        result = []
        for relative, depth, owner in rows:
            tree = ast.parse((checkout / relative).read_text())
            expected = {"_AI_ROOT": f"Path(__file__).resolve().parents[{depth}]",
                        "_ENV_FILE": '_AI_ROOT / ".env"'}
            if owner == "explain":
                expected["_PROMPT_PATH"] = 'Path(__file__).parents[2] / "prompts" / "explain.txt"'
            elif owner is None:
                expected["_SRC"] = '_AI_ROOT / "src"'
            names = {"_AI_ROOT", "_ENV_FILE", "_SRC", "_PROMPT_PATH"}
            declarations = []
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(isinstance(item, ast.Name) and item.id in names
                                                       for target in node.targets for item in ast.walk(target)):
                    self.assertEqual(len(node.targets), 1)
                    self.assertIsInstance(node.targets[0], ast.Name)
                    declarations.append(node)
            selected = [node.targets[0].id for node in declarations]
            self.assertEqual(len(selected), len(set(selected)))
            self.assertEqual(set(selected), set(expected))
            self.assertCountEqual([node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
                                   and isinstance(node.ctx, ast.Store) and node.id in names], selected)
            self.assertFalse(any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                                 and node.name in names for node in ast.walk(tree)))
            self.assertFalse(any(isinstance(node, ast.alias) and (node.asname or node.name) in names
                                 for node in ast.walk(tree)))
            for node in declarations:
                self.assertEqual(ast.dump(node.value), ast.dump(ast.parse(expected[node.targets[0].id], mode="eval").body))
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == "load_dotenv"]
            self.assertEqual(len(calls), 1)
            self.assertEqual(ast.dump(calls[0]),
                             ast.dump(ast.parse("load_dotenv(dotenv_path=_ENV_FILE, override=False)", mode="eval").body))
            self.assertFalse(any(isinstance(node, ast.Name) and node.id == "find_dotenv"
                                 for node in ast.walk(tree)))
            body = tree.body if owner is None else next(node.body for node in tree.body
                                                       if isinstance(node, ast.FunctionDef) and node.name == owner)
            self.assertTrue(any(isinstance(node, ast.Expr) and node.value is calls[0] for node in body))
            program = ast.Module(body=declarations + [ast.Expr(value=calls[0])], type_ignores=[])
            ast.fix_missing_locations(program)
            result.append((relative, compile(program, "<synthetic-flow-env-policy>", "exec")))
        return result

    def test_flow_explicit_env_uses_ai_root_and_preserves_resource_anchors(self):
        from unittest.mock import Mock
        from scripts import check_safe as controller
        programs = self._flow_env_programs()
        self.assertEqual(len(programs), 3)
        self.assertEqual(controller.FLOW_POLICY_SOURCES, frozenset(row[0] for row in programs))
        for relative, program in programs:
            with self.subTest(source=relative):
                self.assertIn(relative, controller.NEW)
                self.assertNotIn(relative, controller.FLOW_INPUTS)
                self.assertTrue(controller.source_allowed(relative))
                namespace = {"__file__": str(Path(os.environ["TMPDIR"]) / "project" / relative),
                             "Path": Path, "load_dotenv": Mock(), "__builtins__": {}}
                exec(program, namespace)
                ai = Path(os.environ["TMPDIR"]) / "project/ai"
                self.assertEqual(namespace["_AI_ROOT"], ai)
                self.assertEqual(namespace["_ENV_FILE"], ai / ".env")
                namespace["load_dotenv"].assert_called_once_with(dotenv_path=ai / ".env", override=False)
                if "_PROMPT_PATH" in namespace:
                    self.assertEqual(namespace["_PROMPT_PATH"], ai / "src/agents/flow/prompts/explain.txt")
                if "_SRC" in namespace:
                    self.assertEqual(namespace["_SRC"], ai / "src")
        for relative in ("ai/src/agents/flow/infrastructure/other.py",
                         "ai/src/agents/flow/infrastructure/llm/other.py",
                         "ai/devtools/flow/other.py"):
            self.assertFalse(controller.source_allowed(relative))

    def test_flow_explicit_env_stream_fixture_process_precedence_and_no_search(self):
        import io
        from unittest.mock import patch
        import dotenv
        from dotenv.main import load_dotenv as parse_stream_environment
        blocked_load, blocked_find = dotenv.load_dotenv, dotenv.find_dotenv
        self.assertIsNot(blocked_load, parse_stream_environment)
        self.assertIsNot(blocked_find, dotenv.main.find_dotenv)
        programs = self._flow_env_programs()
        # Virtual .env paths map only to synthetic in-memory streams. No .env file is created/opened.
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            project = Path(directory) / "project"
            ai = project / "ai"
            previous_cwd = Path.cwd()
            try:
                for cwd in (project / "work", ai / "nested/work", Path(directory) / "other"):
                    cwd.mkdir(parents=True)
                    os.chdir(cwd)
                    for relative, program in programs:
                        with self.subTest(source=relative, cwd=cwd.name):
                            virtual_source = project / relative
                            fixtures = {
                                ai / ".env": "ST001_PRIORITY=root\nST001_ROOT_ONLY=synthetic-root\n",
                                virtual_source.parent / ".env": "ST001_INTERMEDIATE_ONLY=not-selected\n",
                                project / ".env": "ST001_PARENT_ONLY=not-selected\n",
                                cwd / ".env": "ST001_CWD_ONLY=not-selected\n",
                            }
                            hits = []
                            def selected_stream(*, dotenv_path, override):
                                self.assertEqual(dotenv_path, ai / ".env")
                                self.assertIs(override, False)
                                hits.append(dotenv_path)
                                return parse_stream_environment(stream=io.StringIO(fixtures[dotenv_path]), override=override)
                            for priority in ("process", ""):
                                hits.clear()
                                with patch.dict(os.environ, {"ST001_PRIORITY": priority}, clear=True), \
                                     patch("dotenv.main.find_dotenv", side_effect=AssertionError("automatic discovery forbidden")):
                                    exec(program, {"__file__": str(virtual_source), "Path": Path,
                                                   "load_dotenv": selected_stream, "__builtins__": {}})
                                    self.assertEqual(os.environ["ST001_PRIORITY"], priority)
                                    self.assertEqual(os.environ["ST001_ROOT_ONLY"], "synthetic-root")
                                    self.assertFalse(set(os.environ) & {"ST001_INTERMEDIATE_ONLY", "ST001_PARENT_ONLY", "ST001_CWD_ONLY"})
                                    self.assertEqual(hits, [ai / ".env"])
            finally:
                os.chdir(previous_cwd)
        self.assertIs(dotenv.load_dotenv, blocked_load)
        self.assertIs(dotenv.find_dotenv, blocked_find)

    def test_flow_missing_explicit_env_keeps_process_environment_without_fallback(self):
        import io
        from unittest.mock import patch
        from dotenv.main import load_dotenv as parse_stream_environment
        import dotenv
        blocked_load, blocked_find = dotenv.load_dotenv, dotenv.find_dotenv
        self.assertIsNot(blocked_load, parse_stream_environment)
        self.assertIsNot(blocked_find, dotenv.main.find_dotenv)
        project = Path.cwd().parent / "missing-project"
        for relative, program in self._flow_env_programs():
            with self.subTest(source=relative), patch.dict(os.environ, {"ST001_PRIORITY": "process"}, clear=True), \
                 patch("dotenv.main.find_dotenv", side_effect=AssertionError("automatic discovery forbidden")):
                outcomes = []
                def missing_stream(*, dotenv_path, override):
                    self.assertEqual(dotenv_path, project / "ai/.env")
                    self.assertIs(override, False)
                    loaded = parse_stream_environment(stream=io.StringIO(""), override=override)
                    outcomes.append(loaded)
                    return loaded
                # __file__ is absolute and confined to the already owned test root.
                exec(program, {"__file__": str(project / relative), "Path": Path,
                               "load_dotenv": missing_stream, "__builtins__": {}})
                self.assertEqual(outcomes, [False])
                self.assertEqual(dict(os.environ), {"ST001_PRIORITY": "process"})
        self.assertIs(dotenv.load_dotenv, blocked_load)
        self.assertIs(dotenv.find_dotenv, blocked_find)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EntryBoundary)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
