import pytest
from pydantic import ValidationError

from servers.huggingface.schemas import HuggingFaceTrendingRequest


def test_huggingface_trending_request_defaults() -> None:
    request = HuggingFaceTrendingRequest(resource_type="paper")
    assert request.resource_type == "paper"
    assert request.max_results == 10
    assert request.sort == "trending"
    assert request.days == 30


def test_huggingface_trending_request_resolves_period() -> None:
    request = HuggingFaceTrendingRequest(resource_type="model", period="week")
    assert request.period == "week"
    assert request.days == 7


def test_huggingface_trending_request_rejects_bad_period() -> None:
    with pytest.raises(ValidationError):
        HuggingFaceTrendingRequest(resource_type="dataset", period="soonish")
