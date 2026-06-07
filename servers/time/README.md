# time server

提供当前时间、时区转换和相对时间解析能力。

## 当前工具

### `get_current_time(timezone="UTC")`

返回指定时区的当前时间。

返回：

- `timezone`
- `datetime`
- `unix_timestamp`
- `utc_offset`

### `convert_time(datetime_text, from_timezone="UTC", to_timezone="UTC")`

把 ISO 8601 时间从一个时区转换到另一个时区。

说明：

- `datetime_text` 如果不带时区，会按 `from_timezone` 解释。
- `datetime_text` 如果已带时区，会优先使用输入里的时区。
- `timezone` 使用 IANA 时区名，例如 `UTC`、`Asia/Shanghai`、`America/Los_Angeles`。

### `parse_relative_time(expression, timezone="UTC", base_datetime=None)`

解析相对时间表达式。

当前支持：

- `now`
- `today`
- `tomorrow`
- `yesterday`
- `in 3 days`
- `2 hours ago`
- `现在`
- `今天`
- `明天`
- `昨天`
- `3天后`
- `2小时前`

## Phase 3 后续可选增强

- 支持更多自然语言时间表达式。
- 支持工作日 / 周末计算。
- 支持定时任务和提醒类能力。
