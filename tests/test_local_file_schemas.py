import pytest
from pydantic import ValidationError

from servers.local_file.schemas import LocalFileRequest, LocalGlobRequest, LocalSearchRequest


def test_local_file_request_defaults() -> None:
    request = LocalFileRequest(path="README.md")
    assert request.path == "README.md"
    assert request.offset == 0
    assert request.max_chars == 20000


def test_local_file_request_rejects_blank_path() -> None:
    with pytest.raises(ValidationError):
        LocalFileRequest(path="   ")


def test_local_file_request_rejects_negative_offset() -> None:
    with pytest.raises(ValidationError):
        LocalFileRequest(path="README.md", offset=-1)


def test_local_glob_request_rejects_blank_pattern() -> None:
    with pytest.raises(ValidationError):
        LocalGlobRequest(path=".", pattern=" ")


def test_local_search_request_defaults() -> None:
    request = LocalSearchRequest(path=".", query="phase")
    assert request.include_glob is None
    assert request.max_results == 50
    assert request.max_file_chars == 200000
