from pathlib import Path
from tempfile import gettempdir

from httpx import AsyncClient, HTTPError, Timeout
from mcp.server.fastmcp import FastMCP
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from servers.browser.schemas import BrowserResponse
from servers.browser.server import _extract_page_content
from servers.fetch.schemas import FetchResponse
from servers.fetch.server import _extract_content
from servers.search.schemas import SearchResponse
from servers.search.server import search_web
from shared.errors import BrowserError, FetchError, PermissionDeniedError
from shared.logging import get_logger
from shared.permissions import validate_outbound_url
from shared.settings import get_settings
from shared.site_auth import (
    is_medium_url,
    medium_browser_context_options,
    medium_browser_cookies,
    medium_fetch_headers,
    medium_search_query,
)

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-medium")


@mcp.resource("llmmcp://medium/help")
def medium_help_resource() -> str:
    return (
        "llmmcp-medium is the dedicated Medium MCP server.\n\n"
        "Preferred tools:\n"
        "- search_medium_articles\n"
        "- fetch_medium_url\n"
        "- browser_fetch_medium\n\n"
        "Use this server for Medium-specific discovery and reading. Do not route "
        "Medium queries through generic fetch/browser tools when you want the "
        "Medium-authenticated path."
    )


def _ensure_medium_url(url: str) -> str:
    if not is_medium_url(url):
        raise FetchError("Medium URL required for llmmcp-medium tools")
    return url


async def _fetch_medium_url(url: str, timeout: int = 60) -> FetchResponse:
    settings = get_settings()

    try:
        validate_outbound_url(url)
        _ensure_medium_url(url)
    except PermissionDeniedError:
        raise
    except Exception as exc:
        raise FetchError(f"Invalid fetch request: {exc}") from exc

    effective_timeout = Timeout(timeout or settings.http_timeout)
    logger.debug("fetch_medium_url called", extra={"url": url, "timeout": timeout})
    headers = medium_fetch_headers(url)

    try:
        async with AsyncClient(follow_redirects=True, timeout=effective_timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
    except HTTPError as exc:
        raise FetchError(f"HTTP request failed: {exc}") from exc
    except Exception as exc:  # pragma: no cover
        raise FetchError(f"Unexpected fetch failure: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    title, content = _extract_content(response.text, content_type)
    return FetchResponse(
        message="Fetched Medium URL successfully",
        url=str(response.url),
        status_code=response.status_code,
        title=title,
        content=content,
        content_length=len(content),
    )


async def _browser_fetch_medium(
    url: str, timeout: int = 60, wait_until: str = "domcontentloaded"
) -> BrowserResponse:
    settings = get_settings()

    try:
        validate_outbound_url(url)
        _ensure_medium_url(url)
    except PermissionDeniedError:
        raise
    except Exception as exc:
        raise BrowserError(f"Invalid browser request: {exc}") from exc

    timeout_ms = timeout * 1000
    screenshot_path = str(Path(gettempdir()) / "llmmcp_medium_browser_preview.png")
    logger.debug(
        "browser_fetch_medium called",
        extra={"url": url, "timeout": timeout, "wait_until": wait_until},
    )

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=settings.browser_headless)
            context = await browser.new_context(**medium_browser_context_options(url))
            if cookies := medium_browser_cookies(url):
                await context.add_cookies(cookies)
            page = await context.new_page()
            response = await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            await page.screenshot(path=screenshot_path, full_page=False)
            html = await page.content()
            final_url = page.url
            page_title = await page.title()
            await context.close()
            await browser.close()
    except PlaywrightError as exc:
        raise BrowserError(f"Playwright request failed: {exc}") from exc
    except Exception as exc:  # pragma: no cover
        raise BrowserError(f"Unexpected browser failure: {exc}") from exc

    extracted_title, content = _extract_page_content(html)
    return BrowserResponse(
        message="Fetched Medium page with browser successfully",
        url=url,
        final_url=final_url,
        title=page_title or extracted_title,
        content=content,
        content_length=len(content),
        screenshot_path=screenshot_path,
        status_code=response.status if response is not None else None,
    )


@mcp.tool()
async def search_medium_articles(
    query: str, max_results: int = 10, provider: str = "auto"
) -> SearchResponse:
    """Search Medium articles with Medium-specific scoping."""
    return await search_web(
        query=medium_search_query(query),
        max_results=max_results,
        provider=provider,
    )


@mcp.tool()
async def fetch_medium_url(url: str, timeout: int = 60) -> FetchResponse:
    """Fetch a Medium URL with Medium cookies and browser-like headers."""
    return await _fetch_medium_url(_ensure_medium_url(url), timeout=timeout)


@mcp.tool()
async def browser_fetch_medium(
    url: str, timeout: int = 60, wait_until: str = "domcontentloaded"
) -> BrowserResponse:
    """Fetch a Medium URL with Playwright using Medium-specific defaults."""
    return await _browser_fetch_medium(
        _ensure_medium_url(url),
        timeout=timeout,
        wait_until=wait_until,
    )


if __name__ == "__main__":
    mcp.run()
