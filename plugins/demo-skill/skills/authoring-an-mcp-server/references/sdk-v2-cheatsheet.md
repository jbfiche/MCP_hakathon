# MCP Python SDK v2 cheat sheet

Verified against `mcp` 2.1.1. Protocol revision **2026-07-28**.

## Install

```bash
uv add "mcp[cli]"          # or: pip install "mcp[cli]"
```

Python 3.10+. The `[cli]` extra provides the `mcp` command (`mcp dev`, `mcp run`).

## Imports

```python
from mcp.server import MCPServer                          # the server
from mcp.server.mcpserver import Context                  # per-request context
from mcp.server.mcpserver.exceptions import ToolError, ResourceError
from mcp.server.mcpserver.prompts.base import Message, UserMessage, AssistantMessage
from mcp.types import ToolAnnotations, INVALID_PARAMS      # protocol types and JSON-RPC codes
from mcp import Client, MCPError, StdioServerParameters    # client, protocol error, stdio params
```

## `MCPServer(...)`

Frequently used arguments:

| Argument | Purpose |
| --- | --- |
| `name` | server name shown to hosts |
| `instructions` | what the server is for; hosts put this in the system prompt |
| `title`, `version`, `website_url`, `icons` | presentation metadata |
| `lifespan` | async context manager for startup/shutdown state |
| `middleware` | sequence of `ServerMiddleware` for cross-cutting concerns |
| `token_verifier`, `auth` | authorization |
| `log_level` | `"DEBUG"`…`"CRITICAL"`, default `"INFO"` |

## Decorators

```python
@mcp.tool(name=None, title=None, description=None, annotations=None,
          icons=None, meta=None, structured_output=None)

@mcp.resource(uri, *, name=None, title=None, description=None,
              mime_type=None, icons=None, annotations=None, meta=None, security=None)

@mcp.prompt(name=None, title=None, description=None, icons=None)

@mcp.completion()          # server-side autocomplete for prompt/template arguments
```

Registered imperatively: `mcp.add_tool(fn, ...)`, `mcp.add_resource(...)`,
`mcp.add_prompt(...)`, and `mcp.remove_tool(name)` / `mcp.remove_prompt(name)`.

## Return-value rules

| You return | `content` (for the model) | `structured_content` (for the app) |
| --- | --- | --- |
| `str`, `int`, `float`, `bool`, `bytes`, `None` | the value as text | `{"result": value}` |
| a Pydantic model / dataclass / `TypedDict` / annotated class | JSON text | the object, field for field |
| `list` / `tuple` / union | JSON text | `{"result": [...]}` |
| `TextContent`, `Image`, `Audio`, `EmbeddedResource` | the block itself | `None` (opted out) |
| a class with **no class-body annotations** | the object's `repr` | `None` — **silent failure** |

`structured_output=False` opts a tool out entirely. `structured_output=True` makes an
underivable schema a hard error at import time.

For **resources**: `str` → text, `bytes` → base64 blob, anything else JSON-serialisable → JSON
text. `mime_type=` is a label you declare; it defaults to `text/plain` and is never inferred.

## The `Context`

Ask for it by annotating any parameter (in a tool, resource or prompt) with `Context`. The
parameter name is yours; it never appears in the input schema.

```python
@mcp.tool()
async def analyse(gene: str, ctx: Context) -> str: ...
```

| Member | Purpose |
| --- | --- |
| `ctx.request_id` | id of the request being served |
| `await ctx.read_resource(uri)` | read one of this server's own resources |
| `await ctx.report_progress(progress, total=None, message=None)` | progress must strictly increase |
| `await ctx.elicit(message, schema)` | **legacy connections only** — prefer a `Resolve` resolver |
| `ctx.session` | channel back to the client (`send_tool_list_changed()`, …) |
| `ctx.headers` | transport headers, or `None` on stdio. Client input — never an identity |
| `ctx.request_context.lifespan_context` | whatever your `lifespan` yielded |

Injection happens only for the function you registered. Pass `ctx` down to helpers as an
ordinary argument; there is no ambient current-context lookup.

**Logging is not on the Context.** Use the standard library: `logging.getLogger(__name__)`.
Output goes to stderr, which is correct for stdio servers.

## Elicitation on current connections

There are no server-initiated requests on 2026-07-28, so `ctx.elicit()` fails there. A
**resolver** works on every connection:

```python
from typing import Annotated
from mcp.server.mcpserver import (
    AcceptedElicitation, CancelledElicitation, DeclinedElicitation,
    Elicit, ElicitationResult, Resolve,
)

async def confirm(path: str) -> Confirm | Elicit[Confirm]:
    if nothing_to_confirm:
        return Confirm(ok=True)              # no round-trip
    return Elicit("Are you sure?", Confirm)

@mcp.tool()
async def act(path: str,
              answer: Annotated[ElicitationResult[Confirm], Resolve(confirm)]) -> str:
    match answer:
        case AcceptedElicitation(data=Confirm(ok=True)): ...
        case DeclinedElicitation() | CancelledElicitation(): ...
```

## Lifespan

```python
@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[AppContext]:
    db = await Database.connect()
    try:
        yield AppContext(db=db)
    finally:
        await db.disconnect()

mcp = MCPServer("Name", lifespan=lifespan)
# in a handler: ctx.request_context.lifespan_context.db
```

Runs **once**, before the first request and after the last. Every request shares the object.

## Transports

```python
mcp.run()                                             # stdio
mcp.run("streamable-http", host="127.0.0.1", port=8000)
mcp.run("sse", ...)                                   # deprecated, legacy clients only
```

Mount into an existing ASGI app with `mcp.streamable_http_app()`; the host app's lifespan must
run the session manager.

## Client

```python
from mcp import Client, StdioServerParameters

async with Client(mcp) as c:                  # in-process, for tests
async with Client(StdioServerParameters(command="uv", args=[...])) as c:   # subprocess
```

Useful keyword arguments: `raise_exceptions` (tests), `sampling_callback`,
`elicitation_callback`, `list_roots_callback`, `logging_callback`, `mode` (`"auto"` /
`"legacy"`), `cache`. `call_tool(...)` accepts `progress_callback=`.

## v1 → v2, the changes you will actually hit

| v1 | v2 |
| --- | --- |
| `from mcp.server.fastmcp import FastMCP` | `from mcp.server import MCPServer` |
| `resource.uri` was `AnyUrl` | plain `str` |
| transport params in the constructor | passed to `run()` |
| returning a `dict`/`list` auto-wrapped in the low-level server | construct the result yourself |
| server-initiated elicitation always available | resolvers; `ctx.elicit()` is legacy-only |

The full list is at <https://py.sdk.modelcontextprotocol.io/migration/>.
