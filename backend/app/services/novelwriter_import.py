"""O01 — novelWriter 프로젝트 zip import (stdlib 전용).

novelWriter 형식: 루트 `.nwx`(XML 프로젝트) + `content/<handle>.nws` 문서.
`.nws`는 `%%~` 메타 헤더 뒤에 본문이 오고, 첫 `#` 계열 헤딩을 제목으로 쓴다.
DOCUMENT layout의 FILE 항목만 회차로 가져오고 `order` 속성 순으로 정렬한다.
"""

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

_HEADING_RE = re.compile(r"^#{1,4}\s+(.+?)\s*$")
_META_PREFIX = "%%~"


@dataclass
class ImportedChapter:
    title: str
    content: str


@dataclass
class NovelWriterImport:
    project_name: str
    chapters: list[ImportedChapter] = field(default_factory=list)


def _find_nwx(zf: zipfile.ZipFile) -> str | None:
    names = [n for n in zf.namelist() if n.lower().endswith(".nwx")]
    return names[0] if names else None


def _nws_content(zf: zipfile.ZipFile, handle: str) -> str | None:
    for candidate in (f"content/{handle}.nws",):
        try:
            raw = zf.read(candidate)
        except KeyError:
            continue
        lines = raw.decode("utf-8", errors="replace").splitlines()
        body = [ln for ln in lines if not ln.startswith(_META_PREFIX)]
        return "\n".join(body).strip()
    return None


def _doc_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match:
            return match.group(1)
    return fallback


def parse_project_zip(zip_bytes: bytes) -> NovelWriterImport:
    """novelWriter 프로젝트 zip을 파스한다. 실패 시 ValueError."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError("not a zip file") from exc
    with zf:
        nwx_name = _find_nwx(zf)
        if nwx_name is None:
            raise ValueError("no .nwx project file in zip")
        try:
            root = ET.fromstring(zf.read(nwx_name))
        except ET.ParseError as exc:
            raise ValueError("malformed .nwx XML") from exc

        project_el = root.find("project")
        project_name = (
            project_el.get("name") if project_el is not None else None
        ) or "novelWriter 프로젝트"

        chapters: list[ImportedChapter] = []
        content_el = root.find("content")
        items = [] if content_el is None else content_el.findall("item")
        ordered = sorted(
            items, key=lambda it: float(it.get("order") or 0)
        )
        for item in ordered:
            item_type = (item.findtext("type") or item.get("type") or "").upper()
            if item_type != "FILE":
                continue
            layout = (
                item.findtext("layout") or item.get("layout") or "DOCUMENT"
            ).upper()
            if layout != "DOCUMENT":
                continue
            handle = item.get("handle") or ""
            body = _nws_content(zf, handle)
            if body is None:
                continue
            name_el = item.find("name")
            fallback = (name_el.text or "").strip() if name_el is not None else ""
            title = _doc_title(body, fallback or handle)
            chapters.append(ImportedChapter(title=title, content=body))

        if not chapters:
            raise ValueError("no importable novel documents")
        return NovelWriterImport(project_name=project_name, chapters=chapters)
