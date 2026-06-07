import pytest
from pydantic import ValidationError

from servers.fetch.schemas import FetchRequest


def test_fetch_request_defaults() -> None:
    request = FetchRequest(url="https://example.com")
    assert str(request.url) == "https://example.com/"
    assert request.timeout == 20


def test_fetch_request_rejects_bad_url() -> None:
    with pytest.raises(ValidationError):
        FetchRequest(url="not-a-url")
