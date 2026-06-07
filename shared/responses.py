from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    status: str = Field(default="ok")
    message: str | None = None


class ErrorResponse(BaseResponse):
    status: str = Field(default="error")
    error_code: str
    details: str


class HealthResponse(BaseResponse):
    service: str | None = None
    version: str = Field(default="0.1.0")
