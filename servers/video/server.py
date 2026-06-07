import re
from collections import Counter
from collections.abc import Iterable
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from mcp.server.fastmcp import FastMCP

from servers.video.schemas import (
    VideoChapterSummary,
    VideoPlatform,
    VideoSegmentSummaryRequest,
    VideoSourceResponse,
    VideoSummaryRequest,
    VideoSummaryResponse,
    VideoTranscriptSegment,
    VideoUrlRequest,
)
from shared.errors import MCPToolError
from shared.logging import get_logger

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-video")

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？；;])\s+|\n+")
_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{1,}")
_WHITESPACE_RE = re.compile(r"\s+")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
_BILIBILI_HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com", "b23.tv"}
_STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "but",
    "for",
    "from",
    "have",
    "into",
    "just",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "with",
    "一个",
    "一些",
    "这个",
    "这个视频",
    "这里",
    "我们",
    "你们",
    "他们",
    "然后",
    "因为",
    "所以",
    "就是",
    "如果",
    "可以",
    "需要",
}


class VideoError(MCPToolError):
    """Raised when video parsing or summarization fails."""


def _normalize_transcript(text: str) -> str:
    collapsed = _WHITESPACE_RE.sub(" ", text.strip())
    return collapsed


def _split_sentences(text: str) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(normalized)]
    sentences = [part for part in parts if part]
    if sentences:
        return sentences
    return [normalized]


def _tokens(text: str) -> list[str]:
    found = [token.lower() for token in _TOKEN_RE.findall(text)]
    return [token for token in found if token not in _STOPWORDS]


def _top_sentences(
    transcript: str, max_points: int, max_summary_sentences: int
) -> tuple[list[str], str]:
    sentences = _split_sentences(transcript)
    if not sentences:
        raise VideoError("Transcript is empty after normalization")

    frequencies = Counter(token for sentence in sentences for token in _tokens(sentence))
    scored: list[tuple[int, float, str]] = []
    for index, sentence in enumerate(sentences):
        sentence_tokens = _tokens(sentence)
        if sentence_tokens:
            score = sum(frequencies[token] for token in sentence_tokens) / (
                len(sentence_tokens) ** 0.5
            )
        else:
            score = 0.0
        scored.append((index, score, sentence))

    scored.sort(key=lambda item: (-item[1], item[0]))
    selected = scored[: max(max_points, max_summary_sentences)]
    selected.sort(key=lambda item: item[0])
    ordered_sentences = [item[2] for item in selected]
    key_points = ordered_sentences[:max_points]
    summary = " ".join(ordered_sentences[:max_summary_sentences])
    if not summary:
        summary = sentences[0]
    return key_points, summary


def _canonicalize_url(url: str) -> tuple[VideoPlatform, str | None, str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path
    query = parse_qs(parsed.query)

    if host in _YOUTUBE_HOSTS:
        if host == "youtu.be":
            video_id = path.strip("/") or None
        else:
            video_id = query.get("v", [None])[0]
            if not video_id and path.startswith("/shorts/"):
                video_id = path.split("/", maxsplit=2)[2]
        canonical = f"https://www.youtube.com/watch?v={video_id}" if video_id else url
        return "youtube", video_id, canonical

    if host in _BILIBILI_HOSTS:
        match = re.search(r"/video/(BV[0-9A-Za-z]+|av\d+)", path)
        video_id = match.group(1) if match else None
        canonical = f"https://www.bilibili.com/video/{video_id}" if video_id else url
        return "bilibili", video_id, canonical

    return "generic", None, url


def _chapter_summaries(
    segments: Iterable[VideoTranscriptSegment],
    chapter_window_seconds: int,
    max_summary_sentences: int,
) -> list[VideoChapterSummary]:
    buckets: dict[int, list[VideoTranscriptSegment]] = {}
    for segment in segments:
        bucket = int(segment.start_seconds // chapter_window_seconds)
        buckets.setdefault(bucket, []).append(segment)

    chapters: list[VideoChapterSummary] = []
    for bucket in sorted(buckets):
        chunk = buckets[bucket]
        chapter_text = " ".join(segment.text for segment in chunk)
        _, summary = _top_sentences(
            chapter_text,
            max_points=2,
            max_summary_sentences=max_summary_sentences,
        )
        chapters.append(
            VideoChapterSummary(
                start_seconds=chunk[0].start_seconds,
                end_seconds=chunk[-1].end_seconds,
                summary=summary,
            )
        )
    return chapters


def _response_from_transcript(
    transcript: str,
    url: str | None,
    title: str | None,
    max_points: int,
    max_summary_sentences: int,
    segments: list[VideoTranscriptSegment] | None = None,
    chapter_window_seconds: int = 180,
) -> VideoSummaryResponse:
    normalized = _normalize_transcript(transcript)
    key_points, summary = _top_sentences(
        normalized,
        max_points=max_points,
        max_summary_sentences=max_summary_sentences,
    )
    platform: VideoPlatform = "generic"
    video_id: str | None = None
    canonical_url: str | None = None
    if url:
        platform, video_id, canonical_url = _canonicalize_url(url)

    estimated_duration_seconds = segments[-1].end_seconds if segments else None
    chapters = []
    if segments:
        chapters = _chapter_summaries(
            segments,
            chapter_window_seconds,
            max_summary_sentences,
        )
    return VideoSummaryResponse(
        message="Summarized video transcript successfully",
        platform=platform,
        video_id=video_id,
        canonical_url=canonical_url,
        title=title,
        summary=summary,
        key_points=key_points,
        chapters=chapters,
        transcript_characters=len(normalized),
        transcript_segments=len(segments or []),
        estimated_duration_seconds=estimated_duration_seconds,
    )


@mcp.tool()
def parse_video_url(url: str) -> VideoSourceResponse:
    request = VideoUrlRequest(url=cast(Any, url))
    platform, video_id, canonical_url = _canonicalize_url(str(request.url))
    logger.info("parse_video_url called", extra={"url": str(request.url), "platform": platform})
    return VideoSourceResponse(
        message="Parsed video URL successfully",
        url=request.url,
        platform=platform,
        video_id=video_id,
        canonical_url=canonical_url,
    )


@mcp.tool()
def summarize_video_transcript(
    transcript: str,
    url: str | None = None,
    title: str | None = None,
    max_points: int = 5,
    max_summary_sentences: int = 3,
) -> VideoSummaryResponse:
    request = VideoSummaryRequest(
        transcript=transcript,
        url=cast(Any, url),
        title=title,
        max_points=max_points,
        max_summary_sentences=max_summary_sentences,
    )
    logger.info(
        "summarize_video_transcript called",
        extra={"url": str(request.url) if request.url else None, "title": request.title},
    )
    return _response_from_transcript(
        transcript=request.transcript,
        url=str(request.url) if request.url else None,
        title=request.title,
        max_points=request.max_points,
        max_summary_sentences=request.max_summary_sentences,
    )


@mcp.tool()
def summarize_video_segments(
    segments: list[VideoTranscriptSegment],
    url: str | None = None,
    title: str | None = None,
    max_points: int = 5,
    max_summary_sentences: int = 3,
    chapter_window_seconds: int = 180,
) -> VideoSummaryResponse:
    request = VideoSegmentSummaryRequest(
        segments=segments,
        url=cast(Any, url),
        title=title,
        max_points=max_points,
        max_summary_sentences=max_summary_sentences,
        chapter_window_seconds=chapter_window_seconds,
    )
    transcript = " ".join(segment.text for segment in request.segments)
    logger.info(
        "summarize_video_segments called",
        extra={
            "url": str(request.url) if request.url else None,
            "segments": len(request.segments),
            "title": request.title,
        },
    )
    return _response_from_transcript(
        transcript=transcript,
        url=str(request.url) if request.url else None,
        title=request.title,
        max_points=request.max_points,
        max_summary_sentences=request.max_summary_sentences,
        segments=request.segments,
        chapter_window_seconds=request.chapter_window_seconds,
    )


if __name__ == "__main__":
    mcp.run()
