"""Call one Step 0 tool through the existing local MCP server."""
import argparse
import asyncio
import json
from pathlib import Path
from mcp import Client
from chromatin_trace_mcp.server import mcp


async def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('experiment_root')
    p.add_argument('--tool', default='run_experiment_validation', choices=['inspect_experiment_directory', 'discover_roi_files', 'validate_experiment_structure', 'validate_ecsv_tables', 'run_experiment_validation'])
    p.add_argument('--rules', type=Path, help='Optional explicit JSON validation policy')
    args = p.parse_args()
    arguments = {'experiment_root': args.experiment_root}
    if args.rules:
        arguments['rules'] = json.loads(args.rules.read_text())
    async with Client(mcp, raise_exceptions=True) as client:
        result = await client.call_tool(args.tool, arguments)
        print(json.dumps(result.structured_content, indent=2))
        if result.is_error:
            raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
