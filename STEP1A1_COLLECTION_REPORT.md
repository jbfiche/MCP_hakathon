# Step 1a.1 — collect_files implementation and validation

Date: 2026-10-19. Scope: explicit collection only. Step 0 live-agent validation remains independent.

## Implementation

Added one MCP tool, `collect_files`, in `collection.py` and registered it on the existing trace server (20 total tools). It delegates matching/copy policy to native Traceratops `build_pattern`, `FilePattern.matches`, `collect_files`, `scan_subdirectories` and `dest_name`. No Traceratops source was changed.

Inputs are an authorized root, example ECSV basename, optional fixed-length variable part, table kind and rename flag. Force-skipping is disabled. Collection creates a private eligible-file snapshot, invokes native copying, validates ECSV schemas/ROI provenance and byte/row/column identity, rehashes sources, and atomically publishes a fresh collection directory. Missing, ambiguous, invalid, conflicting or changed inputs fail without publishing a partial dataset.

A full JSON manifest preserves source paths, original ROI directories, normalized ROI IDs, hashes, sizes/mtime, rows/columns, output identities, parameters and native module version/hash. Native console output stays local. The response contains counts, at most ten preview entries (reduced for long paths), paths, execution time and structured-response byte count. JSON-RPC sizes are measured separately by the benchmark.

Step 0 code and its autonomous-agent benchmark were left byte-identical. The only existing test-contract update is the global catalog expectation of 20 rather than 19 tools. Collection is not invoked by Step 0 and stays outside its agent allowlist. No persisted Step 0 approval state is fabricated: this explicit operation was authorized separately while Step 0 validation proceeds in parallel. No Pearson, merge or analyzer is called.

Changed files: new collection source/tests, native/SDK benchmark script and collection reference; trace registration/catalog expectation/configuration/README; repository instructions, tool reference and diagnosis skill. The report server is unchanged.

## Tests and scientific accuracy

- Full trace, richer-report and single-call Step 0 workflow suite: **117 passed, 0 failed, 1 skipped** in 10.31 seconds. New collection tests: **38 passed**. The skipped test is the optional configured-real-table compatibility check; the real tables were checked separately in the benchmarks below.
- Native-equivalence tests cover tracing (renamed and unrenamed) and exact-name localization collection, plus repeatable output bytes and distinct output runs.
- Negative tests cover missing/ambiguous inputs, invalid ECSV, missing columns, ROI mismatch, variable-width filenames, bad patterns, unauthorized roots, unsafe output locations, matching/ROI symlinks, excluded trees, traversal/byte/file limits, native failures, output tampering, source changes, collisions, and preview limits.
- Real MCP integration covers dynamic discovery, input/output schema validation, invalid-argument protocol errors, structured byte counts and actual subprocess stdio invocation.
- Reference experiments: **2 trace files / 81,196 rows** and **2 localization files / 103,161 rows**. Four original reference files match the read-only copies by SHA-256. Source-copy fingerprints stayed unchanged in every benchmark run.
- Across three repeats per kind, **12/12 MCP/SDK comparisons** exactly matched direct native filenames, all output bytes and row counts. The six direct native control runs are separate deterministic baselines. SHA-256 equality preserves coordinates, identifiers and metadata without asking an LLM to assess scientific accuracy.
- Every collection result is marked `collection_only` and stops for review. A tripwire test rejects downstream Pearson/merge invocation; Step 0 automatic calls are neither changed nor extended.
- Existing Step 0 SDK regression suite: **37 passed, 0 failed, 0 skipped** in 14.29 seconds. These remain offline tests and do not substitute for the parallel fresh-agent validation.
- Skill validation passed. Existing pytest-asyncio configuration and All-NaN test warnings remain; no unrelated packaging fix was attempted.

## Performance and provider usage

Three repeats per cell, fresh MCP/SDK instances. Timings exclude server startup. Native timing covers copying only; MCP additionally snapshots, parses both source/output tables, hashes, validates and persists provenance. These are different workloads, not a measurement of transport overhead alone. SDK runs use an explicitly scripted Model and are not autonomous LLM trials.

| Inputs | Direct native seconds | MCP seconds | Scripted SDK seconds | MCP result bytes | Calls per MCP/SDK run |
|---|---:|---:|---:|---:|---:|
| Tracing | 0.002646 | 0.627270 | 0.635680 | 2848–2854 | 1 |
| Localization | 0.003076 | 0.947441 | 0.954861 | 2820–2822 | 1 |

Bytes are canonical serialized MCP CallToolResult JSON (text/structured duplication included; JSON-RPC framing excluded). They are not token estimates. Direct execution has no MCP response. Scripted SDK runs perform two model-double steps and one tool invocation.

**Live autonomous trials: NOT RUN (no API credentials configured). Actual provider model/input/output/total/cached/reasoning tokens, live-model latency and monetary cost: unavailable/null.** The reusable benchmark includes `--live --model` with fresh agent objects, scoped dynamic tools and the existing provider-usage recorder. That provider path was not exercised and is not claimed as passed. Offline SDK values are excluded from actual model usage. Exact setup and scope are in `references/collect-files.md`.

## Limitations and next step

- The snapshot adds temporary disk I/O and ECSV parsing overhead. Astropy loads tables in memory; application limits are not an OS memory/filesystem sandbox.
- Native matching is fixed-length. Mixed-width ROI filenames can fail; no alternate matching algorithm or automatic mask choice was introduced.
- Only regular eligible inputs are collected. Excluded trees and unrelated links are not inspected; their counts are recorded. Immediate ROI symlinks/matching symlink files fail. Equivalence is scoped to eligible inputs, not excluded targets.
- No scientific threshold or biological interpretation is inferred from collection or Step 0 PASS. Empty valid tables are preserved and explicitly marked.
- Future traces/merge workflows still need their separately approved scientific QC and approval mechanisms. Existing unrelated tools remain available for compatibility; this operation does not invoke them.
- The next proposed substep is **Step 1a.2 — trace_pearsons**, using the reviewed collected manifests/tables. It was not implemented. Stop here and await owner approval; do not implement Step 1b.
