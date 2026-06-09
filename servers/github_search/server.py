from typing import Any
from urllib.parse import quote

from bs4 import BeautifulSoup
from httpx import Client, HTTPError, Timeout
from mcp.server.fastmcp import FastMCP

from servers.github_search.schemas import (
    GitHubCodeResult,
    GitHubCodeSearchResponse,
    GitHubIssueResult,
    GitHubIssueSearchResponse,
    GitHubModelRepositorySearchResponse,
    GitHubModelSearchRequest,
    GitHubRepositoryResult,
    GitHubRepositorySearchResponse,
    GitHubSearchRequest,
    GitHubTrendingRepositoriesResponse,
    GitHubTrendingRepositoryResult,
    GitHubTrendingRequest,
)
from shared.errors import GitHubSearchError
from shared.logging import get_logger
from shared.settings import get_settings

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-github-search")

GITHUB_API_BASE = "https://api.github.com/search"
GITHUB_TRENDING_BASE = "https://github.com/trending"


def _github_headers() -> dict[str, str]:
    settings = get_settings()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "llmmcp-github-search",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def _github_search_error_message(exc: HTTPError) -> str:
    response = getattr(exc, "response", None)
    if response is None:
        return f"GitHub search request failed: {exc}"

    status_code = getattr(response, "status_code", None)
    text = getattr(response, "text", "") or ""
    lowered = text.lower()
    rate_remaining = response.headers.get("x-ratelimit-remaining")
    if status_code in {403, 429} and (
        rate_remaining == "0" or "rate limit" in lowered or "api rate limit exceeded" in lowered
    ):
        return (
            "GitHub API rate limit exceeded. Configure GITHUB_TOKEN to raise the API quota; "
            "use github_trending_repositories for GitHub Trending because it does not require "
            "the GitHub Search API. Do not switch to browser_fetch unless the user explicitly "
            "asks to inspect a specific GitHub page."
        )
    return f"GitHub search request failed: {exc}"


def _run_github_search(endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    settings = get_settings()
    url = f"{GITHUB_API_BASE}/{endpoint}"

    try:
        with Client(timeout=Timeout(settings.http_timeout), follow_redirects=True) as client:
            response = client.get(url, params=params, headers=_github_headers())
            response.raise_for_status()
    except HTTPError as exc:
        raise GitHubSearchError(_github_search_error_message(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise GitHubSearchError(f"Unexpected GitHub search failure: {exc}") from exc

    try:
        payload = response.json()
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise GitHubSearchError("GitHub search response is missing items")
        return items
    except GitHubSearchError:
        raise
    except Exception as exc:
        raise GitHubSearchError(f"Failed to decode GitHub search response: {exc}") from exc


def _repository_params(request: GitHubSearchRequest) -> dict[str, Any]:
    params: dict[str, Any] = {"q": request.query, "per_page": request.max_results}
    if request.sort != "best-match":
        params["sort"] = request.sort
    return params


def _model_repository_query(request: GitHubModelSearchRequest) -> str:
    query_parts = [
        request.query,
        "model",
        "in:name,description,readme",
    ]
    if request.language:
        query_parts.append(f"language:{request.language}")
    return " ".join(query_parts)


def _model_repository_params(request: GitHubModelSearchRequest) -> dict[str, Any]:
    params: dict[str, Any] = {
        "q": _model_repository_query(request),
        "per_page": request.max_results,
    }
    if request.sort != "best-match":
        params["sort"] = request.sort
    return params


def _normalize_repository_results(items: list[dict[str, Any]]) -> list[GitHubRepositoryResult]:
    return [
        GitHubRepositoryResult(
            name=item.get("name") or "",
            full_name=item.get("full_name") or "",
            url=item["html_url"],
            description=item.get("description"),
            stars=int(item.get("stargazers_count") or 0),
            language=item.get("language"),
        )
        for item in items
        if item.get("html_url")
    ]


def _normalize_code_results(items: list[dict[str, Any]]) -> list[GitHubCodeResult]:
    normalized: list[GitHubCodeResult] = []
    for item in items:
        repository = item.get("repository") or {}
        url = item.get("html_url")
        if not url:
            continue
        normalized.append(
            GitHubCodeResult(
                name=item.get("name") or "",
                path=item.get("path") or "",
                repository=repository.get("full_name") or "",
                url=url,
                sha=item.get("sha") or "",
            )
        )
    return normalized


def _normalize_issue_results(items: list[dict[str, Any]]) -> list[GitHubIssueResult]:
    normalized: list[GitHubIssueResult] = []
    for item in items:
        url = item.get("html_url")
        repository_url = item.get("repository_url") or ""
        if not url:
            continue
        normalized.append(
            GitHubIssueResult(
                title=item.get("title") or "",
                url=url,
                repository=_repository_name_from_api_url(repository_url),
                state=item.get("state") or "",
                number=int(item.get("number") or 0),
            )
        )
    return normalized


def _repository_name_from_api_url(repository_url: str) -> str:
    if not repository_url:
        return ""
    parts = repository_url.rstrip("/").rsplit("/", 2)
    if len(parts) < 2:
        return ""
    return f"{parts[-2]}/{parts[-1]}"


def _parse_compact_int(value: str) -> int | None:
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return None
    token = cleaned.split()[0]
    try:
        return int(token)
    except ValueError:
        return None


def _trending_url(request: GitHubTrendingRequest) -> str:
    language_path = f"/{quote(request.language)}" if request.language else ""
    return f"{GITHUB_TRENDING_BASE}{language_path}?since={request.since}"


def _parse_trending_repositories(
    html: str, request: GitHubTrendingRequest
) -> list[GitHubTrendingRepositoryResult]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[GitHubTrendingRepositoryResult] = []

    for article in soup.select("article.Box-row"):
        repo_link = article.select_one("h2 a[href]")
        if repo_link is None:
            continue

        full_name = repo_link.get("href", "").strip("/")
        if "/" not in full_name:
            continue

        name = full_name.rsplit("/", 1)[-1]
        description_node = article.select_one("p")
        language_node = article.select_one('[itemprop="programmingLanguage"]')
        muted_links = article.select("a.Link--muted")
        stars_period_node = article.select_one("span.float-sm-right")

        total_stars = (
            _parse_compact_int(muted_links[0].get_text(" ", strip=True)) if muted_links else None
        )
        forks = (
            _parse_compact_int(muted_links[1].get_text(" ", strip=True))
            if len(muted_links) > 1
            else None
        )
        stars_period = (
            _parse_compact_int(stars_period_node.get_text(" ", strip=True))
            if stars_period_node
            else None
        )

        results.append(
            GitHubTrendingRepositoryResult(
                rank=len(results) + 1,
                name=name,
                full_name=full_name,
                url=f"https://github.com/{full_name}",
                description=description_node.get_text(" ", strip=True)
                if description_node
                else None,
                language=language_node.get_text(" ", strip=True) if language_node else None,
                total_stars=total_stars,
                forks=forks,
                stars_period=stars_period,
                period=request.since,
            )
        )

        if len(results) >= request.max_results:
            break

    return results


def _fetch_trending_repositories(
    request: GitHubTrendingRequest,
) -> list[GitHubTrendingRepositoryResult]:
    settings = get_settings()
    try:
        with Client(timeout=Timeout(settings.http_timeout), follow_redirects=True) as client:
            response = client.get(
                _trending_url(request),
                headers={"User-Agent": "llmmcp-github-search"},
            )
            response.raise_for_status()
    except HTTPError as exc:
        raise GitHubSearchError(f"GitHub trending request failed: {exc}") from exc
    except Exception as exc:  # pragma: no cover
        raise GitHubSearchError(f"Unexpected GitHub trending failure: {exc}") from exc

    return _parse_trending_repositories(response.text, request)


@mcp.tool()
def github_search_repositories(
    query: str, max_results: int = 5, sort: str = "best-match"
) -> GitHubRepositorySearchResponse:
    """Search GitHub repositories through the GitHub search API.

    Use this tool for GitHub repository discovery. Do not use MCP resources for
    GitHub searches; this server exposes GitHub search as tools.
    """
    request = GitHubSearchRequest(query=query, max_results=max_results, sort=sort)
    items = _run_github_search("repositories", _repository_params(request))
    results = _normalize_repository_results(items)
    logger.debug("github_search_repositories called", extra={"query": request.query})
    return GitHubRepositorySearchResponse(
        message=f"Returned {len(results)} GitHub repositories",
        query=request.query,
        results=results,
        total_results=len(results),
    )


@mcp.tool()
def github_search_model_repositories(
    query: str,
    max_results: int = 10,
    sort: str = "stars",
    language: str | None = None,
) -> GitHubModelRepositorySearchResponse:
    """Search GitHub repositories that are likely related to AI/ML models.

    Use this tool for model-code repository discovery. Do not use MCP resources
    for GitHub searches; this server exposes GitHub search as tools.
    """
    request = GitHubModelSearchRequest(
        query=query,
        max_results=max_results,
        sort=sort,
        language=language,
    )
    resolved_query = _model_repository_query(request)
    items = _run_github_search("repositories", _model_repository_params(request))
    results = _normalize_repository_results(items)
    logger.debug(
        "github_search_model_repositories called",
        extra={"query": request.query, "resolved_query": resolved_query},
    )
    return GitHubModelRepositorySearchResponse(
        message=f"Returned {len(results)} GitHub model repositories",
        query=request.query,
        resolved_query=resolved_query,
        language=request.language,
        results=results,
        total_results=len(results),
    )


@mcp.tool()
def github_search_code(query: str, max_results: int = 5) -> GitHubCodeSearchResponse:
    """Search GitHub code through the GitHub search API.

    Use this tool for code search. Do not use MCP resources for GitHub code;
    this server exposes code search as a tool.
    """
    request = GitHubSearchRequest(query=query, max_results=max_results)
    items = _run_github_search("code", {"q": request.query, "per_page": request.max_results})
    results = _normalize_code_results(items)
    logger.debug("github_search_code called", extra={"query": request.query})
    return GitHubCodeSearchResponse(
        message=f"Returned {len(results)} GitHub code results",
        query=request.query,
        results=results,
        total_results=len(results),
    )


@mcp.tool()
def github_search_issues(
    query: str, max_results: int = 5, sort: str = "best-match"
) -> GitHubIssueSearchResponse:
    """Search GitHub issues and pull requests through the GitHub search API.

    Use this tool for issue discovery. Do not use MCP resources for GitHub
    searches; this server exposes issue search as a tool.
    """
    request = GitHubSearchRequest(query=query, max_results=max_results, sort=sort)
    items = _run_github_search("issues", _repository_params(request))
    results = _normalize_issue_results(items)
    logger.debug("github_search_issues called", extra={"query": request.query})
    return GitHubIssueSearchResponse(
        message=f"Returned {len(results)} GitHub issues",
        query=request.query,
        results=results,
        total_results=len(results),
    )


@mcp.tool()
def github_trending_repositories(
    since: str = "daily", language: str | None = None, max_results: int = 15
) -> GitHubTrendingRepositoriesResponse:
    """Read GitHub trending repositories.

    Use this tool for GitHub trending lookups. Do not use MCP resources for
    trending pages; this server exposes trending lookup as a tool.
    """
    request = GitHubTrendingRequest(since=since, language=language, max_results=max_results)
    results = _fetch_trending_repositories(request)
    logger.debug(
        "github_trending_repositories called",
        extra={"since": request.since, "language": request.language},
    )
    return GitHubTrendingRepositoriesResponse(
        message=f"Returned {len(results)} GitHub trending repositories",
        since=request.since,
        language=request.language,
        results=results,
        total_results=len(results),
    )


if __name__ == "__main__":
    mcp.run()
