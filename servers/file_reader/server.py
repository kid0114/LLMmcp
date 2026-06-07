from __future__ import annotations

from pathlib import Path
from shutil import which
from typing import Any

from mcp.server.fastmcp import FastMCP
from PIL import Image, UnidentifiedImageError

from servers.file_reader.schemas import (
    ImageMetadataRequest,
    ImageMetadataResponse,
    ImageOcrRequest,
    ImageOcrResponse,
    PdfReadRequest,
    PdfReadResponse,
)
from shared.errors import FileReaderError, PermissionDeniedError
from shared.logging import get_logger
from shared.permissions import validate_local_path
from shared.settings import get_settings

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-file-reader")


def _resolve_local_root() -> Path:
    settings = get_settings()
    if settings.local_file_root:
        return Path(settings.local_file_root).resolve()
    return Path.cwd().resolve()


def _resolve_safe_path(path: str, root: Path) -> Path:
    try:
        return validate_local_path(path, root)
    except PermissionDeniedError:
        raise
    except Exception as exc:
        raise FileReaderError(f"Invalid file reader request: {exc}") from exc


def _require_file(path: Path) -> None:
    if not path.exists():
        raise FileReaderError(f"File does not exist: {path}")
    if not path.is_file():
        raise FileReaderError(f"Path is not a file: {path}")


def _load_pypdf() -> Any:
    try:
        from importlib import import_module
        return import_module("pypdf").PdfReader
    except ImportError as exc:
        raise FileReaderError("pypdf is required to read PDF files") from exc


def _load_pytesseract() -> Any:
    try:
        from importlib import import_module
        return import_module("pytesseract")
    except ImportError as exc:
        raise FileReaderError("pytesseract is required to OCR image files") from exc


def _load_rapidocr() -> Any:
    try:
        from importlib import import_module
        return import_module("rapidocr_onnxruntime").RapidOCR
    except ImportError as exc:
        raise FileReaderError("rapidocr-onnxruntime is required to OCR image files") from exc


def _ensure_tesseract_available() -> None:
    if which("tesseract") is None:
        raise FileReaderError("tesseract binary is required to OCR image files")


def _safe_exif(image: Image.Image) -> dict[str, str] | None:
    exif = image.getexif()
    if not exif:
        return None
    extracted: dict[str, str] = {}
    for key, value in exif.items():
        extracted[str(key)] = str(value)
    return extracted or None


def _ocr_with_rapidocr(target: Path) -> str:
    rapidocr = _load_rapidocr()
    try:
        engine = rapidocr()
        raw_result: Any = engine(str(target))
    except Exception as exc:
        raise FileReaderError(f"RapidOCR failed: {exc}") from exc

    if not isinstance(raw_result, tuple) or not raw_result:
        return ""

    candidates = raw_result[0]
    if not isinstance(candidates, list):
        return ""

    parts: list[str] = []
    for item in candidates:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        text = item[1]
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts)


def _ocr_with_tesseract(target: Path, language: str) -> str:
    pytesseract = _load_pytesseract()
    _ensure_tesseract_available()
    try:
        with Image.open(target) as image:
            return str(pytesseract.image_to_string(image, lang=language))
    except UnidentifiedImageError as exc:
        raise FileReaderError(f"Unsupported image file: {exc}") from exc
    except Exception as exc:
        raise FileReaderError(f"Tesseract OCR failed: {exc}") from exc


@mcp.tool()
def read_pdf_file(path: str, max_chars: int = 20000, max_pages: int = 20) -> PdfReadResponse:
    request = PdfReadRequest(path=path, max_chars=max_chars, max_pages=max_pages)
    root = _resolve_local_root()
    target = _resolve_safe_path(request.path, root)
    _require_file(target)

    pdf_reader = _load_pypdf()
    try:
        reader = pdf_reader(str(target))
    except Exception as exc:
        raise FileReaderError(f"Failed to open PDF file: {exc}") from exc

    page_count = len(reader.pages)
    parts: list[str] = []
    pages_read = 0
    for page in reader.pages[: request.max_pages]:
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise FileReaderError(f"Failed to extract PDF text: {exc}") from exc
        parts.append(text.strip())
        pages_read += 1

    content = "\n\n".join(part for part in parts if part)
    truncated = len(content) > request.max_chars or page_count > request.max_pages
    if len(content) > request.max_chars:
        content = content[: request.max_chars]

    logger.info("read_pdf_file called", extra={"path": request.path, "pages_read": pages_read})
    return PdfReadResponse(
        message="Read PDF file successfully",
        path=request.path,
        absolute_path=str(target),
        page_count=page_count,
        pages_read=pages_read,
        content=content,
        content_length=len(content),
        truncated=truncated,
    )


@mcp.tool()
def inspect_image_file(path: str) -> ImageMetadataResponse:
    request = ImageMetadataRequest(path=path)
    root = _resolve_local_root()
    target = _resolve_safe_path(request.path, root)
    _require_file(target)

    try:
        with Image.open(target) as image:
            width, height = image.size
            mode = image.mode
            image_format = image.format
            has_alpha = "A" in mode
            exif = _safe_exif(image)
    except UnidentifiedImageError as exc:
        raise FileReaderError(f"Unsupported image file: {exc}") from exc
    except Exception as exc:
        raise FileReaderError(f"Failed to inspect image file: {exc}") from exc

    logger.info("inspect_image_file called", extra={"path": request.path})
    return ImageMetadataResponse(
        message="Inspected image file successfully",
        path=request.path,
        absolute_path=str(target),
        format=image_format,
        mode=mode,
        width=width,
        height=height,
        has_alpha=has_alpha,
        exif=exif,
    )


@mcp.tool()
def ocr_image_file(path: str, language: str = "eng", max_chars: int = 20000) -> ImageOcrResponse:
    request = ImageOcrRequest(path=path, language=language, max_chars=max_chars)
    root = _resolve_local_root()
    target = _resolve_safe_path(request.path, root)
    _require_file(target)

    try:
        content = _ocr_with_rapidocr(target)
        backend = "rapidocr"
    except Exception as exc:
        logger.warning("rapidocr failed, falling back to tesseract", extra={"error": str(exc)})
        content = _ocr_with_tesseract(target, request.language)
        backend = "tesseract"

    content = content.strip()
    truncated = len(content) > request.max_chars
    if truncated:
        content = content[: request.max_chars]

    logger.info(
        "ocr_image_file called",
        extra={"path": request.path, "language": request.language, "backend": backend},
    )
    return ImageOcrResponse(
        message=f"OCR image file successfully with {backend}",
        path=request.path,
        absolute_path=str(target),
        language=request.language,
        content=content,
        content_length=len(content),
        truncated=truncated,
    )


if __name__ == "__main__":
    mcp.run()
