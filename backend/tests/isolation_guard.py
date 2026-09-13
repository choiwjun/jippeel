"""Test-only, stdlib pre-import isolation. Never imported by production code."""
import functools
import importlib.abc
import importlib.machinery
import json
import os
from pathlib import Path
import sys
import socket
import _socket
import tempfile
import types
from typing import NoReturn


_SOCKETPAIR_CODE = None if hasattr(_socket, "socketpair") else getattr(socket, "_fallback_socketpair").__code__


class IsolationViolation(BaseException):
    """Fatal even across product code's ordinary Exception fallback handlers."""


def require_pristine(modules):
    forbidden = {"app", "pytest", "_pytest", "coverage", "pytest_cov", "keyring"}
    if any(name.split(".")[0] in forbidden for name in modules):
        raise IsolationViolation("isolation must precede all protected imports")


def reject_overrides(environ):
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "COVERAGE_RCFILE", "COVERAGE_FILE",
                 "DATABASE_URL", "JIPPEEL_KEY_FILE"):
        if environ.get(name):
            raise IsolationViolation("conflicting inherited test configuration: " + name)


def validate_arguments(args):
    for arg in args:
        if arg in ("-q", "-v", "-x", "--isolation-coverage", "--isolation-preflight"):
            continue
        path = arg.split("::", 1)[0]
        if (not path.startswith("tests/") or ".." in path or "\\" in path
                or ":" in path or not path.endswith(".py")):
            raise IsolationViolation("unsupported pytest argument")


class IsolationState:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.violations = []
        self.internal_ipc_count = 0
        self.subprocess_attempts = 0
        self.fake_keyring_calls = 0
        self.keyring = types.ModuleType("keyring")
        setattr(self.keyring, "get_password", self.unavailable_keyring)
        setattr(self.keyring, "set_password", self.unavailable_keyring)

    def unavailable_keyring(self, *args, **kwargs):
        self.fake_keyring_calls += 1
        raise RuntimeError("synthetic keyring unavailable; use owned Fernet fallback")

    def fail(self, message) -> NoReturn:
        self.violations.append(message)
        raise IsolationViolation(message)

    def owned_path(self, value):
        if not isinstance(value, (str, os.PathLike)) or not str(value):
            self.fail("missing owned path")
        path = Path(value)
        # Reject UNC, ADS and lexical traversal before resolving any filesystem path.
        if (not path.is_absolute() or str(path).startswith(("\\\\", "//"))
                or ".." in path.parts or any(":" in p for p in path.parts[1:])):
            self.fail("invalid absolute owned path")
        resolved = path.resolve()
        if resolved == self.root or not resolved.is_relative_to(self.root):
            self.fail("path outside owned root")
        return resolved

    def database_path(self, url):
        if (not isinstance(url, str) or not url.startswith("sqlite:///")
                or any(c in url for c in ("?", "#", "%"))):
            self.fail("invalid SQLite file URL")
        return self.owned_path(url[len("sqlite:///"):])

    def destinations(self):
        return tuple(self.root / name for name in ("lifespan.db", "dummy.key", "test.coverage", "pytest"))

    def environment(self):
        database, key, coverage, basetemp = self.destinations()
        return {"DATABASE_URL": "sqlite:///" + database.as_posix(),
                "JIPPEEL_KEY_FILE": str(key), "COVERAGE_FILE": str(coverage),
                "JIPPEEL_TEST_BASETEMP": str(basetemp)}

    def validate_environment(self, environ):
        values = [self.database_path(environ.get("DATABASE_URL"))]
        values += [self.owned_path(environ.get(name)) for name in (
            "JIPPEEL_KEY_FILE", "COVERAGE_FILE", "JIPPEEL_TEST_BASETEMP")]
        if len(set(values)) != len(values) or tuple(values) != self.destinations():
            self.fail("destinations collide or differ from runner-owned configuration")

    def check_keyring(self, modules):
        if (modules.get("keyring") is not self.keyring
                or getattr(self.keyring, "get_password", None) != self.unavailable_keyring
                or getattr(self.keyring, "set_password", None) != self.unavailable_keyring):
            self.fail("fake keyring missing or replaced")

    def guard_call(self, path, consumer):
        self.owned_path(path)
        return consumer()

    def wrap_crypto(self, module):
        for name in ("get_cipher", "_load_master_key_from_file"):
            original = getattr(module, name)

            @functools.wraps(original)
            def guarded(*args, _original=original, **kwargs):
                self.check_keyring(sys.modules)
                return self.guard_call(module.FALLBACK_KEY_FILE,
                                       lambda: _original(*args, **kwargs))

            setattr(module, name, guarded)

    def is_internal_ipc(self, args, frame):
        if (not isinstance(frame, types.FrameType) or _SOCKETPAIR_CODE is None
                or frame.f_code is not _SOCKETPAIR_CODE):
            return False
        client, address = args
        listener = frame.f_locals.get("lsock")
        return (client is frame.f_locals.get("csock") and isinstance(listener, socket.socket)
                and address[0] in ("127.0.0.1", "::1")
                and tuple(address) == listener.getsockname()[:2]
                and tuple(address) == (frame.f_locals.get("addr"), frame.f_locals.get("port")))

    def audit(self, event, args):
        if event in ("subprocess.Popen", "os.system"):
            self.subprocess_attempts += 1
        if event == "socket.connect" and self.is_internal_ipc(args, sys._getframe(1)):
            self.internal_ipc_count += 1
            return
        if event in ("socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"):
            self.fail("unmocked network or subprocess invocation")
        if event == "import" and (args[0] == "keyring" or str(args[0]).startswith("keyring.")):
            self.fail("real keyring backend discovery")
        if event == "sqlite3.connect":
            self.owned_path(args[0])
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0]))
            writing = args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            # Match known sensitive names across Windows case/stream/trailing aliases.
            name = path.name.split(":", 1)[0].rstrip(" .").casefold()
            if writing or name.endswith(".key") or name in ("auth.json", ".env"):
                self.owned_path(path)


class CryptoLoader(importlib.abc.Loader):
    def __init__(self, loader, state):
        self.loader, self.state = loader, state

    def create_module(self, spec):
        return self.loader.create_module(spec)

    def exec_module(self, module):
        self.loader.exec_module(module)
        self.state.wrap_crypto(module)


class CryptoFinder(importlib.abc.MetaPathFinder):
    def __init__(self, state: IsolationState):
        self.state = state

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "app.services.crypto":
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            self.state.fail("crypto import loader missing")
        spec.loader = CryptoLoader(spec.loader, self.state)
        return spec


_STATE = None


def require_isolation():
    if _STATE is None:
        raise IsolationViolation("use the isolated native test runner")
    _STATE.validate_environment(os.environ)
    _STATE.check_keyring(sys.modules)
    if _STATE.violations:
        raise IsolationViolation("isolation violation was recorded")
    return _STATE


def _configure_owned_environment(state):
    os.environ.update(state.environment())
    # Redirect optional home scripts/config and every tempfile used by tests.
    for name in ("HOME", "USERPROFILE", "TMP", "TEMP", "TMPDIR"):
        os.environ[name] = str(state.root)
    tempfile.tempdir = str(state.root)
    for name in ("IM_NOT_AI_DIAGNOSE_CMD", "IM_NOT_AI_REFINE_CMD", "IM_NOT_AI_ROOT",
                 "OPENAI_API_KEY", "JIPPEEL_GPT_OAUTH_BASE_URL", "JIPPEEL_GPT_MODEL",
                 "JIPPEEL_GPT_REASONING_EFFORT"):
        os.environ.pop(name, None)
    os.environ["IM_NOT_AI_ROOT"] = str(state.root / "no-host-scripts")
    os.environ["IM_NOT_AI_METRICS_DIR"] = str(state.root / "no-host-metrics")
    scripts = state.root / "no-host-scripts" / "scripts"
    scripts.mkdir(parents=True)
    for name in ("prepare_monolith_input.py", "verify_gates.py"):
        (scripts / name).write_text(
            'raise RuntimeError("synthetic existence sentinel must never execute")\n',
            encoding="utf-8")
    os.environ["JIPPEEL_ALLOW_TEMP_CREATE_ALL"] = "1"
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True


def install(args):
    """All setup runs inside the native Python process, before third-party imports."""
    global _STATE
    require_pristine(sys.modules)
    reject_overrides(os.environ)
    validate_arguments(args)
    state = IsolationState(tempfile.mkdtemp(prefix="jippeel-isolated-"))
    _configure_owned_environment(state)
    sys.modules["keyring"] = state.keyring
    sys.meta_path.insert(0, CryptoFinder(state))
    sys.addaudithook(state.audit)
    _STATE = state
    require_isolation()
    config = state.root / "pytest.ini"
    config.write_text("[pytest]\n", encoding="utf-8")
    cov_config = state.root / "coverage.ini"
    cov_config.write_text("[run]\nbranch = True\ndata_file = " + os.environ["COVERAGE_FILE"] + "\n",
                          encoding="utf-8")
    pytest_args = ["--capture=sys", "--log-file=" + str(state.root / "pytest.log"),
                   "-c", str(config), "--basetemp", os.environ["JIPPEEL_TEST_BASETEMP"],
                   "-o", "cache_dir=" + str(state.root / "pytest-cache")]
    if "--isolation-coverage" in args:
        pytest_args += ["-p", "pytest_cov", "--cov=app.services.canon", "--cov=app.services.bootstrap",
                        "--cov=app.routers.projects", "--cov=tests.isolation_guard",
                        "--cov=app.services.quality", "--cov-branch", "--cov-config=" + str(cov_config),
                        "--cov-report=term-missing", "--cov-report=json:" + str(state.root / "coverage.json")]
    pytest_args += [arg for arg in args if arg not in ("--isolation-coverage", "--isolation-preflight")]
    print(json.dumps({"isolation": "ready-before-pytest", "root": str(state.root),
                      "destinations": {k: v for k, v in state.environment().items()},
                      "fake_keyring": sys.modules["keyring"] is state.keyring,
                      "crypto_loader_guard": True, "network_subprocess_tripwire": True,
                      "protected_imports_absent": not any(n in sys.modules for n in ("app", "pytest", "coverage"))}),
          flush=True)
    return pytest_args


def preflight_ipc():
    state = require_isolation()
    left, right = socket.socketpair()
    try:
        left.sendall(b"synthetic-ipc")
        if right.recv(32) != b"synthetic-ipc":
            state.fail("internal IPC preflight failed")
    finally:
        left.close()
        right.close()
    print(json.dumps({"preflight": "passed", "internal_ipc_count": state.internal_ipc_count,
                      "violations": state.violations, "app_imported": "app" in sys.modules,
                      "pytest_imported": "pytest" in sys.modules}), flush=True)
