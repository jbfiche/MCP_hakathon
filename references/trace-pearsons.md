# Step 1a.2 — native Pearson QC

Only invoke `trace_pearsons` when requested. Use previously validated collection
manifests; this tool never collects data or runs Step 0 implicitly. The trace
server now exposes 21 tools; existing names and schemas remain compatible.

```json
{
  "collections": [
    {
      "collection_run_id": "32-lowercase-hex-run-id",
      "manifest_sha256": "64-lowercase-hex-manifest-checksum"
    }
  ],
  "output_format": "png"
}
```

The placeholders above must be replaced with actual `collect_files` result values.
All tracing files in each manifest are included. Localization collections are
rejected. Use 1–8 manifests containing 2–32 datasets total. There is no mask
selection, exclusion, scientific acceptance threshold or approval parameter.
`png`, `svg` and `pdf` are the original native figure formats.

## Native calculation and limitations

The adapter uses Traceratops `silent_load_trace`, `accumulate_distances`,
`compare_distance_maps` and `plot_correlation_matrix`, unchanged. It computes
median nucleus-level distances for each barcode pair, then Pearson correlations
between dataset vectors over shared non-NaN entries. Returned numbers and saved
NPY matrices come from Traceratops, not an MCP reimplementation. P-values are not
returned by this native API and are not invented.

Native handling keeps the last row for repeated barcodes within a Trace_ID.
The report identifies affected groups; the wrapper does not resolve alleles or
filter observations. Trace_ID identifies a segmented nucleus. NaN/undefined
coefficients are JSON `null`, never zero. The native plot uses a fixed 0–1 color
range, so negative correlations can be visually clipped; inspect numerical results.
No change to that scientific or plotting behavior is made here.

`COMPUTED` means the operation completed, not scientific PASS or permission to
merge. Correlation alone does not demonstrate biological equivalence. Review the
QC report and figures; no datasets are selected and no approval state is created.

## Configuration and integrity

`CHROMATIN_COLLECTION_OUTPUT_DIR` must point to the store used for collection. Its
fallback is `<CHROMATIN_TRACE_OUTPUT_DIR>/collections`, then `./results/collections`.
`CHROMATIN_PEARSON_OUTPUT_DIR` defaults to
`<CHROMATIN_TRACE_OUTPUT_DIR>/pearson_qc`, then `./results/pearson_qc`.
Outputs must be outside the collection store and original experiment roots.
Callers pass run IDs/checksums, not arbitrary input/output paths.

The server verifies manifest identity, schema, role and SHA-256; opens bounded,
regular collected ECSV files without following file/run-directory symlinks; checks
copied-file hashes, row counts, columns and ROI provenance; and passes private
snapshots to native loading. It rechecks manifests/files before publishing output.
Original experimental files are never writable destinations. Only complete,
verified results are atomically published under a fresh run ID. Failures return
`status=ERROR`, an error type/message and no successful artifact paths. Invalid
MCP arguments produce schema errors. Temporary snapshots/results are removed.

Limits reuse collection's 100 MB per file/1 GB total selected bytes, plus 16 MB per
manifest and 32 datasets. Native calculations run locally in memory. These checks
are not an OS sandbox or isolation from another process running as the same user.
Do not change collection artifacts during execution. Runtime errors do not publish
a failure artifact; they remain in the MCP response.

## Artifacts and compact response

Each successful output directory contains:

- `trace_correlation_matrix.png` (or SVG/PDF): unchanged native figure.
- `trace_correlation_matrix.npy`: unchanged native numerical matrix.
- `results.json`: full correlation matrix, median-distance maps, dataset/ROI mapping,
  exact collection references, warnings, native version/hash and parameters.
- `pearson_qc.md`: counts, dataset mapping, warnings and a short preview, followed
  by the complete pairwise table for larger runs. Every comparison is retained.
- `native.log`: native stdout/stderr; scientific warnings also appear in the report.

The MCP response includes compact index/ROI/collection-ID mapping for all datasets,
dataset/comparison counts, at most ten off-diagonal
correlations with shared-pair counts, four warning previews with total/truncation
flags, artifact paths/checksum, time and JSON-response size. Full evidence and images
remain outside model context by default. `structured_response_bytes` is compact
UTF-8 JSON only, not transport size or token usage. The benchmark records serialized
MCP size separately, which includes duplicated text/structured protocol content.

## Reproducing verification and benchmark

In the validated Python environment with this MCP and Traceratops installed:

```sh
python -m pytest chromatin-trace-mcp/tests/test_pearsons.py -q
python chromatin-trace-mcp/benchmarks/benchmark_pearsons.py \
  --references /private/collection-references.json --output /private/new-pearson-benchmark
```

The reference file contains the JSON `collections` list. In a source checkout,
configure `PYTHONPATH` to the trace package's `src` and the validated Traceratops
source. The child MCP inherits this environment. Set `MPLBACKEND=Agg` headlessly.
Use output outside scientific inputs. The benchmark performs one direct native run
and one real stdio tool call, asserting exact matrices, distance maps, PNG bytes and
unchanged input hashes. Native baseline timing excludes adapter validation/report
work; startup and tool latency are separate. Single trials do not establish a
performance distribution. No LLM is invoked: autonomous validation, provider usage,
tokens and monetary cost remain pending/null. Bytes are not estimated tokens.

Stop after the QC report for user review. Merging, approval automation and downstream
analyzers are outside this substep and must not be inferred from a favorable r.


Reporting stays in the trace server for routine Pearson QC. The local formatter
is pure and modular; human forms use bounded pair previews and artifact references.
See [reporting boundaries and future report-server criteria](pearson-reporting.md).
