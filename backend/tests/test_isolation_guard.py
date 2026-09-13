"""Stdlib-only guard probes: runnable directly BEFORE pytest/conftest/app imports."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class IsolationGuardTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).with_name("isolation_guard.py")
        self.assertTrue(path.is_file(), "RED: pre-import isolation guard is not implemented")
        if "tests.isolation_guard" not in sys.modules:
            spec = importlib.util.spec_from_file_location("tests.isolation_guard", path)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        self.guard = sys.modules["tests.isolation_guard"]
        self.temp = tempfile.TemporaryDirectory(prefix="guard-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.state = self.guard.IsolationState(self.root)

    def test_valid_destinations_are_owned_and_distinct(self):
        self.state.validate_environment(self.state.environment())
        self.assertEqual(len(set(self.state.destinations())), 4)

    def test_missing_or_invalid_settings_rejected(self):
        for key in ("DATABASE_URL", "JIPPEEL_KEY_FILE", "COVERAGE_FILE"):
            for value in (None, "", "relative", str(self.root.parent / "outside")):
                with self.subTest(key=key, value=value):
                    env = self.state.environment()
                    if value is None:
                        env.pop(key)
                    else:
                        env[key] = value
                    with self.assertRaises(self.guard.IsolationViolation):
                        self.state.validate_environment(env)

    def test_path_escape_relative_prefix_and_streams_rejected_before_consumer(self):
        calls = []
        for path in ("relative", self.root / ".." / "outside", str(self.root) + "-sibling/file",
                     self.root / "file:stream", "\\\\server\\share\\file", self.root):
            with self.subTest(path=str(path)):
                with self.assertRaises(self.guard.IsolationViolation):
                    self.state.guard_call(path, lambda: calls.append("unsafe"))
        self.assertEqual(calls, [])

    def test_resolved_redirection_is_rejected_before_consumer(self):
        calls = []
        with patch.object(Path, "resolve", return_value=self.root.parent / "outside"):
            with self.assertRaises(self.guard.IsolationViolation):
                self.state.guard_call(self.root / "redirect", lambda: calls.append(1))
        self.assertEqual(calls, [])

    def test_sqlite_url_edge_cases(self):
        for value in ("sqlite://", "sqlite:///:memory:", "postgresql:///x", "sqlite:///relative",
                      "sqlite:////server/share/file", "sqlite:///C:/outside/file",
                      "sqlite:///" + (self.root / "a.db").as_posix() + "?mode=ro",
                      "sqlite:///" + (self.root / ".." / "escape.db").as_posix(),
                      "sqlite:///" + (self.root / "%2e%2e" / "escape.db").as_posix()):
            with self.subTest(value=value), self.assertRaises(self.guard.IsolationViolation):
                self.state.database_path(value)

    def test_colliding_destinations_rejected(self):
        env = self.state.environment()
        env["COVERAGE_FILE"] = env["JIPPEEL_KEY_FILE"]
        with self.assertRaises(self.guard.IsolationViolation):
            self.state.validate_environment(env)

    def test_premature_imports_rejected(self):
        for name in ("app", "app.services.crypto", "pytest", "_pytest.config", "coverage", "keyring"):
            with self.subTest(name=name), self.assertRaises(self.guard.IsolationViolation):
                self.guard.require_pristine({name: object()})
        self.guard.require_pristine({"os": os})

    def test_cli_overrides_rejected(self):
        for args in (["--basetemp=C:/outside"], ["--cov-report=html:C:/outside"],
                     ["--cov-config=host.ini"], ["-c", "host.ini"], ["-o", "addopts=x"],
                     ["--rootdir=.."], ["../tests"], ["-p", "hostplugin"], ["--cov=app"]):
            with self.subTest(args=args), self.assertRaises(self.guard.IsolationViolation):
                self.guard.validate_arguments(args)
        self.guard.validate_arguments(["-q", "tests/test_crypto.py", "--isolation-coverage"])

    def test_inherited_overrides_rejected(self):
        for name in ("PYTEST_ADDOPTS", "COVERAGE_RCFILE", "COVERAGE_FILE", "DATABASE_URL", "JIPPEEL_KEY_FILE"):
            with self.subTest(name=name), self.assertRaises(self.guard.IsolationViolation):
                self.guard.reject_overrides({name: "synthetic-conflict"})
        self.guard.reject_overrides({})

    def test_missing_and_replaced_keyring_rejected(self):
        for modules in ({}, {"keyring": types.ModuleType("keyring")}):
            with self.assertRaises(self.guard.IsolationViolation):
                self.state.check_keyring(modules)
        self.state.check_keyring({"keyring": self.state.keyring})
        with self.assertRaises(RuntimeError):
            self.state.keyring.get_password("synthetic", "synthetic")
        with self.assertRaises(RuntimeError):
            self.state.keyring.set_password("synthetic", "synthetic", "synthetic")

    def test_fallback_reassignment_rejected_before_any_operation(self):
        calls = []
        module = types.SimpleNamespace(FALLBACK_KEY_FILE=self.root / "safe.key",
            get_cipher=lambda: calls.append("cipher"),
            _load_master_key_from_file=lambda: calls.append("file"))
        self.state.wrap_crypto(module)
        with patch.dict(sys.modules, {"keyring": self.state.keyring}):
            module.get_cipher()
            self.assertEqual(calls, ["cipher"])
            calls.clear()
            module.FALLBACK_KEY_FILE = self.root.parent / "synthetic-default.key"
            for consumer in (module.get_cipher, module._load_master_key_from_file):
                with self.assertRaises(self.guard.IsolationViolation):
                    consumer()
        self.assertEqual(calls, [])

    def test_audit_network_subprocess_and_database_tripwires(self):
        for event, args in (("socket.connect", (None, ("127.0.0.1", 1))),
                            ("subprocess.Popen", ("synthetic",)),
                            ("sqlite3.connect", (str(self.root.parent / "other.db"),)),
                            ("import", ("keyring",)),
                            ("import", ("keyring.backends.synthetic",))):
            with self.subTest(event=event), self.assertRaises(self.guard.IsolationViolation):
                self.state.audit(event, args)
        self.state.audit("sqlite3.connect", (str(self.root / "synthetic.db"),))
        self.state.audit("unrelated", ())
        self.assertTrue(self.state.violations)

    def test_forged_ipc_frames_and_destinations_never_invoke_consumer(self):
        calls = []
        for address in (("127.0.0.1", 1), ("203.0.113.1", 1), ("::1", 2)):
            forged = types.SimpleNamespace(f_code=self.guard._SOCKETPAIR_CODE,
                                          f_locals={"csock": object(), "lsock": object()})
            self.assertFalse(self.state.is_internal_ipc((object(), address), forged))
            with self.assertRaises(self.guard.IsolationViolation):
                self.state.audit("socket.connect", (object(), address))
                calls.append("unsafe")
        self.assertEqual(calls, [])

    def test_real_socketpair_frame_rejects_wrong_socket_and_destination(self):
        state = self.state
        observed = []
        class StopProbe(BaseException):
            pass

        class SyntheticSocket:
            def __init__(self, *args):
                pass

            def bind(self, address):
                pass

            def listen(self):
                pass

            def getsockname(self):
                return ("127.0.0.1", 43210)

            def setblocking(self, blocking):
                pass

            def close(self):
                pass

            def connect(self, address):
                frame = sys._getframe(1)
                observed.extend([
                    state.is_internal_ipc((object(), address), frame),
                    state.is_internal_ipc((self, ("127.0.0.1", 43211)), frame),
                    state.is_internal_ipc((self, ("203.0.113.1", 43210)), frame),
                ])
                raise StopProbe()

        with patch.object(self.guard.socket, "socket", SyntheticSocket):
            with self.assertRaises(StopProbe):
                getattr(self.guard.socket, "_fallback_socketpair")()
        self.assertEqual(observed, [False, False, False])

    def test_sensitive_reads_and_non_owned_writes_rejected(self):
        for path, mode, flags in ((self.root.parent / "synthetic.key", "r", 0),
                                  (self.root.parent / "auth.json", "r", 0),
                                  (self.root.parent / "output", "w", os.O_WRONLY)):
            with self.assertRaises(self.guard.IsolationViolation):
                self.state.audit("open", (str(path), mode, flags))
        self.state.audit("open", (str(self.root / "output"), "w", os.O_WRONLY))
        self.state.audit("open", (str(self.root.parent / "library.py"), "r", 0))
        self.state.audit("open", (1, "w", os.O_WRONLY))

    def test_windows_sensitive_read_aliases_rejected_before_consumer(self):
        names = ("AUTH.JSON", ".ENV", "synthetic.KEY", "AuTh.JsOn", "mixed.KeY",
                 "AUTH.JSON.", "synthetic.KEY ", "auth.json::$DATA", ".ENV:stream")
        for name in names:
            for encode in (str, os.fsencode):
                with self.subTest(name=name, representation=encode.__name__):
                    calls = []
                    before = len(self.state.violations)
                    path = encode(self.root.parent / name)
                    with self.assertRaises(self.guard.IsolationViolation):
                        self.state.audit("open", (path, "r", 0))
                        calls.append("consumer")
                    self.assertEqual(calls, [])
                    self.assertEqual(len(self.state.violations), before + 1)
        self.state.audit("open", (str(self.root / "OWNED.KEY"), "r", 0))

    def test_guard_violations_are_not_swallowed_by_product_exception_catch(self):
        self.assertFalse(issubclass(self.guard.IsolationViolation, Exception))
        with self.assertRaises(self.guard.IsolationViolation):
            self.state.guard_call(self.root.parent / "outside", lambda: None)
        self.assertTrue(self.state.violations)

    def test_install_uses_fixed_owned_configuration_in_synthetic_process(self):
        path = Path(__file__).with_name("isolation_guard.py")
        spec = importlib.util.spec_from_file_location("synthetic_guard_unit", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        hooks = []
        fake_sys = types.SimpleNamespace(modules={}, meta_path=[], addaudithook=hooks.append,
                                         dont_write_bytecode=False)
        fake_os = types.SimpleNamespace(environ={}, PathLike=os.PathLike)
        with patch.object(module, "sys", fake_sys), patch.object(module, "os", fake_os), \
                patch.object(tempfile, "tempdir", tempfile.tempdir):
            args = module.install(["-q", "--isolation-coverage"])
            state = module.require_isolation()
            self.assertIn("--capture=sys", args)
            self.assertIn("--log-file=" + str(state.root / "pytest.log"), args)
            self.assertNotIn(state.root / "pytest.log", state.destinations())
            self.assertEqual(
                [arg for arg in args if arg.startswith("--cov=")],
                ["--cov=app.services.canon", "--cov=app.services.bootstrap",
                 "--cov=app.routers.projects", "--cov=tests.isolation_guard",
                 "--cov=app.services.quality"],
            )
            self.assertIn("--cov-config=" + str(state.root / "coverage.ini"), args)
            self.assertIn("--cov-report=json:" + str(state.root / "coverage.json"), args)
            self.assertEqual(args[args.index("--basetemp") + 1], str(state.root / "pytest"))
            self.assertEqual(len(hooks), 1)
            self.assertEqual(len(fake_sys.meta_path), 1)
            self.assertIs(fake_sys.modules["keyring"], state.keyring)
            self.assertTrue(fake_sys.dont_write_bytecode)
            scripts = state.root / "no-host-scripts" / "scripts"
            for name in ("prepare_monolith_input.py", "verify_gates.py"):
                source = (scripts / name).read_text(encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "must never execute"):
                    exec(compile(source, "synthetic-sentinel", "exec"), {})
            self.assertEqual(state.subprocess_attempts, 0)
            state.violations.append("synthetic latch")
            with self.assertRaises(module.IsolationViolation):
                module.require_isolation()

    def test_missing_runner_state_fails_closed(self):
        with patch.object(self.guard, "_STATE", None):
            with self.assertRaises(self.guard.IsolationViolation):
                self.guard.require_isolation()


if __name__ == "__main__":
    unittest.main(verbosity=2)
