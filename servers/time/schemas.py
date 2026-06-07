from pydantic import BaseModel, Field, field_validator

from shared.responses import BaseResponse


class TimezoneRequest(BaseModel):
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("timezone must not be empty")
        return stripped


class TimeConvertRequest(BaseModel):
    datetime_text: str = Field(min_length=1)
    from_timezone: str = "UTC"
    to_timezone: str = "UTC"

    @field_validator("datetime_text", "from_timezone", "to_timezone")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        return stripped


class RelativeTimeRequest(BaseModel):
    expression: str = Field(min_length=1)
    timezone: str = "UTC"
    base_datetime: str | None = None

    @field_validator("expression", "timezone")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        return stripped

    @field_validator("base_datetime")
    @classmethod
    def validate_base_datetime(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TimeResponse(BaseResponse):
    timezone: str
    datetime: str
    unix_timestamp: float
    utc_offset: str


class TimeConvertResponse(BaseResponse):
    input_datetime: str
    from_timezone: str
    to_timezone: str
    converted_datetime: str
    unix_timestamp: float
    utc_offset: str


class RelativeTimeResponse(BaseResponse):
    expression: str
    timezone: str
    base_datetime: str
    resolved_datetime: str
    unix_timestamp: float
    utc_offset: str
