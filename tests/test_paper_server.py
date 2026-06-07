from pathlib import Path

import pytest

from servers.huggingface.schemas import HuggingFaceResourceResult, HuggingFaceTrendingResponse
from servers.modelscope.schemas import ModelScopeResourceResult
from servers.paper.schemas import PaperResult, TrendingPaperResult
from servers.paper.server import (
    _detect_identifier_type,
    _huggingface_sort,
    _modelscope_sort,
    _normalize_arxiv_id,
    _resource_to_trending_paper,
    _score_from_signals,
    _split_sections,
    read_paper,
    resolve_paper_identifier,
    search_papers,
    trending_papers,
)
from shared.settings import get_settings


def test_normalize_arxiv_id_accepts_url() -> None:
    assert _normalize_arxiv_id("https://arxiv.org/abs/2401.12345v2") == "2401.12345v2"


def test_detect_identifier_type() -> None:
    assert _detect_identifier_type("10.1000/example", "auto") == "doi"
    assert _detect_identifier_type("2401.12345", "auto") == "arxiv_id"
    assert _detect_identifier_type("https://example.com/paper.pdf", "auto") == "url"
    assert _detect_identifier_type("papers/example.pdf", "auto") == "local_path"


def test_split_sections_extracts_named_sections() -> None:
    sections = _split_sections(
        "Abstract\nShort abstract.\n1 Introduction\nIntro text.\nReferences\n[1] A"
    )

    assert sections["abstract"] == "Short abstract."
    assert sections["introduction"] == "Intro text."
    assert sections["references"] == "[1] A"


def test_search_papers_uses_selected_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "servers.paper.server._search_arxiv",
        lambda request: [
            PaperResult(
                title="A Paper",
                authors=["A"],
                year=2024,
                venue="arXiv",
                arxiv_id="2401.00001",
                url="https://arxiv.org/abs/2401.00001",
                pdf_url="https://arxiv.org/pdf/2401.00001",
                source="arxiv",
            )
        ],
    )

    response = search_papers("test", provider="arxiv")

    assert response.total_results == 1
    assert response.results[0].source == "arxiv"


def test_trending_papers_uses_selected_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "servers.paper.server.query_huggingface_papers",
        lambda **kwargs: HuggingFaceTrendingResponse(
            message="ok",
            resource_type="paper",
            query=kwargs["query"],
            sort=kwargs["sort"],
            period=kwargs["period"],
            days=14,
            total_results=1,
            results=[
                HuggingFaceResourceResult(
                    rank=1,
                    resource_type="paper",
                    id="1234.5678",
                    title="A Paper",
                    authors=["org"],
                    url="https://huggingface.co/papers/1234.5678",
                    updated_at="2026-06-01T00:00:00.000Z",
                )
            ],
        ),
    )

    response = trending_papers("llm", provider="huggingface", sort="growth", period="14d")

    assert response.provider == "huggingface"
    assert response.sort == "growth"
    assert response.period == "14d"
    assert response.days == 14
    assert response.total_results == 1
    assert response.results[0].source == "huggingface"


def test_model_hub_sort_mappings() -> None:
    assert _huggingface_sort("likes") == "likes"
    assert _huggingface_sort("downloads") == "downloads"
    assert _huggingface_sort("trending") == "trending"
    assert _huggingface_sort("growth") == "growth"
    assert _modelscope_sort("likes") == "favorites"
    assert _modelscope_sort("downloads") == "downloads"
    assert _modelscope_sort("citations") == "impact"
    assert _modelscope_sort("trending") == "trending"
    assert _modelscope_sort("growth") == "growth"


def test_modelscope_paper_conversion_derives_arxiv_metadata_and_score() -> None:
    paper = _resource_to_trending_paper(
        ModelScopeResourceResult(
            rank=1,
            resource_type="paper",
            id="123",
            title="ModelScope Paper",
            url="https://arxiv.org/abs/2606.06390",
            impact_score=480,
            view_count=20,
            favorite_count=2,
            updated_at="2026-06-01T00:00:00Z",
        ),
        provider="modelscope",
        venue="ModelScope",
        sort_source="modelscope_trending",
        days=7,
    )

    assert paper.arxiv_id == "2606.06390"
    assert paper.pdf_url == "https://arxiv.org/pdf/2606.06390"
    assert paper.citation_count == 480
    assert paper.score is not None
    assert paper.score > 0
    assert paper.signals["citation_count"] == 480


def test_score_from_signals_uses_source_specific_metrics_without_double_counting() -> None:
    assert _score_from_signals({"likes": 10, "trending_score": 100}) == 200
    assert _score_from_signals({"impact_score": 480, "favorite_count": 2, "view_count": 20}) == 502


def test_resolve_paper_identifier_uses_arxiv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "servers.paper.server._metadata_by_arxiv_id",
        lambda identifier: PaperResult(
            title="Resolved Paper",
            authors=[],
            arxiv_id=identifier,
            source="arxiv",
        ),
    )

    response = resolve_paper_identifier("2401.00001")

    assert response.identifier_type == "arxiv_id"
    assert response.paper is not None
    assert response.paper.title == "Resolved Paper"


def test_read_paper_reads_local_pdf_with_safe_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCAL_FILE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-1.4\n")

    class FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class FakeReader:
        def __init__(self, _: str) -> None:
            self.pages = [
                FakePage("Abstract\nThis is a test paper."),
                FakePage("References\n[1] Ref"),
            ]

    monkeypatch.setattr("servers.paper.server._load_pypdf", lambda: FakeReader)

    response = read_paper("sample.pdf", identifier_type="local_path", max_pages=1)

    assert response.page_count == 2
    assert response.pages_read == 1
    assert "test paper" in response.content
    assert response.truncated is True
