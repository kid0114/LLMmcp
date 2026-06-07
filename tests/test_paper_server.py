from pathlib import Path

import pytest

from servers.paper.schemas import PaperResult
from servers.paper.server import (
    _detect_identifier_type,
    _normalize_arxiv_id,
    _split_sections,
    read_paper,
    resolve_paper_identifier,
    search_papers,
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
