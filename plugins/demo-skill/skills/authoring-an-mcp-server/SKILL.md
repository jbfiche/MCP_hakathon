---
name: authoring-an-mcp-server
description: Write, review or debug an MCP server in Python using the MCP Python SDK v2 (mcp>=2.1, protocol revision 2026-07-28). Use when the user wants to expose a database, analysis script, simulation, CLI tool or Python library to an LLM agent as MCP tools, resources or prompts; when they ask how to start an MCP server, what MCPServer is, or why their tool is not being called correctly; and when migrating a v1 FastMCP server to v2. Written for cancer systems-biology and bioinformatics work.
license: MIT
compatibility: Requires Python 3.10+ and uv (or pip). No network access needed for the offline demos.
metadata:
  author: sysbio-curie
  version: "0.1.0"
---

# Authoring an MCP server

## Before writing any code, check whether it already exists

Someone has probably already wrapped the database. Read
[`inventory/README.md`](https://github.com/sysbio-curie/MCP_Hackaton/blob/main/inventory/README.md)
first: it lists the MCP servers that already cover UniProt, ChEMBL, Ensembl, KEGG, Reactome,
STRING, PubMed, ClinicalTrials.gov, Open Targets, AlphaFold, the PDB, MaBoSS, NeKo and
PhysiCell/PhysiBoSS.

Build a new server when the thing you want to expose is **yours**: your analysis, your pipeline,
your lab's data, your model. That is also the most valuable kind to build.

## The one import that matters

SDK v2 entry point — **not** `FastMCP`, which was v1 and is gone:

```python
from mcp.server import MCPServer

mcp = MCPServer("Server Name", instructions="What this server is for.")
```

Run it with `mcp.run()` (stdio by default) under `if __name__ == "__main__":`.

## Choose the right primitive

Get this wrong and the tool list grows to forty entries and the model picks badly.

| Primitive | Who decides to use it | Use for |
| --- | --- | --- |
| `@mcp.tool()` | the **model**, mid-reasoning | an action or a query the agent should choose to run |
| `@mcp.resource(uri)` | the **application** | reference data the host loads into context: a model spec, a config, a document |
| `@mcp.prompt()` | a **person**, from a menu | a canned analysis request the user invokes deliberately |

A large reference document should be a **resource**, not a tool that returns it.

## The tool contract checklist

Work through this for every tool. It is the difference between a tool that works when you call it
by hand and one an agent uses reliably.

1. **Docstring** — the model reads it. Say what the tool does and when to use it.
2. **Type hints** — they *are* the input schema, enforced before your function runs.
3. **Constraints** — `Annotated[int, Field(ge=1, le=50)]` and `Literal["BRCA", "LUAD"]`. A
   rejected argument comes back as a message the model reads and retries against. This is the
   cheapest reliability win available.
4. **Descriptions per argument** — `Field(description=...)` for anything not obvious from the name.
5. **A typed return** — `-> SomePydanticModel` publishes an `output_schema` and fills
   `structured_content` for the application, not just prose for the model.
6. **`raise ToolError`, never `return "error: ..."`** — a returned string has `is_error=False`, so
   the failure looks like an answer. Put the recovery path in the message: name the valid options.
7. **Annotations** — `ToolAnnotations(read_only_hint=True, open_world_hint=False)` on read-only
   tools, so hosts know they need not ask the user first. Hints, not security.
8. **`async def`** for I/O. A plain `def` is fine and runs in a thread.

## Errors: which exception

One question decides it: **could a smarter model have avoided this?**

- **Yes → `ToolError`** (`from mcp.server.mcpserver.exceptions import ToolError`). Returns a
  result with `is_error=True` and your message where the model reads it. This is almost always
  what you want: a misspelled gene, a missing record, an upstream timeout.
- **No → `MCPError`** (`from mcp import MCPError`, with a code from `mcp.types`). The request
  itself fails; the host sees it and the model gets nothing.
- **Anything else** is a crash: logged with a traceback on the server, and the model is told only
  that the call failed. Your internals never leak to it.

`ResourceError` is the resource equivalent of `ToolError`.

## Test it in-process

There is no reason to test an MCP server through a subprocess:

```python
import pytest
from mcp import Client
from my_server import mcp

@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c

@pytest.mark.anyio
async def test_it(client: Client) -> None:
    result = await client.call_tool("my_tool", {"gene": "TP53"})
    assert result.structured_content == {...}
```

Assert on **protocol-visible** behaviour: the published schema, `is_error`,
`structured_content`. `raise_exceptions=True` is for tests only — it stops the server
sanitising unexpected failures so you can see the real message.

Inspect it by hand with `uv run --with "mcp[cli]" mcp dev my_server.py`.

## Mistakes that cost people an afternoon

- Using `FastMCP`. That is v1. Use `MCPServer`.
- `print()` in a stdio server. **stdout belongs to the protocol.** Use `logging`, which goes to
  stderr; `logger.info("...")` is the same one line of effort.
- Returning a class with no annotations on its class body. The SDK finds no schema, gives up
  **silently**, and the model reads the object's `repr`. Use a Pydantic model, or pass
  `structured_output=True` to turn it into an import-time error.
- A URI template placeholder that does not match the parameter name. This one at least fails at
  import time.
- `ctx.elicit()` on a current connection. Server-initiated requests do not exist on the
  2026-07-28 revision. Use a `Resolve(...)` resolver, which works on every connection.
- Forgetting that `Context` is injected by **annotation**, not by parameter name, and never
  appears in the input schema.

## Working examples

[`plugins/`](https://github.com/sysbio-curie/MCP_Hackaton/tree/main/plugins) has five
one-feature, tested servers, each with its own README:

- `plugins/demo-tools` — tools and the `ToolError` contract, applied.
- `plugins/demo-progress` — a tool that reports progress mid-call.
- `plugins/demo-elicitation` — a tool that asks the user something via a `Resolve` resolver.
- `plugins/demo-prompt` — a prompt with no tools.
- `plugins/demo-resource` — a resource and resource template with no tools.

## More detail

- [`references/sdk-v2-cheatsheet.md`](references/sdk-v2-cheatsheet.md) — imports, signatures and
  the `Context` surface, in one page.
- The SDK documentation is at <https://py.sdk.modelcontextprotocol.io/> and is genuinely good;
  every example in it is exercised by the SDK's own test suite.
