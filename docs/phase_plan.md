# Phase Plan

## Phase 1

- search MCP
  - async search_web
  - Brave Search 使用 async HTTP
  - DDGS 同步库使用 asyncio.to_thread 隔离
- fetch MCP
  - async fetch_url
  - 使用 httpx.AsyncClient
- browser MCP
  - async browser_fetch
  - 使用 Playwright Async API
  - status_code 字段区分 HTTP 状态和响应状态
- 基础配置
- 基础测试
- 异步适配
  - 避免 MCP asyncio loop 中运行同步 Playwright
  - 避免 fetch/search 阻塞事件循环
  - 待补：browser_fetch 截图路径唯一化
  - 待补：browser_fetch 并发限制 / semaphore

## Phase 2

- local_file MCP
  - read_local_file
  - list_local_files
  - stat_local_file
  - glob_local_files
  - search_local_files
  - read_local_file offset 分段读取
  - 待补：OpenAI-style tools 导出
- github_search MCP
  - github_search_repositories
  - github_search_model_repositories
  - github_search_code
  - github_search_issues
  - github_trending_repositories
  - 待补：server 行为测试覆盖
  - 待补：OpenAI-style tools 导出

## Phase 3

- paper_search MCP
  - search_papers
  - get_paper_metadata
  - resolve_paper_identifier
  - 目标支持 arXiv / Semantic Scholar / Crossref / OpenAlex
  - 查询条件支持 keyword、author、title、doi、arxiv_id、year_range、venue、领域标签
  - 返回结构化字段：title、authors、abstract、year、venue、doi、arxiv_id、url、pdf_url、citation_count、source
  - 结果去重：优先 DOI，其次 arXiv ID，其次标题归一化
  - provider 目标使用 async HTTP，外部 API 失败时返回分 provider 错误
  - 已实现：arXiv / Crossref / OpenAlex 首版同步 HTTP 检索
  - 待补：async HTTP provider
  - 待补：Semantic Scholar API key 配置
  - 待补：OpenAI-style tools 导出
- paper_reader MCP
  - read_paper
  - read_paper_sections
  - summarize_paper
  - extract_paper_citations
  - compare_papers
  - 输入支持 DOI / arXiv ID / URL / 本地 PDF 路径
  - URL / PDF 下载和 PDF 文本提取首版内置实现，后续可与 fetch / file_reader MCP 解耦复用
  - 结构化解析：abstract、introduction、method、experiments、results、limitations、references
  - 支持 offset / section 分段读取，避免长论文一次性塞满上下文
  - 输出保留页码、章节名、引用标记，便于追溯原文
  - 已实现：arXiv ID / URL / 本地 PDF 读取、章节切分、引用提取、启发式摘要、论文关键词对比
  - 待补：DOI 到全文 PDF 的可靠解析
  - 扫描版论文 OCR 依赖 file_reader 的扫描版 PDF OCR 能力
  - 待补：表格 / 公式 / 图注提取
  - 待补：引用网络和相似论文推荐
  - 待补：OpenAI-style tools 导出
- file_reader MCP
  - read_pdf_file
  - inspect_image_file
  - ocr_image_file
  - 待补：扫描版 PDF OCR
  - 待补：DOCX / PPTX / XLSX 阅读
- video MCP
  - parse_video_url
  - summarize_video_transcript
  - summarize_video_segments
  - 先支持 transcript / subtitle 输入
  - YouTube / Bilibili 字幕抓取后置解耦
- git_repo MCP
  - git_status
  - git_diff
  - git_log
  - git_show
  - git_branch
  - 只读优先，写操作后置
- memory MCP
  - 项目长期记忆
  - 决策记录
  - 用户偏好
- time MCP
  - get_current_time
  - convert_time
  - parse_relative_time
  - 待补：OpenAI-style tools 导出

## Phase 4

- rag_search MCP
- Qdrant
- 本地知识库
- database MCP
  - SQLite 只读查询
  - PostgreSQL 只读查询
  - schema inspection
- doc_search MCP
  - 官方文档搜索
  - API 文档搜索
  - 本地 docs / README 聚合搜索
- github_context MCP
  - github_get_repository
  - github_get_file
  - github_list_pull_requests
  - github_get_pull_request
  - read-only mode

## Phase 5

- local_router MCP
- 本地模型状态检查
- MTPLX / oMLX / LM Studio 适配
- mcp_registry MCP
  - MCP server 发现
  - MCP server 推荐
  - 本地 MCP 配置检查
- monitoring MCP
  - 本地服务健康检查
  - 日志搜索
  - 简单错误聚合

## Backlog / 暂缓

- browser_fetch 并发安全增强
  - 截图路径使用唯一文件名
  - 浏览器实例并发限制
  - 可配置截图目录

- write_github MCP
  - 创建 issue / PR / comment
  - 需要权限边界和确认机制
- shell_command MCP
  - 命令执行风险高
  - 只适合作为受限白名单工具
- video_stream MCP
  - 长视频转写 / 摘要流式回传
  - 依赖字幕抓取或本地 ASR，后置
- cloud_deploy MCP
  - 部署、云资源、支付相关操作后置
- browser_automation MCP
  - 点击、填表、登录流程后置
