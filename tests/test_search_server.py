import asyncio
from typing import Any

import pytest

from servers.search.server import (
    _normalize_brave_results,
    _resolve_requested_provider,
    _resolve_search_provider,
    _should_fallback_to_brave,
    search_web,
)
from shared.errors import SearchError
from shared.settings import get_settings


def test_normalize_brave_results() -> None:
    results = _normalize_brave_results(
        [
            {
                "title": "Example",
                "url": "https://example.com",
                "description": "Snippet",
            }
        ]
    )
    assert len(results) == 1
    assert results[0].title == "Example"
    assert str(results[0].url) == "https://example.com/"
    assert results[0].snippet == "Snippet"
    assert results[0].source == "brave"


def test_resolve_search_provider_defaults_to_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)
    get_settings.cache_clear()
    assert _resolve_search_provider() == "auto"


def test_resolve_search_provider_defaults_to_auto_without_brave_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)
    get_settings.cache_clear()
    assert _resolve_search_provider() == "auto"


def test_resolve_requested_provider_prefers_explicit_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "ddgs")
    get_settings.cache_clear()
    assert _resolve_requested_provider("brave") == "brave"


def test_resolve_requested_provider_uses_settings_when_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    get_settings.cache_clear()
    assert _resolve_requested_provider("auto") == "brave"


def test_should_fallback_to_brave_for_timeout() -> None:
    assert _should_fallback_to_brave(SearchError("DDGS search failed: operation timed out"))


def test_should_not_fallback_to_brave_for_non_timeout() -> None:
    assert not _should_fallback_to_brave(SearchError("DDGS search failed: bad response"))


def test_search_web_uses_brave(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    get_settings.cache_clear()

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "web": {
                    "results": [
                        {
                            "title": "Example",
                            "url": "https://example.com",
                            "description": "Snippet",
                        }
                    ]
                }
            }

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        async def get(
            self, url: str, params: dict[str, Any], headers: dict[str, str]
        ) -> FakeResponse:
            assert "api.search.brave.com" in url
            assert params["q"] == "mcp"
            assert headers["X-Subscription-Token"] == "test-key"
            return FakeResponse()

    monkeypatch.setattr("servers.search.server.AsyncClient", FakeClient)

    response = asyncio.run(search_web("mcp", 1))
    assert response.total_results == 1
    assert response.results[0].source == "brave"


def test_search_web_explicit_provider_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "ddgs")
    get_settings.cache_clear()

    async def fake_ddgs(query: str, max_results: int) -> list[Any]:
        raise AssertionError("ddgs should not be used when provider=brave")

    async def fake_brave(query: str, max_results: int) -> list[Any]:
        return _normalize_brave_results(
            [
                {
                    "title": "Example",
                    "url": "https://example.com",
                    "description": "Snippet",
                }
            ]
        )

    monkeypatch.setattr("servers.search.server._search_with_ddgs", fake_ddgs)
    monkeypatch.setattr("servers.search.server._search_with_brave", fake_brave)

    response = asyncio.run(search_web("mcp", 1, provider="brave"))
    assert response.total_results == 1
    assert response.results[0].source == "brave"


def test_search_web_rejects_brave_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    get_settings.cache_clear()

    with pytest.raises(SearchError, match="BRAVE_API_KEY is required"):
        asyncio.run(search_web("mcp", 1))


def test_search_web_auto_falls_back_to_brave_on_ddgs_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)
    get_settings.cache_clear()

    async def fake_ddgs(query: str, max_results: int) -> list[Any]:
        raise SearchError("DDGS search failed: operation timed out")

    async def fake_brave(query: str, max_results: int) -> list[Any]:
        return _normalize_brave_results(
            [
                {
                    "title": "Example",
                    "url": "https://example.com",
                    "description": "Snippet",
                }
            ]
        )

    monkeypatch.setattr("servers.search.server._search_with_ddgs", fake_ddgs)
    monkeypatch.setattr("servers.search.server._search_with_brave", fake_brave)

    response = asyncio.run(search_web("mcp", 1))
    assert response.total_results == 1
    assert response.results[0].source == "brave"


def test_search_web_auto_does_not_fallback_on_non_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)
    get_settings.cache_clear()

    async def fake_ddgs(query: str, max_results: int) -> list[Any]:
        raise SearchError("DDGS search failed: decode error")

    monkeypatch.setattr("servers.search.server._search_with_ddgs", fake_ddgs)

    with pytest.raises(SearchError, match="decode error"):
        asyncio.run(search_web("mcp", 1))
