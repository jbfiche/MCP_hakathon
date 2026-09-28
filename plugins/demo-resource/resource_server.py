"""Resources: data the *application* loads into context, addressed by URI.

Two forms. A fixed URI (`genes://panel`) is a plain resource. A URI with a `{placeholder}`
is a resource template: the placeholder name must match the function's parameter name.
Return `str` for text, `bytes` for a blob, or anything JSON-serialisable for JSON.

Run it:
    uv run --with "mcp[cli]" mcp dev resource_server.py
"""

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError

mcp = MCPServer(
    "Demo: resource",
    instructions="A five-gene panel as resources: genes://panel and genes://panel/{symbol}.",
)

ROLES = {
    "TP53": "tumour suppressor",
    "KRAS": "oncogene",
    "BRAF": "oncogene",
    "PTEN": "tumour suppressor",
    "RB1": "tumour suppressor",
}


@mcp.resource("genes://panel", mime_type="application/json")
def panel() -> dict[str, str]:
    """Every gene in the panel and its role."""
    return ROLES


@mcp.resource("genes://panel/{symbol}", mime_type="text/plain")
def gene(symbol: str) -> str:
    """One gene of the panel. `symbol` comes from the URI."""
    role = ROLES.get(symbol.upper())
    if role is None:
        raise ResourceError(f"{symbol.upper()} is not in the panel. Read genes://panel for the list.")
    return f"{symbol.upper()} is a {role}."


if __name__ == "__main__":
    mcp.run()
