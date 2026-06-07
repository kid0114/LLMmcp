# huggingface MCP

`huggingface MCP` 提供对 Hugging Face 公开资源索引的趋势查询能力，当前聚焦：

- `huggingface_trending_resources`：统一查询 `paper`、`model`、`dataset` 三类资源。
- 支持 `period=today|week|10d|14d|month|Nd`，也支持直接传 `days`。
- 支持 `sort=trending|recent|updated|downloads|likes`。

## 边界

- `model` 走 `https://huggingface.co/api/models`
- `dataset` 走 `https://huggingface.co/api/datasets`
- `paper` 走 `https://huggingface.co/api/papers`
- 当前不提供 `skill` 资源类型，因为 Hugging Face 没有对等公开索引
