from pydantic import BaseModel, Field, field_validator

from shared.responses import BaseResponse


class FileReaderPathRequest(BaseModel):
    path: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("path must not be empty")
        return stripped


class PdfReadRequest(FileReaderPathRequest):
    max_chars: int = Field(default=20000, ge=1, le=500000)
    max_pages: int = Field(default=20, ge=1, le=500)


class TextReadRequest(FileReaderPathRequest):
    max_chars: int = Field(default=20000, ge=1, le=500000)
    offset: int = Field(default=0, ge=0)


class MixedTextReadRequest(TextReadRequest):
    pass


class ImageMetadataRequest(FileReaderPathRequest):
    pass


class ImageOcrRequest(FileReaderPathRequest):
    language: str = "eng"
    max_chars: int = Field(default=20000, ge=1, le=500000)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("language must not be empty")
        return stripped


class PdfReadResponse(BaseResponse):
    path: str
    absolute_path: str
    page_count: int
    pages_read: int
    content: str
    content_length: int
    truncated: bool = False


class FileClassificationResponse(BaseResponse):
    path: str
    absolute_path: str
    extension: str
    media_type: str | None = None
    size: int
    category: str
    readable: bool
    reader: str | None = None
    text_kind: str | None = None
    mixed_kind: str | None = None
    notes: list[str] = Field(default_factory=list)


class TextReadResponse(BaseResponse):
    path: str
    absolute_path: str
    category: str
    text_kind: str | None = None
    mixed_kind: str | None = None
    content: str
    content_length: int
    offset: int = 0
    bytes_size: int
    truncated: bool = False


class ImageMetadataResponse(BaseResponse):
    path: str
    absolute_path: str
    format: str | None = None
    mode: str | None = None
    width: int
    height: int
    has_alpha: bool
    exif: dict[str, str] | None = None


class ImageOcrResponse(BaseResponse):
    path: str
    absolute_path: str
    language: str
    content: str
    content_length: int
    truncated: bool = False
