# Step 0: experiment validation

This milestone adds validation to the existing Chromatin Trace server. It does not
collect/copy experimental files, calculate Pearson correlations, merge, or run
analyzers. The existing 12 tools remain available. Seven additional tools expose
shared deterministic validation functions; there is no new server.

## Tools and inputs

All new inspection tools use an explicit `experiment_root`, checked against the
server administrator's `CHROMATIN_EXPERIMENT_ROOTS` allowlist (OS path separator).
An unset allowlist denies experiment reads. Root arguments do not expand it.
`rules` is an optional `StructureRules` object. Defaults select mask-based traces.

| Tool | Purpose | Main output |
|---|---|---|
| inspect_experiment_directory | Sorted discovery, extension counts, empty directories, skipped links/access problems; no table reads | Counts and paged findings |
| discover_roi_files | Per-ROI file-role mappings, normalized ROI ID, missing/ambiguous candidates | Paged mappings and findings |
| validate_experiment_structure | Required directories, expected ROI policy, file roles/naming | PASS/FAIL/INCOMPLETE/ERROR, findings |
| validate_ecsv_tables | Parse selected ECSV, validate schemas/identifiers, BED reference and barcode coverage | Compact summary and mandatory saved report |
| run_experiment_validation | Preferred full Step 0 orchestration using the same functions | Compact summary and mandatory saved report |
| generate_data_quality_report | Return an existing generated report by `validation_run_id` | Saved summary and artifact references, no reanalysis |
| read_validation_details | Page cached `findings`, `rois`, or `files` by run ID | Bounded evidence without table rereads |

Discovery supports `roi_identifier` and `discovery_mode` = filename (default),
metadata, or automatic. Automatic falls back to observed column signatures only
when no filename match exists; it does not hide ambiguous filename matches.
See [ecsv-identification.md](ecsv-identification.md).

Inspection/structure tools accept `max_findings` (1–100, default 20) and `offset`.
Full validators accept `max_findings` and `output_level` = compact or detailed.
Cached detail accepts `offset` and `limit` (1–100). Nested evidence lists beyond
100 items are marked truncated; complete evidence remains in `details.json`.
No complete scientific table is returned.

## Rules and authority

`configs/step0-mask-defaults.json` is a portable default policy, not experiment
metadata. Configure expected IDs from the actual experiment design; do not fill
these from observed detections just to obtain PASS.

Rules may be supplied inline, or through an experiment-local `experiment.yaml`
with a documented `step0:` mapping. Explicit tool rules take precedence. Other
YAML layouts are reported as unrecognized, rather than guessed. Safe YAML parsing
is size-limited. Unsupported keys in the policy are rejected.

```yaml
step0:
  expected_roi_ids: ['92', '93']
  expected_barcodes: ['1', '2', '3']
  barcode_source: 'Approved experimental design, revision X'
  # If a BED is actually associated with this experiment:
  # bed_file: design.bed
  # bed_barcode_column: 4
  # bed_required: true
  require_each_barcode: false
```

The values above are illustrative. Barcode/ROI identifiers must encode integers;
zero-padding is normalized. Numeric YAML/JSON identifiers are accepted. An explicit
expected barcode list needs a `barcode_source`. A configured BED can supply the
expected set when its barcode column is explicitly identified (one-based).
Traceratops contains a verified four-column BED convention with barcode in column
4, and an additional remapping convention; this is not a universal BED guarantee.
Do not assume a BED is associated solely because it exists in the tree.

Required/optional directories, filename patterns, required/allowed columns,
expected ROI/barcode sets, BED association, strict barcode coverage, recursion,
file-count, table-byte and record limits are configurable. Optional directories
are documentary allowances; absence does not fail. Unexpected directories are
warnings only when `allowed_top_level_directories` is specified. Unclassified
scientific outputs are not labelled unexpected without a rule defining them.

BED checks separate existence from mapping consistency, validate interval shape,
integer barcode IDs, duplicate/conflicting mappings and explicit-set conflicts.
Observed barcode identifiers outside the reference are warnings. No coordinate
conversion, BED assignment to raw observations, allele inference or genome
assembly verification is performed. Table metadata is recorded, not interpreted
as proof that the experiment's biological annotation is correct.

## Status and findings

Execution/parsing failures produce ERROR. Otherwise required validation failures
produce FAIL, unavailable reference checks produce INCOMPLETE, and evaluated
checks produce PASS. Noncritical warnings remain separate from this four-state
status; there is deliberately no fifth WARNING execution status.

Missing required files/columns, inconsistent ROI IDs and ambiguous file roles
are errors. Missing barcode observations are warnings unless
`require_each_barcode=true` was explicitly configured. Unknown expected ROIs do
not imply missing ROIs. Unknown expected barcodes yield null missing/unexpected
lists and INCOMPLETE. No result automatically approves Step 1.

Trace counts use `Trace_ID` within each ROI/table. A trace represents a segmented
nucleus, not necessarily a chromosome. Barcode coverage is reported separately
for tracing and localization tables; neither is silently substituted for the
other. Counts are identifier/schema inspection, not new scientific algorithms.
`Spot_ID` corresponds to localization `Buid` in existing project conventions;
Step 0 does not perform or infer a cross-table filtering join.

## Reports, provenance and metrics

Set `CHROMATIN_STEP0_OUTPUT_DIR` outside the experimental input tree. It falls
back to `CHROMATIN_TRACE_OUTPUT_DIR`, then `./results/step0_validation` in the server
working directory. Full validation always attempts to save a unique run folder:

```
<output>/<run_id>/summary.json
<output>/<run_id>/details.json
<output>/<run_id>/report.md
<output>/tool_metrics.jsonl
```

Reports include PASS, FAIL, ERROR and INCOMPLETE outcomes, policy/source, counts,
per-ROI coverage, uncompleted checks, warnings/errors and conclusion. Saved
parsed-table evidence includes relative source paths, size, modification time and
SHA-256. Input changes during parsing/hashing invalidate the result. Cached run
IDs identify immutable snapshots, not a claim that current input files remain
unchanged. Re-run validation after changing inputs/policy. `generate_data_quality_report`
retrieves this deterministic report rather than asking a model to reconstruct it.
The existing comparison-report server and schema remain unchanged; Step 0's
report is a separate validation contract, not fabricated comparison data.

New-tool metrics contain invocation ID, tool name, duration, serialized parameter
and response bytes, file/record/finding counts, execution success and validation
status. FAIL may be a successfully executed validation. Raw tables and model
credentials are not logged. Model usage is unavailable at this boundary.
Optional estimated response tokens require `tiktoken` and an explicitly enabled,
locally provisioned tokenizer (`CHROMATIN_STEP0_ESTIMATE_TOKENS=1`); no token
estimates are attempted by default. Estimates never replace provider usage.

## Boundaries

All symlinks are skipped, including internal ones. Required symlinked scientific
inputs therefore cannot validate; stage real files or use an authorized physical
root. Huge `full_pwd/` and `PWD_comparison/` directories are excluded by default;
no image or NumPy matrix contents are read. Byte/entry/depth limits report
incomplete checks instead of silently passing. Astropy loads each selected table
in RAM; record limits are checked after parsing, so they are not an OS memory
sandbox. Metadata signatures require only a bounded ECSV header.

This path validation is not an OS sandbox: deploy with read-only input mounts,
restricted filesystem/network permissions and resource limits when inputs can
be concurrently modified by hostile users. Concurrent parent-directory replacement
is not protected with descriptor-relative OS traversal. Output disk failures can
prevent report persistence; that execution error must be surfaced. New telemetry
covers new Step 0 tools, not retrofitted legacy tools. No benchmark can validate
free-form biological interpretations solely from this structural oracle.
