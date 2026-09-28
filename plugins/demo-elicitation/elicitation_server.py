"""Elicitation: a tool that asks the user a question before it answers.

On the 2026-07-28 protocol revision the server never calls the client directly. Instead a
*resolver* returns `Elicit(message, Schema)`; the SDK hands the question to the host, and
when the user has answered, the tool body runs with the outcome injected into the parameter
that carries `Resolve(resolver)`. The host never sees that parameter in the input schema.

Run it:
    uv run --with "mcp[cli]" mcp dev elicitation_server.py
"""

from typing import Annotated

from pydantic import BaseModel, Field

from mcp.server import MCPServer
from mcp.server.mcpserver import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
    Elicit,
    ElicitationResult,
    Resolve,
)

mcp = MCPServer(
    "Demo: elicitation",
    instructions="One tool, greet, that asks the user for their name before greeting them.",
)


class Name(BaseModel):
    """The form the host shows the user. Only flat, primitive fields are allowed."""

    name: Annotated[str, Field(description="What should the server call you?")]


def ask_name() -> Elicit[Name]:
    """The resolver: it asks; the framework does the round-trip."""
    return Elicit("The demo-elicitation server would like to know your name.", Name)


@mcp.tool()
def greet(answer: Annotated[ElicitationResult[Name], Resolve(ask_name)]) -> str:
    """Greet the user by name. The server asks the user for the name; you do not pass it."""
    match answer:
        case AcceptedElicitation(data=Name(name=name)):
            return f"Hello, {name}!"
        case DeclinedElicitation():
            return "No name given. Hello, stranger!"
        case CancelledElicitation():
            return "The question was cancelled, so no greeting."
    return "unreachable"


if __name__ == "__main__":
    mcp.run()
