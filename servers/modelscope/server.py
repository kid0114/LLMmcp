from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
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
from shared.http_headers import browser_like_headers
from shared.logging import get_logger
from shared.settings import get_settings

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-modelscope")

@mcp.resource("llmmcp://modelscope/help")
def modelscope_help_resource() -> str:
    """Static help resource for clients that list resources before tools."""
    return (
        "llmmcp-modelscope is primarily a tool-based MCP server.\n\n"
        "Preferred tools:\n"
        "- modelscope_trending_resources\n\n"
        "Use these tools for ModelScope resource lookups. Do not use resources/read for ordinary "
        "tool tasks unless this server explicitly advertises a matching resource "
        "template. Empty or minimal MCP resources do not mean the tools are "
        "unavailable."
    )


MODELSCOPE_SKILLS_BASE = "https://modelscope.cn/openapi/v1/skills"
MODELSCOPE_DATASETS_BASE = "https://modelscope.cn/openapi/v1/datasets"
MODELSCOPE_MODELS_BASE = "https://modelscope.cn/openapi/v1/models"
MODELSCOPE_PAPERS_BASE = "https://modelscope.cn/api/v1/papers"
MODELSCOPE_MCP_SERVERS_BASE = "https://modelscope.cn/api/v1/dolphin/mcpServers"


def _http_client() -> Client:
    settings = get_settings()
    return Client(
        timeout=Timeout(settings.http_timeout),
        follow_redirects=True,
        headers=browser_like_headers(),
    )


def _require_json(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise ModelScopeError(f"Failed to decode ModelScope response: {exc}") from exc
    if not isinstance(payload, dict):
        raise ModelScopeError("ModelScope response must be a JSON object")
    return payload


def _is_waf_challenge(text: str) -> bool:
    return "aliyun_waf_aa" in text or "acw_sc__v2" in text


def _solve_aliyun_waf_cookie(html: str) -> str | None:
    if shutil.which("node") is None:
        return None
    render_match = re.search(
        r'<textarea id="renderData"[^>]*>(.*?)</textarea>', html, flags=re.S
    )
    if render_match is None:
        return None
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.S)
    if not scripts:
        return None
    node_code = """
const vm = require('vm');
let cookieValue = '';
const challenge = CHALLENGE_JSON;
const renderData = RENDER_JSON;
const sandbox = {
  console: { log() {}, error() {} },
  navigator: {
    userAgent: 'Mozilla/5.0',
    webdriver: false,
    platform: 'MacIntel',
    language: 'zh-CN'
  },
  location: {
    href: 'https://modelscope.cn/api/v1/dolphin/mcpServers',
    reload() {}
  },
  document: {
    referrer: 'https://modelscope.cn/mcp',
    getElementById() { return { innerHTML: renderData }; }
  },
  setTimeout(fn) { if (typeof fn === 'function') fn(); },
  clearTimeout() {}
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
Object.defineProperty(sandbox.document, 'cookie', {
  get() { return cookieValue; },
  set(v) { cookieValue = cookieValue ? `${cookieValue}; ${v}` : v; }
});
Object.defineProperty(sandbox.document, 'location', {
  get() { return sandbox.location; },
  set(v) { sandbox.location.href = v; }
});
vm.createContext(sandbox);
try {
  vm.runInContext(challenge, sandbox, { timeout: 5000 });
  console.log(cookieValue);
} catch (_) {
  process.exit(2);
}
""".replace("CHALLENGE_JSON", json.dumps("\n".join(scripts))).replace(
        "RENDER_JSON", json.dumps(render_match.group(1))
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
        handle.write(node_code)
        script_path = handle.name
    try:
        completed = subprocess.run(
            ["node", script_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
    if completed.returncode != 0:
        return None
    match = re.search(r"\bacw_sc__v2=([^;\s]+)", completed.stdout)
    if match is None:
        return None
    return f"acw_sc__v2={match.group(1)}"


def _cookie_header_from_client(client: Client, extra_cookie: str) -> str:
    values: dict[str, str] = {}
    for cookie in client.cookies.jar:
        if cookie.domain.endswith("modelscope.cn"):
            values[cookie.name] = cookie.value
    name, value = extra_cookie.split("=", 1)
    values[name] = value
    return "; ".join(f"{name}={value}" for name, value in values.items())


def _cookie_value(cookie_header: str | None, name: str) -> str | None:
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name and value:
            return value
    return None


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


def _normalize_mcp(item: dict[str, Any]) -> ModelScopeResourceResult | None:
    name = item.get("Name")
    path = item.get("Path") or item.get("FromSitePath")
    if not isinstance(name, str) or not name:
        return None
    resource_id = f"{path}/{name}" if isinstance(path, str) and path else name
    title = item.get("ChineseName") or name
    tags = item.get("Tags")
    category = item.get("Category")
    tag_values = [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []
    if isinstance(category, str) and category:
        tag_values.append(category)
    return ModelScopeResourceResult(
        rank=0,
        resource_type="mcp",
        id=resource_id,
        title=title if isinstance(title, str) else name,
        description=item.get("Description") or item.get("Summary") or item.get("Abstract"),
        url=f"https://modelscope.cn/mcp/servers/{resource_id}",
        downloads=item.get("CallVolume") if isinstance(item.get("CallVolume"), int) else None,
        likes=item.get("Stars") if isinstance(item.get("Stars"), int) else None,
        view_count=item.get("ViewCount") if isinstance(item.get("ViewCount"), int) else None,
        favorite_count=item.get("Stars") if isinstance(item.get("Stars"), int) else None,
        created_at=item.get("CreatedAt") or item.get("CreateTime"),
        updated_at=item.get("UpdatedAt") or item.get("UpdateTime") or item.get("GmtModified"),
        tags=tag_values,
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


def _fetch_mcp_items(query: str | None = None) -> list[dict[str, Any]]:
    payload = {"PageSize": 100, "PageNumber": 1, "Query": query or "", "Criterion": []}
    cookie = os.getenv("MODELSCOPE_MCP_COOKIE")
    csrf_token = os.getenv("MODELSCOPE_MCP_CSRF_TOKEN") or _cookie_value(cookie, "csrf_token")
    headers = browser_like_headers(
        {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": os.getenv(
                "MODELSCOPE_MCP_ACCEPT_LANGUAGE",
                "en-GB,en-US;q=0.9,en;q=0.8",
            ),
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "Referer": "https://modelscope.cn/mcp",
            "Origin": "https://modelscope.cn",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": os.getenv(
                "MODELSCOPE_MCP_USER_AGENT",
                (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/148.0.0.0 Safari/537.36"
                ),
            ),
            "sec-ch-ua": os.getenv(
                "MODELSCOPE_MCP_SEC_CH_UA",
                '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            ),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "x-modelscope-accept-language": os.getenv("MODELSCOPE_ACCEPT_LANGUAGE", "zh_CN"),
            "X-Modelscope-Trace-Id": str(uuid.uuid4()),
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    if csrf_token:
        headers["X-CSRF-TOKEN"] = csrf_token
    if cookie:
        headers["Cookie"] = cookie
    try:
        with _http_client() as client:
            response = client.put(MODELSCOPE_MCP_SERVERS_BASE, json=payload, headers=headers)
            response.raise_for_status()
            if _is_waf_challenge(response.text) and not cookie:
                solved_cookie = _solve_aliyun_waf_cookie(response.text)
                if solved_cookie:
                    headers["Cookie"] = _cookie_header_from_client(client, solved_cookie)
                    response = client.put(
                        MODELSCOPE_MCP_SERVERS_BASE,
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code == 404:
                        raise ModelScopeError(
                            "ModelScope MCP Plaza WAF automatic cookie solving failed; "
                            "set MODELSCOPE_MCP_COOKIE from a browser session"
                        )
                    response.raise_for_status()
    except HTTPError as exc:
        raise ModelScopeError(f"ModelScope MCP Plaza request failed: {exc}") from exc
    if _is_waf_challenge(response.text):
        raise ModelScopeError(
            "ModelScope MCP Plaza request was blocked by Aliyun WAF; "
            "automatic cookie solving failed; set MODELSCOPE_MCP_COOKIE from a browser session "
            "if direct access is required"
        )
    payload_json = _require_json(response)
    data = payload_json.get("Data") or payload_json.get("data") or {}
    mcp_server = data.get("McpServer") or data.get("mcpServer") or {}
    items = mcp_server.get("McpServers") or mcp_server.get("mcpServers") or []
    return [item for item in items if isinstance(item, dict)]


def _resource_items(
    resource_type: ModelScopeResourceType, query: str | None = None
) -> list[ModelScopeResourceResult]:
    if resource_type == "skill":
        items = _fetch_openapi_items(MODELSCOPE_SKILLS_BASE, "skills")
        return [item for raw in items if (item := _normalize_skill(raw))]
    if resource_type == "dataset":
        items = _fetch_openapi_items(MODELSCOPE_DATASETS_BASE, "datasets")
        return [item for raw in items if (item := _normalize_dataset(raw))]
    if resource_type == "model":
        items = _fetch_openapi_items(MODELSCOPE_MODELS_BASE, "models")
        return [item for raw in items if (item := _normalize_model(raw))]
    if resource_type == "mcp":
        items = _fetch_mcp_items(query)
        return [item for raw in items if (item := _normalize_mcp(raw))]
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
        if not _matches_query(
            request.query, result.id, result.title, result.description, result.url, tag_text
        ):
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
    """Query trending ModelScope resources.

    For resource_type="mcp", this tool executes one ModelScope MCP Plaza query.
    Concrete MCP names or package ids such as @modelcontextprotocol/fetch or
    leetcode-mcp-server can be searched directly.
    Do not use MCP resources for ModelScope queries; this server exposes
    ModelScope lookup as a tool.
    """
    request = ModelScopeTrendingRequest(
        resource_type=cast(ModelScopeResourceType, resource_type),
        query=query,
        max_results=max_results,
        sort=cast(ModelScopeSort, sort),
        period=period,
        days=days,
    )
    results = _resource_items(request.resource_type, request.query)
    results = _filter_results(request, results)
    results = _sort_results(results, request.sort)[: request.max_results]
    logger.debug(
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
