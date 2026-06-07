from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from httpx import Client, HTTPError, Timeout
from mcp.server.fastmcp import FastMCP

from servers.modelscope.schemas import (
    ModelScopeResourceResult,
    ModelScopeResourceType,
    ModelScopeSort,
    ModelScopeTrendingRequest,
    ModelScopeTrendingResponse,
)
from shared.errors import ModelScopeError
from shared.logging import get_logger
from shared.settings import get_settings

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-modelscope")

MODELSCOPE_SKILLS_BASE = "https://modelscope.cn/openapi/v1/skills"
MODELSCOPE_DATASETS_BASE = "https://modelscope.cn/openapi/v1/datasets"
MODELSCOPE_MODELS_BASE = "https://modelscope.cn/openapi/v1/models"
MODELSCOPE_PAPERS_BASE = "https://modelscope.cn/api/v1/papers"


def _http_client() -> Client:
    settings = get_settings()
    return Client(timeout=Timeout(settings.http_timeout), follow_redirects=True)


def _require_json(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise ModelScopeError(f"Failed to decode ModelScope response: {exc}") from exc
    if not isinstance(payload, dict):
        raise ModelScopeError("ModelScope response must be a JSON object")
    return payload


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


def _score_result(result: ModelScopeResourceResult) -> float:
    score = 0.0
    for value, weight in (
        (result.impact_score, 10.0),
        (result.favorite_count or result.likes, 5.0),
        (result.view_count or result.downloads, 1.0),
    ):
        if isinstance(value, int):
            score += float(value) * weight
    return score


def _sort_results(
    results: list[ModelScopeResourceResult], sort: ModelScopeSort
) -> list[ModelScopeResourceResult]:
    def key_downloads(item: ModelScopeResourceResult) -> int:
        return item.downloads or 0

    def key_likes(item: ModelScopeResourceResult) -> int:
        return item.likes or 0

    def key_views(item: ModelScopeResourceResult) -> int:
        return item.view_count or 0

    def key_favorites(item: ModelScopeResourceResult) -> int:
        return item.favorite_count or 0

    def key_impact(item: ModelScopeResourceResult) -> int:
        return item.impact_score or 0

    def key_updated(item: ModelScopeResourceResult) -> str:
        return item.updated_at or item.created_at or ""

    key_fn: Callable[[ModelScopeResourceResult], object]
    if sort == "downloads":
        key_fn = key_downloads
    elif sort == "likes":
        key_fn = key_likes
    elif sort == "views":
        key_fn = key_views
    elif sort == "favorites":
        key_fn = key_favorites
    elif sort == "impact":
        key_fn = key_impact
    elif sort in {"recent", "updated", "growth"}:
        key_fn = key_updated
    else:
        key_fn = _score_result
    ranked = sorted(results, key=key_fn, reverse=True)
    for index, result in enumerate(ranked, start=1):
        result.rank = index
    return ranked


def _normalize_skill(item: dict[str, Any]) -> ModelScopeResourceResult | None:
    skill_id = item.get("id")
    title = item.get("display_name")
    if not isinstance(skill_id, str) or not isinstance(title, str):
        return None
    tags = item.get("tags")
    return ModelScopeResourceResult(
        rank=0,
        resource_type="skill",
        id=skill_id,
        title=title,
        description=item.get("description"),
        url=item.get("source_url") or f"https://modelscope.cn/skills/{skill_id}",
        downloads=item.get("downloads") if isinstance(item.get("downloads"), int) else None,
        view_count=item.get("view_count") if isinstance(item.get("view_count"), int) else None,
        created_at=item.get("created_at"),
        updated_at=item.get("last_modified"),
        tags=[tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else [],
    )


def _normalize_dataset(item: dict[str, Any]) -> ModelScopeResourceResult | None:
    dataset_id = item.get("id")
    title = item.get("display_name")
    if not isinstance(dataset_id, str) or not isinstance(title, str):
        return None
    tags = item.get("tags")
    return ModelScopeResourceResult(
        rank=0,
        resource_type="dataset",
        id=dataset_id,
        title=title,
        description=item.get("description"),
        url=f"https://modelscope.cn/datasets/{dataset_id}",
        downloads=item.get("downloads") if isinstance(item.get("downloads"), int) else None,
        likes=item.get("likes") if isinstance(item.get("likes"), int) else None,
        created_at=item.get("created_at"),
        updated_at=item.get("last_modified"),
        tags=[tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else [],
    )


def _normalize_model(item: dict[str, Any]) -> ModelScopeResourceResult | None:
    model_id = item.get("id")
    title = item.get("display_name")
    if not isinstance(model_id, str) or not isinstance(title, str):
        return None
    tags = item.get("tags")
    return ModelScopeResourceResult(
        rank=0,
        resource_type="model",
        id=model_id,
        title=title,
        description=item.get("description"),
        url=f"https://modelscope.cn/models/{model_id}",
        downloads=item.get("downloads") if isinstance(item.get("downloads"), int) else None,
        likes=item.get("likes") if isinstance(item.get("likes"), int) else None,
        created_at=item.get("created_at"),
        updated_at=item.get("last_modified"),
        tags=[tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else [],
    )


def _normalize_paper(item: dict[str, Any]) -> ModelScopeResourceResult | None:
    paper_id = item.get("Id")
    title = item.get("Title")
    if paper_id is None or not isinstance(title, str):
        return None
    authors_raw = item.get("Authors")
    authors: list[str] = []
    if isinstance(authors_raw, str):
        authors = [part.strip() for part in re.split(r"[,;，]", authors_raw) if part.strip()]
    return ModelScopeResourceResult(
        rank=0,
        resource_type="paper",
        id=str(paper_id),
        title=title,
        authors=authors,
        description=item.get("AbstractEn") or item.get("AbstractCn"),
        url=item.get("ArxivUrl") or item.get("PdfUrl") or f"https://modelscope.cn/papers/{paper_id}",
        view_count=item.get("ViewCount") if isinstance(item.get("ViewCount"), int) else None,
        favorite_count=item.get("FavoriteCount")
        if isinstance(item.get("FavoriteCount"), int)
        else None,
        impact_score=item.get("ImpactScore") if isinstance(item.get("ImpactScore"), int) else None,
        created_at=item.get("PublishDate"),
        updated_at=item.get("PublishDate"),
        tags=[],
    )


def _fetch_openapi_items(url: str, top_key: str) -> list[dict[str, Any]]:
    try:
        with _http_client() as client:
            response = client.get(url)
            response.raise_for_status()
    except HTTPError as exc:
        raise ModelScopeError(f"ModelScope request failed: {exc}") from exc
    payload = _require_json(response)
    data = payload.get("data") or {}
    items = data.get(top_key) or []
    return [item for item in items if isinstance(item, dict)]


def _fetch_paper_items() -> list[dict[str, Any]]:
    try:
        with _http_client() as client:
            response = client.get(MODELSCOPE_PAPERS_BASE, params={"PageNumber": 1, "PageSize": 100})
            response.raise_for_status()
    except HTTPError as exc:
        raise ModelScopeError(f"ModelScope paper request failed: {exc}") from exc
    payload = _require_json(response)
    data = payload.get("Data") or payload.get("data") or {}
    items = data.get("Papers") or data.get("papers") or []
    return [item for item in items if isinstance(item, dict)]


def _resource_items(resource_type: ModelScopeResourceType) -> list[ModelScopeResourceResult]:
    if resource_type == "skill":
        items = _fetch_openapi_items(MODELSCOPE_SKILLS_BASE, "skills")
        return [item for raw in items if (item := _normalize_skill(raw))]
    if resource_type == "dataset":
        items = _fetch_openapi_items(MODELSCOPE_DATASETS_BASE, "datasets")
        return [item for raw in items if (item := _normalize_dataset(raw))]
    if resource_type == "model":
        items = _fetch_openapi_items(MODELSCOPE_MODELS_BASE, "models")
        return [item for raw in items if (item := _normalize_model(raw))]
    items = _fetch_paper_items()
    return [item for raw in items if (item := _normalize_paper(raw))]


def _filter_results(
    request: ModelScopeTrendingRequest, results: list[ModelScopeResourceResult]
) -> list[ModelScopeResourceResult]:
    filtered: list[ModelScopeResourceResult] = []
    for result in results:
        if not _date_within_days(result.updated_at or result.created_at, request.days):
            continue
        tag_text = " ".join(result.tags)
        if not _matches_query(request.query, result.title, result.description, tag_text):
            continue
        filtered.append(result)
    return filtered


@mcp.tool()
def modelscope_trending_resources(
    resource_type: str,
    query: str | None = None,
    max_results: int = 10,
    sort: str = "trending",
    period: str | None = None,
    days: int = 30,
) -> ModelScopeTrendingResponse:
    request = ModelScopeTrendingRequest(
        resource_type=cast(ModelScopeResourceType, resource_type),
        query=query,
        max_results=max_results,
        sort=cast(ModelScopeSort, sort),
        period=period,
        days=days,
    )
    results = _resource_items(request.resource_type)
    results = _filter_results(request, results)
    results = _sort_results(results, request.sort)[: request.max_results]
    logger.info(
        "modelscope_trending_resources called",
        extra={
            "resource_type": request.resource_type,
            "query": request.query,
            "sort": request.sort,
            "days": request.days,
        },
    )
    return ModelScopeTrendingResponse(
        message=f"Returned {len(results)} ModelScope resources",
        resource_type=request.resource_type,
        query=request.query,
        sort=request.sort,
        period=request.period,
        days=request.days,
        results=results,
        total_results=len(results),
    )


if __name__ == "__main__":
    mcp.run()
