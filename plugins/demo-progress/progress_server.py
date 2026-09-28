"""Progress: a slow tool that tells the host how far along it is.

Ask for the `Context` by annotating a parameter with it; the host never sees that parameter.
`ctx.report_progress(progress, total, message)` sends a progress notification each step.
It is a no-op when the host did not ask for progress, so it is always safe to call.

Run it:
    uv run --with "mcp[cli]" mcp dev progress_server.py
"""

from typing import Annotated

import anyio
from pydantic import Field

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

mcp = MCPServer(
    "Demo: progress",
    instructions="One slow tool, count_to, that reports progress after every step.",
)


@mcp.tool()
async def count_to(
    ctx: Context,
    n: Annotated[int, Field(ge=1, le=100, description="How many steps to take.")] = 10,
    delay: Annotated[float, Field(ge=0, le=5, description="Seconds to wait per step.")] = 1.0,
) -> str:
    """Count from 1 to n, waiting `delay` seconds per step and reporting progress each time."""
    for i in range(1, n + 1):
        await anyio.sleep(delay)
        await ctx.report_progress(progress=i, total=n, message=f"step {i} of {n}")
    return f"Counted to {n}."


if __name__ == "__main__":
    mcp.run()
