from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from servers.file_reader.server import inspect_image_file, ocr_image_file, read_pdf_file
from shared.errors import FileReaderError
from shared.settings import get_settings


def _set_local_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setenv("LOCAL_FILE_ROOT", str(root))
    get_settings.cache_clear()


def test_inspect_image_file_returns_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_local_root(monkeypatch, tmp_path)
    path = tmp_path / "sample.png"
    Image.new("RGBA", (16, 8), color=(255, 0, 0, 255)).save(path)

    response = inspect_image_file("sample.png")

    assert response.format == "PNG"
    assert response.mode == "RGBA"
    assert response.width == 16
    assert response.height == 8
    assert response.has_alpha is True


def test_read_pdf_file_uses_pypdf_reader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_local_root(monkeypatch, tmp_path)
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-1.4\n")

    class FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class FakeReader:
        def __init__(self, _: str) -> None:
            self.pages = [FakePage("Page 1"), FakePage("Page 2")]

    monkeypatch.setattr("servers.file_reader.server._load_pypdf", lambda: FakeReader)

    response = read_pdf_file("sample.pdf", max_chars=100, max_pages=1)

    assert response.page_count == 2
    assert response.pages_read == 1
    assert response.content == "Page 1"
    assert response.truncated is True


def test_ocr_image_file_requires_tesseract_when_rapidocr_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_local_root(monkeypatch, tmp_path)
    path = tmp_path / "sample.png"
    Image.new("RGB", (8, 8), color=(255, 255, 255)).save(path)

    monkeypatch.setattr(
        "servers.file_reader.server._ocr_with_rapidocr",
        lambda target: (_ for _ in ()).throw(FileReaderError("RapidOCR failed")),
    )
    monkeypatch.setattr(
        "servers.file_reader.server._load_pytesseract",
        lambda: SimpleNamespace(image_to_string=lambda image, lang: "hello"),
    )
    monkeypatch.setattr("servers.file_reader.server.which", lambda name: None)

    with pytest.raises(FileReaderError, match="tesseract binary is required"):
        ocr_image_file("sample.png")


def test_ocr_image_file_uses_rapidocr_when_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_local_root(monkeypatch, tmp_path)
    path = tmp_path / "sample.png"
    Image.new("RGB", (8, 8), color=(255, 255, 255)).save(path)

    monkeypatch.setattr(
        "servers.file_reader.server._ocr_with_rapidocr",
        lambda target: "hello world",
    )

    response = ocr_image_file("sample.png", max_chars=5)

    assert response.language == "eng"
    assert response.content == "hello"
    assert response.truncated is True
    assert "rapidocr" in (response.message or "")


def test_ocr_image_file_falls_back_to_pytesseract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_local_root(monkeypatch, tmp_path)
    path = tmp_path / "sample.png"
    Image.new("RGB", (8, 8), color=(255, 255, 255)).save(path)

    monkeypatch.setattr(
        "servers.file_reader.server._ocr_with_rapidocr",
        lambda target: (_ for _ in ()).throw(FileReaderError("RapidOCR failed")),
    )
    monkeypatch.setattr(
        "servers.file_reader.server._load_pytesseract",
        lambda: SimpleNamespace(image_to_string=lambda image, lang: "hello world"),
    )
    monkeypatch.setattr("servers.file_reader.server.which", lambda name: "/usr/bin/tesseract")

    response = ocr_image_file("sample.png", max_chars=5)

    assert response.language == "eng"
    assert response.content == "hello"
    assert response.truncated is True
    assert "tesseract" in (response.message or "")
