# mcp-server-lab

I built a QA tools server on the Model Context Protocol — the real `mcp`
Python SDK (v2.2.0), not a mock. It exposes three QA tools and one resource
over MCP, and I drive all of them from a real MCP client over the stdio
transport. Everything runs offline: no API key, no network, no cloud.

I'm a QA Lead moving into AI architect work, and I built this to learn the
protocol the way I learn everything — by testing it. The mock system under
test, the bug database, and the test-case catalog are all local JSON, so
every tool call is deterministic and every test in `tests/` goes through the
actual MCP client↔server wire protocol (spawning the server as a subprocess),
not a stubbed-out shortcut.

## What is MCP, and why should an agent architect care?

The Model Context Protocol is an open standard (by Anthropic) for connecting
AI models to the tools and data they need — a USB-C port for AI applications.
Instead of every agent framework inventing its own function-calling plumbing,
you write a **server** that exposes **tools** (things the model can do),
**resources** (data the model can read), and **prompts**, and any MCP
**client** — Claude Desktop, an IDE agent, your own script — can discover and
call them over a standard transport (stdio or HTTP/SSE).

Why this matters if you architect agents:

- **Decoupling.** Tool logic lives in the server; any model, any client can
  use it. Swap the model without rewriting your tools.
- **Typed contracts.** Tools declare JSON input/output schemas, so agents get
  structured results instead of parsing free text.
- **Testability.** Because the protocol is standard, you can test the whole
  loop — list tools, call them, read resources — with a script, exactly like
  I do in `tests/`. No LLM in the loop required to validate the plumbing.

## Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │            MCP CLIENT (client_demo.py)         │
                    │  ClientSession over stdio transport          │
                    │  initialize → list_tools → call_tool →       │
                    │  list_resources → read_resource              │
                    └──────────────────────┬───────────────────────┘
                                           │ JSON-RPC 2.0 over
                                           │ stdin / stdout
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │         MCP SERVER (src/qa_server.py)          │
                    │  MCPServer("qa-tools")  ·  mcp SDK 2.2.0      │
                    │                                              │
                    │  TOOLS (@mcp.tool, structured output)        │
                    │   · run_test_case(case_id)                   │
                    │   · search_bug_db(keyword, severity?)        │
                    │   · generate_test_data(entity, count, seed)  │
                    │                                              │
                    │  RESOURCE                                    │
                    │   · test-plan-template://v1  (markdown)      │
                    └──────────────────────┬───────────────────────┘
                                           │ reads local files
                                           ▼
                                   data/
                                   ├── test_cases.json  (3 cases incl. 1 failing)
                                   └── bugs.json        (8-bug database)
```

Tools return typed results (`TypedDict` schemas published as MCP
`outputSchema`), so clients receive real structured data. Tool failures —
unknown test case, bad severity, unknown entity — come back as MCP error
results (`is_error=True`); an unknown tool name does the same, and an
unknown resource URI raises a protocol-level `MCPError`.

## Quickstart

```bash
git clone <this-repo> && cd mcp-server-lab
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # mcp==2.2.0, pytest — that's it
python src/client_demo.py         # end-to-end demo, fully offline
pytest -q                         # 24 tests, all through the MCP protocol
```

No `.env` setup needed — `.env.example` documents the two optional knobs
(`MCP_SERVER_NAME`, `LOG_LEVEL`); the repo runs with zero configuration.

## Sample output

`python src/client_demo.py` prints (trimmed):

```
=== tools/list ===
["run_test_case", "search_bug_db", "generate_test_data"]

=== run_test_case(TC-LOGIN-001) ===
{"case_id": "TC-LOGIN-001", "name": "Valid user login returns a session token",
 "status": "pass", "steps": [...], "log": [..., "Result: PASS"]}

=== run_test_case(TC-CHECKOUT-001) status ===
{"status": "fail"}

=== search_bug_db(login, high) ===
{"count": 2, "ids": ["BUG-101", "BUG-107"]}

=== generate_test_data(user, 2, seed=7) ===
{"entity": "user", "count": 2, "seed": 7, "rows": [...]}

=== resources/list ===
["test-plan-template://v1"]
```

`pytest -q` → `24 passed`. CI (`.github/workflows/ci.yml`) runs the same
plus a byte-compile check and the client demo as a mock-mode smoke test.

## Plugging this into Claude Desktop / any MCP client

Any MCP-compatible client can use this server over stdio. For Claude
Desktop, add it to your config file (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "qa-tools": {
      "command": "/absolute/path/to/mcp-server-lab/.venv/bin/python",
      "args": ["/absolute/path/to/mcp-server-lab/src/qa_server.py"]
    }
  }
}
```

Restart Claude Desktop and the three QA tools plus the test-plan resource
show up in its tool picker — ask it to "run test case TC-LOGIN-001" or
"search the bug database for checkout bugs" and it will call this server.
The same works for any MCP client (IDE agents, custom harnesses) that
supports stdio servers.

## Offline vs. production — honest notes

- **Runs offline:** the server, the client demo, and all 24 tests. The
  system under test is a mock (expected vs. simulated actuals in
  `test_cases.json`), the bug DB is a static JSON file, and test data is
  seeded PRNG output. Nothing phones home.
- **Not production:** there is no auth, no real SUT integration, and the
  stdio transport means one client per server process. A production version
  would put this behind the Streamable HTTP transport, add API-key auth,
  wire `run_test_case` to a real test runner (pytest/JUnit XML), back
  `search_bug_db` with Jira/Linear, and persist generated data to a proper
  test-data service.

## Roadmap

- [ ] Streamable HTTP transport + API-key auth for multi-client use
- [ ] `run_test_case` backed by a real pytest run (JUnit XML parsed to steps)
- [ ] `search_bug_db` backed by a live Jira/Linear query with local fallback
- [ ] Prompt templates (`/mcp.prompt`) for "triage these failures" workflows
- [ ] Contract tests against the MCP spec's schema validation suite

## Repo layout

```
mcp-server-lab/
├── src/
│   ├── qa_server.py      # MCPServer: 3 tools + 1 resource (stdio)
│   └── client_demo.py    # real MCP client: lists/calls everything
├── tests/
│   ├── test_schemas.py        # tool/resource schemas via protocol
│   ├── test_tools_protocol.py # end-to-end tool calls via protocol
│   └── test_errors_resources.py # error paths + resource reads
├── data/
│   ├── test_cases.json
│   └── bugs.json
├── .github/workflows/ci.yml
├── requirements.txt  # mcp==2.2.0, pytest
└── .env.example
```

One MCP 2.x gotcha I documented in code comments: test bodies must not let
exceptions escape the client's `async with` blocks — teardown deadlocks
otherwise. Error-path tests therefore catch inside the session.
