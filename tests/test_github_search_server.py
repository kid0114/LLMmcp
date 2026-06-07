from servers.github_search.schemas import GitHubModelSearchRequest, GitHubTrendingRequest
from servers.github_search.server import (
    _model_repository_params,
    _model_repository_query,
    _parse_trending_repositories,
    _trending_url,
)

TRENDING_HTML = """
<article class="Box-row">
  <h2><a href="/owner-one/repo-one">owner-one / repo-one</a></h2>
  <p>First repository description.</p>
  <span itemprop="programmingLanguage">Python</span>
  <a class="Link--muted" href="/owner-one/repo-one/stargazers">1,234</a>
  <a class="Link--muted" href="/owner-one/repo-one/forks">56</a>
  <span class="d-inline-block float-sm-right">123 stars today</span>
</article>
<article class="Box-row">
  <h2><a href="/owner-two/repo-two">owner-two / repo-two</a></h2>
  <a class="Link--muted" href="/owner-two/repo-two/stargazers">99</a>
  <a class="Link--muted" href="/owner-two/repo-two/forks">8</a>
  <span class="d-inline-block float-sm-right">7 stars today</span>
</article>
"""


def test_trending_url_without_language() -> None:
    request = GitHubTrendingRequest()
    assert _trending_url(request) == "https://github.com/trending?since=daily"


def test_trending_url_with_language() -> None:
    request = GitHubTrendingRequest(language="python")
    assert _trending_url(request) == "https://github.com/trending/python?since=daily"


def test_parse_trending_repositories_limits_and_normalizes_results() -> None:
    request = GitHubTrendingRequest(max_results=1)
    results = _parse_trending_repositories(TRENDING_HTML, request)

    assert len(results) == 1
    assert results[0].rank == 1
    assert results[0].name == "repo-one"
    assert results[0].full_name == "owner-one/repo-one"
    assert str(results[0].url) == "https://github.com/owner-one/repo-one"
    assert results[0].description == "First repository description."
    assert results[0].language == "Python"
    assert results[0].total_stars == 1234
    assert results[0].forks == 56
    assert results[0].stars_period == 123
    assert results[0].period == "daily"


def test_model_repository_query_adds_model_terms_and_language() -> None:
    request = GitHubModelSearchRequest(query="qwen", language="Python")
    query = _model_repository_query(request)

    assert "qwen" in query
    assert "model" in query
    assert "in:name,description,readme" in query
    assert "language:Python" in query


def test_model_repository_params_default_to_stars_sort() -> None:
    request = GitHubModelSearchRequest(query="embedding", max_results=7)
    params = _model_repository_params(request)

    assert params["per_page"] == 7
    assert params["sort"] == "stars"
    assert "embedding" in params["q"]
