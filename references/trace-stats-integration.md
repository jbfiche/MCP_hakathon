# Native trace_stats integration and pre-filtering QC roadmap

Audited native Traceratops 1.0.1 at locked commit
`261a48fe92498abcb154891fe6e5a5ca8219b610`. Scientific algorithms are unchanged.

## Existing native operation and public tool

`trace_stats(dataset_name="current")` resolves a registered tracing ECSV. `current`
uses CHROMATIN_TRACE_ECSV; named datasets use the existing catalog. Inputs are trace
tables, never localization tables. Individual-ROI and merged trace tables are
supported when valid and nonempty. The public tool arguments and result fields
remain unchanged; registration does not itself establish checksum-bound provenance.

The shared `trace_statistics.compute_statistics` adapter calls native
`compute_trace_statistics`, captures stdout for stdio safety, and parses exactly
three native integers: unique `ROI #`, global unique `Trace_ID`, unique `Barcode #`.
It returns source path, Traceratops version, those three counts and native terminal
text. Native loading/error behavior is preserved; no statistics formula is copied
into MCP. Native stdout labels are an interface dependency.

The native operation creates no figures, saved numerical artifacts, distributions,
filtering statistics or thresholds. Statistics stored in Step 0 evidence below are
MCP persistence of native results, not additional native outputs.

## Implemented Step 0 per-ROI enhancement

`run_experiment_validation` and `validate_ecsv_tables` now compute native statistics
inside their existing single call, after existing file/schema/identifier/BED checks.
Each unambiguously selected, valid, within-limit ROI tracing table receives one
native run. There are no per-ROI agent calls, automatic catalog registrations or
localization-statistics runs. Inspection and structure-only tools do not run stats.

For each discovered ROI, saved `details.json` includes `roi.trace_stats`:
COMPUTED, NOT_RUN or ERROR; original ROI directory/normalized identifier and trace
path; original ECSV SHA-256; and, when computed, native counts, text, version,
native module SHA-256, warnings and stderr. Missing/ambiguous/invalid/over-limit
trace tables have explicit NOT_RUN reasons. Native exceptions or changed source
hashes produce ERROR statistics; unrelated ROI checks continue.

Native execution reads a private read-only snapshot whose hash matches the
already-validated source ECSV. The source is checked again after statistics.
Displayed native paths are mapped from the temporary snapshot to that exact original
source. Complete tables and snapshots are not persisted in reports or sent to the
model. Source inputs are never written.

Existing validation status/findings remain intact. New compact fields separately
report `trace_stats_status` (COMPLETE/INCOMPLETE/NOT_RUN), computed/not-run/error
counts. A validation PASS does not hide missing statistics or imply scientific
acceptance. Markdown and HTML include each ROI's native results or unavailable
reason. Cached retrieval/formatting does not rerun statistics. Full native records
remain in checksum-identified details evidence; default compact responses do not
include all ROI records or terminal text. Existing dataset-size limits apply.

The native path-based function rereads each eligible tracing snapshot. This is
additional local I/O, not an additional model/tool round trip. Existing schema and
barcode checks remain necessary and are not replaced by native descriptive counts.
Global Trace_ID counts may differ from distinct ROI/Trace_ID pairs. Trace_ID is a
segmented nucleus, not necessarily a chromosome or allele. Observed barcode count
does not establish expected barcode completeness or biological success.

## Remaining milestones — separately approved, not implemented

The final comprehensive experiment report must be produced **after both analyzers
and before filtering**. Its scope is broader than the initial Step 0 report.

1. Step 1c merged-trace statistics is implemented for owner review through
   merged_trace_stats. It reuses the existing native adapter without catalog
   registration or another agent call, verifies exact merge/approval evidence and
   saves a reproducible unfiltered baseline. See [merged statistics](merged-trace-statistics.md).
   No analyzer or comprehensive report runs automatically.
2. Native trace_analyzer integration is implemented for owner review. It uses a
   checksum-bound Step 1c baseline and exact unfiltered merge, rejects global ID
   collisions and invalid genomic/physical metadata, and preserves native numerical
   values/figures. See [trace analyzer](trace-analyzer.md). Actual experiment analysis
   still requires valid input metadata; synthetic equivalence is not a substitute.
3. Reuse and verify the existing localization_analyzer wrapper on the corresponding
   merged, unfiltered localization table. The plotting schema includes Barcode #,
   zcentroid, snr, skew, object_class and roundness. Legacy schemas may skip plotting;
   an absent figure must be reported, not represented as successful QC. Neither
   native analyzer requires prior filtering. Approval required for this integration.
4. Only after both analyzer stages, use chromatin-report-mcp to compose the
   comprehensive human-readable pre-filtering QC report from validated saved
   artifacts. Include Step 0 validation/per-ROI stats; Pearson results and human
   approval; tracing/localization merges and source ROI mappings; merged trace_stats;
   both analyzers' available statistics, warnings, failures and saved figure
   references. Missing evidence remains explicit; do not label a partial report
   complete. This report implementation requires separate approval.
5. Filtering is a later scientific decision/stage, never an automatic consequence
   of descriptive statistics, correlation, completed analyzers or report generation.

Scientific execution, provenance, validation and approval stay in the trace server.
The report server must only format verified evidence, never recalculate scientific
measurements or change source data. Plan read-only authorized artifact access using
a small QC manifest/run reference and SHA-256 values rather than passing full JSON,
matrices, ECSV tables or images through the model. Existing comparison report tools
are not yet a general workflow-composition interface; this milestone adds no report
server tool, shared-store integration, or comprehensive formatter. Simple Step 0
and Pearson reports remain in trace without extra cross-server calls.

## Evidence required for the future comprehensive report

Link original Step 0 table hashes to collection source hashes; bind both merge runs,
ECSV/provenance hashes and original experiment/ROI mappings to the same Pearson ID,
results hash, approval revision and exact selection. Retain native versions,
parameters, analyzer input/output hashes, execution outcomes, warnings and figure
references. A registered path alone is not that evidence. Trace approval covers the
tracing ROI selection; localization bytes absent from Pearson review remain
separately hash-verified execution evidence, not retroactively human-reviewed data.

Provider-backed autonomous validation and actual token/cost measurements remain
pending unless genuinely run. Deterministic/native/stdio results and response bytes
are not actual provider tokens.


Native genomic annotation is now available as an explicit derivative stage between
merged trace statistics and trace_analyzer. Use native replacement barcodes and
researcher-confirmed assembly evidence; original baseline artifacts remain unchanged.
See [annotation evidence](genomic-annotation.md). Do not silently compare annotated
trace barcode IDs with original localization or earlier QC barcode IDs.
