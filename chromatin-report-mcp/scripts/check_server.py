"""Generate a sample report through the MCP protocol."""

import asyncio
import json
import os
from pathlib import Path

from mcp import Client

from chromatin_report_mcp.server import mcp


SAMPLE_COMPARISON = {
    "first": {
        "dataset_name": "experiment_A", "trace_row_count": 100,
        "trace_count": 10, "roi_count": 2, "barcode_count": 3,
        "barcodes": ["1", "2", "3"], "median_rows_per_trace": 10.0,
        "coordinate_missing_fraction": 0.0, "duplicate_trace_barcode_rows": 0,
        "localization_row_count": None, "localization_barcode_count": None,
        "median_localization_snr": None,
    },
    "second": {
        "dataset_name": "experiment_B", "trace_row_count": 120,
        "trace_count": 12, "roi_count": 2, "barcode_count": 3,
        "barcodes": ["1", "2", "3"], "median_rows_per_trace": 10.0,
        "coordinate_missing_fraction": 0.0, "duplicate_trace_barcode_rows": 0,
        "localization_row_count": None, "localization_barcode_count": None,
        "median_localization_snr": None,
    },
    "status": "compatible_with_warnings", "comparable": True,
    "shared_barcodes": ["1", "2", "3"], "only_in_first": [],
    "only_in_second": [], "same_columns": True,
    "columns_only_in_first": [], "columns_only_in_second": [],
    "coordinate_unit_first": "micron", "coordinate_unit_second": "micron",
    "reasons": ["Required fields are compatible."],
    "warnings": ["This is a sample report used to test the report MCP."],
}


async def main() -> None:
    async with Client(mcp, raise_exceptions=True) as client:
        result = await client.call_tool(
            "write_comparison_report",
            {
                "comparison": SAMPLE_COMPARISON,
                "report_title": "Sample chromatin comparison",
            },
        )
    if result.is_error:
        raise SystemExit("Report tool failed")
    print(json.dumps(result.structured_content, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
