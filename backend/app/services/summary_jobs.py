"""Provider-free summary backfill planning primitives.

This module only builds deterministic manifests. It does not call a provider,
write MemoryEntry rows, or require a job-table migration.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Literal, Mapping, Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Chapter
from app.services.long_memory import content_sha256

SummaryPlanStatus = Literal["planned", "skipped_empty"]
_SECRET_KEY_NAMES = {"api_key", "apikey", "token", "secret", "password", "credential"}
_SECRET_KEY_SUFFIXES = ("_api_key", "_token", "_secret", "_password", "_credential")


@dataclass(frozen=True)
class SummaryManifestItem:
    project_id: int
    chapter_id: int
    source_revision: int
    source_sha256: str
    source_sort_order: float
    source_content_length: int
    kind: Literal["summary"]
    prompt_version: str
    provider_identity: str
    model_snapshot: str
    request_options_hash: str
    idempotency_key: str
    status: SummaryPlanStatus


def _assert_safe_options(value: Any, path: str = "options") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _SECRET_KEY_NAMES or normalized.endswith(_SECRET_KEY_SUFFIXES):
                raise ValueError(f"secret-bearing request option is not allowed: {path}.{key}")
            _assert_safe_options(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_safe_options(child, f"{path}[{index}]")


def canonical_request_options_hash(options: Mapping[str, Any]) -> str:
    """Hash JSON-safe request options without allowing credentials into the key."""
    _assert_safe_options(options)
    try:
        canonical = json.dumps(
            options,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("request options must be finite JSON values") from exc
    return sha256(canonical.encode("utf-8")).hexdigest()


def _idempotency_key(item: dict[str, Any]) -> str:
    try:
        canonical = json.dumps(
            item,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("idempotency data must be finite JSON values") from exc
    return sha256(canonical.encode("utf-8")).hexdigest()


def build_summary_manifest(
    db: Session,
    *,
    project_id: int,
    chapter_ids: Sequence[int],
    prompt_version: str,
    provider_identity: str,
    model_snapshot: str,
    request_options: Mapping[str, Any],
) -> list[SummaryManifestItem]:
    """Build a sorted, append-free summary plan for an explicit chapter allowlist."""
    if not prompt_version.strip():
        raise ValueError("prompt_version must not be empty")
    if not provider_identity.strip():
        raise ValueError("provider_identity must not be empty")
    if not model_snapshot.strip():
        raise ValueError("model_snapshot must not be empty")

    options_hash = canonical_request_options_hash(request_options)
    unique_ids = sorted(set(chapter_ids))
    chapters: list[Chapter] = []
    for chapter_id in unique_ids:
        try:
            chapter = db.get(Chapter, chapter_id)
        except SQLAlchemyError as exc:
            raise RuntimeError("summary manifest chapter lookup failed") from exc
        if chapter is None:
            raise ValueError("chapter not found")
        if chapter.project_id != project_id:
            raise ValueError("chapter belongs to another project")
        chapters.append(chapter)

    normalized_chapters: list[tuple[Chapter, float]] = []
    for chapter in chapters:
        try:
            sort_order = float(chapter.sort_order)
        except (TypeError, ValueError) as exc:
            raise ValueError("chapter sort_order must be numeric") from exc
        normalized_chapters.append((chapter, sort_order))
    normalized_chapters.sort(key=lambda item: (item[1], item[0].id))
    manifest: list[SummaryManifestItem] = []
    for chapter, source_sort_order in normalized_chapters:
        source_text = chapter.content_md or ""
        source_hash = content_sha256(source_text)
        status: SummaryPlanStatus = "planned" if source_text.strip() else "skipped_empty"
        key_data = {
            "chapter_id": chapter.id,
            "kind": "summary",
            "model_snapshot": model_snapshot,
            "prompt_version": prompt_version,
            "project_id": project_id,
            "provider_identity": provider_identity,
            "request_options_hash": options_hash,
            "source_revision": chapter.revision,
            "source_sha256": source_hash,
        }
        manifest.append(
            SummaryManifestItem(
                project_id=project_id,
                chapter_id=chapter.id,
                source_revision=chapter.revision,
                source_sha256=source_hash,
                source_sort_order=source_sort_order,
                source_content_length=len(source_text),
                kind="summary",
                prompt_version=prompt_version,
                provider_identity=provider_identity,
                model_snapshot=model_snapshot,
                request_options_hash=options_hash,
                idempotency_key=_idempotency_key(key_data),
                status=status,
            )
        )
    return manifest
