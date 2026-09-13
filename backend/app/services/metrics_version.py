"""V04 — 외부 im-not-ai metrics_v2.py 버전 동기화 검증기.

quality.py가 요구하는 호출 계약(compute_all_v2(text, genre))과
humanize.py가 "동일"이라고 주장하는 상수(CHANGE_RATE_WARN/ABORT)를
외부 파일을 **실행하지 않고** AST 파싱으로 비교한다.

- 외부 코드 미실행 — ast.parse만 사용 (side-effect 안전, 격리 가드 적합).
- 파일 부재·파싱 실패는 예외가 아니라 보고 — 진단 도구는 손상 입력에 크래시하지 않는다.
- 실물 metrics_v2.py가 설치된 환경에서 verify_metrics_module(실물 경로) 1회 실행이
  실제 버전 동기화 확인 절차다.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services import humanize

_FUNCTION = "compute_all_v2"
_PARAMS = ("text", "genre")
_CONSTANTS = {
    "CHANGE_RATE_WARN": humanize.WARN_RATIO,
    "CHANGE_RATE_ABORT": humanize.BLOCK_RATIO,
}


def expected_contract() -> dict[str, Any]:
    """코드가 외부 모듈에 요구하는 계약 표면 — 문서와 코드의 단일 출처."""
    return {
        "module": "metrics_v2.py",
        "function": _FUNCTION,
        "params": list(_PARAMS),
        "constants": dict(_CONSTANTS),
        "call_site": "app.services.quality.try_metrics_v2 (genre=\"essay\" 전달)",
        "ratio_site": "app.services.humanize WARN_RATIO/BLOCK_RATIO",
    }


@dataclass
class MetricsVersionReport:
    ok: bool
    found: bool
    mismatches: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """실물 파일 검증 실행 시 그대로 붙여넣을 수 있는 직렬화 형태."""
        return {
            "ok": self.ok,
            "found": self.found,
            "mismatches": list(self.mismatches),
            "checked": list(self.checked),
        }


def _literal_number(node: ast.expr) -> float | None:
    """모듈 수준 상수가 평가 가능한 숫자 리터럴인지 — 그 외는 None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    return None


def verify_metrics_module(path: Path) -> MetricsVersionReport:
    """metrics_v2.py 경로를 AST로 검증 — 실행 없이 계약만 비교한다."""
    path = Path(path)
    if not path.is_file():
        return MetricsVersionReport(
            ok=False, found=False,
            mismatches=[f"metrics_v2.py not found: {path}"],
        )
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, ValueError, RecursionError) as exc:
        # ValueError는 UnicodeDecodeError 등 디코딩 오류를 포함하고
        # SyntaxError는 별도 계열 — compile 단계 오류를 모두 보고로 변환한다
        return MetricsVersionReport(
            ok=False, found=True,
            mismatches=[f"parse failed: {exc}"],
        )

    mismatches: list[str] = []
    checked: list[str] = []

    functions = {
        n.name: n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    constants: dict[str, float | None] = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            constants[node.targets[0].id] = _literal_number(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                constants[node.target.id] = _literal_number(node.value)

    # 1) compute_all_v2 시그니처 — quality.try_metrics_v2의 호출 형태와 일치해야 한다
    #    호출 형태: compute_all_v2(text값, genre="essay") — 위치 1개 + 키워드 1개
    fn = functions.get(_FUNCTION)
    if fn is None:
        mismatches.append(f"{_FUNCTION} function missing")
    elif isinstance(fn, ast.AsyncFunctionDef):
        mismatches.append(f"{_FUNCTION} is async — 동기 호출 계약 위반")
    else:
        args = fn.args
        posonly = [a.arg for a in args.posonlyargs]
        positional = posonly + [a.arg for a in args.args]
        required_positional = len(positional) - len(args.defaults)
        if positional[:2] != list(_PARAMS):
            mismatches.append(
                f"signature mismatch: {_FUNCTION}({', '.join(positional[:2])}) "
                f"expected ({', '.join(_PARAMS)})"
            )
        elif "genre" in posonly:
            mismatches.append(
                'signature mismatch: genre is positional-only — '
                'genre="essay" keyword call 실패'
            )
        elif required_positional > 2 and args.vararg is None:
            mismatches.append(
                f"signature mismatch: {required_positional} required positional "
                "params but call site passes 1 positional"
            )
        else:
            checked.append(f"{_FUNCTION} signature")

    # 2) 변경률 게이트 상수 — humanize.py의 WARN/BLOCK 기준과 동일해야 한다
    for name, expected in _CONSTANTS.items():
        if name not in constants:
            mismatches.append(f"{name} missing")
        elif constants[name] is None:
            mismatches.append(f"{name} not a literal number — 평가 불가")
        elif constants[name] != expected:
            mismatches.append(
                f"{name}={constants[name]} != expected {expected}"
            )
        else:
            checked.append(name)

    warn, abort = constants.get("CHANGE_RATE_WARN"), constants.get("CHANGE_RATE_ABORT")
    if warn is not None and abort is not None:
        if warn <= abort:
            checked.append("warn<=abort")
        else:
            mismatches.append(
                f"warn {warn} > abort {abort} — 게이트 순서 관계 파손"
            )

    return MetricsVersionReport(
        ok=not mismatches, found=True,
        mismatches=mismatches, checked=checked,
    )
