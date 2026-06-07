# file_reader server

在 `LOCAL_FILE_ROOT` 范围内读取 PDF 和图片内容，给本地模型补充文档阅读能力。

## 当前工具

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
