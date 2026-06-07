from pytest import MonkeyPatch

from servers.modelscope.schemas import ModelScopeResourceResult, ModelScopeTrendingRequest
from servers.modelscope.server import (
    _filter_results,
    _matches_query,
    _normalize_dataset,
    _normalize_paper,
    _normalize_skill,
    _sort_results,
    modelscope_trending_resources,
)


def test_matches_query_uses_title_description_and_tags() -> None:
    assert _matches_query("llm agent", "LLM Agent Planner", None, "") is True
    assert _matches_query("vision", "Model", "vision language model", "") is True
    assert _matches_query("rag", "Model", None, "custom_tag:rag") is True
    assert _matches_query("diffusion", "LLM Agent Planner", None, "") is False


def test_normalize_skill_maps_fields() -> None:
    result = _normalize_skill(
        {
            "id": "@anthropics/skill-creator",
            "display_name": "skill-creator",
            "description": "Create skills",
            "source_url": "https://example.com/skill",
            "downloads": 10,
            "view_count": 20,
            "tags": ["a"],
        }
    )
    assert result is not None
    assert result.resource_type == "skill"
    assert result.url == "https://example.com/skill"


def test_normalize_dataset_and_paper_map_fields() -> None:
    dataset = _normalize_dataset(
        {
            "id": "org/data",
            "display_name": "Data",
            "downloads": 7,
            "likes": 3,
            "tags": [],
        }
    )
    paper = _normalize_paper(
        {
            "Id": 123,
            "Title": "Paper",
            "AbstractEn": "Abstract",
            "ArxivUrl": "https://arxiv.org/abs/1234.5678",
            "ViewCount": 40,
            "FavoriteCount": 5,
            "ImpactScore": 9,
            "PublishDate": "2026-06-01T00:00:00Z",
        }
    )
    assert dataset is not None
    assert dataset.url.endswith("/datasets/org/data")
    assert paper is not None
    assert paper.impact_score == 9


def test_filter_and_sort_results() -> None:
    request = ModelScopeTrendingRequest(resource_type="paper", query="llm", days=30, sort="impact")
    results = [
        ModelScopeResourceResult(
            rank=0,
            resource_type="paper",
            id="1",
            title="LLM Paper",
            description="study",
            url="https://example.com/1",
            impact_score=10,
            created_at="2026-06-01T00:00:00Z",
            updated_at="2026-06-01T00:00:00Z",
        ),
        ModelScopeResourceResult(
            rank=0,
            resource_type="paper",
            id="2",
            title="Other",
            description="study",
            url="https://example.com/2",
            impact_score=100,
            created_at="2020-06-01T00:00:00Z",
            updated_at="2020-06-01T00:00:00Z",
        ),
    ]
    filtered = _filter_results(request, results)
    ranked = _sort_results(filtered, request.sort)
    assert len(ranked) == 1
    assert ranked[0].id == "1"
    assert ranked[0].rank == 1


def test_modelscope_trending_resources_uses_resource_fetcher(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "servers.modelscope.server._resource_items",
        lambda resource_type: [
            ModelScopeResourceResult(
                rank=0,
                resource_type=resource_type,
                id="a",
                title="Skill A",
                url="https://example.com/a",
                created_at="2026-06-01T00:00:00Z",
                updated_at="2026-06-01T00:00:00Z",
            )
        ],
    )
    response = modelscope_trending_resources(resource_type="skill", period="week")
    assert response.resource_type == "skill"
    assert response.days == 7
    assert response.total_results == 1
