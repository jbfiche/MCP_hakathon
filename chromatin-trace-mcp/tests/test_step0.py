"""Independent small experiments: exact identifiers, findings, statuses and report artifacts."""
import json
from pathlib import Path

import pytest
from astropy.table import Table
from mcp import Client

from chromatin_trace_mcp.step0 import (
    OUTPUT_ENV, ROOTS_ENV, StructureRules, compact, evaluate,
    save_validation_result, read_run,
)
from chromatin_trace_mcp.server import mcp


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    root = tmp_path / "experiment"
    root.mkdir()
    monkeypatch.setenv(ROOTS_ENV, str(root))
    monkeypatch.setenv(OUTPUT_ENV, str(tmp_path / "outputs"))
    return root


def write_roi(root, rid="092", barcodes=(1, 2, 3), *, loc_nested=True):
    folder = root / rid
    trace = folder / "tracing/data" / f"Trace_3D_barcode_mask-mask0_ROI-{int(rid)}.ecsv"
    loc = folder / ("localize_3d/data" if loc_nested else "localize_3d") / "localizations_3D_barcode.ecsv"
    trace.parent.mkdir(parents=True, exist_ok=True)
    loc.parent.mkdir(parents=True, exist_ok=True)
    n = len(barcodes)
    Table({"Spot_ID": [f"spot-{i}" for i in range(n)], "Trace_ID": ["nucleus-1"] * n,
           "x": [float(i) for i in range(n)], "y": [0.] * n, "z": [0.] * n,
           "ROI #": [int(rid)] * n, "Barcode #": list(barcodes)},
          meta={"comments": ["xyz_unit=micron"]}).write(trace, format="ascii.ecsv", overwrite=True)
    Table({"Buid": [f"spot-{i}" for i in range(n)], "ROI #": [int(rid)] * n,
           "Barcode #": list(barcodes), "xcentroid": [float(i) for i in range(n)],
           "ycentroid": [0.] * n, "zcentroid": [0.] * n}).write(loc, format="ascii.ecsv", overwrite=True)
    return trace, loc


def policy(rois=("92",), **kw):
    return StructureRules(expected_roi_ids=list(rois), expected_barcodes=["1", "2", "3"], barcode_source="synthetic experiment design", **kw)


def codes(doc):
    return {f["code"] for f in doc["findings"]}


def table_at(doc, roi="92", role="tracing"):
    return next(t for r in doc["rois"] if r["roi"] == roi for t in r["tables"] if t["role"] == role)


def test_valid_single_roi_normalizes_padding_and_reports(experiment):
    trace, loc = write_roi(experiment)
    original = {p: p.read_bytes() for p in (trace, loc)}
    doc = evaluate(str(experiment), policy())
    assert doc["status"] == "PASS"
    assert [r["roi"] for r in doc["rois"]] == ["92"]
    assert table_at(doc)["observed_barcodes"] == ["1", "2", "3"]
    assert table_at(doc)["record_count"] == 3
    assert table_at(doc)["unique_trace_count"] == 1
    assert table_at(doc)["missing_barcodes"] == []
    summary = save_validation_result(doc)
    assert summary["complete_file_rois"] == 1
    assert summary["ecsv_records_inspected"] == 6
    assert all(Path(summary[k]).is_file() for k in ("report_path", "summary_path", "details_path"))
    assert read_run(summary["run_id"])["status"] == "PASS"
    assert {p: p.read_bytes() for p in original} == original


def test_multi_roi_exact_missing_and_unexpected_observations(experiment):
    write_roi(experiment, "092", (1, 3))
    write_roi(experiment, "093", (2, 3, 99), loc_nested=False)
    doc = evaluate(str(experiment), policy(("92", "93")))
    assert doc["status"] == "PASS"  # warnings are separate from validation success
    assert table_at(doc, "92")["missing_barcodes"] == ["2"]
    assert table_at(doc, "93")["missing_barcodes"] == ["1"]
    assert table_at(doc, "93")["unexpected_barcodes"] == ["99"]
    assert compact(doc)["rois_with_warnings"] == 2


@pytest.mark.parametrize("role", ["tracing", "localization"])
def test_missing_required_file_exact_roi_and_status(experiment, role):
    trace, loc = write_roi(experiment)
    (trace if role == "tracing" else loc).unlink()
    doc = evaluate(str(experiment), policy())
    assert doc["status"] == "FAIL"
    match = [f for f in doc["findings"] if f["code"] == "MISSING_" + role.upper()]
    assert len(match) == 1 and match[0]["roi"] == "92"
    summary = save_validation_result(doc)
    assert Path(summary["details_path"]).is_file()
    assert Path(summary["human_report_path"]).is_file()
    assert Path(summary["html_report_path"]).is_file()


def test_invalid_ecsv_is_error_and_has_report(experiment):
    trace, _ = write_roi(experiment)
    trace.write_text("not ECSV\ninvalid", encoding="utf-8")
    doc = evaluate(str(experiment), policy())
    assert doc["status"] == "ERROR"
    assert "INVALID_ECSV" in codes(doc)
    assert compact(doc, report=True)["status"] == "ERROR"


def test_missing_required_columns(experiment):
    trace, _ = write_roi(experiment)
    table = Table.read(trace, format="ascii.ecsv")
    table.remove_column("Trace_ID")
    table.write(trace, format="ascii.ecsv", overwrite=True)
    doc = evaluate(str(experiment), policy())
    assert doc["status"] == "FAIL"
    assert table_at(doc)["missing_required_columns"] == ["Trace_ID"]
    assert "unique_trace_count" not in table_at(doc)


def test_strict_coverage_is_explicit_policy(experiment):
    write_roi(experiment, barcodes=(1, 3))
    doc = evaluate(str(experiment), policy(require_each_barcode=True))
    assert doc["status"] == "FAIL"
    assert all(f["severity"] == "ERROR" for f in doc["findings"] if f["code"] == "MISSING_BARCODE_OBSERVATIONS")


def test_bed_mapping_is_explicit_and_consistent(experiment):
    write_roi(experiment)
    (experiment / "design.bed").write_text("chr2L\t0\t10\t1\nchr2L\t10\t20\t2\nchr2L\t20\t30\t3\n")
    rules = StructureRules(expected_roi_ids=["92"], bed_file="design.bed", bed_barcode_column=4)
    doc = evaluate(str(experiment), rules)
    assert doc["status"] == "PASS"
    assert doc["expected_barcodes"] == ["1", "2", "3"]
    assert doc["bed"]["existence"] == doc["bed"]["mapping_status"] == "PASS"


@pytest.mark.parametrize("case,code", [("missing", "BED_MISSING"), ("conflict", "BED_CONFLICTING_BARCODE"), ("duplicate", "BED_DUPLICATE_BARCODE"), ("interval", "BED_INVALID")])
def test_invalid_bed_associations(experiment, case, code):
    write_roi(experiment)
    if case != "missing":
        contents = {"conflict": "chr1 0 10 1\nchr1 10 20 1\n", "duplicate": "chr1 0 10 1\nchr1 0 10 1\n", "interval": "chr1 20 10 1\n"}
        (experiment / "design.bed").write_text(contents[case])
    doc = evaluate(str(experiment), policy(bed_file="design.bed", bed_barcode_column=4))
    assert doc["status"] == "FAIL"
    assert code in codes(doc)


def test_missing_bed_mapping_metadata_does_not_guess_column(experiment):
    write_roi(experiment)
    (experiment / "design.bed").write_text("chr1 0 10 1\n")
    doc = evaluate(str(experiment), StructureRules(expected_roi_ids=["92"], bed_file="design.bed"))
    assert doc["status"] == "INCOMPLETE"
    assert doc["expected_barcodes"] is None
    assert doc["bed"]["existence"] == "PASS"
    assert doc["bed"]["mapping_status"] == "INCOMPLETE"
    assert table_at(doc)["missing_barcodes"] is None


def test_no_expected_roi_configuration_never_claims_missing_rois(experiment):
    write_roi(experiment)
    doc = evaluate(str(experiment))
    assert doc["status"] == "INCOMPLETE"
    assert {"EXPECTED_ROIS_UNAVAILABLE", "EXPECTED_BARCODES_UNAVAILABLE"} <= codes(doc)
    assert "MISSING_EXPECTED_ROI" not in codes(doc)


def test_missing_expected_roi_uses_authoritative_list(experiment):
    write_roi(experiment)
    doc = evaluate(str(experiment), policy(("92", "93")))
    assert doc["status"] == "FAIL"
    assert [f["roi"] for f in doc["findings"] if f["code"] == "MISSING_EXPECTED_ROI"] == ["93"]


def test_multiple_masks_ambiguous_but_kdtree_ignored(experiment):
    trace, _ = write_roi(experiment)
    trace.with_name(trace.name.replace("mask-mask0", "KDtree")).write_bytes(trace.read_bytes())
    assert evaluate(str(experiment), policy())["status"] == "PASS"
    trace.with_name(trace.name.replace("mask0", "mask1")).write_bytes(trace.read_bytes())
    doc = evaluate(str(experiment), policy())
    assert doc["status"] == "FAIL"
    assert "AMBIGUOUS_TRACING" in codes(doc)
    assert len(doc["rois"][0]["tracing"]) == 2
    assert all(t["role"] != "tracing" for t in doc["rois"][0]["tables"])


def test_empty_and_unexpected_directories(experiment):
    write_roi(experiment)
    (experiment / "092/unexpected").mkdir()
    doc = evaluate(str(experiment), policy(allowed_top_level_directories=["tracing", "localize_3d"]))
    assert {"UNEXPECTED_DIRECTORY", "EMPTY_DIRECTORY"} <= codes(doc)
    assert doc["status"] == "PASS"


def test_large_roi_set_pages_findings(experiment):
    for i in range(120):
        (experiment / f"{i:03d}").mkdir()
    doc = evaluate(str(experiment), StructureRules(expected_roi_ids=[str(i) for i in range(120)]))
    result = compact(doc, limit=3)
    assert result["roi_count"] == 120
    assert len(result["findings"]["items"]) == 3
    assert result["findings"]["next_offset"] == 3
    assert result["status"] == "FAIL"


def test_unauthorized_root_and_missing_allowlist(experiment, tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    assert evaluate(str(outside))["status"] == "ERROR"
    monkeypatch.delenv(ROOTS_ENV)
    assert evaluate(str(experiment))["status"] == "ERROR"


def test_symlink_cannot_escape_root(experiment, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    write_roi(outside)
    (experiment / "092").symlink_to(outside / "092", target_is_directory=True)
    doc = evaluate(str(experiment))
    assert "SYMLINK_SKIPPED" in codes(doc)
    assert doc["rois"] == []
    assert doc["files"] == []


def test_permission_failure_is_error(experiment, monkeypatch):
    write_roi(experiment)
    original = Path.iterdir
    def denied(p):
        if p == experiment / "092/tracing/data":
            raise PermissionError("synthetic permission denied")
        return original(p)
    monkeypatch.setattr(Path, "iterdir", denied)
    doc = evaluate(str(experiment), policy())
    assert doc["status"] == "ERROR"
    assert "DIRECTORY_UNREADABLE" in codes(doc)


def test_incomplete_schema_rules(experiment):
    write_roi(experiment)
    doc = evaluate(str(experiment), policy(required_trace_columns=[]))
    assert doc["status"] == "INCOMPLETE"
    assert "SCHEMA_RULES_UNAVAILABLE" in codes(doc)


def test_schema_and_roi_conflicts_are_distinct(experiment):
    write_roi(experiment, "092")
    trace, _ = write_roi(experiment, "093")
    table = Table.read(trace, format="ascii.ecsv")
    table["ROI #"] = [92, 92, 92]
    table["new_column"] = [1, 2, 3]
    table.write(trace, format="ascii.ecsv", overwrite=True)
    doc = evaluate(str(experiment), policy(("92", "93")))
    assert doc["status"] == "FAIL"
    assert {"SCHEMA_INCONSISTENCY", "ROI_TABLE_CONFLICT"} <= codes(doc)


def test_metadata_identification_verified_columns_and_automatic_fallback(experiment):
    trace, _ = write_roi(experiment)
    trace.rename(trace.with_name("other_name.ecsv"))
    doc = evaluate(str(experiment), policy(), discovery_mode="automatic")
    assert doc["status"] == "PASS"
    assert doc["rois"][0]["tracing_discovery_method"] == "column_signature"


def test_file_discovery_does_not_parse_tables(experiment, monkeypatch):
    write_roi(experiment)
    def forbidden(*args, **kwargs):
        raise AssertionError("Discovery must not load a table")
    monkeypatch.setattr(Table, "read", forbidden)
    assert evaluate(str(experiment), policy(), phase="inspection")["status"] == "PASS"
    assert evaluate(str(experiment), policy(), phase="discovery")["status"] == "PASS"


def test_json_and_yaml_configuration_are_explicit(experiment):
    write_roi(experiment)
    (experiment / "experiment.yaml").write_text("step0:\n  expected_roi_ids: ['92']\n  expected_barcodes: ['1', '2', '3']\n  barcode_source: synthetic design\n")
    doc = evaluate(str(experiment))
    assert doc["status"] == "PASS"
    assert doc["rules_source"] == "experiment.yaml:step0"


def test_limits_never_silently_report_complete(experiment):
    write_roi(experiment)
    doc = evaluate(str(experiment), policy(max_entries=2))
    assert "ENTRY_LIMIT" in codes(doc)
    assert doc["status"] != "PASS"
    doc = evaluate(str(experiment), policy(max_table_bytes=1))
    assert doc["status"] == "INCOMPLETE"
    assert "TABLE_SIZE_LIMIT" in codes(doc)


@pytest.mark.anyio
async def test_mcp_aggregate_and_cached_detail_without_reanalysis(experiment, monkeypatch):
    write_roi(experiment)
    async with Client(mcp, raise_exceptions=True) as client:
        result = await client.call_tool("run_experiment_validation", {"experiment_root": str(experiment), "rules": policy().model_dump()})
        assert not result.is_error
        payload = result.structured_content
        # SDK may use a generic-dict result envelope; assert actual returned payload below.
        if "result" in payload:
            payload = payload["result"]
        assert payload["status"] == "PASS"
        assert "rois" not in payload
        run_id = payload["run_id"]
        monkeypatch.setattr(Table, "read", lambda *a, **k: (_ for _ in ()).throw(AssertionError("No repeat analysis")))
        detailed = await client.call_tool("read_validation_details", {"validation_run_id": run_id, "section": "rois", "limit": 1})
        detail = detailed.structured_content
        if "result" in detail:
            detail = detail["result"]
        assert detail["items"][0]["roi"] == "92"
        report = await client.call_tool("get_validation_summary", {"validation_run_id": run_id})
        assert not report.is_error
    metrics = [json.loads(line) for line in (Path(__import__('os').environ[OUTPUT_ENV]) / "tool_metrics.jsonl").read_text().splitlines()]
    assert [m["tool_name"] for m in metrics] == ["run_experiment_validation", "read_validation_details", "get_validation_summary"]
    assert all(m["output_bytes"] > 0 and m["model_usage"] == "unavailable_at_mcp_server" for m in metrics)


def test_output_cannot_modify_experiment_tree(experiment, monkeypatch):
    write_roi(experiment)
    doc = evaluate(str(experiment), policy())
    monkeypatch.setenv(OUTPUT_ENV, str(experiment / "results"))
    with pytest.raises(PermissionError):
        save_validation_result(doc)
    assert not (experiment / "results").exists()


def test_derived_barcode_index_is_not_a_trace_candidate(experiment):
    trace, _ = write_roi(experiment)
    derived = trace.with_name(trace.stem + "_Matrix_uniqueBarcodes.ecsv")
    Table({"Barcode #": [1, 2, 3]}).write(derived, format="ascii.ecsv")
    doc = evaluate(str(experiment), policy())
    assert doc["status"] == "PASS"
    assert doc["rois"][0]["tracing"] == [str(trace.relative_to(experiment))]


@pytest.mark.anyio
async def test_telemetry_cannot_write_into_experiment(experiment, monkeypatch):
    write_roi(experiment)
    destination = experiment / "forbidden_outputs"
    monkeypatch.setenv(OUTPUT_ENV, str(destination))
    async with Client(mcp, raise_exceptions=True) as client:
        result = await client.call_tool("inspect_experiment_directory", {"experiment_root": str(experiment)})
        assert "telemetry_error" in result.structured_content
        result = await client.call_tool("run_experiment_validation", {"experiment_root": str(experiment)})
        assert result.structured_content["status"] == "ERROR"
    assert not destination.exists()


def test_denied_root_still_saves_error_report(experiment):
    doc = evaluate("/")
    assert doc["status"] == "ERROR"
    summary = save_validation_result(doc)
    assert Path(summary["details_path"]).is_file()
    assert Path(summary["human_report_path"]).is_file()
    assert Path(summary["html_report_path"]).is_file()


def test_partial_check_does_not_claim_full_readiness(experiment):
    write_roi(experiment)
    summary = compact(evaluate(str(experiment), policy(), phase="inspection"))
    assert not summary["full_validation_performed"]
    assert "has not been assessed" in summary["conclusion"]
