"""Shared fixtures/helpers for MCP protocol tests.

Each test spawns the real server as a subprocess and talks to it through a
genuine MCP ClientSession over stdio — no mocks of the protocol layer.

Note: session bodies must not let exceptions escape the `async with` blocks
(mcp 2.x teardown deadlocks otherwise), so error-path tests catch inside.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, Coroutine

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_SCRIPT = REPO_ROOT / "src" / "qa_server.py"

# Make `from tests.conftest import ...` work regardless of where pytest runs.
sys.path.insert(0, str(REPO_ROOT))


def run(coro: Coroutine[Any, Any, Any]):
    """Drive one async test body to completion (no pytest-asyncio needed)."""
    return asyncio.run(coro)


async def _with_session(
    params: StdioServerParameters, fn: Callable[[ClientSession], Awaitable[Any]]
):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


def run_with_session(params: StdioServerParameters, fn):
    return run(_with_session(params, fn))


@pytest.fixture()
def server_params() -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])


def call_tool_ok(params: StdioServerParameters, name: str, args: dict):
    """Call a tool, assert it did not error, return its structured content."""

    async def fn(session: ClientSession):
        result = await session.call_tool(name, args)
        assert not result.is_error, f"tool {name} errored: {result.content}"
        return result.structured_content

    return run_with_session(params, fn)


def call_tool_raw(params: StdioServerParameters, name: str, args: dict):
    """Call a tool and return the raw CallToolResult (may carry is_error)."""

    async def fn(session: ClientSession):
        return await session.call_tool(name, args)

    return run_with_session(params, fn)
