"""고정 GPT OAuth 브릿지 provider 설정.

jippeel은 OAuth 토큰을 직접 다루지 않는다. ``openai-oauth`` 사이드카가
``~/.codex/auth.json``을 관리하고, 앱은 localhost의 OpenAI 호환 transport만
호출한다. 이 모듈은 사용자가 endpoint/API key를 저장하지 않도록 집필 경로에
필요한 최소 provider 설정만 환경변수로 제공한다.
"""
from dataclasses import dataclass
import os
from urllib.parse import urlsplit

DEFAULT_BASE_URL = "http://127.0.0.1:10531/v1"
DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "xhigh"
PROVIDER_NAME = "ChatGPT OAuth"
_ALLOWED_REASONING_EFFORTS = frozenset({"minimal", "low", "medium", "high", "xhigh"})


class OAuthProviderConfigError(ValueError):
    """고정 GPT OAuth provider 설정이 유효하지 않을 때 발생한다."""


@dataclass(frozen=True)
class GptOAuthProvider:
    """실제 OAuth credential 없이 집필에 필요한 provider 메타데이터."""

    name: str
    base_url: str
    default_model: str
    reasoning_effort: str


def get_provider() -> GptOAuthProvider:
    """환경변수에서 고정 provider 설정을 읽어 반환한다.

    ``JIPPEEL_GPT_OAUTH_BASE_URL``은 로컬 브릿지 주소만 허용한다. 원격 URL을
    허용하면 OAuth 브릿지 대신 임의 서버로 요청이 전송될 수 있으므로 fail-fast한다.
    """
    base_url = os.getenv("JIPPEEL_GPT_OAUTH_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    try:
        parsed = urlsplit(base_url)
        hostname = parsed.hostname
    except ValueError as exc:
        raise OAuthProviderConfigError(
            "GPT OAuth 브릿지 주소가 올바른 URL이 아닙니다."
        ) from exc
    if (
        parsed.scheme != "http"
        or hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise OAuthProviderConfigError(
            "GPT OAuth 브릿지 주소는 credential/query 없는 localhost http URL이어야 합니다."
        )
    if parsed.path != "/v1":
        raise OAuthProviderConfigError(
            "GPT OAuth 브릿지 주소는 /v1 경로만 허용합니다."
        )

    model = os.getenv("JIPPEEL_GPT_MODEL", DEFAULT_MODEL).strip()
    if not model:
        raise OAuthProviderConfigError("GPT OAuth 모델을 비워 둘 수 없습니다.")

    reasoning_effort = os.getenv(
        "JIPPEEL_GPT_REASONING_EFFORT", DEFAULT_REASONING_EFFORT
    ).strip().lower()
    if reasoning_effort not in _ALLOWED_REASONING_EFFORTS:
        allowed = ", ".join(sorted(_ALLOWED_REASONING_EFFORTS))
        raise OAuthProviderConfigError(
            f"GPT OAuth 추론 강도는 다음 중 하나여야 합니다: {allowed}"
        )

    return GptOAuthProvider(
        name=PROVIDER_NAME,
        base_url=base_url,
        default_model=model,
        reasoning_effort=reasoning_effort,
    )
