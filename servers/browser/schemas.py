from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from shared.responses import BaseResponse


class BrowserRequest(BaseModel):
    url: HttpUrl
    timeout: int = Field(default=30, ge=1, le=180)
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "networkidle"


class BrowserResponse(BaseResponse):
    url: HttpUrl
    final_url: HttpUrl
    title: str | None = None
    content: str
    content_length: int
    screenshot_path: str | None = None
    status_code: int | None = None
