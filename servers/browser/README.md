# browser server

基于 Playwright 读取动态网页和 SPA 页面内容。

## 当前工具

### `browser_fetch(url, timeout=30, wait_until="networkidle")`

打开浏览器访问页面，等待页面加载后提取正文内容，并保存截图路径。

参数：

- `url`：目标 HTTP/HTTPS URL。
- `timeout`：浏览器加载超时时间，范围 `1..180` 秒。
- `wait_until`：等待策略，可选 `load`、`domcontentloaded`、`networkidle`。

返回：

- `url`
- `final_url`
- `title`
- `content`
- `content_length`
- `screenshot_path`
- `status_code`

说明：

- 适合读取需要 JavaScript 渲染、SPA、普通抓取拿不到正文的页面。
- `browser_fetch` 的 Playwright context 会复用通用浏览器风格 header；Medium URL 仍会注入本地 `MEDIUM_COOKIE`。
- 成本比 `fetch_url` 更高，会占用本机 CPU/内存。
- 出站 URL 会经过权限检查，默认阻止 localhost、私有地址和非 HTTP/HTTPS scheme。
- 如果配置了 `ALLOWLIST_DOMAINS`，只允许访问白名单域名。
## 配置

常用环境变量：

- `BROWSER_TIMEOUT`
- `BROWSER_HEADLESS`
- `ALLOWLIST_DOMAINS`
- `MEDIUM_COOKIE`

## Phase 2/3 后续可选增强

- 支持自定义 selector 等待。
- 支持滚动页面后再提取内容。
- 支持截图输出目录配置。
- 支持只返回可见文本或完整 HTML。
