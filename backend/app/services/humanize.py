"""im-not-ai(~/.agents/im-not-ai) 윤문 파이프라인 서브프로세스 래퍼 (사양 §5 M5).

파이프라인 (humanize-korean SKILL.md v2.3 준수):
  1. 지표 계산 — scripts/prepare_monolith_input.py shim → 00_metrics.json
     (route_hint: light|standard|heavy, graceful degrade 시 standard)
  2. 진단(standard·heavy) — 외부 진단 명령(IM_NOT_AI_DIAGNOSE_CMD) → 02_diagnosis.md
     → shim 재실행(--diagnosis)으로 진단 결합 입력 생성
  3. 윤문 — 외부 윤문 명령(IM_NOT_AI_REFINE_CMD) → final.md
  4. 게이트 — scripts/verify_gates.py --json (철칙 #4, 결정적 판정)

변경률 게이트(FR-505)는 백엔드에서도 강제한다:
  changed_ratio >= 0.30 → warn / >= 0.50 → block(윤문본 채택 금지)
기준값은 im-not-ai references/metrics_v2.py의 CHANGE_RATE_WARN/ABORT와 동일.

외부 진단/윤문 명령 템플릿(환경변수):
  IM_NOT_AI_DIAGNOSE_CMD  예) "claude -p \"$(cat {input}) ... > {diagnosis}\""
  IM_NOT_AI_REFINE_CMD    예) "claude -p \"$(cat {input}) ... > {output}\""
  플레이스홀더: {run_dir} {input} {input_combined} {diagnosis} {output}
미설정 시 HumanizeNotConfigured → 라우터가 503으로 변환한다.
진단/윤문은 본질적으로 LLM 에이전트 콜이므로 배포 환경별 명령을 주입받는 구조다.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

SKILL_SCRIPTS = Path(
    os.environ.get("IM_NOT_AI_ROOT", str(Path.home() / ".agents" / "im-not-ai"))
) / "scripts"

SHIM_SCRIPT = "prepare_monolith_input.py"
GATES_SCRIPT = "verify_gates.py"
DIAGNOSE_CMD_ENV = "IM_NOT_AI_DIAGNOSE_CMD"
REFINE_CMD_ENV = "IM_NOT_AI_REFINE_CMD"

SUBPROCESS_TIMEOUT = 900  # 초
WARN_RATIO = 0.30   # im-not-ai CHANGE_RATE_WARN
BLOCK_RATIO = 0.50  # im-not-ai CHANGE_RATE_ABORT

_SUMMARY_RE = re.compile(r"<!--\s*HUMANIZE-SUMMARY-->.*?<!--\s*/\s*HUMANIZE-SUMMARY-->",
                         re.DOTALL)
_PATTERN_ID_RE = re.compile(r"\b([A-J])-?(\d{1,2})\b")
_SEVERITY_RE = re.compile(r"\[S([123])\]")
_QUOTED_RE = re.compile(r"[\u201c\u2018\u00ab\"]([^\u201d\u2019\u00bb\"]{2,40})[\u201d\u2019\u00bb\"]")


class HumanizeError(Exception):
    """서브프로세스 실패 등 래퍼 오류."""


class HumanizeNotConfigured(HumanizeError):
    """진단/윤문 명령이 설정되지 않음."""


@dataclass
class GateResult:
    verdict: str          # pass | warn | block
    exit_code: int
    changed_ratio: float
    raw: dict = field(default_factory=dict)


def run_subprocess(args, timeout: float = SUBPROCESS_TIMEOUT,
                   shell: bool = False) -> subprocess.CompletedProcess:
    """모든 외부 호출(shim·게이트·진단/윤문 명령)은 이 함수를 경유한다 (테스트 모킹 지점).

    encoding을 utf-8로 고정한다 — 미지정 시 Windows는 시스템 로캘(cp949)로
    디코딩해 한글 출력에서 UnicodeDecodeError가 난다(QA 재현: verify_gates).
    """
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          timeout=timeout, shell=shell)


def _check_script(name: str) -> Path:
    path = SKILL_SCRIPTS / name
    if not path.exists():
        raise HumanizeError(f"im-not-ai 스크립트를 찾을 수 없습니다: {path}")
    return path


# ---------- 1. 지표 계산 ----------
def compute_metrics(text: str, run_dir: Path, genre: str = "essay") -> dict:
    """shim 실행 → 00_metrics.json 파싱. route_hint·위험도 등 정량 지표 반환."""
    shim = _check_script(SHIM_SCRIPT)
    run_dir.mkdir(parents=True, exist_ok=True)
    input_path = run_dir / "01_input.txt"
    input_path.write_text(text, encoding="utf-8")

    proc = run_subprocess(
        ["python3", str(shim), "--run-dir", str(run_dir), "--genre", genre],
        timeout=60,
    )
    if proc.returncode != 0:
        raise HumanizeError(f"shim 실행 실패: {proc.stderr.strip()[:500]}")
    metrics_path = run_dir / "00_metrics.json"
    if not metrics_path.exists():
        raise HumanizeError("00_metrics.json이 생성되지 않았습니다")
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def resolve_route(metrics: dict, force_route: str | None) -> str:
    """FR-502 — 사용자 지정 최우선, 없으면 shim route_hint, degrade 시 standard."""
    if force_route:
        return force_route
    hint = metrics.get("route_hint")
    return hint if hint in ("light", "standard", "heavy") else "standard"


# ---------- 2~3. 진단·윤문 ----------
def _render_cmd(template: str, placeholders: dict[str, str]) -> list[str]:
    """템플릿에 shlex.quote를 적용해 안전한 argv를 만든다 (shell=False 실행)."""
    from shlex import quote

    rendered = template.format(**{k: quote(v) for k, v in placeholders.items()})
    # 템플릿 작성 편의를 위해 shell 문법(| && > $( ))을 허용한다 → shell=True
    return rendered


def _run_external(template_env: str, placeholders: dict[str, str], outputs: list[Path],
                  what: str) -> None:
    template = os.environ.get(template_env)
    if not template:
        raise HumanizeNotConfigured(
            f"{what} 명령이 설정되지 않았습니다. 환경변수 {template_env} 를 설정하세요."
        )
    cmd = _render_cmd(template, placeholders)
    try:
        proc = run_subprocess(cmd, shell=True)
    except subprocess.TimeoutExpired as exc:
        raise HumanizeError(f"{what} 시간 초과({SUBPROCESS_TIMEOUT}초)") from exc
    if proc.returncode != 0:
        raise HumanizeError(f"{what} 실패(exit={proc.returncode}): {proc.stderr.strip()[:500]}")
    missing = [p for p in outputs if not p.exists()]
    if missing:
        raise HumanizeError(f"{what} 산출 파일이 없습니다: {[str(m) for m in missing]}")


def run_diagnosis(run_dir: Path, genre: str) -> str:
    """진단 1콜 → 02_diagnosis.md 내용 반환."""
    diagnosis_path = run_dir / "02_diagnosis.md"
    _run_external(
        DIAGNOSE_CMD_ENV,
        {"run_dir": str(run_dir),
         "input": str(run_dir / "01_input_with_metrics.txt"),
         "diagnosis": str(diagnosis_path)},
        [diagnosis_path],
        "진단",
    )
    return diagnosis_path.read_text(encoding="utf-8")


def combine_diagnosis(run_dir: Path, genre: str) -> Path:
    """shim --diagnosis 재실행 → [진단→정량블록→원문] 결합 입력 경로 반환."""
    shim = _check_script(SHIM_SCRIPT)
    proc = run_subprocess(
        ["python3", str(shim), "--run-dir", str(run_dir), "--genre", genre,
         "--diagnosis", str(run_dir / "02_diagnosis.md")],
        timeout=60,
    )
    if proc.returncode != 0:
        raise HumanizeError(f"진단 결합 실패: {proc.stderr.strip()[:500]}")
    return run_dir / "01_input_with_metrics.txt"


def run_refine_engine(run_dir: Path) -> str:
    """윤문 1콜 → final.md 본문(HUMANIZE-SUMMARY 제거) 반환."""
    final_path = run_dir / "final.md"
    _run_external(
        REFINE_CMD_ENV,
        {"run_dir": str(run_dir),
         "input": str(run_dir / "01_input_with_metrics.txt"),
         "diagnosis": str(run_dir / "02_diagnosis.md"),
         "output": str(final_path)},
        [final_path],
        "윤문",
    )
    return strip_summary(final_path.read_text(encoding="utf-8"))


def strip_summary(text: str) -> str:
    """final.md 말미 <!-- HUMANIZE-SUMMARY --> 블록 제거 (본문만 저장·반환)."""
    cleaned = _SUMMARY_RE.sub("", text).strip()
    # 닫는 태그 없는 형태 폴백
    idx = cleaned.find("<!-- HUMANIZE-SUMMARY")
    if idx != -1:
        cleaned = cleaned[:idx].strip()
    return cleaned


# ---------- span 추출 (부록05 §⑤-5, taxonomy ID A~J 고정) ----------
def parse_spans(diagnosis_md: str, original: str, max_spans: int = 100) -> list[dict]:
    """진단 마크다운에서 패턴 ID(A-n~J-n)와 시그니처 인용구를 뽑아 원본 오프셋 span으로 변환.

    원문에서 정확히 일치하는 구간을 찾지 못한 탐지는 건너뛴다(오프셋 보정 금지 —
    부정확한 하이라이트보다 누락이 낫다).
    """
    lines = diagnosis_md.splitlines()
    # 카테고리 severity 집계 — 같은 카테고리 안에 [S1] 탐지가 하나라도 있으면
    # 해당 카테고리 전체를 warn으로 승격 (S1이 최우선 위험 등급)
    warn_categories = {m.group(1) for line in lines
                       if (m := _PATTERN_ID_RE.search(line)) and "[S1]" in line}

    spans: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for line in lines:
        if len(spans) >= max_spans:
            break
        id_match = _PATTERN_ID_RE.search(line)
        if not id_match:
            continue
        category = id_match.group(1)
        severity = "warn" if category in warn_categories else "info"
        message = line.strip().lstrip("-* ").strip()[:200]
        for quoted in _QUOTED_RE.findall(line):
            core = _signature_core(quoted)
            start = original.find(core)
            if start == -1:
                continue
            end = start + len(core)
            if (start, end) in seen:
                continue
            seen.add((start, end))
            spans.append({
                "category": category,
                "start": start,
                "end": end,
                "severity": severity,
                "message": message,
            })
            break
    spans.sort(key=lambda s: s["start"])
    return spans


def _signature_core(quoted: str) -> str:
    """시그니처 인용구에서 원문 검색용 코어를 추출.

    "~에 대해(서)" 같은 선택 괄호와 '~', '/' 표기를 정리하고 가장 긴 조각을 택한다.
    """
    fragments = re.split(r"[/\n]", quoted.replace("~", "").replace("…", ""))
    cores: list[str] = []
    for frag in fragments:
        frag = re.sub(r"[()]", "", frag).strip()
        if len(frag) >= 2:
            cores.append(frag)
    return max(cores, key=len) if cores else quoted.strip()


# ---------- 4. 게이트 ----------
def decide_gate(changed_ratio: float, exit_code: int | None = None) -> str:
    """FR-505 백엔드 강제 판정. exit_code(im-not-ai 게이트)와 무관하게 비율로 재판정한다.

    30% 미만 pass · 30% 이상 warn · 50% 이상 block.
    """
    if changed_ratio >= BLOCK_RATIO:
        return "block"
    if changed_ratio >= WARN_RATIO:
        return "warn"
    return "pass"


def verify_gates(before: Path, after: Path, genre: str = "essay") -> GateResult:
    """im-not-ai verify_gates.py 실행 → JSON 파싱 + 백엔드 자체 판정(decide_gate).

    스크립트 exit code(0/1/2/3)는 참고로 남기고, 최종 gate는 변경률 기준
    백엔드 규칙(FR-505)으로 결정한다 — 과윤문 차단을 우회 불가하게 만들기 위함.
    """
    gates = _check_script(GATES_SCRIPT)
    try:
        proc = run_subprocess(
            ["python3", str(gates), "--before", str(before), "--after", str(after),
             "--genre", genre, "--json"],
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise HumanizeError("게이트 스크립트 시간 초과") from exc
    raw: dict = {}
    try:
        raw = json.loads(_extract_json(proc.stdout))
    except (ValueError, json.JSONDecodeError):
        if proc.returncode == 3:
            raise HumanizeError(f"게이트 판정 불가: {proc.stderr.strip()[:300]}") from None
    ratio = float(raw.get("change_rate", {}).get("rate", 1.0))  # 파싱 실패 시 보수적 처리
    return GateResult(
        verdict=decide_gate(ratio, proc.returncode),
        exit_code=proc.returncode,
        changed_ratio=ratio,
        raw=raw,
    )


def _extract_json(stdout: str) -> str:
    """stdout에서 첫 '{'부터 끝 JSON 블록을 잘라낸다."""
    start = stdout.find("{")
    if start == -1:
        raise ValueError("no json")
    return stdout[start:]


# ---------- 전체 파이프라인 ----------
def run_pipeline(text: str, force_route: str | None = None, genre: str = "essay",
                 work_parent: Path | None = None) -> dict:
    """진단→윤문→게이트 전체 실행. 반환 키:
    route_hint, refined, changed_ratio, gate, spans, report(metrics/gate raw), work_dir
    """
    work_root = Path(work_parent or tempfile.mkdtemp(prefix="jippeel-refine-"))
    work_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=str(work_root)))

    metrics = compute_metrics(text, run_dir, genre)
    route = resolve_route(metrics, force_route)

    diagnosis_md = ""
    if route in ("standard", "heavy"):
        diagnosis_md = run_diagnosis(run_dir, genre)
        combine_diagnosis(run_dir, genre)

    refined = run_refine_engine(run_dir)

    gates = verify_gates(run_dir / "01_input.txt", run_dir / "final.md", genre)
    status = "blocked" if gates.verdict == "block" else "ok"
    spans = parse_spans(diagnosis_md, text) if diagnosis_md else []

    return {
        "route_hint": route,
        "refined": refined,
        "changed_ratio": gates.changed_ratio,
        "gate": gates.verdict,
        "status": status,
        "spans": spans,
        "report": {"metrics": metrics, "gates": gates.raw},
        "work_dir": str(work_root),
    }


def cleanup_workdir(work_dir: str | Path) -> None:
    shutil.rmtree(work_dir, ignore_errors=True)
