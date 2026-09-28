import pytest
from mcp import Client

from progress_server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


@pytest.mark.anyio
async def test_context_is_not_part_of_the_input_schema(client: Client) -> None:
    tool = (await client.list_tools()).tools[0]
    assert tool.name == "count_to"
    assert set(tool.input_schema["properties"]) == {"n", "delay"}


@pytest.mark.anyio
async def test_progress_is_reported_once_per_step(client: Client) -> None:
    seen: list[tuple[float, float | None, str | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        seen.append((progress, total, message))

    result = await client.call_tool("count_to", {"n": 3, "delay": 0}, progress_callback=on_progress)
    assert result.content[0].text == "Counted to 3."
    assert seen == [(1, 3, "step 1 of 3"), (2, 3, "step 2 of 3"), (3, 3, "step 3 of 3")]


@pytest.mark.anyio
async def test_progress_is_a_no_op_when_nobody_listens(client: Client) -> None:
    result = await client.call_tool("count_to", {"n": 2, "delay": 0})
    assert result.is_error is False
