import pytest
from mcp import Client

from tools_server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


@pytest.mark.anyio
async def test_lists_four_tools(client: Client) -> None:
    tools = await client.list_tools()
    assert sorted(t.name for t in tools.tools) == ["add", "divide", "multiply", "subtract"]


@pytest.mark.anyio
async def test_add_returns_a_typed_result(client: Client) -> None:
    result = await client.call_tool("add", {"a": 2, "b": 3})
    assert result.is_error is False
    assert result.structured_content == {"result": 5.0}


@pytest.mark.anyio
async def test_divide(client: Client) -> None:
    result = await client.call_tool("divide", {"a": 1, "b": 4})
    assert result.structured_content == {"result": 0.25}


@pytest.mark.anyio
async def test_divide_by_zero_is_a_tool_error_the_model_can_read(client: Client) -> None:
    result = await client.call_tool("divide", {"a": 1, "b": 0})
    assert result.is_error is True
    assert "Cannot divide by zero" in result.content[0].text
    assert result.structured_content is None
