"""O01 — SillyTavern 카드 PNG import/export 테스트."""

import base64
import io
import json
import struct
import zipfile

import pytest

from app.services import card_png, novelwriter_import


def _create_project(client, title="O01 테스트") -> int:
    res = client.post("/api/v1/projects", json={"title": title})
    assert res.status_code == 201
    return res.json()["id"]


def _texp_chunk(keyword: str, text: str) -> bytes:
    payload = keyword.encode("latin-1") + b"\x00" + text.encode("utf-8")
    return (
        struct.pack(">I", len(payload))
        + b"tEXt"
        + payload
        + struct.pack(">I", card_png._crc(b"tEXt" + payload))
    )


class TestCardPngService:
    def test_roundtrip(self):
        card = {
            "spec": "chara_card_v2",
            "spec_version": "2.0",
            "data": {"name": "테스터", "description": "desc", "personality": "냉정"},
        }
        png = card_png.build_card_png(card)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        parsed = card_png.parse_card_png(png)
        assert parsed["data"]["name"] == "테스터"
        assert parsed["spec"] == "chara_card_v2"

    def test_parse_rejects_non_png(self):
        with pytest.raises(ValueError):
            card_png.parse_card_png(b"not a png at all")

    def test_parse_rejects_png_without_card(self):
        png = card_png.build_card_png({"spec": "chara_card_v2", "data": {"name": "x"}})
        # chara tEXt 청크를 제거한 PNG — IEND 앞 청크를 잘라 재조립하지 않고
        # IHDR+IDAT+IEND만 남긴 최소 PNG를 직접 만든다.
        no_card = card_png._minimal_png()
        with pytest.raises(ValueError, match="chara"):
            card_png.parse_card_png(no_card)

    def test_parse_rejects_bad_base64(self):
        png = (
            b"\x89PNG\r\n\x1a\n"
            + _texp_chunk("chara", "!!!not-base64!!!")
            + card_png._minimal_png()[8:]
        )
        with pytest.raises(ValueError):
            card_png.parse_card_png(png)

    def test_card_field_mapping(self):
        card = {
            "spec": "chara_card_v2",
            "data": {
                "name": "강진우",
                "description": "회귀한 검성",
                "personality": "냉정",
                "first_mes": "인사말",
                "creator_notes": "메모",
            },
        }
        fields = card_png.card_to_character_fields(card)
        assert fields["name"] == "강진우"
        assert fields["personality"] == "냉정"
        assert fields["background"] == "회귀한 검성"
        assert fields["card_json"]["data"]["first_mes"] == "인사말"

    def test_character_to_card_preserves_card_json(self):
        class _C:
            name = "유나"
            personality = "활발"
            appearance = "은발"
            background = "배경"
            card_json = {"data": {"first_mes": "안녕!", "extensions": {"k": 1}}}

        card = card_png.character_to_card(_C())
        assert card["data"]["name"] == "유나"
        assert card["data"]["first_mes"] == "안녕!"
        assert card["data"]["extensions"] == {"k": 1}


class TestCardPngApi:
    def test_export_then_import_roundtrip(self, client):
        pid = _create_project(client)
        res = client.post(
            f"/api/v1/projects/{pid}/characters",
            json={"name": "강진우", "personality": "냉정", "background": "회귀자"},
        )
        assert res.status_code == 201
        chid = res.json()["id"]

        png_res = client.get(f"/api/v1/characters/{chid}/card.png")
        assert png_res.status_code == 200
        assert png_res.headers["content-type"] == "image/png"
        assert "attachment" in png_res.headers["content-disposition"]

        pid2 = _create_project(client, "가져오기 대상")
        imp = client.post(
            f"/api/v1/projects/{pid2}/characters/import-card",
            files={"file": ("card.png", png_res.content, "image/png")},
        )
        assert imp.status_code == 201
        assert imp.json()["name"] == "강진우"
        assert imp.json()["project_id"] == pid2

    def test_import_rejects_non_card_png(self, client):
        pid = _create_project(client)
        res = client.post(
            f"/api/v1/projects/{pid}/characters/import-card",
            files={"file": ("x.png", card_png._minimal_png(), "image/png")},
        )
        assert res.status_code == 422

    def test_import_rejects_garbage(self, client):
        pid = _create_project(client)
        res = client.post(
            f"/api/v1/projects/{pid}/characters/import-card",
            files={"file": ("x.png", b"garbage", "image/png")},
        )
        assert res.status_code == 422


def _nwx(items: list[tuple[str, str, int]]) -> bytes:
    parts = ['<?xml version="1.0"?><novelWriterXML><project name="테스트작품"/><content>']
    for handle, name, order in items:
        parts.append(
            f'<item handle="{handle}" order="{order}" root="NOVEL">'
            f"<name>{name}</name><type>FILE</type><layout>DOCUMENT</layout></item>"
        )
    parts.append("</content></novelWriterXML>")
    return "".join(parts).encode()


def _nws(title: str, body: str) -> bytes:
    return f"%%~name:{title}\n%%~kind:novel/document\n### {title}\n\n{body}\n".encode()


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


class TestNovelWriterImport:
    def test_parse_orders_and_extracts(self):
        files = {
            "nwxProject.nwx": _nwx(
                [("h2", "두번째", 2), ("h1", "첫번째", 1)]
            ),
            "content/h1.nws": _nws("프롤로그", "본문 A"),
            "content/h2.nws": _nws("1화", "본문 B"),
        }
        result = novelwriter_import.parse_project_zip(_zip_bytes(files))
        assert result.project_name == "테스트작품"
        assert [c.title for c in result.chapters] == ["프롤로그", "1화"]
        assert "본문 A" in result.chapters[0].content
        assert "%%~" not in result.chapters[0].content

    def test_title_falls_back_to_item_name(self):
        files = {
            "nwxProject.nwx": _nwx([("h1", "항목이름", 1)]),
            "content/h1.nws": "%%~kind:novel/document\n헤딩 없는 본문".encode(),
        }
        result = novelwriter_import.parse_project_zip(_zip_bytes(files))
        assert result.chapters[0].title == "항목이름"

    def test_skips_non_document_items(self):
        nwx = (
            '<?xml version="1.0"?><novelWriterXML><project name="p"/><content>'
            '<item handle="h1" order="1" root="NOVEL"><name>문서</name>'
            "<type>FILE</type><layout>DOCUMENT</layout></item>"
            '<item handle="h2" order="2" root="NOVEL"><name>폴더</name>'
            "<type>FOLDER</type></item>"
            "</content></novelWriterXML>"
        ).encode()
        files = {
            "nwxProject.nwx": nwx,
            "content/h1.nws": _nws("문서", "본문"),
        }
        result = novelwriter_import.parse_project_zip(_zip_bytes(files))
        assert len(result.chapters) == 1

    def test_rejects_no_nwx(self):
        with pytest.raises(ValueError, match="nwx"):
            novelwriter_import.parse_project_zip(
                _zip_bytes({"readme.txt": b"hi"})
            )

    def test_rejects_empty_document_set(self):
        files = {"nwxProject.nwx": _nwx([])}
        with pytest.raises(ValueError):
            novelwriter_import.parse_project_zip(_zip_bytes(files))


class TestNovelWriterApi:
    def test_import_creates_ordered_chapters(self, client):
        pid = _create_project(client)
        files = {
            "nwxProject.nwx": _nwx([("h2", "둘", 2), ("h1", "하나", 1)]),
            "content/h1.nws": _nws("1화", "첫 본문"),
            "content/h2.nws": _nws("2화", "둘째 본문"),
        }
        res = client.post(
            f"/api/v1/projects/{pid}/import/novelwriter",
            files={"file": ("proj.zip", _zip_bytes(files), "application/zip")},
        )
        assert res.status_code == 201
        body = res.json()
        assert body["created"] == 2
        assert body["project_name"] == "테스트작품"

        chapters = client.get(f"/api/v1/projects/{pid}/chapters").json()
        assert len(chapters) == 2
        assert [c["title"] for c in chapters] == ["1화", "2화"]
        detail = client.get(f"/api/v1/chapters/{chapters[0]['id']}").json()
        assert "첫 본문" in detail["content_md"]

    def test_import_rejects_bad_zip(self, client):
        pid = _create_project(client)
        res = client.post(
            f"/api/v1/projects/{pid}/import/novelwriter",
            files={"file": ("x.zip", b"notzip", "application/zip")},
        )
        assert res.status_code == 422
