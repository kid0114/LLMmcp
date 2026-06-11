# huggingface MCP

`huggingface MCP` 提供对 Hugging Face 公开资源索引的趋势查询能力，当前聚焦：

- `huggingface_trending_resources`：统一查询 `paper`、`model`、`dataset`、`mcp` 四类资源。
- 支持 `period=today|week|10d|14d|month|Nd`，也支持直接传 `days`。
- 支持 `sort=trending|recent|updated|downloads|likes`。

## 边界

- `model` 走 `https://huggingface.co/api/models`
- `dataset` 走 `https://huggingface.co/api/datasets`
- `paper` 走 `https://huggingface.co/api/papers`
- `mcp` 走 `https://huggingface.co/api/spaces`，返回带 MCP / Model Context Protocol 语义的 Spaces。
- 当前不提供 `skill` 资源类型，因为 Hugging Face 没有对等公开索引
- Hugging Face API 请求会使用通用浏览器风格 header；未定义专用覆盖时直接复用默认值。

## MCP 搜索示例

```python
huggingface_trending_resources(resource_type="mcp", query="mcp", max_results=5, sort="likes", days=3650)
huggingface_trending_resources(resource_type="mcp", query="web-scraper", max_results=5, sort="likes", days=3650)
```

Hugging Face 的 MCP 资源主要是 MCP-enabled Spaces。`query` 会传给 Hub Spaces 搜索，结果会再本地过滤 `id`、`title`、`description`、`url` 和 `tags`，并保留带 `mcp` / `model context protocol` 语义的条目。
