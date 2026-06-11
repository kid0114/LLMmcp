# github_search server

提供 GitHub 只读检索能力，用于查仓库、模型项目、代码、issue 和 Trending 项目。

## 当前工具

### `github_search_repositories(query, max_results=5, sort="best-match")`

搜索 GitHub 仓库。

参数：

- `query`：搜索关键词，不能为空。
- `max_results`：返回结果数量，范围 `1..20`。
- `sort`：排序方式，可选 `best-match`、`stars`、`updated`。

返回：

- `query`
- `results`
- `result.name`
- `result.full_name`
- `result.url`
- `result.description`
- `result.stars`
- `result.language`
- `total_results`

### `github_search_model_repositories(query, max_results=10, sort="stars", language=None)`

按关键字搜索模型相关仓库。

`github_search_model_repositories` 会自动把关键词限定到 LLM、foundation model、
embedding、transformer 等模型相关语境，适合查 Qwen、Llama、embedding、reranker
这类模型项目。

参数：

- `query`：模型或任务关键词，例如 `qwen`、`llama`、`embedding`、`reranker`。
- `max_results`：返回结果数量，范围 `1..20`。
- `sort`：排序方式，可选 `best-match`、`stars`、`updated`。
- `language`：可选语言过滤，例如 `Python`、`TypeScript`。

返回：

- `query`
- `resolved_query`
- `language`
- `results`
- `total_results`

### `github_search_code(query, max_results=5)`

搜索 GitHub 代码。

返回：

- `query`
- `results`
- `result.name`
- `result.path`
- `result.repository`
- `result.url`
- `result.sha`
- `total_results`

### `github_search_issues(query, max_results=5, sort="best-match")`

搜索 GitHub issue / PR 结果。

返回：

- `query`
- `results`
- `result.title`
- `result.url`
- `result.repository`
- `result.state`
- `result.number`
- `total_results`

### `github_trending_repositories(since="daily", language=None, max_results=15)`

抓取 GitHub Trending 页面，查询 daily / weekly / monthly 趋势仓库。

参数：

- `since`：趋势周期，可选 `daily`、`weekly`、`monthly`。
- `language`：可选语言 slug，例如 `python`、`typescript`。
- `max_results`：返回结果数量，范围 `1..25`。

返回：

- `since`
- `language`
- `results`
- `result.rank`
- `result.name`
- `result.full_name`
- `result.url`
- `result.description`
- `result.language`
- `result.total_stars`
- `result.forks`
- `result.stars_period`
- `result.period`
- `result.source`
- `total_results`

`github_trending_repositories` 抓取 GitHub Trending 页面，可用于查询 daily / weekly /
monthly 趋势仓库。该功能免费且不需要 `GITHUB_TOKEN`，但依赖 GitHub 网页结构。

## 配置

常用环境变量：

- `GITHUB_TOKEN`
- `HTTP_TIMEOUT`

说明：

- `GITHUB_TOKEN` 可选，不配置也能使用 GitHub API，但匿名限流更严格。
- Trending 抓 GitHub 网页，不需要 token。
- GitHub API 和 Trending 请求都会先使用通用浏览器风格 header，再叠加 GitHub 自己的 `Accept` / token 头。
- 如果 GitHub Search API 返回 rate limit，优先配置 `GITHUB_TOKEN`；不要把 `browser_fetch` 当作通用替代，除非用户明确要查看某个具体 GitHub 页面。
- 当前工具全部是只读能力，不创建 issue、不评论、不 push、不修改仓库。

## Phase 2 待补工具

- `github_get_repository(owner, repo)`：读取单个仓库详情。
- `github_get_file(owner, repo, path, ref=None)`：读取仓库内文本文件。
- server 行为测试覆盖。
- OpenAI-style tools 导出。
