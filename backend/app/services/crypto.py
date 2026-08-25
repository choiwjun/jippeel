"""api_key 암복호화 (사양 §8.2 / NFR-202).

저장 정책 (v0.3 확정):
  1. 1순위 — Windows DPAPI(Python ``keyring``): 설치 시 마스터 키를 OS 자격증명
     저장소에 보관하고, Fernet으로 본문을 암호화한다. DB에는 암호문만 저장.
  2. 폴백 — keyring 불가 환경(Linux 등): Fernet 로컬 키 파일
     (``~/.jippeel/api_key.key``, 권한 0600) 사용.

폴백 한계 문서화(사양 §8 리스크 2 의무):
  - 로컬 키 파일은 동일 사용자 계정의 프로세스가 읽을 수 있다. 동일 PC 로컬
    공격자(동일 계정 탈취 시나리오)에 대해서는 방어할 수 없다.
  - 디스크 이미지 전체 유출 시 DB 암호문과 키 파일이 함께 유출되면 복호화가
    가능하다. 단일 사용자 로컬 MVP의 위협 모델에서 허용된 잔여 위험이다.
  - 가능하면 DPAPI(keyring) 환경에서 실행할 것.
"""
import os
import stat
from pathlib import Path
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken

KEYRING_SERVICE = "jippeel"
KEYRING_ENTRY = "api-master-key"
FALLBACK_KEY_FILE = Path(
    os.environ.get("JIPPEEL_KEY_FILE", str(Path.home() / ".jippeel" / "api_key.key"))
)


class ApiKeyCipher(Protocol):
    def encrypt(self, plaintext: str) -> str:
        """평문 api_key → 암호문(AiEndpoint.api_key_encrypted 저장 값)."""
        ...

    def decrypt(self, ciphertext: str) -> str:
        """암호문 → 평문 api_key (AI 프록시 호출 시에만 사용)."""
        ...


class PlaceholderCipher:
    """테스트 전용 통과 구현. 실제 런타임에서 사용 금지."""

    def encrypt(self, plaintext: str) -> str:
        return plaintext

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext


class FernetCipher:
    """마스터 키 기반 Fernet 암복호화.

    마스터 키의 보관 위치만 다르면 동일 알고리즘이므로,
    keyring(DPAPI)이든 로컬 키 파일이든 이 클래스 하나로 처리한다.
    """

    def __init__(self, master_key: bytes):
        self._fernet = Fernet(master_key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:  # 키 파일 교체·손상 등
            raise ValueError("api_key 복호화 실패: 마스터 키가 일치하지 않습니다") from exc


def _load_master_key_from_keyring() -> bytes | None:
    """keyring(OS 자격증명 저장소)에서 마스터 키를 조회하고, 없으면 생성해 저장."""
    try:
        import keyring
    except Exception:
        return None

    try:
        stored = keyring.get_password(KEYRING_SERVICE, KEYRING_ENTRY)
        if stored:
            return stored.encode("ascii")
        generated = Fernet.generate_key().decode("ascii")
        keyring.set_password(KEYRING_SERVICE, KEYRING_ENTRY, generated)
        return generated.encode("ascii")
    except Exception:
        # keyring 백엔드 부재(dbus 없는 Linux 등)·쓰기 실패 모두 폴백 대상
        return None


def _load_master_key_from_file() -> bytes:
    """로컬 키 파일에서 마스터 키를 조회하고, 없으면 생성해 저장(0600)."""
    FALLBACK_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if FALLBACK_KEY_FILE.exists():
        key = FALLBACK_KEY_FILE.read_text(encoding="ascii").strip()
        if key:
            return key.encode("ascii")
    key = Fernet.generate_key()
    FALLBACK_KEY_FILE.write_bytes(key)
    try:
        os.chmod(FALLBACK_KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass  # Windows 등 chmod 미지원 파일시스템
    return key


def get_cipher() -> ApiKeyCipher:
    """사양 §8.2 순서대로 cipher 인스턴스를 만든다 (결과 캐시).

    keyring 실패 시 Fernet+로컬 키 파일로 폴백하며, 폴백 사용 사실은
    소스 위치(``_master_key_source``)로 확인할 수 있다.
    """
    global _cipher_cache, _master_key_source
    if _cipher_cache is not None:
        return _cipher_cache
    key = _load_master_key_from_keyring()
    if key is not None:
        _master_key_source = "keyring"
    else:
        key = _load_master_key_from_file()
        _master_key_source = "fallback-file"
    _cipher_cache = FernetCipher(key)
    return _cipher_cache


def reset_cipher_cache() -> None:
    """키 저장소 변경 후 재적용용 (주로 테스트)."""
    global _cipher_cache, _master_key_source
    _cipher_cache = None
    _master_key_source = None


_cipher_cache: ApiKeyCipher | None = None
_master_key_source: str | None = None
