# fetch server

基于 `httpx` 抓取静态网页、Markdown、API 文本响应或普通 HTTP 文档。

## 当前工具

### `fetch_url(url, timeout=20)`

读取一个静态 URL，并提取可供模型使用的正文内容。

参数：

- `url`：目标 HTTP/HTTPS URL。
- `timeout`：请求超时时间，范围 `1..120` 秒。

返回：

- `url`
- `status_code`
- `title`
- `content`
- `content_length`

说明：

- 适合读取普通网页、Markdown、文本接口和静态 HTML。
- 对需要 JavaScript 渲染的页面，优先使用 `browser_fetch`。
- 出站 URL 会经过权限检查，默认阻止 localhost、私有地址和非 HTTP/HTTPS scheme。
- 如果配置了 `ALLOWLIST_DOMAINS`，只允许访问白名单域名。

## 配置

常用环境变量：

- `HTTP_TIMEOUT`
- `ALLOWLIST_DOMAINS`

## Phase 2/3 后续可选增强

- 响应内容大小上限。
- 内容类型过滤。
- Markdown / HTML 提取策略选择。
- ETag / Last-Modified 缓存。
