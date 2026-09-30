"""윤문 Copy-Item fallback 실동작 프로브 (2026-09-16).

prod.sh/dev.sh의 IM_NOT_AI_*_CMD 스텁이 Windows Python의 shell=True(cmd)에서
실제로 파일을 복사하는지 검증한다. WSL bash에서 실행:

    backend/.venv/Scripts/python.exe docs/audits/refine-copy-fallback-probe.py

모킹 없이 humanize._render_cmd + run_subprocess 실 경로를 사용한다.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.services import humanize  # noqa: E402

TEMPLATE_DIAGNOSE = (
    'powershell -NoProfile -Command '
    '"Copy-Item -LiteralPath {input} -Destination {diagnosis}"'
)
TEMPLATE_REFINE = (
    'powershell -NoProfile -Command '
    '"Copy-Item -LiteralPath {input} -Destination {output}"'
)

run = Path(tempfile.mkdtemp(prefix="probe-"))
src = run / "in.txt"
src.write_text("probe 한글 본문", encoding="utf-8")

ok = True
for name, template, dest_name in (
    ("diagnose", TEMPLATE_DIAGNOSE, "02_diagnosis.md"),
    ("refine", TEMPLATE_REFINE, "final.md"),
):
    dst = run / dest_name
    cmd = humanize._render_cmd(template, {
        "input": str(src), "diagnosis": str(dst), "output": str(dst)})
    proc = humanize.run_subprocess(cmd, shell=True)
    passed = (proc.returncode == 0 and dst.exists()
              and dst.read_text(encoding="utf-8") == "probe 한글 본문")
    ok = ok and passed
    print(f"[{name}] rc={proc.returncode} exists={dst.exists()} "
          f"content_ok={passed}")
    print(f"  rendered: {cmd}")
    if proc.stderr:
        print(f"  stderr: {proc.stderr[:300]}")

print("PROBE", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
