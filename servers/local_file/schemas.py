from pydantic import BaseModel, Field, field_validator

from shared.responses import BaseResponse


class LocalPathRequest(BaseModel):
    path: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("path must not be empty")
        return stripped


class LocalFileRequest(LocalPathRequest):
    offset: int = Field(default=0, ge=0)
    max_chars: int = Field(default=20000, ge=1, le=200000)


class LocalListRequest(LocalPathRequest):
    max_entries: int = Field(default=100, ge=1, le=1000)


class LocalGlobRequest(LocalPathRequest):
    pattern: str = Field(min_length=1)
    max_results: int = Field(default=100, ge=1, le=1000)

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("pattern must not be empty")
        return stripped


class LocalSearchRequest(LocalPathRequest):
    query: str = Field(min_length=1)
    include_glob: str | None = None
    max_results: int = Field(default=50, ge=1, le=500)
    max_file_chars: int = Field(default=200000, ge=1, le=2_000_000)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return stripped

    @field_validator("include_glob")
    @classmethod
    def validate_include_glob(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class LocalFileResponse(BaseResponse):
    path: str
    absolute_path: str
    content: str
    content_length: int
    offset: int = 0
    bytes_size: int
    truncated: bool = False


class LocalFileEntry(BaseModel):
    name: str
    path: str
    kind: str
    size: int | None = None
    modified_at: str | None = None


class LocalFileListResponse(BaseResponse):
    path: str
    absolute_path: str
    entries: list[LocalFileEntry]
    total_entries: int
    truncated: bool = False


class LocalFileStatResponse(BaseResponse):
    path: str
    absolute_path: str
    exists: bool
    kind: str | None = None
    size: int | None = None
    modified_at: str | None = None


class LocalFileGlobResponse(BaseResponse):
    path: str
    pattern: str
    results: list[LocalFileEntry]
    total_results: int
    truncated: bool = False


class LocalFileSearchMatch(BaseModel):
    path: str
    line_number: int
    line: str


class LocalFileSearchResponse(BaseResponse):
    path: str
    query: str
    include_glob: str | None = None
    results: list[LocalFileSearchMatch]
    total_results: int
    truncated: bool = False
