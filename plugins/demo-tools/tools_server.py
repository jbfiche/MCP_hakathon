"""Tools, and the one error the model is allowed to see.

Four arithmetic tools. `divide` shows the MCP way to fail: raise `ToolError`, so the
result comes back with `is_error=True` and a message the model can read and act on.

Run it:
    uv run --with "mcp[cli]" mcp dev tools_server.py
"""

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer(
    "Demo: tools",
    instructions="Four arithmetic tools. divide fails with a tool error when the divisor is 0.",
)


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b. Fails with a tool error when b is 0."""
    if b == 0:
        # Not `return "error: ..."` (that would look like a valid answer) and not a bare
        # ZeroDivisionError (that would be a crash the model learns nothing from).
        raise ToolError("Cannot divide by zero: pass a non-zero divisor b.")
    return a / b


if __name__ == "__main__":
    mcp.run()
