import asyncio
from typing import Any

from ddgs import DDGS
from httpx import AsyncClient, HTTPError, Timeout
from mcp.server.fastmcp import FastMCP

from servers.search.schemas import SearchRequest, SearchResponse, SearchResult
from shared.errors import SearchError
from shared.logging import get_logger
from shared.settings import get_settings

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-search")

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def _search_with_ddgs_sync(query: str, max_results: int) -> list[SearchResult]:
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:  # pragma: no cover
        raise SearchError(f"DDGS search failed: {exc}") from exc

    try:
        return [
            SearchResult(
                title=item.get("title") or item.get("heading") or "",
                url=item["href"],
                snippet=item.get("body") or item.get("snippet") or "",
                source="duckduckgo",
            )
            for item in raw_results
            if item.get("href")
        ]
    except Exception as exc:
        raise SearchError(f"Failed to normalize DDGS search results: {exc}") from exc


async def _search_with_ddgs(query: str, max_results: int) -> list[SearchResult]:
    return await asyncio.to_thread(_search_with_ddgs_sync, query, max_results)


def _normalize_brave_results(results: list[dict[str, Any]]) -> list[SearchResult]:
    normalized: list[SearchResult] = []
    for item in results:
        url = item.get("url")
        if not url:
            continue
        normalized.append(
            SearchResult(
                title=item.get("title") or "",
                url=url,
                snippet=item.get("description") or item.get("snippet") or "",
                source="brave",
            )
        )
    return normalized


async def _search_with_brave(query: str, max_results: int) -> list[SearchResult]:
    settings = get_settings()
    if not settings.brave_api_key:
        raise SearchError("BRAVE_API_KEY is required when SEARCH_PROVIDER=brave")

    params = {"q": query, "count": max_results}
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": settings.brave_api_key,
    }

    try:
        async with AsyncClient(timeout=Timeout(settings.http_timeout)) as client:
            response = await client.get(BRAVE_SEARCH_URL, params=params, headers=headers)
            response.raise_for_status()
    except HTTPError as exc:
        raise SearchError(f"Brave search request failed: {exc}") from exc
    except Exception as exc:  # pragma: no cover
        raise SearchError(f"Unexpected Brave search failure: {exc}") from exc

    try:
        payload = response.json()
        raw_results = payload.get("web", {}).get("results", [])
        if not isinstance(raw_results, list):
            raise SearchError("Brave search response is missing web.results")
        return _normalize_brave_results(raw_results)
    except SearchError:
        raise
    except Exception as exc:
        raise SearchError(f"Failed to normalize Brave search results: {exc}") from exc


def _resolve_search_provider() -> str:
    settings = get_settings()
    if settings.search_provider == "auto":
        return "auto"
    return settings.search_provider


def _resolve_requested_provider(provider: str) -> str:
    request = SearchRequest(query="provider-check", provider=provider)
    if request.provider != "auto":
        return request.provider
    return _resolve_search_provider()


def _should_fallback_to_brave(exc: SearchError) -> bool:
    message = str(exc).lower()
    timeout_markers = ("timed out", "timeout", "time-out")
    return any(marker in message for marker in timeout_markers)


@mcp.tool()
async def search_web(
    query: str, max_results: int = 5, provider: str = "auto"
) -> SearchResponse:
    request = SearchRequest(query=query, max_results=max_results, provider=provider)
    provider = _resolve_requested_provider(request.provider)
    logger.info(
        "search_web called",
        extra={
            "query": request.query,
            "max_results": request.max_results,
            "provider": provider,
            "requested_provider": request.provider,
        },
    )

    if provider == "brave":
        results = await _search_with_brave(request.query, request.max_results)
    elif provider == "ddgs":
        results = await _search_with_ddgs(request.query, request.max_results)
    else:
        settings = get_settings()
        try:
            results = await _search_with_ddgs(request.query, request.max_results)
        except SearchError as exc:
            if settings.brave_api_key and _should_fallback_to_brave(exc):
                logger.warning("ddgs timed out, falling back to Brave Search")
                results = await _search_with_brave(request.query, request.max_results)
            else:
                raise

    return SearchResponse(
        message=f"Returned {len(results)} search results",
        query=request.query,
        results=results,
        total_results=len(results),
    )


if __name__ == "__main__":
    mcp.run()
