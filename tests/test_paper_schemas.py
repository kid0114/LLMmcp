import pytest
from pydantic import ValidationError

from servers.paper.schemas import PaperCompareRequest, PaperSearchRequest


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
