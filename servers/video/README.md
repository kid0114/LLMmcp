# video MCP

`video MCP` 提供面向视频 transcript 的快速总结能力，当前聚焦：

- 解析 YouTube / Bilibili 视频 URL
- 对整段 transcript 做摘要
- 对带时间戳的 transcript segments 生成章节摘要

当前版本不直接抓取 YouTube/Bilibili 字幕，而是先把“视频字幕抓取”和“摘要逻辑”解耦。
这样可以先稳定 MCP 结构，再逐步接入不同平台的字幕来源。

## 工具

- `parse_video_url(url: str)`
- `summarize_video_transcript(transcript: str, url: str | None = None, title: str | None = None, max_points: int = 5, max_summary_sentences: int = 3)`
- `summarize_video_segments(segments: list[VideoTranscriptSegment], url: str | None = None, title: str | None = None, max_points: int = 5, max_summary_sentences: int = 3, chapter_window_seconds: int = 180)`

## 后续扩展

- `youtube_transcript MCP`：拉取字幕 / 自动字幕
- `bilibili_subtitle MCP`：拉取站内字幕或 ASR 字幕
- `audio_transcribe MCP`：对本地音视频做转写
- `video_stream MCP`：长任务流式回传转写和摘要进度
