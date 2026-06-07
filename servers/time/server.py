from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.fastmcp import FastMCP

from servers.time.schemas import (
    RelativeTimeRequest,
    RelativeTimeResponse,
    TimeConvertRequest,
    TimeConvertResponse,
    TimeResponse,
    TimezoneRequest,
)
from shared.errors import MCPToolError
from shared.logging import get_logger

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-time")

_RELATIVE_UNITS = {
    "second": "seconds",
    "seconds": "seconds",
    "秒": "seconds",
    "minute": "minutes",
    "minutes": "minutes",
    "分钟": "minutes",
    "hour": "hours",
    "hours": "hours",
    "小时": "hours",
    "day": "days",
    "days": "days",
    "天": "days",
    "week": "weeks",
    "weeks": "weeks",
    "周": "weeks",
    "星期": "weeks",
}


class TimeError(MCPToolError):
    """Raised when time parsing or conversion fails."""


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise TimeError(f"Unknown timezone: {name}") from exc


def _utc_offset(value: datetime) -> str:
    offset = value.utcoffset()
    if offset is None:
        return "+00:00"
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"{sign}{hours:02d}:{minutes:02d}"


def _parse_datetime(datetime_text: str, timezone_name: str) -> datetime:
    normalized = datetime_text.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise TimeError("datetime_text must be an ISO 8601 datetime") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_timezone(timezone_name))
    return parsed


def _response_for_datetime(value: datetime, timezone_name: str) -> TimeResponse:
    return TimeResponse(
        message="Read current time successfully",
        timezone=timezone_name,
        datetime=value.isoformat(),
        unix_timestamp=value.timestamp(),
        utc_offset=_utc_offset(value),
    )


def _relative_delta(amount: int, unit: str) -> timedelta:
    normalized_unit = _RELATIVE_UNITS.get(unit)
    if normalized_unit is None:
        raise TimeError(f"Unsupported relative time unit: {unit}")
    return timedelta(**{normalized_unit: amount})


def _parse_relative_expression(expression: str, base: datetime) -> datetime:
    normalized = expression.strip().lower()
    if normalized in {"now", "现在"}:
        return base
    if normalized in {"today", "今天"}:
        return base
    if normalized in {"tomorrow", "明天"}:
        return base + timedelta(days=1)
    if normalized in {"yesterday", "昨天"}:
        return base - timedelta(days=1)

    parts = normalized.split()
    if len(parts) == 3 and parts[0] == "in":
        return base + _relative_delta(int(parts[1]), parts[2])
    if len(parts) == 3 and parts[2] == "ago":
        return base - _relative_delta(int(parts[0]), parts[1])

    if normalized.endswith("后"):
        return base + _parse_chinese_relative_delta(normalized[:-1])
    if normalized.endswith("前"):
        return base - _parse_chinese_relative_delta(normalized[:-1])

    raise TimeError(f"Unsupported relative time expression: {expression}")


def _parse_chinese_relative_delta(value: str) -> timedelta:
    for unit in ("分钟", "小时", "星期", "秒", "天", "周"):
        if value.endswith(unit):
            amount_text = value[: -len(unit)].strip()
            if not amount_text:
                raise TimeError("Relative time amount is missing")
            return _relative_delta(int(amount_text), unit)
    raise TimeError(f"Unsupported relative time expression: {value}")


@mcp.tool()
def get_current_time(timezone: str = "UTC") -> TimeResponse:
    request = TimezoneRequest(timezone=timezone)
    tz = _timezone(request.timezone)
    current = datetime.now(tz)
    logger.info("get_current_time called", extra={"timezone": request.timezone})
    return _response_for_datetime(current, request.timezone)


@mcp.tool()
def convert_time(
    datetime_text: str, from_timezone: str = "UTC", to_timezone: str = "UTC"
) -> TimeConvertResponse:
    request = TimeConvertRequest(
        datetime_text=datetime_text,
        from_timezone=from_timezone,
        to_timezone=to_timezone,
    )
    parsed = _parse_datetime(request.datetime_text, request.from_timezone)
    converted = parsed.astimezone(_timezone(request.to_timezone))
    logger.info(
        "convert_time called",
        extra={"from_timezone": request.from_timezone, "to_timezone": request.to_timezone},
    )
    return TimeConvertResponse(
        message="Converted time successfully",
        input_datetime=request.datetime_text,
        from_timezone=request.from_timezone,
        to_timezone=request.to_timezone,
        converted_datetime=converted.isoformat(),
        unix_timestamp=converted.timestamp(),
        utc_offset=_utc_offset(converted),
    )


@mcp.tool()
def parse_relative_time(
    expression: str, timezone: str = "UTC", base_datetime: str | None = None
) -> RelativeTimeResponse:
    request = RelativeTimeRequest(
        expression=expression,
        timezone=timezone,
        base_datetime=base_datetime,
    )
    tz = _timezone(request.timezone)
    base = (
        _parse_datetime(request.base_datetime, request.timezone).astimezone(tz)
        if request.base_datetime
        else datetime.now(tz)
    )
    resolved = _parse_relative_expression(request.expression, base)
    logger.info(
        "parse_relative_time called",
        extra={"expression": request.expression, "timezone": request.timezone},
    )
    return RelativeTimeResponse(
        message="Parsed relative time successfully",
        expression=request.expression,
        timezone=request.timezone,
        base_datetime=base.isoformat(),
        resolved_datetime=resolved.isoformat(),
        unix_timestamp=resolved.timestamp(),
        utc_offset=_utc_offset(resolved),
    )


if __name__ == "__main__":
    mcp.run()
