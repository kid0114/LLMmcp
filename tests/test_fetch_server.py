import pytest

from servers.fetch import server
from servers.fetch.schemas import FetchResponse


@pytest.mark.anyio
async def test_fetch_url_resource_decodes_encoded_url(monkeypatch: pytest.MonkeyPatch) -> None:
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

    result = await server.fetch_url_resource("https%3A%2F%2Fexample.com%2Farticle%3Fx%3D1")

    assert captured == {"url": "https://example.com/article?x=1", "timeout": 20}
    assert '"title":"Example"' in result
    assert '"content":"Hello"' in result
