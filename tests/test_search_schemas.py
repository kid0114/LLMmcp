import pytest
from pydantic import ValidationError

from servers.search.schemas import SearchRequest


def test_search_request_defaults() -> None:
    request = SearchRequest(query="mcp")
    assert request.query == "mcp"
    assert request.max_results == 5
    assert request.provider == "auto"


def test_search_request_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="   ")


def test_search_request_normalizes_provider() -> None:
    request = SearchRequest(query="mcp", provider="BrAvE")
    assert request.provider == "brave"


def test_search_request_rejects_invalid_provider() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="mcp", provider="google")
