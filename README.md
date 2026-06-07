# LLMmcp

LLMmcp 是一个简单、清晰、可扩展的 MCP 项目骨架。当前已实现九个可运行 MCP Server：`search`、`fetch`、`browser`、`local_file`、`github_search`、`time`、`file_reader`、`video`、`paper`。

## 当前阶段目标

- `search MCP`：搜索网页并返回结构化结果
- `fetch MCP`：抓取静态网页、Markdown 或普通 HTTP 文档
- `browser MCP`：用 Playwright 读取动态网页和 SPA 页面
- `local_file MCP`：在受限根目录中浏览、读取和搜索本地文本文件
- `github_search MCP`：搜索 GitHub 仓库、模型项目、代码、issue 和 Trending 项目
- `time MCP`：当前时间、时区转换和相对时间解析
- `file_reader MCP`：PDF 文本提取、图片元信息读取和 OCR
- `video MCP`：解析视频 URL，并对 transcript / 字幕文本生成快速摘要与章节摘要
- `paper MCP`：检索论文元数据，读取 DOI / arXiv / URL / 本地 PDF
- 提供统一配置、权限检查、日志和基础测试

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

实现位置： [servers/search/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/search/server.py)

## fetch MCP 说明

工具：`fetch_url(url: str, timeout: int = 20)`

返回：

- `url`
- `status_code`
- `title`
- `content`
- `content_length`

实现位置： [servers/fetch/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/fetch/server.py)

适用范围：静态网页、API 文本响应、Markdown、HTML 文档。

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

- `read_pdf_file(path: str, max_chars: int = 20000, max_pages: int = 20)`
- `inspect_image_file(path: str)`
- `ocr_image_file(path: str, language: str = "eng", max_chars: int = 20000)`

实现位置： [servers/file_reader/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/file_reader/server.py)

适用范围：读取 PDF 文本、提取图片元信息、对图片执行 OCR。PDF 文本提取依赖 `pypdf`，
图片 OCR 依赖 `pytesseract` 和系统 `tesseract` 二进制。

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
- `get_paper_metadata(identifier: str, identifier_type: str = "auto")`
- `resolve_paper_identifier(identifier: str, identifier_type: str = "auto")`
- `read_paper(identifier: str, identifier_type: str = "auto", max_chars: int = 20000, offset: int = 0, max_pages: int = 30)`
- `read_paper_sections(identifier: str, section: str, identifier_type: str = "auto", max_chars: int = 20000, offset: int = 0, max_pages: int = 30)`
- `extract_paper_citations(identifier: str, identifier_type: str = "auto", max_chars: int = 80000, offset: int = 0, max_pages: int = 100)`
- `summarize_paper(identifier: str, identifier_type: str = "auto", max_chars: int = 20000, offset: int = 0, max_pages: int = 30, max_points: int = 6)`
- `compare_papers(identifiers: list[str], identifier_type: str = "auto", max_chars_per_paper: int = 8000)`

实现位置： [servers/paper/server.py](/Users/lny/PycharmProjects/LLMmcp/servers/paper/server.py)

适用范围：检索 arXiv / Crossref / OpenAlex 元数据，读取 arXiv ID、PDF URL 或 `LOCAL_FILE_ROOT` 内的本地 PDF。
当前摘要和对比是确定性文本启发，适合作为本地模型进一步阅读前的预处理。

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
make run-search
```

## 如何运行 fetch MCP

```bash
make run-fetch
```

## 如何运行 browser MCP

```bash
make run-browser
```

## 如何运行 local_file MCP

```bash
make run-local-file
```

## 如何运行 github_search MCP

```bash
make run-github-search
```

## 如何运行 time MCP

```bash
make run-time
```

## 如何运行 file_reader MCP

```bash
make run-file-reader
```

## 如何运行 video MCP

```bash
make run-video
```

## 如何运行 paper MCP

```bash
make run-paper
```

## 健康检查

```bash
make health
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
    "llmmcp-video": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python",
      "args": ["scripts/run_video.py"],
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
