import pytest
from pydantic import ValidationError

from shared.settings import Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 8765
    assert settings.http_timeout == 20
    assert settings.browser_timeout == 30
    assert settings.browser_headless is True
    assert settings.allowlist_domains == []


def test_settings_parse_allowlist_domains_from_string() -> None:
    settings = Settings(ALLOWLIST_DOMAINS="example.com, docs.example.com")
    assert settings.allowlist_domains == ["example.com", "docs.example.com"]


def test_settings_parse_allowlist_domains_from_json_string() -> None:
    settings = Settings(ALLOWLIST_DOMAINS='["example.com", "docs.example.com"]')
    assert settings.allowlist_domains == ["example.com", "docs.example.com"]


def test_settings_parse_allowlist_domains_from_env_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWLIST_DOMAINS", "example.com, docs.example.com")
    assert Settings().allowlist_domains == ["example.com", "docs.example.com"]


def test_settings_parse_browser_headless_from_env_style_value() -> None:
    settings = Settings(BROWSER_HEADLESS="false")
    assert settings.browser_headless is False


def test_settings_accepts_local_file_root_and_github_token() -> None:
    settings = Settings(LOCAL_FILE_ROOT="/tmp/project", GITHUB_TOKEN="token")
    assert settings.local_file_root == "/tmp/project"
    assert settings.github_token == "token"


def test_settings_default_search_provider_is_auto() -> None:
    settings = Settings()
    assert settings.search_provider == "auto"


def test_settings_normalize_search_provider() -> None:
    settings = Settings(SEARCH_PROVIDER="BrAvE")
    assert settings.search_provider == "brave"


@pytest.mark.parametrize("blocked_port", [1213, 8000, 12345])
def test_settings_reject_reserved_ports(blocked_port: int) -> None:
    with pytest.raises(ValidationError, match="reserved and cannot be used"):
        Settings(PORT=blocked_port)


def test_settings_reject_invalid_search_provider() -> None:
    with pytest.raises(ValidationError, match="SEARCH_PROVIDER must be one of"):
        Settings(SEARCH_PROVIDER="google")
