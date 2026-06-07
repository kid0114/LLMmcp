from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from shared.responses import BaseResponse


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=20)
    provider: Literal["auto", "brave", "ddgs"] = "auto"

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


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    snippet: str
    source: str


class SearchResponse(BaseResponse):
    query: str
    results: list[SearchResult]
    total_results: int
