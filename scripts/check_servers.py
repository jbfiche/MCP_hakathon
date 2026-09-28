"""Launch every plugin's MCP server exactly as an MCP host would, over real stdio.

Use this to check that every plugin's mcp.json config actually works before you hand the
repo to anyone:

    uv run python scripts/check_servers.py

For every `plugins/*/mcp.json`, this expands `${PLUGIN_ROOT}` to that plugin's own
directory (absolute path) -- no environment variable needed, unlike the single-plugin
predecessor this file replaces -- launches each declared server, lists its tools,
resources, resource templates and prompts, and prints OK/FAIL per server. Exits non-zero
if any server fails to start or complete the MCP handshake.
"""
import json, os, pathlib, anyio
from mcp import Client, StdioServerParameters

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def expand(v: str, plugin_root: pathlib.Path) -> str:
    return v.replace("${PLUGIN_ROOT}", str(plugin_root))


async def check_server(plugin_root: pathlib.Path, name: str, spec: dict) -> bool:
    params = StdioServerParameters(
        command=expand(spec["command"], plugin_root),
        args=[expand(a, plugin_root) for a in spec.get("args", [])],
        env={**os.environ, **spec.get("env", {})},
    )
    try:
        async with Client(params) as c:
            tools = [t.name for t in (await c.list_tools()).tools]
            res = [r.uri for r in (await c.list_resources()).resources]
            tmpl = [t.uri_template for t in (await c.list_resource_templates()).resource_templates]
            prompts = [p.name for p in (await c.list_prompts()).prompts]
        print(f"OK   {plugin_root.name}/{name}")
        print(f"       tools:     {tools}")
        print(f"       resources: {res}  templates: {tmpl}")
        print(f"       prompts:   {prompts}")
        return True
    except Exception as e:
        print(f"FAIL {plugin_root.name}/{name}: {type(e).__name__}: {e}")
        return False


async def main() -> None:
    failures = 0
    checked = 0
    for mcp_json in sorted((REPO_ROOT / "plugins").glob("*/mcp.json")):
        plugin_root = mcp_json.parent
        cfg = json.loads(mcp_json.read_text())
        for name, spec in cfg.get("mcpServers", {}).items():
            checked += 1
            if not await check_server(plugin_root, name, spec):
                failures += 1
    if not checked:
        print("no plugins/*/mcp.json found")
    raise SystemExit(1 if failures else 0)


anyio.run(main)
