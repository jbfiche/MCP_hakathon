import pytest
from mcp import Client

from prompt_server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


@pytest.mark.anyio
async def test_no_tools_one_prompt(client: Client) -> None:
    assert (await client.list_tools()).tools == []
    prompts = (await client.list_prompts()).prompts
    assert [p.name for p in prompts] == ["summarise_gene"]
    assert prompts[0].title == "Summarise a gene's role in cancer"
    assert [a.name for a in prompts[0].arguments] == ["gene"]
    assert prompts[0].arguments[0].required is True


@pytest.mark.anyio
async def test_get_prompt_fills_the_argument(client: Client) -> None:
    result = await client.get_prompt("summarise_gene", {"gene": "TP53"})
    assert len(result.messages) == 1
    assert result.messages[0].role == "user"
    assert "the role of TP53 in cancer" in result.messages[0].content.text
