"""Call MCP tools locally without requiring the browser-based Inspector."""

from __future__ import annotations

import asyncio
import argparse
import json

from mcp import Client

from chromatin_trace_mcp.server import mcp

READ_ONLY_TOOL_NAMES = ("inspect_current_trace", "trace_stats")
TOOL_NAMES = (
    *READ_ONLY_TOOL_NAMES,
    "filter_traces",
    "trace_to_matrix",
    "localization_analyzer",
    "list_datasets",
    "compare_datasets",
    "duplicate_statistics",
    "localization_quality_summary",
    "snr_filter_sweep",
)


def parse_arguments() -> argparse.Namespace:
    """Select one MCP tool or run every read-only check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tool",
        nargs="?",
        choices=(*TOOL_NAMES, "read-only"),
        default="read-only",
        help="MCP tool to call (default: read-only checks).",
    )
    parser.add_argument("--first-dataset", help="First dataset for comparison.")
    parser.add_argument("--second-dataset", help="Second dataset for comparison.")
    parser.add_argument(
        "--dataset-name",
        help="Dataset for localization_quality_summary; defaults to --first-dataset.",
    )
    parser.add_argument(
        "--table-kind",
        choices=("trace", "localization"),
        default="trace",
        help="Table for duplicate_statistics (default: trace).",
    )
    parser.add_argument(
        "--thresholds",
        default="5,7.5,10",
        help="Comma-separated SNR thresholds for snr_filter_sweep.",
    )
    parser.add_argument(
        "--intensity-columns",
        default="mean_intensity,flux",
        help="Comma-separated localization columns for quality/sweep tools.",
    )
    return parser.parse_args()


async def check_server(
    selected_tool: str,
    first_dataset: str | None = None,
    second_dataset: str | None = None,
    table_kind: str = "trace",
    dataset_name: str | None = None,
    thresholds: str = "5,7.5,10",
    intensity_columns: str = "mean_intensity,flux",
) -> None:
    """Connect in-process, call the selected MCP tool(s), and display results."""
    tools_to_call = (
        READ_ONLY_TOOL_NAMES if selected_tool == "read-only" else (selected_tool,)
    )
    output: dict[str, object] = {}
    async with Client(mcp, raise_exceptions=True) as client:
        for tool_name in tools_to_call:
            tool_arguments: dict[str, object] = {}
            if tool_name == "compare_datasets":
                if not first_dataset or not second_dataset:
                    raise SystemExit(
                        "compare_datasets requires --first-dataset and "
                        "--second-dataset."
                    )
                tool_arguments = {
                    "first_dataset": first_dataset,
                    "second_dataset": second_dataset,
                }
            elif tool_name == "duplicate_statistics":
                if not first_dataset or not second_dataset:
                    raise SystemExit(
                        "duplicate_statistics requires --first-dataset and "
                        "--second-dataset."
                    )
                tool_arguments = {
                    "first_dataset": first_dataset,
                    "second_dataset": second_dataset,
                    "table_kind": table_kind,
                }
            elif tool_name == "localization_quality_summary":
                selected_dataset = dataset_name or first_dataset
                if not selected_dataset:
                    raise SystemExit(
                        "localization_quality_summary requires --dataset-name or "
                        "--first-dataset."
                    )
                tool_arguments = {
                    "dataset_name": selected_dataset,
                    "intensity_columns": [
                        column.strip()
                        for column in intensity_columns.split(",")
                        if column.strip()
                    ],
                }
            elif tool_name == "snr_filter_sweep":
                if not first_dataset or not second_dataset:
                    raise SystemExit(
                        "snr_filter_sweep requires --first-dataset and "
                        "--second-dataset."
                    )
                tool_arguments = {
                    "first_dataset": first_dataset,
                    "second_dataset": second_dataset,
                    "thresholds": [
                        float(value.strip())
                        for value in thresholds.split(",")
                        if value.strip()
                    ],
                    "intensity_columns": [
                        column.strip()
                        for column in intensity_columns.split(",")
                        if column.strip()
                    ],
                }
            result = await client.call_tool(tool_name, tool_arguments)
            if result.is_error:
                message = "\n".join(
                    block.text for block in result.content if hasattr(block, "text")
                )
                raise SystemExit(f"MCP tool {tool_name!r} failed: {message}")
            output[tool_name] = result.structured_content
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    arguments = parse_arguments()
    asyncio.run(
        check_server(
            arguments.tool,
            arguments.first_dataset,
            arguments.second_dataset,
            arguments.table_kind,
            arguments.dataset_name,
            arguments.thresholds,
            arguments.intensity_columns,
        )
    )
