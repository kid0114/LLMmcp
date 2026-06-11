from base64 import urlsafe_b64encode
from urllib.parse import quote

import pytest

from servers.fetch import server
from servers.fetch.schemas import FetchResponse
from shared.settings import get_settings
from shared.site_auth import MEDIUM_USER_AGENT


def test_fetch_help_resource_describes_tool_and_templates() -> None:
    result = server.fetch_help_resource()

    assert "fetch_url" in result
    assert "Do not call resources/read with raw https:// URLs" in result
    assert "fetch://url/{encoded_url}" in result
    assert "fetch://url-b64/{encoded_url_b64}" in result


@pytest.mark.anyio
async def test_fetch_url_uses_common_headers_with_medium_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        url = "https://medium.com/p/example"
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html><head><title>Example</title></head><body>Hello</body></html>"

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            captured["client_kwargs"] = kwargs

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setenv("MEDIUM_COOKIE", "uid=123")
    get_settings.cache_clear()
    monkeypatch.setattr(server, "AsyncClient", FakeAsyncClient)

    response = await server.fetch_url("https://medium.com/p/example")

    headers = captured["headers"]
    assert headers["Accept"].startswith("text/html")
    assert headers["User-Agent"] == MEDIUM_USER_AGENT
    assert headers["Cookie"] == "uid=123"
    assert (
        headers["sec-ch-ua"]
        == '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"'
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_fetch_url_resource_decodes_path_encoded_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_fetch_url(url: str, timeout: int = 20) -> FetchResponse:
        captured["url"] = url
        captured["timeout"] = timeout
        return FetchResponse(
            message="Fetched URL successfully",
            url=url,
            status_code=200,
            title="Example",
            content="Hello",
            content_length=5,
        )

    monkeypatch.setattr(server, "_fetch_url", fake_fetch_url)

    url = 'https://github.com/search?q=glow+"open with"+.md&type=text/plain'
    result = await server.fetch_url_resource(quote(url, safe=""))

    assert captured == {"url": url, "timeout": 20}
    assert '"title":"Example"' in result
    assert '"content":"Hello"' in result


@pytest.mark.anyio
async def test_fetch_url_resource_b64_decodes_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_fetch_url(url: str, timeout: int = 20) -> FetchResponse:
        captured["url"] = url
        captured["timeout"] = timeout
        return FetchResponse(
            message="Fetched URL successfully",
            url=url,
            status_code=200,
            title="Example",
            content="Hello",
            content_length=5,
        )

    monkeypatch.setattr(server, "_fetch_url", fake_fetch_url)

    url = 'https://github.com/search?q=glow+"open with"+.md&type=text/plain'
    encoded = urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")
    result = await server.fetch_url_resource_b64(encoded)

    assert captured == {"url": url, "timeout": 20}
    assert '"title":"Example"' in result
