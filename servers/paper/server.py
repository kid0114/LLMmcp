from __future__ import annotations

import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse
from xml.etree import ElementTree

from httpx import Client, HTTPError, Timeout
from mcp.server.fastmcp import FastMCP

from servers.huggingface.schemas import HuggingFaceSort
from servers.huggingface.server import query_huggingface_papers
from servers.modelscope.server import modelscope_trending_resources
from servers.paper.schemas import (
    PaperCitationsResponse,
    PaperCompareRequest,
    PaperComparisonItem,
    PaperComparisonResponse,
    PaperIdentifierType,
    PaperMetadataRequest,
    PaperMetadataResponse,
    PaperProvider,
    PaperReadRequest,
    PaperReadResponse,
    PaperResult,
    PaperSearchRequest,
    PaperSearchResponse,
    PaperSectionReadRequest,
    PaperSectionsResponse,
    PaperSummarizeRequest,
    PaperSummaryResponse,
    PaperTrendProvider,
    PaperTrendSort,
    TrendingPaperResult,
    TrendingPapersRequest,
    TrendingPapersResponse,
)
from shared.errors import PaperError
from shared.logging import get_logger
from shared.permissions import validate_local_path
from shared.settings import get_settings

logger = get_logger(__name__)
mcp = FastMCP(name="llmmcp-paper")

ARXIV_API_BASE = "https://export.arxiv.org/api/query"
CROSSREF_WORKS_BASE = "https://api.crossref.org/works"
OPENALEX_WORKS_BASE = "https://api.openalex.org/works"
SECTION_HEADINGS = {
    "abstract",
    "introduction",
    "background",
    "related work",
    "method",
    "methods",
    "methodology",
    "experiments",
    "experiment",
    "results",
    "discussion",
    "limitations",
    "conclusion",
    "references",
}


def _http_client() -> Client:
    settings = get_settings()
    return Client(timeout=Timeout(settings.http_timeout), follow_redirects=True)


def _require_json(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise PaperError(f"Failed to decode paper provider response: {exc}") from exc
    if not isinstance(payload, dict):
        raise PaperError("Paper provider response must be a JSON object")
    return payload


def _normalize_arxiv_id(value: str) -> str:
    stripped = value.strip()
    stripped = stripped.removeprefix("arXiv:")
    stripped = stripped.removeprefix("arxiv:")
    stripped = stripped.removeprefix("https://arxiv.org/abs/")
    stripped = stripped.removeprefix("http://arxiv.org/abs/")
    return stripped.split()[0].strip("/")


def _detect_identifier_type(
    identifier: str, identifier_type: PaperIdentifierType
) -> PaperIdentifierType:
    if identifier_type != "auto":
        return identifier_type
    if identifier.lower().startswith("10.") or identifier.lower().startswith("doi:"):
        return "doi"
    parsed = urlparse(identifier)
    if parsed.scheme in {"http", "https"}:
        return "url"
    if Path(identifier).suffix.lower() == ".pdf" or "/" in identifier:
        return "local_path"
    if re.match(r"^(arxiv:)?\d{4}\.\d{4,5}(v\d+)?$", identifier.strip(), re.I):
        return "arxiv_id"
    return "doi"


def _build_arxiv_query(request: PaperSearchRequest) -> str:
    parts = [f"all:{request.query}"]
    if request.author:
        parts.append(f"au:{request.author}")
    if request.title:
        parts.append(f"ti:{request.title}")
    if request.arxiv_id:
        parts.append(f"id:{_normalize_arxiv_id(request.arxiv_id)}")
    return " AND ".join(parts)


def _text_from_arxiv_node(node: ElementTree.Element, name: str) -> str | None:
    namespace = "{http://www.w3.org/2005/Atom}"
    target = node.find(f"{namespace}{name}")
    if target is None or target.text is None:
        return None
    return " ".join(target.text.split())


def _arxiv_id_from_entry(entry: ElementTree.Element) -> str | None:
    identifier = _text_from_arxiv_node(entry, "id")
    if not identifier:
        return None
    return _normalize_arxiv_id(identifier)


def _parse_year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\b(18|19|20|21|22)\d{2}\b", value)
    return int(match.group(0)) if match else None


def _search_arxiv(request: PaperSearchRequest) -> list[PaperResult]:
    params: dict[str, str | int] = {
        "search_query": _build_arxiv_query(request),
        "start": 0,
        "max_results": request.max_results,
    }
    try:
        with _http_client() as client:
            response = client.get(ARXIV_API_BASE, params=params)
            response.raise_for_status()
    except HTTPError as exc:
        raise PaperError(f"arXiv request failed: {exc}") from exc

    try:
        root = ElementTree.fromstring(response.text)
    except ElementTree.ParseError as exc:
        raise PaperError(f"Failed to parse arXiv response: {exc}") from exc

    namespace = "{http://www.w3.org/2005/Atom}"
    results: list[PaperResult] = []
    for entry in root.findall(f"{namespace}entry"):
        title = _text_from_arxiv_node(entry, "title") or ""
        arxiv_id = _arxiv_id_from_entry(entry)
        authors: list[str] = []
        for author in entry.findall(f"{namespace}author"):
            name_node = author.find(f"{namespace}name")
            if name_node is not None and name_node.text:
                authors.append(name_node.text.strip())
        pdf_url = None
        for link in entry.findall(f"{namespace}link"):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href")
                break
        if not pdf_url and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        results.append(
            PaperResult(
                title=title,
                authors=authors,
                abstract=_text_from_arxiv_node(entry, "summary"),
                year=_parse_year(_text_from_arxiv_node(entry, "published")),
                venue="arXiv",
                arxiv_id=arxiv_id,
                url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
                pdf_url=pdf_url,
                source="arxiv",
            )
        )
    return _dedupe_results(results)[: request.max_results]


def _crossref_query(request: PaperSearchRequest) -> dict[str, Any]:
    query = request.title or request.query
    params: dict[str, Any] = {"query": query, "rows": request.max_results}
    filters: list[str] = []
    if request.year_from:
        filters.append(f"from-pub-date:{request.year_from}")
    if request.year_to:
        filters.append(f"until-pub-date:{request.year_to}")
    if filters:
        params["filter"] = ",".join(filters)
    return params


def _first(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return value


def _crossref_year(item: dict[str, Any]) -> int | None:
    publication = item.get("published-print") or item.get("published-online") or {}
    date_parts = publication.get("date-parts") or []
    if date_parts and isinstance(date_parts[0], list) and date_parts[0]:
        return int(date_parts[0][0])
    return None


def _search_crossref(request: PaperSearchRequest) -> list[PaperResult]:
    try:
        with _http_client() as client:
            response = client.get(CROSSREF_WORKS_BASE, params=_crossref_query(request))
            response.raise_for_status()
    except HTTPError as exc:
        raise PaperError(f"Crossref request failed: {exc}") from exc

    payload = _require_json(response)
    items = ((payload.get("message") or {}).get("items")) or []
    results: list[PaperResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        authors = [
            " ".join(part for part in [author.get("given"), author.get("family")] if part)
            for author in item.get("author", [])
            if isinstance(author, dict)
        ]
        title = _first(item.get("title")) or ""
        doi = item.get("DOI")
        results.append(
            PaperResult(
                title=str(title),
                authors=authors,
                abstract=item.get("abstract"),
                year=_crossref_year(item),
                venue=str(_first(item.get("container-title")) or "") or None,
                doi=doi,
                url=f"https://doi.org/{doi}" if doi else item.get("URL"),
                citation_count=item.get("is-referenced-by-count"),
                source="crossref",
            )
        )
    return _dedupe_results(results)[: request.max_results]


def _openalex_filter(request: PaperSearchRequest) -> str | None:
    filters: list[str] = []
    if request.year_from:
        filters.append(f"from_publication_date:{request.year_from}-01-01")
    if request.year_to:
        filters.append(f"to_publication_date:{request.year_to}-12-31")
    return ",".join(filters) if filters else None


def _search_openalex(request: PaperSearchRequest) -> list[PaperResult]:
    params: dict[str, Any] = {
        "search": request.title or request.query,
        "per-page": request.max_results,
    }
    filters = _openalex_filter(request)
    if filters:
        params["filter"] = filters
    try:
        with _http_client() as client:
            response = client.get(OPENALEX_WORKS_BASE, params=params)
            response.raise_for_status()
    except HTTPError as exc:
        raise PaperError(f"OpenAlex request failed: {exc}") from exc

    payload = _require_json(response)
    items = payload.get("results") or []
    results: list[PaperResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        open_access = item.get("open_access") or {}
        doi = item.get("doi")
        if isinstance(doi, str) and doi.startswith("https://doi.org/"):
            doi = doi.removeprefix("https://doi.org/")
        authorships = item.get("authorships") or []
        authors = [
            (authorship.get("author") or {}).get("display_name")
            for authorship in authorships
            if isinstance(authorship, dict)
        ]
        results.append(
            PaperResult(
                title=item.get("title") or item.get("display_name") or "",
                authors=[author for author in authors if author],
                abstract=None,
                year=item.get("publication_year"),
                venue=source.get("display_name"),
                doi=doi,
                url=item.get("doi") or item.get("id"),
                pdf_url=open_access.get("oa_url"),
                citation_count=item.get("cited_by_count"),
                source="openalex",
            )
        )
    return _dedupe_results(results)[: request.max_results]


def _result_key(result: PaperResult) -> str:
    if result.doi:
        return f"doi:{result.doi.lower()}"
    if result.arxiv_id:
        return f"arxiv:{result.arxiv_id.lower()}"
    return "title:" + re.sub(r"\W+", "", result.title.lower())


def _dedupe_results(results: list[PaperResult]) -> list[PaperResult]:
    seen: set[str] = set()
    deduped: list[PaperResult] = []
    for result in results:
        key = _result_key(result)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _search_provider(request: PaperSearchRequest) -> list[PaperResult]:
    if request.provider == "arxiv":
        return _search_arxiv(request)
    if request.provider == "crossref":
        return _search_crossref(request)
    if request.provider == "openalex":
        return _search_openalex(request)

    results: list[PaperResult] = []
    errors: list[str] = []
    for provider, searcher in (
        ("arxiv", _search_arxiv),
        ("crossref", _search_crossref),
        ("openalex", _search_openalex),
    ):
        try:
            results.extend(searcher(request))
        except PaperError as exc:
            errors.append(f"{provider}: {exc}")
    deduped = _dedupe_results(results)
    if not deduped and errors:
        raise PaperError("All paper providers failed: " + "; ".join(errors))
    return deduped[: request.max_results]


def _date_days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).date().isoformat()


def _arxiv_date_range(days: int) -> str:
    start = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y%m%d0000")
    end = datetime.now(UTC).strftime("%Y%m%d2359")
    return f"submittedDate:[{start} TO {end}]"


def _score_from_signals(signals: dict[str, Any]) -> float:
    score = 0.0
    if isinstance(signals.get("likes"), int | float):
        score += float(signals["likes"]) * 20.0
    elif isinstance(signals.get("trending_score"), int | float):
        score += float(signals["trending_score"]) * 20.0
    for key, weight in (
        ("citation_count", 10.0),
        ("downloads", 1.0),
        ("impact_score", 1.0),
        ("favorite_count", 10.0),
        ("view_count", 0.1),
    ):
        value = signals.get(key)
        if isinstance(value, int | float):
            score += float(value) * weight
    return score


def _rank_trending_results(results: list[TrendingPaperResult]) -> list[TrendingPaperResult]:
    ranked = sorted(
        results,
        key=lambda result: (
            result.score if result.score is not None else _score_from_signals(result.signals),
            result.year or 0,
        ),
        reverse=True,
    )
    for index, result in enumerate(ranked, start=1):
        result.rank = index
    return ranked


def _trending_from_paper(
    result: PaperResult, rank: int, signals: dict[str, Any]
) -> TrendingPaperResult:
    return TrendingPaperResult(
        rank=rank,
        title=result.title,
        authors=result.authors,
        abstract=result.abstract,
        year=result.year,
        venue=result.venue,
        doi=result.doi,
        arxiv_id=result.arxiv_id,
        url=result.url,
        pdf_url=result.pdf_url,
        citation_count=result.citation_count,
        source=result.source,
        score=_score_from_signals(signals),
        signals=signals,
    )


def _openalex_trending_sort(sort: PaperTrendSort) -> str:
    if sort in {"recent", "updated", "growth"}:
        return "publication_date:desc"
    return "cited_by_count:desc"


def _trending_openalex(request: TrendingPapersRequest) -> list[TrendingPaperResult]:
    params: dict[str, Any] = {
        "search": request.query,
        "per-page": request.max_results,
        "sort": _openalex_trending_sort(request.sort),
        "filter": f"from_publication_date:{_date_days_ago(request.days)}",
    }
    try:
        with _http_client() as client:
            response = client.get(OPENALEX_WORKS_BASE, params=params)
            response.raise_for_status()
    except HTTPError as exc:
        raise PaperError(f"OpenAlex trending request failed: {exc}") from exc

    payload = _require_json(response)
    items = payload.get("results") or []
    results: list[TrendingPaperResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        paper = _openalex_item_to_result(item)
        signals = {
            "citation_count": paper.citation_count,
            "publication_year": paper.year,
            "days": request.days,
            "sort_source": "openalex_cited_by_count"
            if request.sort not in {"recent", "updated", "growth"}
            else "openalex_publication_date",
        }
        results.append(_trending_from_paper(paper, len(results) + 1, signals))
    if request.sort == "growth":
        return _rank_trending_results(results)[: request.max_results]
    return results[: request.max_results]


def _trending_arxiv(request: TrendingPapersRequest) -> list[TrendingPaperResult]:
    query = f"all:{request.query} AND {_arxiv_date_range(request.days)}"
    params: dict[str, str | int] = {
        "search_query": query,
        "start": 0,
        "max_results": request.max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    try:
        with _http_client() as client:
            response = client.get(ARXIV_API_BASE, params=params)
            response.raise_for_status()
    except HTTPError as exc:
        raise PaperError(f"arXiv trending request failed: {exc}") from exc

    try:
        root = ElementTree.fromstring(response.text)
    except ElementTree.ParseError as exc:
        raise PaperError(f"Failed to parse arXiv trending response: {exc}") from exc
    namespace = "{http://www.w3.org/2005/Atom}"
    papers: list[PaperResult] = []
    for entry in root.findall(f"{namespace}entry"):
        title = _text_from_arxiv_node(entry, "title") or ""
        arxiv_id = _arxiv_id_from_entry(entry)
        authors: list[str] = []
        for author in entry.findall(f"{namespace}author"):
            name_node = author.find(f"{namespace}name")
            if name_node is not None and name_node.text:
                authors.append(name_node.text.strip())
        pdf_url = None
        for link in entry.findall(f"{namespace}link"):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href")
                break
        if not pdf_url and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        papers.append(
            PaperResult(
                title=title,
                authors=authors,
                abstract=_text_from_arxiv_node(entry, "summary"),
                year=_parse_year(_text_from_arxiv_node(entry, "published")),
                venue="arXiv",
                arxiv_id=arxiv_id,
                url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
                pdf_url=pdf_url,
                source="arxiv",
            )
        )
    return [
        _trending_from_paper(
            paper,
            rank=index,
            signals={"sort_source": "arxiv_submitted_date", "days": request.days},
        )
        for index, paper in enumerate(_dedupe_results(papers), start=1)
    ][: request.max_results]


def _openalex_item_to_result(item: dict[str, Any]) -> PaperResult:
    primary_location = item.get("primary_location") or {}
    source = primary_location.get("source") or {}
    open_access = item.get("open_access") or {}
    doi = item.get("doi")
    if isinstance(doi, str) and doi.startswith("https://doi.org/"):
        doi = doi.removeprefix("https://doi.org/")
    authorships = item.get("authorships") or []
    authors = [
        (authorship.get("author") or {}).get("display_name")
        for authorship in authorships
        if isinstance(authorship, dict)
    ]
    return PaperResult(
        title=item.get("title") or item.get("display_name") or "",
        authors=[author for author in authors if author],
        abstract=None,
        year=item.get("publication_year"),
        venue=source.get("display_name"),
        doi=doi,
        url=item.get("doi") or item.get("id"),
        pdf_url=open_access.get("oa_url"),
        citation_count=item.get("cited_by_count"),
        source="openalex",
    )


def _huggingface_sort(sort: PaperTrendSort) -> HuggingFaceSort:
    if sort == "likes":
        return "likes"
    if sort in {"recent", "updated", "trending", "growth", "downloads"}:
        return sort
    return "trending"


def _arxiv_id_from_url(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", value, re.I)
    if not match:
        return None
    return _normalize_arxiv_id(match.group(1).removesuffix(".pdf"))


def _resource_to_trending_paper(
    resource: Any,
    provider: str,
    venue: str,
    sort_source: str,
    days: int,
) -> TrendingPaperResult:
    paper_id = str(resource.id)
    arxiv_id = paper_id if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", paper_id) else None
    arxiv_id = arxiv_id or _arxiv_id_from_url(getattr(resource, "url", None))
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None
    impact_score = getattr(resource, "impact_score", None)
    signals = {
        "downloads": getattr(resource, "downloads", None),
        "likes": getattr(resource, "likes", None),
        "view_count": getattr(resource, "view_count", None),
        "favorite_count": getattr(resource, "favorite_count", None),
        "impact_score": impact_score,
        "trending_score": getattr(resource, "trending_score", None),
        "citation_count": impact_score,
        "created_at": getattr(resource, "created_at", None),
        "updated_at": getattr(resource, "updated_at", None),
        "days": days,
        "sort_source": sort_source,
    }
    published_at = getattr(resource, "updated_at", None) or getattr(resource, "created_at", None)
    return TrendingPaperResult(
        rank=resource.rank,
        title=resource.title,
        authors=getattr(resource, "authors", []),
        abstract=getattr(resource, "description", None),
        year=_parse_year(published_at),
        venue=venue,
        arxiv_id=arxiv_id,
        url=resource.url,
        pdf_url=pdf_url,
        citation_count=impact_score,
        source=provider,
        score=_score_from_signals(signals),
        signals=signals,
    )


def _trending_huggingface(request: TrendingPapersRequest) -> list[TrendingPaperResult]:
    response = query_huggingface_papers(
        query=request.query,
        max_results=request.max_results,
        sort=_huggingface_sort(request.sort),
        period=request.period,
        days=request.days,
    )
    return [
        _resource_to_trending_paper(
            resource,
            provider="huggingface",
            venue="Hugging Face Papers",
            sort_source=f"huggingface_{response.sort}",
            days=response.days,
        )
        for resource in response.results
    ]


def _modelscope_sort(sort: PaperTrendSort) -> str:
    if sort == "likes":
        return "favorites"
    if sort == "citations":
        return "impact"
    if sort in {"recent", "updated", "trending", "growth", "downloads"}:
        return sort
    return "views"


def _trending_modelscope(request: TrendingPapersRequest) -> list[TrendingPaperResult]:
    response = modelscope_trending_resources(
        resource_type="paper",
        query=request.query,
        max_results=request.max_results,
        sort=_modelscope_sort(request.sort),
        period=request.period,
        days=request.days,
    )
    return [
        _resource_to_trending_paper(
            resource,
            provider="modelscope",
            venue="ModelScope",
            sort_source=f"modelscope_{response.sort}",
            days=response.days,
        )
        for resource in response.results
    ]


def _trending_provider(request: TrendingPapersRequest) -> list[TrendingPaperResult]:
    if request.provider == "openalex":
        return _trending_openalex(request)
    if request.provider == "arxiv":
        return _trending_arxiv(request)
    if request.provider == "huggingface":
        return _trending_huggingface(request)
    if request.provider == "modelscope":
        return _trending_modelscope(request)

    results: list[TrendingPaperResult] = []
    errors: list[str] = []
    for provider, searcher in (
        ("openalex", _trending_openalex),
        ("arxiv", _trending_arxiv),
        ("huggingface", _trending_huggingface),
        ("modelscope", _trending_modelscope),
    ):
        try:
            results.extend(searcher(request))
        except PaperError as exc:
            errors.append(f"{provider}: {exc}")
    deduped = _dedupe_results(cast(list[PaperResult], results))
    ranked = _rank_trending_results(cast(list[TrendingPaperResult], deduped))
    if not ranked and errors:
        raise PaperError("All paper trend providers failed: " + "; ".join(errors))
    return ranked[: request.max_results]


def _metadata_by_doi(doi: str) -> PaperResult | None:
    request = PaperSearchRequest(query=doi, doi=doi, provider="crossref", max_results=1)
    results = _search_crossref(request)
    return results[0] if results else None


def _metadata_by_arxiv_id(arxiv_id: str) -> PaperResult | None:
    request = PaperSearchRequest(
        query=_normalize_arxiv_id(arxiv_id),
        arxiv_id=arxiv_id,
        provider="arxiv",
        max_results=1,
    )
    results = _search_arxiv(request)
    return results[0] if results else None


def _pdf_url_for_identifier(identifier: str, identifier_type: PaperIdentifierType) -> str:
    resolved_type = _detect_identifier_type(identifier, identifier_type)
    if resolved_type == "url":
        return identifier
    if resolved_type == "arxiv_id":
        return f"https://arxiv.org/pdf/{_normalize_arxiv_id(identifier)}"
    if resolved_type == "doi":
        metadata = _metadata_by_doi(identifier.removeprefix("doi:"))
        if metadata and metadata.pdf_url:
            return str(metadata.pdf_url)
        raise PaperError("DOI metadata did not provide a direct PDF URL")
    raise PaperError("local_path does not have a PDF URL")


def _load_pypdf() -> Any:
    try:
        from importlib import import_module

        return import_module("pypdf").PdfReader
    except ImportError as exc:
        raise PaperError("pypdf is required to read paper PDF files") from exc


def _read_pdf_path(path: Path, max_chars: int, offset: int, max_pages: int) -> PaperReadResponse:
    pdf_reader = _load_pypdf()
    try:
        reader = pdf_reader(str(path))
    except Exception as exc:
        raise PaperError(f"Failed to open paper PDF: {exc}") from exc
    page_count = len(reader.pages)
    parts: list[str] = []
    pages_read = 0
    for page in reader.pages[:max_pages]:
        try:
            parts.append((page.extract_text() or "").strip())
        except Exception as exc:
            raise PaperError(f"Failed to extract paper PDF text: {exc}") from exc
        pages_read += 1
    full_content = "\n\n".join(part for part in parts if part)
    sliced = full_content[offset : offset + max_chars]
    truncated = offset + max_chars < len(full_content) or page_count > max_pages
    return PaperReadResponse(
        message="Read paper successfully",
        identifier=str(path),
        identifier_type="local_path",
        source_path=str(path),
        page_count=page_count,
        pages_read=pages_read,
        content=sliced,
        content_length=len(sliced),
        offset=offset,
        truncated=truncated,
    )


def _download_pdf(url: str) -> Path:
    try:
        with _http_client() as client:
            response = client.get(url)
            response.raise_for_status()
    except HTTPError as exc:
        raise PaperError(f"Failed to download paper PDF: {exc}") from exc
    target = Path(tempfile.gettempdir()) / f"llmmcp_paper_{abs(hash(url))}.pdf"
    target.write_bytes(response.content)
    return target


def _resolve_local_root() -> Path:
    settings = get_settings()
    if settings.local_file_root:
        return Path(settings.local_file_root).resolve()
    return Path.cwd().resolve()


def _read_paper_content(request: PaperReadRequest) -> PaperReadResponse:
    resolved_type = _detect_identifier_type(request.identifier, request.identifier_type)
    if resolved_type == "local_path":
        target = validate_local_path(request.identifier, _resolve_local_root())
        response = _read_pdf_path(target, request.max_chars, request.offset, request.max_pages)
        response.identifier = request.identifier
        response.identifier_type = resolved_type
        return response

    url = _pdf_url_for_identifier(request.identifier, resolved_type)
    target = _download_pdf(url)
    response = _read_pdf_path(target, request.max_chars, request.offset, request.max_pages)
    response.identifier = request.identifier
    response.identifier_type = resolved_type
    response.source_url = url
    return response


def _split_sections(content: str) -> dict[str, str]:
    lines = content.splitlines()
    sections: dict[str, list[str]] = {}
    current = "body"
    sections[current] = []
    for line in lines:
        normalized = re.sub(r"^\d+(\.\d+)*\s+", "", line.strip()).lower()
        if normalized in SECTION_HEADINGS:
            current = normalized
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {name: "\n".join(part for part in body).strip() for name, body in sections.items()}


def _extract_citation_lines(content: str) -> list[str]:
    sections = _split_sections(content)
    references = sections.get("references", "")
    if not references:
        return []
    citations = [line.strip() for line in references.splitlines() if line.strip()]
    return citations[:100]


def _simple_key_points(content: str, max_points: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(content.split()))
    points = [sentence.strip() for sentence in sentences if len(sentence.strip()) > 40]
    return points[:max_points]


def _key_terms(content: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{4,}", content.lower())
    ignored = {"paper", "using", "method", "results", "section", "model", "models", "based"}
    counts: dict[str, int] = {}
    for word in words:
        if word in ignored:
            continue
        counts[word] = counts.get(word, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:12]]


@mcp.tool()
def search_papers(
    query: str,
    max_results: int = 5,
    provider: str = "auto",
    author: str | None = None,
    title: str | None = None,
    doi: str | None = None,
    arxiv_id: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    venue: str | None = None,
) -> PaperSearchResponse:
    """Search scholarly papers by query and optional metadata filters.

    Use this tool for paper discovery. Do not use MCP resources for paper
    search; this server exposes paper operations as tools.
    """
    request = PaperSearchRequest(
        query=query,
        max_results=max_results,
        provider=cast(PaperProvider, provider),
        author=author,
        title=title,
        doi=doi,
        arxiv_id=arxiv_id,
        year_from=year_from,
        year_to=year_to,
        venue=venue,
    )
    results = _search_provider(request)
    logger.debug(
        "search_papers called",
        extra={"query": request.query, "provider": request.provider},
    )
    return PaperSearchResponse(
        message="Searched papers successfully",
        query=request.query,
        provider=request.provider,
        results=results,
        total_results=len(results),
    )


@mcp.tool()
def trending_papers(
    query: str = "large language model",
    max_results: int = 10,
    provider: str = "auto",
    sort: str = "trending",
    period: str | None = None,
    days: int = 30,
) -> TrendingPapersResponse:
    """Find trending or model-linked papers from supported paper providers.

    Use this tool for trending paper lookups. Do not use MCP resources for paper
    discovery; this server exposes paper operations as tools.
    """
    request = TrendingPapersRequest(
        query=query,
        max_results=max_results,
        provider=cast(PaperTrendProvider, provider),
        sort=cast(PaperTrendSort, sort),
        period=period,
        days=days,
    )
    results = _trending_provider(request)
    logger.debug(
        "trending_papers called",
        extra={"query": request.query, "provider": request.provider, "sort": request.sort},
    )
    return TrendingPapersResponse(
        message=f"Returned {len(results)} trending paper or model-linked results",
        query=request.query,
        provider=request.provider,
        sort=request.sort,
        period=request.period,
        days=request.days,
        results=results,
        total_results=len(results),
    )


@mcp.tool()
def resolve_paper_identifier(
    identifier: str, identifier_type: str = "auto"
) -> PaperMetadataResponse:
    """Resolve DOI, arXiv ID, URL, or local path into paper metadata.

    Use this tool for paper identifier resolution. Do not use MCP resources for
    paper identifiers; this server exposes paper operations as tools.
    """
    request = PaperMetadataRequest(
        identifier=identifier,
        identifier_type=cast(PaperIdentifierType, identifier_type),
    )
    resolved_type = _detect_identifier_type(request.identifier, request.identifier_type)
    paper = None
    if resolved_type == "doi":
        paper = _metadata_by_doi(request.identifier.removeprefix("doi:"))
    elif resolved_type == "arxiv_id":
        paper = _metadata_by_arxiv_id(request.identifier)
    return PaperMetadataResponse(
        message="Resolved paper identifier successfully",
        identifier=request.identifier,
        identifier_type=resolved_type,
        paper=paper,
    )


@mcp.tool()
def get_paper_metadata(identifier: str, identifier_type: str = "auto") -> PaperMetadataResponse:
    """Get paper metadata for DOI, arXiv ID, URL, or local path.

    Use this tool for paper metadata lookup. Do not use MCP resources for paper
    metadata; this server exposes paper operations as tools.
    """
    return cast(
        PaperMetadataResponse,
        resolve_paper_identifier(identifier=identifier, identifier_type=identifier_type),
    )


@mcp.tool()
def read_paper(
    identifier: str,
    identifier_type: str = "auto",
    max_chars: int = 20000,
    offset: int = 0,
    max_pages: int = 30,
) -> PaperReadResponse:
    """Read paper content from DOI, arXiv ID, URL, or local PDF path.

    Use this tool for paper text extraction. Do not use resources/read for
    arbitrary paper URLs or paths; this server exposes paper reading as a tool.
    """
    request = PaperReadRequest(
        identifier=identifier,
        identifier_type=cast(PaperIdentifierType, identifier_type),
        max_chars=max_chars,
        offset=offset,
        max_pages=max_pages,
    )
    return _read_paper_content(request)


@mcp.tool()
def read_paper_sections(
    identifier: str,
    section: str,
    identifier_type: str = "auto",
    max_chars: int = 20000,
    offset: int = 0,
    max_pages: int = 30,
) -> PaperSectionsResponse:
    """Read selected sections from a paper.

    Use this tool for section-level paper reading. Do not use resources/read for
    paper sections; this server exposes section reading as a tool.
    """
    request = PaperSectionReadRequest(
        identifier=identifier,
        identifier_type=cast(PaperIdentifierType, identifier_type),
        max_chars=max_chars,
        offset=offset,
        max_pages=max_pages,
        section=section,
    )
    content = _read_paper_content(request).content
    sections = _split_sections(content)
    needle = request.section.lower()
    matched = {name: text for name, text in sections.items() if needle in name}
    if not matched and needle == "all":
        matched = sections
    return PaperSectionsResponse(
        message="Read paper sections successfully",
        identifier=request.identifier,
        sections=matched,
        total_sections=len(matched),
    )


@mcp.tool()
def extract_paper_citations(
    identifier: str,
    identifier_type: str = "auto",
    max_chars: int = 80000,
    offset: int = 0,
    max_pages: int = 100,
) -> PaperCitationsResponse:
    """Extract citation lines from a paper.

    Use this tool for citation extraction. Do not use MCP resources for paper
    citations; this server exposes citation extraction as a tool.
    """
    request = PaperReadRequest(
        identifier=identifier,
        identifier_type=cast(PaperIdentifierType, identifier_type),
        max_chars=max_chars,
        offset=offset,
        max_pages=max_pages,
    )
    citations = _extract_citation_lines(_read_paper_content(request).content)
    return PaperCitationsResponse(
        message="Extracted paper citations successfully",
        identifier=request.identifier,
        citations=citations,
        total_citations=len(citations),
    )


@mcp.tool()
def summarize_paper(
    identifier: str,
    identifier_type: str = "auto",
    max_chars: int = 20000,
    offset: int = 0,
    max_pages: int = 30,
    max_points: int = 6,
) -> PaperSummaryResponse:
    """Summarize a paper with lightweight extractive heuristics.

    Use this tool for paper summaries. Do not use MCP resources for paper
    summarization; this server exposes summarization as a tool.
    """
    request = PaperSummarizeRequest(
        identifier=identifier,
        identifier_type=cast(PaperIdentifierType, identifier_type),
        max_chars=max_chars,
        offset=offset,
        max_pages=max_pages,
        max_points=max_points,
    )
    content = _read_paper_content(request).content
    points = _simple_key_points(content, request.max_points)
    summary = points[0] if points else content[: min(len(content), 500)]
    return PaperSummaryResponse(
        message="Summarized paper with extractive heuristics",
        identifier=request.identifier,
        summary=summary,
        key_points=points,
    )


@mcp.tool()
def compare_papers(
    identifiers: list[str],
    identifier_type: str = "auto",
    max_chars_per_paper: int = 8000,
) -> PaperComparisonResponse:
    """Compare multiple papers using lightweight term and abstract extraction.

    Use this tool for paper comparison. Do not use MCP resources for paper
    comparison; this server exposes comparison as a tool.
    """
    request = PaperCompareRequest(
        identifiers=identifiers,
        identifier_type=cast(PaperIdentifierType, identifier_type),
        max_chars_per_paper=max_chars_per_paper,
    )
    results: list[PaperComparisonItem] = []
    for identifier in request.identifiers:
        read_request = PaperReadRequest(
            identifier=identifier,
            identifier_type=request.identifier_type,
            max_chars=request.max_chars_per_paper,
        )
        content = _read_paper_content(read_request).content
        results.append(
            PaperComparisonItem(
                identifier=identifier,
                abstract=_split_sections(content).get("abstract"),
                key_terms=_key_terms(content),
            )
        )
    return PaperComparisonResponse(
        message="Compared papers with lightweight term extraction",
        results=results,
        total_results=len(results),
    )


if __name__ == "__main__":
    mcp.run()
