#!/usr/bin/env python3
r"""Isolated backend fixture and manuscript-preservation API probe.

Run with the native Windows backend venv Python, for example:

    cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel && backend\.venv\Scripts\python.exe scripts\preservation_backend_fixture.py --run-probes"

The script never touches backend/jippeel.db. It creates a temp SQLite DB,
runs Alembic upgrade head, starts FastAPI on a dedicated port, seeds synthetic
data through the API, runs preservation probes, and writes JSON evidence.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import http.client
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Keep JSON output readable when invoked through cmd.exe from WSL.
with contextlib.suppress(Exception):
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")

HOST = "127.0.0.1"
DEFAULT_PORT = 18080
RELEVANT_TABLES = [
    # Existing manuscript/history tables.
    "alembic_version",
    "projects",
    "chapters",
    "chapter_snapshots",
    "refine_runs",
    # Creative tables that can contain author/story material.
    "volume_notes",
    "characters",
    "relationships",
    "lore_entries",
    "scenes",
    "foreshadows",
]


class ProbeError(RuntimeError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def assert_native_windows_python(root: Path) -> None:
    if os.name != "nt":
        raise ProbeError(
            "This fixture must run under native Windows Python. Use "
            "backend\\.venv\\Scripts\\python.exe through cmd.exe."
        )
    exe = Path(sys.executable).resolve()
    expected = (root / "backend" / ".venv" / "Scripts").resolve()
    try:
        exe.relative_to(expected)
    except ValueError as exc:
        raise ProbeError(f"Use backend .venv Python. Actual sys.executable={exe}") from exc


def fail_if_port_occupied(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        result = sock.connect_ex((host, port))
    if result == 0:
        raise ProbeError(
            f"Dedicated port {host}:{port} is already occupied. "
            "Refusing to reuse or kill any existing service."
        )


def sqlite_url(db_path: Path) -> str:
    return "sqlite:///" + db_path.as_posix()


def run_cmd(args: list[str], cwd: Path, env: dict[str, str], log_path: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    started = now_iso()
    proc = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    entry = {
        "started_at": started,
        "finished_at": now_iso(),
        "cwd": str(cwd),
        "args": args,
        "returncode": proc.returncode,
        "output": proc.stdout,
    }
    log_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    if proc.returncode != 0:
        raise ProbeError(f"Command failed: {args}; see {log_path}")
    return proc


def make_stub_root(root: Path, work_dir: Path) -> tuple[Path, Path]:
    stub_root = work_dir / "im-not-ai-stub-root"
    scripts_dir = stub_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    source = root / "scripts" / "preservation_im_not_ai_stub.py"
    for name in ("prepare_monolith_input.py", "verify_gates.py"):
        shutil.copyfile(source, scripts_dir / name)
    return stub_root, scripts_dir


def make_python3_cmd(work_dir: Path) -> Path:
    bin_dir = work_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "python3.cmd"
    wrapper.write_text(f'@echo off\r\n"{sys.executable}" %*\r\n', encoding="utf-8")
    return bin_dir


def build_env(root: Path, db_path: Path, work_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("JIPPEEL_ALLOW_TEMP_CREATE_ALL", None)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["DATABASE_URL"] = sqlite_url(db_path)
    env["JIPPEEL_PRESERVATION_STUB_LOG"] = str(work_dir / "refine-stub-calls.jsonl")
    stub_root, _ = make_stub_root(root, work_dir)
    env["IM_NOT_AI_ROOT"] = str(stub_root)
    python3_dir = make_python3_cmd(work_dir)
    env["PATH"] = str(python3_dir) + os.pathsep + env.get("PATH", "")
    refine_stub = root / "scripts" / "preservation_refine_stub.py"
    env["IM_NOT_AI_DIAGNOSE_CMD"] = f'"{sys.executable}" "{refine_stub}" diagnose {{input}} {{diagnosis}}'
    env["IM_NOT_AI_REFINE_CMD"] = f'"{sys.executable}" "{refine_stub}" refine {{input}} {{output}}'
    return env


def migrate_database(root: Path, env: dict[str, str], work_dir: Path) -> Path:
    backend_dir = root / "backend"
    log_path = work_dir / "alembic-upgrade-head.json"
    run_cmd([sys.executable, "-m", "alembic", "upgrade", "head"], backend_dir, env, log_path, timeout=180)
    return log_path


def start_backend(root: Path, env: dict[str, str], work_dir: Path, host: str, port: int) -> tuple[subprocess.Popen[str], Path]:
    backend_dir = root / "backend"
    log_path = work_dir / f"backend-{port}.log"
    log_fh = log_path.open("w", encoding="utf-8", errors="replace")
    args = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port)]
    proc = subprocess.Popen(
        args,
        cwd=str(backend_dir),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=log_fh,
        stderr=subprocess.STDOUT,
    )
    # The child owns the handle; close our duplicate so Windows can flush normally.
    log_fh.close()
    return proc, log_path


def request_json(method: str, path: str, body: dict[str, Any] | None, host: str, port: int, expected: int | tuple[int, ...]) -> tuple[int, Any]:
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    conn = http.client.HTTPConnection(host, port, timeout=15)
    try:
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        text = raw.decode("utf-8", errors="replace")
        data: Any
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = text
        else:
            data = None
        allowed = expected if isinstance(expected, tuple) else (expected,)
        if resp.status not in allowed:
            raise ProbeError(f"{method} {path} expected {allowed}, got {resp.status}: {text[:500]}")
        return resp.status, data
    finally:
        conn.close()


def wait_for_health(proc: subprocess.Popen[str], host: str, port: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = "not attempted"
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise ProbeError(f"Backend exited during startup with code {proc.returncode}")
        try:
            status, data = request_json("GET", "/health", None, host, port, 200)
            if data == {"status": "ok"}:
                return
            last_error = f"unexpected health body {data!r}"
        except Exception as exc:  # noqa: BLE001 - startup polling records last error
            last_error = repr(exc)
        time.sleep(0.25)
    raise ProbeError(f"Backend did not become healthy on {host}:{port}; last error: {last_error}")


def fetch_chapter(host: str, port: int, chapter_id: int) -> dict[str, Any]:
    _, chapter = request_json("GET", f"/api/v1/chapters/{chapter_id}", None, host, port, 200)
    return chapter


def stub_call_count(log_path: Path) -> int:
    if not log_path.exists():
        return 0
    return sum(1 for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip())


def run_api_probes(host: str, port: int, work_dir: Path) -> dict[str, Any]:
    synthetic = {
        "project_title": "QA 원고 보존 합성 작품",
        "chapter_title": "합성 회차 1",
        "initial_content": "첫 문장입니다. 두 번째 문장입니다. 보존 검증용 합성 원고입니다.",
        "stale_content": "이 문장은 오래된 revision으로 저장되어서는 안 됩니다.",
        "volume_title": "합성 1권",
        "character_names": ["합성 주인공", "합성 조력자"],
        "lore_title": "합성 도시",
        "scene_title": "합성 장면",
        "foreshadow_title": "합성 붉은 열쇠",
    }
    steps: list[dict[str, Any]] = []
    fixture_ids: dict[str, Any] = {}
    stub_log = work_dir / "refine-stub-calls.jsonl"

    _, project = request_json(
        "POST", "/api/v1/projects",
        {"title": synthetic["project_title"], "genre": "QA", "synopsis": "synthetic only", "platform_note": "no real endpoint"},
        host, port, 201,
    )
    project_id = project["id"]
    fixture_ids["project_id"] = project_id
    steps.append({"name": "create synthetic project", "project_id": project_id})

    _, volume_note = request_json(
        "POST", f"/api/v1/projects/{project_id}/volume-notes",
        {
            "volume": 1,
            "title": synthetic["volume_title"],
            "overview": "합성 권 개요입니다.",
            "emotion_curve": "불안→발견→결심",
            "climax_note": "합성 고봉에서 붉은 열쇠가 드러납니다.",
        },
        host, port, 201,
    )
    fixture_ids["volume_note_id"] = volume_note["id"]
    steps.append({"name": "create synthetic volume note", "volume_note_id": volume_note["id"]})

    _, chapter = request_json(
        "POST", f"/api/v1/projects/{project_id}/chapters",
        {"title": synthetic["chapter_title"], "volume": 1, "sort_order": 1.0},
        host, port, 201,
    )
    chapter_id = chapter["id"]
    fixture_ids["chapter_id"] = chapter_id
    assert chapter["revision"] == 0
    steps.append({"name": "create synthetic chapter", "chapter_id": chapter_id, "revision": chapter["revision"]})

    _, char_a = request_json(
        "POST", f"/api/v1/projects/{project_id}/characters",
        {
            "name": synthetic["character_names"][0],
            "aliases": ["QA-A"],
            "role": "주연",
            "appearance": "합성 검은 코트",
            "personality": "침착함",
            "speech_style": "짧게 말함",
            "background": "테스트 전용 인물",
            "card_json": {"qa": True, "preservation": {"slot": "character-a"}},
        },
        host, port, 201,
    )
    _, char_b = request_json(
        "POST", f"/api/v1/projects/{project_id}/characters",
        {
            "name": synthetic["character_names"][1],
            "aliases": ["QA-B"],
            "role": "조연",
            "appearance": "합성 은색 펜",
            "personality": "호기심 많음",
            "speech_style": "질문형",
            "background": "관계 백업 검증용 인물",
            "card_json": {"qa": True, "preservation": {"slot": "character-b"}},
        },
        host, port, 201,
    )
    fixture_ids["character_ids"] = [char_a["id"], char_b["id"]]
    steps.append({"name": "create synthetic characters", "character_ids": fixture_ids["character_ids"]})

    _, relation = request_json(
        "POST", f"/api/v1/projects/{project_id}/characters/relations",
        {
            "from_character_id": char_a["id"],
            "to_character_id": char_b["id"],
            "label": "합성 동료",
            "note": "백업 비교용 관계입니다.",
        },
        host, port, 201,
    )
    fixture_ids["relationship_id"] = relation["id"]
    steps.append({"name": "create synthetic relationship", "relationship_id": relation["id"]})

    _, lore = request_json(
        "POST", f"/api/v1/projects/{project_id}/lore",
        {
            "category": "장소",
            "title": synthetic["lore_title"],
            "content": "백업 비교용 합성 로어 항목입니다.",
            "keywords": ["합성도시", "QA로어"],
        },
        host, port, 201,
    )
    fixture_ids["lore_id"] = lore["id"]
    steps.append({"name": "create synthetic lore", "lore_id": lore["id"]})

    _, scene = request_json(
        "POST", f"/api/v1/chapters/{chapter_id}/scenes",
        {
            "title": synthetic["scene_title"],
            "sort_order": 1.0,
            "content_md": "합성 장면 본문입니다. 붉은 열쇠가 탁자에 놓입니다.",
        },
        host, port, 201,
    )
    fixture_ids["scene_id"] = scene["id"]
    steps.append({"name": "create synthetic scene", "scene_id": scene["id"]})

    _, foreshadow = request_json(
        "POST", f"/api/v1/projects/{project_id}/foreshadows",
        {
            "title": synthetic["foreshadow_title"],
            "content": "나중에 문을 여는 합성 복선입니다.",
            "keywords": ["붉은 열쇠", "합성 문"],
            "status": "설치",
            "audience_knows": False,
            "planted_chapter_id": chapter_id,
            "resolved_chapter_id": None,
        },
        host, port, 201,
    )
    fixture_ids["foreshadow_id"] = foreshadow["id"]
    steps.append({"name": "create synthetic foreshadow", "foreshadow_id": foreshadow["id"]})

    _, saved = request_json(
        "PUT", f"/api/v1/chapters/{chapter_id}/content",
        {"content_md": synthetic["initial_content"], "expected_revision": 0},
        host, port, 200,
    )
    if saved["revision"] != 1 or saved["content_md"] != synthetic["initial_content"]:
        raise ProbeError("Initial save did not advance to revision 1 with expected content")
    steps.append({"name": "initial content save", "revision": saved["revision"]})

    status, stale = request_json(
        "PUT", f"/api/v1/chapters/{chapter_id}/content",
        {"content_md": synthetic["stale_content"], "expected_revision": 0},
        host, port, 409,
    )
    fresh = fetch_chapter(host, port, chapter_id)
    if fresh["content_md"] != synthetic["initial_content"] or fresh["revision"] != 1:
        raise ProbeError("Stale write mutated chapter content or revision")
    if stale.get("detail", {}).get("code") != "revision_conflict" or stale.get("detail", {}).get("current_revision") != 1:
        raise ProbeError(f"Stale write conflict payload was unexpected: {stale}")
    steps.append({"name": "stale write rejected", "status": status, "detail": stale["detail"]})

    before_stub_calls = stub_call_count(stub_log)
    status, stale_refine = request_json(
        "POST", "/api/v1/refine",
        {"chapter_id": chapter_id, "expected_revision": 0, "force_route": "light"},
        host, port, 409,
    )
    after_stub_calls = stub_call_count(stub_log)
    if after_stub_calls != before_stub_calls:
        raise ProbeError("Stale refine invoked the external refine stub before rejecting")
    if stale_refine.get("detail", {}).get("current_revision") != 1:
        raise ProbeError(f"Stale refine conflict payload was unexpected: {stale_refine}")
    steps.append({"name": "stale refine rejected before stub", "status": status, "stub_calls": after_stub_calls})

    _, refine_result = request_json(
        "POST", "/api/v1/refine",
        {"chapter_id": chapter_id, "expected_revision": 1, "force_route": "light"},
        host, port, 200,
    )
    if refine_result["original"] != synthetic["initial_content"]:
        raise ProbeError("Refine original did not preserve the base input content")
    if "[QA 윤문 stub]" not in refine_result["refined"]:
        raise ProbeError("Refine did not return stubbed refined text")
    if refine_result["gate"] not in ("pass", "warn") or refine_result["status"] != "ok":
        raise ProbeError(f"Refine gate was unexpected: {refine_result}")
    fixture_ids["refine_run_id"] = refine_result["run_id"]
    steps.append({"name": "valid refine uses stub", "run_id": refine_result["run_id"], "gate": refine_result["gate"]})

    _, accepted = request_json(
        "POST", f"/api/v1/refine/runs/{refine_result['run_id']}/accept", None,
        host, port, 200,
    )
    if accepted["revision"] != 2 or accepted["content_md"] != refine_result["refined"]:
        raise ProbeError("Accepting refine did not advance revision 2 with refined content")
    steps.append({"name": "accept refine", "revision": accepted["revision"]})

    _, snapshots = request_json("GET", f"/api/v1/chapters/{chapter_id}/snapshots", None, host, port, 200)
    rev1_snapshots = [s for s in snapshots if s["revision"] == 1 and s["reason"] == "refine"]
    if len(rev1_snapshots) != 1:
        raise ProbeError(f"Expected one revision-1 refine snapshot, got {snapshots}")
    snapshot_id = rev1_snapshots[0]["id"]
    fixture_ids["refine_snapshot_id"] = snapshot_id
    _, snapshot_detail = request_json("GET", f"/api/v1/chapters/{chapter_id}/snapshots/{snapshot_id}", None, host, port, 200)
    if snapshot_detail["content_md"] != synthetic["initial_content"]:
        raise ProbeError("Snapshot detail did not contain pre-refine content")
    steps.append({"name": "snapshot detail preserves pre-image", "snapshot_id": snapshot_id})

    _, restored = request_json(
        "POST", f"/api/v1/chapters/{chapter_id}/restore",
        {"snapshot_id": snapshot_id, "expected_revision": 2},
        host, port, 200,
    )
    if restored["revision"] != 3 or restored["content_md"] != synthetic["initial_content"]:
        raise ProbeError("Snapshot restore did not restore initial content at revision 3")
    steps.append({"name": "snapshot restore", "revision": restored["revision"]})

    return {
        "synthetic": synthetic,
        "fixture_ids": fixture_ids,
        "project_id": project_id,
        "chapter_id": chapter_id,
        "steps": steps,
        "final_revision": restored["revision"],
        "stub_calls": stub_call_count(stub_log),
    }


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    columns = [row[1] for row in rows]
    if not columns:
        raise ProbeError(f"No such table or no visible columns: {table}")
    return columns


def table_rows(conn: sqlite3.Connection, table: str, columns: list[str]) -> list[list[Any]]:
    cols = ", ".join(f'"{col}"' for col in columns)
    order = "id" if "id" in columns else columns[0]
    rows = conn.execute(f'SELECT {cols} FROM "{table}" ORDER BY "{order}"').fetchall()
    normalized: list[list[Any]] = []
    for row in rows:
        normalized.append([value for value in row])
    return normalized


def sqlite_ro_uri(path: Path) -> str:
    return path.resolve().as_uri() + "?mode=ro"


def sqlite_backup_and_compare(db_path: Path, backup_path: Path) -> dict[str, Any]:
    if backup_path.exists():
        raise ProbeError(f"Backup destination already exists; refusing to overwrite: {backup_path}")
    if not db_path.exists():
        raise ProbeError(f"Source DB does not exist: {db_path}")
    # Source is opened read-only by URI. Destination must be new. This validates
    # the app-level backup mechanism, not OS snapshot/restore behavior.
    with sqlite3.connect(sqlite_ro_uri(db_path), uri=True) as src, sqlite3.connect(str(backup_path)) as dst:
        src.backup(dst)
    comparison: dict[str, Any] = {}
    with sqlite3.connect(sqlite_ro_uri(db_path), uri=True) as src, sqlite3.connect(sqlite_ro_uri(backup_path), uri=True) as dst:
        for table in RELEVANT_TABLES:
            columns = table_columns(src, table)
            dst_columns = table_columns(dst, table)
            if columns != dst_columns:
                raise ProbeError(f"Backup column mismatch for table {table}: {columns} != {dst_columns}")
            src_rows = table_rows(src, table, columns)
            dst_rows = table_rows(dst, table, columns)
            if src_rows != dst_rows:
                raise ProbeError(f"Backup comparison mismatch for table {table}")
            comparison[table] = {"columns": columns, "row_count": len(src_rows), "rows": src_rows}
    return comparison


def stop_backend(proc: subprocess.Popen[str], timeout: float = 10.0) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=timeout)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Isolated manuscript-preservation backend fixture/probe")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Dedicated backend port. Default: 18080")
    parser.add_argument("--host", default=HOST, help="Bind host. Default: 127.0.0.1")
    parser.add_argument("--work-dir", type=Path, default=None, help="Existing/new temp work directory. Default: create one under TEMP")
    parser.add_argument("--run-probes", action="store_true", help="Run API and backup probes after startup")
    parser.add_argument("--keep-server", action="store_true", help="Leave the isolated backend running after probes and exit")
    parser.add_argument("--hold-server", action="store_true", help="Keep this fixture process alive until killed, then stop its backend child")
    parser.add_argument("--json-report", type=Path, default=None, help="Optional path for a JSON report copy")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()
    result: dict[str, Any] = {
        "started_at": now_iso(),
        "host": args.host,
        "port": args.port,
        "project_root": str(root),
        "python_executable": sys.executable,
        "status": "started",
    }
    proc: subprocess.Popen[str] | None = None
    try:
        assert_native_windows_python(root)
        fail_if_port_occupied(args.host, args.port)
        work_dir = args.work_dir or Path(tempfile.mkdtemp(prefix="jippeel-preservation-qa-"))
        work_dir.mkdir(parents=True, exist_ok=True)
        db_path = work_dir / "fixture.db"
        backup_path = work_dir / "fixture-backup.db"
        if db_path.exists():
            raise ProbeError(f"Refusing to reuse existing fixture DB: {db_path}")
        env = build_env(root, db_path, work_dir)
        result.update({
            "work_dir": str(work_dir),
            "database_url": env["DATABASE_URL"],
            "db_path": str(db_path),
            "backup_path": str(backup_path),
            "im_not_ai_root": env["IM_NOT_AI_ROOT"],
            "stub_log": env["JIPPEEL_PRESERVATION_STUB_LOG"],
            "jippeel_allow_temp_create_all": env.get("JIPPEEL_ALLOW_TEMP_CREATE_ALL"),
        })
        alembic_log = migrate_database(root, env, work_dir)
        result["alembic_log"] = str(alembic_log)
        proc, backend_log = start_backend(root, env, work_dir, args.host, args.port)
        result.update({"backend_pid": proc.pid, "backend_log": str(backend_log)})
        wait_for_health(proc, args.host, args.port)
        result["health"] = "ok"
        if args.run_probes:
            result["api_probe"] = run_api_probes(args.host, args.port, work_dir)
            result["backup_comparison"] = sqlite_backup_and_compare(db_path, backup_path)
            result["validated"] = [
                "Alembic upgrade head on a new temp SQLite DB before strict startup",
                "backend API stale write/refine conflict handling with deterministic stubs",
                "snapshot detail and restore for a synthetic manuscript",
                "SQLite Connection.backup from read-only source URI to a new destination DB",
                "exact full-row equality for selected creative and manuscript/history tables",
            ]
            result["not_validated"] = [
                "production DB, WAL/SHM, config, secrets, or real endpoints",
                "encryption keys or credential restore",
                "OS-level bare file copy/restore of loose DB/WAL/SHM files",
                "paid model calls or LLM quality",
                "frontend/browser integration or UI behavior",
            ]
        result["status"] = "passed"
        result["finished_at"] = now_iso()
        report_path = work_dir / "preservation-fixture-result.json"
        result["result_json"] = str(report_path)
        result["keep_server"] = bool(args.keep_server)
        result["hold_server"] = bool(args.hold_server)
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.json_report:
            args.json_report.parent.mkdir(parents=True, exist_ok=True)
            args.json_report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        if args.hold_server:
            try:
                while proc.poll() is None:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
            return proc.returncode or 0
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI must record any failure
        result["status"] = "failed"
        result["error"] = repr(exc)
        result["finished_at"] = now_iso()
        with contextlib.suppress(Exception):
            work_dir_value = result.get("work_dir")
            work_dir = Path(
                work_dir_value
                if work_dir_value is not None
                else tempfile.gettempdir()
            )
            fail_path = work_dir / "preservation-fixture-result.failed.json"
            fail_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            result["result_json"] = str(fail_path)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        if proc is not None and not args.keep_server:
            stop_backend(proc)


if __name__ == "__main__":
    raise SystemExit(main())
