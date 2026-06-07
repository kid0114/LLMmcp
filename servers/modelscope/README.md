# modelscope MCP

`modelscope MCP` 提供对 ModelScope 公开资源索引的趋势查询能力，当前聚焦：

- `modelscope_trending_resources`：统一查询 `skill`、`dataset`、`model`、`paper` 四类资源。
- 支持 `period=today|week|10d|14d|month|Nd`，也支持直接传 `days`。
- 支持 `sort=trending|recent|updated|downloads|likes|views|favorites|impact`。

## 边界

- `skill` / `dataset` / `model` 当前走 `openapi/v1`。
- `paper` 当前走 `api/v1/papers`。
- `mcp` 广场页面存在，但本轮尚未定位到稳定公开数据接口，因此暂未纳入 `resource_type`。
