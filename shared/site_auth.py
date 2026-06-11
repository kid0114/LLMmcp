from urllib.parse import urlparse

from shared.http_headers import browser_like_headers
from shared.settings import get_settings

MEDIUM_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)


def is_medium_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "medium.com" or host.endswith(".medium.com")


def medium_search_query(query: str) -> str:
    stripped = query.strip()
    lowered = stripped.lower()
    if "site:medium.com" in lowered or "medium.com" in lowered:
        return stripped
    return f"site:medium.com {stripped}"


def medium_cookie_header(url: str) -> str | None:
    if not is_medium_url(url):
        return None
    cookie = get_settings().medium_cookie
    if not cookie:
        return None
    return cookie.strip() or None


def medium_fetch_headers(url: str) -> dict[str, str]:
    if not is_medium_url(url):
        return {}

    headers = browser_like_headers(
        {
            "User-Agent": MEDIUM_USER_AGENT,
            "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        }
    )
    if cookie := medium_cookie_header(url):
        headers["Cookie"] = cookie
    return headers


def medium_browser_context_options(url: str) -> dict[str, object]:
    return {
        "user_agent": MEDIUM_USER_AGENT,
        "extra_http_headers": {
            key: value
            for key, value in medium_fetch_headers(url).items()
            if key not in {"User-Agent", "Cookie"}
        },
        "locale": "en-US",
    }


def site_specific_headers(url: str) -> dict[str, str]:
    if is_medium_url(url):
        return medium_fetch_headers(url)
    return {}


def medium_browser_cookies(url: str) -> list[dict[str, object]]:
    cookie = medium_cookie_header(url)
    if not cookie:
        return []

    cookies: list[dict[str, object]] = []
    for part in cookie.split(";"):
        name, _, value = part.strip().partition("=")
        if not name or not value:
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": ".medium.com",
                "path": "/",
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax",
            }
        )
    return cookies
