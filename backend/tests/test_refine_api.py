"""윤문 API 테스트 — humanize 서브프로세스 모킹 + FR-505 게이트 강제 (M5, Sprint 3)."""
import json

import pytest

from app.services import humanize


DIAGNOSIS_MD = """# 진단 리포트

## A. 번역투
- **A-1** [S1] "~에 대하여/대해서" 남발 — 시그니처: "~에 대해" · 예: 규제에 대해
- **A-3** [S2] "~에 있어(서)" — 시그니처: "에 있어서"

## G. Hedging
- **G-2** [S2] 완곡 표현 — 시그니처: "요구된다"
"""

FINAL_WITH_SUMMARY = ("수정된 본문입니다.\n"
                      "<!-- HUMANIZE-SUMMARY -->\n| 변경률 99% |\n"
                      "<!-- /HUMANIZE-SUMMARY -->")


def make_fake_subprocess(scenario, calls):
    """run_subprocess 대역 — im-not-ai 스크립트 호출과 진단/윤문 셸 명령을 흉내낸다."""
    import subprocess as sp

    def fake_run_subprocess(args, timeout=900, shell=False):
        calls.append({"shell": shell, "args": args})
        if shell:
            cmd = args
            # shlex.quote가 감싼 따옴표 제거(POSIX/Windows 공통)
            out_path = cmd.split(" > ")[-1].strip().strip("'\"")
            if cmd.startswith("diagnose"):
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(scenario["diagnosis_md"])
                return sp.CompletedProcess(cmd, 0, stdout="", stderr="")
            if cmd.startswith("refine"):
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(FINAL_WITH_SUMMARY)
                return sp.CompletedProcess(cmd, 0, stdout="", stderr="")
            raise AssertionError(f"unexpected shell cmd: {cmd}")

        script = args[1]
        if script.endswith("prepare_monolith_input.py"):
            run_dir = args[args.index("--run-dir") + 1]
            metrics = {"route_hint": scenario["route_hint"],
                       "risk_band": "low", "char_count": 70}
            with open(f"{run_dir}/00_metrics.json", "w", encoding="utf-8") as f:
                json.dump(metrics, f)
            # 결합 입력 파일 생성(모킹이므로 원본 복사면 충분)
            with open(f"{run_dir}/01_input.txt", encoding="utf-8") as src, \
                 open(f"{run_dir}/01_input_with_metrics.txt", "w", encoding="utf-8") as dst:
                dst.write(src.read())
            return sp.CompletedProcess(args, 0, stdout="ok", stderr="")
        if script.endswith("verify_gates.py"):
            payload = {"change_rate": {"rate": scenario["ratio"], "verdict": "?"},
                       "gate": {"exit_code": 0}}
            return sp.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")
        raise AssertionError(f"unexpected script call: {args}")

    return fake_run_subprocess


@pytest.fixture()
def mock_pipeline(monkeypatch):
    calls: list[dict] = []

    def _install(**scenario):
        full = {"route_hint": "standard", "ratio": 0.05,
                "refined": "수정된 본문입니다.", "diagnosis_md": DIAGNOSIS_MD}
        full.update(scenario)
        # 진단/윤문 명령 템플릿 주입 — 모킹된 run_subprocess가 흉내낸다
        monkeypatch.setenv(humanize.DIAGNOSE_CMD_ENV, "diagnose {input} > {diagnosis}")
        monkeypatch.setenv(humanize.REFINE_CMD_ENV, "refine {input} > {output}")
        monkeypatch.setattr(humanize, "run_subprocess",
                            make_fake_subprocess(full, calls))
    _install.calls = calls
    return _install


@pytest.fixture()
def chapter(client):
    project = client.post("/api/v1/projects", json={"title": "소설"}).json()
    ch = client.post(f"/api/v1/projects/{project['id']}/chapters", json={}).json()
    client.put(f"/api/v1/chapters/{ch['id']}/content", json={
        "content_md": "AI 규제에 대해 논의할 필요가 있다. 이 문제에 있어서 신중함이 요구된다."})
    return ch


# ---------- 파이프라인 실행 ----------
def test_refine_runs_and_returns_report(client, mock_pipeline, chapter):
    mock_pipeline(route_hint="standard", ratio=0.08)

    resp = client.post("/api/v1/refine", json={"chapter_id": chapter["id"]})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["route_hint"] == "standard"
    assert body["gate"] == "pass"
    assert body["status"] == "ok"
    assert body["changed_ratio"] == 0.08
    assert body["original"].startswith("AI 규제에 대해")
    assert body["refined"] == "수정된 본문입니다."
    # HUMANIZE-SUMMARY 블록은 결과에서 제거되어야 한다
    assert "HUMANIZE-SUMMARY" not in body["refined"]

    # span: 진단 시그니처가 원본 오프셋 span으로 변환(category는 taxonomy ID A~J)
    cats = [(s["category"], s["severity"]) for s in body["spans"]]
    assert ("A", "warn") in cats          # A-1 [S1] → warn
    assert all(s["category"] in list("ABCDEFGHIJ") for s in body["spans"])
    a_span = next(s for s in body["spans"] if s["category"] == "A")
    original = body["original"]
    assert original[a_span["start"]:a_span["end"]] == "에 대해"  # 오프셋 정합

    # 리포트 재조회 + RefineRun 기록(FR-507)
    run = client.get(f"/api/v1/refine/runs/{body['run_id']}").json()
    assert run["changed_ratio"] == 0.08
    assert run["accepted"] is False
    assert run["chapter_id"] == chapter["id"]


def test_light_route_skips_diagnosis(client, mock_pipeline, chapter):
    mock_pipeline(route_hint="light")
    resp = client.post("/api/v1/refine", json={"chapter_id": chapter["id"]})
    assert resp.status_code == 200
    assert resp.json()["route_hint"] == "light"

    shell_cmds = [c["args"] for c in mock_pipeline.calls if c["shell"]]
    assert not any(c.startswith("diagnose") for c in shell_cmds)  # light는 진단 생략
    scripts = [c["args"][1] for c in mock_pipeline.calls if not c["shell"]]
    assert sum("prepare_monolith_input.py" in s for s in scripts) == 1
    assert sum("verify_gates.py" in s for s in scripts) == 1


def test_force_route_overrides_hint(client, mock_pipeline, chapter):
    mock_pipeline(route_hint="light")
    resp = client.post("/api/v1/refine",
                       json={"chapter_id": chapter["id"], "force_route": "heavy"})
    assert resp.json()["route_hint"] == "heavy"


def test_degraded_hint_falls_back_to_standard(client, mock_pipeline, chapter):
    mock_pipeline(route_hint=None)  # shim graceful degrade → standard
    resp = client.post("/api/v1/refine", json={"chapter_id": chapter["id"]})
    assert resp.json()["route_hint"] == "standard"


def test_refine_empty_chapter_rejected(client, chapter):
    client.put(f"/api/v1/chapters/{chapter['id']}/content", json={"content_md": ""})
    resp = client.post("/api/v1/refine", json={"chapter_id": chapter["id"]})
    assert resp.status_code == 400


def test_engine_not_configured_returns_503(client, monkeypatch, mock_pipeline, chapter):
    mock_pipeline(ratio=0.01)
    monkeypatch.delenv(humanize.REFINE_CMD_ENV, raising=False)
    resp = client.post("/api/v1/refine", json={"chapter_id": chapter["id"]})
    assert resp.status_code == 503
    assert "IM_NOT_AI_REFINE_CMD" in resp.json()["detail"]


# ---------- 수락/거절 플로우 ----------
def test_accept_replaces_chapter_content(client, mock_pipeline, chapter):
    mock_pipeline(ratio=0.10)

    body = client.post("/api/v1/refine", json={"chapter_id": chapter["id"]}).json()
    resp = client.post(f"/api/v1/refine/runs/{body['run_id']}/accept")
    assert resp.status_code == 200

    after = client.get(f"/api/v1/chapters/{chapter['id']}").json()
    assert after["content_md"] == "수정된 본문입니다."
    # 자동저장 흐름 유지 — PUT content와 동일하게 word_count_cache 재계산(공백 제외)
    from app.services.wordcount import count_novelpia_chars
    assert after["word_count_cache"] == count_novelpia_chars(after["content_md"])

    run = client.get(f"/api/v1/refine/runs/{body['run_id']}").json()
    assert run["accepted"] is True
    # 재처리 방지
    assert client.post(f"/api/v1/refine/runs/{body['run_id']}/accept").status_code == 409
    assert client.post(f"/api/v1/refine/runs/{body['run_id']}/reject").status_code == 409


def test_reject_keeps_record_only(client, mock_pipeline, chapter):
    mock_pipeline(ratio=0.12)
    body = client.post("/api/v1/refine", json={"chapter_id": chapter["id"]}).json()

    resp = client.post(f"/api/v1/refine/runs/{body['run_id']}/reject")
    assert resp.status_code == 200
    after = client.get(f"/api/v1/chapters/{chapter['id']}").json()
    assert after["content_md"].startswith("AI 규제에 대해")  # 본문 무변경
    run = client.get(f"/api/v1/refine/runs/{body['run_id']}").json()
    assert run["accepted"] is False
    assert run["report_json"]["rejected"] is True

    # 거절된 실행은 수락 불가(상태 일관성) — 다시 윤문을 실행해야 한다
    resp2 = client.post(f"/api/v1/refine/runs/{body['run_id']}/accept")
    assert resp2.status_code == 409
    after2 = client.get(f"/api/v1/chapters/{chapter['id']}").json()
    assert after2["content_md"].startswith("AI 규제에 대해")
