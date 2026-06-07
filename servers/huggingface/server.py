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
from shared.logging import get_logger
from shared.settings import get_settings

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-huggingface")

HUGGINGFACE_MODELS_BASE = "https://huggingface.co/api/models"
HUGGINGFACE_DATASETS_BASE = "https://huggingface.co/api/datasets"
HUGGINGFACE_PAPERS_BASE = "https://huggingface.co/api/papers"


def _http_client() -> Client:
    settings = get_settings()
    return Client(timeout=Timeout(settings.http_timeout), follow_redirects=True)


def _fetch_items(url: str, limit: int) -> list[dict[str, Any]]:
    try:
        with _http_client() as client:
            response = client.get(url, params={"limit": limit})
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


def _resource_items(resource_type: HuggingFaceResourceType) -> list[HuggingFaceResourceResult]:
    if resource_type == "model":
        items = _fetch_items(HUGGINGFACE_MODELS_BASE, 100)
        return [item for raw in items if (item := _normalize_model(raw))]
    if resource_type == "dataset":
        items = _fetch_items(HUGGINGFACE_DATASETS_BASE, 100)
        return [item for raw in items if (item := _normalize_dataset(raw))]
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
        if not _matches_query(request.query, result.title, result.description, tag_text):
            continue
        filtered.append(result)
    return filtered


def query_huggingface_trending_resources(
    request: HuggingFaceTrendingRequest,
) -> HuggingFaceTrendingResponse:
    results = _resource_items(request.resource_type)
    results = _filter_results(request, results)
    results = _sort_results(results, request.sort)[: request.max_results]
    logger.info(
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
