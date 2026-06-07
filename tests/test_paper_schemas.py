import pytest
from pydantic import ValidationError

from servers.paper.schemas import PaperCompareRequest, PaperSearchRequest, TrendingPapersRequest


def test_paper_search_request_normalizes_provider() -> None:
    request = PaperSearchRequest.model_validate({"query": " transformers ", "provider": "ArXiV"})

    assert request.query == "transformers"
    assert request.provider == "arxiv"


def test_paper_search_request_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        PaperSearchRequest(query=" ")


def test_paper_compare_request_requires_two_identifiers() -> None:
    with pytest.raises(ValidationError):
        PaperCompareRequest(identifiers=["one"])


def test_trending_papers_request_normalizes_provider_and_sort() -> None:
    request = TrendingPapersRequest.model_validate(
        {"query": " agentic llm ", "provider": "HuggingFace", "sort": "Downloads"}
    )

    assert request.query == "agentic llm"
    assert request.provider == "huggingface"
    assert request.sort == "downloads"


def test_trending_papers_request_resolves_period_alias() -> None:
    request = TrendingPapersRequest.model_validate(
        {"query": "llm", "period": "10d", "days": 30, "sort": "growth"}
    )

    assert request.period == "10d"
    assert request.days == 10
    assert request.sort == "growth"
