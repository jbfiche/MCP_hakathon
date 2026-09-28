import pytest
from mcp import Client, MCPError
from mcp.types import ElicitResult

from elicitation_server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_the_answer_is_not_a_tool_argument() -> None:
    async with Client(mcp) as client:
        tool = (await client.list_tools()).tools[0]
    assert tool.name == "greet"
    assert tool.input_schema.get("properties", {}) == {}


@pytest.mark.anyio
async def test_user_accepts() -> None:
    questions: list[str] = []

    async def answer(context, params) -> ElicitResult:
        questions.append(params.message)
        return ElicitResult(action="accept", content={"name": "Ada"})

    async with Client(mcp, elicitation_callback=answer) as client:
        result = await client.call_tool("greet", {})
    assert result.content[0].text == "Hello, Ada!"
    assert questions == ["The demo-elicitation server would like to know your name."]


@pytest.mark.anyio
async def test_user_declines() -> None:
    async def answer(context, params) -> ElicitResult:
        return ElicitResult(action="decline")

    async with Client(mcp, elicitation_callback=answer) as client:
        result = await client.call_tool("greet", {})
    assert result.content[0].text == "No name given. Hello, stranger!"


@pytest.mark.anyio
async def test_a_host_without_elicitation_gets_a_protocol_error() -> None:
    # No elicitation_callback: this client does not declare the capability, so the server
    # refuses the call as an MCP error rather than pretending it asked.
    async with Client(mcp) as client:
        with pytest.raises(MCPError, match="form elicitation"):
            await client.call_tool("greet", {})
