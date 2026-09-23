"""Tool schema tests: names, input JSON schemas, output schemas, resources."""

from tests.conftest import run_with_session


def _list_tools(params):
    async def fn(session):
        return await session.list_tools()

    return run_with_session(params, fn)


def test_tool_names_and_count(server_params):
    tools = _list_tools(server_params)
    assert {t.name for t in tools.tools} == {
        "run_test_case",
        "search_bug_db",
        "generate_test_data",
    }


def test_run_test_case_input_schema(server_params):
    schema = next(
        t for t in _list_tools(server_params).tools if t.name == "run_test_case"
    ).input_schema
    assert schema["type"] == "object"
    assert schema["properties"]["case_id"]["type"] == "string"
    assert schema["required"] == ["case_id"]


def test_search_bug_db_input_schema(server_params):
    schema = next(
        t for t in _list_tools(server_params).tools if t.name == "search_bug_db"
    ).input_schema
    assert schema["properties"]["keyword"]["type"] == "string"
    assert "severity" in schema["properties"]
    assert schema["required"] == ["keyword"]


def test_generate_test_data_input_schema(server_params):
    schema = next(
        t for t in _list_tools(server_params).tools if t.name == "generate_test_data"
    ).input_schema
    props = schema["properties"]
    assert props["entity"]["type"] == "string"
    assert props["count"]["type"] in ("integer", "number")
    assert props["seed"]["type"] in ("integer", "number")
    assert schema["required"] == ["entity"]


def test_tools_advertise_structured_output_schema(server_params):
    """Each tool publishes an outputSchema describing its result shape."""
    tools = {t.name: t for t in _list_tools(server_params).tools}
    for name in ("run_test_case", "search_bug_db", "generate_test_data"):
        assert tools[name].output_schema["type"] == "object", name
    run_schema = tools["run_test_case"].output_schema["properties"]
    assert set(run_schema) >= {"case_id", "name", "status", "steps", "log"}
    assert tools["search_bug_db"].output_schema["properties"]["count"]["type"] in (
        "integer",
        "number",
    )


def test_resource_listed(server_params):
    async def fn(session):
        resources = await session.list_resources()
        return [str(r.uri) for r in resources.resources]

    assert "test-plan-template://v1" in run_with_session(server_params, fn)
