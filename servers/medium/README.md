# medium server

Medium 专用 MCP server，提供独立的 Medium 搜索、抓取和浏览入口。

## 当前工具

### `search_medium_articles(query, max_results=10, provider="auto")`

搜索 Medium 文章。服务器会自动把查询限定到 `site:medium.com`，适合直接做
Medium 内容发现。

### `fetch_medium_url(url, timeout=60)`

抓取 Medium 页面正文。这个入口会自动使用通用浏览器头，并保留 Medium 专用 UA、client hints 和本地 cookie。

### `browser_fetch_medium(url, timeout=60, wait_until="domcontentloaded")`

用 Playwright 读取 Medium 页面，适合需要 JS 渲染或更复杂页面结构的场景。这里也会优先保留 Medium 专用 UA 和 cookie。

## 配置

常用环境变量：

- `MEDIUM_COOKIE`
- `HTTP_TIMEOUT`
- `BROWSER_TIMEOUT`
- `BROWSER_HEADLESS`
