import pytest
from pydantic import ValidationError

from servers.time.schemas import RelativeTimeRequest, TimeConvertRequest, TimezoneRequest


def test_timezone_request_defaults_to_utc() -> None:
    request = TimezoneRequest()
    assert request.timezone == "UTC"


def test_timezone_request_rejects_blank_timezone() -> None:
    with pytest.raises(ValidationError):
        TimezoneRequest(timezone=" ")


def test_time_convert_request_strips_values() -> None:
    request = TimeConvertRequest(
        datetime_text=" 2026-06-07T08:00:00 ",
        from_timezone=" UTC ",
        to_timezone=" Asia/Shanghai ",
    )
    assert request.datetime_text == "2026-06-07T08:00:00"
    assert request.from_timezone == "UTC"
    assert request.to_timezone == "Asia/Shanghai"


def test_relative_time_request_normalizes_empty_base_datetime() -> None:
    request = RelativeTimeRequest(expression="tomorrow", base_datetime=" ")
    assert request.base_datetime is None
