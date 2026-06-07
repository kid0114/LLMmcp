import pytest
from pydantic import ValidationError

from servers.browser.schemas import BrowserRequest


def test_browser_request_defaults() -> None:
    request = BrowserRequest(url="https://example.com")
    assert str(request.url) == "https://example.com/"
    assert request.timeout == 30
    assert request.wait_until == "networkidle"


def test_browser_request_rejects_invalid_wait_until() -> None:
    with pytest.raises(ValidationError):
        BrowserRequest(url="https://example.com", wait_until="idle")
