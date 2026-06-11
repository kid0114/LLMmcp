# LLMmcp

LLMmcp 是一个简单、清晰、可扩展的 MCP 项目骨架。当前已实现十二个可运行 MCP Server：`search`、`fetch`、`browser`、`medium`、`local_file`、`github_search`、`time`、`file_reader`、`video`、`paper`、`modelscope`、`huggingface`。

## 当前阶段目标

- `search MCP`：搜索网页并返回结构化结果
- `fetch MCP`：抓取静态网页、Markdown 或普通 HTTP 文档
- `browser MCP`：用 Playwright 读取动态网页和 SPA 页面
- `medium MCP`：独立的 Medium 搜索、抓取和浏览入口
- `local_file MCP`：在受限根目录中浏览、读取和搜索本地文本文件
- `github_search MCP`：搜索 GitHub 仓库、模型项目、代码、issue 和 Trending 项目
- `time MCP`：当前时间、时区转换和相对时间解析
- `file_reader MCP`：PDF 文本提取、文本/混合文本文件读取、图片元信息读取和 OCR
- `video MCP`：解析视频 URL，并对 transcript / 字幕文本生成快速摘要与章节摘要
- `paper MCP`：检索论文元数据、查找前沿/热门论文和模型关联研究，读取 DOI / arXiv / URL / 本地 PDF
- `modelscope MCP`：查询 ModelScope 上公开可索引的 skill、dataset、model、paper、mcp 趋势资源
- `huggingface MCP`：查询 Hugging Face 上公开可索引的 paper、model、dataset、mcp 趋势资源
- 提供统一配置、权限检查、日志和基础测试

## 启动方式

默认使用 `stdio`，适合桌面端 MCP 插件直连。
如果要让手机或局域网客户端访问，把 `.env` 里的 `MCP_TRANSPORT` 改成 `streamable-http`，把 `HOST` 设成 `0.0.0.0`，并设置 `MCP_ALLOW_LAN=true`。
HTTP 模式下一个进程占用一个端口；如果同时跑多个 MCP server，需要给每个进程分配不同 `PORT`，或者后续用 gateway/profile server 聚合成一个入口。

## 联网请求策略

当前所有联网 server 共享一层基础浏览器风格 header，默认包含 `User-Agent`、`Accept`、`Accept-Language`、`Sec-Fetch-*`、`sec-ch-ua*` 等字段。

站点专用 header 会在这层基础上覆盖默认值：

- `medium` 保留自己的 `MEDIUM_COOKIE`、`Chrome/148` UA 和 client hints
- `fetch` 会在通用 header 基础上按站点追加专用 header
- `github_search`、`modelscope`、`huggingface`、`search` 的 HTTP 请求也走通用 header
- `browser` 的 Playwright context 复用同一套默认值，并对 Medium 保留 cookie 注入

## search MCP 说明

工具：`search_web(query: str, max_results: int = 5, provider: str = "auto")`

返回：

- `query`
- `results`
- `result.title`
- `result.url`
- `result.snippet`
- `result.source`

说明：

- `provider="brave"` 会强制使用 Brave Search
- `provider="ddgs"` 会强制使用 DuckDuckGo
- `provider="auto"` 时会使用 `SEARCH_PROVIDER` 环境变量；若环境变量也是 `auto`，则按当前回退策略执行
- Brave Search 请求会使用通用浏览器风格 header，避免裸请求特征过强

实现位置： [servers/search/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/search/server.py)

## fetch MCP 说明

工具：`fetch_url(url: str, timeout: int = 20)`

普通 URL 读取应优先调用 `fetch_url` tool，不要用 MCP `resources/read`
直接读取 `https://...` URL。fetch server 也提供
`fetch://url/{encoded_url}` 和 `fetch://url-b64/{encoded_url_b64}` resource
template 作为客户端误走 resources 时的兼容兜底。

返回：

- `url`
- `status_code`
- `title`
- `content`
- `content_length`

实现位置： [servers/fetch/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/fetch/server.py)

适用范围：静态网页、API 文本响应、Markdown、HTML 文档。
- `fetch_url` 会使用通用浏览器风格 header；如果目标站点有专用 header，专用值会覆盖通用值
## browser MCP 说明

工具：`browser_fetch(url: str, timeout: int = 30, wait_until: str = "networkidle")`

返回：

- `url`
- `final_url`
- `title`
- `content`
- `content_length`
- `screenshot_path`
- `status_code`

实现位置： [servers/browser/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/browser/server.py)

适用范围：需要 JS 渲染、SPA 页面、静态抓取拿不到正文的页面。
- `browser_fetch` 的 Playwright context 复用通用浏览器风格 header；Medium URL 会继续注入本地 `MEDIUM_COOKIE`

## medium MCP 说明

工具：

- `search_medium_articles(query: str, max_results: int = 10, provider: str = "auto")`
- `fetch_medium_url(url: str, timeout: int = 60)`
- `browser_fetch_medium(url: str, timeout: int = 60, wait_until: str = "domcontentloaded")`

说明：

- 这是独立的 Medium 专用通道，和通用 `fetch` / `browser` 分开。
- `search_medium_articles` 会自动加 `site:medium.com` 约束。
- `fetch_medium_url` 和 `browser_fetch_medium` 会使用本地 `MEDIUM_COOKIE`，并优先保留 Medium 自己的 UA / client hints。
- 访问 Medium 文章前，先把浏览器里的 Medium `cookie` 写入 `.env`。
- 可用 `python -m llmmcp set-medium-cookie` 从剪贴板更新 `.env`。

## local_file MCP 说明

工具：

- `read_local_file(path: str, max_chars: int = 20000, offset: int = 0)`
- `list_local_files(path: str = ".", max_entries: int = 100)`
- `stat_local_file(path: str)`
- `glob_local_files(pattern: str, path: str = ".", max_results: int = 100)`
- `search_local_files(query: str, path: str = ".", include_glob: str | None = None, max_results: int = 50, max_file_chars: int = 200000)`

返回：

- `path`
- `absolute_path`
- `content`
- `content_length`
- `offset`
- `bytes_size`
- `truncated`

实现位置： [servers/local_file/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/local_file/server.py)

适用范围：读取项目内文档、配置、代码片段。默认限制在 `LOCAL_FILE_ROOT` 范围内。

## github_search MCP 说明

工具：

- `github_search_repositories(query: str, max_results: int = 5, sort: str = "best-match")`
- `github_search_model_repositories(query: str, max_results: int = 10, sort: str = "stars", language: str | None = None)`
- `github_search_code(query: str, max_results: int = 5)`
- `github_search_issues(query: str, max_results: int = 5, sort: str = "best-match")`
- `github_trending_repositories(since: str = "daily", language: str | None = None, max_results: int = 15)`

实现位置： [servers/github_search/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/github_search/server.py)

适用范围：查仓库、模型项目、代码搜索、issue 检索和 GitHub Trending 项目。
`GITHUB_TOKEN` 可选，不配置也能用，但 API 搜索会受匿名限流影响；
Trending 抓取 GitHub 页面，不需要 token。
如果 GitHub Search API 返回 rate limit，优先配置 `GITHUB_TOKEN`；不要把 `browser_fetch`
当作通用替代，除非用户明确要查看某个具体 GitHub 页面。
GitHub API / Trending 请求也会走通用浏览器风格 header，再叠加 GitHub 自己的 `Accept` / token 头。

## time MCP 说明

工具：

- `get_current_time(timezone: str = "UTC")`
- `convert_time(datetime_text: str, from_timezone: str = "UTC", to_timezone: str = "UTC")`
- `parse_relative_time(expression: str, timezone: str = "UTC", base_datetime: str | None = None)`

实现位置： [servers/time/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/time/server.py)

适用范围：获取当前时间、处理 IANA 时区转换、解析常用相对时间表达式，例如 `in 3 days`、
`2 hours ago`、`明天`、`3天后`。

## file_reader MCP 说明

工具：

- `classify_readable_file(path: str)`
- `read_text_file(path: str, max_chars: int = 20000, offset: int = 0)`
- `read_mixed_text_file(path: str, max_chars: int = 20000, offset: int = 0)`
- `read_pdf_file(path: str, max_chars: int = 20000, max_pages: int = 20)`
- `inspect_image_file(path: str)`
- `ocr_image_file(path: str, language: str = "eng", max_chars: int = 20000)`

实现位置： [servers/file_reader/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/file_reader/server.py)

适用范围：判断本地文件读取方式，读取代码、配置、日志、CSV、Markdown、HTML、XML、SVG、
Jupyter Notebook 等文本内容，读取 PDF 文本、提取图片元信息、对图片执行 OCR。PDF 文本提取依赖
`pypdf`，图片 OCR 依赖 `pytesseract` 和系统 `tesseract` 二进制。

## video MCP 说明

工具：

- `parse_video_url(url: str)`
- `summarize_video_transcript(transcript: str, url: str | None = None, title: str | None = None, max_points: int = 5, max_summary_sentences: int = 3)`
- `summarize_video_segments(segments: list[VideoTranscriptSegment], url: str | None = None, title: str | None = None, max_points: int = 5, max_summary_sentences: int = 3, chapter_window_seconds: int = 180)`

实现位置： [servers/video/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/video/server.py)

适用范围：对 YouTube、Bilibili 或通用视频的 transcript 文本做快速阅读摘要。当前版本先聚焦 transcript 输入，
不直接负责平台字幕抓取。

## paper MCP 说明

工具：

- `search_papers(query: str, max_results: int = 5, provider: str = "auto", author: str | None = None, title: str | None = None, doi: str | None = None, arxiv_id: str | None = None, year_from: int | None = None, year_to: int | None = None, venue: str | None = None)`
- `trending_papers(query: str = "large language model", max_results: int = 10, provider: str = "auto", sort: str = "trending", period: str | None = None, days: int = 30)`
- `get_paper_metadata(identifier: str, identifier_type: str = "auto")`
- `resolve_paper_identifier(identifier: str, identifier_type: str = "auto")`
- `read_paper(identifier: str, identifier_type: str = "auto", max_chars: int = 20000, offset: int = 0, max_pages: int = 30)`
- `read_paper_sections(identifier: str, section: str, identifier_type: str = "auto", max_chars: int = 20000, offset: int = 0, max_pages: int = 30)`
- `extract_paper_citations(identifier: str, identifier_type: str = "auto", max_chars: int = 80000, offset: int = 0, max_pages: int = 100)`
- `summarize_paper(identifier: str, identifier_type: str = "auto", max_chars: int = 20000, offset: int = 0, max_pages: int = 30, max_points: int = 6)`
- `compare_papers(identifiers: list[str], identifier_type: str = "auto", max_chars_per_paper: int = 8000)`

实现位置： [servers/paper/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/paper/server.py)

适用范围：检索 arXiv / Crossref / OpenAlex 元数据，按 OpenAlex 近期高引、arXiv 近期提交、
Hugging Face / ModelScope 论文页公开热度信号发现前沿研究线索，并读取 arXiv ID、PDF URL 或 `LOCAL_FILE_ROOT` 内的本地 PDF。
当前摘要和对比是确定性文本启发，适合作为本地模型进一步阅读前的预处理。

`trending_papers` 说明：

- `provider="openalex"`：按近期发表窗口内的 citation count 或 publication date 排序，适合找高引/新近论文。
- `provider="arxiv"`：按近期提交时间排序，适合跟踪最新预印本。
- `provider="huggingface"`：返回 Hugging Face 论文页的论文条目及 upvotes / publishedAt 等公开信号。
- `provider="modelscope"`：返回 ModelScope 论文页的论文条目及 ViewCount / FavoriteCount / ImpactScore / PublishDate 等信号。
- `provider="auto"`：合并上述公开来源并按可用热度信号排序。
- `period` 支持 `today`、`week`、`10d`、`14d`、`month` 以及通用 `Nd`；也可以直接传 `days`。
- `sort="growth"` 表示近时间窗口内的增长近似排序，不是精确搜索指数。
- Hugging Face 论文趋势逻辑由 `huggingface MCP` 和 `paper MCP` 共享，避免两套解析 / 排序行为漂移。
- ModelScope paper 结果会从 arXiv URL 反推 `arxiv_id` 和 `pdf_url`，并把 `ImpactScore`、收藏、阅读等公开信号纳入 `score` / `signals`。
- 跨源对比建议按 `arxiv_id` 去重；如果查询词很窄导致某源返回 0，可在 prompt 中放宽到相邻关键词后再合并比较。
- Google Scholar 没有稳定公开 API，当前不作为默认 provider；建议通过 OpenAlex / Crossref / Semantic Scholar 后续 API 覆盖引用信号。

示例：

```python
trending_papers(query="llm agent", period="today", max_results=10, sort="trending")
trending_papers(query="multimodal", period="week", max_results=14, sort="growth")
trending_papers(query="reasoning model", period="10d", max_results=10, provider="openalex", sort="citations")
trending_papers(query="coding model", period="month", max_results=14, provider="huggingface", sort="growth")
```

## modelscope MCP 说明

工具：

- `modelscope_trending_resources(resource_type: str, query: str | None = None, max_results: int = 10, sort: str = "trending", period: str | None = None, days: int = 30)`

说明：

- `resource_type` 当前支持 `skill`、`dataset`、`model`、`paper`、`mcp`
- `period` 支持 `today`、`week`、`10d`、`14d`、`month` 以及通用 `Nd`
- `skill` / `dataset` / `model` 当前走 `openapi/v1`
- `paper` 当前走 `api/v1/papers`
- `mcp` 当前按浏览器抓包走 ModelScope MCP 广场接口 `PUT api/v1/dolphin/mcpServers`，默认不需要 cookie，返回 ViewCount / Stars / CallVolume 等公开信号；仅当接口被 ModelScope WAF 拦截时，可通过 `MODELSCOPE_MCP_COOKIE` 提供浏览器会话 cookie，`csrf_token` 会自动映射为 `X-CSRF-TOKEN`

示例：

```python
modelscope_trending_resources(resource_type="skill", query="agent", period="week", max_results=10, sort="trending")
modelscope_trending_resources(resource_type="dataset", query="llm", period="month", max_results=14, sort="downloads")
modelscope_trending_resources(resource_type="model", query="multimodal", period="10d", max_results=10, sort="likes")
modelscope_trending_resources(resource_type="paper", query="reasoning", period="week", max_results=10, sort="impact")
modelscope_trending_resources(resource_type="mcp", query="browser", period="month", max_results=10, sort="views")
modelscope_trending_resources(resource_type="mcp", query="@modelcontextprotocol/fetch", max_results=5, sort="views")
modelscope_trending_resources(resource_type="mcp", query="leetcode-mcp-server", max_results=5, sort="views")
```

## huggingface MCP 说明

工具：

- `huggingface_trending_resources(resource_type: str, query: str | None = None, max_results: int = 10, sort: str = "trending", period: str | None = None, days: int = 30)`

说明：

- `resource_type` 当前支持 `paper`、`model`、`dataset`、`mcp`
- `period` 支持 `today`、`week`、`10d`、`14d`、`month` 以及通用 `Nd`
- `model` 走 `https://huggingface.co/api/models`
- `dataset` 走 `https://huggingface.co/api/datasets`
- `paper` 走 `https://huggingface.co/api/papers`
- `mcp` 走 `https://huggingface.co/api/spaces`，返回带 MCP / Model Context Protocol 语义的 Spaces；Hugging Face 的 MCP 形态主要是 MCP-enabled Spaces，不是独立 MCP 广场
- 当前不提供 `skill` 资源类型，因为 Hugging Face 没有对等公开索引

示例：

```python
huggingface_trending_resources(resource_type="paper", query="llm", period="week", max_results=10, sort="trending")
huggingface_trending_resources(resource_type="dataset", query="instruction", period="month", max_results=14, sort="downloads")
huggingface_trending_resources(resource_type="model", query="multimodal", period="10d", max_results=10, sort="likes")
huggingface_trending_resources(resource_type="mcp", query="web-scraper", period="month", max_results=10, sort="likes")
```

## 为什么 fetch 和 browser 分开

- `fetch` 基于 `httpx`，更轻、更快，适合普通静态内容读取。
- `browser` 基于 Playwright，成本更高，但能处理前端渲染页面。
- 分开后更容易控制依赖、性能和权限边界，也避免把简单需求强行走浏览器流程。

## 安装方法

```bash
conda activate mcp-llm
make install
cp .env.example .env
```

默认建议保持 `.env` 中的 `SEARCH_PROVIDER=ddgs`。需要时可在工具调用里显式传 `provider="brave"` 强制切换到 Brave Search。

## 如何安装 Playwright browser 依赖

安装 Python 包后，继续执行：

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python -m playwright install chromium
```

## 如何运行 search MCP

```bash
python -m llmmcp run search
```

## 如何运行 fetch MCP

```bash
python -m llmmcp run fetch
```

## 如何运行 browser MCP

```bash
python -m llmmcp run browser
```

## 如何运行 medium MCP

```bash
python -m llmmcp run medium
```

## 如何运行 local_file MCP

```bash
python -m llmmcp run local-file
```

## 如何运行 github_search MCP

```bash
python -m llmmcp run github-search
```

## 如何运行 time MCP

```bash
python -m llmmcp run time
```

## 如何运行 file_reader MCP

```bash
python -m llmmcp run file-reader
```

## 如何运行 video MCP

```bash
python -m llmmcp run video
```

## 如何运行 paper MCP

```bash
python -m llmmcp run paper
```

## 如何运行 modelscope MCP

```bash
python -m llmmcp run modelscope
```

`resource_type="mcp"` 默认不需要 cookie；如果遇到 ModelScope WAF 拦截，可用真实浏览器自动导出 cookie 到 `.env` 作为兜底：

```bash
python -m llmmcp export-modelscope-cookie
```

## 如何运行 huggingface MCP

```bash
python -m llmmcp run huggingface
```

## 健康检查

```bash
python -m llmmcp health
```

## 如何接入 MCP 客户端

示例配置见 [configs/mcp.example.json](/Users/lny/PycharmProjects/LLMmcp/configs/mcp.example.json)。

```json
{
  "mcpServers": {
    "llmmcp-search": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_search.py"],
      "cwd": "/Users/lny/PycharmProjects/LLMmcp"
    },
    "llmmcp-fetch": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_fetch.py"],
      "cwd": "/Users/lny/PycharmProjects/LLMmcp"
    },
    "llmmcp-browser": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_browser.py"],
      "cwd": "/Users/lny/PycharmProjects/LLMmcp"
    },
    "llmmcp-local-file": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_local_file.py"],
      "cwd": "/Users/lny/PycharmProjects/LLMmcp"
    },
    "llmmcp-github-search": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_github_search.py"],
      "cwd": "/Users/lny/PycharmProjects/LLMmcp"
    },
    "llmmcp-time": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_time.py"],
      "cwd": "/Users/lny/PycharmProjects/LLMmcp"
    },
    "llmmcp-file-reader": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_file_reader.py"],
      "cwd": "/Users/lny/PycharmProjects/LLMmcp"
    },
    "llmmcp-video": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_video.py"],
      "cwd": "/Users/lny/PycharmProjects/LLMmcp"
    },
    "llmmcp-paper": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_paper.py"],
      "cwd": "/Users/lny/PycharmProjects/LLMmcp"
    },
    "llmmcp-modelscope": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_modelscope.py"],
      "cwd": "/Users/lny/PycharmProjects/LLMmcp"
    },
    "llmmcp-huggingface": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_huggingface.py"],
      "cwd": "/Users/lny/PycharmProjects/LLMmcp"
    }
  }
}
```

## 如何导出 OpenAI-style tools

如果你要对接 MTPLX 这类支持 OpenAI-style `tools` / `tool_choice` 的服务端，可以直接导出同一套能力的 tool 定义：

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python scripts/export_openai_tools.py
```

当前导出的工具为：

- `search_web`
- `fetch_url`
- `browser_fetch`

执行单个 tool 的本地调试示例：

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python scripts/run_openai_tool.py search_web '{"query":"OpenAI MCP","max_results":5,"provider":"brave"}'
```

实现位置：

- [web_tools.py](/Users/lny/PycharmProjects/LLMmcp/openai_tools/web_tools.py)

## 如何新增 MCP Server

参考 [docs/add_new_server.md](/Users/lny/PycharmProjects/LLMmcp/docs/add_new_server.md)。

## 后续路线

- Phase 1：search / fetch / browser / 基础配置 / 基础测试
- Phase 2：local_file MCP / github_search MCP
- Phase 3：paper_search MCP / paper_reader MCP / video MCP / git_repo MCP / memory MCP
- Phase 4：rag_search MCP / Qdrant / 本地知识库
- Phase 5：local_router MCP / 本地模型状态检查 / MTPLX / oMLX / LM Studio 适配
