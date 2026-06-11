from types import SimpleNamespace

import pytest

from servers.browser import server
from shared.http_headers import DEFAULT_BROWSER_HTTP_HEADERS, DEFAULT_BROWSER_USER_AGENT


@pytest.mark.anyio
async def test_browser_fetch_sets_basic_browser_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakePage:
        def __init__(self) -> None:
            self.url = "https://example.com/"

        async def goto(self, url: str, wait_until: str, timeout: int):
            captured["goto"] = {"url": url, "wait_until": wait_until, "timeout": timeout}
            return SimpleNamespace(status=200)

        async def screenshot(self, path: str, full_page: bool) -> None:
            captured["screenshot"] = {"path": path, "full_page": full_page}

        async def content(self) -> str:
            return "<html><head><title>Example</title></head><body>Hello</body></html>"

        async def title(self) -> str:
            return "Example"

    class FakeContext:
        async def new_page(self) -> FakePage:
            return FakePage()

        async def close(self) -> None:
            return None

    class FakeBrowser:
        async def new_context(self, **kwargs):
            captured["context"] = kwargs
            return FakeContext()

        async def close(self) -> None:
            return None

    class FakeChromium:
        async def launch(self, headless: bool) -> FakeBrowser:
            captured["headless"] = headless
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

        async def __aenter__(self) -> "FakePlaywright":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(server, "async_playwright", lambda: FakePlaywright())

    response = await server.browser_fetch(
        url="https://example.com",
        timeout=5,
        wait_until="domcontentloaded",
    )

    assert captured["headless"] is True
    assert captured["goto"] == {
        "url": "https://example.com/",
        "wait_until": "domcontentloaded",
        "timeout": 5000,
    }
    assert captured["context"]["user_agent"] == DEFAULT_BROWSER_USER_AGENT
    assert captured["context"]["locale"] == "en-US"
    assert captured["context"]["extra_http_headers"] == DEFAULT_BROWSER_HTTP_HEADERS
    assert response.status_code == 200
    assert response.title == "Example"
    assert "Hello" in response.content
