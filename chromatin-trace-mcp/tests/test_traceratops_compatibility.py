"""Compatibility contract between this MCP project and traceratops."""

from __future__ import annotations

import os
from importlib.metadata import distribution, version
from pathlib import Path

import pytest
from astropy.table import Table
from traceratops.core.chromatin_trace_table import (
    ChromatinTraceTable,
    read_table_from_ecsv,
    save_table_to_ecsv,
)
from traceratops.trace_stats import compute_trace_statistics

from chromatin_trace_mcp.server import TRACE_PATH_ENV

EXPECTED_COLUMNS = [
    "Spot_ID",
    "Trace_ID",
    "x",
    "y",
    "z",
    "Chrom",
    "Chrom_Start",
    "Chrom_End",
    "ROI #",
    "Mask_id",
    "Barcode #",
    "label",
]

CORE_TRACERATOPS_COMMANDS = {
    "trace_analyzer",
    "trace_filter",
    "trace_merge",
    "trace_plot",
    "trace_stats",
    "trace_to_matrix",
}


@pytest.fixture
def representative_trace_path() -> Path:
    return Path(__file__).parent / "fixtures" / "representative_trace.ecsv"


def test_native_traceratops_reader_accepts_representative_trace(
    representative_trace_path: Path,
) -> None:
    """Our baseline pyHiM ECSV schema must load through traceratops unchanged."""
    table = read_table_from_ecsv(representative_trace_path)

    assert isinstance(table, Table)
    assert len(table) == 4
    assert table.colnames == EXPECTED_COLUMNS
    assert table["x"].dtype.name == "float32"
    assert table["Chrom_Start"].dtype.name == "int64"
    assert table.meta["comments"] == [
        "xyz_unit=micron",
        "genome_assembly=mm10",
    ]


def test_high_level_traceratops_table_accepts_representative_trace(
    representative_trace_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The higher-level class used by traceratops commands must accept the file."""
    trace = ChromatinTraceTable()

    loaded = trace.load(representative_trace_path)

    assert loaded is trace.data
    assert len(loaded) == 4
    assert trace.original_format == "ecsv"
    assert "Successfully loaded trace table" in capsys.readouterr().out


def test_traceratops_ecsv_round_trip_preserves_data_and_metadata(
    representative_trace_path: Path, tmp_path: Path
) -> None:
    """Loading and saving with traceratops must preserve the trace contract."""
    original = read_table_from_ecsv(representative_trace_path)
    output_path = tmp_path / "round_trip.ecsv"

    save_table_to_ecsv(original, output_path)
    reloaded = read_table_from_ecsv(output_path)

    assert reloaded.colnames == original.colnames
    assert reloaded.meta == original.meta
    assert len(reloaded) == len(original)
    assert all(reloaded[column].tolist() == original[column].tolist() for column in EXPECTED_COLUMNS)


def test_native_trace_stats_runs_on_representative_trace(
    representative_trace_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Run traceratops' own statistics implementation rather than duplicating it."""
    compute_trace_statistics(representative_trace_path)

    output = capsys.readouterr().out
    assert "Number of unique ROIs: 2" in output
    assert "Number of unique chromatin traces: 2" in output
    assert "Number of unique barcodes: 3" in output


def test_core_traceratops_commands_are_installed() -> None:
    """Fail clearly if the installed traceratops distribution loses core commands."""
    console_scripts = {
        entry_point.name
        for entry_point in distribution("traceratops").entry_points
        if entry_point.group == "console_scripts"
    }

    assert version("traceratops") == "1.0.1"
    assert CORE_TRACERATOPS_COMMANDS <= console_scripts


def test_configured_real_trace_is_traceratops_compatible() -> None:
    """Optionally validate the actual trace selected for the MCP server."""
    configured_path = os.environ.get(TRACE_PATH_ENV)
    if not configured_path:
        pytest.skip(f"Set {TRACE_PATH_ENV} to run the real-trace compatibility test")

    path = Path(configured_path).expanduser()
    if not path.is_file():
        pytest.skip(f"Configured real trace is currently unavailable: {path}")

    table = read_table_from_ecsv(path)

    assert len(table) > 0
    assert table.colnames == EXPECTED_COLUMNS
    assert len(set(table["Trace_ID"])) > 0
    assert len(set(table["Barcode #"])) > 0
