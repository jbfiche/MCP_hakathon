# Step 1b.2 — localization_merge implementation and validation

Date: 2026-10-21. Implemented localization merging only. Future trace_stats reporting
was inspected and documented, not implemented. Stop for owner review before Step 1c.

## Implementation

Added `localization_merge(pearson_run_id, results_sha256,
selected_dataset_indices, localization_collections)` to chromatin-trace-mcp, now
24 tools. Existing clients/tool names are preserved; restart the MCP server/client
connection to discover the new tool. chromatin-report-mcp is unchanged.

The wrapper calls the existing `require_scientific_approval` gate and requires the
exact human-approved tracing selection. It reads hash-verified tracing/localization
collection manifests and matches original experiment roots and source ROI directory
provenance. Renamed collected filenames or output ROI numbers are not association
keys. Unselected ROIs are excluded; ambiguous/missing/foreign mappings fail closed.

Selected localization bytes are copied to private read-only snapshots. Unmodified
native `traceratops.localization_merge.run` performs merging using
`load_localizations`/`appends_traces`, `LocalizationTable.load`, `append` (Astropy
vstack), and `save`. The wrapper verifies output row contributions, all input column
values/masks, unchanged ROI/barcode/Buid values and scientific units after ECSV
reload. It adds compatibility/integrity checks, not another scientific algorithm.

Before publication, approval revision, Pearson/tracing evidence, localization
manifest/file hashes and source associations are rechecked. The final evidence
checks and atomic publication use the existing approval decision lock. Missing or
changed evidence, revoked approval, invalid schemas/metadata or native failure
produces ERROR with no published success artifacts.

Full native ECSV, source/merged table and column metadata, original-path associations,
row/ROI contributions, hashes, approval snapshot and native log remain on disk.
The MCP response contains compact counts, artifact references, warnings and timing/
byte telemetry. Output goes to `CHROMATIN_LOCALIZATION_MERGE_OUTPUT_DIR`, outside
experiment and evidence stores. No trace merge, analyzer, statistics workflow or
filter is invoked automatically.

### Authorization scope

The existing human decision binds tracing evidence and the original tracing ROI
selection. It does **not** bind localization bytes absent from Pearson review.
This wrapper authorizes localization merging for those source ROIs, binds exact
localization collection/file checksums for the execution, and records that distinction
in warnings and provenance. It does not claim localization bytes were human-reviewed.
A future requirement for human approval of exact localization versions needs an
explicit approval-contract extension. No new approval mechanism was added here.

## Tests

Final regression results:

| Suite | Passed | Failed | Skipped | Duration |
|---|---:|---:|---:|---:|
| Trace server and Step 0 cross-server workflow | 205 | 0 | 1 | 54.84 s |
| Report server | 7 | 0 | 0 | 1.12 s |
| Total | **212** | **0** | **1** | **55.96 s** |

Includes **33 new localization checks**, including real MCP stdio discovery,
input/output schemas, rejected calls before approval, host-elicitation test fixtures,
approved invocation, compact response validation and error handling. Scripted host
responses are clearly labeled synthetic fixtures; they are not autonomous-agent
validation or consent for real scientific data.

Tests cover native byte equivalence, exact selected subset, reproducibility,
provenance/metadata preservation, invalid/awaiting/rejected approval, changed tracing
evidence, missing/modified localization files, bad localization manifests, wrong
roles/experiment roots/source paths/ROI directories, ambiguous/missing mappings,
ROI collisions, row/schema/ROI corruption, invalid ECSV, unit/assembly conflicts,
native exceptions/SystemExit, unsafe output placement, and changes/rejection during
execution preventing publication.

The existing optional real-trace test skipped because CHROMATIN_TRACE_ECSV was
intentionally unset. Existing pytest asyncio_mode configuration, native constant-input
Pearson and All-NaN warnings remain. Skill validation passed. The first combined
runner stopped during test collection because both servers have test_server.py;
separate processes fixed the runner collision, and the results above are the final
executed suites. No validation logic was changed to make tests pass.

The unrelated pre-existing plugin-packaging check and separate optional Agents SDK
suite were not rerun. No claim is made that those checks were fixed or live agent
behavior was evaluated.

## Reference experiment: ROIs 092 and 093

Reused the actual saved manual test approval for Pearson run
`d345da968c654d29b9c6842fe3d74fac`, checksum
`23a5f8e237647041bbd358803c7f96ad435b9a2043036d52855f27b5888742e2`,
selection `[0,1]`, revision `3f8780a346424ea1b3d16c05f8868c3c`.
No decision was created or simulated. This approval applies to the existing
reference-copy experiment, not a different live experiment or Pearson store.

A new native validated localization collection was written into the same collection
store as the approved traces; existing collection artifacts were not altered.
It uses the previously protected input copies. The two original source associations
are `092/localize_3d/data/localizations_3D_barcode.ecsv` and
`093/localize_3d/data/localizations_3D_barcode.ecsv` under that same experiment root.
A real stdio call merged exactly those approved ROIs:

- ROI 092: **61,420** input rows.
- ROI 093: **41,741** input rows.
- Merged: **103,161 rows**, **29 observed barcodes**, **2 ROIs**, **103,161 unique Buid**.
- Full saved ECSV is **byte-identical** to direct native Traceratops output.
- Source ROI numbers, barcode/localization identifiers and all checked source values
  are preserved. Metadata declarations are incomplete; no missing unit/assembly
  information is inferred or claimed verified.

Hash checks confirmed unchanged collection files, scientific reference copies,
Pearson artifacts and approval record. An additional 42-file integrity record covers
four reference scientific ECSV inputs, their four corresponding original ECSV files
in Ressources/092 and Ressources/093, and 34 native Python source files. Those
files remain unchanged. This is a scoped integrity check, not a scan of every image
or every unrelated file in the experiment directories.

## Performance and usage

One direct/native trial and one MCP trial on the reference copies:

| Measurement | Result |
|---|---:|
| Native merge and save | 0.963 s |
| MCP tool call latency | 2.322 s |
| Server wrapper execution | 2.293 s |
| MCP startup, separate from call | 1.525 s |
| Scientific MCP tool calls | 1 |
| Discovery requests | 1 |
| Structured JSON response | 1,372 bytes |
| Serialized MCP result | 3,142 bytes |

The native baseline excludes approval checks, snapshots, reload verification and
provenance. A single trial is not a performance distribution. MCP result bytes
include text/structured duplication, excluding JSON-RPC framing.

**Provider-backed autonomous orchestration and actual model usage: PENDING / NOT
RUN.** No LLM/provider requests were made. Model, input/output/total/cached/reasoning
tokens and cost are null/unavailable, not estimated from response bytes. These
measurements validate native/MCP execution, not agent tool selection or token savings.

## trace_stats audit and roadmap — documentation only

See `references/trace-stats-integration.md`. Existing `trace_stats(dataset_name)`
resolves a registered trace table and calls native compute_trace_statistics.
It returns unique ROI, global Trace_ID and barcode counts plus captured text.
Compatible individual-ROI and merged tables are supported via registration.
It emits no figures, saved numerical files or full statistical distributions.
Empty/invalid tables fail; global Trace_ID counts can differ from ROI/trace counts.
These are descriptive observations, not acceptance criteria or allele counts.

The roadmap documents future per-ROI Step 0 statistics and a merged Step 1c
pre-filtering baseline, reusing existing numbers/evidence and referencing future
figures when available. Simple summaries remain in trace; requested rich
multi-analysis composition may later use the report server. Neither statistics
reporting workflow was implemented, and no duplicate statistics wrapper was added.

## Remaining limitations

- Native localization merging preserves ROI IDs, while tracing merging renumbers
  collisions. Repeated numeric source ROI IDs across approved experiments are
  rejected; no independent relabeling algorithm or automatic alignment is invented.
- Multiple selected tracing tables for the same original experiment/ROI, duplicate
  localization candidates and one-dataset selections are rejected as unsupported.
- Approval covers tracing source ROI selection, not human review of localization
  bytes absent from Pearson QC. Snapshot hashes protect execution consistency.
- Original paths are collection-time provenance. Scientific execution uses validated
  collected snapshots; it does not rediscover mutable original directories or certify
  Spot_ID/Buid link coverage. No barcode-only join is used.
- Native metadata reconciliation is retained with source metadata in provenance.
  Conservative unit/assembly conflicts are rejected; no alias normalization or unit
  conversion is implemented. Missing metadata remains explicitly unverified.
- Astropy merging uses local memory. File/count/byte bounds are not an OS resource
  sandbox; another process with unrestricted write access is outside application
  lock/hash isolation. Keep artifact stores trusted and stable during execution.
- Actual autonomous-agent/provider-token validation remains pending.

## Changed files and evidence

Added `localization_merge.py`, `tests/test_localization_merge.py`,
`benchmarks/benchmark_localization_merge.py`, `references/localization-merge.md`,
`references/trace-stats-integration.md`, and this report. Updated server registration,
discovery expectations in three existing test files, configuration example, READMEs,
AGENTS, diagnosis SKILL, tool reference, approval/trace-merge references and audit
status. Existing server functions/classes, Step 0, collection, Pearson, approval,
trace_merge, report formatting, report server and native algorithms are unchanged.

Machine-readable local evidence:

- `implementation/step1b2-localization/trace-step0.xml` and `report.xml`: exact tests.
- `implementation/step1b2-localization/scope-integrity.json`: unchanged implementations.
- `acceptance/step1b2_localization_merge_2026-10-21/original-integrity.json`: original hashes.
- `acceptance/step1b2_localization_merge_2026-10-21/reference-benchmark/benchmark.json`:
  native equivalence, latency, bytes, provider-usage nulls and protected evidence hashes.
- Same benchmark directory: direct ECSV/log, MCP response, and complete merged
  ECSV/provenance/native log under `mcp/55fee4c7edd54980a210cf94dc695558/`.

Evidence paths above are relative to the local amel project workspace, not the
repository. The repository contains the reusable benchmark and documentation.

**Stop for owner review.** Step 1c and new statistics reporting require separate
approval. No further pipeline stage was implemented or triggered.
