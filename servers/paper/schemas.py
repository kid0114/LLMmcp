from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.responses import BaseResponse

PaperProvider = Literal["auto", "arxiv", "crossref", "openalex"]
PaperTrendProvider = Literal["auto", "openalex", "arxiv", "huggingface", "modelscope"]
PaperTrendSort = Literal[
    "trending",
    "recent",
    "citations",
    "downloads",
    "likes",
    "updated",
    "growth",
]
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


class TrendingPapersRequest(BaseModel):
    query: str = Field(default="large language model", min_length=1)
    max_results: int = Field(default=10, ge=1, le=25)
    provider: PaperTrendProvider = "auto"
    sort: PaperTrendSort = "trending"
    period: str | None = None
    days: int = Field(default=30, ge=1, le=3650)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return stripped

    @field_validator("provider", "sort", mode="before")
    @classmethod
    def normalize_literal(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().lower()

    @field_validator("period")
    @classmethod
    def normalize_period(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().lower().replace(" ", "").replace("_", "").replace("-", "")
        return stripped or None

    @model_validator(mode="after")
    def resolve_period(self) -> "TrendingPapersRequest":
        if self.period is None:
            return self
        aliases = {
            "today": 1,
            "day": 1,
            "1d": 1,
            "week": 7,
            "1week": 7,
            "7d": 7,
            "10d": 10,
            "10days": 10,
            "14d": 14,
            "14days": 14,
            "2weeks": 14,
            "month": 30,
            "1month": 30,
            "30d": 30,
        }
        if self.period in aliases:
            self.days = aliases[self.period]
            return self
        if self.period.endswith("d") and self.period[:-1].isdigit():
            self.days = int(self.period[:-1])
            return self
        raise ValueError("period must be one of today, week, 10d, 14d, month, or Nd")


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


class TrendingPaperResult(PaperResult):
    rank: int
    score: float | None = None
    signals: dict[str, Any] = Field(default_factory=dict)
    related_model_id: str | None = None
    related_model_url: str | None = None


class PaperSearchResponse(BaseResponse):
    query: str
    provider: PaperProvider
    results: list[PaperResult]
    total_results: int


class TrendingPapersResponse(BaseResponse):
    query: str
    provider: PaperTrendProvider
    sort: PaperTrendSort
    period: str | None = None
    days: int
    results: list[TrendingPaperResult]
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
