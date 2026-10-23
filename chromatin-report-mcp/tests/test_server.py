import json
from pathlib import Path

import pytest
from mcp import Client

import chromatin_report_mcp.server as server


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(server.mcp, raise_exceptions=True) as connected:
        yield connected


def comparison_payload() -> dict[str, object]:
    metrics_a = {
        "dataset_name": "experiment_A",
        "trace_row_count": 100,
        "trace_count": 10,
        "roi_count": 2,
        "barcode_count": 3,
        "barcodes": ["1", "2", "3"],
        "median_rows_per_trace": 10.0,
        "coordinate_missing_fraction": 0.0,
        "duplicate_trace_barcode_rows": 0,
        "localization_row_count": None,
        "localization_barcode_count": None,
        "median_localization_snr": None,
    }
    metrics_b = {**metrics_a, "dataset_name": "experiment_B", "trace_row_count": 120}
    return {
        "first": metrics_a,
        "second": metrics_b,
        "status": "compatible_with_warnings",
        "comparable": True,
        "shared_barcodes": ["1", "2", "3"],
        "only_in_first": [],
        "only_in_second": [],
        "same_columns": True,
        "columns_only_in_first": [],
        "columns_only_in_second": [],
        "coordinate_unit_first": "micron",
        "coordinate_unit_second": "micron",
        "reasons": ["Required fields are compatible."],
        "warnings": ["Dataset sizes differ."],
    }


def sweep_payload() -> dict[str, object]:
    def point(threshold: float) -> dict[str, object]:
        duplicate_stats = {
            "table_kind": "localization",
            "grouping_columns": ["ROI #", "CellID #", "Barcode #"],
            "row_count": 10,
            "unique_group_count": 4,
            "zero_duplicate_groups": 1,
            "one_duplicate_groups": 1,
            "two_duplicate_groups": 1,
            "more_than_two_duplicate_groups": 1,
            "duplicate_rows": 6,
            "maximum_group_size": 5,
        }
        distributions = [
            {"column": "mean_intensity", "finite_count": 10, "missing_or_nonfinite_count": 0, "minimum": 1.0, "p10": 2.0, "median": 5.0 + threshold, "p90": 12.0, "maximum": 20.0},
            {"column": "flux", "finite_count": 10, "missing_or_nonfinite_count": 0, "minimum": 1.0, "p10": 2.0, "median": 3.0 + threshold / 10, "p90": 8.0, "maximum": 12.0},
        ]
        return {
            "threshold": threshold,
            "localization_rows_before": 10,
            "localization_rows_retained": 8,
            "localization_retained_fraction": 0.8,
            "unique_buids_retained": 8,
            "unique_barcodes_retained": 3,
            "unique_rois_retained": 1,
            "unique_cells_retained": 1,
            "trace_rows_before": 10,
            "trace_rows_retained": 7,
            "trace_retained_fraction": 0.7,
            "unique_traces_retained": 2,
            "unmatched_localization_buids": 0,
            "intensity_distributions": distributions,
            "duplicate_statistics": duplicate_stats,
            "trace_copy_multiplicity": [
                {"multiplicity": "1", "groups_before": 4, "groups_after": 3, "rows_before": 4, "rows_retained": 3, "rows_dropped": 1},
                {"multiplicity": "2", "groups_before": 3, "groups_after": 2, "rows_before": 6, "rows_retained": 4, "rows_dropped": 2},
                {"multiplicity": "3", "groups_before": 2, "groups_after": 1, "rows_before": 6, "rows_retained": 3, "rows_dropped": 3},
                {"multiplicity": "4+", "groups_before": 1, "groups_after": 1, "rows_before": 5, "rows_retained": 4, "rows_dropped": 1},
            ],
        }

    return {
        "thresholds": [5.0, 7.5, 10.0],
        "intensity_columns": ["mean_intensity", "flux"],
        "first": {"dataset_name": "experiment_A", "localization_file": "loc_a.ecsv", "trace_file": "trace_a.ecsv", "points": [point(value) for value in (5.0, 7.5, 10.0)]},
        "second": {"dataset_name": "experiment_B", "localization_file": "loc_b.ecsv", "trace_file": "trace_b.ecsv", "points": [point(value) for value in (5.0, 7.5, 10.0)]},
        "artifacts": [],
        "notes": [],
    }


@pytest.mark.anyio
async def test_publishes_report_tools_and_latest_report_resource(client: Client) -> None:
    tools = (await client.list_tools()).tools
    resources = (await client.list_resources()).resources

    assert sorted(tool.name for tool in tools) == sorted([
        "write_comparison_report",
        "write_comparison_pdf",
        "generate_experiment_qc_report",
    ])
    assert all(tool.output_schema is not None for tool in tools)
    assert [resource.uri for resource in resources] == ["report://latest"]


@pytest.mark.anyio
@pytest.mark.parametrize("output_format,suffix", [("markdown", ".md"), ("html", ".html")])
async def test_writes_comparison_report(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    output_format: str,
    suffix: str,
) -> None:
    monkeypatch.setenv(server.REPORT_OUTPUT_ENV, str(tmp_path))
    result = await client.call_tool(
        "write_comparison_report",
        {
            "comparison": comparison_payload(),
            "report_title": "A versus B",
            "output_format": output_format,
            "scientist_notes": "Pilot comparison.",
        },
    )

    assert result.is_error is False
    output_path = Path(result.structured_content["path"])
    assert output_path.is_file()
    assert output_path.suffix == suffix
    text = output_path.read_text(encoding="utf-8")
    assert "compatible_with_warnings" in text
    assert "Dataset sizes differ." in text
    assert "Pilot comparison." in text
    assert "Not available" in text
    assert "## Summary of data" in text
    assert "## Recommendations" in text
    assert "## Conclusion" in text


@pytest.mark.anyio
async def test_renders_explicit_recommendations_and_conclusion(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(server.REPORT_OUTPUT_ENV, str(tmp_path))
    result = await client.call_tool(
        "write_comparison_report",
        {
            "comparison": comparison_payload(),
            "recommendations": "Use a minimum of 10 loci and inspect duplicate candidates.",
            "conclusion": "The datasets are suitable for a pilot comparison.",
        },
    )

    text = Path(result.structured_content["path"]).read_text(encoding="utf-8")
    assert "Use a minimum of 10 loci and inspect duplicate candidates." in text
    assert "The datasets are suitable for a pilot comparison." in text


@pytest.mark.anyio
async def test_writes_comparison_pdf(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(server.REPORT_OUTPUT_ENV, str(tmp_path))
    result = await client.call_tool(
        "write_comparison_pdf",
        {
            "comparison": comparison_payload(),
            "report_title": "A versus B PDF",
            "scientist_notes": "Pilot comparison.",
            "recommendations": "Inspect duplicate candidates.",
            "conclusion": "Suitable for a pilot comparison.",
        },
    )

    assert result.is_error is False
    output_path = Path(result.structured_content["path"])
    assert output_path.is_file()
    assert output_path.suffix == ".pdf"
    assert output_path.read_bytes().startswith(b"%PDF-")
    assert result.structured_content["format"] == "pdf"


@pytest.mark.anyio
async def test_writes_pdf_with_snr_sweep_figures(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(server.REPORT_OUTPUT_ENV, str(tmp_path))
    result = await client.call_tool(
        "write_comparison_pdf",
        {
            "comparison": comparison_payload(),
            "sweep": sweep_payload(),
            "report_title": "A versus B full PDF",
        },
    )

    assert result.is_error is False
    output_path = Path(result.structured_content["path"])
    assert output_path.is_file()
    assert output_path.read_bytes().startswith(b"%PDF-")
    assert output_path.stat().st_size > 10_000


def test_comparison_fixture_is_json_serializable() -> None:
    json.dumps(comparison_payload())
