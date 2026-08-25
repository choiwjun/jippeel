"""cipher 저장→복호화 왕복 + 평문 노출 없음 검증 (NFR-202)."""
import pytest

from app.services import crypto


@pytest.fixture(autouse=True)
def isolated_key_file(tmp_path, monkeypatch):
    """테스트마다 독립된 폴백 키 파일을 쓴다."""
    monkeypatch.setattr(crypto, "FALLBACK_KEY_FILE", tmp_path / "keys" / "api_key.key")
    crypto.reset_cipher_cache()
    yield
    crypto.reset_cipher_cache()


def test_fallback_key_file_created_on_first_use():
    cipher = crypto.get_cipher()
    assert crypto._master_key_source == "fallback-file"
    key_file = crypto.FALLBACK_KEY_FILE
    assert key_file.exists()
    # 키 파일 권한(POSIX) 0600 — 소유자만 읽기/쓰기
    import os
    if os.name == "posix":
        mode = key_file.stat().st_mode & 0o777
        assert mode == 0o600
    assert cipher is crypto.get_cipher()  # 캐시 재사용


def test_encrypt_decrypt_roundtrip():
    cipher = crypto.get_cipher()
    plaintext = "sk-live-abc123SECRET"
    ciphertext = cipher.encrypt(plaintext)
    assert ciphertext != plaintext          # 암호문이 평문과 다르고
    assert "abc123" not in ciphertext       # 평문 조각도 없으며
    assert plaintext not in ciphertext
    assert cipher.decrypt(ciphertext) == plaintext  # 왕복 복호화 성공


def test_ciphertext_is_deterministic_format_but_unique():
    cipher = crypto.get_cipher()
    c1 = cipher.encrypt("same-key")
    c2 = cipher.encrypt("same-key")
    assert c1 != c2  # Fernet: 매번 다른 IV → 같은 평문이라도 암호문 상이
    assert cipher.decrypt(c1) == cipher.decrypt(c2) == "same-key"


def test_decrypt_with_wrong_master_key_raises():
    cipher1 = crypto.get_cipher()
    ciphertext = cipher1.encrypt("secret")
    # 키 파일 교체 = 마스터 키 교체 시나리오
    crypto.FALLBACK_KEY_FILE.write_text(
        __import__("cryptography").fernet.Fernet.generate_key().decode("ascii"),
        encoding="ascii",
    )
    crypto.reset_cipher_cache()
    cipher2 = crypto.get_cipher()
    with pytest.raises(ValueError):
        cipher2.decrypt(ciphertext)


def test_endpoint_api_key_stored_encrypted_and_never_returned(client):
    """라우터 경유 저장 → DB 암호문 확인 → 모든 응답에서 평문 부재(NFR-202)."""
    plaintext_key = "sk-my-ultra-secret-123"

    resp = client.post("/api/v1/ai/endpoints", json={
        "name": "LM Studio",
        "base_url": "http://localhost:1234/v1",
        "api_key": plaintext_key,
        "default_model": "qwen3-32b",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["has_api_key"] is True
    assert plaintext_key not in resp.text            # 응답 전체에 평문 없음
    for forbidden in ("api_key", "api_key_encrypted"):
        assert forbidden not in body                 # 키 필드 자체가 노출되지 않음

    # DB에는 암호문만 저장
    from app.database import get_db
    db = next(iter(client.app.dependency_overrides[get_db]()))
    from sqlalchemy import select
    from app.models import AiEndpoint
    row = db.scalars(select(AiEndpoint)).one()
    assert row.api_key_encrypted != plaintext_key
    assert plaintext_key not in (row.api_key_encrypted or "")
    # 암호문으로 왕복 복호화 가능
    assert crypto.get_cipher().decrypt(row.api_key_encrypted) == plaintext_key

    # 목록/단건 조회에서도 평문 미반환
    assert plaintext_key not in client.get("/api/v1/ai/endpoints").text
    assert plaintext_key not in client.patch(
        f"/api/v1/ai/endpoints/{row.id}", json={"name": "renamed"}
    ).text
