from servers.video.server import (
    parse_video_url,
    summarize_video_segments,
    summarize_video_transcript,
)


def test_parse_youtube_watch_url() -> None:
    response = parse_video_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert response.platform == "youtube"
    assert response.video_id == "dQw4w9WgXcQ"
    assert response.canonical_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_parse_bilibili_video_url() -> None:
    response = parse_video_url("https://www.bilibili.com/video/BV1xx411c7mD")

    assert response.platform == "bilibili"
    assert response.video_id == "BV1xx411c7mD"
    assert response.canonical_url == "https://www.bilibili.com/video/BV1xx411c7mD"


def test_summarize_video_transcript_returns_points() -> None:
    response = summarize_video_transcript(
        transcript=(
            "今天这个视频主要讲如何把 MCP server 做成可复用组件。"
            "第一部分讲 server 边界，第二部分讲 transcript 摘要，"
            "第三部分讲 OpenAI-style tools 导出。"
        ),
        title="MCP Video Summary",
    )

    assert response.title == "MCP Video Summary"
    assert response.platform == "generic"
    assert response.transcript_characters > 0
    assert len(response.key_points) >= 1
    assert response.summary


def test_summarize_video_segments_returns_chapters() -> None:
    response = summarize_video_segments(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        segments=[
            {
                "start_seconds": 0,
                "end_seconds": 45,
                "text": "开头先介绍 MCP 的目标和为什么要拆成多个 server。",
            },
            {
                "start_seconds": 60,
                "end_seconds": 120,
                "text": "接着说明 transcript summary 如何支持长视频快速阅读。",
            },
            {
                "start_seconds": 220,
                "end_seconds": 260,
                "text": "最后讲到章节摘要和后续 YouTube 字幕抓取能力。",
            },
        ],
        chapter_window_seconds=180,
    )

    assert response.platform == "youtube"
    assert response.video_id == "dQw4w9WgXcQ"
    assert response.transcript_segments == 3
    assert response.estimated_duration_seconds == 260
    assert len(response.chapters) == 2
