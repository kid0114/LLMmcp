from pathlib import Path
from tempfile import gettempdir

from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright
from trafilatura import extract

from servers.browser.schemas import BrowserRequest, BrowserResponse
from shared.errors import BrowserError, PermissionDeniedError
from shared.logging import get_logger
from shared.permissions import validate_outbound_url
from shared.settings import get_settings

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-browser")


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


@mcp.tool()
async def browser_fetch(
    url: str, timeout: int = 30, wait_until: str = "networkidle"
) -> BrowserResponse:
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
    logger.info(
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
            page = await browser.new_page()
            response = await page.goto(
                str(request.url),
                wait_until=request.wait_until,
                timeout=timeout_ms,
            )
            await page.screenshot(path=screenshot_path, full_page=False)
            html = await page.content()
            final_url = page.url
            page_title = await page.title()
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
