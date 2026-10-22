# Step 1c — merged, unfiltered tracing statistics

`merged_trace_stats` in chromatin-trace-mcp creates a reproducible descriptive
baseline from an exact native Step 1b.1 trace merge. It performs no analyzer,
filtering, localization processing, registration, reporting or cross-server call.

## One-call interface

Inputs: `trace_merge_run_id` (32 lowercase hex), `merged_sha256` and
`provenance_sha256` (64 lowercase hex each). Both checksums are mandatory. No
arbitrary input path, scientific parameters, selection override or approval option
is exposed. The tracing merge now returns the additive `provenance_sha256` field,
so its response supplies all arguments without another model call. Existing
trace_merge clients and trace_stats(dataset_name) remain compatible. Older merge
runs remain readable; obtain their provenance checksum from the trusted saved file.

The tool reuses `trace_statistics.compute_statistics`, the same adapter used by
trace_stats and Step 0. Native Traceratops compute_trace_statistics supplies three
integers: unique ROI, globally unique Trace_ID and barcode counts. No statistical
formula, scientific threshold or allele-handling policy is introduced. The small
internal adapter extension accepts a caller-owned transcript stream to preserve
native text even when execution fails; public trace_stats results are unchanged.

## Evidence verification and immutability

Read the configured trace merge store by run ID using bounded, non-symlink artifact
reads. Verify merged ECSV/provenance hashes and schema, phase, native merge policy,
artifact names, native implementation hashes, exact approved source order and saved
approval snapshot/revision/fingerprint. Reuse require_scientific_approval to check
current Pearson report/matrix/figure, collection hashes, parameters and selection.
No new human decision is requested or generated.

On private read-only snapshots, compare merged row contributions with approved
collection inputs using the existing merge validator, including all non-ROI values,
masks and units. Check recorded source metadata, row ranges and ROI mappings. The
existing ROI/Trace_ID count is independently checked as an identifier-integrity
check, then reused from merge provenance. Verify native counts agree with the merge
counts. This does not rerun merging, Pearson or per-ROI statistics.

Immediately before publication, recheck current approval and collection/Pearson
evidence, merged/provenance hashes and the native merge log hash under the existing
approval decision lock. Changed or revoked evidence cannot publish COMPUTED.
Original sources and existing merged artifacts are never destinations.

## Counts and scopes

The compact response labels `global_unique_trace_id_count` and `roi_trace_count`
separately. Its scope is `merged_unfiltered_tracing`. Native unique Trace_ID is a
global ID count; it can be smaller than distinct (output ROI, Trace_ID) combinations.
Trace_ID is nucleus-level, not necessarily a chromosome or allele.

Saved evidence includes approved original experiment/source ROI paths, collection
references, source hashes and output ROI mappings. Original per-ROI native statistics
remain in Step 0 evidence: this call does not recompute, add together or claim to
incorporate them. Its explicit `original_per_roi_statistics` status records that
separation. Linking the exact Step 0 evidence is later comprehensive-report work.
Neither COMPUTED nor a large count establishes scientific acceptance.

## Output and reproducibility

Configure CHROMATIN_MERGE_OUTPUT_DIR, CHROMATIN_COLLECTION_OUTPUT_DIR and
CHROMATIN_PEARSON_OUTPUT_DIR to the stores used by the saved run and human review.
Set CHROMATIN_MERGED_STATS_OUTPUT_DIR outside source experiments, collection,
Pearson/approval and both merge stores. Default:
`<CHROMATIN_TRACE_OUTPUT_DIR>/merged_trace_statistics`, otherwise
`./results/merged_trace_statistics`.

Each invocation saves a fresh UUID directory with statistics.json and native.log.
Evidence includes status, generated UTC time, execution duration, merged/provenance/
merge-log hashes, Pearson/checksum/approval identifiers, source contributions,
native version/module/class hashes, parameters, counts, warnings and native text.

The `baseline_fingerprint` covers exact input/provenance, approval revision/evidence,
native implementation/version, fixed parameters and successful counts. It is stable
for identical evidence/backend; run IDs, times, full evidence checksums differ.
Changed approval revision or backend intentionally defines a different baseline.
This fingerprints an execution context; it is not a signature or proof of biological
validity. Artifact stores are trusted server-managed local evidence, not writable
by ordinary agent tools.

Native/runtime or final evidence failures after verified input scope save ERROR
evidence, warnings, version and available transcript, with no success counts or
baseline fingerprint in the MCP response. Early unverifiable inputs/unsafe output
locations return ERROR without writing evidence. No RUNNING artifact is published.
Original lookup paths alone are not checksum evidence.

Response: COMPUTED/ERROR; evidence path/SHA, log reference, baseline fingerprint,
row/ROI/global-ID/ROI-ID-pair/barcode counts; at most four 320-character warning
previews with total/truncation flags; time and structured-response bytes. Full
records, source metadata and native terminal text stay local. Failures expose no
successful baseline/counts. Native trace_stats creates no figures/distributions.

The existing 32-dataset and 1 GB combined input limit apply. Native Astropy loading,
row verification and repeated hashing require local CPU/memory/I/O. These are not
OS resource quotas or protection against an unrestricted external process changing
files. Original raw paths remain collection-time provenance; validated collected
snapshots are the authorization source. No Spot_ID/Buid coverage claim is made.

## Native/MCP benchmark

With validated package/backend paths configured, use
`python chromatin-trace-mcp/benchmarks/benchmark_merged_statistics.py --help`.
Provide saved merge/checksum arguments and a fresh, separate output directory.
The script requires existing approval, calls direct native statistics and one real
stdio merged_trace_stats invocation, checks equality and protected file hashes,
and records duration/response sizes. It never creates approval or invokes an LLM.
Actual provider input/output/cached/reasoning tokens and cost remain unavailable
until a provider-backed test actually runs. Bytes are not tokens.

## Stop and subsequent stages

Stop for owner review. Later native trace_analyzer and localization_analyzer run
on their respective merged, unfiltered datasets after separate approval. Only after
both analyzers may chromatin-report-mcp compose the comprehensive pre-filtering
report from Step 0/per-ROI evidence, Pearson/approval, both merges/provenance, this
merged baseline and both analyzers' statistics/warnings/figure references. Filtering
comes later. No part of those later integrations is implemented here.
