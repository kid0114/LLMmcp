import pytest
from pydantic import ValidationError

from servers.github_search.schemas import (
    GitHubModelSearchRequest,
    GitHubSearchRequest,
    GitHubTrendingRequest,
)


def test_github_search_request_defaults() -> None:
    request = GitHubSearchRequest(query="fastmcp")
    assert request.query == "fastmcp"
    assert request.max_results == 5
    assert request.sort == "best-match"


def test_github_search_request_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        GitHubSearchRequest(query=" ")


def test_github_trending_request_defaults() -> None:
    request = GitHubTrendingRequest()
    assert request.since == "daily"
    assert request.language is None
    assert request.max_results == 15


def test_github_trending_request_normalizes_language() -> None:
    request = GitHubTrendingRequest(language=" /python/ ")
    assert request.language == "python"


def test_github_model_search_request_defaults() -> None:
    request = GitHubModelSearchRequest(query="qwen")
    assert request.query == "qwen"
    assert request.max_results == 10
    assert request.sort == "stars"
    assert request.language is None


def test_github_model_search_request_normalizes_language() -> None:
    request = GitHubModelSearchRequest(query="embedding", language=" Python ")
    assert request.language == "Python"


def test_github_model_search_request_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        GitHubModelSearchRequest(query=" ")
