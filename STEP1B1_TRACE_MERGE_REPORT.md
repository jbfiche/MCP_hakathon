# Step 1b.1 — trace_merge implementation and validation

Date: 2026-10-21. Scope: approved tracing-table merging only. No localization
merging, analyzers, new reporting functionality or Traceratops algorithm changes.
Stop for owner review before Step 1b.2.

## Implementation

Added `trace_merge(pearson_run_id, results_sha256, selected_dataset_indices)` to
`chromatin-trace-mcp` (23 tools). It reuses saved Pearson results and verified
collection outputs. The selection must exactly match existing human approval and
contain at least two datasets. No source/output path arguments, force-skipping,
scientific tuning, implicit approval or dataset selection are exposed.

The wrapper calls `require_scientific_approval`, snapshots approved bytes into
private read-only files, and delegates to native `trace_merge.load_traces` and
`ChromatinTraceTable.save`. It verifies ECSV row counts and every non-ROI input
column/mask/value and column unit against the corresponding output rows. Native
ROI changes are recorded per source with output row ranges, preserving provenance
without implementing a separate renumbering algorithm.

Approval and evidence are rechecked before publication. The last current-evidence
and decision check plus atomic output rename use the existing decision lock.
Revocation or changed inputs/evidence prevents successful artifact publication.
Original files are never writable destinations. Outputs must be outside source
experiments, collection and Pearson/approval stores.

A fresh output directory holds complete native ECSV, `provenance.json` and
`native.log`. Provenance includes a snapshot of the actual approval/revision/
fingerprint, manifest/file hashes, original-to-output ROI mapping and row ranges,
complete table and column metadata serialized as Astropy YAML, native module/class
hashes/version, counts and full warnings. The compact MCP response has paths,
checksum, counts, warning previews/truncation flags, duration and response bytes;
no complete tables or approval snapshots are returned to the agent.

Added `merge.py`, `tests/test_merge.py`, `benchmarks/benchmark_merge.py`,
`references/trace-merge.md` and this report. Updated trace registration/discovery,
the existing approval test's discovery expectation, configuration example, README,
AGENTS, tool reference, scientific-approval reference and diagnosis SKILL.
Existing uncommitted Pearson-reporting work was preserved. No approval helper,
Step 0/collection/Pearson implementation, formatter or report-server logic changed.

## Tests

Final relevant regression suite: **179 passed, 0 failed, 1 skipped in 40.76 s**,
including **20 new merge checks**. The optional real-trace compatibility test skipped
because `CHROMATIN_TRACE_ECSV` was intentionally unset. Existing native constant-
input/All-NaN and pytest `asyncio_mode` warnings remain. Skill validation passed.
The unrelated packaging and separate SDK suites were not rerun.

Coverage: exact native ECSV byte equivalence and reproducibility; approved subset
only; source metadata, columns, row counts and input integrity; awaiting/rejected/
changed approval; wrong selection and missing/symlink/modified files; altered
report/results/manifests; revocation or source changes during native execution;
native ROI collisions and empty inputs; metadata conflicts/unknown declarations;
unsafe destinations; native failures; and real stdio schema/discovery/approval-to-
merge invocation. Synthetic host/approval fixtures are test fixtures, never consent
for real experiments. The existing Step 0 and Pearson/approval regressions pass.

An initial empty-input test found that native output can promote ROI IDs to float.
The wrapper was corrected to normalize integer-valued labels only for summary/
provenance purposes, with a warning; the saved native ECSV remains unchanged.
The final empty-input test verifies byte equality with direct native execution.

## Reference experiment and benchmark

Used the **existing manual terminal approval** in isolated trial
`20261020T101713Z-5eaf376a`, selecting dataset indices `[0,1]` (source ROIs 092/093).
No new real-data approval was created. The original/main Pearson store is a
separate authorization scope; this test-copy approval does not approve that store.

The measured initial reference trial produced **81,196 rows, 29 unique barcodes,
12,609 unique Trace_IDs, 12,609 ROI/Trace_ID pairs, and 2 ROIs**. Complete ECSV bytes,
including native metadata, matched direct Traceratops execution. Input tables,
collection manifests, saved QC artifacts and the approval record were unchanged.
The merged artifact and provenance are in the workspace under
`acceptance/step1b1_trace_merge_2026-10-21/reference-benchmark/`.

| Initial measured trial | Value |
|---|---:|
| Direct native load/save | 0.635688 s |
| MCP client tool latency | 1.624803 s |
| MCP server execution | 1.597692 s |
| MCP startup, separate | 1.507644 s |
| Merge tool calls | 1 |
| Discovery requests, separate | 1 |
| Structured response | 1,085 bytes |
| Serialized MCP result | 2,558 bytes |

**Version caveat:** this trial preceded the final empty-input label handling and
additional per-source metadata checks/provenance fields. The final benchmark
execution was declined by the user and was not rerun or worked around. Final-
wrapper timing and response-size measurements are therefore **NOT MEASURED**.
The final code's scientific equivalence is established by regression tests; the
numbers above must not be presented as timings for that exact final code version.
One initial run per mode is not a performance distribution. Native baseline omits
wrapper approval, snapshots, validation and provenance. Serialized result bytes
include text/structured duplication, excluding JSON-RPC framing.

Provider requests: **0**. No API key was configured in the benchmark environment.
Actual model input/output/total/cached/reasoning tokens, live agent latency and cost
are unavailable/null. Autonomous-agent merge validation remains pending. No token
estimates or token-savings claim is made. A reusable no-LLM benchmark script is
provided; it requires an existing approval and never creates one.

## Limitations and scientific conventions

- Native merging seeds `xyz_unit=micron` and `genome_assembly=mm10`. Conflicting
  input/output unit or assembly declarations fail closed. Thus consistently declared
  `dm6` inputs currently fail when native initialization introduces `mm10`; an
  upstream-compatible native fix is needed, outside this milestone. Metadata is
  not relabeled to make tests pass. Labels are not biologically verified, and unit
  aliases are handled conservatively. Missing source declarations are warned about.
- Native ROI renumbering and empty-input float promotion are preserved, not fixed.
  Full source/column metadata remains in provenance even when native reconciliation
  chooses one value for differing non-unit/assembly metadata.
- Trace_ID is nucleus-level. Repeated barcodes/alleles are not resolved or filtered.
  Global unique IDs and ROI-scoped counts are separate; repeated IDs across ROIs
  are warned about without relabeling.
- The existing gate binds Pearson parameters. This tool has a fixed native merge
  policy, not configurable scientific parameters. Future tunable policies must
  extend authorization before exposing those options. Backend hashes are recorded;
  approvals are not cryptographic attestations of installed merge code.
- Application snapshots/locks/byte limits are not an OS CPU/memory/filesystem
  sandbox against another process with unrestricted access as the same user.
  Astropy/native merging remains in memory. There is no separate failure artifact.

Evidence: `regression-final.xml`, `source_integrity.json`,
`final-benchmark-status.json`, and the initial benchmark records in the project
workspace's `acceptance/step1b1_trace_merge_2026-10-21/` directory.

## Next milestone — not implemented

Step 1b.2 is localization merging and requires explicit owner approval. Before
its authorization rules are designed, verify localization-manifest correspondence
to the approved original experiment/source tracing ROIs and any required consistent
ROI renumbering. Output ROI numbers alone are insufficient across collections.
No localization mapping, merge or analyzers were implemented here.
