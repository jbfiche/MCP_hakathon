"""Shared adapter for native trace_stats; no duplicate statistical calculations."""
import io
import re
from contextlib import redirect_stdout
from importlib.metadata import version
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError
from traceratops import trace_stats as native


def count_from_report(report, label):
    match = re.search(rf"Number of {re.escape(label)}:\s*(\d+)", report)
    if match is None:
        raise ToolError(
            "traceratops completed but its trace_stats report had an unexpected "
            f"format: could not find the number of {label}. The installed "
            "traceratops version may be incompatible with this MCP adapter."
        )
    return int(match.group(1))


def compute_statistics(path, *, transcript=None):
    """Retain the existing public wrapper's result fields and native error handling."""
    captured = transcript if transcript is not None else io.StringIO()
    try:
        with redirect_stdout(captured):
            native.compute_trace_statistics(path)
    except SystemExit as exc:
        raise ToolError(f"traceratops trace_stats stopped before completing (exit code {exc.code}).") from exc
    except Exception as exc:
        raise ToolError(f"traceratops trace_stats failed: {exc}") from exc
    report = captured.getvalue().strip()
    return dict(source_file=str(Path(path).resolve()), traceratops_version=version('traceratops'),
                unique_roi_count=count_from_report(report, 'unique ROIs'),
                unique_trace_count=count_from_report(report, 'unique chromatin traces'),
                unique_barcode_count=count_from_report(report, 'unique barcodes'),
                traceratops_report=report)
