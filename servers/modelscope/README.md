# modelscope MCP

`modelscope MCP` 提供对 ModelScope 公开资源索引的趋势查询能力，当前聚焦：

- `modelscope_trending_resources`：统一查询 `skill`、`dataset`、`model`、`paper`、`mcp` 五类资源。
- 支持 `period=today|week|10d|14d|month|Nd`，也支持直接传 `days`。
- 支持 `sort=trending|recent|updated|downloads|likes|views|favorites|impact`。

## 边界

- `skill` / `dataset` / `model` 当前走 `openapi/v1`。
- `paper` 当前走 `api/v1/papers`。
- `mcp` 当前按浏览器抓包走 ModelScope MCP 广场接口 `PUT api/v1/dolphin/mcpServers`，默认不需要 cookie。
- ModelScope 的公开 API 和 MCP 广场请求都会先使用通用浏览器风格 header，再叠加 ModelScope 自己的请求头。
- `mcp` 热度信号映射：`CallVolume -> downloads`，`Stars -> likes / favorite_count`，`ViewCount -> view_count`。
- ModelScope MCP 广场接口可能受 Aliyun WAF 影响；被拦截时会返回明确错误，而不是吞掉为 0 结果。
- 仅当 MCP 广场接口被 WAF 拦截时，可设置 `MODELSCOPE_MCP_COOKIE` 为浏览器会话中的 ModelScope cookie；`csrf_token` 会自动映射为 `X-CSRF-TOKEN`，也可用 `MODELSCOPE_MCP_CSRF_TOKEN` 显式覆盖。

## MCP 搜索示例

```python
modelscope_trending_resources(resource_type="mcp", query="fetch", max_results=5, sort="views")
modelscope_trending_resources(resource_type="mcp", query="github", max_results=5, sort="views")
modelscope_trending_resources(resource_type="mcp", query="@modelcontextprotocol/fetch", max_results=5, sort="views")
modelscope_trending_resources(resource_type="mcp", query="leetcode-mcp-server", max_results=5, sort="views")
```

`query` 会传给 ModelScope 服务端搜索，同时本地会再匹配 `id`、`title`、`description`、`url` 和 `tags`，因此既可以搜关键词，也可以搜具体 MCP 名称或包 ID。
