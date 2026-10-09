from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client, MCPError

from chromatin_trace_mcp.server import (
    DATASET_CATALOG_ENV,
    LOCALIZATION_PATH_ENV,
    OUTPUT_DIR_ENV,
    TRACE_PATH_ENV,
    _DATASETS,
    mcp,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def clear_registered_datasets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the process-local registry isolated between protocol tests.

    The catalog variable is also cleared, so that registering a dataset in a test
    can never write into a real catalog configured in the user's shell.
    """
    _DATASETS.clear()
    monkeypatch.delenv(DATASET_CATALOG_ENV, raising=False)


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as connected_client:
        yield connected_client


@pytest.mark.anyio
async def test_lists_one_resource_and_twelve_tools(client: Client) -> None:
    resources = (await client.list_resources()).resources
    tools = (await client.list_tools()).tools

    assert [resource.uri for resource in resources] == ["trace://current/ecsv"]
    assert resources[0].mime_type == "text/csv"
    assert [tool.name for tool in tools] == [
        "register_dataset",
        "list_datasets",
        "inspect_dataset",
        "inspect_current_trace",
        "trace_stats",
        "filter_traces",
        "trace_to_matrix",
        "localization_analyzer",
        "compare_datasets",
        "localization_quality_summary",
        "snr_filter_sweep",
        "duplicate_statistics",
    ]
    assert all(tool.output_schema is not None for tool in tools)


@pytest.mark.anyio
async def test_reads_the_ecsv_unchanged(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    expected = (
        "# %ECSV 1.0\n"
        "# ---\n"
        "# datatype:\n"
        "# - {name: Trace_ID, datatype: string}\n"
        "Trace_ID x y z\n"
        "trace-1 1.0 2.0 3.0\n"
    )
    trace_path = tmp_path / "example.ecsv"
    trace_path.write_text(expected, encoding="utf-8")
    monkeypatch.setenv(TRACE_PATH_ENV, str(trace_path))

    result = await client.read_resource("trace://current/ecsv")

    assert result.contents[0].mime_type == "text/csv"
    assert result.contents[0].text == expected


@pytest.mark.anyio
async def test_missing_configuration_is_a_resource_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(TRACE_PATH_ENV, raising=False)

    async with Client(mcp) as client:
        with pytest.raises(MCPError, match=f"Set {TRACE_PATH_ENV}"):
            await client.read_resource("trace://current/ecsv")


@pytest.mark.anyio
async def test_rejects_a_non_ecsv_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    wrong_format = tmp_path / "example.txt"
    wrong_format.write_text("not ECSV", encoding="utf-8")
    monkeypatch.setenv(TRACE_PATH_ENV, str(wrong_format))

    async with Client(mcp) as client:
        with pytest.raises(MCPError, match="must have the .ecsv extension"):
            await client.read_resource("trace://current/ecsv")


@pytest.mark.anyio
async def test_inspects_trace_with_traceratops(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trace_path = tmp_path / "example.ecsv"
    trace_path.write_text(
        "# %ECSV 1.0\n"
        "# ---\n"
        "# datatype:\n"
        "# - {name: Trace_ID, datatype: string}\n"
        "# - {name: 'Barcode #', datatype: int64}\n"
        "# - {name: 'ROI #', datatype: int64}\n"
        "# meta: !!omap\n"
        "# - comments: [xyz_unit=micron, genome_assembly=mm10]\n"
        "# schema: astropy-2.0\n"
        'Trace_ID "Barcode #" "ROI #"\n'
        "trace-1 1 24\n"
        "trace-1 2 24\n"
        "trace-2 1 25\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(TRACE_PATH_ENV, str(trace_path))

    result = await client.call_tool("inspect_current_trace", {})

    assert result.is_error is False
    assert result.structured_content["row_count"] == 3
    assert result.structured_content["column_names"] == [
        "Trace_ID",
        "Barcode #",
        "ROI #",
    ]
    assert result.structured_content["unique_trace_count"] == 2
    assert result.structured_content["unique_barcode_count"] == 2
    assert result.structured_content["unique_roi_count"] == 2


@pytest.mark.anyio
async def test_trace_stats_calls_traceratops_and_returns_structured_counts(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    trace_path = Path(__file__).parent / "fixtures" / "representative_trace.ecsv"
    monkeypatch.setenv(TRACE_PATH_ENV, str(trace_path))

    result = await client.call_tool("trace_stats", {})

    assert result.is_error is False
    assert result.structured_content["traceratops_version"] == "1.0.1"
    assert result.structured_content["unique_roi_count"] == 2
    assert result.structured_content["unique_trace_count"] == 2
    assert result.structured_content["unique_barcode_count"] == 3
    assert "Successfully loaded trace table" in result.structured_content[
        "traceratops_report"
    ]
    assert "Number of unique chromatin traces: 2" in result.structured_content[
        "traceratops_report"
    ]


@pytest.mark.anyio
async def test_filter_traces_uses_traceratops_and_preserves_input(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trace_path = Path(__file__).parent / "fixtures" / "representative_trace.ecsv"
    original_text = trace_path.read_text(encoding="utf-8")
    monkeypatch.setenv(TRACE_PATH_ENV, str(trace_path))
    monkeypatch.setenv(OUTPUT_DIR_ENV, str(tmp_path / "outputs"))

    result = await client.call_tool(
        "filter_traces",
        {"minimum_barcodes": 2, "remove_barcodes": [2]},
    )

    assert result.is_error is False
    structured = result.structured_content
    assert structured["input_row_count"] == 4
    assert structured["output_row_count"] == 2
    output_file = Path(structured["output_file"])
    assert output_file.is_file()
    assert output_file.parent.parent == (tmp_path / "outputs").resolve()
    assert trace_path.read_text(encoding="utf-8") == original_text
    assert "Saved output trace file" in structured["traceratops_report"]

    from traceratops.core.chromatin_trace_table import read_table_from_ecsv

    filtered = read_table_from_ecsv(output_file)
    assert set(filtered["Trace_ID"]) == {"trace-2"}
    assert set(filtered["Barcode #"]) == {1, 3}


@pytest.mark.anyio
async def test_trace_to_matrix_uses_traceratops_and_returns_artifacts(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trace_path = Path(__file__).parent / "fixtures" / "representative_trace.ecsv"
    monkeypatch.setenv(TRACE_PATH_ENV, str(trace_path))
    monkeypatch.setenv(OUTPUT_DIR_ENV, str(tmp_path / "outputs"))

    result = await client.call_tool(
        "trace_to_matrix",
        {"distance_threshold": 10.0, "n_jobs": 1, "plot_histograms": False},
    )

    assert result.is_error is False
    structured = result.structured_content
    assert structured["matrix_shape"] == [3, 3, 2]
    assert structured["unique_barcode_count"] == 3
    assert structured["trace_count"] == 2
    assert structured["distance_threshold"] == 10.0
    artifact_paths = {Path(item["path"]) for item in structured["artifacts"]}
    assert len(artifact_paths) == 7
    assert all(path.is_file() for path in artifact_paths)
    assert any(path.name.endswith("_PWDscMatrix.npy") for path in artifact_paths)
    assert any(path.name.endswith("_HiMmatrix.png") for path in artifact_paths)
    assert "Total elapsed time for trace analysis" in structured["traceratops_report"]


@pytest.mark.anyio
async def test_localization_analyzer_uses_traceratops_and_creates_qc_plot(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    localization_path = (
        Path(__file__).parent / "fixtures" / "representative_localizations.ecsv"
    )
    monkeypatch.setenv(LOCALIZATION_PATH_ENV, str(localization_path))
    monkeypatch.setenv(OUTPUT_DIR_ENV, str(tmp_path / "outputs"))

    result = await client.call_tool("localization_analyzer", {"output_format": "png"})

    assert result.is_error is False
    structured = result.structured_content
    assert structured["row_count"] == 4
    assert structured["unique_barcode_count"] == 2
    output_file = Path(structured["output_file"])
    assert output_file.is_file()
    assert output_file.suffix == ".png"
    assert output_file.parent.parent == (tmp_path / "outputs").resolve()
    assert structured["artifacts"] == [
        {"path": str(output_file.resolve()), "size_bytes": output_file.stat().st_size}
    ]
    assert "Finished execution" in structured["traceratops_report"]


@pytest.mark.anyio
async def test_register_list_inspect_and_read_named_dataset(client: Client) -> None:
    fixture_directory = Path(__file__).parent / "fixtures"
    trace_path = fixture_directory / "representative_trace.ecsv"
    localization_path = fixture_directory / "representative_localizations.ecsv"

    registered = await client.call_tool(
        "register_dataset",
        {
            "name": "experiment_A",
            "trace_file": str(trace_path),
            "localization_file": str(localization_path),
        },
    )
    listed = await client.call_tool("list_datasets", {})
    inspected = await client.call_tool(
        "inspect_dataset", {"dataset_name": "experiment_A"}
    )
    assert registered.is_error is False
    assert registered.structured_content["name"] == "experiment_A"
    assert [item["name"] for item in listed.structured_content["datasets"]] == [
        "experiment_A"
    ]
    assert inspected.structured_content["unique_trace_count"] == 2


@pytest.mark.anyio
async def test_compare_two_compatible_registered_datasets(client: Client) -> None:
    fixture_directory = Path(__file__).parent / "fixtures"
    trace_path = fixture_directory / "representative_trace.ecsv"
    localization_path = fixture_directory / "representative_localizations.ecsv"
    for name in ("experiment_A", "experiment_B"):
        result = await client.call_tool(
            "register_dataset",
            {
                "name": name,
                "trace_file": str(trace_path),
                "localization_file": str(localization_path),
            },
        )
        assert result.is_error is False

    comparison = await client.call_tool(
        "compare_datasets",
        {"first_dataset": "experiment_A", "second_dataset": "experiment_B"},
    )

    assert comparison.is_error is False
    structured = comparison.structured_content
    assert structured["status"] == "compatible"
    assert structured["comparable"] is True
    assert structured["shared_barcodes"] == ["1", "2", "3"]
    assert structured["same_columns"] is True
    assert structured["coordinate_unit_first"] == "micron"
    assert structured["first"]["trace_count"] == 2
    assert structured["first"]["localization_row_count"] == 4
    assert structured["first"]["median_localization_snr"] == 6.5


@pytest.mark.anyio
async def test_duplicate_statistics_reports_trace_and_localization_buckets(
    client: Client,
) -> None:
    fixture_directory = Path(__file__).parent / "fixtures"
    trace_path = fixture_directory / "representative_trace.ecsv"
    localization_path = fixture_directory / "representative_localizations.ecsv"
    for name in ("experiment_A", "experiment_B"):
        result = await client.call_tool(
            "register_dataset",
            {
                "name": name,
                "trace_file": str(trace_path),
                "localization_file": str(localization_path),
            },
        )
        assert result.is_error is False

    trace_stats = await client.call_tool(
        "duplicate_statistics",
        {
            "first_dataset": "experiment_A",
            "second_dataset": "experiment_B",
            "table_kind": "trace",
        },
    )
    localization_stats = await client.call_tool(
        "duplicate_statistics",
        {
            "first_dataset": "experiment_A",
            "second_dataset": "experiment_B",
            "table_kind": "localization",
        },
    )

    assert trace_stats.is_error is False
    trace_structured = trace_stats.structured_content
    assert trace_structured["first"]["zero_duplicate_groups"] == 4
    assert trace_structured["first"]["one_duplicate_groups"] == 0
    assert trace_structured["first"]["duplicate_rows"] == 0

    assert localization_stats.is_error is False
    localization_structured = localization_stats.structured_content
    assert localization_structured["first"]["zero_duplicate_groups"] == 0
    assert localization_structured["first"]["one_duplicate_groups"] == 2
    assert localization_structured["first"]["two_duplicate_groups"] == 0
    assert localization_structured["first"]["duplicate_rows"] == 2


@pytest.mark.anyio
async def test_localization_quality_summary_and_snr_sweep(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture_directory = Path(__file__).parent / "fixtures"
    trace_path = fixture_directory / "representative_trace.ecsv"
    localization_path = fixture_directory / "representative_localizations.ecsv"
    monkeypatch.setenv(OUTPUT_DIR_ENV, str(tmp_path))
    for name in ("experiment_A", "experiment_B"):
        result = await client.call_tool(
            "register_dataset",
            {
                "name": name,
                "trace_file": str(trace_path),
                "localization_file": str(localization_path),
            },
        )
        assert result.is_error is False

    summary = await client.call_tool(
        "localization_quality_summary",
        {"dataset_name": "experiment_A"},
    )
    assert summary.is_error is False
    assert summary.structured_content["row_count"] == 4
    assert summary.structured_content["snr"]["median"] == 6.5
    assert summary.structured_content["intensity_distributions"][0]["median"] == 1350.0

    sweep = await client.call_tool(
        "snr_filter_sweep",
        {
            "first_dataset": "experiment_A",
            "second_dataset": "experiment_B",
            "thresholds": [5, 7, 10],
        },
    )
    assert sweep.is_error is False
    structured = sweep.structured_content
    assert structured["thresholds"] == [5.0, 7.0, 10.0]
    assert structured["first"]["points"][0]["localization_rows_retained"] == 4
    assert structured["first"]["points"][1]["localization_rows_retained"] == 2
    assert structured["first"]["points"][1]["trace_rows_retained"] == 0
    assert structured["first"]["points"][1]["unmatched_localization_buids"] == 2
    assert structured["first"]["points"][2]["localization_rows_retained"] == 0
    assert len(structured["artifacts"]) == 5
    assert all(Path(artifact["path"]).is_file() for artifact in structured["artifacts"])
    assert structured["first"]["points"][0]["trace_copy_multiplicity"]
    assert {artifact["path"].split("/")[-1] for artifact in structured["artifacts"]} == {
        "snr_filter_sweep.json",
        "snr_filter_sweep.png",
        "snr_filter_histogram_mean_intensity.png",
        "snr_filter_histogram_flux.png",
        "snr_filter_copy_multiplicity.png",
    }


@pytest.mark.anyio
async def test_comparison_rejects_datasets_without_shared_barcodes(
    client: Client, tmp_path: Path
) -> None:
    from traceratops.core.chromatin_trace_table import read_table_from_ecsv

    original = Path(__file__).parent / "fixtures" / "representative_trace.ecsv"
    shifted = read_table_from_ecsv(original)
    shifted["Barcode #"] = shifted["Barcode #"] + 100
    shifted_path = tmp_path / "shifted_barcodes.ecsv"
    shifted.write(shifted_path, format="ascii.ecsv")
    for name, path in (("original", original), ("shifted", shifted_path)):
        result = await client.call_tool(
            "register_dataset", {"name": name, "trace_file": str(path)}
        )
        assert result.is_error is False

    comparison = await client.call_tool(
        "compare_datasets",
        {"first_dataset": "original", "second_dataset": "shifted"},
    )

    assert comparison.structured_content["status"] == "not_comparable"
    assert comparison.structured_content["comparable"] is False
    assert comparison.structured_content["shared_barcodes"] == []
    assert "no barcode identifiers in common" in " ".join(
        comparison.structured_content["reasons"]
    )


@pytest.mark.anyio
async def test_persistent_json_catalog_loads_and_compares_datasets(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import json

    fixture_directory = Path(__file__).parent / "fixtures"
    trace_path = fixture_directory / "representative_trace.ecsv"
    localization_path = fixture_directory / "representative_localizations.ecsv"
    catalog_path = tmp_path / "datasets.json"
    catalog_path.write_text(
        json.dumps(
            {
                name: {
                    "trace_file": str(trace_path),
                    "localization_file": "",
                }
                for name in ("experiment_A", "experiment_B")
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(DATASET_CATALOG_ENV, str(catalog_path))

    listed = await client.call_tool("list_datasets", {})
    comparison = await client.call_tool(
        "compare_datasets",
        {"first_dataset": "experiment_A", "second_dataset": "experiment_B"},
    )

    assert [item["name"] for item in listed.structured_content["datasets"]] == [
        "experiment_A",
        "experiment_B",
    ]
    assert all(
        item["localization_file"] is None
        for item in listed.structured_content["datasets"]
    )
    assert comparison.structured_content["status"] == "compatible"


FIXTURES = Path(__file__).parent / "fixtures"


def _write_catalog(path: Path, entries: dict[str, Path]) -> None:
    import json

    path.write_text(
        json.dumps(
            {
                name: {"trace_file": str(trace), "localization_file": ""}
                for name, trace in entries.items()
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _read_catalog(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.anyio
async def test_registered_dataset_is_saved_and_survives_a_restart(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trace_path = FIXTURES / "representative_trace.ecsv"
    localization_path = FIXTURES / "representative_localizations.ecsv"
    catalog_path = tmp_path / "datasets.local.json"
    _write_catalog(catalog_path, {"experiment_A": trace_path})
    monkeypatch.setenv(DATASET_CATALOG_ENV, str(catalog_path))

    registered = await client.call_tool(
        "register_dataset",
        {
            "name": "exp_231",
            "trace_file": str(trace_path),
            "localization_file": str(localization_path),
        },
    )

    assert registered.is_error is False
    assert registered.structured_content["saved_to_catalog"] == str(catalog_path.resolve())
    catalog = _read_catalog(catalog_path)
    assert list(catalog) == ["experiment_A", "exp_231"]
    assert catalog["experiment_A"]["trace_file"] == str(trace_path)
    assert catalog["exp_231"] == {
        "trace_file": str(trace_path.resolve()),
        "localization_file": str(localization_path.resolve()),
    }
    assert not list(tmp_path.glob(".*.tmp"))

    _DATASETS.clear()  # what a server restart does to session registrations
    listed = await client.call_tool("list_datasets", {})
    inspected = await client.call_tool("inspect_dataset", {"dataset_name": "exp_231"})

    assert [item["name"] for item in listed.structured_content["datasets"]] == [
        "exp_231",
        "experiment_A",
    ]
    assert inspected.structured_content["unique_trace_count"] == 2


@pytest.mark.anyio
async def test_registration_creates_the_catalog_when_missing(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trace_path = FIXTURES / "representative_trace.ecsv"
    catalog_path = tmp_path / "new_catalog.json"
    monkeypatch.setenv(DATASET_CATALOG_ENV, str(catalog_path))

    registered = await client.call_tool(
        "register_dataset", {"name": "exp_214", "trace_file": str(trace_path)}
    )

    assert registered.is_error is False
    assert _read_catalog(catalog_path) == {
        "exp_214": {"trace_file": str(trace_path.resolve()), "localization_file": ""}
    }


@pytest.mark.anyio
async def test_registering_the_same_files_twice_changes_nothing(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trace_path = FIXTURES / "representative_trace.ecsv"
    catalog_path = tmp_path / "datasets.local.json"
    monkeypatch.setenv(DATASET_CATALOG_ENV, str(catalog_path))
    arguments = {"name": "exp_214", "trace_file": str(trace_path)}

    first = await client.call_tool("register_dataset", arguments)
    _DATASETS.clear()
    second = await client.call_tool("register_dataset", arguments)

    assert first.is_error is False
    assert second.is_error is False
    assert list(_read_catalog(catalog_path)) == ["exp_214"]


@pytest.mark.anyio
async def test_replacing_a_dataset_requires_overwrite(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original_trace = FIXTURES / "representative_trace.ecsv"
    other_trace = tmp_path / "other_trace.ecsv"
    other_trace.write_text(original_trace.read_text(encoding="utf-8"), encoding="utf-8")
    catalog_path = tmp_path / "datasets.local.json"
    _write_catalog(catalog_path, {"experiment_A": original_trace})
    monkeypatch.setenv(DATASET_CATALOG_ENV, str(catalog_path))
    arguments = {"name": "experiment_A", "trace_file": str(other_trace)}

    refused = await client.call_tool("register_dataset", arguments)

    assert refused.is_error is True
    assert "overwrite=true" in refused.content[0].text
    assert _read_catalog(catalog_path)["experiment_A"]["trace_file"] == str(original_trace)

    replaced = await client.call_tool("register_dataset", {**arguments, "overwrite": True})

    assert replaced.is_error is False
    assert _read_catalog(catalog_path)["experiment_A"]["trace_file"] == str(
        other_trace.resolve()
    )


@pytest.mark.anyio
async def test_registration_without_catalog_is_session_only(
    client: Client, tmp_path: Path
) -> None:
    trace_path = FIXTURES / "representative_trace.ecsv"

    registered = await client.call_tool(
        "register_dataset", {"name": "exp_214", "trace_file": str(trace_path)}
    )

    assert registered.is_error is False
    assert registered.structured_content["saved_to_catalog"] is None
    assert "session only" in registered.structured_content["note"]
    assert list(tmp_path.iterdir()) == []
