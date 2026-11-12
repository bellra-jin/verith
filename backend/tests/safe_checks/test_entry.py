"""Synthetic stdlib regressions; invoked ONLY after the OS/bootstrap gate."""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest


class EntryBoundary(unittest.TestCase):
    def test_cf005_exact_helper_html_fixture_and_origin(self):
        import hashlib
        from scripts import check_safe as controller
        expected = "ai/src/agents/flow/domain/observation_window.py"
        self.assertEqual(set(controller.CF005_INPUTS), {expected})
        self.assertEqual(controller.CF005_SOURCE_ONLY, {
            "ai/src/agents/flow/domain/verification/signals.py",
            "ai/src/agents/flow/infrastructure/render/builder.py",
            "ai/src/agents/flow/prompts/explain.txt",
            "ai/src/agents/flow/infrastructure/render/templates/supply_demand.html",
            "frontend/tests/fixtures/cf005-observation-cases.json",
        })
        self.assertEqual(controller.UNIT.count("tests/unit/test_cf005_flow_observation.py"), 1)
        checkout = Path(__file__).resolve().parents[3]
        self.assertEqual(hashlib.sha256(controller.regular_bytes(checkout, expected)).hexdigest(), controller.CF005_INPUTS[expected])
        for name in {expected, *controller.CF005_SOURCE_ONLY}:
            self.assertTrue(controller.source_allowed(name))
            self.assertTrue(controller.regular_bytes(checkout, name))
        for name in ("ai/src/agents/flow/domain/adjacent.py", "ai/src/agents/flow/infrastructure/render/templates/other.html", "frontend/tests/fixtures/other.json"):
            self.assertFalse(controller.source_allowed(name))

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
                               ("agents.flow.domain.models", "agents/flow/domain/models.py"), ("agents.flow.domain.observation_window", "agents/flow/domain/observation_window.py"),
                               ("agents.flow.infrastructure.token_cache", "agents/flow/infrastructure/token_cache.py")):
            modules[name] = SimpleNamespace(__spec__=SimpleNamespace(origin=str(ai / relative)))
        self.assertTrue(valid_flow_origins(source, modules))
        modules["agents.flow.infrastructure"].__spec__.submodule_search_locations.append("/synthetic/other")
        self.assertFalse(valid_flow_origins(source, modules))
        modules["agents.flow.infrastructure"].__spec__.submodule_search_locations.pop()
        modules["agents.flow.infrastructure.token_cache"].__spec__.origin = str(ai / "agents/flow/infrastructure/adjacent.py")
        self.assertFalse(valid_flow_origins(source, modules))

    def test_cf008_exact_copy_unit_and_default_off_gate(self):
        from scripts import check_safe as controller
        expected={"backend/src/modules/flow/api/synthetic_demo_schemas.py","backend/src/modules/flow/api/synthetic_demo_router.py","backend/src/modules/flow/application/synthetic_demo_service.py","backend/tests/unit/test_cf008_flow_synthetic_demo.py","backend/scripts/cf008_synthetic_demo_check.py"}
        self.assertEqual(controller.CF008_SOURCES,expected)
        self.assertEqual(controller.UNIT.count("tests/unit/test_cf008_flow_synthetic_demo.py"),1)
        for name in expected:
            self.assertTrue(controller.source_allowed(name));self.assertFalse(controller.source_allowed(name+'.adjacent'))
        root=Path(__file__).resolve().parents[2]
        self.assertIn('FLOW_SYNTHETIC_DEMO_ENABLED: bool = False',(root/'src/shared/config.py').read_text())
        source=(root/'scripts/cf002_interactive_login.py').read_text()
        self.assertLess(source.index('verify_synthetic_demo(proof)'),source.index('project = prepare_projects'))

    def test_cf007_exact_sources_selection_and_fixed_revision_modes(self):
        from scripts import check_safe as controller
        expected = {
            "backend/src/modules/flow/domain/fake_execution.py",
            "backend/src/modules/flow/application/fake_execution_service.py",
            "backend/src/modules/flow/infrastructure/fake_execution_repository.py",
            "backend/db/models/flow/fake_execution.py",
            "backend/db/migrations/versions/20261108_c7001a7e0001_flow_fake_execution.py",
            "backend/scripts/cf007_fake_execution_check.py",
            "backend/tests/unit/test_cf007_flow_fake_execution.py",
        }
        self.assertEqual(controller.CF007_SOURCES, expected)
        self.assertEqual(controller.UNIT.count("tests/unit/test_cf007_flow_fake_execution.py"), 1)
        for name in expected:
            self.assertTrue(controller.source_allowed(name))
            self.assertFalse(controller.source_allowed(name + ".adjacent"))
        root = Path(__file__).resolve().parents[2]
        source = (root / "scripts/cf002_interactive_login.py").read_text()
        self.assertIn('target not in {"head", "c6001a7e0001"}', source)
        self.assertIn('migrate_owned(second_proof, target="c6001a7e0001")', source)
        self.assertLess(source.index("result = asyncio.run(asyncio.wait_for(verify_fake_execution(proof)"), source.index("project = prepare_projects"))

    def test_cf006_exact_sources_fixed_selection_and_db_only_order(self):
        import ast
        from scripts import check_safe as controller
        expected = {
            "backend/src/modules/flow/domain/input_snapshot.py",
            "backend/src/modules/flow/application/input_preparation_service.py",
            "backend/src/modules/flow/infrastructure/input_snapshot_repository.py",
            "backend/db/models/flow/input_snapshot.py",
            "backend/db/migrations/versions/20261108_c6001a7e0001_flow_input_snapshots.py",
            "backend/scripts/cf006_input_snapshot_check.py",
            "backend/tests/unit/test_cf006_flow_input_snapshot.py",
        }
        self.assertEqual(controller.CF006_SOURCES, expected)
        self.assertEqual(controller.UNIT.count("tests/unit/test_cf006_flow_input_snapshot.py"), 1)
        self.assertTrue(expected <= controller.NEW)
        for name in expected:
            self.assertTrue(controller.source_allowed(name))
            self.assertFalse(controller.source_allowed(name + ".adjacent"))
        root = Path(__file__).resolve().parents[2]
        source = (root / "scripts/cf002_interactive_login.py").read_text()
        self.assertIn('mode.add_argument("--verify-flow-input-snapshot-db", action="store_true")', source)
        self.assertLess(source.index("result = asyncio.run(asyncio.wait_for(verify_input_snapshot(proof)"), source.index("project = prepare_projects"))
        checker = (root / "scripts/cf006_input_snapshot_check.py").read_text()
        tree = ast.parse(checker)
        wrapper = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "verify_input_snapshot")
        self.assertLess(ast.unparse(wrapper).index("verify_admission(proof)"), ast.unparse(wrapper).index("_verify(proof)"))
        self.assertIn('normalized.startswith("CREATE TABLE FLOW_INPUT_SNAPSHOTS")', checker)
        self.assertNotIn('normalized.startswith("CREATE TABLE FLOW_RUNS")', checker)

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
        for name, relative in (("agents.flow.api.payload", "agents/flow/api/payload.py"), ("agents.flow.domain.models", "agents/flow/domain/models.py"), ("agents.flow.domain.observation_window", "agents/flow/domain/observation_window.py"), ("agents.flow.infrastructure.token_cache", "agents/flow/infrastructure/token_cache.py")):
            modules[name] = SimpleNamespace(__spec__=SimpleNamespace(origin=str(ai / relative)))
        self.assertTrue(valid_flow_origins(source, modules))
        modules["agents"].__spec__.submodule_search_locations.append("/synthetic/unapproved")
        self.assertFalse(valid_flow_origins(source, modules))
        modules["agents"].__spec__.submodule_search_locations.pop()
        for name in ("agents.flow.api.payload", "agents.flow.domain.models", "agents.flow.infrastructure.token_cache", "agents.flow.domain.observation_window"):
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



class CF012Boundary(unittest.TestCase):
    def test_exact_four_pinned_inputs_and_adjacent_rejected(self):
        import hashlib
        from scripts import check_safe as c
        expected={'ai/src/agents/flow/api/http.py','ai/src/agents/flow/api/schemas.py','ai/src/agents/flow/application/execution_runtime.py','ai/src/shared/runtime/deadline.py'}
        self.assertEqual(set(c.CF012_INPUTS),expected)
        root=Path(__file__).resolve().parents[3]
        for name in expected:
            self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),c.CF012_INPUTS[name])
            self.assertFalse(c.source_allowed(name+'.adjacent'))
        self.assertEqual(c.CF012_TESTS,('tests/unit/test_cf012_flow_analysis.py','tests/unit/test_flow_contract.py'))

    def test_copy_loader_has_no_searchable_graph_path(self):
        import sys
        from scripts.cf012_analysis_check import flow_app,engine_result
        flow_app(engine_result)
        self.assertEqual(sys.modules['_cf012_flow'].__path__,[])
        self.assertNotIn('_cf012_flow.application.agent',sys.modules)
        self.assertNotIn('_cf012_flow.config',sys.modules)

    def test_existing_guard_and_legacy_pins_remain(self):
        from scripts import check_safe as c
        self.assertEqual(len(c.FLOW_INPUTS),2)
        self.assertEqual(len(c.CF004_INPUTS),1)
        self.assertEqual(len(c.CF005_INPUTS),1)
        self.assertFalse(c.source_allowed('ai/src/agents/flow/application/agent.py'))

class CF013Boundary(unittest.TestCase):
    def test_exact_sources_and_single_file_selection(self):
        import ast
        from scripts import check_safe as c
        self.assertEqual(c.CF013_TESTS,("tests/unit/test_cf013_analysis_contracts.py",))
        expected={"backend/src/modules/analysis/domain/contracts.py","backend/src/modules/analysis/application/ports.py","backend/src/modules/flow/application/analysis_adapter.py","backend/examples/analysis/fundamental_adapter.py","backend/examples/analysis/fundamental-response.v1.json","backend/tests/unit/test_cf013_analysis_contracts.py","backend/scripts/cf013_contract_check.py"}
        self.assertEqual(c.CF013_SOURCES,expected)
        root=Path(__file__).resolve().parents[3]
        for name in expected:
            self.assertTrue(c.regular_bytes(root,name));self.assertFalse(c.source_allowed(name+'.adjacent'))
        tree=ast.parse((root/'backend/tests/unit/test_cf013_analysis_contracts.py').read_text())
        imports=[n for n in tree.body if isinstance(n,ast.ImportFrom) and n.module in {'tests.unit.test_flow_contract','tests.unit.test_cf012_flow_analysis'}]
        self.assertEqual({a.name for n in imports for a in n.names},{'test_relocation_public_contract_baseline','test_confirmed_collision_stays_terminal_after_winner_deleted','test_other_integrity_failure_is_not_confirmed_report_collision'})
        self.assertTrue(all(a.asname.startswith('_') for n in imports for a in n.names))

    def test_neutral_contracts_have_only_stdlib_dependencies(self):
        import ast
        root=Path(__file__).resolve().parents[2]
        tree=ast.parse((root/'src/modules/analysis/domain/contracts.py').read_text())
        names={n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}|{a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
        self.assertLessEqual(names,{'dataclasses','datetime','hashlib','json','math','re','typing','uuid'})


class CF014Boundary(unittest.TestCase):
    def test_exact_fifteen_pins_and_single_focused_collection(self):
        import hashlib
        from unittest.mock import patch
        from scripts import check_safe as c
        self.assertEqual(len(c.CF014_INPUTS),14)
        self.assertEqual(c.CF014_COMPAT,c.CF004_INPUTS)
        self.assertEqual(c.CF014_TESTS,("tests/unit/test_cf014_flow_quality.py",))
        root=Path(__file__).resolve().parents[3]
        expected=set(c.CF014_INPUTS)|set(c.CF014_COMPAT)
        for name in expected:
            self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),(c.CF014_INPUTS|c.CF014_COMPAT)[name])
            self.assertFalse(c.source_allowed(name+'.adjacent'))
        indexed=c.EXTRA | c.FLOW_INPUTS.keys() | c.CF004_INPUTS.keys() | c.CF005_INPUTS.keys() | {'backend/'+u for u in c.UNIT}
        raw=b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):
            copied=c.selected_sources(Path('/synthetic'),quality_only=True)
        self.assertEqual({p for p in copied if p.startswith('ai/')},expected)
        self.assertEqual(len(expected),15)

    def test_pure_loader_is_closed_and_dangerous_sources_remain_static(self):
        import ast
        root=Path(__file__).resolve().parents[3]
        source=(root/'backend/tests/unit/test_cf014_flow_quality.py').read_text()
        self.assertIn('_module.__path__ = []',source)
        self.assertNotIn('sys.path.append',source)
        self.assertNotIn('flow_app(',source)
        for name in ('workflow','explain','signals'):
            self.assertNotIn('from agents.flow.application.'+name,source)
        self.assertNotIn('from agents.flow.domain.signals import',source)
        self.assertIn('domain/verification/consecutive.py',__import__('scripts.check_safe',fromlist=['CF014_INPUTS']).CF014_INPUTS.keys().__str__())
        imports=[n for n in ast.parse((root/'ai/src/agents/flow/domain/interpretation_claims.py').read_text()).body if isinstance(n,(ast.Import,ast.ImportFrom))]
        names={n.module for n in imports if isinstance(n,ast.ImportFrom)}|{a.name for n in imports if isinstance(n,ast.Import) for a in n.names}
        self.assertLessEqual(names,{'dataclasses','hashlib','json','math','re','observation_window','verification.consecutive'})


class CF015Boundary(unittest.TestCase):
    def test_exact_fourteen_AI_inputs_and_one_collection(self):
        import hashlib
        from scripts import check_safe as c
        root=Path(__file__).resolve().parents[3]
        self.assertEqual(len(c.CF015_INPUTS),14)
        self.assertEqual(c.CF015_TESTS,('tests/unit/test_cf015_fundamental_analysis.py',))
        for name,digest in c.CF015_INPUTS.items():self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),digest)
        for name,digest in c.CF012_INPUTS.items():self.assertEqual(c.CF015_INPUTS[name],digest)
        for name in ('ai/src/agents/flow/domain/interpretation_claims.py','ai/src/agents/flow/domain/verification/consecutive.py'):self.assertEqual(c.CF015_INPUTS[name],c.CF014_INPUTS[name])

    def test_fixed_profiles_and_no_protection_change(self):
        import ast
        from scripts import check_safe as c
        self.assertEqual(len(c.FLOW_INPUTS),2);self.assertEqual(len(c.CF004_INPUTS),1)
        root=Path(__file__).resolve().parents[3]
        tree=ast.parse((root/'backend/tests/unit/test_cf015_fundamental_analysis.py').read_text())
        imports=[node for node in tree.body if isinstance(node,ast.ImportFrom) and node.module in {'tests.unit.test_flow_contract','tests.unit.test_cf012_flow_analysis'}]
        self.assertEqual({a.name for node in imports for a in node.names},{'test_relocation_public_contract_baseline','test_confirmed_collision_stays_terminal_after_winner_deleted','test_other_integrity_failure_is_not_confirmed_report_collision'})
        self.assertTrue(all(a.asname.startswith('_') for node in imports for a in node.names))


class CF017Boundary(unittest.TestCase):
    def test_exact_twelve_pins_single_collection_and_adjacent_exclusion(self):
        import hashlib
        from unittest.mock import patch
        from scripts import check_safe as c
        expected={'ai/src/agents/flow/'+p for p in ('api/http.py','api/schemas.py','application/execution_runtime.py','api/payload.py','domain/models.py','domain/observation_window.py','infrastructure/token_cache.py','domain/interpretation_claims.py','domain/verification/consecutive.py','infrastructure/kis_client.py','infrastructure/llm/explain.py')}|{'ai/src/shared/runtime/deadline.py'}
        self.assertEqual(set(c.CF017_INPUTS),expected)
        self.assertEqual(c.CF017_TESTS,('tests/unit/test_cf017_flow_error_classification.py',))
        root=Path(__file__).resolve().parents[3]
        for name in expected:
            self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),c.CF017_INPUTS[name])
            self.assertFalse(c.source_allowed(name+'.adjacent'))
        indexed=c.EXTRA | c.FLOW_INPUTS.keys() | c.CF004_INPUTS.keys() | c.CF005_INPUTS.keys() | {'backend/'+u for u in c.UNIT}
        raw=b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):
            copied=c.selected_sources(Path('/synthetic'),flow_errors_only=True)
        self.assertEqual({p for p in copied if p.startswith('ai/')},expected)
        for old in (c.CF012_INPUTS,c.CF014_INPUTS,c.CF015_INPUTS):
            for name in set(old)&expected:self.assertEqual(old[name],c.CF017_INPUTS[name])

    def test_closed_origins_AST_only_providers_and_unchanged_guard(self):
        from scripts import check_safe as c
        from scripts.safe_checks_bootstrap import valid_flow_origins
        import sys
        from scripts.cf015_fundamental_check import load_origins
        load_origins()
        self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2],sys.modules))
        self.assertEqual(len(c.FLOW_INPUTS),2);self.assertEqual(len(c.CF004_INPUTS),1)
        self.assertEqual((len(c.CF012_INPUTS),len(c.CF014_INPUTS),len(c.CF015_INPUTS)),(4,14,14))
        for name in ('agents.flow.infrastructure.kis_client','agents.flow.infrastructure.llm.explain','pandas','openai','langchain_openai'):
            self.assertNotIn(name,sys.modules)


class CF018Boundary(unittest.TestCase):
    def test_exact_same_twelve_AI_inputs_and_one_collection(self):
        import hashlib
        from unittest.mock import patch
        from scripts import check_safe as c
        self.assertEqual(c.CF018_TESTS,('tests/unit/test_cf018_flow_usage_limits.py',))
        self.assertEqual(c.CF018_INPUTS,c.CF017_INPUTS);self.assertEqual(len(c.CF018_INPUTS),12)
        root=Path(__file__).resolve().parents[3]
        for name,digest in c.CF018_INPUTS.items():
            self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),digest)
            self.assertFalse(c.source_allowed(name+'.adjacent'))
        for mapping in (c.CF012_INPUTS,c.CF014_INPUTS,c.CF015_INPUTS):
            for name in mapping.keys()&c.CF018_INPUTS.keys():self.assertEqual(mapping[name],c.CF018_INPUTS[name])
        indexed=c.EXTRA | c.FLOW_INPUTS.keys() | c.CF004_INPUTS.keys() | c.CF005_INPUTS.keys() | {'backend/'+u for u in c.UNIT}
        raw=b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):copied=c.selected_sources(Path('/synthetic'),usage_only=True)
        self.assertEqual({p for p in copied if p.startswith('ai/')},set(c.CF018_INPUTS))

    def test_origin_guard_and_other_profile_boundaries_unchanged(self):
        import sys
        from scripts import check_safe as c
        from scripts.safe_checks_bootstrap import valid_flow_origins
        from scripts.cf015_fundamental_check import load_origins
        load_origins();self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2],sys.modules))
        self.assertEqual((len(c.CF012_INPUTS),len(c.CF014_INPUTS),len(c.CF015_INPUTS),len(c.CF017_INPUTS)),(4,14,14,12))
        for name in ('agents.flow.application.agent','agents.flow.infrastructure.kis_client','agents.flow.infrastructure.llm.explain','pandas','openai','langchain_openai'):
            self.assertNotIn(name,sys.modules)


class CF019Boundary(unittest.TestCase):
    def test_exact_seventeen_inputs_and_single_focused_file(self):
        import hashlib
        from unittest.mock import patch
        from scripts import check_safe as c
        self.assertEqual(c.CF019_TESTS,('tests/unit/test_cf019_flow_display_quality.py',))
        self.assertEqual(len(c.CF019_INPUTS),17)
        self.assertEqual({k:v for k,v in c.CF019_INPUTS.items() if k in c.CF014_INPUTS},c.CF014_INPUTS)
        self.assertTrue(set(c.CF014_COMPAT)<=set(c.CF019_INPUTS))
        root=Path(__file__).resolve().parents[3]
        for name,digest in c.CF019_INPUTS.items():
            self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),digest)
            self.assertFalse(c.source_allowed(name+'.adjacent'))
        indexed=c.EXTRA | c.FLOW_INPUTS.keys() | c.CF004_INPUTS.keys() | c.CF005_INPUTS.keys() | {'backend/'+u for u in c.UNIT}
        raw=b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):copied=c.selected_sources(Path('/synthetic'),display_only=True)
        self.assertEqual({p for p in copied if p.startswith('ai/')},set(c.CF019_INPUTS))
        self.assertIn('frontend/tests/fixtures/cf019-flow-display-cases.json',copied)
    def test_public_display_modes_dispatch_only_the_new_capability(self):
        from unittest.mock import patch
        from scripts import check_safe as c
        for mode in ('display-self','display-unit'):
            with patch.object(c,'execute') as execute:
                self.assertEqual(c.main([mode]),0)
                self.assertTrue(execute.call_args.kwargs['display_only'])
                self.assertFalse(execute.call_args.kwargs['usage_only'])
                self.assertEqual(execute.call_args.args[1],('self-test' if mode.endswith('self') else 'unit',))
    def test_origin_and_graph_provider_boundaries_unchanged(self):
        import sys
        from scripts.safe_checks_bootstrap import valid_flow_origins
        from scripts.cf015_fundamental_check import load_origins
        load_origins();self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2],sys.modules))
        for name in ('pandas','openai','langchain_openai','agents.flow.infrastructure.render.builder','agents.flow.application.agent'):
            self.assertNotIn(name,sys.modules)


class CF020Boundary(unittest.TestCase):
    def test_exact_22_inputs_and_new_single_collection(self):
        import hashlib
        from scripts import check_safe as c
        self.assertEqual(c.CF020_TESTS,('tests/unit/test_cf020_supervisor_flow.py',))
        self.assertEqual(len(c.CF020_INPUTS),22)
        self.assertEqual({k:v for k,v in c.CF020_INPUTS.items() if k in c.CF018_INPUTS},c.CF018_INPUTS)
        root=Path(__file__).resolve().parents[3]
        for name,pin in c.CF020_INPUTS.items():self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),pin)
        from unittest.mock import patch
        indexed=c.EXTRA|c.FLOW_INPUTS.keys()|c.CF004_INPUTS.keys()|c.CF005_INPUTS.keys()|{'backend/'+u for u in c.UNIT}
        raw=b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):copied=c.selected_sources(Path('/synthetic'),supervisor_only=True)
        self.assertEqual({p for p in copied if p.startswith('ai/')},set(c.CF020_INPUTS))
    def test_public_modes_are_independent(self):
        from unittest.mock import patch
        from scripts import check_safe as c
        for mode in ('supervisor-self','supervisor-unit'):
            with patch.object(c,'execute') as run:
                self.assertEqual(c.main([mode]),0);self.assertTrue(run.call_args.kwargs['supervisor_only']);self.assertFalse(run.call_args.kwargs['display_only']);self.assertFalse(run.call_args.kwargs['usage_only'])
                self.assertEqual(run.call_args.args[1],('self-test' if mode.endswith('self') else 'unit',))
    def test_closed_loader_and_existing_origin_guard(self):
        import sys
        from scripts.cf020_supervisor_check import load_planner
        from scripts.safe_checks_bootstrap import valid_flow_origins
        load_planner();self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2],sys.modules))
        for name in ('src.api.dependencies','pandas','redis','openai','langchain_openai','src.agents.flow.application.agent'):self.assertNotIn(name,sys.modules)


class CF022Boundary(unittest.TestCase):
    def test_exact_inputs_and_collection(self):
        import hashlib
        from scripts import check_safe as c
        self.assertEqual(len(c.CF022_INPUTS),28);self.assertEqual(c.CF022_TESTS,('tests/unit/test_cf022_supervisor_core.py',))
        self.assertEqual({k:v for k,v in c.CF022_INPUTS.items() if k in c.CF020_INPUTS},c.CF020_INPUTS)
        root=Path(__file__).resolve().parents[3]
        for name,h in c.CF022_INPUTS.items():self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),h)
        from unittest.mock import patch
        indexed=c.EXTRA|c.FLOW_INPUTS.keys()|c.CF004_INPUTS.keys()|c.CF005_INPUTS.keys()|{'backend/'+u for u in c.UNIT}
        raw=b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):copied=c.selected_sources(root,core_only=True)
        self.assertIn(c.CF022_FIXTURE,copied)
        self.assertEqual({p for p in copied if p.startswith('ai/')},set(c.CF022_INPUTS))
    def test_independent_modes(self):
        from scripts import check_safe as c
        from unittest.mock import patch
        for mode in ('core-self','core-unit'):
            with patch.object(c,'execute') as run:
                self.assertEqual(c.main([mode]),0);self.assertTrue(run.call_args.kwargs['core_only']);self.assertFalse(run.call_args.kwargs['supervisor_only'])
    def test_closed_loader_and_existing_origin_guard(self):
        from scripts.cf022_supervisor_core_check import load_core
        from scripts.safe_checks_bootstrap import valid_flow_origins
        import sys
        load_core();self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2],sys.modules))
        for name in ('src.api.dependencies','pandas','openai','redis','src.agents.flow.application.agent'):self.assertNotIn(name,sys.modules)

class CF023Boundary(unittest.TestCase):
    def test_ai_lifespan_uses_explicit_default_off_runtime_without_import_time_configuration(self):
        import ast
        root=Path(__file__).resolve().parents[3]
        tree=ast.parse((root/'ai/src/main.py').read_text())
        lifecycle=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='lifespan')
        text=ast.unparse(lifecycle)
        self.assertIn('startup_options(os.environ)',text)
        self.assertIn('install_supervisor_meaning_runtime(options)',text)
        self.assertIn('finally:',text)
        app=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='app' for t in n.targets))
        self.assertEqual(next(v.value.id for v in app.keywords if v.arg=='lifespan'),'lifespan')
        factory=(root/'ai/src/supervisor/application/meaning_gateway_factory.py').read_text()
        imports=[n.module for n in ast.walk(ast.parse(factory)) if isinstance(n,ast.ImportFrom)]
        imports += [alias.name for n in ast.walk(ast.parse(factory)) if isinstance(n,ast.Import) for alias in n.names]
        self.assertFalse(any(name and name.startswith('dotenv') for name in imports))
        self.assertNotIn('getenv',factory)

    def test_preparation_public_deadline_source_and_existing_pin(self):
        import hashlib
        from scripts import check_safe as c
        root=Path(__file__).resolve().parents[3]
        name='backend/src/shared/http/access_boundary.py'
        self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),c.CF036_INPUTS[name])
        self.assertFalse(c.source_allowed(name+'.adjacent'))
        for path in ('backend/src/modules/supervisor/api/router.py','backend/src/modules/supervisor/application/preparation_service.py',name):
            self.assertIn(path,c.CF023_SOURCES)
        self.assertEqual(hashlib.sha256(c.regular_bytes(root,'backend/scripts/safe_checks_bootstrap.py')).hexdigest(),'2b4f706192b9ca20770b3005843d934bcdd44dace385168f84920904b9ca68a6')

    def test_runtime_exact_sources_and_closed_inputs(self):
        from scripts import check_safe as c
        import hashlib
        root=Path(__file__).resolve().parents[3]
        self.assertEqual(set(c.CF045_INPUTS),{'ai/src/supervisor/application/meaning_gateway_factory.py','ai/src/supervisor/infrastructure/backend/meaning_budget_client.py','ai/src/main.py'})
        self.assertEqual(len(c.CF023_INPUTS),32)
        for path,digest in c.CF045_INPUTS.items():
            self.assertTrue(c.source_allowed(path));self.assertFalse(c.source_allowed(path+'.adjacent'))
            self.assertEqual(hashlib.sha256(c.regular_bytes(root,path)).hexdigest(),digest)
        self.assertEqual(len(c.CF045_SOURCES),2)
        source=(root/'backend/scripts/cf002_interactive_login.py').read_text()
        self.assertIn('\"--verify-supervisor-meaning-runtime-db\", action=\"store_true\"',source)
        self.assertIn('verify_meaning_runtime(proof)',source)

    def test_accounting_exact_sources_and_owned_flag(self):
        from scripts import check_safe as c
        self.assertEqual(len(c.CF044_SOURCES),5)
        for path in c.CF044_SOURCES:
            self.assertIn(path,c.CF023_SOURCES)
            self.assertTrue(c.source_allowed(path))
            self.assertFalse(c.source_allowed(path+'.adjacent'))
        source=(Path(__file__).resolve().parents[2]/'scripts/cf002_interactive_login.py').read_text()
        self.assertIn('"--verify-supervisor-accounting-db", action="store_true"',source)
        self.assertIn('verify_meaning_accounting(proof)',source)

    def test_exact_inputs_and_collection(self):
        import hashlib
        from scripts import check_safe as c
        self.assertEqual(len(c.CF023_INPUTS),32)
        self.assertEqual(c.CF023_TESTS,('tests/unit/test_cf023_supervisor_meaning.py',))
        self.assertEqual({k:v for k,v in c.CF023_INPUTS.items() if k in c.CF022_INPUTS},c.CF022_INPUTS)
        root=Path(__file__).resolve().parents[3]
        for name,h in c.CF023_INPUTS.items():self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),h)
        from unittest.mock import patch
        indexed=c.EXTRA|c.FLOW_INPUTS.keys()|c.CF004_INPUTS.keys()|c.CF005_INPUTS.keys()|{'backend/'+u for u in c.UNIT}
        raw=b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):copied=c.selected_sources(root,meaning_only=True)
        self.assertEqual({p for p in copied if p.startswith('ai/')},set(c.CF023_INPUTS)|set(c.CF045_INPUTS))
        self.assertIn(c.CF023_FIXTURE,copied)
    def test_independent_modes(self):
        from scripts import check_safe as c
        from unittest.mock import patch
        for mode in ('meaning-self','meaning-unit'):
            with patch.object(c,'execute') as run:
                self.assertEqual(c.main([mode]),0)
                self.assertTrue(run.call_args.kwargs['meaning_only'])
                self.assertFalse(run.call_args.kwargs['core_only'])
    def test_closed_loader_and_existing_origin_guard(self):
        from scripts.cf023_supervisor_meaning_check import load_meaning
        from scripts.safe_checks_bootstrap import valid_flow_origins
        import sys
        load_meaning()
        self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2],sys.modules))
        from src.modules.supervisor.domain import contracts
        proposals=sys.modules['src.supervisor.domain.meaning_proposals']
        meaning=sys.modules['src.supervisor.domain.meaning']
        self.assertEqual(proposals.semantic_spec(),contracts.MEANING_SPEC)
        self.assertEqual(meaning.sha(proposals.semantic_spec()),contracts.MEANING_SPEC_SHA256)
        for name in ('src.api.dependencies','pandas','openai','redis','src.agents.flow.application.agent'):self.assertNotIn(name,sys.modules)

class CF024Boundary(unittest.TestCase):
    def test_exact_existing_inputs_new_single_collection(self):
        import hashlib
        from scripts import check_safe as c
        self.assertEqual(len(c.CF023_INPUTS),32)
        self.assertEqual(c.CF024_TESTS,('tests/unit/test_cf024_supervisor_live_verifier.py',))
        root=Path(__file__).resolve().parents[3]
        for name,h in c.CF023_INPUTS.items():self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),h)
        from unittest.mock import patch
        indexed=c.EXTRA|c.FLOW_INPUTS.keys()|c.CF004_INPUTS.keys()|c.CF005_INPUTS.keys()|{'backend/'+u for u in c.UNIT}
        raw=b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):copied=c.selected_sources(root,assembly_only=True)
        self.assertEqual({p for p in copied if p.startswith('ai/')},set(c.CF023_INPUTS)|set(c.CF045_INPUTS))
    def test_fixed_modes(self):
        from scripts import check_safe as c
        from unittest.mock import patch
        for mode in ('meaning-assembly-self','meaning-assembly-unit'):
            with patch.object(c,'execute') as run:
                self.assertEqual(c.main([mode]),0)
                self.assertTrue(run.call_args.kwargs['assembly_only'])
                self.assertFalse(run.call_args.kwargs['meaning_only'])
    def test_default_live_stays_closed_and_original_origin_guard(self):
        import asyncio,sys
        from scripts.cf023_supervisor_meaning_check import load_meaning,verify_live
        from scripts.safe_checks_bootstrap import valid_flow_origins
        load_meaning()
        with self.assertRaises(sys.modules['src.supervisor.infrastructure.meaning_gateway'].CounterUnavailable):asyncio.run(verify_live())
        self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2],sys.modules))

class CF026Boundary(unittest.TestCase):
    def test_closed_provider0_recovery_is_fixed_and_keeps_original_controller(self):
        source=(Path(__file__).resolve().parents[2]/'scripts/cf026_successor.py').read_text()
        for value in ('CF037_ORDINAL4_CLOSED_PROVIDER0_RECOVERY_ONCE',
                      'poststart-provider0-recovery1.json','def check_closed_provider0_recovery(',
                      'def create_recovery_claim(','st_mtime_ns,info.st_ctime_ns',
                      'UUID(str(fresh.id))','not isinstance(fresh.id, UUID)'):
            self.assertIn(value,source)
        self.assertIn('if self.state["status"] != "offered":\n                raise Closed("ALREADY_USED")',source)

    def test_fixed_post_alignment_selection_preserves_controller(self):
        import hashlib
        from scripts import check_safe as c
        root=Path(__file__).resolve().parents[3]
        self.assertEqual(hashlib.sha256(c.regular_bytes(root,'backend/scripts/cf026_supervisor_live_controller.py')).hexdigest(),'c6a93f1de94e462306dce02aaad15319fc342dcd24e1c21f813b78fd6481ce08')
        self.assertEqual(len(c.CF023_INPUTS),32)
        self.assertEqual(c.CF023_INPUTS['ai/src/supervisor/application/meaning_policy.py'],'b1efe0bec8c2a27031b9ba26a2d390d49c874776c6a4ec5c8646dc024951dbe0')
        self.assertEqual(c.CF023_INPUTS['ai/src/supervisor/prompts/meaning.txt'],'0456f2afc6939b45a61c6d59159bd42a8e807647c656b15fb7ed23a0bf7714c4')
        self.assertFalse(c.source_allowed('backend/scripts/cf026_successor_extra.py'))

    def test_exact_new_inputs_and_existing_pins(self):
        import hashlib
        from unittest.mock import patch
        from scripts import check_safe as c
        root = Path(__file__).resolve().parents[3]
        self.assertEqual(c.CF026_TESTS, ('tests/unit/test_cf026_supervisor_live_controller.py',))
        self.assertEqual(len(c.CF023_INPUTS), 32)
        for name, value in c.CF023_INPUTS.items():
            self.assertEqual(hashlib.sha256(c.regular_bytes(root, name)).hexdigest(), value)
        indexed = c.EXTRA | c.FLOW_INPUTS.keys() | c.CF004_INPUTS.keys() | c.CF005_INPUTS.keys() | {'backend/' + u for u in c.UNIT}
        raw = b''.join(('100644 ' + '0'*40 + ' 0\t' + p + '\0').encode() for p in sorted(indexed))
        with patch.object(c.subprocess, 'check_output', return_value=raw):
            copied = c.selected_sources(root, controller_only=True)
            assembly_copied = c.selected_sources(root, assembly_only=True)
        self.assertNotIn("backend/scripts/cf026_successor.py", assembly_copied)
        self.assertEqual({p for p in copied if p.startswith('ai/')}, set(c.CF023_INPUTS)|set(c.CF045_INPUTS))
        self.assertIn('backend/scripts/cf026_supervisor_live_controller.py', copied)
        self.assertIn('backend/scripts/cf026_successor.py', copied)
        self.assertNotIn('backend/scripts/cf026_successor_other.py', copied)
        self.assertIn('backend/tests/unit/test_cf026_supervisor_live_controller.py', copied)

    def test_fixed_selection_keeps_existing_worker(self):
        from unittest.mock import patch
        from scripts import check_safe as c
        for mode in ('live-controller-self', 'live-controller-unit'):
            with patch.object(c, 'execute') as run:
                self.assertEqual(c.main([mode]), 0)
                self.assertTrue(run.call_args.kwargs['controller_only'])
                self.assertFalse(run.call_args.kwargs['assembly_only'])

    def test_controller_import_and_default_have_no_runtime_actions(self):
        import asyncio
        from scripts import cf026_supervisor_live_controller as controller
        from scripts import cf026_successor as successor
        with self.assertRaisesRegex(successor.Closed, "DEFAULT_UNAVAILABLE"):
            asyncio.run(successor.run())
        with self.assertRaisesRegex(controller.ControllerError, 'LIVE_GATE_CLOSED'):
            asyncio.run(controller.run_controller(None))
        import sys
        for name in ('scripts.runner_owned_database', 'src.shared.config', 'openai', 'src.api.main'):
            self.assertNotIn(name, sys.modules)

class CF021Boundary(unittest.TestCase):
    def test_exact_pins_and_single_collection(self):
        import hashlib
        from unittest.mock import patch
        from scripts import check_safe as c
        root=Path(__file__).resolve().parents[3]
        self.assertEqual(len(c.CF021_INPUTS),29)
        self.assertEqual({k:v for k,v in c.CF021_INPUTS.items() if k in c.CF018_INPUTS},c.CF018_INPUTS)
        self.assertEqual(c.CF021_TESTS,('tests/unit/test_cf021_technical_boundary.py',))
        for name,h in (c.CF021_INPUTS | c.CF021_FIXED_INPUTS).items():
            self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),h)
            self.assertFalse(c.source_allowed(name+'.adjacent'))
        indexed=c.EXTRA|c.FLOW_INPUTS.keys()|c.CF004_INPUTS.keys()|c.CF005_INPUTS.keys()|{'backend/'+u for u in c.UNIT}
        raw=b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):copied=c.selected_sources(root,technical_boundary_only=True)
        self.assertEqual({p for p in copied if p.startswith('ai/')},set(c.CF021_INPUTS))
        self.assertEqual({p for p in copied if p.startswith('frontend/')},{p for p in c.CF021_FIXED_INPUTS if p.startswith('frontend/')})

    def test_fixed_modes_and_no_existing_dispatch_change(self):
        from unittest.mock import patch
        from scripts import check_safe as c
        for mode in ('technical-boundary-self','technical-boundary-unit'):
            with patch.object(c,'execute') as run:
                self.assertEqual(c.main([mode]),0)
                self.assertTrue(run.call_args.kwargs['technical_boundary_only'])
                self.assertFalse(run.call_args.kwargs['controller_only'])
        self.assertEqual(c.main(['list']),0)

    def test_closed_absolute_loader_existing_origin_guards(self):
        from tests.unit import test_cf021_technical_boundary as boundary
        from scripts.safe_checks_bootstrap import valid_flow_origins
        import sys
        boundary.load_boundary()
        self.assertFalse(boundary.ATTEMPTS)
        self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2],sys.modules))
        for name in boundary.FORBIDDEN:self.assertNotIn(name,sys.modules)

class CF031Boundary(unittest.TestCase):
    def test_exact_new_pins_and_preserved_ai_fixed_inputs(self):
        import hashlib
        from unittest.mock import patch
        from scripts import check_safe as c
        root = Path(__file__).resolve().parents[3]
        self.assertEqual(c.CF031_TESTS, ('tests/unit/test_cf031_technical_boundary_restore.py',))
        self.assertEqual(set(c.CF031_INPUTS), {
            'backend/src/modules/technical/application/boundary_restore.py',
            'frontend/tests/fixtures/cf031-technical-boundary-read.json',
        })
        self.assertEqual(len(c.CF021_INPUTS), 29)
        self.assertEqual(len(c.CF021_FIXED_INPUTS), 9)
        for name, sha in (c.CF021_INPUTS | c.CF021_FIXED_INPUTS | c.CF031_INPUTS).items():
            self.assertEqual(hashlib.sha256(c.regular_bytes(root, name)).hexdigest(), sha)
            self.assertFalse(c.source_allowed(name + '.adjacent'))
        indexed = c.EXTRA | c.FLOW_INPUTS.keys() | c.CF004_INPUTS.keys() | c.CF005_INPUTS.keys() | {'backend/' + u for u in c.UNIT}
        raw = b''.join(('100644 ' + '0' * 40 + ' 0\t' + name + '\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess, 'check_output', return_value=raw):
            copied = c.selected_sources(root, technical_read_only=True)
            prior = c.selected_sources(root, technical_boundary_only=True)
        self.assertEqual({p for p in copied if p.startswith('ai/')}, set(c.CF021_INPUTS))
        self.assertEqual({p for p in copied if p.startswith('frontend/')},
            {p for p in c.CF021_FIXED_INPUTS | c.CF031_INPUTS if p.startswith('frontend/')})
        self.assertNotIn('frontend/tests/fixtures/cf031-technical-boundary-read.json', prior)

    def test_exact_modes_select_single_new_test_without_changing_old_mode(self):
        from unittest.mock import patch
        from scripts import check_safe as c
        for mode in ('technical-read-self', 'technical-read-unit'):
            with patch.object(c, 'execute') as run:
                self.assertEqual(c.main([mode]), 0)
                self.assertTrue(run.call_args.kwargs['technical_read_only'])
                self.assertFalse(run.call_args.kwargs['technical_boundary_only'])
                self.assertEqual(run.call_args.args[1], ('self-test' if mode.endswith('self') else 'unit',))
        with patch.object(c, 'execute') as run:
            c.main(['technical-boundary-unit'])
            self.assertTrue(run.call_args.kwargs['technical_boundary_only'])
            self.assertFalse(run.call_args.kwargs['technical_read_only'])

    def test_closed_loader_and_existing_origin_guard_are_reused(self):
        from tests.unit import test_cf021_technical_boundary as loader
        from scripts import check_safe as c
        from scripts.safe_checks_bootstrap import valid_flow_origins
        import sys
        loader.load_boundary()
        loader._load('src.modules.technical.application.boundary_restore',
            'backend/src/modules/technical/application/boundary_restore.py', c.CF031_INPUTS)
        self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2], sys.modules))
        self.assertFalse(loader.ATTEMPTS)
        for name in loader.FORBIDDEN:
            self.assertNotIn(name, sys.modules)


class CF035Boundary(unittest.TestCase):
    def test_exact_selection_and_unchanged_origin_inputs(self):
        import hashlib
        from unittest.mock import patch
        from scripts import check_safe as c
        root = Path(__file__).resolve().parents[3]
        self.assertEqual(c.CF035_TESTS,('tests/unit/test_cf035_technical_owned_storage.py',))
        self.assertEqual(len(c.CF035_COMPAT),6)
        for name,digest in (c.CF035_COMPAT | c.CF035_INPUTS).items():
            self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),digest)
            self.assertFalse(c.source_allowed(name+'.adjacent'))
        indexed = c.EXTRA | c.FLOW_INPUTS.keys() | c.CF004_INPUTS.keys() | c.CF005_INPUTS.keys() | {'backend/'+u for u in c.UNIT}
        raw = b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):
            selection = c.selected_sources(root,technical_owned_only=True)
        self.assertEqual({p for p in selection if p.startswith('ai/')},set(c.CF035_COMPAT))
        self.assertEqual({p for p in selection if p.startswith('frontend/')},
                         {'frontend/tests/fixtures/cf031-technical-boundary-read.json'})
        self.assertNotIn('backend/scripts/cf026_successor.py',selection)
        self.assertNotIn('backend/scripts/cf026_supervisor_live_controller.py',selection)
        self.assertTrue(c.CF035_SOURCES <= set(selection))

    def test_fixed_modes_and_db_only_dispatch_without_bootstrap(self):
        import ast
        from unittest.mock import patch
        from scripts import check_safe as c
        for mode in ('technical-owned-self','technical-owned-unit'):
            with patch.object(c,'execute') as run:
                self.assertEqual(c.main([mode]),0)
                self.assertTrue(run.call_args.kwargs['technical_owned_only'])
                self.assertFalse(run.call_args.kwargs['technical_read_only'])
                self.assertEqual(run.call_args.args[1],('self-test' if mode.endswith('self') else 'unit',))
        source = (Path(__file__).resolve().parents[2]/'scripts/cf002_interactive_login.py').read_text()
        tree = ast.parse(source)
        conditions = [n for n in ast.walk(tree) if isinstance(n,ast.If) and
                      isinstance(n.test,ast.Attribute) and n.test.attr == 'verify_technical_owned_db']
        self.assertEqual(len(conditions),1)
        block = ast.unparse(conditions[0])
        self.assertIn('timeout=180',block)
        self.assertIn('verify_technical_owned(proof)',block)
        self.assertIsInstance(conditions[0].body[-1],ast.Return)
        self.assertIn('args.verify_technical_owned_db or args.verify_supervisor_meaning_assembly_db',source)
        self.assertIn('--verify-technical-owned-db',source)

    def test_real_six_file_loader_and_worker_guard_unchanged(self):
        import sys
        from scripts.safe_checks_bootstrap import valid_flow_origins
        from tests.unit import test_cf035_technical_owned_storage as unit
        unit.load_flow_compat()
        self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2],sys.modules))
        for name in ('src.shared.config','src.api.main','src.agents.technical.application.agent',
                     'src.modules.technical.application.report_service','openai'):
            self.assertNotIn(name,sys.modules)


class CF036Boundary(unittest.TestCase):
    def test_exact_selection_and_existing_flow_origin_inputs(self):
        import hashlib
        from unittest.mock import patch
        from scripts import check_safe as c
        root=Path(__file__).resolve().parents[3]
        self.assertEqual(c.CF036_TESTS,('tests/unit/test_cf036_technical_owned_read.py',))
        self.assertEqual(len(c.CF035_COMPAT),6)
        for name,digest in (c.CF035_COMPAT | c.CF035_INPUTS | c.CF036_INPUTS).items():
            self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),digest)
            self.assertFalse(c.source_allowed(name+'.adjacent'))
        indexed=c.EXTRA | c.FLOW_INPUTS.keys() | c.CF004_INPUTS.keys() | c.CF005_INPUTS.keys() | {'backend/'+u for u in c.UNIT}
        raw=b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):selection=c.selected_sources(root,technical_owned_read_only=True)
        self.assertEqual({p for p in selection if p.startswith('ai/')},set(c.CF035_COMPAT))
        self.assertEqual({p for p in selection if p.startswith('frontend/')},{'frontend/tests/fixtures/cf031-technical-boundary-read.json','frontend/tests/fixtures/cf036-technical-owned-read.json'})
        self.assertTrue(c.CF036_SOURCES <= set(selection))
        for name in ('backend/scripts/cf026_successor.py','backend/scripts/cf026_supervisor_live_controller.py'):
            self.assertNotIn(name,selection)

    def test_fixed_read_modes_and_owned_database_branch(self):
        import ast
        from unittest.mock import patch
        from scripts import check_safe as c
        for mode in ('technical-owned-read-self','technical-owned-read-unit'):
            with patch.object(c,'execute') as run:
                self.assertEqual(c.main([mode]),0)
                self.assertTrue(run.call_args.kwargs['technical_owned_read_only'])
                self.assertFalse(run.call_args.kwargs['technical_owned_only'])
                self.assertEqual(run.call_args.args[1],('self-test' if mode.endswith('self') else 'unit',))
        source=(Path(__file__).resolve().parents[2]/'scripts/cf002_interactive_login.py').read_text()
        tree=ast.parse(source)
        branches=[n for n in ast.walk(tree) if isinstance(n,ast.If) and isinstance(n.test,ast.Attribute) and n.test.attr=='verify_technical_owned_read_db']
        self.assertEqual(len(branches),1)
        self.assertIn('verify_technical_owned_read(proof)',ast.unparse(branches[0]))
        self.assertIsInstance(branches[0].body[-1],ast.Return)
        self.assertIn('--verify-technical-owned-read-db',source)

    def test_actual_readonly_loader_without_application_or_engine(self):
        import sys
        from scripts.safe_checks_bootstrap import valid_flow_origins
        from tests.unit import test_cf036_technical_owned_read as unit
        unit.load_readonly()
        self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2],sys.modules))
        self.assertFalse(unit.ATTEMPTS)
        for name in ('src.api.main','openai','src.agents.technical.application.agent','tests.unit.test_cf021_technical_boundary'):
            self.assertNotIn(name,sys.modules)

class CF040Boundary(unittest.TestCase):
    def test_exact_four_inputs_six_origins_and_single_collection(self):
        import hashlib
        from unittest.mock import patch
        from scripts import check_safe as c
        root=Path(__file__).resolve().parents[3]
        self.assertEqual(c.CF040_TESTS,('tests/unit/test_cf040_technical_runtime_setup.py',))
        self.assertEqual(c.CF040_COMPAT,c.CF035_COMPAT)
        self.assertEqual(len(c.CF040_COMPAT),6)
        self.assertEqual(set(c.CF040_INPUTS),{
            'ai/src/agents/technical/config.py','ai/src/api/dependencies.py',
            'ai/src/agents/technical/domain/intraday_limits.py','ai/src/shared/runtime/deadline.py'})
        self.assertEqual(c.CF021_INPUTS['ai/src/agents/technical/config.py'],c.CF040_INPUTS['ai/src/agents/technical/config.py'])
        for name,digest in (c.CF040_COMPAT | c.CF040_INPUTS).items():
            self.assertEqual(hashlib.sha256(c.regular_bytes(root,name)).hexdigest(),digest)
            self.assertFalse(c.source_allowed(name+'.adjacent'))
        indexed=c.EXTRA | c.FLOW_INPUTS.keys() | c.CF004_INPUTS.keys() | c.CF005_INPUTS.keys() | {'backend/'+u for u in c.UNIT}
        raw=b''.join(('100644 '+'0'*40+' 0\t'+name+'\0').encode() for name in sorted(indexed))
        with patch.object(c.subprocess,'check_output',return_value=raw):selected=c.selected_sources(root,technical_runtime_only=True)
        self.assertEqual({p for p in selected if p.startswith('ai/')},set(c.CF040_COMPAT | c.CF040_INPUTS))
        self.assertFalse(any(p.startswith('frontend/') for p in selected))
        self.assertTrue(c.CF040_SOURCES <= set(selected))
        for name in ('backend/scripts/cf026_successor.py','backend/scripts/cf026_supervisor_live_controller.py',
                     'ai/src/agents/technical/application/agent.py','ai/src/agents/technical/application/orchestration/technical_graph.py'):
            self.assertNotIn(name,selected)

    def test_fixed_runtime_modes_preserve_existing_dispatch(self):
        from unittest.mock import patch
        from scripts import check_safe as c
        for mode in ('technical-runtime-self','technical-runtime-unit'):
            with patch.object(c,'execute') as run:
                self.assertEqual(c.main([mode]),0)
                self.assertTrue(run.call_args.kwargs['technical_runtime_only'])
                self.assertFalse(run.call_args.kwargs['technical_boundary_only'])
                self.assertFalse(run.call_args.kwargs['technical_owned_read_only'])
                self.assertEqual(run.call_args.args[1],('self-test' if mode.endswith('self') else 'unit',))

    def test_actual_import_probe_origin_and_original_access_boundary(self):
        import sys
        from tests.unit import test_cf040_technical_runtime_setup as unit
        from scripts.safe_checks_bootstrap import valid_flow_origins,read_allowed
        unit.load_readonly()
        self.assertTrue(valid_flow_origins(Path(__file__).resolve().parents[2],sys.modules))
        self.assertFalse(unit.COLLECTION_PROBE.events)
        self.assertFalse(unit.COLLECTION_PROBE.loads)
        self.assertFalse(unit.COLLECTION_PROBE.io)
        self.assertFalse(any(name=='dotenv' for name,_ in unit.COLLECTION_PROBE.imports))
        self.assertFalse(read_allowed(Path('/unapproved-original/ai/src/agents/technical/config.py'),Path('/owned'),Path('/site'),Path('/runtime')))
        self.assertFalse(read_allowed(Path('/unapproved-original/.env'),Path('/owned'),Path('/site'),Path('/runtime')))
        self.assertNotIn('src.api.dependencies',sys.modules)
        self.assertNotIn('tests.unit.test_cf021_technical_boundary',sys.modules)
        for name in unit.LATE:self.assertNotIn(name,sys.modules)

if __name__ == "__main__":
    import json, sys
    focused=json.loads(Path(sys.argv[1]).read_text()).get("cf012_self_only",False)
    adapter_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf013_self_only",False)
    quality_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf014_self_only",False)
    fundamental_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf015_self_only",False)
    errors_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf017_self_only",False)
    usage_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf018_self_only",False)
    display_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf019_self_only",False)
    supervisor_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf020_self_only",False)
    core_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf022_self_only",False)
    meaning_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf023_self_only",False)
    assembly_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf024_self_only",False)
    controller_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf026_self_only",False)
    technical_boundary_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf021_self_only",False)
    technical_read_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf031_self_only",False)
    technical_owned_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf035_self_only",False)
    technical_owned_read_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf036_self_only",False)
    technical_runtime_focused=json.loads(Path(sys.argv[1]).read_text()).get("cf040_self_only",False)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CF040Boundary if technical_runtime_focused else CF036Boundary if technical_owned_read_focused else CF035Boundary if technical_owned_focused else CF031Boundary if technical_read_focused else CF021Boundary if technical_boundary_focused else CF026Boundary if controller_focused else CF024Boundary if assembly_focused else CF023Boundary if meaning_focused else CF022Boundary if core_focused else CF020Boundary if supervisor_focused else CF019Boundary if display_focused else CF018Boundary if usage_focused else CF017Boundary if errors_focused else CF015Boundary if fundamental_focused else CF014Boundary if quality_focused else CF013Boundary if adapter_focused else CF012Boundary if focused else EntryBoundary)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
