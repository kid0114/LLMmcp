from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from shared.responses import BaseResponse


class GitHubSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=20)
    sort: Literal["best-match", "stars", "updated"] = "best-match"

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return stripped


class GitHubTrendingRequest(BaseModel):
    since: Literal["daily", "weekly", "monthly"] = "daily"
    language: str | None = None
    max_results: int = Field(default=15, ge=1, le=25)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().strip("/")
        return stripped or None


class GitHubModelSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=10, ge=1, le=20)
    sort: Literal["best-match", "stars", "updated"] = "stars"
    language: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return stripped

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class GitHubRepositoryResult(BaseModel):
    name: str
    full_name: str
    url: HttpUrl
    description: str | None = None
    stars: int
    language: str | None = None


class GitHubCodeResult(BaseModel):
    name: str
    path: str
    repository: str
    url: HttpUrl
    sha: str


class GitHubIssueResult(BaseModel):
    title: str
    url: HttpUrl
    repository: str
    state: str
    number: int


class GitHubTrendingRepositoryResult(BaseModel):
    rank: int
    name: str
    full_name: str
    url: HttpUrl
    description: str | None = None
    language: str | None = None
    total_stars: int | None = None
    forks: int | None = None
    stars_period: int | None = None
    period: Literal["daily", "weekly", "monthly"]
    source: str = "github_trending"


class GitHubRepositorySearchResponse(BaseResponse):
    query: str
    results: list[GitHubRepositoryResult]
    total_results: int


class GitHubCodeSearchResponse(BaseResponse):
    query: str
    results: list[GitHubCodeResult]
    total_results: int


class GitHubIssueSearchResponse(BaseResponse):
    query: str
    results: list[GitHubIssueResult]
    total_results: int


class GitHubTrendingRepositoriesResponse(BaseResponse):
    since: Literal["daily", "weekly", "monthly"]
    language: str | None = None
    results: list[GitHubTrendingRepositoryResult]
    total_results: int


class GitHubModelRepositorySearchResponse(BaseResponse):
    query: str
    resolved_query: str
    language: str | None = None
    results: list[GitHubRepositoryResult]
    total_results: int
