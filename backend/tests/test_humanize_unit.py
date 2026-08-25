"""FR-505 변경률 게이트 경계값 + span 파서 단위 테스트."""
import pytest

from app.services import humanize


# ---------- decide_gate 경계값 (30% 경고 / 50% 차단) ----------
@pytest.mark.parametrize("ratio,expected", [
    (0.0, "pass"),
    (0.2999, "pass"),
    (0.30, "warn"),    # 30% 경계 — 경고 시작
    (0.31, "warn"),
    (0.4999, "warn"),
    (0.50, "block"),   # 50% 경계 — 차단(im-not-ai CHANGE_RATE_ABORT와 동일)
    (0.51, "block"),
    (1.0, "block"),
])
def test_decide_gate_boundaries(ratio, expected):
    assert humanize.decide_gate(ratio) == expected


def test_gate_values_match_im_not_ai_constants():
    """기준값이 im-not-ai metrics_v2의 상수와 동기화되어 있는지 방어 검증."""
    from pathlib import Path
    mv2 = Path.home() / ".agents/im-not-ai/skills/humanize-korean/references/metrics_v2.py"
    if not mv2.exists():
        pytest.skip("im-not-ai 미설치 환경")
    text = mv2.read_text(encoding="utf-8")
    warn_line = next(l for l in text.splitlines() if l.startswith("CHANGE_RATE_WARN"))
    abort_line = next(l for l in text.splitlines() if l.startswith("CHANGE_RATE_ABORT"))
    assert float(warn_line.split("=")[1].split("#")[0].strip()) == humanize.WARN_RATIO
    assert float(abort_line.split("=")[1].split("#")[0].strip()) == humanize.BLOCK_RATIO


def test_verify_gates_blocked_even_if_script_says_ok(monkeypatch):
    """게이트 스크립트가 OK를 보고해도 백엔드 비율 판정이 우선한다(FR-505 강제)."""
    import json
    import subprocess as sp

    def fake_run(args, timeout=900, shell=False):
        payload = {"change_rate": {"rate": 0.62}, "gate": {"exit_code": 0}}
        return sp.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(humanize, "run_subprocess", fake_run)
    result = humanize.verify_gates(before="a.txt", after="b.txt")
    assert result.changed_ratio == 0.62
    assert result.verdict == "block"  # 스크립트 exit code와 무관하게 차단


def test_verify_gates_unparseable_output_is_conservative(monkeypatch):
    import subprocess as sp

    def fake_run(args, timeout=900, shell=False):
        return sp.CompletedProcess(args, 0, stdout="이상한 출력", stderr="")

    monkeypatch.setattr(humanize, "run_subprocess", fake_run)
    result = humanize.verify_gates(before="a.txt", after="b.txt")
    assert result.verdict == "block"  # 파싱 실패 시 rate=1.0(보수적) 처리


# ---------- span 파서 ----------
ORIGINAL = "AI 규제에 대해 논의할 필요가 있다. 이 문제에 있어서 신중함이 요구된다."

DIAGNOSIS = """## A. 번역투
- **A-1** [S1] "~에 대하여/대해서" 남발 — 시그니처: "~에 대해" · 예문 생략
- **A-3** [S2] "~에 있어(서)" — 시그니처: "에 있어서"

## G. Hedging
- **G-2** 완곡 표현 — 시그니처: "요구된다"
"""


def test_parse_spans_offsets_and_categories():
    spans = humanize.parse_spans(DIAGNOSIS, ORIGINAL)
    by_cat = {s["category"]: s for s in spans}
    assert set(by_cat) == {"A", "G"}
    for s in spans:
        assert ORIGINAL[s["start"]:s["end"]] in ("에 대해", "에 있어서", "요구된다")
        assert s["severity"] in ("info", "warn")
    # A 카테고리 첫 매치는 S1 → warn
    assert by_cat["A"]["severity"] == "warn"


def test_parse_spans_skips_unmatched_signatures():
    diagnosis = '- **B-2** [S2] buzzword 과다 — 시그니처: "seamless"'
    assert humanize.parse_spans(diagnosis, ORIGINAL) == []  # 원문에 없는 시그니처는 스킵


def test_parse_spans_empty_diagnosis():
    assert humanize.parse_spans("", ORIGINAL) == []


# ---------- strip_summary ----------
def test_strip_summary_removes_block_and_fallback():
    with_block = "본문\n<!-- HUMANIZE-SUMMARY -->\n표\n<!-- /HUMANIZE-SUMMARY -->"
    assert humanize.strip_summary(with_block) == "본문"
    unclosed = "본문\n<!-- HUMANIZE-SUMMARY -->\n표..."
    assert humanize.strip_summary(unclosed) == "본문"


# ---------- 서브프로세스 실패 처리 ----------
def test_shim_failure_raises_humanize_error(monkeypatch, tmp_path):
    import subprocess as sp

    def fake_run(args, timeout=900, shell=False):
        return sp.CompletedProcess(args, 1, stdout="", stderr="boom")

    monkeypatch.setattr(humanize, "run_subprocess", fake_run)
    with pytest.raises(humanize.HumanizeError):
        humanize.compute_metrics("텍스트", tmp_path / "run")


def test_missing_skill_scripts_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(humanize, "SKILL_SCRIPTS", tmp_path / "nowhere")
    with pytest.raises(humanize.HumanizeError):
        humanize._check_script("prepare_monolith_input.py")
