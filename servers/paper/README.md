# paper MCP

`paper MCP` 提供论文检索、元数据解析和 PDF 阅读能力，当前首版聚焦：

- `search_papers`：检索 arXiv / Crossref / OpenAlex 并返回结构化论文元数据。
- `get_paper_metadata` / `resolve_paper_identifier`：按 DOI 或 arXiv ID 获取论文信息。
- `read_paper`：读取 arXiv ID、PDF URL 或 `LOCAL_FILE_ROOT` 内本地 PDF。
- `read_paper_sections`：按章节名从论文文本中提取片段。
- `extract_paper_citations`：从 `references` 段落提取引用行。
- `summarize_paper`：基于提取式启发生成快速要点。
- `compare_papers`：读取多篇论文并抽取高频关键词用于初步对比。

## 边界

- Semantic Scholar API key 后续再接入。
- 扫描版 PDF OCR 依赖 `file_reader MCP` 后续增强。
- 当前摘要和对比不是 LLM 推理，只是确定性文本启发，适合作为本地模型进一步阅读前的预处理。
