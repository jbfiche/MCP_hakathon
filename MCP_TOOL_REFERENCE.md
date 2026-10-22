# MCP tool reference

Original tools inspected: 15 October 2026. Seven Step 0 tools added on 16 October 2026; see references below. Scope: the two production servers in this repository, not the demonstration plugins. Branch at inspection: `Test`; source commit: `979645c242c0be4fa47e3d0479e7322561e03d8e`. Static source inspection only: no server, test suite or experiment analysis was run.

## How to read this reference

- **Native Traceratops analysis**: delegates the main calculation to an existing Traceratops script/function.
- **Reader + custom logic**: uses Traceratops to read tables, then performs calculations in the MCP server. This is not a native analysis-script wrapper.
- **Management/reporting**: registers paths, lists datasets or formats supplied results.

All analysis executes in the MCP process on its configured host, using that host’s CPU and memory. With local deployment this is the local PC; the protocol itself does not create a virtual machine. These implementations load full ECSV tables into local memory. Tools return compact summaries and artifact paths. Input tables are preserved; generated artifacts use configured output directories.

## Server inventory

| Server | Tools | Main role |
|---|---:|---|
| chromatin-trace-mcp | 26 | Dataset management, Step 0 validation, native scientific wrappers and approval |
| chromatin-report-mcp | 2 | Format comparison results as Markdown, HTML or PDF |

## Tool details

### `register_dataset`

Server: `chromatin-trace-mcp`. Classification: **Reader + custom management**.

**What it does:** Validates ECSV paths, opens trace/localization tables and registers a name; optionally persists a JSON catalog.

**Traceratops calls:** read_table_from_ecsv; LocalizationTable.load

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `name` | `str` | Required |
| `trace_file` | `str` | Required |
| `localization_file` | `str ∣ None` | `None` |
| `overwrite` | `bool` | `False` |

**Returned output:** `RegisteredDataset` with these fields:

- `name`: `str`.
- `trace_file`: `str`.
- `localization_file`: `str | None`.
- `saved_to_catalog`: `str | None`.
- `note`: `str`.

**Files / effects:** May write catalog; inputs unchanged.

**Interpretation and limits:** Name must match `[A-Za-z0-9][A-Za-z0-9_.-]{0,63}`; `current` is reserved. Paths must identify existing ECSV files. This validates readability, not biological suitability. Registration persists only if `CHROMATIN_DATASETS_JSON` is configured. `overwrite=True` replaces the registration, not the raw data.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `register_dataset` (line 634 at inspection).

### `list_datasets`

Server: `chromatin-trace-mcp`. Classification: **Management only**.

**What it does:** Lists the environment-configured current dataset and named registry/catalog entries.

**Traceratops calls:** None

**Expected inputs:**

None.

**Returned output:** `DatasetListResult` with these fields:

- `datasets`: `list[DatasetInfo]`.

**Files / effects:** Read-only.

**Interpretation and limits:** Returns names and paths; it does not open the data tables or perform QC.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `list_datasets` (line 714 at inspection).

### `inspect_dataset`

Server: `chromatin-trace-mcp`. Classification: **Reader + custom summary**.

**What it does:** Loads a named trace and counts rows, traces, barcodes and ROIs.

**Traceratops calls:** read_table_from_ecsv via _load_dataset_trace

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `dataset_name` | `str` | Required |

**Returned output:** `TraceSummary` with these fields:

- `source_file`: `str`.
- `row_count`: `int`.
- `column_names`: `list[str]`.
- `metadata`: `dict[str, str]`.
- `unique_trace_count`: `int | None`.
- `unique_barcode_count`: `int | None`.
- `unique_roi_count`: `int | None`.

**Files / effects:** Read-only.

**Interpretation and limits:** Returns table structure and simple counts. This is custom summarization after a Traceratops read, not a call to a Traceratops analysis script.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `inspect_dataset` (line 733 at inspection).

### `inspect_current_trace`

Server: `chromatin-trace-mcp`. Classification: **Reader + custom summary**.

**What it does:** Inspects the environment-configured trace.

**Traceratops calls:** read_table_from_ecsv via load_current_trace

**Expected inputs:**

None.

**Returned output:** `TraceSummary` with these fields:

- `source_file`: `str`.
- `row_count`: `int`.
- `column_names`: `list[str]`.
- `metadata`: `dict[str, str]`.
- `unique_trace_count`: `int | None`.
- `unique_barcode_count`: `int | None`.
- `unique_roi_count`: `int | None`.

**Files / effects:** Read-only.

**Interpretation and limits:** Requires `CHROMATIN_TRACE_ECSV`; there are no tool arguments. Equivalent inspection scope to inspect_dataset, using the configured current file.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `inspect_current_trace` (line 760 at inspection).

### `trace_stats`

Server: `chromatin-trace-mcp`. Classification: **Native Traceratops analysis**.

**What it does:** Returns native ROI, trace and barcode counts, library version and captured terminal report.

**Traceratops calls:** traceratops.trace_stats.compute_trace_statistics

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `dataset_name` | `str` | `'current'` |

**Returned output:** `TraceStatsResult` with these fields:

- `source_file`: `str`.
- `traceratops_version`: `str`.
- `unique_roi_count`: `int`.
- `unique_trace_count`: `int`.
- `unique_barcode_count`: `int`.
- `traceratops_report`: `str`.

**Files / effects:** Read-only.

**Interpretation and limits:** Native trace_stats is the calculation engine. Its terminal text is captured and selected counts are parsed into structured output.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `trace_stats` (line 797 at inspection).

### `filter_traces`

Server: `chromatin-trace-mcp`. Classification: **Native Traceratops analysis**.

**What it does:** Applies barcode/label/coordinate/length/duplicate filters to a working copy.

**Traceratops calls:** traceratops.trace_filter.runtime

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `dataset_name` | `str` | `'current'` |
| `minimum_barcodes` | `int` | `2` |
| `remove_barcodes` | `list[int] ∣ None` | `None` |
| `keep_label` | `str ∣ None` | `None` |
| `remove_label` | `str ∣ None` | `None` |
| `clean_duplicate_spots` | `bool` | `False` |
| `x_min` | `float` | `0` |
| `x_max` | `float ∣ None` | `None` |
| `y_min` | `float` | `0` |
| `y_max` | `float ∣ None` | `None` |
| `z_min` | `float` | `0` |
| `z_max` | `float ∣ None` | `None` |

**Returned output:** `FilterTraceResult` with these fields:

- `source_file`: `str`.
- `output_file`: `str`.
- `input_row_count`: `int`.
- `output_row_count`: `int`.
- `artifacts`: `list[GeneratedArtifact]`.
- `traceratops_report`: `str`.

**Files / effects:** New filtered ECSV and artifacts.

**Interpretation and limits:** Runs native trace_filter against a working copy. Returns a newly generated filtered ECSV and artifacts. Coordinate bounds default to zero minima, so inspect these parameters before assuming a pass-through. Minimum barcodes is described in the interface as spots/barcodes per trace; do not assume this guarantees distinct loci or chromosome assignment. Duplicate cleanup is off by default.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `filter_traces` (line 858 at inspection).

### `trace_to_matrix`

Server: `chromatin-trace-mcp`. Classification: **Native Traceratops analysis**.

**What it does:** Generates per-trace pairwise distances, N-matrix, barcode index and standard plots.

**Traceratops calls:** traceratops.trace_to_matrix.runtime

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `dataset_name` | `str` | `'current'` |
| `distance_threshold` | `float ∣ None` | `None` |
| `n_jobs` | `int` | `1` |
| `plot_histograms` | `bool` | `False` |

**Returned output:** `TraceMatrixResult` with these fields:

- `source_file`: `str`.
- `output_directory`: `str`.
- `matrix_shape`: `list[int]`.
- `unique_barcode_count`: `int`.
- `trace_count`: `int`.
- `distance_threshold`: `float | None`.
- `artifacts`: `list[GeneratedArtifact]`.
- `traceratops_report`: `str`.

**Files / effects:** NumPy matrices and plots.

**Interpretation and limits:** Native trace_to_matrix produces distance matrices and plots. The PWD matrix shape is [barcodes, barcodes, traces]. n_jobs accepts -1 or integers 1–32; 0 is rejected. distance_threshold is specified as microns: verify coordinate metadata first. The returned shape is not a verification of every scientific matrix value.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `trace_to_matrix` (line 982 at inspection).

### `localization_analyzer`

Server: `chromatin-trace-mcp`. Classification: **Native Traceratops analysis**.

**What it does:** Runs localization QC on the associated localization table.

**Traceratops calls:** traceratops.localization_analyzer.run; LocalizationTable.load

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `dataset_name` | `str` | `'current'` |
| `output_format` | `str` | `'png'` |

**Returned output:** `LocalizationAnalysisResult` with these fields:

- `source_file`: `str`.
- `row_count`: `int`.
- `unique_barcode_count`: `int`.
- `output_file`: `str`.
- `artifacts`: `list[GeneratedArtifact]`.
- `traceratops_report`: `str`.

**Files / effects:** QC figure and artifact metadata.

**Interpretation and limits:** Requires an associated localization file. Runs native localization_analyzer. The main scientific output is a QC figure; the wrapper does not expose all plotted values as a numeric table.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `localization_analyzer` (line 1070 at inspection).

### `compare_datasets`

Server: `chromatin-trace-mcp`. Classification: **Reader + custom QC**.

**What it does:** Compares schemas, units, barcode overlap, missing coordinates, sizes, multiplicity and optional SNR.

**Traceratops calls:** read_table_from_ecsv; optional LocalizationTable.load

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `first_dataset` | `str` | Required |
| `second_dataset` | `str` | Required |

**Returned output:** `DatasetComparisonResult` with these fields:

- `first`: `DatasetQualityMetrics`.
- `second`: `DatasetQualityMetrics`.
- `status`: `Literal['compatible', 'compatible_with_warnings', 'not_comparable']`.
- `comparable`: `bool`.
- `shared_barcodes`: `list[str]`.
- `only_in_first`: `list[str]`.
- `only_in_second`: `list[str]`.
- `same_columns`: `bool`.
- `columns_only_in_first`: `list[str]`.
- `columns_only_in_second`: `list[str]`.
- `coordinate_unit_first`: `str | None`.
- `coordinate_unit_second`: `str | None`.
- `reasons`: `list[str]`.
- `warnings`: `list[str]`.

**Files / effects:** Read-only structured comparison.

**Interpretation and limits:** Requires two distinct registered names. Custom QC compares required columns (Trace_ID, Barcode #, ROI #, x, y, z), schema, barcode sets, unit strings, sizes, median rows per trace, missing/non-finite coordinates, repeated trace/barcode rows and optional localization median SNR. Missing units produce a warning; different known unit strings reject comparison without unit conversion. This is not a distance-map comparison, Pearson calculation, genome-assembly/BED validation or biological equivalence test. It calls no other exposed MCP tool.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `compare_datasets` (line 1221 at inspection).

### `localization_quality_summary`

Server: `chromatin-trace-mcp`. Classification: **Reader + custom QC**.

**What it does:** Computes SNR/intensity quantiles and identifier coverage locally.

**Traceratops calls:** LocalizationTable.load

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `dataset_name` | `str` | Required |
| `intensity_columns` | `list[Literal['mean_intensity', 'flux', 'spot_pixel_percentage']]` | `['mean_intensity', 'flux']` |

**Returned output:** `LocalizationQualitySummary` with these fields:

- `dataset_name`: `str`.
- `source_file`: `str`.
- `row_count`: `int`.
- `unique_buid_count`: `int`.
- `unique_barcode_count`: `int`.
- `unique_roi_count`: `int`.
- `unique_cell_count`: `int | None`.
- `snr`: `NumericDistribution`.
- `intensity_distributions`: `list[NumericDistribution]`.

**Files / effects:** Read-only structured summary.

**Interpretation and limits:** Requires localization columns Buid, Barcode #, ROI # and snr. Select at least one intensity column from mean_intensity, flux and spot_pixel_percentage; defaults are mean_intensity and flux. Custom distributions report finite/missing counts, minimum, p10, median, p90, p99, maximum, mean and standard deviation. It does not choose a threshold or invoke native localization_analyzer.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `localization_quality_summary` (line 1317 at inspection).

### `snr_filter_sweep`

Server: `chromatin-trace-mcp`. Classification: **Reader + custom analysis**.

**What it does:** Evaluates 1–5 explicit SNR thresholds using NumPy; joins Buid to Spot_ID and measures retention/multiplicity.

**Traceratops calls:** read_table_from_ecsv; LocalizationTable.load; no native filter_runtime call

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `first_dataset` | `str` | Required |
| `second_dataset` | `str` | Required |
| `thresholds` | `list[float]` | Required |
| `intensity_columns` | `list[Literal['mean_intensity', 'flux', 'spot_pixel_percentage']]` | `['mean_intensity', 'flux']` |

**Returned output:** `SNRFilterSweepResult` with these fields:

- `thresholds`: `list[float]`.
- `intensity_columns`: `list[str]`.
- `first`: `SNRFilterDatasetResult`.
- `second`: `SNRFilterDatasetResult`.
- `artifacts`: `list[GeneratedArtifact]`.
- `notes`: `list[str]`.

**Files / effects:** JSON summary and PNG figures; inputs unchanged.

**Interpretation and limits:** Requires two distinct registered names with both trace and localization files. Supply 1–5 explicit finite SNR thresholds in [0,100]; they are sorted and deduplicated. Custom NumPy code retains finite snr >= threshold and joins localization Buid to trace Spot_ID. It reports localization/trace-row retention, traces with at least one retained spot, intensity distributions and multiplicity. A retained trace does not imply sufficient locus completeness. It writes summary JSON and PNG plots, not filtered ECSV datasets. It does not call trace_filter, localization_analyzer, duplicate_statistics or other exposed tools. No automatic best-threshold selection.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `snr_filter_sweep` (line 1590 at inspection).

### `duplicate_statistics`

Server: `chromatin-trace-mcp`. Classification: **Reader + custom QC**.

**What it does:** Uses Counter to report repeated grouping keys in trace or localization tables.

**Traceratops calls:** read_table_from_ecsv or LocalizationTable.load

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `first_dataset` | `str` | Required |
| `second_dataset` | `str` | Required |
| `table_kind` | `Literal['trace', 'localization']` | `'trace'` |

**Returned output:** `DuplicateStatisticsResult` with these fields:

- `first`: `DuplicateMultiplicityStats`.
- `second`: `DuplicateMultiplicityStats`.
- `table_kind`: `Literal['trace', 'localization']`.
- `same_grouping_columns`: `bool`.
- `notes`: `list[str]`.

**Files / effects:** Read-only structured comparison.

**Interpretation and limits:** Requires two distinct registered names. Custom Counter calculations group trace rows by (Trace_ID, Barcode #), or localization rows by (ROI #, CellID #, Barcode #). The output names count EXTRA rows: zero_duplicate_groups means one observed row, one_duplicate_groups means two rows, two_duplicate_groups means three rows, more_than_two_duplicate_groups means four or more rows. Zero does not mean an undetected locus. Repetition is not automatically an error or proof of an allele.

Source: `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`, function `duplicate_statistics` (line 1817 at inspection).

### `write_comparison_pdf`

Server: `chromatin-report-mcp`. Classification: **Reporting only**.

**What it does:** Renders a supplied comparison and optional sweep into a PDF; may build figures from supplied summaries.

**Traceratops calls:** None

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `comparison` | `DatasetComparison` | Required |
| `report_title` | `str` | `'Chromatin dataset comparison'` |
| `scientist_notes` | `str ∣ None` | `None` |
| `recommendations` | `str ∣ None` | `None` |
| `conclusion` | `str ∣ None` | `None` |
| `sweep` | `SNRFilterSweep ∣ None` | `None` |

**Returned output:** `PdfReportArtifact` with these fields:

- `path`: `str`.
- `format`: `Literal['pdf']`.
- `size_bytes`: `int`.
- `comparison_status`: `str`.
- `generated_at_utc`: `str`.

**Files / effects:** PDF report; ReportLab and Matplotlib.

**Interpretation and limits:** Requires the complete structured compare_datasets result. Optionally accepts the full snr_filter_sweep result to include plots and summaries. Uses ReportLab/Matplotlib; it does not run Traceratops. Returns a PDF path and metadata. It does not update the text resource report://latest.

Source: `chromatin-report-mcp/src/chromatin_report_mcp/server.py`, function `write_comparison_pdf` (line 643 at inspection).

### `write_comparison_report`

Server: `chromatin-report-mcp`. Classification: **Reporting only**.

**What it does:** Formats a supplied comparison as Markdown or escaped HTML with optional scientist-authored interpretation.

**Traceratops calls:** None

**Expected inputs:**

| Parameter | Type | Default / required |
|---|---|---|
| `comparison` | `DatasetComparison` | Required |
| `report_title` | `str` | `'Chromatin dataset comparison'` |
| `output_format` | `Literal['markdown', 'html']` | `'markdown'` |
| `scientist_notes` | `str ∣ None` | `None` |
| `recommendations` | `str ∣ None` | `None` |
| `conclusion` | `str ∣ None` | `None` |

**Returned output:** `ReportArtifact` with these fields:

- `path`: `str`.
- `format`: `Literal['markdown', 'html']`.
- `size_bytes`: `int`.
- `comparison_status`: `str`.
- `generated_at_utc`: `str`.

**Files / effects:** Markdown or HTML report.

**Interpretation and limits:** Requires the complete structured compare_datasets result, not just names or file paths. Writes a new Markdown or HTML file. HTML currently presents escaped Markdown inside a preformatted block. Optional prose is supplied by the caller; no raw scientific measurements are recalculated. Updates report://latest for this process.

Source: `chromatin-report-mcp/src/chromatin_report_mcp/server.py`, function `write_comparison_report` (line 697 at inspection).

## Nested output objects

The returned objects above contain these main nested structures:

- **DatasetInfo:** `name`, `trace_file`, `localization_file`.
- **GeneratedArtifact:** `path`, `size_bytes`.
- **DatasetQualityMetrics:** `dataset_name`, `trace_row_count`, `trace_count`, `roi_count`, `barcode_count`, `barcodes`, `median_rows_per_trace`, `coordinate_missing_fraction`, `duplicate_trace_barcode_rows`, `localization_row_count`, `localization_barcode_count`, `median_localization_snr`.
- **DuplicateMultiplicityStats:** `dataset_name`, `table_kind`, `source_file`, `grouping_columns`, `row_count`, `unique_group_count`, `zero_duplicate_groups`, `one_duplicate_groups`, `two_duplicate_groups`, `more_than_two_duplicate_groups`, `duplicate_rows`, `maximum_group_size`.
- **NumericDistribution:** `column`, `finite_count`, `missing_or_nonfinite_count`, `minimum`, `p10`, `median`, `p90`, `p99`, `maximum`, `mean`, `standard_deviation`.
- **CopyMultiplicityRetention:** `multiplicity`, `groups_before`, `groups_after`, `rows_before`, `rows_retained`, `rows_dropped`.
- **SNRFilterPoint:** `threshold`, `localization_rows_before`, `localization_rows_retained`, `localization_retained_fraction`, `unique_buids_retained`, `unique_barcodes_retained`, `unique_rois_retained`, `unique_cells_retained`, `trace_rows_before`, `trace_rows_retained`, `trace_retained_fraction`, `unique_traces_retained`, `unmatched_localization_buids`, `intensity_distributions`, `duplicate_statistics`, `trace_copy_multiplicity`.
- **SNRFilterDatasetResult:** `dataset_name`, `localization_file`, `trace_file`, `points`.

## What compare_datasets actually calls

```text
compare_datasets(first_dataset, second_dataset)
  -> _load_dataset_trace(first_dataset / second_dataset)
       -> dataset resolution + read_table_from_ecsv(...)
  -> custom schema, barcode-set and coordinate-unit checks
  -> _dataset_quality_metrics(...) for each table
       -> custom NumPy/Python counts and missing-value calculations
       -> optional LocalizationTable().load(localization_file)
       -> custom median SNR
  -> DatasetComparisonResult
```

It does not call inspect_dataset, trace_stats, localization_analyzer, localization_quality_summary or duplicate_statistics. The private helpers are ordinary functions in the same server, not separate MCP tools. Using a Traceratops reader does not make the subsequent custom QC a Traceratops analysis.

## Implication for the proposed script-focused branch

The current implementation does not fully match the requested design: four tools wrap native analysis scripts, while compare_datasets, duplicate_statistics, localization_quality_summary and snr_filter_sweep add custom scientific/QC logic. Registration and inspection also use custom logic, but their role is infrastructure and input description.

A suitable direction, proposed here rather than implemented:

1. Keep small registration, path-validation and inspection utilities with explicit descriptions of their limited role.
2. Expose individual Traceratops operations with their native parameters and structured outputs. The four existing native wrappers are the starting inventory.
3. Put sequencing, comparisons of returned results and report assembly in a documented workflow. The assistant can call each operation and carry its result to the report server. A workflow can orchestrate narrow tools without creating a broad custom analysis tool.
4. For a missing scientific capability, identify an existing Traceratops script first. If none provides it, treat it as a proposed Traceratops addition with scientific tests rather than silently recreating it in the MCP layer.
5. Review the report contract before removing compare_datasets: both report tools currently require its DatasetComparison schema. AGENTS.md, server instructions, the diagnosis skill and tests also reference the broad QC tools and would need coordinated updates.

No tool has been removed or refactored by this documentation task. No unverified mapping from a custom calculation to an equivalent native script is asserted here.

## Resources and configuration

Resources are not tools:

- `trace://current/ecsv` returns the complete configured trace ECSV text. Avoid fetching it for ordinary summaries because it can put the full table in context.
- `report://latest` returns the most recent Markdown/HTML report in the report server process; PDF generation does not update it.

Trace-server configuration: `CHROMATIN_TRACE_ECSV`, `CHROMATIN_LOCALIZATION_ECSV`, `CHROMATIN_DATASETS_JSON`, `CHROMATIN_TRACE_OUTPUT_DIR`. Dataset names are resolved locally; the reserved `current` name uses environment configuration. Generated analysis files use isolated run directories. Report output location is configured separately in the report server.


## Step 0 additions — 16 October 2026

The server now exposes 19 trace/validation tools and two report tools (21 total).
All original tools remain registered; the earlier proposed disabling/refactoring
was not applied. New tools do not implement Traceratops scientific algorithms.

| Tool | Expected input | Returned output / effects |
|---|---|---|
| inspect_experiment_directory | experiment_root, optional rules, max_findings, offset | Read-only file/ROI/extension counts and bounded findings; no table loads |
| discover_roi_files | experiment_root, optional rules, roi_identifier, discovery_mode, max_findings, offset | Paged ROI trace/localization mappings; missing/ambiguous roles and method |
| validate_experiment_structure | experiment_root, optional rules, max_findings, offset | Configured directory/file-role/ROI checks and four-state status |
| validate_ecsv_tables | experiment_root, optional rules, discovery_mode, max_findings, output_level | ECSV/schema/identifier/BED/barcode checks; JSON evidence plus Markdown/HTML reports in one call |
| run_experiment_validation | experiment_root, optional rules, discovery_mode, max_findings, output_level | Complete Step 0 orchestration and compact report summary; no Step 1 |
| get_validation_summary | validation_run_id | Cached deterministic validation summary, checksum and JSON paths; no table reanalysis |
| read_validation_details | validation_run_id, section, offset, limit | Paged saved findings, ROI evidence or file provenance |

See [the complete Step 0 input/output and configuration reference](references/step0.md).
Each new invocation also writes separate local timing/byte/count telemetry when its
configured output location is writable. This is not model-token instrumentation.

### Step 0 Data Quality Reports (chromatin-trace-mcp)

`run_experiment_validation` and `validate_ecsv_tables` automatically write Markdown
and HTML reports with the JSON evidence. Return `human_report_path` and
`html_report_path`; no second MCP call or reporting process is required.
`get_validation_summary(validation_run_id)` retrieves cached paths and results.
The richer comparison/PDF report tools remain in chromatin-report-mcp.

### collect_files — Step 1a.1, chromatin-trace-mcp

Input: `experiment_root`, `example_file`, optional `variable_part`, `table_kind`
(`tracing` default or `localization`), and `rename` (false default). Uses native
Traceratops collection, copying one selected ECSV per ROI into a fresh isolated
output run. Exact filenames automatically receive the source ROI directory suffix.
Variable matching preserves native fixed-length semantics. Force-skipping is not
exposed. Returns status, counts, compact file preview, timings, structured-response
bytes, and the full JSON manifest path/hash. No Pearson, merge or analyzer runs.
See [collection reference](references/collect-files.md).


### trace_pearsons — Step 1a.2, chromatin-trace-mcp

Input: `collections` (1–8 validated tracing collection references, each with
`collection_run_id` and `manifest_sha256`), optional `output_format` (`png`, `svg`,
`pdf`). Requires at least two datasets. Uses native Traceratops median-distance
and Pearson calculations, preserves the native figure and NPY matrix, and saves
full numerical results/provenance plus a human QC report. Returns compact indexed
ROI mapping, correlation previews, undefined counts, warnings, artifact paths,
timing and structured-response bytes. `COMPUTED` does not mean scientific PASS;
no thresholds, approval state, merging or downstream analysis are introduced.
See [Pearson reference](references/trace-pearsons.md). There are now 21 trace tools
and two richer report tools; no existing client/tool names were changed.


### review_pearson_approval — Step 1a.3, chromatin-trace-mcp

Input: `pearson_run_id`, exact `results_sha256`, optional `request_decision` (false).
Checks current evidence and returns approval status, explicitly selected indices,
evidence fingerprint and report/state paths. `request_decision=true` displays a
human review form through a trusted capable host; the model cannot pass a decision
or selection. The form presents saved QC/numerical evidence without recalculating
science. Changed inputs, report, artifacts or parameters invalidate the grant.
No merge operation, standalone decision tool or numerical-retrieval tool is added.
There are now 22 trace tools. See [scientific approval](references/scientific-approval.md).


### trace_merge — Step 1b.1, chromatin-trace-mcp

Input: `pearson_run_id`, `results_sha256`, `selected_dataset_indices` (exact sorted
human-approved selection, at least two). Native Traceratops merging on immutable,
checksum-verified snapshots; approval/evidence rechecked before publication.
Output: compact merged ECSV/provenance paths and checksum, source/row/barcode/
trace/ROI counts, warnings, timing and response bytes. Full approval snapshot,
metadata and row-to-source/ROI mapping remain in the provenance artifact. No
localization merge, filters or analyzers. See [trace merge](references/trace-merge.md).
The trace server now has 23 tools; existing tool names are unchanged.


### localization_merge — Step 1b.2, chromatin-trace-mcp

Input: saved `pearson_run_id`, exact `results_sha256`, exact sorted human-approved
`selected_dataset_indices` (at least two), and `localization_collections` containing
validated collection run IDs and manifest SHA-256 values. Matches original experiment
and source ROI provenance, not renamed output IDs. Uses native localization merging
only for that selection, revalidating approval and localization evidence before
publication. Output: compact MERGED/ERROR, ECSV/provenance paths and hashes,
source-file/row/barcode/ROI/Buid counts, bounded warnings, duration and response bytes.
Full values and metadata remain local. No filtering/analyzers. See
[localization merge](references/localization-merge.md). Current trace tool count: 24;
report server unchanged. Existing tool names are preserved.

### trace_stats — existing wrapper, future reporting use

Input: `dataset_name` (default `current`), resolving an existing registered trace
table. Calls native `compute_trace_statistics`, returning source/version, three
unique counts (ROI, global Trace_ID, barcode) and captured native text. Supports
compatible individual-ROI and merged tables; produces no figures or saved artifacts.
These counts do not establish scientific acceptance. Step 0 now includes these native counts per eligible ROI inside its validation call.
Merged-statistics, analyzer and comprehensive-report integrations remain future work; see
[trace_stats audit and roadmap](references/trace-stats-integration.md).


### merged_trace_stats — Step 1c, chromatin-trace-mcp

Input: trace_merge_run_id, merged_sha256, provenance_sha256. Verifies native Step
1b.1 provenance, current exact approval, source contributions and checksums; runs
the existing native trace_stats adapter on an immutable merged snapshot. Saves
complete statistics/status/native log locally. Returns compact COMPUTED/ERROR,
evidence path/SHA, reproducible baseline fingerprint, row/ROI/global Trace_ID/
ROI-Trace_ID pair/barcode counts, warnings, timing and response bytes. Original
per-ROI Step 0 results remain separate. No analyzers, report tools or filters are
invoked. See [merged statistics](references/merged-trace-statistics.md). There are
25 trace tools; trace_merge gains only the additive provenance_sha256 response field.


### trace_analyzer — merged, unfiltered tracing analysis

Input: baseline_run_id, baseline_sha256; optional native png/svg/pdf format, plotting
neighbor_distance_range (1 default or auto/positive microns), and NumPy random_seed
(0 default). Reuses native process_traces and existing evidence validators; no
scientific algorithms are duplicated. Verifies current merge/approval/baseline
evidence and rejects cross-ROI Trace_ID collisions or invalid genomic/unit metadata.
Output: compact ANALYZED/ERROR, evidence/hash, manifest/output directory, five-figure
count, native neighbor summary with availability, warnings, latency/response bytes.
Full numerical arrays, plots and logs stay local. No localization/report/filter call.
See [trace analyzer](references/trace-analyzer.md). Trace tool count: 26.
