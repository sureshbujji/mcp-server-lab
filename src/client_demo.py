"""End-to-end client demo for the QA tools MCP server.

Spawns src/qa_server.py over the stdio transport, lists the available tools,
calls each one, reads the test-plan resource, and prints the results.
Runs fully offline — no API key, no network.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

SERVER_SCRIPT = Path(__file__).resolve().parent / "qa_server.py"


def _show(title: str, payload) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2))


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            _show("tools/list", [t.name for t in tools.tools])

            res = await session.call_tool("run_test_case", {"case_id": "TC-LOGIN-001"})
            assert not res.is_error
            _show("run_test_case(TC-LOGIN-001)", res.structured_content)

            res = await session.call_tool("run_test_case", {"case_id": "TC-CHECKOUT-001"})
            out = res.structured_content
            _show("run_test_case(TC-CHECKOUT-001) status", {"status": out["status"]})

            res = await session.call_tool(
                "search_bug_db", {"keyword": "login", "severity": "high"}
            )
            out = res.structured_content
            _show(
                "search_bug_db(login, high)",
                {"count": out["count"], "ids": [b["id"] for b in out["matches"]]},
            )

            res = await session.call_tool(
                "generate_test_data", {"entity": "user", "count": 2, "seed": 7}
            )
            _show("generate_test_data(user, 2, seed=7)", res.structured_content)

            resources = await session.list_resources()
            _show("resources/list", [str(r.uri) for r in resources.resources])

            content = await session.read_resource("test-plan-template://v1")
            text = content.contents[0].text
            _show("resource test-plan-template://v1 (first 3 lines)", text.splitlines()[:3])

    print("\nDemo complete — all calls served locally over stdio.")


if __name__ == "__main__":
    asyncio.run(main())
