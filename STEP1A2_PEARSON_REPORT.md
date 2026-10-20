# Step 1a.2 — trace_pearsons implementation and validation

Date: 2026-10-20. Scope: native Pearson QC only. Implemented and deterministically
validated; awaiting owner review. Autonomous-agent validation and actual provider
token measurements are **PENDING / NOT RUN**.

## Implementation

Added trace `trace_pearsons(collections, output_format="png")`. It consumes approved
Step 1a.1 collection run IDs plus manifest SHA-256 values; all tracing files in each
manifest are included. No arbitrary input/output path arguments, implicit Step 0,
collection, merging, approval automation or downstream analyzer are introduced.
The report server and Traceratops scientific algorithms are unchanged.

The wrapper delegates loading, median barcode-pair distance accumulation, Pearson
comparison and plotting to native Traceratops 1.0.1:
`silent_load_trace`, `accumulate_distances`, `compare_distance_maps`,
`plot_correlation_matrix`. It preserves the returned numbers and native NPY/figure
outputs. Full distance maps, matrix, warnings and exact input references are saved
in JSON; a concise Markdown QC report is generated in the same call. The compact
response contains index/ROI/collection mapping and up to ten comparison previews;
full maps and images are not sent by default. Undefined coefficients remain null.

Input files/manifests are checksum verified, copied into private temporary
snapshots, checked for schema/ROI provenance, and rechecked before atomic output
publication. Outputs cannot be placed inside the collection store or its source
experiment root. Original ECSV files are never overwritten. Technical limits:
32 datasets, 8 manifests, 100 MB/file, 1 GB total, 16 MB/manifest. Failures publish no
successful run; MCP schema errors and structured runtime errors are distinct.

Changed/added files:

- `chromatin-trace-mcp/src/chromatin_trace_mcp/pearsons.py`: new modular adapter/report.
- `chromatin-trace-mcp/src/chromatin_trace_mcp/server.py`: register tool (21 trace tools).
- `chromatin-trace-mcp/tests/test_pearsons.py`: 18 focused tests.
- `chromatin-trace-mcp/tests/test_server.py`: updated discovery expectation only.
- `chromatin-trace-mcp/benchmarks/benchmark_pearsons.py`: native/real-stdio benchmark.
- `chromatin-trace-mcp/mcp-config.example.json`: Pearson output-directory example.
- `skills/him-data-diagnosis/SKILL.md`, `AGENTS.md`, trace README,
  `MCP_TOOL_REFERENCE.md`, `references/trace-pearsons.md`, `references/collect-files.md`:
  invocation, compact evidence, native caveats, configuration and stop instructions.
- This implementation report. Existing uncommitted Step 1a.1 work was preserved.

## Tests and scientific accuracy

Focused new tests: **18 passed** (17 deterministic cases and 1 real stdio workflow).
Final combined trace/report/Step 0 workflow suite: **135 passed, 0 failed, 1 skipped**
in **18.34 s**. The 18 new checks are included in that total, not additional to it.
The optional `test_configured_real_trace_is_traceratops_compatible` skipped because
`CHROMATIN_TRACE_ECSV` was intentionally unset. The separate real-collection Pearson
benchmark below did run. Skill frontmatter validation passed.

Tests compare exact native matrices and median-distance maps, native PNG bytes,
preserved PNG/SVG/PDF figures, repeated-run numerical reproducibility, known
negative correlation, undefined constant/one-pair/disjoint-panel cases, duplicate
native handling, unchanged input bytes and distinct output runs. Damaged manifest
hashes, modified/missing/symlink files, localization/wrong-size collections,
duplicate references, unsafe destinations and native failures are rejected without
publishing successful artifacts. The stdio client discovers the tool, validates
input/output schemas, calls collection then Pearson, checks compact response size
and exercises both schema/runtime errors. These are deterministic assertions, not
an AI evaluating its own answer.

Warnings: expected native constant-input warning, the existing All-NaN matrix test
warning, and the existing pytest `asyncio_mode` configuration warning. The unrelated
pre-existing plugin-packaging check and separate SDK benchmark suite were not
rerun; no claim is made that every repository test or live SDK test passed.

### Reference experiment QC

Used the existing approved collection of byte-identical read-only experiment
copies, not a newly selected set of raw files:

| ROI | Rows | Median barcode-pair distances | Repeated trace/barcode groups |
|---|---:|---:|---:|
| 92 | 46,296 | 406 | 1,330 |
| 93 | 34,900 | 406 | 603 |

**Pearson r = 0.8691053986549377 over 406 shared non-NaN barcode pairs.** The saved
matrix, all median-distance values and PNG are exactly equal to direct native
execution. This is a description of the computed result, not a scientific
acceptance threshold or authorization to merge.

Native Pearson uses the last row for repeated barcodes inside a trace, without
allele separation. The native figure uses a fixed 0–1 range and can hide negative
values; numerical outputs preserve them. Trace_ID identifies a nucleus, not
necessarily one chromosome. All these limitations remain visible in the QC report.

Before/after fingerprints of both collected ECSV files, their manifest and source
copies are unchanged. Both actual original ROI trace files also match the approved
manifest hashes; `original_integrity.json` records that check. Integrity claims
cover these specified files, not an unperformed hash of the entire image dataset.

## Performance and provider usage

Final measurement: one direct native run and one real stdio Pearson call using the
same reference collection. Preliminary measurements from the earlier response
shape are retained separately and excluded from the table.

| Measurement | Direct native | MCP |
|---|---:|---:|
| Execution / client tool latency | 1.779462 s | 2.065473 s |
| Server execution | — | 2.032186 s |
| Server startup (separate) | — | 1.464653 s |
| Tool invocations | 0 | 1 |
| Discovery requests (separate) | 0 | 1 |
| Compact structured response | — | 2,184 bytes |
| Serialized MCP result | — | 4,967 bytes |
| Numerical/PNG equivalence | reference | exact |

Native timing excludes adapter snapshotting, ECSV/provenance validation, JSON/report
formatting and checksum rechecks. These workloads differ; this is not a pure
transport-overhead comparison or a repeated-trial performance distribution.
Serialized result bytes include MCP text/structured duplication but exclude
JSON-RPC framing. Neither byte figure is an actual or estimated token count.

**Live provider requests: 0.** Autonomous model tool selection, model latency,
provider model identifier/input/output/total/cached/reasoning tokens and monetary
cost are pending/unavailable (`null` in records). No claim of live agent accuracy
or token savings is made. The benchmark intentionally uses no model credentials.

## Evidence and next step

Local evidence is in the project workspace under
`acceptance/step1a2_pearsons_2026-10-20/`:

- `regression-final.xml`: exact combined test results.
- `original_integrity.json`: original files versus approved fingerprints.
- `real-experiment-final/benchmark.json`: final timings, bytes, integrity and usage.
- `real-experiment-final/mcp_response.json`: real MCP response.
- `real-experiment-final/direct.png` / `.npy`: direct native outputs.
- `real-experiment-final/mcp/d345da968c654d29b9c6842fe3d74fac/`: QC report, original
  native figure/NPY, full numerical JSON and native log.

No scientific algorithms, Step 0 validation logic, collection implementation or
report-server code changed. Existing broad legacy tools remain available for
compatibility; this substep does not implement a global approval/security gate.
Application checks are not an OS memory/CPU sandbox. Correlation may be undefined,
and duplicate handling/plot-range limitations require human scientific review.

The next roadmap substep is **Step 1a.3 — scientific approval gate**, requiring
explicit owner approval of further development. It is **not implemented** here.
Review the Pearson QC report first. Stop after Step 1a.2.
