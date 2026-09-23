"""QA tools MCP server.

Exposes a small set of deterministic QA tools plus one resource over the
Model Context Protocol (stdio transport). Everything runs offline: the
"system under test" is a mock driven by data/test_cases.json, and the bug
database is a local JSON file.
"""

from __future__ import annotations

import asyncio
import json
import random
import string
from pathlib import Path
from typing import Any, TypedDict

from mcp.server.mcpserver import MCPServer

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

mcp = MCPServer("qa-tools")


def _load_json(name: str):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


# --- Structured output schemas ---------------------------------------------


class StepResult(TypedDict):
    step: int
    action: str
    expected: str
    actual: str
    passed: bool


class TestCaseResult(TypedDict):
    case_id: str
    name: str
    status: str  # "pass" | "fail"
    steps: list[StepResult]
    log: list[str]


class BugRecord(TypedDict):
    id: str
    title: str
    description: str
    severity: str
    status: str
    component: str


class BugSearchResult(TypedDict):
    keyword: str
    severity: str | None
    count: int
    matches: list[BugRecord]


class TestDataResult(TypedDict):
    entity: str
    count: int
    seed: int
    rows: list[dict[str, Any]]


# --- Tools ------------------------------------------------------------------


@mcp.tool(structured_output=True)
def run_test_case(case_id: str) -> TestCaseResult:
    """Execute a named test case from the test-case catalog against the mock
    system under test and return pass/fail plus a step-by-step log."""
    cases = _load_json("test_cases.json")
    case = next((c for c in cases if c["id"] == case_id), None)
    if case is None:
        known = ", ".join(c["id"] for c in cases)
        raise ValueError(f"Unknown test case '{case_id}'. Known ids: {known}")

    step_results: list[StepResult] = []
    log = [f"Executing {case['id']}: {case['name']}"]
    for i, step in enumerate(case["steps"], start=1):
        passed = step["simulated_actual"] == step["expected"]
        step_results.append(
            {
                "step": i,
                "action": step["action"],
                "expected": step["expected"],
                "actual": step["simulated_actual"],
                "passed": passed,
            }
        )
        log.append(
            f"  step {i}: {'PASS' if passed else 'FAIL'} "
            f"(expected={step['expected']!r}, actual={step['simulated_actual']!r})"
        )
    status = "pass" if all(s["passed"] for s in step_results) else "fail"
    log.append(f"Result: {status.upper()}")
    return {
        "case_id": case["id"],
        "name": case["name"],
        "status": status,
        "steps": step_results,
        "log": log,
    }


@mcp.tool(structured_output=True)
def search_bug_db(keyword: str, severity: str | None = None) -> BugSearchResult:
    """Keyword-search the bug database (title + description, case-insensitive).
    Optionally filter by severity: critical, high, medium, low."""
    bugs = _load_json("bugs.json")
    kw = keyword.strip().lower()
    if not kw:
        raise ValueError("keyword must be a non-empty string")
    if severity is not None and severity.lower() not in {"critical", "high", "medium", "low"}:
        raise ValueError(f"Invalid severity '{severity}'. Use critical|high|medium|low.")

    matches = [
        b
        for b in bugs
        if (kw in b["title"].lower() or kw in b["description"].lower())
        and (severity is None or b["severity"] == severity.lower())
    ]
    return {"keyword": keyword, "severity": severity, "count": len(matches), "matches": matches}


@mcp.tool(structured_output=True)
def generate_test_data(entity: str, count: int = 5, seed: int = 42) -> TestDataResult:
    """Generate deterministic fake test data. entity is one of
    user|order|bug. Same seed always yields the same rows."""
    entity = entity.lower()
    if entity not in {"user", "order", "bug"}:
        raise ValueError(f"Unknown entity '{entity}'. Use user|order|bug.")
    if not 1 <= count <= 100:
        raise ValueError("count must be between 1 and 100")

    rng = random.Random(seed)

    def word(n: int = 8) -> str:
        return "".join(rng.choice(string.ascii_lowercase) for _ in range(n))

    rows: list[dict[str, Any]] = []
    for i in range(count):
        if entity == "user":
            rows.append(
                {
                    "user_id": f"u-{seed:04d}-{i:03d}",
                    "email": f"{word()}@example.com",
                    "role": rng.choice(["admin", "editor", "viewer"]),
                    "active": rng.choice([True, False]),
                }
            )
        elif entity == "order":
            rows.append(
                {
                    "order_id": f"ord-{seed:04d}-{i:03d}",
                    "amount": round(rng.uniform(5.0, 500.0), 2),
                    "currency": "USD",
                    "status": rng.choice(["pending", "paid", "refunded"]),
                }
            )
        else:
            rows.append(
                {
                    "bug_id": f"BUG-{seed:04d}-{i:03d}",
                    "title": f"synthetic {word(6)} failure",
                    "severity": rng.choice(["critical", "high", "medium", "low"]),
                }
            )
    return {"entity": entity, "count": count, "seed": seed, "rows": rows}


# --- Resources ---------------------------------------------------------------


@mcp.resource("test-plan-template://v1")
def test_plan_template() -> str:
    """Markdown test-plan template resource."""
    return """# Test Plan: <Feature Name>

## 1. Scope
- In scope:
- Out of scope:

## 2. Test Strategy
- Functional:
- Regression:
- Exploratory:

## 3. Entry / Exit Criteria
- Entry:
- Exit:

## 4. Test Cases
| ID | Name | Priority | Status |
|----|------|----------|--------|
| TC-XXX-001 | | P1 | |

## 5. Risks & Mitigations
-
"""


def main() -> None:
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
