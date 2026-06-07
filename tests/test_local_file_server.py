from pathlib import Path

import pytest

from servers.local_file.server import (
    glob_local_files,
    list_local_files,
    read_local_file,
    search_local_files,
    stat_local_file,
)
from shared.settings import get_settings


def _set_local_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setenv("LOCAL_FILE_ROOT", str(root))
    get_settings.cache_clear()


def test_read_local_file_supports_offset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_local_root(monkeypatch, tmp_path)
    (tmp_path / "notes.txt").write_text("abcdef", encoding="utf-8")

    response = read_local_file("notes.txt", max_chars=3, offset=2)

    assert response.content == "cde"
    assert response.content_length == 3
    assert response.offset == 2
    assert response.bytes_size == 6
    assert response.truncated


def test_list_local_files_returns_directory_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_local_root(monkeypatch, tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")

    response = list_local_files(".")

    assert response.total_entries == 2
    assert response.entries[0].name == "docs"
    assert response.entries[0].kind == "directory"
    assert response.entries[1].name == "README.md"
    assert response.entries[1].kind == "file"


def test_stat_local_file_reports_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_local_root(monkeypatch, tmp_path)
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")

    response = stat_local_file("README.md")

    assert response.exists
    assert response.kind == "file"
    assert response.size == 6
    assert response.modified_at is not None


def test_glob_local_files_matches_pattern(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_local_root(monkeypatch, tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "phase.md").write_text("phase", encoding="utf-8")
    (tmp_path / "docs" / "notes.txt").write_text("notes", encoding="utf-8")

    response = glob_local_files("*.md", path="docs")

    assert response.total_results == 1
    assert response.results[0].path == "docs/phase.md"


def test_search_local_files_finds_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_local_root(monkeypatch, tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "phase.md").write_text("Phase 2\nPhase 3", encoding="utf-8")
    (tmp_path / "docs" / "notes.txt").write_text("other", encoding="utf-8")

    response = search_local_files("phase", path="docs", include_glob="*.md")

    assert response.total_results == 2
    assert response.results[0].path == "docs/phase.md"
    assert response.results[0].line_number == 1
