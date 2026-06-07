# local_file server

在 `LOCAL_FILE_ROOT` 范围内安全读取本地文本文件，给本地模型提供项目文件上下文。

## 当前工具

### `read_local_file(path, max_chars=20000, offset=0)`

读取一个已知路径的文本文件，支持 offset 分段读取。

返回：

- `path`
- `absolute_path`
- `content`
- `content_length`
- `offset`
- `bytes_size`
- `truncated`

说明：

- `path` 可以是相对 `LOCAL_FILE_ROOT` 的路径，也可以是位于 `LOCAL_FILE_ROOT` 内的绝对路径。
- 文件内容按 UTF-8 读取，无法解码的字符会被替换。
- 当文件内容超过 `max_chars` 时会截断，并返回 `truncated=true`。
- `offset` 用于从指定字符位置开始读取大文件。
- 路径不能逃逸出 `LOCAL_FILE_ROOT`。

### `list_local_files(path=".", max_entries=100)`

列出目录内容，让模型可以先探索项目结构，再决定读取哪些文件。

返回：

- `path`
- `entries`
- `entry.name`
- `entry.path`
- `entry.kind`
- `entry.size`

### `stat_local_file(path)`

查看文件或目录元信息，用于判断路径是否存在、是否可读、是文件还是目录。

返回：

- `path`
- `absolute_path`
- `exists`
- `kind`
- `size`
- `modified_at`

### `glob_local_files(pattern, path=".", max_results=100)`

按 glob 模式查找文件，例如 `*.py`、`docs/*.md`、`servers/*/README.md`。

返回：

- `path`
- `pattern`
- `results`
- `total_results`
- `truncated`

### `search_local_files(query, path=".", include_glob=None, max_results=50, max_file_chars=200000)`

在本地文本文件中搜索关键词，适合让模型快速定位代码、配置和文档片段。

返回：

- `path`
- `query`
- `include_glob`
- `results`
- `result.path`
- `result.line_number`
- `result.line`
- `total_results`
- `truncated`

说明：

- 搜索大小写不敏感。
- `include_glob` 可限制文件模式，例如 `*.py`、`*.md`。
- 超过 `max_file_chars` 的文件会跳过，避免大文件拖慢本地模型。

## Phase 2 后续可选增强

- 支持排除目录，例如 `.git`、`__pycache__`、`.venv`。
- 搜索结果增加上下文行。
- 支持正则搜索。
- OpenAI-style tools 导出。
