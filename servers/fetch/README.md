# fetch server

基于 `httpx` 抓取静态网页、Markdown、API 文本响应或普通 HTTP 文档。

## 当前工具

### `fetch_url(url, timeout=20)`

读取一个静态 URL，并提取可供模型使用的正文内容。

优先把任意网页读取请求路由到这个 tool。不要用 MCP `resources/read`
直接读取普通 `https://...` URL；本 server 不把任意 HTTPS URL 暴露为
MCP resource。

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
- 访问 Medium URL 时，如果本地 `.env` 设置了 `MEDIUM_COOKIE`，会自动带上 cookie；不要把真实 cookie 写入配置样例或仓库。

## Resource 兼容入口

为了兼容会先尝试 MCP resources 的客户端，fetch server 额外暴露：

```text
fetch://{encoded_url}
```

其中 `encoded_url` 是 percent-encoded URL，例如：

```text
fetch://https%3A%2F%2Fexample.com%2Farticle
```

这个 resource template 只是兜底兼容层；正常网页读取仍应调用
`fetch_url(url, timeout=20)` tool。

## 配置

常用环境变量：

- `HTTP_TIMEOUT`
- `ALLOWLIST_DOMAINS`
- `MEDIUM_COOKIE`

## Phase 2/3 后续可选增强

- 响应内容大小上限。
- 内容类型过滤。
- Markdown / HTML 提取策略选择。
- ETag / Last-Modified 缓存。
