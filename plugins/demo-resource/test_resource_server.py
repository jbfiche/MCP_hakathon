import json

import pytest
from mcp import Client

from resource_server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


@pytest.mark.anyio
async def test_one_resource_one_template_no_tools(client: Client) -> None:
    assert (await client.list_tools()).tools == []
    assert [r.uri for r in (await client.list_resources()).resources] == ["genes://panel"]
    templates = (await client.list_resource_templates()).resource_templates
    assert [t.uri_template for t in templates] == ["genes://panel/{symbol}"]


@pytest.mark.anyio
async def test_read_the_panel_as_json(client: Client) -> None:
    result = await client.read_resource("genes://panel")
    content = result.contents[0]
    assert content.mime_type == "application/json"
    assert json.loads(content.text)["KRAS"] == "oncogene"


@pytest.mark.anyio
async def test_read_one_gene_through_the_template(client: Client) -> None:
    result = await client.read_resource("genes://panel/tp53")
    assert result.contents[0].text == "TP53 is a tumour suppressor."


@pytest.mark.anyio
async def test_unknown_gene_is_a_resource_error() -> None:
    from mcp import MCPError

    async with Client(mcp) as client:
        with pytest.raises(MCPError, match="not in the panel"):
            await client.read_resource("genes://panel/EGFR")
