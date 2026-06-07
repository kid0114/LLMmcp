import pytest
from pydantic import ValidationError

from servers.file_reader.schemas import ImageOcrRequest, PdfReadRequest


def test_pdf_read_request_defaults() -> None:
    request = PdfReadRequest(path="docs/file.pdf")
    assert request.max_chars == 20000
    assert request.max_pages == 20


def test_pdf_read_request_rejects_blank_path() -> None:
    with pytest.raises(ValidationError):
        PdfReadRequest(path=" ")


def test_image_ocr_request_defaults() -> None:
    request = ImageOcrRequest(path="images/test.png")
    assert request.language == "eng"
    assert request.max_chars == 20000


def test_image_ocr_request_rejects_blank_language() -> None:
    with pytest.raises(ValidationError):
        ImageOcrRequest(path="images/test.png", language=" ")
