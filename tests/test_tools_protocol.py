"""End-to-end tool invocation through the real MCP client."""

from tests.conftest import call_tool_ok


def test_run_test_case_pass(server_params):
    out = call_tool_ok(server_params, "run_test_case", {"case_id": "TC-LOGIN-001"})
    assert out["case_id"] == "TC-LOGIN-001"
    assert out["status"] == "pass"
    assert len(out["steps"]) == 2
    assert all(st["passed"] for st in out["steps"])
    assert out["log"][-1] == "Result: PASS"
    assert set(out["steps"][0]) == {"step", "action", "expected", "actual", "passed"}


def test_run_test_case_fail(server_params):
    out = call_tool_ok(server_params, "run_test_case", {"case_id": "TC-CHECKOUT-001"})
    assert out["status"] == "fail"
    assert any(not st["passed"] for st in out["steps"])
    assert out["log"][-1] == "Result: FAIL"


def test_search_bug_db_keyword(server_params):
    out = call_tool_ok(server_params, "search_bug_db", {"keyword": "checkout"})
    assert out["count"] == 2
    assert {b["id"] for b in out["matches"]} == {"BUG-103", "BUG-106"}


def test_search_bug_db_severity_filter(server_params):
    out = call_tool_ok(
        server_params, "search_bug_db", {"keyword": "login", "severity": "high"}
    )
    assert out["count"] == 2
    assert {b["id"] for b in out["matches"]} == {"BUG-101", "BUG-107"}


def test_search_bug_db_case_insensitive(server_params):
    lower = call_tool_ok(server_params, "search_bug_db", {"keyword": "timeout"})
    upper = call_tool_ok(server_params, "search_bug_db", {"keyword": "TIMEOUT"})
    assert lower["count"] == upper["count"] == 2


def test_generate_test_data_deterministic(server_params):
    args = {"entity": "user", "count": 3, "seed": 7}
    first = call_tool_ok(server_params, "generate_test_data", args)
    second = call_tool_ok(server_params, "generate_test_data", args)
    assert first == second
    assert first["entity"] == "user" and first["seed"] == 7
    assert len(first["rows"]) == 3
    assert set(first["rows"][0]) == {"user_id", "email", "role", "active"}


def test_generate_test_data_seed_changes_output(server_params):
    a = call_tool_ok(
        server_params, "generate_test_data", {"entity": "order", "count": 2, "seed": 1}
    )
    b = call_tool_ok(
        server_params, "generate_test_data", {"entity": "order", "count": 2, "seed": 2}
    )
    assert a["rows"] != b["rows"]
    assert set(a["rows"][0]) == {"order_id", "amount", "currency", "status"}


def test_generate_test_data_bug_entity(server_params):
    out = call_tool_ok(
        server_params, "generate_test_data", {"entity": "bug", "count": 1, "seed": 9}
    )
    assert set(out["rows"][0]) == {"bug_id", "title", "severity"}
