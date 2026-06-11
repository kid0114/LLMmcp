from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from httpx import Client, HTTPError, Timeout
from mcp.server.fastmcp import FastMCP

from servers.huggingface.schemas import (
    HuggingFaceResourceResult,
    HuggingFaceResourceType,
    HuggingFaceSort,
    HuggingFaceTrendingRequest,
    HuggingFaceTrendingResponse,
)
from shared.errors import HuggingFaceError
from shared.http_headers import browser_like_headers
from shared.logging import get_logger
from shared.settings import get_settings

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-huggingface")

@mcp.resource("llmmcp://huggingface/help")
def huggingface_help_resource() -> str:
    """Static help resource for clients that list resources before tools."""
    return (
        "llmmcp-huggingface is primarily a tool-based MCP server.\n\n"
        "Preferred tools:\n"
        "- huggingface_trending_resources\n\n"
        "Use these tools for Hugging Face resource lookups. Do not use resources/read for ordinary "
        "tool tasks unless this server explicitly advertises a matching resource "
        "template. Empty or minimal MCP resources do not mean the tools are "
        "unavailable."
    )


HUGGINGFACE_MODELS_BASE = "https://huggingface.co/api/models"
HUGGINGFACE_DATASETS_BASE = "https://huggingface.co/api/datasets"
HUGGINGFACE_PAPERS_BASE = "https://huggingface.co/api/papers"
HUGGINGFACE_SPACES_BASE = "https://huggingface.co/api/spaces"


def _http_client() -> Client:
    settings = get_settings()
    return Client(
        timeout=Timeout(settings.http_timeout),
        follow_redirects=True,
        headers=browser_like_headers({"Accept": "application/json"}),
    )


def _fetch_items(
    url: str, limit: int, params: dict[str, str | int] | None = None
) -> list[dict[str, Any]]:
    request_params: dict[str, str | int] = {"limit": limit}
    if params:
        request_params.update(params)
    try:
        with _http_client() as client:
            response = client.get(url, params=request_params)
            response.raise_for_status()
    except HTTPError as exc:
        raise HuggingFaceError(f"Hugging Face request failed: {exc}") from exc
    try:
        payload = response.json()
    except Exception as exc:
        raise HuggingFaceError(f"Failed to decode Hugging Face response: {exc}") from exc
    if not isinstance(payload, list):
        raise HuggingFaceError("Hugging Face response must be a JSON list")
    return [item for item in payload if isinstance(item, dict)]


def _date_within_days(value: str | None, days: int) -> bool:
    if not value:
        return True
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    cutoff = datetime.now(UTC) - timedelta(days=days)
    return parsed >= cutoff


def _matches_query(query: str | None, *parts: str | None) -> bool:
    if not query:
        return True
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_+-]+", query) if term.strip()]
    if not terms:
        return True
    haystack = "\n".join(part or "" for part in parts).lower()
    return all(term in haystack for term in terms)


def _score_result(result: HuggingFaceResourceResult) -> float:
    score = 0.0
    for value, weight in (
        (result.trending_score, 10.0),
        (result.likes, 5.0),
        (result.downloads, 1.0),
    ):
        if isinstance(value, int):
            score += float(value) * weight
    return score


def _sort_results(
    results: list[HuggingFaceResourceResult], sort: HuggingFaceSort
) -> list[HuggingFaceResourceResult]:
    def key_downloads(item: HuggingFaceResourceResult) -> int:
        return item.downloads or 0

    def key_likes(item: HuggingFaceResourceResult) -> int:
        return item.likes or 0

    def key_trending(item: HuggingFaceResourceResult) -> float:
        return _score_result(item)

    def key_updated(item: HuggingFaceResourceResult) -> str:
        return item.updated_at or item.created_at or ""

    key_fn: Callable[[HuggingFaceResourceResult], object]
    if sort == "downloads":
        key_fn = key_downloads
    elif sort == "likes":
        key_fn = key_likes
    elif sort in {"recent", "updated", "growth"}:
        key_fn = key_updated
    else:
        key_fn = key_trending
    ranked = sorted(results, key=key_fn, reverse=True)
    for index, result in enumerate(ranked, start=1):
        result.rank = index
    return ranked


def _normalize_model(item: dict[str, Any]) -> HuggingFaceResourceResult | None:
    model_id = item.get("id")
    if not isinstance(model_id, str):
        return None
    tags = item.get("tags")
    return HuggingFaceResourceResult(
        rank=0,
        resource_type="model",
        id=model_id,
        title=model_id,
        description=item.get("description"),
        url=f"https://huggingface.co/{model_id}",
        downloads=item.get("downloads") if isinstance(item.get("downloads"), int) else None,
        likes=item.get("likes") if isinstance(item.get("likes"), int) else None,
        trending_score=item.get("trendingScore")
        if isinstance(item.get("trendingScore"), int)
        else None,
        created_at=item.get("createdAt"),
        updated_at=item.get("lastModified"),
        tags=[tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else [],
    )


def _normalize_dataset(item: dict[str, Any]) -> HuggingFaceResourceResult | None:
    dataset_id = item.get("id")
    if not isinstance(dataset_id, str):
        return None
    tags = item.get("tags")
    return HuggingFaceResourceResult(
        rank=0,
        resource_type="dataset",
        id=dataset_id,
        title=dataset_id,
        description=item.get("description"),
        url=f"https://huggingface.co/datasets/{dataset_id}",
        downloads=item.get("downloads") if isinstance(item.get("downloads"), int) else None,
        likes=item.get("likes") if isinstance(item.get("likes"), int) else None,
        trending_score=item.get("trendingScore")
        if isinstance(item.get("trendingScore"), int)
        else None,
        created_at=item.get("createdAt"),
        updated_at=item.get("lastModified"),
        tags=[tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else [],
    )


def _normalize_paper(item: dict[str, Any]) -> HuggingFaceResourceResult | None:
    paper_id = item.get("id")
    title = item.get("title")
    if not isinstance(paper_id, str) or not isinstance(title, str):
        return None
    authors_raw = item.get("authors")
    authors: list[str] = []
    if isinstance(authors_raw, list):
        for author in authors_raw:
            if not isinstance(author, dict):
                continue
            name = author.get("name")
            if isinstance(name, str):
                authors.append(name)
    return HuggingFaceResourceResult(
        rank=0,
        resource_type="paper",
        id=paper_id,
        title=title,
        authors=authors,
        description=item.get("summary") or item.get("ai_summary"),
        url=f"https://huggingface.co/papers/{paper_id}",
        likes=item.get("upvotes") if isinstance(item.get("upvotes"), int) else None,
        trending_score=item.get("upvotes") if isinstance(item.get("upvotes"), int) else None,
        created_at=item.get("publishedAt"),
        updated_at=item.get("publishedAt"),
        tags=[],
    )


def _normalize_mcp_space(item: dict[str, Any]) -> HuggingFaceResourceResult | None:
    space_id = item.get("id")
    if not isinstance(space_id, str):
        return None
    tags = item.get("tags")
    tag_values = [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []
    sdk = item.get("sdk")
    if isinstance(sdk, str) and sdk:
        tag_values.append(f"sdk:{sdk}")
    return HuggingFaceResourceResult(
        rank=0,
        resource_type="mcp",
        id=space_id,
        title=space_id,
        description=item.get("description"),
        url=f"https://huggingface.co/spaces/{space_id}",
        likes=item.get("likes") if isinstance(item.get("likes"), int) else None,
        trending_score=item.get("trendingScore")
        if isinstance(item.get("trendingScore"), int)
        else None,
        created_at=item.get("createdAt"),
        updated_at=item.get("lastModified") or item.get("createdAt"),
        tags=tag_values,
    )


def _is_mcp_space(result: HuggingFaceResourceResult) -> bool:
    tag_text = " ".join(result.tags)
    mcp_text = "\n".join([result.id, result.title, result.description or "", tag_text]).lower()
    return "mcp" in mcp_text or "model context protocol" in mcp_text


def _resource_items(
    resource_type: HuggingFaceResourceType, query: str | None = None
) -> list[HuggingFaceResourceResult]:
    if resource_type == "model":
        items = _fetch_items(HUGGINGFACE_MODELS_BASE, 100)
        return [item for raw in items if (item := _normalize_model(raw))]
    if resource_type == "dataset":
        items = _fetch_items(HUGGINGFACE_DATASETS_BASE, 100)
        return [item for raw in items if (item := _normalize_dataset(raw))]
    if resource_type == "mcp":
        params = {"search": query} if query else {"filter": "mcp"}
        items = _fetch_items(HUGGINGFACE_SPACES_BASE, 100, params=params)
        return [item for raw in items if (item := _normalize_mcp_space(raw))]
    items = _fetch_items(HUGGINGFACE_PAPERS_BASE, 100)
    return [item for raw in items if (item := _normalize_paper(raw))]


def _filter_results(
    request: HuggingFaceTrendingRequest, results: list[HuggingFaceResourceResult]
) -> list[HuggingFaceResourceResult]:
    filtered: list[HuggingFaceResourceResult] = []
    for result in results:
        if not _date_within_days(result.updated_at or result.created_at, request.days):
            continue
        tag_text = " ".join(result.tags)
        if not _matches_query(
            request.query, result.id, result.title, result.description, result.url, tag_text
        ):
            continue
        if result.resource_type == "mcp" and not _is_mcp_space(result):
            continue
        filtered.append(result)
    return filtered


def query_huggingface_trending_resources(
    request: HuggingFaceTrendingRequest,
) -> HuggingFaceTrendingResponse:
    results = _resource_items(request.resource_type, request.query)
    results = _filter_results(request, results)
    results = _sort_results(results, request.sort)[: request.max_results]
    logger.debug(
        "huggingface_trending_resources called",
        extra={
            "resource_type": request.resource_type,
            "query": request.query,
            "sort": request.sort,
            "days": request.days,
        },
    )
    return HuggingFaceTrendingResponse(
        message=f"Returned {len(results)} Hugging Face resources",
        resource_type=request.resource_type,
        query=request.query,
        sort=request.sort,
        period=request.period,
        days=request.days,
        results=results,
        total_results=len(results),
    )


def query_huggingface_papers(
    query: str | None = None,
    max_results: int = 10,
    sort: HuggingFaceSort = "trending",
    period: str | None = None,
    days: int = 30,
) -> HuggingFaceTrendingResponse:
    request = HuggingFaceTrendingRequest(
        resource_type="paper",
        query=query,
        max_results=max_results,
        sort=sort,
        period=period,
        days=days,
    )
    return query_huggingface_trending_resources(request)


@mcp.tool()
def huggingface_trending_resources(
    resource_type: str,
    query: str | None = None,
    max_results: int = 10,
    sort: str = "trending",
    period: str | None = None,
    days: int = 30,
) -> HuggingFaceTrendingResponse:
    """Query trending Hugging Face resources.

    For resource_type="mcp", results are MCP-enabled Spaces rather than a separate
    MCP plaza. This tool executes one Hugging Face Spaces query.
    Do not use MCP resources for Hugging Face queries; this server exposes
    Hugging Face lookup as a tool.
    """
    request = HuggingFaceTrendingRequest(
        resource_type=cast(HuggingFaceResourceType, resource_type),
        query=query,
        max_results=max_results,
        sort=cast(HuggingFaceSort, sort),
        period=period,
        days=days,
    )
    return query_huggingface_trending_resources(request)


if __name__ == "__main__":
    mcp.run()
