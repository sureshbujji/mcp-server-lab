"""Error handling and resource-read tests through the real MCP client."""

import pytest
from mcp.shared.exceptions import MCPError

from tests.conftest import call_tool_raw, run_with_session


def test_unknown_tool_returns_error_result(server_params):
    result = call_tool_raw(server_params, "does_not_exist", {})
    assert result.is_error
    assert "does_not_exist" in result.content[0].text


@pytest.mark.parametrize(
    "tool,args",
    [
        ("run_test_case", {"case_id": "TC-NOPE-999"}),
        ("search_bug_db", {"keyword": "   "}),
        ("search_bug_db", {"keyword": "login", "severity": "urgent"}),
        ("generate_test_data", {"entity": "invoice"}),
        ("generate_test_data", {"entity": "user", "count": 0}),
        ("generate_test_data", {"entity": "user", "count": 101}),
    ],
)
def test_bad_args_return_tool_error(server_params, tool, args):
    result = call_tool_raw(server_params, tool, args)
    assert result.is_error
    assert result.content, "error result should carry a message"


def test_missing_required_arg_returns_tool_error(server_params):
    result = call_tool_raw(server_params, "run_test_case", {})
    assert result.is_error


def test_resource_read(server_params):
    async def fn(session):
        return await session.read_resource("test-plan-template://v1")

    result = run_with_session(server_params, fn)
    text = result.contents[0].text
    assert text.startswith("# Test Plan:")
    for heading in ("## 1. Scope", "## 4. Test Cases", "## 5. Risks"):
        assert heading in text


def test_unknown_resource_raises(server_params):
    async def fn(session):
        try:
            await session.read_resource("nope://missing")
        except MCPError as e:
            return e
        return None

    err = run_with_session(server_params, fn)
    assert isinstance(err, MCPError)
