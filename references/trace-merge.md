# Step 1b.1 — native trace_merge with scientific approval

Only run when merging is requested and an existing human approval covers the exact
selected tracing datasets. Approval of software development/tests is not approval
to merge an experiment. There is no automatic approval, dataset selection,
localization merge, analyzer, or new reporting workflow.

```json
{
  "pearson_run_id": "32-lowercase-hex-run-id",
  "results_sha256": "64-lowercase-hex-results-checksum",
  "selected_dataset_indices": [0, 1]
}
```

Replace placeholders with an existing saved Pearson result and its human-approved
selection. Indices are positions in that run, not ROI numbers. The list must exactly
match the sorted approved selection, with at least two datasets. Added, omitted,
reordered or duplicate indices do not silently change the authorized operation.
No arbitrary source/output paths, force flags, scientific parameters, ROI policies,
thresholds or identifier relabeling options are exposed.

## Native operation and approval enforcement

The wrapper calls `require_scientific_approval` before reading selected inputs and
again before publication. It reuses validated collection files and Pearson evidence,
not newly discovered tracing tables. Selected bytes are copied into private,
read-only temporary snapshots and checksum/schema/row/ROI checked. Native
`traceratops.trace_merge.load_traces` and `ChromatinTraceTable.save` operate on those
snapshots, with the native `appended_trace_files=N` comment. No native algorithms
are changed or reimplemented.

Before publishing, the wrapper rechecks approval revision, current evidence and
selected files. The last evidence check and atomic output rename occur under the
existing per-run decision lock. A rejected/awaiting/stale grant, changed evidence,
missing file, changed selection or decision during merging prevents publication.
The native computation may have run on temporary snapshots, but no successful
merged artifact is advertised when these checks fail. Snapshot data always matches
the approved hashes; another process with unrestricted OS access is not isolated
by application checks. Do not edit scientific inputs during execution.

The existing approval binds Pearson parameters. This tool exposes a fixed
`native-trace-merge-v1` operation rather than configurable merge parameters; native
module/class hashes are recorded. Any future tunable merge policy must extend the
authorization contract before exposing those options. Pin and review backend
changes; this milestone does not create a new approval mechanism or cryptographic
attestation of the installed merge implementation.

## Scientific integrity and native limitations

- All non-ROI input columns, masks and values are checked against their exact output
  row contributions after ECSV reload. Output rows must equal the sum of selected
  rows. Column units must be preserved. No rows/barcodes/alleles are filtered.
- Native merging renumbers colliding ROI IDs. The wrapper preserves native output
  and records each dataset's source ROI, row range and observed output ROI mapping.
  It does not add its own renumbering algorithm or rename Trace_ID/Spot_ID values.
- Native empty-input handling can promote ROI IDs to floating point. The ECSV stays
  byte-identical to native execution; integer-valued labels are normalized only in
  summary counts/provenance mapping and this behavior is warned about.
- Global unique `Trace_ID` count and distinct `(output ROI, Trace_ID)` count are
  returned separately. Repeated IDs across ROIs are warned about. Trace_ID is a
  nucleus-level identifier; merging does not establish allele separation.
- Table and column metadata for every source, plus merged metadata, are preserved
  as Astropy YAML strings in provenance, alongside immutable ECSV references/hashes.
  Native metadata reconciliation is retained; differing non-unit/assembly metadata
  is warned about and remains recoverable per source.
- **The native constructor seeds `xyz_unit=micron` and `genome_assembly=mm10`.** The
  wrapper rejects conflicting input units/assemblies or conflicting native output.
  For example, consistently declared `dm6` inputs currently fail because native
  initialization introduces `mm10`; they are not silently relabeled or corrected.
  An upstream-compatible native metadata fix would be needed for that case and is
  outside this milestone. Unit/assembly labels are compared conservatively; aliases
  may need consistent declarations. There is no unit conversion or biological
  verification of recorded assembly labels. Missing declarations are warned about;
  native defaults do not establish previously unknown experimental metadata.

## Configuration and output

Set `CHROMATIN_COLLECTION_OUTPUT_DIR` and `CHROMATIN_PEARSON_OUTPUT_DIR` to the same
stores used for collection and human review. A grant in a terminal test-copy store
does not authorize a run in a different Pearson store. Do not manufacture an
APPROVED record for an experiment.

Set `CHROMATIN_MERGE_OUTPUT_DIR` outside experiment inputs, collections and Pearson/
approval evidence. Default: `<CHROMATIN_TRACE_OUTPUT_DIR>/trace_merges`, otherwise
`./results/trace_merges`. Every invocation publishes a fresh UUID directory:

- `merged_traces.ecsv`: complete native output, with SHA-256.
- `provenance.json`: approval snapshot/revision/fingerprint, Pearson ID/checksum,
  exact selection and collection references, full per-source row/ROI/metadata
  contributions, native hashes/version, merged counts and all warnings.
- `native.log`: native stdout/stderr and processing messages.

The compact MCP result contains `MERGED` or `ERROR`, ECSV/provenance paths,
SHA-256, source-file/row/barcode/trace/ROI counts, four warning previews with full
count/truncation flags, time and JSON response bytes. Complete tables, metadata and
approval snapshots stay on disk. Invalid arguments produce schema errors; runtime
failures return ERROR with no successful artifact paths. Temporary results are
removed. Errors do not publish a separate failure artifact.

Existing 32-dataset, 100 MB/file and 1 GB total input limits apply through the
approval/collection checks. Astropy/native merging is in memory; byte limits are
not an OS memory/CPU sandbox. ECSV bytes are reproducible for the same approved
ordered inputs under the validated backend; run IDs and timing differ.

## Benchmark

Run the existing Python environment with both this package's `src` and the validated
Traceratops source on `PYTHONPATH`, configure the stores above, then use:

```sh
python chromatin-trace-mcp/benchmarks/benchmark_merge.py \
  --pearson-run-id VALID_RUN_ID --results-sha256 VALID_SHA256 \
  --indices 0 1 --output /private/new-merge-benchmark
```

The script requires an existing approval; it never requests or creates a decision.
It compares direct native execution and a real stdio MCP call, checks exact ECSV
bytes and unchanged input/approval hashes, and saves machine-readable records.
One run per mode is not a performance distribution. Native timing omits the
wrapper's approval, snapshot, parsing/validation and provenance work. Startup is
separate; serialized MCP result bytes include text/structured duplication but not
JSON-RPC framing. Bytes are not model tokens. No LLM is invoked by this script;
provider-backed autonomous validation and token/cost measurements remain pending.
Synthetic approval fixtures in unit/protocol tests are test evidence, never consent
for real data. The reference benchmark can reuse an actual existing manual test
approval without making a new decision.

## Stop and Step 1b.2

Tracing merge does not invoke localization merging. The separately requested
Step 1b.2 operation is documented in [localization merging](localization-merge.md).
It matches original experiment/source ROI provenance and rejects source ROI
collisions that native localization merging cannot align with tracing renumbering.
Owner review is required before later milestones; no analyzers run here.
