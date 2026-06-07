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
