from pathlib import Path
from tempfile import gettempdir

from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright
from trafilatura import extract

from servers.browser.schemas import BrowserRequest, BrowserResponse
from shared.errors import BrowserError, PermissionDeniedError
from shared.http_headers import browser_context_options
from shared.logging import get_logger
from shared.permissions import validate_outbound_url
from shared.settings import get_settings
from shared.site_auth import medium_browser_cookies, site_specific_headers

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-browser")

@mcp.resource("llmmcp://browser/help")
def browser_help_resource() -> str:
    """Static help resource for clients that list resources before tools."""
    return (
        "llmmcp-browser is primarily a tool-based MCP server.\n\n"
        "Preferred tools:\n"
        "- browser_fetch\n\n"
        "Use these tools for JavaScript-rendered page fetches. "
        "Do not use resources/read for ordinary "
        "tool tasks unless this server explicitly advertises a matching resource "
        "template. Empty or minimal MCP resources do not mean the tools are "
        "unavailable."
    )



def _extract_page_content(html: str) -> tuple[str | None, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    extracted = extract(html, include_comments=False, include_tables=False)
    if extracted:
        return title, extracted.strip()

    main = soup.find("main") or soup.body or soup
    cleaned = "\n".join(line.strip() for line in main.get_text("\n").splitlines() if line.strip())
    return title, cleaned


def _is_playwright_timeout(exc: PlaywrightError) -> bool:
    return "Timeout" in str(exc) or "timeout" in str(exc)


async def _goto_with_fallback(page, url: str, wait_until: str, timeout_ms: int):
    try:
        return await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
    except PlaywrightError as exc:
        if wait_until != "domcontentloaded" and _is_playwright_timeout(exc):
            logger.debug(
                "browser_fetch retrying with domcontentloaded",
                extra={"url": url, "wait_until": wait_until, "timeout_ms": timeout_ms},
            )
            return await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        raise


@mcp.tool()
async def browser_fetch(
    url: str, timeout: int = 30, wait_until: str = "networkidle"
) -> BrowserResponse:
    """Fetch JavaScript-rendered web pages with Playwright and extract readable content.

    Use this tool for pages that need browser rendering, login cookies, or SPA execution.
    Do not use resources/read for ordinary URLs; this server exposes browser actions as tools.
    """
    settings = get_settings()

    try:
        validate_outbound_url(url)
        request = BrowserRequest(url=url, timeout=timeout, wait_until=wait_until)
    except PermissionDeniedError:
        raise
    except Exception as exc:
        raise BrowserError(f"Invalid browser request: {exc}") from exc

    timeout_ms = (request.timeout or settings.browser_timeout) * 1000
    screenshot_path = str(Path(gettempdir()) / "llmmcp_browser_preview.png")
    logger.debug(
        "browser_fetch called",
        extra={
            "url": str(request.url),
            "timeout": request.timeout,
            "wait_until": request.wait_until,
        },
    )

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=settings.browser_headless)
            options = browser_context_options()
            specific_headers = site_specific_headers(str(request.url))
            headers = {
                **dict(options["extra_http_headers"]),
                **{
                    key: value
                    for key, value in specific_headers.items()
                    if key not in {"User-Agent", "Cookie"}
                },
            }
            options["extra_http_headers"] = headers
            if user_agent := specific_headers.get("User-Agent"):
                options["user_agent"] = user_agent
            context = await browser.new_context(**options)
            if cookies := medium_browser_cookies(str(request.url)):
                await context.add_cookies(cookies)
            page = await context.new_page()
            response = await _goto_with_fallback(
                page,
                str(request.url),
                request.wait_until,
                timeout_ms,
            )
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
        message="Fetched page with browser successfully",
        url=str(request.url),
        final_url=final_url,
        title=page_title or extracted_title,
        content=content,
        content_length=len(content),
        screenshot_path=screenshot_path,
        status_code=response.status if response is not None else None,
    )


if __name__ == "__main__":
    mcp.run()
