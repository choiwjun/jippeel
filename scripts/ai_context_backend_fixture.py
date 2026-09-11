#!/usr/bin/env python3
r"""Strict Alembic FastAPI fixture for AI context Task 4.

Run with native Windows backend .venv Python only. The script creates one fresh
SQLite database under the native temp directory, runs Alembic before app import,
starts the deterministic provider and FastAPI on dedicated ports, seeds only
synthetic data through HTTP, writes phase-updated JSON evidence, and stops only
its own child process handles.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import http.client
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
DEFAULT_BACKEND_PORT = 18112
DEFAULT_PROVIDER_PORT = 18113
BODY_SENTINEL = "초기 서버 본문은 프롬프트에 없어야 한다"
SECOND_BODY = "두 번째 회차 원고입니다. 결과 원본 불일치 검증용 합성 원고입니다."

with contextlib.suppress(Exception):
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


class FixtureError(RuntimeError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def assert_native_windows_python(root: Path) -> None:
    if os.name != "nt":
        raise FixtureError("Use native Windows backend .venv Python for this fixture")
    exe = Path(sys.executable).resolve()
    expected = (root / "backend" / ".venv" / "Scripts").resolve()
    try:
        exe.relative_to(expected)
    except ValueError as exc:
        raise FixtureError(f"Use backend .venv Python. Actual sys.executable={exe}") from exc


def fail_if_port_occupied(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        result = sock.connect_ex((HOST, port))
    if result == 0:
        raise FixtureError(f"Dedicated port {HOST}:{port} is occupied; refusing reuse or kill")


def listener_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((HOST, port)) == 0


def sqlite_url(db_path: Path) -> str:
    return "sqlite:///" + db_path.as_posix()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def archive_existing_pointer(path: Path, run_id: str) -> str | None:
    if not path.exists():
        return None
    archive = path.with_name(f"{path.stem}-archived-before-{run_id}{path.suffix}")
    if archive.exists():
        raise FixtureError(f"Archive report already exists: {archive}")
    shutil.copy2(path, archive)
    return str(archive)


def update_report(report: dict[str, Any], pointer_path: Path | None = None, run_report_path: Path | None = None) -> None:
    report["updated_at"] = now_iso()
    if run_report_path is not None:
        write_json(run_report_path, report)
    if pointer_path is not None:
        write_json(pointer_path, report)


def run_cmd(args: list[str], cwd: Path, env: dict[str, str], log_path: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
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
    write_json(log_path, entry)
    if proc.returncode != 0:
        raise FixtureError(f"Command failed: {args}; see {log_path}")
    return proc


def request_json(method: str, path: str, body: dict[str, Any] | None, port: int, expected: int | tuple[int, ...]) -> tuple[int, Any]:
    raw_body = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if raw_body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    conn = http.client.HTTPConnection(HOST, port, timeout=20)
    try:
        conn.request(method, path, body=raw_body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        text = raw.decode("utf-8", errors="replace")
        try:
            data = json.loads(text) if text else None
        except json.JSONDecodeError:
            data = text
        allowed = expected if isinstance(expected, tuple) else (expected,)
        if resp.status not in allowed:
            raise FixtureError(f"{method} {path} expected {allowed}, got {resp.status}: {text[:1000]}")
        return resp.status, data
    finally:
        conn.close()


def wait_for_http(proc: subprocess.Popen[str], port: int, path: str, expected_body: dict[str, Any] | None, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = "not attempted"
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise FixtureError(f"Process exited during startup with code {proc.returncode}; path={path}")
        try:
            _status, data = request_json("GET", path, None, port, 200)
            if expected_body is None or data == expected_body:
                return
            last_error = f"unexpected body {data!r}"
        except Exception as exc:  # noqa: BLE001 - startup health probe records last error
            last_error = repr(exc)
        time.sleep(0.25)
    raise FixtureError(f"HTTP service did not become healthy on {HOST}:{port}{path}; last error: {last_error}")


def start_logged_process(args: list[str], cwd: Path, env: dict[str, str], log_path: Path) -> subprocess.Popen[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = log_path.open("w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=log_fh,
        stderr=subprocess.STDOUT,
    )
    log_fh.close()
    return proc


def stop_process(proc: subprocess.Popen[str] | None, name: str, events: list[dict[str, Any]], timeout: float = 10.0) -> None:
    if proc is None:
        return
    event: dict[str, Any] = {"name": name, "pid": proc.pid, "started_at": now_iso()}
    try:
        if proc.poll() is not None:
            event.update({"action": "already-exited", "returncode": proc.returncode})
            return
        proc.terminate()
        event["action"] = "terminate"
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            event["kill_fallback"] = True
            proc.kill()
            proc.wait(timeout=timeout)
        event["returncode"] = proc.returncode
    finally:
        event["finished_at"] = now_iso()
        events.append(event)


def seed_data(port: int, provider_port: int, db_path: Path) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    sentinels = {
        "body": BODY_SENTINEL,
        "second_body": SECOND_BODY,
        "style": "AI_CONTEXT_STYLE_SENTINEL — 문장은 짧고 단호하게 끝낸다.",
        "relationship": "AI_CONTEXT_REL_SENTINEL — 스승은 제자를 공개적으로 감싸지 못한다.",
        "lore": "AI_CONTEXT_LORE_SENTINEL — 흑요 문은 피로만 열린다.",
        "approved_payoff": "AI_CONTEXT_PAYOFF_SENTINEL — 검의 진짜 주인은 강무진이다.",
        "future_plant": "AI_CONTEXT_FUTURE_PLANT_SENTINEL — 미래 회차에서 처음 등장할 계획이다.",
        "future_resolution": "AI_CONTEXT_FUTURE_RESOLUTION_SENTINEL — 해결은 다음 회차 계획이지만 현재 사실은 아니다.",
    }

    _status, project = request_json("POST", "/api/v1/projects", {
        "title": "AI Context Task4 합성 작품",
        "genre": "QA",
        "synopsis": "합성 시놉시스. 실제 원고나 비밀 없음.",
        "platform_note": "Task4 deterministic provider only.",
    }, port, 201)
    pid = project["id"]
    _status, patched = request_json("PATCH", f"/api/v1/projects/{pid}", {
        "style_profile": sentinels["style"],
    }, port, 200)
    steps.append({"name": "project", "project_id": pid, "style_profile": patched.get("style_profile")})

    _status, ch1 = request_json("POST", f"/api/v1/projects/{pid}/chapters", {
        "title": "AI Context Task4 1화", "volume": 1, "sort_order": 1.0, "memo": "닫아야 할 감정선은 구출과 선택이다.",
    }, port, 201)
    _status, ch2 = request_json("POST", f"/api/v1/projects/{pid}/chapters", {
        "title": "AI Context Task4 2화", "volume": 1, "sort_order": 2.0, "memo": "다음 회차 방향은 후일담이다.",
    }, port, 201)
    _status, ch3 = request_json("POST", f"/api/v1/projects/{pid}/chapters", {
        "title": "AI Context Task4 미래 설치 회차", "volume": 1, "sort_order": 3.0, "memo": "미래 복선 계획만 둔다.",
    }, port, 201)
    _status, ch1 = request_json("PATCH", f"/api/v1/chapters/{ch1['id']}", {
        "memo": "닫아야 할 감정선은 구출과 선택이다.",
    }, port, 200)
    _status, ch2 = request_json("PATCH", f"/api/v1/chapters/{ch2['id']}", {
        "memo": "다음 회차 방향은 후일담이다.",
    }, port, 200)
    _status, ch3 = request_json("PATCH", f"/api/v1/chapters/{ch3['id']}", {
        "memo": "미래 복선 계획만 둔다.",
    }, port, 200)
    _status, saved1 = request_json("PUT", f"/api/v1/chapters/{ch1['id']}/content", {
        "content_md": BODY_SENTINEL, "expected_revision": 0,
    }, port, 200)
    _status, saved2 = request_json("PUT", f"/api/v1/chapters/{ch2['id']}/content", {
        "content_md": SECOND_BODY, "expected_revision": 0,
    }, port, 200)
    steps.append({"name": "chapters", "chapter_id": ch1["id"], "revision": saved1["revision"], "second_chapter_id": ch2["id"], "second_revision": saved2["revision"], "future_chapter_id": ch3["id"]})

    _status, volume = request_json("POST", f"/api/v1/projects/{pid}/volume-notes", {
        "volume": 1,
        "title": "Task4 합성 1권",
        "overview": "왕좌를 포기하고 사람을 구하는 권.",
        "emotion_curve": "의심→선택→종결",
        "climax_note": "문 앞에서 복수 대신 구출을 고른다.",
    }, port, 201)
    steps.append({"name": "volume_note", "volume_note_id": volume["id"]})

    _status, char_a = request_json("POST", f"/api/v1/projects/{pid}/characters", {
        "name": "한서윤",
        "role": "주연",
        "appearance": "검은 코트",
        "personality": "끝까지 확인한다",
        "speech_style": "짧게 말한다",
        "background": "Task4 합성 인물 A",
    }, port, 201)
    _status, char_b = request_json("POST", f"/api/v1/projects/{pid}/characters", {
        "name": "강무진",
        "role": "조연",
        "appearance": "낡은 붕대",
        "personality": "침묵으로 버틴다",
        "speech_style": "단문으로 답한다",
        "background": "Task4 합성 인물 B",
    }, port, 201)
    _status, relationship = request_json("POST", f"/api/v1/projects/{pid}/characters/relations", {
        "from_character_id": char_a["id"],
        "to_character_id": char_b["id"],
        "label": "사제",
        "note": sentinels["relationship"],
    }, port, 201)
    steps.append({"name": "characters_relationship", "character_ids": [char_a["id"], char_b["id"]], "relationship_id": relationship["id"]})

    _status, lore = request_json("POST", f"/api/v1/projects/{pid}/lore", {
        "category": "용어",
        "title": "흑요 문",
        "content": sentinels["lore"],
        "keywords": ["흑요", "문"],
    }, port, 201)
    steps.append({"name": "lore", "lore_id": lore["id"]})

    _status, scene = request_json("POST", f"/api/v1/chapters/{ch1['id']}/scenes", {
        "title": "문 앞 대치",
        "sort_order": 1.0,
        "content_md": "장면 본문. 한서윤과 강무진이 문 앞에 선다.",
    }, port, 201)
    steps.append({"name": "scene", "scene_id": scene["id"]})

    _status, fs_approved = request_json("POST", f"/api/v1/projects/{pid}/foreshadows", {
        "title": "검의 진짜 주인",
        "content": sentinels["approved_payoff"],
        "keywords": ["검", "주인"],
        "status": "설치",
        "audience_knows": False,
        "planted_chapter_id": ch1["id"],
        "resolved_chapter_id": None,
    }, port, 201)
    _status, fs_future_plant = request_json("POST", f"/api/v1/projects/{pid}/foreshadows", {
        "title": "황궁 지하 문",
        "content": sentinels["future_plant"],
        "keywords": ["지하문"],
        "status": "보류",
        "audience_knows": False,
        "planted_chapter_id": ch3["id"],
        "resolved_chapter_id": None,
    }, port, 201)
    _status, fs_future_resolution = request_json("POST", f"/api/v1/projects/{pid}/foreshadows", {
        "title": "왕좌 포기의 대가",
        "content": sentinels["future_resolution"],
        "keywords": ["왕좌", "대가"],
        "status": "설치",
        "audience_knows": False,
        "planted_chapter_id": ch1["id"],
        "resolved_chapter_id": ch2["id"],
    }, port, 201)
    steps.append({"name": "foreshadows", "foreshadow_id": fs_approved["id"], "future_plant_foreshadow_id": fs_future_plant["id"], "future_resolution_foreshadow_id": fs_future_resolution["id"]})

    _status, foreign_project = request_json("POST", "/api/v1/projects", {
        "title": "AI Context Task4 외부 작품",
        "genre": "QA",
        "synopsis": "ownership negative only",
    }, port, 201)
    foreign_pid = foreign_project["id"]
    _status, foreign_chapter = request_json("POST", f"/api/v1/projects/{foreign_pid}/chapters", {
        "title": "외부 1화", "volume": 1, "sort_order": 1.0,
    }, port, 201)
    _status, foreign_saved = request_json("PUT", f"/api/v1/chapters/{foreign_chapter['id']}/content", {
        "content_md": "외부 작품 본문", "expected_revision": 0,
    }, port, 200)
    _status, foreign_char = request_json("POST", f"/api/v1/projects/{foreign_pid}/characters", {"name": "외부 인물"}, port, 201)
    _status, foreign_lore = request_json("POST", f"/api/v1/projects/{foreign_pid}/lore", {
        "category": "기타", "title": "외부 로어", "content": "타작품 로어",
    }, port, 201)
    _status, foreign_scene = request_json("POST", f"/api/v1/chapters/{foreign_chapter['id']}/scenes", {
        "title": "외부 장면", "sort_order": 1.0, "content_md": "타작품 장면",
    }, port, 201)
    _status, foreign_foreshadow = request_json("POST", f"/api/v1/projects/{foreign_pid}/foreshadows", {
        "title": "외부 복선", "content": "타작품 복선", "keywords": ["외부"], "status": "설치",
        "audience_knows": False,
        "planted_chapter_id": foreign_chapter["id"],
        "resolved_chapter_id": None,
    }, port, 201)
    _status, bad_ref_foreshadow = request_json("POST", f"/api/v1/projects/{pid}/foreshadows", {
        "title": "교차 참조 복선",
        "content": "승인하면 거절되어야 하는 교차 참조 복선",
        "keywords": ["교차"],
        "status": "회수",
        "audience_knows": False,
        "planted_chapter_id": ch1["id"],
        "resolved_chapter_id": ch2["id"],
    }, port, 201)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE foreshadows SET resolved_chapter_id = ? WHERE id = ?",
            (foreign_chapter["id"], bad_ref_foreshadow["id"]),
        )
        conn.commit()
    steps.append({
        "name": "foreign_negative_ids",
        "foreign_project_id": foreign_pid,
        "foreign_chapter_id": foreign_chapter["id"],
        "foreign_chapter_revision": foreign_saved["revision"],
        "foreign_character_id": foreign_char["id"],
        "foreign_lore_id": foreign_lore["id"],
        "foreign_scene_id": foreign_scene["id"],
        "foreign_foreshadow_id": foreign_foreshadow["id"],
        "bad_ref_foreshadow_id": bad_ref_foreshadow["id"],
    })

    _status, endpoint = request_json("POST", "/api/v1/ai/endpoints", {
        "name": "Task4 deterministic provider",
        "base_url": f"http://{HOST}:{provider_port}/v1",
        "default_model": "ai-context-fake",
        "temperature": None,
        "reasoning_effort": None,
        "is_default": True,
    }, port, 201)
    steps.append({"name": "endpoint", "endpoint_id": endpoint["id"], "base_url": endpoint["base_url"]})

    return {
        "steps": steps,
        "sentinels": sentinels,
        "project_id": pid,
        "chapter_id": ch1["id"],
        "chapter_revision": saved1["revision"],
        "second_chapter_id": ch2["id"],
        "second_chapter_revision": saved2["revision"],
        "future_chapter_id": ch3["id"],
        "character_ids": [char_a["id"], char_b["id"]],
        "relationship_id": relationship["id"],
        "lore_id": lore["id"],
        "scene_id": scene["id"],
        "foreshadow_id": fs_approved["id"],
        "future_plant_foreshadow_id": fs_future_plant["id"],
        "future_resolution_foreshadow_id": fs_future_resolution["id"],
        "endpoint_id": endpoint["id"],
        "foreign_project_id": foreign_pid,
        "foreign_chapter_id": foreign_chapter["id"],
        "foreign_character_id": foreign_char["id"],
        "foreign_lore_id": foreign_lore["id"],
        "foreign_scene_id": foreign_scene["id"],
        "foreign_foreshadow_id": foreign_foreshadow["id"],
        "bad_ref_foreshadow_id": bad_ref_foreshadow["id"],
        "missing_id": 987654321,
    }


def sqlite_counts(db_path: Path) -> dict[str, int]:
    tables = ["projects", "chapters", "characters", "relationships", "lore_entries", "foreshadows", "ai_endpoints"]
    counts: dict[str, int] = {}
    if not db_path.exists():
        return counts
    uri = db_path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        for table in tables:
            try:
                counts[table] = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            except sqlite3.Error:
                counts[table] = -1
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI context Task 4 strict backend fixture")
    parser.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT)
    parser.add_argument("--provider-port", type=int, default=DEFAULT_PROVIDER_PORT)
    parser.add_argument("--json-report", type=Path, required=True)
    parser.add_argument("--hold-server", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    pointer_path = args.json_report.resolve()
    work_dir = Path(tempfile.mkdtemp(prefix="jippeel-ai-context-task4-"))
    db_path = work_dir / "ai-context-task4.db"
    prompt_log = work_dir / "provider-prompts.jsonl"
    run_report_path = work_dir / "backend-fixture-result.json"
    eval_run_report_path = pointer_path.parent / f"backend-fixture-{run_id}.json"
    cleanup_events: list[dict[str, Any]] = []
    backend_proc: subprocess.Popen[str] | None = None
    provider_proc: subprocess.Popen[str] | None = None

    report: dict[str, Any] = {
        "run_id": run_id,
        "started_at": now_iso(),
        "status": "starting",
        "host": HOST,
        "backend_port": args.backend_port,
        "provider_port": args.provider_port,
        "frontend_port": 15212,
        "project_root": str(root),
        "python_executable": sys.executable,
        "work_dir": str(work_dir),
        "db_path": str(db_path),
        "database_url": sqlite_url(db_path),
        "prompt_log": str(prompt_log),
        "provider_log": str(work_dir / f"provider-{args.provider_port}.log"),
        "backend_log": str(work_dir / f"backend-{args.backend_port}.log"),
        "alembic_log": str(work_dir / "alembic-upgrade-head.json"),
        "pointer_report": str(pointer_path),
        "run_report": str(run_report_path),
        "eval_run_report": str(eval_run_report_path),
        "owned_pids": {},
        "phase_evidence": [],
        "cleanup_events": cleanup_events,
    }

    archived = None
    try:
        assert_native_windows_python(root)
        if args.backend_port in (8000, 5173) or args.provider_port in (8000, 5173) or args.backend_port == args.provider_port:
            raise FixtureError("Dedicated Task4 ports must not use defaults or collide")
        fail_if_port_occupied(args.backend_port)
        fail_if_port_occupied(args.provider_port)
        archived = archive_existing_pointer(pointer_path, run_id)
        report["archived_previous_pointer"] = archived
        update_report(report, pointer_path, run_report_path)
        update_report(report, eval_run_report_path, None)

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["DATABASE_URL"] = sqlite_url(db_path)
        env.pop("JIPPEEL_ALLOW_TEMP_CREATE_ALL", None)
        report["jippeel_allow_temp_create_all"] = env.get("JIPPEEL_ALLOW_TEMP_CREATE_ALL")
        report["phase_evidence"].append({"phase": "env", "database_url_set_before_app_import": True, "allow_temp_create_all_unset": True})
        update_report(report, pointer_path, run_report_path)
        update_report(report, eval_run_report_path, None)

        alembic_log = Path(report["alembic_log"])
        run_cmd([sys.executable, "-m", "alembic", "upgrade", "head"], root / "backend", env, alembic_log, timeout=240)
        report["status"] = "alembic_complete"
        report["phase_evidence"].append({"phase": "alembic", "log": str(alembic_log), "db_exists": db_path.exists()})
        update_report(report, pointer_path, run_report_path)
        update_report(report, eval_run_report_path, None)

        provider_proc = start_logged_process([
            sys.executable, str(root / "scripts" / "ai_context_fake_llm_server.py"),
            "--port", str(args.provider_port), "--prompt-log", str(prompt_log),
        ], root, env, Path(report["provider_log"]))
        report["owned_pids"]["provider"] = provider_proc.pid
        wait_for_http(provider_proc, args.provider_port, "/health", {"status": "ok"}, timeout=20)
        report["status"] = "provider_healthy"
        report["phase_evidence"].append({"phase": "provider", "pid": provider_proc.pid, "health": "ok", "prompt_log": str(prompt_log)})
        update_report(report, pointer_path, run_report_path)
        update_report(report, eval_run_report_path, None)

        backend_proc = start_logged_process([
            sys.executable, "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(args.backend_port),
        ], root / "backend", env, Path(report["backend_log"]))
        report["owned_pids"]["backend"] = backend_proc.pid
        wait_for_http(backend_proc, args.backend_port, "/health", {"status": "ok"}, timeout=40)
        report["status"] = "backend_healthy"
        report["phase_evidence"].append({"phase": "backend", "pid": backend_proc.pid, "health": "ok", "backend_log": report["backend_log"]})
        update_report(report, pointer_path, run_report_path)
        update_report(report, eval_run_report_path, None)

        seed = seed_data(args.backend_port, args.provider_port, db_path)
        report.update(seed)
        report["sqlite_counts_after_seed"] = sqlite_counts(db_path)
        report["status"] = "seeded"
        report["phase_evidence"].append({"phase": "seeding", "ids": {key: seed[key] for key in seed if key.endswith("_id") or key.endswith("_ids") or key.endswith("_revision")}})
        update_report(report, pointer_path, run_report_path)
        update_report(report, eval_run_report_path, None)

        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        if args.hold_server:
            report["status"] = "holding"
            update_report(report, pointer_path, run_report_path)
            update_report(report, eval_run_report_path, None)
            try:
                while True:
                    if backend_proc.poll() is not None:
                        raise FixtureError(f"Backend exited while holding: {backend_proc.returncode}")
                    if provider_proc.poll() is not None:
                        raise FixtureError(f"Provider exited while holding: {provider_proc.returncode}")
                    time.sleep(0.5)
            except KeyboardInterrupt:
                report["phase_evidence"].append({"phase": "hold", "ended_by": "KeyboardInterrupt"})
        report["status"] = "completed"
        return 0
    except Exception as exc:  # noqa: BLE001 - fixture must persist failure evidence
        report["status"] = "failed"
        report["error"] = repr(exc)
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr, flush=True)
        return 1
    finally:
        stop_process(backend_proc, "backend", cleanup_events)
        stop_process(provider_proc, "provider", cleanup_events)
        with contextlib.suppress(Exception):
            report["listener_cleanup"] = {
                "backend_port_open_after_stop": listener_open(args.backend_port),
                "provider_port_open_after_stop": listener_open(args.provider_port),
            }
            report["finished_at"] = now_iso()
            if report.get("status") not in ("failed",):
                report["status"] = "stopped"
            report["sqlite_counts_final"] = sqlite_counts(db_path)
            update_report(report, pointer_path, run_report_path)
            update_report(report, eval_run_report_path, None)


if __name__ == "__main__":
    raise SystemExit(main())
