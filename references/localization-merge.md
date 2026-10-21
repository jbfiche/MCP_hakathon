# Step 1b.2 — native localization_merge

Explicitly requested localization merging is available in chromatin-trace-mcp.
It never triggers trace merging, statistics, filtering, or analyzers.

## Interface and authorization

`localization_merge(pearson_run_id, results_sha256, selected_dataset_indices,
localization_collections)` accepts the exact saved Pearson ID/checksum and sorted
human-approved tracing selection, plus 1–8 localization collection references:
`{"collection_run_id": "<32 hex>", "manifest_sha256": "<64 hex>"}`.
At least two approved tracing datasets are required by the native localization
loader. No arbitrary input/output paths, force flags, or scientific parameters
are accepted. Each invocation has one MCP call and returns compact JSON.

The existing human gate authorizes the **original experiment and tracing ROI
selection**. It does not certify localization bytes that were not part of Pearson
review. Localization manifests and selected bytes are bound by explicit checksums
for this execution, recorded in provenance, and rechecked before publication.
A newly collected localization version with the same verified source ROI is within
this ROI-selection authorization; it is not claimed to have been Pearson-reviewed.
A future requirement for human approval of exact localization bytes would require
an explicit extension to the approval contract, not silent reuse of this grant.
No new decision mechanism is introduced here.

The wrapper calls `require_scientific_approval` before execution and publication.
It verifies the exact selection and approval revision. The final current evidence,
localization manifest/file checks and atomic publication run under the existing
approval decision lock. Changed or revoked approval, modified evidence, missing
files, ambiguous associations, or native failures prevent successful publication.
Application-level hashes and locks do not isolate another process with arbitrary
OS write access. Collection and approval stores must be trusted server-managed
artifacts, not writable by ordinary agent tools.

## Source association

1. Read the tracing collection manifests already bound to the approved Pearson run.
2. Recover each selected tracing file's original experiment root, source path,
   numeric source ROI directory, and source-relative path.
3. Verify localization collection manifests, their declared role, destination paths,
   copied-file hashes and internally consistent original-source provenance.
4. Match by `(canonical original experiment root, original numeric ROI)`; source
   paths must agree with that experiment/ROI directory. Numeric zero-padding is
   normalized. Renamed collection filenames and output ROI numbers are not keys.
5. Require exactly one localization table for each approved tracing source ROI.
   Unselected localization ROIs may exist in a collection; they are not merged.
   Duplicate tracing selections for the same source ROI and ambiguous localization
   candidates are rejected, rather than silently duplicated or chosen.

Only immutable collected snapshots are read for scientific execution. Original
paths describe provenance at collection time; the wrapper does not rediscover or
substitute current raw files. If original data changed since collection, recollect
and review the appropriate tracing evidence instead of editing stored manifests.
Spot_ID in tracing corresponds to Buid in localization; barcode alone is never a
join key. This merge does not calculate or certify spot-link coverage.

## Native calculation and scientific integrity

The wrapper calls unmodified `traceratops.localization_merge.run`, which delegates
to `load_localizations`/`appends_traces`, `LocalizationTable.load`, native Astropy
`vstack` via `LocalizationTable.append`, and `LocalizationTable.save`. The saved
comment is `appended_loc_files=N`, matching direct native execution.

Every output source row range is compared with input values/masks after ECSV
reload, including unchanged ROI numbers, barcode IDs, Buid and coordinates.
Rows must equal the selected source contributions. Declared coordinate units,
assembly metadata and all column units are checked for compatibility; no coordinate
conversion or inferred metadata is performed. Missing unit/assembly declarations
produce a warning. Non-scientific metadata conflicts retain native reconciliation
and produce warnings. Complete table and column metadata for each source and the
merged result are preserved as Astropy YAML strings in provenance.

**Native limitation:** localization merging preserves ROI IDs, while trace merging
renumbers collisions. This wrapper rejects repeated numeric source ROI IDs across
selected experiments. It cannot safely publish aligned output for that case without
an agreed upstream identifier policy; it does not implement a new relabeling
algorithm. Multiple approved tracing tables for the same experiment/ROI are also
ambiguous and rejected. Native single-input merging is unsupported, so selections
of one dataset are rejected. Empty source contributions are not intentionally
filtered. No allele separation, scientific acceptance threshold, barcode filtering,
or localization quality selection is added.

## Configuration and artifacts

Use the same `CHROMATIN_COLLECTION_OUTPUT_DIR` and `CHROMATIN_PEARSON_OUTPUT_DIR`
as collection and human review. Configure `CHROMATIN_LOCALIZATION_MERGE_OUTPUT_DIR`
outside original experiment roots, collection and Pearson stores. Default:
`<CHROMATIN_TRACE_OUTPUT_DIR>/localization_merges`, otherwise
`./results/localization_merges`. Outputs have fresh UUID run directories:

- `merged_localizations.ecsv`: full native output with SHA-256.
- `provenance.json`: approval snapshot/revision/fingerprint; original tracing and
  localization associations, collection/file hashes, source row ranges and ROI
  mappings; native module/class hashes/version; complete metadata and warnings.
- `native.log`: captured native processing text.

Compact JSON returns MERGED/ERROR, artifact paths and hashes, source-file, row,
barcode, ROI and global Buid counts, at most four warning previews with truncation
flags, elapsed seconds and structured-response bytes. Repeated Buid values are
warned about; global unique Buid count is not necessarily row count. Full tables,
source metadata, and approval snapshots stay outside model context. Runtime errors
return ERROR without success paths; malformed arguments are MCP schema errors.

Limits: at most 32 selected datasets, eight collection references, 100 MB per
selected file and 1 GB total selected bytes. Native Astropy stacking is in memory;
these input limits do not impose OS memory or CPU quotas. No provider request is
made by the tool, and response bytes are not actual model tokens.

Stop after reviewing the localization merge. Step 1c and new trace_stats reporting
workflows require separate approval; see [trace_stats roadmap](trace-stats-integration.md).

## Reproducible native/MCP comparison

With the validated Python environment and source paths configured, run
`python chromatin-trace-mcp/benchmarks/benchmark_localization_merge.py --help`.
Supply an existing human-approved Pearson run, exact indices, a JSON file of
localization collection references, and a fresh benchmark output directory.
The script never creates approval. It checks exact native/MCP ECSV bytes and
unchanged source, evidence and approval hashes, saving machine-readable timings,
response sizes and explicit null provider-usage fields. One trial is not a
performance distribution; no autonomous model behavior is tested.
