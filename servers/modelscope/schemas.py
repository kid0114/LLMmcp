from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.responses import BaseResponse

ModelScopeResourceType = Literal["skill", "dataset", "model", "paper"]
ModelScopeSort = Literal[
    "trending",
    "growth",
    "recent",
    "updated",
    "downloads",
    "likes",
    "views",
    "favorites",
    "impact",
]


class ModelScopeTrendingRequest(BaseModel):
    resource_type: ModelScopeResourceType
    query: str | None = None
    max_results: int = Field(default=10, ge=1, le=25)
    sort: ModelScopeSort = "trending"
    period: str | None = None
    days: int = Field(default=30, ge=1, le=3650)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("sort", mode="before")
    @classmethod
    def normalize_sort(cls, value: object) -> object:
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
    def resolve_period(self) -> "ModelScopeTrendingRequest":
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


class ModelScopeResourceResult(BaseModel):
    rank: int
    resource_type: ModelScopeResourceType
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    description: str | None = None
    url: str
    source: str = "modelscope"
    downloads: int | None = None
    likes: int | None = None
    view_count: int | None = None
    favorite_count: int | None = None
    impact_score: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class ModelScopeTrendingResponse(BaseResponse):
    resource_type: ModelScopeResourceType
    query: str | None = None
    sort: ModelScopeSort
    period: str | None = None
    days: int
    results: list[ModelScopeResourceResult]
    total_results: int
