from base64 import urlsafe_b64decode
from urllib.parse import unquote

from bs4 import BeautifulSoup
from httpx import AsyncClient, HTTPError, Timeout
from mcp.server.fastmcp import FastMCP
from trafilatura import extract

from servers.fetch.schemas import FetchRequest, FetchResponse
from shared.errors import FetchError, PermissionDeniedError
from shared.http_headers import browser_like_headers
from shared.logging import get_logger
from shared.permissions import validate_outbound_url
from shared.settings import get_settings
from shared.site_auth import site_specific_headers

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

    try:
        async with AsyncClient(follow_redirects=True, timeout=effective_timeout) as client:
            response = await client.get(
                str(request.url),
                headers=browser_like_headers(site_specific_headers(str(request.url))),
            )
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
    HTTPS URLs as MCP resources; resources are only compatibility fallbacks
    for fetch://url/{encoded_url} and fetch://url-b64/{encoded_url_b64}.
    """
    return await _fetch_url(url=url, timeout=timeout)


@mcp.resource("fetch://{encoded_url}")
async def fetch_url_resource_legacy(encoded_url: str) -> str:
    """Legacy compatibility resource for simple percent-encoded URLs.

    Prefer fetch://url/{encoded_url}. The legacy form can fail for URLs that
    contain query strings because URI parsers may treat `&...` as resource URI
    query parameters.
    """
    url = unquote(encoded_url)
    response = await _fetch_url(url=url)
    return response.model_dump_json()


@mcp.resource("fetch://help")
def fetch_help_resource() -> str:
    """Static help resource for clients that list resources before tools."""
    return (
        "llmmcp-fetch is primarily a tool-based MCP server.\n\n"
        "Preferred tool:\n"
        "- fetch_url(url: str, timeout: int = 20): fetch arbitrary HTTP/HTTPS URLs "
        "and extract readable content.\n\n"
        "Do not call resources/read with raw https:// URLs. Raw web URLs are tool "
        "inputs, not MCP resource URIs.\n\n"
        "Compatibility resource templates:\n"
        "- fetch://url/{encoded_url}: percent-encoded full URL\n"
        "- fetch://url-b64/{encoded_url_b64}: URL-safe base64 full URL without padding\n\n"
        "Use fetch_url for normal page reads. Use resource templates only if the "
        "client insists on MCP resources."
    )


@mcp.resource("fetch://url/{encoded_url}")
async def fetch_url_resource(encoded_url: str) -> str:
    """Compatibility resource for clients that try resources/read before tools.

    The entire URL must be percent-encoded, including `?`, `&`, `/`, and spaces.
    Example: fetch://url/https%3A%2F%2Fexample.com%2Farticle%3Fx%3D1%26y%3D2
    """
    url = unquote(encoded_url)
    response = await _fetch_url(url=url)
    return response.model_dump_json()


@mcp.resource("fetch://url-b64/{encoded_url_b64}")
async def fetch_url_resource_b64(encoded_url_b64: str) -> str:
    """Compatibility resource using URL-safe base64 without padding.

    This is the most robust fallback for URLs with complex query strings.
    """
    padding = "=" * (-len(encoded_url_b64) % 4)
    url = urlsafe_b64decode(f"{encoded_url_b64}{padding}").decode("utf-8")
    response = await _fetch_url(url=url)
    return response.model_dump_json()


if __name__ == "__main__":
    mcp.run()
