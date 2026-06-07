from pytest import MonkeyPatch

from servers.huggingface.schemas import HuggingFaceResourceResult, HuggingFaceTrendingRequest
from servers.huggingface.server import (
    _filter_results,
    _matches_query,
    _normalize_dataset,
    _normalize_model,
    _normalize_paper,
    _sort_results,
    huggingface_trending_resources,
    query_huggingface_papers,
)


def test_matches_query_uses_title_description_and_tags() -> None:
    assert _matches_query("llm agent", "LLM Agent Planner", None, "") is True
    assert _matches_query("vision", "Model", "vision language model", "") is True
    assert _matches_query("rag", "Model", None, "arxiv:rag custom_tag:rag") is True
    assert _matches_query("diffusion", "LLM Agent Planner", None, "") is False


def test_normalize_model_dataset_and_paper_map_fields() -> None:
    model = _normalize_model(
        {
            "id": "org/model",
            "downloads": 7,
            "likes": 3,
            "trendingScore": 9,
            "tags": ["a"],
        }
    )
    dataset = _normalize_dataset(
        {
            "id": "org/data",
            "downloads": 8,
            "likes": 4,
            "trendingScore": 10,
            "tags": [],
        }
    )
    paper = _normalize_paper(
        {
            "id": "2606.12345",
            "title": "Paper",
            "summary": "Abstract",
            "upvotes": 9,
            "publishedAt": "2026-06-01T00:00:00.000Z",
        }
    )
    assert model is not None
    assert model.url.endswith("/org/model")
    assert dataset is not None
    assert dataset.url.endswith("/datasets/org/data")
    assert paper is not None
    assert paper.likes == 9


def test_filter_and_sort_results() -> None:
    request = HuggingFaceTrendingRequest(resource_type="paper", query="llm", days=30, sort="likes")
    results = [
        HuggingFaceResourceResult(
            rank=0,
            resource_type="paper",
            id="1",
            title="LLM Paper",
            description="study",
            url="https://example.com/1",
            likes=10,
            created_at="2026-06-01T00:00:00.000Z",
            updated_at="2026-06-01T00:00:00.000Z",
        ),
        HuggingFaceResourceResult(
            rank=0,
            resource_type="paper",
            id="2",
            title="Other",
            description="study",
            url="https://example.com/2",
            likes=100,
            created_at="2020-06-01T00:00:00.000Z",
            updated_at="2020-06-01T00:00:00.000Z",
        ),
    ]
    filtered = _filter_results(request, results)
    ranked = _sort_results(filtered, request.sort)
    assert len(ranked) == 1
    assert ranked[0].id == "1"
    assert ranked[0].rank == 1


def test_huggingface_trending_resources_uses_resource_fetcher(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "servers.huggingface.server._resource_items",
        lambda resource_type: [
            HuggingFaceResourceResult(
                rank=0,
                resource_type=resource_type,
                id="a",
                title="Resource A",
                url="https://example.com/a",
                created_at="2026-06-01T00:00:00.000Z",
                updated_at="2026-06-01T00:00:00.000Z",
            )
        ],
    )
    response = huggingface_trending_resources(resource_type="paper", period="10d")
    assert response.resource_type == "paper"
    assert response.days == 10
    assert response.total_results == 1


def test_query_huggingface_papers_uses_shared_trending_path(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "servers.huggingface.server._resource_items",
        lambda resource_type: [
            HuggingFaceResourceResult(
                rank=0,
                resource_type=resource_type,
                id="2606.12345",
                title="LLM Paper",
                url="https://huggingface.co/papers/2606.12345",
                likes=11,
                created_at="2026-06-01T00:00:00.000Z",
                updated_at="2026-06-01T00:00:00.000Z",
            )
        ],
    )

    response = query_huggingface_papers(query="llm", sort="likes", period="week")

    assert response.resource_type == "paper"
    assert response.sort == "likes"
    assert response.days == 7
    assert response.results[0].rank == 1
