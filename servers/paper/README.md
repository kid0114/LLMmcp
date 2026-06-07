# paper MCP

`paper MCP` 提供论文检索、元数据解析和 PDF 阅读能力，当前首版聚焦：

- `search_papers`：检索 arXiv / Crossref / OpenAlex 并返回结构化论文元数据。
- `trending_papers`：按 OpenAlex / arXiv / Hugging Face / ModelScope 的公开热度信号发现前沿论文和模型关联研究。
- `get_paper_metadata` / `resolve_paper_identifier`：按 DOI 或 arXiv ID 获取论文信息。
- `read_paper`：读取 arXiv ID、PDF URL 或 `LOCAL_FILE_ROOT` 内本地 PDF。
- `read_paper_sections`：按章节名从论文文本中提取片段。
- `extract_paper_citations`：从 `references` 段落提取引用行。
- `summarize_paper`：基于提取式启发生成快速要点。
- `compare_papers`：读取多篇论文并抽取高频关键词用于初步对比。

## 边界

- `trending_papers` 支持 `period=today|week|10d|14d|month|Nd`，也支持直接传 `days`。
- `sort="growth"` 是基于近窗口新近性和公开热度信号的增长近似排序，不是精确搜索量增幅。
- Google Scholar 没有稳定公开 API，当前不作为默认 provider。
- Hugging Face 当前走 `https://huggingface.co/api/papers`，返回论文条目的 upvotes 和发布时间等公开信号。
- ModelScope 当前走 `https://modelscope.cn/api/v1/papers`，返回论文条目的阅读、收藏和影响力等公开信号。
- Hugging Face 论文趋势查询复用 `huggingface MCP` 的内部查询函数，`paper MCP` 只负责转换为论文统一响应结构。
- ModelScope paper 会从 `ArxivUrl` / `PdfUrl` 反推 `arxiv_id` 和 `pdf_url`，并把 `ImpactScore`、收藏、阅读等信号写入 `score` / `signals`。
- 跨 Hugging Face / ModelScope 对比时优先按 `arxiv_id` 去重；窄主题查询可能需要先严格查，再在 prompt 中放宽到相邻关键词。
- Semantic Scholar API key 后续再接入。
- 扫描版 PDF OCR 依赖 `file_reader MCP` 后续增强。
- 当前摘要和对比不是 LLM 推理，只是确定性文本启发，适合作为本地模型进一步阅读前的预处理。

## 示例

```python
trending_papers(query="llm agent", period="today", max_results=10, sort="trending")
trending_papers(query="multimodal", period="week", max_results=14, sort="growth")
trending_papers(query="reasoning model", period="10d", max_results=10, provider="openalex", sort="citations")
trending_papers(query="coding model", period="month", max_results=14, provider="huggingface", sort="growth")
```
