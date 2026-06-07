# file_reader server

在 `LOCAL_FILE_ROOT` 范围内读取 PDF、图片、文本型文件和混合文本文件，给本地模型补充文档阅读能力。

## 当前工具

### `classify_readable_file(path)`

判断文件应该如何读取，避免模型盲目调用错误工具。

返回：

- `path`
- `absolute_path`
- `extension`
- `media_type`
- `size`
- `category`
- `readable`
- `reader`
- `text_kind`
- `mixed_kind`
- `notes`

分类：

- `text`：代码、配置、日志、CSV、SQL 等纯文本可读文件，建议使用 `read_text_file`。
- `mixed`：Markdown、HTML、XML、SVG、Jupyter Notebook 等文本可读但包含结构/嵌入内容的文件，建议使用 `read_mixed_text_file`。
- `document`：PDF，建议使用 `read_pdf_file`。
- `image`：图片，建议使用 `inspect_image_file` 或 `ocr_image_file`。
- `binary`：当前没有可用文本读取器。

### `read_text_file(path, max_chars=20000, offset=0)`

读取纯文本可读文件，也可以直接读取混合文本文件的原始文本。

返回：

- `path`
- `absolute_path`
- `category`
- `text_kind`
- `mixed_kind`
- `content`
- `content_length`
- `offset`
- `bytes_size`
- `truncated`

### `read_mixed_text_file(path, max_chars=20000, offset=0)`

读取混合文本文件，并尽量抽取适合模型理解的正文。

支持：

- Markdown：保留原始 Markdown 文本。
- HTML / XML / SVG：去除脚本和样式后抽取可见文本。
- Jupyter Notebook：抽取 cell 类型、源码和文本输出。

返回字段同 `read_text_file`。

### `read_pdf_file(path, max_chars=20000, max_pages=20)`

读取 PDF 文本内容。

返回：

- `path`
- `absolute_path`
- `page_count`
- `pages_read`
- `content`
- `content_length`
- `truncated`

说明：

- 依赖 `pypdf`。
- 对扫描版 PDF，如果页面本身没有文本层，结果可能为空。
- `max_pages` 和 `max_chars` 用于控制大文件读取成本。

### `inspect_image_file(path)`

读取图片元信息。

返回：

- `path`
- `absolute_path`
- `format`
- `mode`
- `width`
- `height`
- `has_alpha`
- `exif`

### `ocr_image_file(path, language="eng", max_chars=20000)`

对图片执行 OCR。

返回：

- `path`
- `absolute_path`
- `language`
- `content`
- `content_length`
- `truncated`

说明：

- 优先使用 `rapidocr-onnxruntime`。
- 如果 `RapidOCR` 不可用或失败，会回退到 `pytesseract` + 系统 `tesseract`。
- 当前适合静态图片 OCR，不负责复杂版面还原。

## Phase 3 后续可选增强

- PDF 按页返回结构化文本。
- 扫描版 PDF 转图片后 OCR。
- DOCX / PPTX / XLSX 阅读。
- 图片区域 OCR 和表格 OCR。
