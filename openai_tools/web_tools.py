import asyncio
from collections.abc import Callable
from typing import Any

from servers.browser.schemas import BrowserRequest
from servers.browser.server import browser_fetch
from servers.fetch.schemas import FetchRequest
from servers.fetch.server import fetch_url
from servers.search.schemas import SearchRequest
from servers.search.server import search_web

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _tool_parameters(schema_model: type[Any]) -> dict[str, Any]:
    schema = schema_model.model_json_schema()
    return {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
        "additionalProperties": False,
    }


def _run_search(arguments: dict[str, Any]) -> dict[str, Any]:
    request = SearchRequest(**arguments)
    response = asyncio.run(
        search_web(
            query=request.query,
            max_results=request.max_results,
            provider=request.provider,
        )
    )
    return response.model_dump(mode="json")


def _run_fetch(arguments: dict[str, Any]) -> dict[str, Any]:
    request = FetchRequest(**arguments)
    response = asyncio.run(fetch_url(url=str(request.url), timeout=request.timeout))
    return response.model_dump(mode="json")


def _run_browser(arguments: dict[str, Any]) -> dict[str, Any]:
    request = BrowserRequest(**arguments)
    response = asyncio.run(
        browser_fetch(
            url=str(request.url),
            timeout=request.timeout,
            wait_until=request.wait_until,
        )
    )
    return response.model_dump(mode="json")


OPENAI_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the web for candidate sources. "
                "Use provider='brave' to force Brave Search, provider='ddgs' to force DuckDuckGo, "
                "or provider='auto' to use the configured fallback strategy."
            ),
            "parameters": _tool_parameters(SearchRequest),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "Fetch and extract content from a static URL or text endpoint. "
                "Prefer this after search results identify a concrete page."
            ),
            "parameters": _tool_parameters(FetchRequest),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fetch",
            "description": (
                "Load a dynamic web page in a browser, wait for rendering, "
                "and extract page content. "
                "Use this for SPA pages or when static fetching is insufficient."
            ),
            "parameters": _tool_parameters(BrowserRequest),
        },
    },
]


TOOL_HANDLERS: dict[str, ToolHandler] = {
    "search_web": _run_search,
    "fetch_url": _run_fetch,
    "browser_fetch": _run_browser,
}


def execute_openai_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        handler = TOOL_HANDLERS[name]
    except KeyError as exc:
        available = ", ".join(sorted(TOOL_HANDLERS))
        raise ValueError(f"Unknown tool '{name}'. Available tools: {available}") from exc
    return handler(arguments)
