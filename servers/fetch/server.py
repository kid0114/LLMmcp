from urllib.parse import unquote

from bs4 import BeautifulSoup
from httpx import AsyncClient, HTTPError, Timeout
from mcp.server.fastmcp import FastMCP
from trafilatura import extract

from servers.fetch.schemas import FetchRequest, FetchResponse
from shared.errors import FetchError, PermissionDeniedError
from shared.logging import get_logger
from shared.permissions import validate_outbound_url
from shared.settings import get_settings
from shared.site_auth import medium_fetch_headers

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-fetch")


def _extract_content(text: str, content_type: str) -> tuple[str | None, str]:
    if "html" not in content_type:
        cleaned = text.strip()
        return None, cleaned

    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    extracted = extract(text, include_comments=False, include_tables=False)
    if extracted:
        return title, extracted.strip()

    body = soup.body or soup
    cleaned = "\n".join(line.strip() for line in body.get_text("\n").splitlines() if line.strip())
    return title, cleaned


async def _fetch_url(url: str, timeout: int = 20) -> FetchResponse:
    settings = get_settings()

    try:
        validate_outbound_url(url)
        request = FetchRequest(url=url, timeout=timeout)
    except PermissionDeniedError:
        raise
    except Exception as exc:
        raise FetchError(f"Invalid fetch request: {exc}") from exc

    effective_timeout = Timeout(request.timeout or settings.http_timeout)
    logger.debug("fetch_url called", extra={"url": str(request.url), "timeout": request.timeout})
    headers = medium_fetch_headers(str(request.url))

    try:
        async with AsyncClient(follow_redirects=True, timeout=effective_timeout) as client:
            response = await client.get(str(request.url), headers=headers)
            response.raise_for_status()
    except HTTPError as exc:
        raise FetchError(f"HTTP request failed: {exc}") from exc
    except Exception as exc:  # pragma: no cover
        raise FetchError(f"Unexpected fetch failure: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    title, content = _extract_content(response.text, content_type)
    return FetchResponse(
        message="Fetched URL successfully",
        url=str(response.url),
        status_code=response.status_code,
        title=title,
        content=content,
        content_length=len(content),
    )


@mcp.tool()
async def fetch_url(url: str, timeout: int = 20) -> FetchResponse:
    """Fetch arbitrary HTTP/HTTPS URLs and extract readable content.

    Use this tool to read web pages returned by search tools. Do not use
    resources/read for ordinary URLs. This server does not expose arbitrary
    HTTPS URLs as MCP resources; resources are only a compatibility fallback
    for fetch://{encoded_url}.
    """
    return await _fetch_url(url=url, timeout=timeout)


@mcp.resource("fetch://{encoded_url}")
async def fetch_url_resource(encoded_url: str) -> str:
    """Compatibility resource for clients that try resources/read before tools.

    The URL must be percent-encoded, for example:
    fetch://https%3A%2F%2Fexample.com%2Farticle
    """
    url = unquote(encoded_url)
    response = await _fetch_url(url=url)
    return response.model_dump_json()


if __name__ == "__main__":
    mcp.run()
