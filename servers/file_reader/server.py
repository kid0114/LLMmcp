from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Any

from mcp.server.fastmcp import FastMCP
from PIL import Image, UnidentifiedImageError

from servers.file_reader.schemas import (
    FileClassificationResponse,
    FileReaderPathRequest,
    ImageMetadataRequest,
    ImageMetadataResponse,
    ImageOcrRequest,
    ImageOcrResponse,
    MixedTextReadRequest,
    PdfReadRequest,
    PdfReadResponse,
    TextReadRequest,
    TextReadResponse,
)
from shared.errors import FileReaderError, PermissionDeniedError
from shared.logging import get_logger
from shared.permissions import validate_local_path
from shared.settings import get_settings

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-file-reader")

TEXT_EXTENSIONS: dict[str, str] = {
    ".txt": "plain_text",
    ".log": "plain_text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "restructured_text",
    ".py": "python",
    ".pyi": "python_stub",
    ".js": "javascript",
    ".jsx": "javascript_react",
    ".ts": "typescript",
    ".tsx": "typescript_react",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c_header",
    ".cpp": "cpp",
    ".hpp": "cpp_header",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".fish": "shell",
    ".ps1": "powershell",
    ".json": "json",
    ".jsonl": "json_lines",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "config",
    ".conf": "config",
    ".env": "env",
    ".csv": "csv",
    ".tsv": "tsv",
    ".sql": "sql",
    ".css": "css",
}
MIXED_TEXT_EXTENSIONS: dict[str, str] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
    ".xml": "xml",
    ".svg": "svg",
    ".ipynb": "notebook",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


@dataclass(frozen=True)
class FileClassification:
    extension: str
    media_type: str | None
    size: int
    category: str
    readable: bool
    reader: str | None
    text_kind: str | None = None
    mixed_kind: str | None = None
    notes: tuple[str, ...] = ()


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


def _looks_like_utf8_text(path: Path, max_bytes: int = 8192) -> bool:
    try:
        sample = path.read_bytes()[:max_bytes]
    except Exception as exc:
        raise FileReaderError(f"Failed to inspect file bytes: {exc}") from exc
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _classify_file(target: Path) -> FileClassification:
    extension = target.suffix.lower()
    media_type, _ = mimetypes.guess_type(target.name)
    size = target.stat().st_size

    if extension in MIXED_TEXT_EXTENSIONS:
        return FileClassification(
            extension=extension,
            media_type=media_type,
            size=size,
            category="mixed",
            readable=True,
            reader="read_mixed_text_file",
            text_kind=TEXT_EXTENSIONS.get(extension, "markup"),
            mixed_kind=MIXED_TEXT_EXTENSIONS[extension],
            notes=("Text-readable file with embedded or structured content.",),
        )
    if extension in TEXT_EXTENSIONS:
        return FileClassification(
            extension=extension,
            media_type=media_type,
            size=size,
            category="text",
            readable=True,
            reader="read_text_file",
            text_kind=TEXT_EXTENSIONS[extension],
        )
    if extension == ".pdf":
        return FileClassification(
            extension=extension,
            media_type=media_type,
            size=size,
            category="document",
            readable=True,
            reader="read_pdf_file",
            text_kind="pdf_text_layer",
            notes=("Scanned PDFs may need OCR; read_pdf_file only extracts text layers.",),
        )
    if extension in IMAGE_EXTENSIONS or (media_type or "").startswith("image/"):
        return FileClassification(
            extension=extension,
            media_type=media_type,
            size=size,
            category="image",
            readable=True,
            reader="ocr_image_file",
            notes=("Use inspect_image_file for metadata or ocr_image_file for text.",),
        )
    if media_type and media_type.startswith("text/"):
        return FileClassification(
            extension=extension,
            media_type=media_type,
            size=size,
            category="text",
            readable=True,
            reader="read_text_file",
            text_kind=media_type.removeprefix("text/"),
        )
    if _looks_like_utf8_text(target):
        return FileClassification(
            extension=extension,
            media_type=media_type,
            size=size,
            category="text",
            readable=True,
            reader="read_text_file",
            text_kind="utf8_text",
            notes=("Detected as UTF-8 text from file bytes.",),
        )
    return FileClassification(
        extension=extension,
        media_type=media_type,
        size=size,
        category="binary",
        readable=False,
        reader=None,
        notes=("No text reader is available for this file type.",),
    )


def _read_text_slice(target: Path, offset: int, max_chars: int) -> tuple[str, bool]:
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise FileReaderError(f"Failed to read text file: {exc}") from exc
    sliced = content[offset : offset + max_chars]
    truncated = offset + len(sliced) < len(content)
    return sliced, truncated


def _extract_html_text(target: Path) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise FileReaderError("beautifulsoup4 is required to read HTML-like files") from exc

    raw = target.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")
    for element in soup(["script", "style"]):
        element.extract()
    return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())


def _source_to_text(source: object) -> str:
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)


def _extract_notebook_text(target: Path) -> str:
    try:
        data = json.loads(target.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        raise FileReaderError(f"Failed to parse notebook JSON: {exc}") from exc

    cells = data.get("cells") if isinstance(data, dict) else None
    if not isinstance(cells, list):
        raise FileReaderError("Notebook JSON does not contain a cells list")

    parts: list[str] = []
    for index, cell in enumerate(cells, start=1):
        if not isinstance(cell, dict):
            continue
        cell_type = str(cell.get("cell_type", "unknown"))
        source = _source_to_text(cell.get("source", ""))
        if source.strip():
            parts.append(f"[cell {index}: {cell_type}]\n{source.strip()}")
        outputs = cell.get("outputs")
        if isinstance(outputs, list):
            for output in outputs:
                if not isinstance(output, dict):
                    continue
                text = output.get("text")
                if text:
                    parts.append(f"[cell {index}: output]\n{_source_to_text(text).strip()}")
    return "\n\n".join(parts)


def _extract_mixed_text(target: Path, mixed_kind: str) -> str:
    if mixed_kind in {"html", "xml", "svg"}:
        return _extract_html_text(target)
    if mixed_kind == "notebook":
        return _extract_notebook_text(target)
    content, _ = _read_text_slice(target, 0, 500000)
    return content


@mcp.tool()
def classify_readable_file(path: str) -> FileClassificationResponse:
    request = FileReaderPathRequest(path=path)
    root = _resolve_local_root()
    target = _resolve_safe_path(request.path, root)
    _require_file(target)

    classification = _classify_file(target)
    logger.info("classify_readable_file called", extra={"path": request.path})
    return FileClassificationResponse(
        message="Classified readable file successfully",
        path=request.path,
        absolute_path=str(target),
        extension=classification.extension,
        media_type=classification.media_type,
        size=classification.size,
        category=classification.category,
        readable=classification.readable,
        reader=classification.reader,
        text_kind=classification.text_kind,
        mixed_kind=classification.mixed_kind,
        notes=list(classification.notes),
    )


@mcp.tool()
def read_text_file(path: str, max_chars: int = 20000, offset: int = 0) -> TextReadResponse:
    request = TextReadRequest(path=path, max_chars=max_chars, offset=offset)
    root = _resolve_local_root()
    target = _resolve_safe_path(request.path, root)
    _require_file(target)
    classification = _classify_file(target)
    if classification.category not in {"text", "mixed"}:
        raise FileReaderError(
            f"File is classified as {classification.category}; use {classification.reader}"
        )

    content, truncated = _read_text_slice(target, request.offset, request.max_chars)
    logger.info("read_text_file called", extra={"path": request.path})
    return TextReadResponse(
        message="Read text file successfully",
        path=request.path,
        absolute_path=str(target),
        category=classification.category,
        text_kind=classification.text_kind,
        mixed_kind=classification.mixed_kind,
        content=content,
        content_length=len(content),
        offset=request.offset,
        bytes_size=classification.size,
        truncated=truncated,
    )


@mcp.tool()
def read_mixed_text_file(
    path: str, max_chars: int = 20000, offset: int = 0
) -> TextReadResponse:
    request = MixedTextReadRequest(path=path, max_chars=max_chars, offset=offset)
    root = _resolve_local_root()
    target = _resolve_safe_path(request.path, root)
    _require_file(target)
    classification = _classify_file(target)
    if classification.category != "mixed" or classification.mixed_kind is None:
        raise FileReaderError("File is not classified as a mixed text file")

    extracted = _extract_mixed_text(target, classification.mixed_kind)
    content = extracted[request.offset : request.offset + request.max_chars]
    truncated = request.offset + len(content) < len(extracted)
    logger.info("read_mixed_text_file called", extra={"path": request.path})
    return TextReadResponse(
        message="Read mixed text file successfully",
        path=request.path,
        absolute_path=str(target),
        category=classification.category,
        text_kind=classification.text_kind,
        mixed_kind=classification.mixed_kind,
        content=content,
        content_length=len(content),
        offset=request.offset,
        bytes_size=classification.size,
        truncated=truncated,
    )


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
