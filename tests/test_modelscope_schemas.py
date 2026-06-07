import pytest
from pydantic import ValidationError

from servers.modelscope.schemas import ModelScopeTrendingRequest


def test_modelscope_trending_request_defaults() -> None:
    request = ModelScopeTrendingRequest(resource_type="skill")
    assert request.resource_type == "skill"
    assert request.max_results == 10
    assert request.sort == "trending"
    assert request.days == 30


def test_modelscope_trending_request_resolves_period() -> None:
    request = ModelScopeTrendingRequest(resource_type="paper", period="14d")
    assert request.days == 14
    assert request.period == "14d"


def test_modelscope_trending_request_rejects_bad_period() -> None:
    with pytest.raises(ValidationError):
        ModelScopeTrendingRequest(resource_type="dataset", period="yesterdayish")
