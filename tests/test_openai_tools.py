from openai_tools.web_tools import OPENAI_TOOL_DEFINITIONS, execute_openai_tool


def test_openai_tool_definitions_expose_three_web_tools() -> None:
    names = [item["function"]["name"] for item in OPENAI_TOOL_DEFINITIONS]
    assert names == ["search_web", "fetch_url", "browser_fetch"]


def test_search_tool_definition_includes_provider() -> None:
    search_tool = OPENAI_TOOL_DEFINITIONS[0]
    properties = search_tool["function"]["parameters"]["properties"]
    assert "provider" in properties
    assert properties["provider"]["default"] == "auto"


def test_execute_openai_tool_rejects_unknown_name() -> None:
    try:
        execute_openai_tool("unknown_tool", {})
    except ValueError as exc:
        assert "Unknown tool 'unknown_tool'" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown tool")
