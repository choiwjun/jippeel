"""O01 — SillyTavern V2 카드 PNG import/export (stdlib 전용).

PNG의 tEXt 청크에 `chara` 키워드로 base64 JSON 카드를 싣는 ST 호환 형식.
내보내기는 고정 1×1 RGBA 픽셀을 쓴다 — 이미지가 아니라 카드 데이터가 목적이다.
"""

import base64
import binascii
import json
import struct
import zlib
from typing import Any

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_CARD_KEYWORD = b"chara"

# 카드의 ST V2 data 키 중 Character 고정 필드로 흡수되지 않는 확장 키는 card_json에 통째로 보존한다.
_FIELD_MAP = {
    "name": "name",
    "personality": "personality",
    "description": "background",
}


def _crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", _crc(kind + payload))
    )


def _minimal_png() -> bytes:
    """카드 청크 없는 최소 유효 1×1 RGBA PNG."""
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    raw = b"\x00\x00\x00\x00\x00"  # filter byte + RGBA 픽셀
    idat = zlib.compress(raw)
    return (
        _PNG_SIG
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", idat)
        + _chunk(b"IEND", b"")
    )


def _card_payload(card: dict) -> bytes:
    text = base64.b64encode(json.dumps(card, ensure_ascii=False).encode("utf-8"))
    return _CARD_KEYWORD + b"\x00" + text


def build_card_png(card: dict) -> bytes:
    """카드 dict를 싣은 PNG 바이트를 만든다."""
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00\x00")
    return (
        _PNG_SIG
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"tEXt", _card_payload(card))
        + _chunk(b"IDAT", idat)
        + _chunk(b"IEND", b"")
    )


def _decode_text_chunk(kind: bytes, payload: bytes) -> tuple[bytes, bytes] | None:
    """tEXt/iTXt 페이로드에서 (keyword, text)를 꺼낸다. iTXt는 압축 플래그를 건너뛴다."""
    nul = payload.find(b"\x00")
    if nul <= 0:
        return None
    keyword = payload[:nul]
    if kind == b"tEXt":
        return keyword, payload[nul + 1 :]
    if kind == b"iTXt":
        rest = payload[nul + 1 :]
        if len(rest) < 2:
            return None
        compressed = rest[0] == 1
        # comp_method(1) + lang(\0-terminated) + translated(\0-terminated)
        after = rest[2:]
        lang_end = after.find(b"\x00")
        if lang_end < 0:
            return None
        after2 = after[lang_end + 1 :]
        trans_end = after2.find(b"\x00")
        if trans_end < 0:
            return None
        text = after2[trans_end + 1 :]
        if compressed:
            try:
                text = zlib.decompress(text)
            except zlib.error:
                return None
        return keyword, text
    return None


def parse_card_png(data: bytes) -> dict:
    """PNG에서 `chara` 카드를 꺼낸다. 없거나 손상이면 ValueError."""
    if not data.startswith(_PNG_SIG):
        raise ValueError("not a PNG file")
    pos = len(_PNG_SIG)
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        if len(payload) != length:
            raise ValueError("truncated PNG chunk")
        if kind in (b"tEXt", b"iTXt"):
            decoded = _decode_text_chunk(kind, payload)
            if decoded and decoded[0] == _CARD_KEYWORD:
                try:
                    raw = base64.b64decode(decoded[1], validate=True)
                    card = json.loads(raw.decode("utf-8"))
                except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
                    raise ValueError("malformed chara card payload") from exc
                if not isinstance(card, dict):
                    raise ValueError("chara card is not an object")
                return card
        if kind == b"IEND":
            break
        pos += 12 + length
    raise ValueError("no chara card chunk in PNG")


def _card_data(card: dict) -> dict:
    data = card.get("data")
    return data if isinstance(data, dict) else card


def character_to_card(character: Any) -> dict:
    """Character ORM/객체 → ST V2 카드. 기존 card_json의 ST 키를 보존한다."""
    existing = _card_data(character.card_json) if character.card_json else {}
    data: dict = dict(existing)
    data["name"] = character.name or existing.get("name", "")
    if character.personality:
        data["personality"] = character.personality
    description_parts = [p for p in (character.background, character.appearance) if p]
    if description_parts:
        data["description"] = "\n\n".join(description_parts)
    data.setdefault("description", existing.get("description", ""))
    data.setdefault("personality", existing.get("personality", ""))
    return {"spec": "chara_card_v2", "spec_version": "2.0", "data": data}


def card_to_character_fields(card: dict) -> dict:
    """ST 카드 → Character 생성 필드. 전체 카드는 card_json에 보존해 왕복성을 확보한다."""
    data = _card_data(card)
    fields: dict = {"card_json": card}
    for card_key, field in _FIELD_MAP.items():
        value = data.get(card_key)
        if isinstance(value, str) and value:
            fields[field] = value
    return fields
