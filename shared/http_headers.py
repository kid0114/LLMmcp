DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

DEFAULT_BROWSER_LOCALE = "en-US"

DEFAULT_BROWSER_HTTP_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="126", "Google Chrome";v="126", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}


def browser_like_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": DEFAULT_BROWSER_USER_AGENT,
        **DEFAULT_BROWSER_HTTP_HEADERS,
    }
    if extra:
        headers.update(extra)
    return headers


def browser_context_options() -> dict[str, object]:
    return {
        "user_agent": DEFAULT_BROWSER_USER_AGENT,
        "extra_http_headers": DEFAULT_BROWSER_HTTP_HEADERS,
        "locale": DEFAULT_BROWSER_LOCALE,
    }
