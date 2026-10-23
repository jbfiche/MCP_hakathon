# Native localization analyzer on an approved merged dataset

The existing `localization_analyzer` tool now supports an optional verified-merge
mode. No second localization tool, filtering operation or report-server dependency
is added. The registered dataset mode remains available with its existing argument
names and JSON fields. Scientific execution uses native
`traceratops.localization_analyzer.run` and `LocalizationTable.plot_distribution_fluxes`.

## One-call verified mode

Pass `localization_merge_run_id`, `merged_sha256`, `provenance_sha256`, and optional
`output_format` (png/svg/pdf, default png). These three merge reference fields must
be supplied together. Do not combine a merge reference with dataset_name other
than its default current; the registered dataset is not read in this mode.
Optional `annotation_run_id` and `annotation_sha256` link tracing's verified BED
replacement mapping; supply both or neither. Real workflow calls should include
the established annotation reference when annotated tracing data exists.

Inputs are references to the existing native Step 1b.2 merge, not arbitrary paths.
Verify merged/provenance hashes, native merge/table/version hashes, current exact
human approval snapshot/revision/fingerprint, source tracing/localization ROI
associations, collection hashes, source row ranges, original ROI/Buid/barcode
values, counts, and table/column metadata before execution. Reuse existing merge
and approval validators; no merge or approval is recreated. At publication recheck
all source/evidence/approval hashes under the existing approval lock, including
the optional tracing baseline, annotation, BED and assembly-reference evidence.
The analysis never creates a human decision or changes an existing grant.

The tool keeps its legacy registered-dataset path for compatibility. That mode is
not a substitute for workflow authorization: use the verified mode for merged
workflow data. Both payloads are validated by their respective Pydantic models,
then serialized as typed string-keyed dictionaries so the SDK emits top-level
structured JSON without a union result envelope. The dual-mode output schema is
an open object; the existing legacy payload fields remain unchanged.

## Scientific behavior and input requirements

The native operation produces one four-panel figure:

- SNR distributions by original barcode (violin plots).
- SNR versus supplied zcentroid, colored by object_class.
- Native detection counts by original barcode.
- Roundness versus skew, colored by original barcode.

Its historical filename is `localization_distribution_fluxes.<format>`; it does
not calculate a flux histogram or return a statistics object. There is no native
acceptance threshold, allele separation, coordinate conversion or barcode replacement.
Legacy-format tables can cause native plotting to be skipped; verified mode rejects
missing current plotting columns explicitly rather than advertising a missing plot.
Required columns: original localization identity/ROI/coordinate columns plus
Barcode #, zcentroid, snr, skew, object_class, roundness. Plotting values must be
finite numeric and unmasked, and barcode IDs integer. Nonfinite/masked values are
rejected without silently dropping observations. Finite extreme or negative values
are not excluded by invented quality thresholds. Native plotting can compress the
bulk of the scatter when extreme values stretch its axes. Sparse/gapped barcode
numbers, including 639, retain their native numeric positions and labels.

The worker consumes a byte-identical private read-only input snapshot. No further
filtering is applied. The scope label merged_unfiltered_localization means unfiltered
by these MCP stages, not a claim that upstream pyHiM never filtered the supplied
files: existing filtered/registered comments remain intact and are reported.
Unspecified z/coordinate units and localization assembly are not inferred from
tracing metadata or native defaults. Axes show supplied values without calibration.

## Numerical evidence and artifacts

An isolated worker runs the native operation with transparent wrappers around its
Matplotlib plotting calls, returning original objects unchanged. It preserves:

- All SNR arrays by barcode and native positions supplied to violinplot.
- Returned violin density vertices and native median/min/max/bar segments.
- Complete x/y/color inputs to both scatterplots and their rendered offsets.
- Barcode IDs and counts already computed by the native bar plot.

This captures native plot inputs and returned plotting objects, not every private
intermediate of Matplotlib's KDE implementation. No scientific metric is recalculated
or inferred from pixels. Complete array values and masks stay in numerical_outputs.npz
(allow_pickle=False), with label/method mapping, native counts, warnings and runtime
versions in numerical_outputs.json. Native table identity remains original; capture
of color indices is a plotting palette mapping, not replacement of ECSV identifiers.

`CHROMATIN_LOCALIZATION_ANALYZER_OUTPUT_DIR` defaults to
<CHROMATIN_TRACE_OUTPUT_DIR>/localization_analysis or ./results/localization_analysis.
It must be outside experiment inputs, collection/Pearson/merge/baseline/annotation
and tracing-analysis stores. Each invocation creates a fresh UUID directory:

- localization_distribution_fluxes.png (or selected format): original native figure.
- numerical_outputs.json and numerical_outputs.npz: complete captured numerical data.
- stdout.log / stderr.log: native processing messages and failures.
- artifacts.json: file sizes and SHA-256 hashes.
- analysis.json: status, native/table/worker versions and hashes, approved dataset
  selection, localization merge/source evidence, optional tracing barcode mapping
  reference, parameters, warnings, counts and artifact manifest checksum.

Before success publication, verify the figure, numerical interface and total native
barcode counts against all input rows. Native failures or final evidence changes
retain ERROR artifacts/logs with no successful counts or figure claim. Preflight
failures produce ERROR with no scientific output. A 300-second worker timeout bounds
execution; existing byte limits are not OS CPU/RAM quotas. Trusted server stores
remain necessary; checksums do not prevent unrestricted OS writers.

Return compact ANALYZED/ERROR, row/ROI/barcode counts, paths/checksums, bounded warning
previews, execution seconds and response bytes. No complete table, plot arrays,
images or full logs are sent to the agent by default. Existing tool count stays 27.

## Barcode namespaces and reporting boundary

Merged localization barcode IDs remain original. Annotated tracing IDs were replaced
using the experiment's five-column BED. The optional annotation reference is fully
verified against the same current approval and saved baseline; record its mapping
path/hash and BED checksum without renaming or copying localization data. Translate
barcode meanings through barcode_mapping.json and join spots via Spot_ID/Buid, not
barcode alone. No localization assembly/coordinates are assigned from that mapping.

Link completed artifacts into the existing experiment inspection view; never move
canonical stores or rewrite old approval-bound evidence. Publication of links needs
no scientific computation or new MCP call. The current view is maintained separately
from the tools, not a newly introduced automatic publisher.

Stop after this milestone for owner review. Both analyzers are prerequisites to the
future comprehensive pre-filtering report in chromatin-report-mcp, but that report
and filtering still require separate approval and are not implemented here.

## Verification and benchmark

`benchmarks/benchmark_localization_analysis.py` compares an existing approved merge
with direct native execution and one real stdio invocation. It compares every native
plot input array, exact native PNG bytes, counts, artifact hashes and unchanged sources/
approval. A real workflow may supply the existing tracing annotation reference in
that same call. Existing tests also cover response compatibility, schema validation,
invalid/stale approvals, source/provenance changes, missing/legacy columns, nonfinite
values, native failures and changes during execution. PNG is the byte-equivalence
reference; SVG/PDF are passed through to the existing native format option.

Timing is one local trial, not a performance distribution. Provider-backed agent
validation and input/output tokens remain pending unless genuinely measured;
response bytes are never reported as actual model tokens.
