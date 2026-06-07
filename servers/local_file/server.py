from datetime import UTC, datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from servers.local_file.schemas import (
    LocalFileEntry,
    LocalFileGlobResponse,
    LocalFileListResponse,
    LocalFileRequest,
    LocalFileResponse,
    LocalFileSearchMatch,
    LocalFileSearchResponse,
    LocalFileStatResponse,
    LocalGlobRequest,
    LocalListRequest,
    LocalPathRequest,
    LocalSearchRequest,
)
from shared.errors import LocalFileError, PermissionDeniedError
from shared.logging import get_logger
from shared.permissions import validate_local_path
from shared.settings import get_settings

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-local-file")


def _resolve_local_root() -> Path:
    settings = get_settings()
    if settings.local_file_root:
        return Path(settings.local_file_root).resolve()
    return Path.cwd().resolve()


def _resolve_safe_path(path: str, root: Path) -> Path:
    try:
        return validate_local_path(path, root)
    except PermissionDeniedError:
        raise
    except Exception as exc:
        raise LocalFileError(f"Invalid local file request: {exc}") from exc


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _modified_at(path: Path) -> str | None:
    try:
        timestamp = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _entry_for_path(path: Path, root: Path) -> LocalFileEntry:
    kind = "directory" if path.is_dir() else "file" if path.is_file() else "other"
    size = path.stat().st_size if path.is_file() else None
    return LocalFileEntry(
        name=path.name,
        path=_relative_path(path, root),
        kind=kind,
        size=size,
        modified_at=_modified_at(path),
    )


def _iter_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file()]


@mcp.tool()
def read_local_file(path: str, max_chars: int = 20000, offset: int = 0) -> LocalFileResponse:
    request = LocalFileRequest(path=path, max_chars=max_chars, offset=offset)
    root = _resolve_local_root()
    target = _resolve_safe_path(request.path, root)

    if not target.exists():
        raise LocalFileError(f"File does not exist: {target}")
    if not target.is_file():
        raise LocalFileError(f"Path is not a file: {target}")

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise LocalFileError(f"Failed to read file: {exc}") from exc

    sliced = content[request.offset : request.offset + request.max_chars]
    truncated = request.offset + len(sliced) < len(content)

    logger.info("read_local_file called", extra={"path": request.path, "root": str(root)})
    return LocalFileResponse(
        message="Read local file successfully",
        path=request.path,
        absolute_path=str(target),
        content=sliced,
        content_length=len(sliced),
        offset=request.offset,
        bytes_size=target.stat().st_size,
        truncated=truncated,
    )


@mcp.tool()
def list_local_files(path: str = ".", max_entries: int = 100) -> LocalFileListResponse:
    request = LocalListRequest(path=path, max_entries=max_entries)
    root = _resolve_local_root()
    target = _resolve_safe_path(request.path, root)

    if not target.exists():
        raise LocalFileError(f"Directory does not exist: {target}")
    if not target.is_dir():
        raise LocalFileError(f"Path is not a directory: {target}")

    entries = sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    selected = entries[: request.max_entries]
    logger.info("list_local_files called", extra={"path": request.path, "root": str(root)})
    return LocalFileListResponse(
        message="Listed local files successfully",
        path=request.path,
        absolute_path=str(target),
        entries=[_entry_for_path(entry, root) for entry in selected],
        total_entries=len(entries),
        truncated=len(entries) > request.max_entries,
    )


@mcp.tool()
def stat_local_file(path: str) -> LocalFileStatResponse:
    request = LocalPathRequest(path=path)
    root = _resolve_local_root()
    target = _resolve_safe_path(request.path, root)

    if not target.exists():
        return LocalFileStatResponse(
            message="Local path does not exist",
            path=request.path,
            absolute_path=str(target),
            exists=False,
        )

    kind = "directory" if target.is_dir() else "file" if target.is_file() else "other"
    logger.info("stat_local_file called", extra={"path": request.path, "root": str(root)})
    return LocalFileStatResponse(
        message="Read local path metadata successfully",
        path=request.path,
        absolute_path=str(target),
        exists=True,
        kind=kind,
        size=target.stat().st_size if target.is_file() else None,
        modified_at=_modified_at(target),
    )


@mcp.tool()
def glob_local_files(
    pattern: str, path: str = ".", max_results: int = 100
) -> LocalFileGlobResponse:
    request = LocalGlobRequest(path=path, pattern=pattern, max_results=max_results)
    root = _resolve_local_root()
    target = _resolve_safe_path(request.path, root)

    if not target.exists():
        raise LocalFileError(f"Directory does not exist: {target}")
    if not target.is_dir():
        raise LocalFileError(f"Path is not a directory: {target}")

    matches = sorted(target.glob(request.pattern), key=lambda item: item.as_posix())
    safe_matches = [_resolve_safe_path(str(match), root) for match in matches]
    selected = safe_matches[: request.max_results]
    logger.info("glob_local_files called", extra={"path": request.path, "pattern": request.pattern})
    return LocalFileGlobResponse(
        message="Matched local files successfully",
        path=request.path,
        pattern=request.pattern,
        results=[_entry_for_path(match, root) for match in selected],
        total_results=len(safe_matches),
        truncated=len(safe_matches) > request.max_results,
    )


@mcp.tool()
def search_local_files(
    query: str,
    path: str = ".",
    include_glob: str | None = None,
    max_results: int = 50,
    max_file_chars: int = 200000,
) -> LocalFileSearchResponse:
    request = LocalSearchRequest(
        path=path,
        query=query,
        include_glob=include_glob,
        max_results=max_results,
        max_file_chars=max_file_chars,
    )
    root = _resolve_local_root()
    target = _resolve_safe_path(request.path, root)

    if not target.exists():
        raise LocalFileError(f"Search path does not exist: {target}")
    candidates = [target] if target.is_file() else _iter_files(target)
    if request.include_glob:
        candidates = [item for item in candidates if item.match(request.include_glob)]

    results: list[LocalFileSearchMatch] = []
    lowered_query = request.query.lower()
    for candidate in candidates:
        if len(results) >= request.max_results:
            break
        if candidate.stat().st_size > request.max_file_chars:
            continue
        try:
            content = candidate.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if lowered_query in line.lower():
                results.append(
                    LocalFileSearchMatch(
                        path=_relative_path(candidate, root),
                        line_number=line_number,
                        line=line.strip(),
                    )
                )
                if len(results) >= request.max_results:
                    break

    logger.info("search_local_files called", extra={"path": request.path, "query": request.query})
    return LocalFileSearchResponse(
        message="Searched local files successfully",
        path=request.path,
        query=request.query,
        include_glob=request.include_glob,
        results=results,
        total_results=len(results),
        truncated=len(results) >= request.max_results,
    )


if __name__ == "__main__":
    mcp.run()
