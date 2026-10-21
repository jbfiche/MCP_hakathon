# Existing trace_stats and future integration roadmap

Source audit: current `chromatin_trace_mcp.server.trace_stats` and locked
Traceratops 1.0.1 `traceratops.trace_stats.compute_trace_statistics` at commit
`261a48fe92498abcb154891fe6e5a5ca8219b610`. This milestone changes no statistics
code and implements neither of the reporting workflows below.

## Actual current interface

`trace_stats(dataset_name="current")` resolves the trace file through the existing
MCP dataset catalog. `current` uses `CHROMATIN_TRACE_ECSV`; named entries use the
registered trace path. It does not accept an arbitrary path, collection manifest,
ROI selection or merge run ID. Reusing a collected or merged table therefore
requires an existing authorized dataset registration/configuration; do not add
another wrapper or bypass registration validation.

The native function loads the entire trace table using `ChromatinTraceTable.load`
and calculates exactly:

- `len(set(table['ROI #']))` — unique observed ROI values.
- `len(set(table['Trace_ID']))` — globally unique observed trace IDs.
- `len(set(table['Barcode #']))` — unique observed barcode IDs.

It prints these integers and the source path. The MCP captures stdout (required
for stdio safety), parses the three labeled integers, and returns `source_file`,
`traceratops_version`, `unique_roi_count`, `unique_trace_count`,
`unique_barcode_count`, and the complete short `traceratops_report` text.

**Output artifacts:** none. There are no generated figures, distributions,
per-barcode counts, numerical matrices, JSON files, or saved report from this native
function or wrapper. The numbers and captured text are the available results.
The wrapper reads locally on the configured MCP host and performs no provider call.
Existing trace_stats does not measure its own latency, response bytes or model tokens.

## Applicability and limitations

Both a single-ROI trace ECSV and a merged trace ECSV are accepted if registered
and compatible with the native trace loader. There is no special merged-table
branch. Empty or unreadable tables fail, and missing required native columns can
fail; errors become MCP ToolError. Parsing depends on the native printed labels.
No independent per-ROI breakdown or cached-statistics lookup is available.

Global unique Trace_ID is not the number of `(ROI, Trace_ID)` pairs when IDs repeat
between ROIs; the existing trace_merge provenance already records both counts.
Trace_ID identifies a segmented nucleus, not necessarily a chromosome or allele.
Observed barcode count is not expected barcode completeness, coverage, genome
assembly validation or biological success. No acceptance threshold is defined by
these statistics. Native loading/metadata behavior remains authoritative; no
scientific algorithm change or extra statistics calculation is proposed here.

## Planned Step 0 integration — not implemented

After existing directory/schema/barcode/BED validation identifies individual ROI
trace tables, reuse the existing native trace_stats operation for available
per-table descriptive counts. Preserve exact input hashes and distinguish failed
or unavailable statistics from validation status. Complement existing validation;
never turn a descriptive count into PASS/FAIL or infer expected barcodes from it.
Determine the minimum dataset-registration and persistence changes in a separately
approved milestone. One ROI call per file through an agent is not a required
architecture: prefer server-side orchestration and cached compact results to avoid
context/call growth. Keep the existing one-call Step 0 workflow intact until then.

## Planned Step 1c pre-filtering baseline — not implemented

After approved trace and localization merging, use the existing trace_stats wrapper
on the registered merged trace table. Reuse its returned numbers and already-saved
merge/validation/Pearson evidence, retaining input hashes, native version and exact
parameters. Record global-ID counting limitations alongside existing ROI/trace
counts. Preserve the baseline before any later filtering.

Include available analyzer numerical outputs and existing figures by reference
when those separately approved tools exist. trace_stats itself supplies no figures;
do not fabricate artifacts or recalculate measurements merely to format a report.
Simple statistics and compact summaries remain in chromatin-trace-mcp. Consider
chromatin-report-mcp for a separately requested multi-analysis report combining
validation, Pearson, both merges and analyzer outputs, or rich comparison/export
needs. It should format saved evidence, not rerun scientific calculations. No new
cross-server calls or duplicate formatting are introduced in Step 1b.2.

## Development status

- Step 1b.1 trace_merge: implemented with existing human approval enforcement.
- Step 1b.2 localization_merge: implemented; owner review pending.
- Step 0 trace_stats reporting extension: planned, not implemented.
- Step 1c pre-filtering baseline and analyzers: planned, not implemented.
- Filtering and downstream workflows: outside this milestone.
- Autonomous-agent trials and provider-reported token measurements: pending until
  genuinely executed; deterministic/stdio tests and response bytes do not replace them.
