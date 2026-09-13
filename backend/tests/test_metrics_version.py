"""V04 — 외부 im-not-ai metrics_v2.py 버전 동기화 검증기 테스트.

합성 TEMP 파일로 계약 검사를 검증한다. 실제 외부 스킬은 실행하지 않는다 —
외부 파일은 import/exec 없이 AST로만 파싱한다.
"""
import pytest

from app.services import humanize
from app.services.metrics_version import (
    expected_contract,
    verify_metrics_module,
)

MATCHING_MODULE = '''
CHANGE_RATE_WARN = 0.30
CHANGE_RATE_ABORT = 0.50


def compute_all_v2(text, genre="essay"):
    return {"risk_band": "low", "text_len": len(text)}
'''

MISMATCHING_MODULE = '''
CHANGE_RATE_WARN = 0.40
CHANGE_RATE_ABORT = 0.45


def compute_all_v2(text, genre="essay"):
    return {}
'''


def _write(tmp_path, content):
    path = tmp_path / "metrics_v2.py"
    path.write_text(content, encoding="utf-8")
    return path


# ---------- 계약 표면 ----------

def test_expected_contract_matches_call_sites():
    """expected_contract는 quality.py 호출부·humanize.py 상수와 동기화된다."""
    contract = expected_contract()
    assert contract["function"] == "compute_all_v2"
    assert contract["params"][:2] == ["text", "genre"]
    assert contract["constants"]["CHANGE_RATE_WARN"] == humanize.WARN_RATIO
    assert contract["constants"]["CHANGE_RATE_ABORT"] == humanize.BLOCK_RATIO


# ---------- happy path ----------

def test_matching_module_passes(tmp_path):
    report = verify_metrics_module(_write(tmp_path, MATCHING_MODULE))
    assert report.ok and report.found
    assert report.mismatches == []
    assert set(report.checked) >= {
        "compute_all_v2 signature",
        "CHANGE_RATE_WARN",
        "CHANGE_RATE_ABORT",
        "warn<=abort",
    }


def test_module_with_extra_content_passes(tmp_path):
    """계약 외 상수·함수가 있어도 필요 계약만 충족하면 통과."""
    report = verify_metrics_module(_write(tmp_path, MATCHING_MODULE + (
        "\nEXTRA = 1\n\ndef helper():\n    pass\n"
    )))
    assert report.ok


def test_annotated_signature_passes(tmp_path):
    """타입 주석이 붙은 시그니처도 허용한다."""
    report = verify_metrics_module(_write(tmp_path, (
        "CHANGE_RATE_WARN = 0.30\nCHANGE_RATE_ABORT = 0.50\n"
        "def compute_all_v2(text: str, genre: str = \"essay\") -> dict:\n"
        "    return {}\n"
    )))
    assert report.ok


# ---------- 파일 상태 ----------

def test_missing_file_reports_not_found(tmp_path):
    report = verify_metrics_module(tmp_path / "metrics_v2.py")
    assert not report.ok and not report.found
    assert report.mismatches  # 이유 포함


def test_unparseable_module_reports_not_crashes(tmp_path):
    path = _write(tmp_path, "def broken(:\n")
    report = verify_metrics_module(path)
    assert not report.ok and report.found
    assert any("parse" in m.lower() or "syntax" in m.lower()
               for m in report.mismatches)


def test_non_utf8_module_reports_not_crashes(tmp_path):
    path = tmp_path / "metrics_v2.py"
    path.write_bytes(b"\xff\xfe\x00\x01")
    report = verify_metrics_module(path)
    assert not report.ok


# ---------- 계약 불일치 ----------

def test_constant_mismatch_reported(tmp_path):
    report = verify_metrics_module(_write(tmp_path, MISMATCHING_MODULE))
    assert not report.ok
    assert any("CHANGE_RATE_WARN" in m for m in report.mismatches)
    assert any("CHANGE_RATE_ABORT" in m for m in report.mismatches)


def test_missing_function_reported(tmp_path):
    report = verify_metrics_module(_write(tmp_path, (
        "CHANGE_RATE_WARN = 0.30\nCHANGE_RATE_ABORT = 0.50\n"
    )))
    assert not report.ok
    assert any("compute_all_v2" in m for m in report.mismatches)


def test_wrong_signature_reported(tmp_path):
    report = verify_metrics_module(_write(tmp_path, (
        "CHANGE_RATE_WARN = 0.30\nCHANGE_RATE_ABORT = 0.50\n"
        "def compute_all_v2(content, style):\n    return {}\n"
    )))
    assert not report.ok
    assert any("signature" in m for m in report.mismatches)


def test_missing_constant_reported(tmp_path):
    report = verify_metrics_module(_write(tmp_path, (
        "CHANGE_RATE_WARN = 0.30\n"
        "def compute_all_v2(text, genre):\n    return {}\n"
    )))
    assert not report.ok
    assert any("CHANGE_RATE_ABORT" in m for m in report.mismatches)


def test_inverted_warn_abort_reported(tmp_path):
    report = verify_metrics_module(_write(tmp_path, (
        "CHANGE_RATE_WARN = 0.60\nCHANGE_RATE_ABORT = 0.50\n"
        "def compute_all_v2(text, genre):\n    return {}\n"
    )))
    assert not report.ok
    assert any(">" in m and "관계" in m for m in report.mismatches)


def test_positional_only_genre_rejected(tmp_path):
    """compute_all_v2(text, genre, /) — genre=\"essay\" 키워드 호출이 실패한다."""
    report = verify_metrics_module(_write(tmp_path, (
        "CHANGE_RATE_WARN = 0.30\nCHANGE_RATE_ABORT = 0.50\n"
        "def compute_all_v2(text, genre, /):\n    return {}\n"
    )))
    assert not report.ok
    assert any("positional-only" in m for m in report.mismatches)


def test_extra_required_positional_rejected(tmp_path):
    """compute_all_v2(text, genre, mode) — 호출부는 위치 인자 1개만 넘긴다."""
    report = verify_metrics_module(_write(tmp_path, (
        "CHANGE_RATE_WARN = 0.30\nCHANGE_RATE_ABORT = 0.50\n"
        "def compute_all_v2(text, genre, mode):\n    return {}\n"
    )))
    assert not report.ok
    assert any("signature mismatch" in m for m in report.mismatches)


def test_extra_defaulted_positional_passes(tmp_path):
    """compute_all_v2(text, genre, mode=\"x\") — 호출 호환."""
    report = verify_metrics_module(_write(tmp_path, (
        "CHANGE_RATE_WARN = 0.30\nCHANGE_RATE_ABORT = 0.50\n"
        "def compute_all_v2(text, genre, mode=\"x\"):\n    return {}\n"
    )))
    assert report.ok


def test_async_function_rejected(tmp_path):
    """async compute_all_v2 — 동기 호출 계약 위반."""
    report = verify_metrics_module(_write(tmp_path, (
        "CHANGE_RATE_WARN = 0.30\nCHANGE_RATE_ABORT = 0.50\n"
        "async def compute_all_v2(text, genre):\n    return {}\n"
    )))
    assert not report.ok
    assert any("async" in m for m in report.mismatches)


def test_null_byte_source_reports_not_crashes(tmp_path):
    """null byte는 UTF-8 디코딩은 통과하지만 compile 단계에서 거부된다."""
    path = tmp_path / "metrics_v2.py"
    path.write_bytes(b"x = 1\n\x00\n")
    report = verify_metrics_module(path)
    assert not report.ok and report.found


def test_non_literal_constant_reported_not_silently_passed(tmp_path):
    """계산식·참조 상수는 평가 불가를 보고한다 — 조용한 통과 금지."""
    report = verify_metrics_module(_write(tmp_path, (
        "CHANGE_RATE_WARN = 0.3\nCHANGE_RATE_ABORT = 2 * 0.25\n"
        "def compute_all_v2(text, genre):\n    return {}\n"
    )))
    assert not report.ok
    assert any("CHANGE_RATE_ABORT" in m for m in report.mismatches)


# ---------- 외부 파일 미실행 보장 ----------

def test_module_is_never_executed(tmp_path):
    """검증이 모듈을 exec/import하지 않는다 — side-effect 코드가 있어도 안전."""
    path = _write(tmp_path, (
        "import pathlib\n"
        "pathlib.Path(r'" + str(tmp_path / "EXECUTED") + "').write_text('x')\n"
        "CHANGE_RATE_WARN = 0.30\nCHANGE_RATE_ABORT = 0.50\n"
        "def compute_all_v2(text, genre):\n    return {}\n"
    ))
    report = verify_metrics_module(path)
    assert report.ok
    assert not (tmp_path / "EXECUTED").exists()


def test_report_serializable(tmp_path):
    import json
    report = verify_metrics_module(_write(tmp_path, MATCHING_MODULE))
    payload = report.to_dict()
    json.dumps(payload)
    assert payload["ok"] is True and payload["mismatches"] == []
