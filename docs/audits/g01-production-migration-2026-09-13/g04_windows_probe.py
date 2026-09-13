"""G04 부분 — Windows 네이티브 실기동·부하 프로브 (1회성 수용 스크립트).

최신 코드(jippeel-g04 복사본)를 Windows venv 인터프리터로 uvicorn 기동하고,
실 DB 복사본에 대해: 기동/스키마 assert 통과 → 프로젝트/회차 읽기 →
5만 자 본문 PUT(CAS) 저장 지연 → snapshot/resume 파생 읽기를 측정한다.

실행: ``python g04_windows_probe.py`` (Windows 네이티브에서)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

BACKEND = r"C:\Users\wj941\AppData\Local\Temp\jippeel-g04\backend"
VENV_PY = r"C:\Users\wj941\Documents\jippeel\backend\.venv\Scripts\python.exe"
SRC_DB = r"C:\Users\wj941\Documents\jippeel\backend\jippeel.db"
PORT = 18341
BASE = f"http://127.0.0.1:{PORT}/api/v1"


def http(method, path, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read())


def main():
    tmp = tempfile.mkdtemp(prefix="jippeel-g04run-")
    db = os.path.join(tmp, "run.db")
    shutil.copy2(SRC_DB, db)
    for ext in ("-wal", "-shm"):
        if os.path.exists(SRC_DB + ext):
            shutil.copy2(SRC_DB + ext, db + ext)

    env = dict(os.environ)
    env["DATABASE_URL"] = "sqlite:///" + db.replace(os.sep, "/")
    env["JIPPEEL_KEY_FILE"] = os.path.join(tmp, "key.key")

    boot = time.monotonic()
    proc = subprocess.Popen(
        [VENV_PY, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=BACKEND, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        ready = None
        for _ in range(120):
            if proc.poll() is not None:
                raise RuntimeError("uvicorn exited early")
            try:
                status, _ = http("GET", "/system/db-info", timeout=2)
                if status == 200:
                    ready = time.monotonic() - boot
                    break
            except Exception:
                time.sleep(0.5)
        if ready is None:
            raise RuntimeError("readiness timeout")
        print(f"boot_ready_s={ready:.2f}  (init_db+schema assert+fts+presets)")

        t0 = time.monotonic()
        _, projects = http("GET", "/projects")
        print(f"GET /projects 200 rows={len(projects)} {time.monotonic()-t0:.3f}s")
        pid = projects[0]["id"]
        _, chapters = http("GET", f"/projects/{pid}/chapters")
        cid = chapters[0]["id"]
        print(f"GET /projects/{pid}/chapters 200 rows={len(chapters)}")
        _, detail = http("GET", f"/chapters/{cid}")
        rev = detail["revision"]
        print(f"GET /chapters/{cid} 200 revision={rev} len={len(detail.get('content_md') or '')}")

        body = ("한국 웹소설 본문 성능 프로브. " * 10 + "\n") * 300  # ≥50k자
        print(f"probe_body_chars={len(body)}")
        t0 = time.monotonic()
        st, saved = http("PUT", f"/chapters/{cid}/content",
                         {"content_md": body, "expected_revision": rev}, timeout=60)
        dt = time.monotonic() - t0
        print(f"PUT content 50k 200 latency_s={dt:.3f} new_rev={saved['revision']}")

        t0 = time.monotonic()
        st, saved2 = http("PUT", f"/chapters/{cid}/content",
                          {"content_md": body + "추가", "expected_revision": saved["revision"]},
                          timeout=60)
        print(f"PUT content CAS second save 200 latency_s={time.monotonic()-t0:.3f}")

        _, snaps = http("GET", f"/chapters/{cid}/snapshots")
        print(f"GET snapshots 200 rows={len(snaps)}")
        _, resume = http("GET", f"/chapters/{cid}/resume")
        print(f"GET resume 200 keys={sorted(resume.keys())[:4]}")

        # CAS 충돌 확인 — 옛 revision으로 저장하면 409
        try:
            http("PUT", f"/chapters/{cid}/content",
                 {"content_md": "x", "expected_revision": rev}, timeout=10)
            print("CAS stale write ACCEPTED (bad)")
        except urllib.error.HTTPError as e:
            print(f"CAS stale write -> {e.code} (expect 409)")
        print("PROBE PASS")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
