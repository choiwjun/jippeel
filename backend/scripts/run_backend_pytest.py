"""Supported backend test entrypoint; run from backend with Python -I -B."""
import importlib
import json
import pathlib
import sys


def main():
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    isolation = importlib.import_module("tests.isolation_guard")
    arguments = isolation.install(sys.argv[1:])
    if "--isolation-preflight" in sys.argv:
        isolation.preflight_ipc()
        return 0

    import pytest

    result = pytest.main(arguments)
    state = isolation.require_isolation()
    print(json.dumps({"isolation": "complete", "pytest_exit": result,
                      "internal_ipc_count": state.internal_ipc_count,
                      "subprocess_attempts": state.subprocess_attempts,
                      "fake_keyring_calls": state.fake_keyring_calls,
                      "violations": state.violations}), flush=True)
    return result


if __name__ == "__main__":
    sys.exit(main())
