from pydantic import BaseModel, Field, HttpUrl

from shared.responses import BaseResponse


class FetchRequest(BaseModel):
    url: HttpUrl
    timeout: int = Field(default=20, ge=1, le=120)


class FetchResponse(BaseResponse):
    url: HttpUrl
    status_code: int
    title: str | None = None
    content: str
    content_length: int
