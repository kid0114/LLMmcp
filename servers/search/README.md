# search server

提供网页搜索能力，返回结构化搜索结果。

## 当前工具

### `search_web(query, max_results=5, provider="auto")`

搜索网页并返回候选结果。

参数：

- `query`：搜索关键词，不能为空。
- `max_results`：返回结果数量，范围 `1..20`。
- `provider`：搜索 provider，可选 `auto`、`ddgs`、`brave`。

返回：

- `query`
- `results`
- `result.title`
- `result.url`
- `result.snippet`
- `result.source`
- `total_results`

说明：

- `provider="ddgs"` 使用 DuckDuckGo / ddgs。
- `provider="brave"` 使用 Brave Search，需要 `BRAVE_API_KEY`。
- `provider="auto"` 会读取 `SEARCH_PROVIDER` 环境变量，再按当前回退策略执行。
- Brave Search 请求会使用通用浏览器风格 header，避免裸请求特征过强。
- 适合先找候选页面，再交给 `fetch_url` 或 `browser_fetch` 读取正文。

## 配置

常用环境变量：

- `SEARCH_PROVIDER`
- `BRAVE_API_KEY`
- `HTTP_TIMEOUT`
- `ALLOWLIST_DOMAINS`

## Phase 2/3 后续可选增强

- 搜索结果缓存。
- provider 健康检查。
- 搜索结果去重和域名聚合。
- 针对论文、GitHub、文档站的垂直搜索入口。
