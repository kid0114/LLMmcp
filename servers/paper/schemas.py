from typing import Literal

from pydantic import BaseModel, Field, field_validator

from shared.responses import BaseResponse

PaperProvider = Literal["auto", "arxiv", "crossref", "openalex"]
PaperIdentifierType = Literal["auto", "doi", "arxiv_id", "url", "local_path"]


class PaperSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=20)
    provider: PaperProvider = "auto"
    author: str | None = None
    title: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    year_from: int | None = Field(default=None, ge=1800, le=2200)
    year_to: int | None = Field(default=None, ge=1800, le=2200)
    venue: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return stripped

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().lower()

    @field_validator("author", "title", "doi", "arxiv_id", "venue")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PaperMetadataRequest(BaseModel):
    identifier: str = Field(min_length=1)
    identifier_type: PaperIdentifierType = "auto"

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("identifier must not be empty")
        return stripped

    @field_validator("identifier_type", mode="before")
    @classmethod
    def normalize_identifier_type(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().lower()


class PaperReadRequest(PaperMetadataRequest):
    max_chars: int = Field(default=20000, ge=1, le=500000)
    offset: int = Field(default=0, ge=0)
    max_pages: int = Field(default=30, ge=1, le=500)


class PaperSectionReadRequest(PaperReadRequest):
    section: str = Field(min_length=1)

    @field_validator("section")
    @classmethod
    def validate_section(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("section must not be empty")
        return stripped


class PaperSummarizeRequest(PaperReadRequest):
    max_points: int = Field(default=6, ge=1, le=20)


class PaperCompareRequest(BaseModel):
    identifiers: list[str] = Field(min_length=2, max_length=5)
    identifier_type: PaperIdentifierType = "auto"
    max_chars_per_paper: int = Field(default=8000, ge=1000, le=50000)

    @field_validator("identifiers")
    @classmethod
    def validate_identifiers(cls, value: list[str]) -> list[str]:
        stripped = [item.strip() for item in value if item.strip()]
        if len(stripped) < 2:
            raise ValueError("at least two paper identifiers are required")
        return stripped


class PaperResult(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    citation_count: int | None = None
    source: str


class PaperSearchResponse(BaseResponse):
    query: str
    provider: PaperProvider
    results: list[PaperResult]
    total_results: int


class PaperMetadataResponse(BaseResponse):
    identifier: str
    identifier_type: PaperIdentifierType
    paper: PaperResult | None = None


class PaperReadResponse(BaseResponse):
    identifier: str
    identifier_type: PaperIdentifierType
    source_path: str | None = None
    source_url: str | None = None
    page_count: int | None = None
    pages_read: int | None = None
    content: str
    content_length: int
    offset: int = 0
    truncated: bool = False


class PaperSectionsResponse(BaseResponse):
    identifier: str
    sections: dict[str, str]
    total_sections: int


class PaperCitationsResponse(BaseResponse):
    identifier: str
    citations: list[str]
    total_citations: int


class PaperSummaryResponse(BaseResponse):
    identifier: str
    title: str | None = None
    summary: str
    key_points: list[str]


class PaperComparisonItem(BaseModel):
    identifier: str
    title: str | None = None
    abstract: str | None = None
    key_terms: list[str]


class PaperComparisonResponse(BaseResponse):
    results: list[PaperComparisonItem]
    total_results: int
