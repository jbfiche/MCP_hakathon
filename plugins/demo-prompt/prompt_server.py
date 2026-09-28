"""A prompt: a canned request a *person* picks from the host's menu.

The model does not decide to use a prompt; the user does (in Claude Code it appears as a
slash command). A prompt function returns the text of the request, or a list of messages.
Its parameters become the arguments the host asks the user for.

Run it:
    uv run --with "mcp[cli]" mcp dev prompt_server.py
"""

from typing import Annotated

from pydantic import Field

from mcp.server import MCPServer

mcp = MCPServer(
    "Demo: prompt",
    instructions="One prompt, summarise_gene, that a user can pick from the host's prompt menu.",
)


@mcp.prompt(title="Summarise a gene's role in cancer")
def summarise_gene(
    gene: Annotated[str, Field(description="An HGNC gene symbol, e.g. TP53.")],
) -> str:
    """Ask for a three-bullet summary of one gene's role in cancer."""
    return (
        f"In three bullet points, summarise the role of {gene} in cancer: "
        "whether it acts as an oncogene or a tumour suppressor, the tumour types where it "
        "is most often altered, and one approved or investigational therapy that targets it "
        "or its pathway. Say explicitly when something is uncertain."
    )


if __name__ == "__main__":
    mcp.run()
