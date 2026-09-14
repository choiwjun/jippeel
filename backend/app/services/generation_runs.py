"""생성 이력 기록 — 작가 피드백 자가개선 E1.

usage.py와 같은 방식으로 자체 SessionLocal을 열어 SSE 스트림 수명과
독립적으로 기록한다. 기록 실패는 삼켜 본 스트림을 절대 막지 않는다
(best-effort). 프롬프트 원문은 저장하지 않고 sha256·주입 내역만 남긴다.
"""
import hashlib
import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Chapter, GenerationOutput, GenerationRun


@dataclass
class OutputSpec:
    """save_run에 전달할 산출물 1건."""

    channel: str  # draft|review|refined|plan|worker
    text: str
    scene_order: int | None = None


def messages_sha256(messages: list[dict]) -> str:
    """canonical JSON(messages)의 sha256 — 프롬프트 원문 대신 식별자로 보존."""
    canonical = json.dumps(messages, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save_run(*, surface: str, project_id: int | None, chapter_id: int | None,
             preset_id: int | None, model: str | None,
             reasoning_effort: str | None, messages: list[dict] | None,
             manifest: dict | None, status: str, wall_ms: int,
             outputs: list[OutputSpec], ai_usage_id: int | None = None,
             applied_rules: list[int] | None = None,
             db: Session | None = None) -> tuple[int | None, dict[str, int]]:
    """run + outputs를 한 세션에 기록하고 (run_id, {key: output_id})를 반환.

    outputs 키: channel — worker는 `worker_{scene_order}`. 동일 채널 중복 시
    마지막 id가 키에 남는다(현재 surface별 채널은 유일).
    """
    try:
        session = db if db is not None else SessionLocal()
        try:
            # project_id 미지정 시 chapter에서 유도 — 작품 격리 스코프 보존
            if project_id is None and chapter_id is not None:
                chapter = session.get(Chapter, chapter_id)
                if chapter is not None:
                    project_id = chapter.project_id
            prompt_chars = sum(len(str(m.get("content") or "")) for m in (messages or []))
            run = GenerationRun(
                project_id=project_id,
                chapter_id=chapter_id,
                surface=surface,
                preset_id=preset_id,
                model=model,
                reasoning_effort=reasoning_effort,
                input_sha256=messages_sha256(messages) if messages else None,
                input_manifest_json=manifest or {},
                prompt_chars=prompt_chars,
                status=status,
                wall_ms=max(wall_ms, 0),
                ai_usage_id=ai_usage_id,
                applied_rules_json=applied_rules,
            )
            session.add(run)
            session.flush()
            output_ids: dict[str, int] = {}
            for spec in outputs:
                if not spec.text:
                    continue
                out = GenerationOutput(
                    run_id=run.id,
                    channel=spec.channel,
                    scene_order=spec.scene_order,
                    output_text=spec.text,
                    output_sha256=hashlib.sha256(spec.text.encode("utf-8")).hexdigest(),
                    output_chars=len(spec.text),
                )
                session.add(out)
                session.flush()
                key = (f"worker_{spec.scene_order}" if spec.channel == "worker"
                       and spec.scene_order is not None else spec.channel)
                output_ids[key] = out.id
            session.commit()
            return run.id, output_ids
        finally:
            if db is None:
                session.close()
    except Exception:  # noqa: BLE001 — 이력 기록은 본 스트림을 절대 막지 않는다
        return None, {}
