"""Read-only experiment validation; no Traceratops scientific algorithms.

Only discovery, schema/metadata checks, identifier counts, reporting and telemetry
live here. Experiment inputs are never written. See references/step0.md.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import numpy as np
import yaml
from astropy.table import Table
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOTS_ENV = "CHROMATIN_EXPERIMENT_ROOTS"
OUTPUT_ENV = "CHROMATIN_STEP0_OUTPUT_DIR"
TRACE_COLUMNS = ["Spot_ID", "Trace_ID", "x", "y", "z", "ROI #", "Barcode #"]
LOCALIZATION_COLUMNS = ["Buid", "ROI #", "Barcode #", "xcentroid", "ycentroid", "zcentroid"]
TRACE_GLOB = "tracing/data/Trace_3D_barcode_mask-*_ROI-*.ecsv"
LOCALIZATION_GLOBS = ["localize_3d/data/localizations_3D_barcode.ecsv", "localize_3d/localizations_3D_barcode.ecsv"]


class Step0Result(BaseModel):
    """Structured MCP envelope; section-specific fields are preserved."""
    model_config = ConfigDict(extra="allow")
    status: Literal["PASS", "FAIL", "INCOMPLETE", "ERROR"] | None = None


class StructureRules(BaseModel):
    """Explicit policy; empty reference lists differ from unavailable references."""
    model_config = ConfigDict(extra="forbid")
    roi_pattern: str = r"^[0-9]+$"
    required_directories: list[str] = Field(default_factory=lambda: ["tracing/data", "localize_3d"])
    optional_directories: list[str] = Field(default_factory=list)
    allowed_top_level_directories: list[str] | None = None
    trace_glob: str = TRACE_GLOB
    localization_globs: list[str] = Field(default_factory=lambda: list(LOCALIZATION_GLOBS))
    required_trace_columns: list[str] = Field(default_factory=lambda: list(TRACE_COLUMNS))
    required_localization_columns: list[str] = Field(default_factory=lambda: list(LOCALIZATION_COLUMNS))
    allowed_trace_columns: list[str] | None = None
    allowed_localization_columns: list[str] | None = None
    expected_roi_ids: list[str] | None = None
    expected_barcodes: list[str] | None = None
    barcode_source: str | None = None
    bed_file: str | None = None
    bed_barcode_column: int | None = Field(default=None, ge=1)
    bed_required: bool = False
    require_each_barcode: bool = False
    max_depth: int = Field(default=12, ge=1, le=64)
    max_entries: int = Field(default=100000, ge=1, le=1000000)
    max_table_bytes: int = Field(default=100_000_000, ge=1, le=2_000_000_000)
    max_records: int = Field(default=5_000_000, ge=1, le=50_000_000)
    skip_directories: list[str] = Field(default_factory=lambda: ["full_pwd", "PWD_comparison", ".git", ".venv"])

    @field_validator("expected_roi_ids", "expected_barcodes", mode="before")
    @classmethod
    def reference_identifiers(cls, values):
        if values is None:
            return None
        return [identifier(value) for value in values]

    @field_validator("roi_pattern")
    @classmethod
    def valid_pattern(cls, value):
        re.compile(value)
        return value

    @field_validator("required_directories", "optional_directories", "localization_globs")
    @classmethod
    def relative_paths(cls, values):
        for value in values:
            if Path(value).is_absolute() or ".." in Path(value).parts:
                raise ValueError("Patterns and directories must be relative without '..'.")
        return values

    @field_validator("trace_glob", "bed_file")
    @classmethod
    def relative_path(cls, value):
        if value is not None and (Path(value).is_absolute() or ".." in Path(value).parts):
            raise ValueError("Experiment paths must be relative without '..'.")
        return value


def identifier(value) -> str:
    """Canonical integer identifiers, including zero-padded ROI strings."""
    if np.ma.is_masked(value) or value is None:
        raise ValueError("Missing identifier")
    text = str(value).strip()
    if not re.fullmatch(r"[+-]?[0-9]+", text):
        raise ValueError(f"Expected an integer identifier, got {text[:60]!r}")
    return str(int(text))


def status(findings: list[dict]) -> str:
    if any(f.get("execution_error") for f in findings):
        return "ERROR"
    severities = {f["severity"] for f in findings}
    return "FAIL" if "ERROR" in severities else "INCOMPLETE" if "INCOMPLETE" in severities else "PASS"


def finding(doc, severity, code, message, *, roi=None, path=None, execution_error=False):
    item = dict(severity=severity, code=code, message=message[:500])
    if roi is not None:
        item["roi"] = str(roi)
    if path is not None:
        item["path"] = str(path)
    if execution_error:
        item["execution_error"] = True
    doc["findings"].append(item)


def authorized_root(raw: str) -> Path:
    path = Path(raw).expanduser().resolve(strict=True)
    roots = [Path(p).expanduser().resolve(strict=True) for p in os.environ.get(ROOTS_ENV, "").split(os.pathsep) if p]
    if not roots or not any(path == allowed or path.is_relative_to(allowed) for allowed in roots):
        raise PermissionError(f"Experiment root is outside the server allowlist ({ROOTS_ENV}).")
    if not path.is_dir():
        raise NotADirectoryError(str(path))
    return path


def checked_path(root: Path, relative: str) -> Path:
    p = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise PermissionError("Path escapes the authorized experiment root.")
    for part in [p, *p.parents]:
        if part == root:
            break
        if part.is_symlink():
            raise PermissionError("Symlink inputs are not followed.")
    if not p.resolve().is_relative_to(root):
        raise PermissionError("Path escapes the authorized experiment root.")
    return p


def output_root(experiment: Path | None = None) -> Path:
    raw = os.environ.get(OUTPUT_ENV) or os.environ.get("CHROMATIN_TRACE_OUTPUT_DIR")
    p = Path(raw).expanduser().resolve() if raw else (Path.cwd() / "results" / "step0_validation").resolve()
    # Never create validation artifacts within the inspected source tree.
    if experiment is not None and (p == experiment or p.is_relative_to(experiment)):
        raise PermissionError("Step 0 output directory must be outside the experiment input tree.")
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_rules(root: Path, supplied: StructureRules | None, doc: dict) -> StructureRules:
    """Only a documented step0 section is interpreted; no guessed YAML keys."""
    path = checked_path(root, "experiment.yaml")
    config = None
    if path.is_file():
        if path.stat().st_size > 1_000_000:
            raise ValueError("experiment.yaml exceeds 1 MB.")
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        if config is not None and not isinstance(config, dict):
            raise ValueError("experiment.yaml must contain a mapping.")
        doc["experiment_metadata"] = {"file": "experiment.yaml", "keys": sorted(str(k) for k in (config or {}))}
    if supplied is not None:
        doc["rules_source"] = "explicit_tool_arguments"
        return supplied
    if config and "step0" in config:
        doc["rules_source"] = "experiment.yaml:step0"
        return StructureRules.model_validate(config["step0"])
    doc["rules_source"] = "documented_mask_based_defaults"
    if config:
        finding(doc, "INCOMPLETE", "UNRECOGNIZED_CONFIGURATION", "experiment.yaml has no documented step0 section; no barcode or ROI meanings inferred.")
    return StructureRules()


def scan(root: Path, rules: StructureRules, doc: dict):
    files, directories, empty, extensions = [], [], [], Counter()
    visited = 0
    def walk(directory, depth):
        nonlocal visited
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            finding(doc, "ERROR", "DIRECTORY_UNREADABLE", str(exc), path=directory.relative_to(root), execution_error=True)
            return
        if not entries:
            rel = str(directory.relative_to(root))
            empty.append(rel)
            finding(doc, "INFO", "EMPTY_DIRECTORY", "Directory is empty.", path=rel)
        for p in entries:
            visited += 1
            if visited > rules.max_entries:
                return
            rel = str(p.relative_to(root))
            try:
                if p.is_symlink():
                    finding(doc, "WARNING", "SYMLINK_SKIPPED", "Symbolic link was not followed.", path=rel)
                    continue
                if p.is_dir():
                    directories.append(rel)
                    if p.name in rules.skip_directories:
                        finding(doc, "INFO", "DIRECTORY_EXCLUDED", "Directory excluded by discovery policy; no content read.", path=rel)
                    elif depth >= rules.max_depth:
                        finding(doc, "INCOMPLETE", "DEPTH_LIMIT", "Discovery depth limit reached.", path=rel)
                    else:
                        walk(p, depth + 1)
                elif p.is_file():
                    info = p.stat()
                    files.append({"path": rel, "size_bytes": info.st_size, "mtime_ns": info.st_mtime_ns})
                    extensions[p.suffix.lower() or "[none]"] += 1
                else:
                    finding(doc, "WARNING", "SPECIAL_FILE_SKIPPED", "Non-regular filesystem entry skipped.", path=rel)
            except OSError as exc:
                finding(doc, "ERROR", "FILE_INACCESSIBLE", str(exc), path=rel, execution_error=True)
    walk(root, 0)
    if visited > rules.max_entries:
        finding(doc, "INCOMPLETE", "ENTRY_LIMIT", "Discovery entry limit reached; inventory is incomplete.")
    doc.update(files=files, directories=directories, empty_directories=empty, file_counts_by_extension=dict(sorted(extensions.items())))
    candidates = [d for d in directories if re.fullmatch(rules.roi_pattern, Path(d).name)]
    candidates = [d for d in candidates if not any(str(Path(d).parent) == c or Path(d).is_relative_to(c) for c in candidates if c != d)]
    rois = []
    seen = set()
    for d in sorted(candidates):
        try:
            rid = identifier(Path(d).name)
        except ValueError:
            finding(doc, "ERROR", "ROI_NAME_INVALID", "ROI folder must encode an integer identifier.", path=d)
            continue
        if rid in seen:
            finding(doc, "ERROR", "DUPLICATE_ROI_FOLDER", "Several folders normalize to the same ROI identifier.", roi=rid, path=d)
        seen.add(rid)
        rois.append({"roi": rid, "directory": d, "tracing": [], "localization": [], "tables": []})
    doc["rois"] = rois
    if not rois:
        finding(doc, "INCOMPLETE", "NO_ROI_FOLDERS", "No candidate ROI directories discovered under the configured naming rule.")


def header_role(path: Path) -> str | None:
    """Read only bounded ECSV header/schema, not scientific records."""
    header = []
    size = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            size += len(line.encode("utf-8"))
            if size > 262144:
                raise ValueError("ECSV header exceeds 256 KiB.")
            header.append(line)
            if not line.startswith("#"):
                break
    if not header or not header[0].startswith("# %ECSV"):
        return None
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        table = Table.read("".join(header), format="ascii.ecsv")
    columns = set(table.colnames)
    roles = []
    if set(TRACE_COLUMNS) <= columns:
        roles.append("tracing")
    if set(LOCALIZATION_COLUMNS) <= columns:
        roles.append("localization")
    return roles[0] if len(roles) == 1 else None


def discover(root: Path, rules: StructureRules, doc: dict, mode: str):
    for roi in doc["rois"]:
        prefix = roi["directory"] + "/"
        local = [f["path"] for f in doc["files"] if f["path"].startswith(prefix) and f["path"].lower().endswith(".ecsv")]
        for role, patterns in (("tracing", [rules.trace_glob]), ("localization", rules.localization_globs)):
            matches = [f for f in local if any(fnmatch.fnmatchcase(f[len(prefix):], pat) for pat in patterns)] if mode != "metadata" else []
            # The glob's wildcard must not swallow derived Matrix_* ECSV outputs.
            if role == "tracing" and "ROI-" in rules.trace_glob:
                matches = [f for f in matches if re.search(r"ROI-[0-9]+\.ecsv$", Path(f).name)]
            method = "filename"
            if mode == "metadata" or (mode == "automatic" and not matches):
                method = "column_signature"
                for f in local:
                    try:
                        if header_role(checked_path(root, f)) == role:
                            matches.append(f)
                    except Exception as exc:
                        finding(doc, "WARNING", "HEADER_UNREADABLE", f"Could not identify file role from header: {str(exc)[:200]}", roi=roi["roi"], path=f)
            roi[role] = sorted(set(matches))
            roi[role + "_discovery_method"] = method
            if len(roi[role]) == 0:
                finding(doc, "ERROR", "MISSING_" + role.upper(), f"No {role} ECSV matches the selected discovery rule.", roi=roi["roi"], path=roi["directory"])
            elif len(roi[role]) > 1:
                finding(doc, "ERROR", "AMBIGUOUS_" + role.upper(), f"{len(roi[role])} candidate {role} tables; none selected automatically.", roi=roi["roi"], path=roi["directory"])
            if role == "tracing" and method == "filename":
                for f in roi[role]:
                    m = re.search(r"ROI-([0-9]+)\.ecsv$", f)
                    if not m or identifier(m.group(1)) != roi["roi"]:
                        finding(doc, "ERROR", "ROI_FILENAME_CONFLICT", "Trace filename ROI does not match its directory.", roi=roi["roi"], path=f)


def validate_structure(root: Path, rules: StructureRules, doc: dict):
    observed = {r["roi"] for r in doc["rois"]}
    if rules.expected_roi_ids is None:
        finding(doc, "INCOMPLETE", "EXPECTED_ROIS_UNAVAILABLE", "ROI count is discovered, not an authoritative expected ROI count; missing ROI checks unavailable.")
    else:
        expected = {identifier(v) for v in rules.expected_roi_ids}
        for rid in sorted(expected - observed, key=int):
            finding(doc, "ERROR", "MISSING_EXPECTED_ROI", "An explicitly expected ROI directory is missing.", roi=rid)
        for rid in sorted(observed - expected, key=int):
            finding(doc, "WARNING", "UNEXPECTED_ROI", "ROI is not in the configured expected list.", roi=rid)
    if not rules.required_trace_columns or not rules.required_localization_columns:
        finding(doc, "INCOMPLETE", "SCHEMA_RULES_UNAVAILABLE", "A required-column validation rule is empty.")
    for roi in doc["rois"]:
        for directory in rules.required_directories:
            rel = str(Path(roi["directory"]) / directory)
            if rel not in doc["directories"]:
                finding(doc, "ERROR", "MISSING_DIRECTORY", "Required ROI directory is missing.", roi=roi["roi"], path=rel)
        if rules.allowed_top_level_directories is not None:
            allowed = set(rules.allowed_top_level_directories)
            children = {Path(d).name for d in doc["directories"] if str(Path(d).parent) == roi["directory"]}
            for name in sorted(children - allowed):
                finding(doc, "WARNING", "UNEXPECTED_DIRECTORY", "ROI directory is outside the configured allowed set.", roi=roi["roi"], path=str(Path(roi["directory"]) / name))


def bed_reference(root: Path, rules: StructureRules, doc: dict):
    expected = None if rules.expected_barcodes is None else {identifier(v) for v in rules.expected_barcodes}
    if expected is not None and not rules.barcode_source:
        finding(doc, "INCOMPLETE", "BARCODE_AUTHORITY_UNDOCUMENTED", "Explicit expected barcodes have no barcode_source identifying their authority.")
    bed = {"file": rules.bed_file, "existence": "NOT_CONFIGURED", "mapping_status": "NOT_CONFIGURED", "barcodes": None}
    if rules.bed_file:
        path = checked_path(root, rules.bed_file)
        bed["existence"] = "PASS" if path.is_file() else "FAIL"
        if not path.is_file():
            finding(doc, "ERROR", "BED_MISSING", "Configured BED file does not exist.", path=rules.bed_file)
        elif rules.bed_barcode_column is None:
            finding(doc, "INCOMPLETE", "BED_MAPPING_UNAVAILABLE", "BED exists but barcode column has not been explicitly specified; BED has no universal barcode field.", path=rules.bed_file)
            bed["mapping_status"] = "INCOMPLETE"
        else:
            mapping = {}
            try:
                if path.stat().st_size > rules.max_table_bytes:
                    raise ValueError("BED exceeds configured size limit")
                for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if not line.strip() or line.startswith(("#", "track", "browser")):
                        continue
                    values = line.split()
                    if len(values) < max(3, rules.bed_barcode_column):
                        raise ValueError(f"BED line {line_no} has insufficient columns")
                    start, end = int(values[1]), int(values[2])
                    if start < 0 or end <= start:
                        raise ValueError(f"Invalid interval on BED line {line_no}")
                    barcode = identifier(values[rules.bed_barcode_column - 1])
                    interval = (values[0], start, end)
                    if barcode in mapping:
                        finding(doc, "ERROR", "BED_DUPLICATE_BARCODE" if mapping[barcode] == interval else "BED_CONFLICTING_BARCODE", f"BED barcode {barcode} occurs more than once.", path=rules.bed_file)
                    mapping[barcode] = interval
                if not mapping:
                    raise ValueError("BED contains no barcode mappings")
                bed["barcodes"] = sorted(mapping, key=int)
                bed["mapping_status"] = "FAIL" if any(f["code"].startswith("BED_") and f["severity"] == "ERROR" for f in doc["findings"]) else "PASS"
                bed["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                if expected is not None and expected != set(mapping):
                    finding(doc, "ERROR", "BARCODE_REFERENCE_CONFLICT", "Explicit expected barcode set conflicts with the configured BED mapping.")
                    bed["mapping_status"] = "FAIL"
                if expected is None:
                    expected = set(mapping)
            except (OSError, ValueError) as exc:
                finding(doc, "ERROR", "BED_INVALID", str(exc), path=rules.bed_file)
                bed["mapping_status"] = "FAIL"
    elif rules.bed_required:
        finding(doc, "INCOMPLETE", "BED_ASSOCIATION_UNAVAILABLE", "BED association is required but no file is configured.")
    doc["bed"] = bed
    doc["expected_barcodes"] = None if expected is None else sorted(expected, key=int)
    doc["barcode_source"] = rules.barcode_source or (f"{rules.bed_file}:column{rules.bed_barcode_column}" if expected is not None and rules.bed_file else None)
    if expected is None:
        finding(doc, "INCOMPLETE", "EXPECTED_BARCODES_UNAVAILABLE", "No authoritative expected barcode set; observed coverage is reported without inventing missing barcodes.")
    return expected


def validate_tables(root: Path, rules: StructureRules, doc: dict):
    expected = bed_reference(root, rules, doc)
    schemas = {"tracing": None, "localization": None}
    for roi in doc["rois"]:
        for role in ("tracing", "localization"):
            # Ambiguous candidates are reported, never silently selected or combined.
            if len(roi[role]) != 1:
                continue
            rel = roi[role][0]
            info = {"path": rel, "role": role, "roi": roi["roi"], "valid": False}
            roi["tables"].append(info)
            try:
                path = checked_path(root, rel)
                before = path.stat()
                if before.st_size > rules.max_table_bytes:
                    finding(doc, "INCOMPLETE", "TABLE_SIZE_LIMIT", "Table exceeds configured byte limit; not loaded.", roi=roi["roi"], path=rel)
                    continue
                # ECSV parser is required: an ASCII/CSV guess is not an acceptable fallback.
                table = Table.read(path, format="ascii.ecsv")
                info["record_count"] = len(table)
                if len(table) > rules.max_records:
                    finding(doc, "INCOMPLETE", "RECORD_LIMIT", "Table exceeds configured record limit; identifiers not analyzed.", roi=roi["roi"], path=rel)
                    continue
                info["columns"] = list(table.colnames)
                info["schema"] = {c: str(table[c].dtype) for c in table.colnames}
                info["metadata"] = {str(k): str(v)[:2000] for k, v in table.meta.items()}
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                after = path.stat()
                if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
                    raise OSError("Input changed during validation; result cannot be trusted")
                info.update(size_bytes=after.st_size, mtime_ns=after.st_mtime_ns, sha256=digest.hexdigest())
                required = rules.required_trace_columns if role == "tracing" else rules.required_localization_columns
                missing = sorted(set(required) - set(table.colnames))
                info["missing_required_columns"] = missing
                if missing:
                    finding(doc, "ERROR", "MISSING_COLUMNS", f"Required columns missing: {', '.join(missing)}.", roi=roi["roi"], path=rel)
                allowed = rules.allowed_trace_columns if role == "tracing" else rules.allowed_localization_columns
                if allowed is not None:
                    extra = sorted(set(table.colnames) - set(allowed))
                    if extra:
                        finding(doc, "WARNING", "UNEXPECTED_COLUMNS", f"Columns outside configured schema: {', '.join(extra)}.", roi=roi["roi"], path=rel)
                if schemas[role] is None:
                    schemas[role] = info["schema"]
                elif schemas[role] != info["schema"]:
                    finding(doc, "WARNING", "SCHEMA_INCONSISTENCY", "Column names or dtypes differ between ROI tables of the same role.", roi=roi["roi"], path=rel)
                if "ROI #" in table.colnames:
                    values = sorted({identifier(v) for v in table["ROI #"]}, key=int)
                    info["observed_roi_ids"] = values
                    if values != [roi["roi"]]:
                        finding(doc, "ERROR", "ROI_TABLE_CONFLICT", f"Observed ROI identifiers {values} disagree with directory ROI {roi['roi']}.", roi=roi["roi"], path=rel)
                if "Barcode #" in table.colnames:
                    observed = {identifier(v) for v in table["Barcode #"]}
                    info["observed_barcodes"] = sorted(observed, key=int)
                    info["unique_barcode_count"] = len(observed)
                    info["expected_barcodes"] = doc["expected_barcodes"]
                    info["missing_barcodes"] = None if expected is None else sorted(expected - observed, key=int)
                    info["unexpected_barcodes"] = None if expected is None else sorted(observed - expected, key=int)
                    if expected is not None and expected - observed:
                        finding(doc, "ERROR" if rules.require_each_barcode else "WARNING", "MISSING_BARCODE_OBSERVATIONS", f"Missing expected barcode observations: {', '.join(info['missing_barcodes'])}.", roi=roi["roi"], path=rel)
                    if expected is not None and observed - expected:
                        finding(doc, "WARNING", "UNEXPECTED_BARCODES", f"Observed barcodes outside reference set: {', '.join(info['unexpected_barcodes'])}.", roi=roi["roi"], path=rel)
                    if doc["bed"]["barcodes"] is not None:
                        info["barcodes_not_in_bed"] = sorted(observed - set(doc["bed"]["barcodes"]), key=int)
                if "Trace_ID" in table.colnames and role == "tracing":
                    if np.ma.getmaskarray(table["Trace_ID"]).any():
                        finding(doc, "ERROR", "MISSING_TRACE_IDS", "Trace_ID contains missing values.", roi=roi["roi"], path=rel)
                    info["unique_trace_count"] = len(set(str(v) for v in table["Trace_ID"] if not np.ma.is_masked(v)))
                # Identity and coordinate presence/type checks are schema checks, not analysis.
                coords = ("x", "y", "z") if role == "tracing" else ("xcentroid", "ycentroid", "zcentroid")
                for column in coords:
                    if column in table.colnames:
                        if table[column].dtype.kind not in "iuf":
                            finding(doc, "ERROR", "COORDINATE_TYPE", f"{column} is not a numeric column.", roi=roi["roi"], path=rel)
                        elif np.ma.getmaskarray(table[column]).any() or not np.isfinite(np.asarray(table[column])).all():
                            finding(doc, "WARNING", "NONFINITE_COORDINATES", f"{column} contains masked or non-finite coordinates.", roi=roi["roi"], path=rel)
                info["valid"] = not any(f["severity"] == "ERROR" and f.get("path") == rel for f in doc["findings"])
            except PermissionError as exc:
                finding(doc, "ERROR", "TABLE_INACCESSIBLE", str(exc), roi=roi["roi"], path=rel, execution_error=True)
            except Exception as exc:
                finding(doc, "ERROR", "INVALID_ECSV", f"{type(exc).__name__}: {str(exc)[:300]}", roi=roi["roi"], path=rel, execution_error=True)


def evaluate(experiment_root: str, rules: StructureRules | None = None, *, phase="full", discovery_mode="filename") -> dict:
    """Deterministic baseline shared by individual and aggregated tools."""
    doc = {"schema_version": 1, "experiment_root": experiment_root, "findings": [], "rois": [], "files": [], "phase": phase}
    try:
        root = authorized_root(experiment_root)
        doc["experiment_root"] = str(root)
        doc["input_authorized"] = True
        policy = load_rules(root, rules, doc)
        doc["rules"] = policy.model_dump()
        scan(root, policy, doc)
        if phase != "inspection":
            discover(root, policy, doc, discovery_mode)
        if phase in {"structure", "tables", "full"}:
            validate_structure(root, policy, doc)
        if phase in {"tables", "full"}:
            validate_tables(root, policy, doc)
    except Exception as exc:
        finding(doc, "ERROR", "VALIDATION_EXECUTION_ERROR", f"{type(exc).__name__}: {str(exc)[:300]}", execution_error=True)
    doc["status"] = status(doc["findings"])
    return doc


def summarize(doc: dict) -> dict:
    fs = doc["findings"]
    rois = doc["rois"]
    tables = [t for r in rois for t in r["tables"]]
    return {
        "status": doc["status"], "phase": doc["phase"],
        "full_validation_performed": doc["phase"] in {"tables", "full"}, "roi_count": len(rois),
        "roi_count_basis": "discovered_folders",
        "tracing_tables": sum(len(r["tracing"]) for r in rois),
        "localization_tables": sum(len(r["localization"]) for r in rois),
        "tables_parsed": sum("record_count" in t for t in tables),
        "ecsv_records_inspected": sum(t.get("record_count", 0) for t in tables),
        "files_inspected": len(doc["files"]),
        "complete_file_rois": sum(len(r["tracing"]) == len(r["localization"]) == 1 for r in rois) if doc["phase"] != "inspection" else None,
        "rois_with_warnings": len({f["roi"] for f in fs if f["severity"] == "WARNING" and "roi" in f}),
        "rois_with_missing_files": len({f["roi"] for f in fs if f["code"] in {"MISSING_TRACING", "MISSING_LOCALIZATION"}}),
        "rois_with_invalid_ecsv": len({f["roi"] for f in fs if f["code"] in {"INVALID_ECSV", "MISSING_COLUMNS", "TABLE_INACCESSIBLE"}}),
        "error_count": sum(f["severity"] == "ERROR" for f in fs),
        "warning_count": sum(f["severity"] == "WARNING" for f in fs),
        "incomplete_count": sum(f["severity"] == "INCOMPLETE" for f in fs),
        "finding_count": len(fs),
        "file_counts_by_extension": doc.get("file_counts_by_extension", {}),
        "bed_files_discovered": sum(f["path"].lower().endswith(".bed") for f in doc["files"]),
        "empty_directory_count": len(doc.get("empty_directories", [])),
        "conclusion": ("Only the requested partial check was evaluated; full Step 0 readiness has not been assessed."
                       if doc["phase"] not in {"tables", "full"}
                       else "Step 0 checks passed within the configured policy; downstream analysis was not run."
                       if doc["status"] == "PASS"
                       else "Review failures or incomplete checks before claiming readiness; downstream analysis was not run."),
    }


def bounded(value):
    """Bound nested evidence, while complete evidence stays in details.json."""
    if isinstance(value, list):
        items = [bounded(v) for v in value[:100]]
        return items if len(value) <= 100 else {"items": items, "total": len(value), "truncated": True, "full_evidence": "details.json"}
    if isinstance(value, dict):
        return {k: bounded(v) for k, v in value.items()}
    return value


def page(items, offset, limit):
    return {"items": [bounded(v) for v in items[offset:offset + limit]], "total": len(items), "offset": offset, "next_offset": offset + limit if offset + limit < len(items) else None}


def human_report(doc, summary):
    lines = ["# Experiment Data Quality Report", "", f"Status: **{summary['status']}**", "", f"Experiment: {doc['experiment_root']}", f"Discovered ROIs: {summary['roi_count']}", f"ROIs with complete required file associations: {summary['complete_file_rois']}", f"Parsed tables: {summary['tables_parsed']}", f"Errors: {summary['error_count']}; warnings: {summary['warning_count']}; incomplete checks: {summary['incomplete_count']}", "", "Expected barcodes: " + str(doc.get('expected_barcodes')), "BED association: " + str(doc.get('bed')), "", "## Per-ROI coverage", ""]
    for roi in doc["rois"]:
        lines.append(f"### ROI {roi['roi']} ({roi['directory']})")
        lines.append(f"Tracing candidates: {len(roi['tracing'])}; localization candidates: {len(roi['localization'])}")
        for t in roi["tables"]:
            lines.append(f"- {t['role']}: {t['path']}; records={t.get('record_count', 'unavailable')}; observed barcodes={t.get('observed_barcodes')}; missing={t.get('missing_barcodes')}; unexpected={t.get('unexpected_barcodes')}; traces={t.get('unique_trace_count', 'not applicable')}")
        lines.append("")
    lines += ["## Findings", ""]
    lines += [f"- {f['severity']} [{f['code']}] ROI {f.get('roi', '—')}: {f['message']} ({f.get('path', '')})" for f in doc["findings"]]
    lines += ["", "## Conclusion", "", summary["conclusion"], "Warnings do not change PASS to FAIL unless the configured policy explicitly requires that. PASS is not a biological-equivalence finding or permission to merge.", ""]
    return "\n".join(lines)


def generate_data_quality_report(doc: dict) -> dict:
    """Always called for a full validation, including ERROR/FAIL/INCOMPLETE."""
    experiment = Path(doc["experiment_root"]).resolve() if doc.get("input_authorized") else None
    directory = output_root(experiment) / uuid4().hex
    directory.mkdir()
    run_id = directory.name
    summary = summarize(doc)
    summary.update(run_id=run_id, generated_at_utc=datetime.now(timezone.utc).isoformat(),
                   report_path=str(directory / "summary.json"), details_path=str(directory / "details.json"), human_report_path=str(directory / "report.md"))
    doc["summary"] = summary
    (directory / "details.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    (directory / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    (directory / "report.md").write_text(human_report(doc, summary), encoding="utf-8")
    return summary


def read_run(run_id: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ValueError("Invalid validation run identifier.")
    path = output_root() / run_id / "details.json"
    if path.is_symlink() or path.parent.is_symlink():
        raise PermissionError("Symlink report references are not accepted.")
    return json.loads(path.read_text(encoding="utf-8"))


def compact(doc, *, offset=0, limit=20, detailed=False, report=False):
    result = generate_data_quality_report(doc) if report else summarize(doc)
    result = dict(result)
    ordered = sorted(doc["findings"], key=lambda f: ({"ERROR": 0, "INCOMPLETE": 1, "WARNING": 2, "INFO": 3}[f["severity"]], f.get("roi", ""), f.get("path", ""), f["code"]))
    result["findings"] = page(ordered, offset, limit)
    if detailed:
        result["rois"] = page(doc["rois"], offset, limit)
    return result


def measured(name, arguments, function):
    arguments = {k: (v.model_dump() if isinstance(v, BaseModel) else v) for k, v in arguments.items() if k != "work"}
    start = time.perf_counter()
    try:
        result = function()
        success = result.get("status") not in {"ERROR"}
    except Exception as exc:
        result = {"status": "ERROR", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        success = False
    elapsed = time.perf_counter() - start
    encoded = Step0Result.model_validate(result).model_dump_json().encode()
    # Server-side bytes/timing are not provider model token usage.
    event = {"invocation_id": uuid4().hex, "tool_name": name, "execution_seconds": elapsed,
             "input_bytes": len(json.dumps(arguments, default=str).encode()), "output_bytes": len(encoded),
             "files_inspected": result.get("files_inspected", 0), "ecsv_records_inspected": result.get("ecsv_records_inspected", 0),
             "finding_count": result.get("finding_count", result.get("total", 0)), "success": success,
             "validation_status": result.get("status"), "estimated_response_tokens": None, "tokenizer": None,
             "model_usage": "unavailable_at_mcp_server"}
    try:
        if os.environ.get("CHROMATIN_STEP0_ESTIMATE_TOKENS") != "1":
            raise ImportError("Tokenizer estimates are opt-in; no vocabulary downloads by default")
        import tiktoken
        encoding = tiktoken.get_encoding("o200k_base")
        event["estimated_response_tokens"] = len(encoding.encode(encoded.decode()))
        event["tokenizer"] = "o200k_base_estimate_not_provider_usage"
    except Exception:
        pass
    try:
        experiment = None
        if arguments.get("experiment_root"):
            try:
                experiment = authorized_root(arguments["experiment_root"])
            except (OSError, ValueError):
                pass
        with (output_root(experiment) / "tool_metrics.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")
    except OSError:
        result["telemetry_error"] = "Could not persist tool telemetry."
    return Step0Result.model_validate(result)


def register_step0_tools(mcp):
    """Register on the existing server, preserving its tools and resources."""
    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    writer = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)

    @mcp.tool(annotations=read_only)
    async def inspect_experiment_directory(
        experiment_root: str, rules: StructureRules | None = None,
        max_findings: Annotated[int, Field(ge=1, le=100)] = 20,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> Step0Result:
        """Read-only bounded filesystem summary; no scientific table loads. Recursion limits are in rules."""
        return measured("inspect_experiment_directory", locals(), lambda: compact(evaluate(experiment_root, rules, phase="inspection"), offset=offset, limit=max_findings))

    @mcp.tool(annotations=read_only)
    async def discover_roi_files(
        experiment_root: str, rules: StructureRules | None = None,
        roi_identifier: str | None = None,
        discovery_mode: Literal["filename", "metadata", "automatic"] = "filename",
        max_findings: Annotated[int, Field(ge=1, le=100)] = 20,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> Step0Result:
        """Map trace/localization roles; default mask-based filename rules, never choose ambiguous matches. Paged ROI mappings."""
        def work():
            doc = evaluate(experiment_root, rules, phase="discovery", discovery_mode=discovery_mode)
            if roi_identifier is not None:
                rid = identifier(roi_identifier)
                doc["rois"] = [r for r in doc["rois"] if r["roi"] == rid]
                doc["findings"] = [f for f in doc["findings"] if f.get("roi", rid) == rid]
                if not doc["rois"]:
                    finding(doc, "ERROR", "ROI_NOT_FOUND", "Requested ROI not discovered.", roi=rid)
                doc["status"] = status(doc["findings"])
            return compact(doc, offset=offset, limit=max_findings, detailed=True)
        return measured("discover_roi_files", locals(), work)

    @mcp.tool(annotations=read_only)
    async def validate_experiment_structure(
        experiment_root: str, rules: StructureRules | None = None,
        max_findings: Annotated[int, Field(ge=1, le=100)] = 20,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> Step0Result:
        """Validate configurable directories/file roles and ROI naming; no ECSV record analysis."""
        return measured("validate_experiment_structure", locals(), lambda: compact(evaluate(experiment_root, rules, phase="structure"), offset=offset, limit=max_findings))

    @mcp.tool(annotations=writer)
    async def validate_ecsv_tables(
        experiment_root: str, rules: StructureRules | None = None,
        discovery_mode: Literal["filename", "metadata", "automatic"] = "filename",
        max_findings: Annotated[int, Field(ge=1, le=100)] = 20,
        output_level: Literal["compact", "detailed"] = "compact",
    ) -> Step0Result:
        """Parse selected ECSV tables, validate schema/ROI/BED/barcodes, always save a quality report. Raw inputs unchanged."""
        return measured("validate_ecsv_tables", locals(), lambda: compact(evaluate(experiment_root, rules, phase="tables", discovery_mode=discovery_mode), limit=max_findings, detailed=output_level == "detailed", report=True))

    @mcp.tool(annotations=writer)
    async def run_experiment_validation(
        experiment_root: str, rules: StructureRules | None = None,
        discovery_mode: Literal["filename", "metadata", "automatic"] = "filename",
        max_findings: Annotated[int, Field(ge=1, le=100)] = 20,
        output_level: Literal["compact", "detailed"] = "compact",
    ) -> Step0Result:
        """Preferred complete Step 0: discovery, structure/ECSV/reference checks and mandatory report; never run downstream analysis."""
        return measured("run_experiment_validation", locals(), lambda: compact(evaluate(experiment_root, rules, discovery_mode=discovery_mode), limit=max_findings, detailed=output_level == "detailed", report=True))

    @mcp.tool(annotations=read_only, name="generate_data_quality_report")
    async def report_existing_validation(validation_run_id: str) -> Step0Result:
        """Return a saved Step 0 report summary by run ID; no repeated table analysis or model calculations."""
        return measured("generate_data_quality_report", locals(), lambda: read_run(validation_run_id)["summary"])

    @mcp.tool(annotations=read_only)
    async def read_validation_details(
        validation_run_id: str, section: Literal["findings", "rois", "files"] = "findings",
        offset: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> Step0Result:
        """Page cached findings/ROI evidence/file provenance from an existing report without loading experiment tables again."""
        return measured("read_validation_details", locals(), lambda: page(read_run(validation_run_id)[section], offset, limit))
