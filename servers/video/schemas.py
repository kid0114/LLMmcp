from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from shared.responses import BaseResponse

VideoPlatform = Literal["youtube", "bilibili", "generic"]


class VideoUrlRequest(BaseModel):
    url: HttpUrl


class VideoSummaryRequest(BaseModel):
    transcript: str = Field(min_length=1)
    url: HttpUrl | None = None
    title: str | None = None
    max_points: int = Field(default=5, ge=1, le=10)
    max_summary_sentences: int = Field(default=3, ge=1, le=6)

    @field_validator("transcript")
    @classmethod
    def validate_transcript(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("transcript must not be empty")
        return stripped

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class VideoTranscriptSegment(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be empty")
        return stripped

    @model_validator(mode="after")
    def validate_range(self) -> "VideoTranscriptSegment":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        return self


class VideoSegmentSummaryRequest(BaseModel):
    segments: list[VideoTranscriptSegment] = Field(min_length=1)
    url: HttpUrl | None = None
    title: str | None = None
    max_points: int = Field(default=5, ge=1, le=10)
    max_summary_sentences: int = Field(default=3, ge=1, le=6)
    chapter_window_seconds: int = Field(default=180, ge=30, le=1800)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class VideoSourceResponse(BaseResponse):
    url: HttpUrl
    platform: VideoPlatform
    video_id: str | None = None
    canonical_url: str


class VideoChapterSummary(BaseModel):
    start_seconds: float
    end_seconds: float
    summary: str


class VideoSummaryResponse(BaseResponse):
    platform: VideoPlatform
    video_id: str | None = None
    canonical_url: str | None = None
    title: str | None = None
    summary: str
    key_points: list[str]
    chapters: list[VideoChapterSummary]
    transcript_characters: int
    transcript_segments: int
    estimated_duration_seconds: float | None = None
