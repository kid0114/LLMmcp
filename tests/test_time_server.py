from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from servers.time.server import (
    TimeError,
    _parse_relative_expression,
    convert_time,
    parse_relative_time,
)


def test_convert_time_from_naive_datetime() -> None:
    response = convert_time(
        "2026-06-07T08:00:00",
        from_timezone="UTC",
        to_timezone="Asia/Shanghai",
    )

    assert response.converted_datetime == "2026-06-07T16:00:00+08:00"
    assert response.utc_offset == "+08:00"


def test_convert_time_rejects_unknown_timezone() -> None:
    with pytest.raises(TimeError, match="Unknown timezone"):
        convert_time("2026-06-07T08:00:00", to_timezone="Bad/Timezone")


def test_parse_relative_expression_english_future() -> None:
    base = datetime(2026, 6, 7, 8, 0, tzinfo=ZoneInfo("UTC"))
    resolved = _parse_relative_expression("in 3 days", base)

    assert resolved.isoformat() == "2026-06-10T08:00:00+00:00"


def test_parse_relative_expression_chinese_past() -> None:
    base = datetime(2026, 6, 7, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    resolved = _parse_relative_expression("2小时前", base)

    assert resolved.isoformat() == "2026-06-07T06:00:00+08:00"


def test_parse_relative_time_with_base_datetime() -> None:
    response = parse_relative_time(
        "明天",
        timezone="Asia/Shanghai",
        base_datetime="2026-06-07T08:00:00",
    )

    assert response.base_datetime == "2026-06-07T08:00:00+08:00"
    assert response.resolved_datetime == "2026-06-08T08:00:00+08:00"
