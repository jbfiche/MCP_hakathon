# demo-tools

The smallest useful MCP server: four **tools** (`add`, `subtract`, `multiply`, `divide`) and
one deliberate failure. `divide` by zero raises `ToolError`, which is the MCP way to say
"this call failed, here is why" so that the model can read the message and try again.

The whole syntax is in [`tools_server.py`](tools_server.py): `MCPServer(...)`, `@mcp.tool()`,
type hints as the input schema, a docstring as the description, and `raise ToolError(...)`.

## Try it in your agent

Install the plugin (see the [repository README](../../README.md#install-the-demo-plugins)),
then ask:

> Use the demo-tools server to divide 10 by 4, then divide 1 by 0.

The first call returns `2.5`. The second comes back as an **error result**, not a crash: the
agent sees `Cannot divide by zero: pass a non-zero divisor b.` and should explain that to you
rather than retry blindly. Compare this with what a Python `ZeroDivisionError` would have
looked like: the model would only be told "the tool failed".

## Run and test it by hand

```bash
cd plugins/demo-tools
uv run --with "mcp[cli]" mcp dev tools_server.py     # MCP Inspector in the browser
```

```bash
uv run pytest plugins/demo-tools                     # from the repository root
```
