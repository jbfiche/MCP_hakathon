# Step 1c — merged, unfiltered tracing statistics

Date: 22 October 2026. Implemented merged statistics only. No analyzer, comprehensive
report, filtering, new cross-server tool, native algorithm or approval-mechanism change.
Stop for owner review.

## Implementation

Added `merged_trace_stats(trace_merge_run_id, merged_sha256, provenance_sha256)`
to chromatin-trace-mcp (now 25 tools). This one-call operation reuses the existing
native trace_stats adapter shared with the public trace_stats tool and Step 0.
No catalog registration or separate native-statistics call is required from the
agent. The shared adapter accepts an optional internal transcript stream so a
failed native call can preserve its printed evidence; existing public arguments
and result fields remain compatible.

The existing trace_merge result gains the additive provenance_sha256 field so it
supplies all three required reference arguments. This changes only its returned
checksum, not merge execution/calculations, stored artifacts or approval behavior.
Older merge artifacts remain usable with their trusted provenance checksum.

Before native execution, the tool verifies merged ECSV and provenance checksums,
merge schema/run/phase/policy, native implementation hashes, current exact human
approval and saved snapshot/revision/fingerprint, Pearson/collection evidence and
source selection/order. Using immutable snapshots, it validates source contributions
with the existing merge validator, including values/masks/units, source metadata,
row counts/ranges and ROI mappings. It checks the existing ROI/Trace_ID count as
an identifier-integrity check, then reuses that provenance value.

Native Traceratops compute_trace_statistics provides the unique ROI, global unique
Trace_ID and barcode counts. These must agree with merge provenance. The tool
rechecks current approval/Pearson/collection evidence and merged/provenance/native
log hashes immediately before atomic publication under the existing decision lock.
No scientific algorithms are copied or modified, and no merging/Pearson/per-ROI
statistics are rerun.

Complete statistics.json and native.log are saved under a fresh UUID directory.
Evidence includes status, UTC time/duration, input/provenance/log hashes, native
version/module/class hashes, fixed parameters, approval identifiers, selected
original source contributions, ROI mappings, counts, warnings and native text.
A stable baseline_fingerprint binds exact input/provenance, approval revision,
native implementation/version, parameters and counts. Random run IDs and timing
are excluded; identical execution context produces the same fingerprint.

The compact response labels global_unique_trace_id_count and roi_trace_count
separately and returns artifact references/hashes, counts, bounded warnings and
latency/response bytes. Original per-ROI native counts remain in Step 0 evidence;
this run explicitly records that separation and does not recompute/sum those counts
or claim they were incorporated. A checked baseline has scope
merged_unfiltered_tracing; generic trace_stats on a registered path alone does not
supply this evidence contract.

## Tests

| Suite | Passed | Failed | Skipped | Duration |
|---|---:|---:|---:|---:|
| Trace server and Step 0 workflow | 242 | 0 | 1 | 65.98 s |
| Report server | 7 | 0 | 0 | 1.11 s |
| Total | **249** | **0** | **1** | **67.09 s** |

Includes 22 new baseline checks: direct native count/text equivalence, stable
fingerprint and fresh run IDs, source/metadata/approval references, unchanged
scientific artifacts, missing/modified merge/provenance, stale/rejected approval,
changed collection sources, invalid run IDs, unsafe output placement, symlinked
merge logs, rehashed but inconsistent selection/ROI mapping/row count/phase/
ROI-Trace_ID count, and changes during execution to approval, merge ECSV,
provenance, source or log preventing successful publication. Native failure tests
verify saved ERROR status/version/warnings/transcript without a successful baseline.
A real stdio MCP test covers discovery, input/output schema validation, malformed
arguments and one-call compact execution.

The repeated-ID synthetic fixture deliberately has one global Trace_ID across two
output ROIs: native global count is 1 while ROI/Trace_ID count is 2. The tool preserves
that distinction and does not relabel IDs or invent allele/chromosome counts.
Synthetic decisions authorize temporary test fixtures only, never actual experiments.

The one skip is the existing optional test requiring configured CHROMATIN_TRACE_ECSV.
Existing asyncio_mode configuration, native constant-input Pearson and All-NaN
warnings remain. Skill validation passed. The unrelated plugin-packaging and
optional Agents SDK suites were not rerun. No claim is made that live agent behavior
or provider-backed orchestration was tested.

## Reference experiment and integrity

Reused the existing saved ROI 092/093 reference trace merge
c841d63159b84837bd208bfeebf79dd9; did not rerun trace_merge or localization_merge.
The real saved manual approval revision was
3f8780a346424ea1b3d16c05f8868c3c, from MCP_HOST_ELICITATION. No decision was requested,
generated, simulated or modified. This is the existing reference-copy experiment
approval, not authorization for a different experiment/store.

| Statistic | Checked baseline |
|---|---:|
| Merged tracing rows | 81,196 |
| Unique output ROIs | 2 |
| Globally unique Trace_ID values | 12,609 |
| Distinct output ROI/Trace_ID combinations | 12,609 |
| Unique observed barcodes | 29 |

All three native counts match independent direct native execution; row and pair
counts match verified merge provenance. These are descriptive counts, not scientific
acceptance thresholds. Equality between global-ID and ROI-ID-pair counts in this
reference does not imply they are interchangeable for other experiments.

Merged ECSV SHA-256:
fe57ee6f85b022bae9ec8357753ae06854e038359a7305537d7d0f2fe4e2162a

Provenance SHA-256:
84972873deb1ddbcb037e6e7f10ce940e27ca655a432dcf6c3442e1709872905

Baseline fingerprint:
d972eed35719299b5314895837d400b3bd170031365d09fe0adc9cf0e216d21e

Integrity checks confirmed unchanged approved collection inputs/manifests, original
reference ECSV inputs, corresponding original Ressources ECSV files, Pearson
artifacts and saved approval, trace/localization merged artifacts, and native
Python source files. This is scoped file-hash verification, not a scan of all raw
images or unrelated experiment files.

## Performance and provider usage

One direct native trial versus one real stdio baseline call:

| Measurement | Result |
|---|---:|
| Direct native trace_stats | 0.282 s |
| MCP call latency | 1.059 s |
| Server baseline execution | 1.033 s |
| Server startup, separate | 1.464 s |
| Scientific MCP tool calls | 1 |
| Discovery requests | 1 |
| Structured JSON response | 1,364 bytes |
| Serialized MCP result | 3,135 bytes |

Native timing excludes provenance/approval checks, snapshots, contribution
verification and evidence writing. A single trial is not a performance distribution.
Serialized result bytes include text/structured duplication but exclude JSON-RPC
framing. Complete source contributions, native text and tables are not sent in the
compact result.

No LLM/provider requests were made. Actual model, input/output/total/cached/reasoning
tokens and cost remain null/unavailable. Autonomous-agent validation remains
PENDING_NOT_RUN; response bytes are not estimated or actual model tokens.

## Limitations and scope boundaries

- Native trace_stats supplies only three counts and text: no figures, distributions,
  SNR/coverage metrics or filtering statistics are invented.
- Global Trace_ID and ROI/Trace_ID combination counts describe identifiers/nuclei,
  not resolved chromosomes or alleles. Native algorithms/grouping are unchanged.
- Original per-ROI Step 0 results remain separate. Their checksum linkage belongs
  to the future comprehensive report, not an implicit sum or rerun in this milestone.
- Baseline verification uses approved collected snapshots; original raw paths are
  collection-time provenance. No Spot_ID/Buid linkage coverage is certified.
- Current approval must still match the recorded merge revision and evidence.
  A changed/reissued approval or backend may require renewed scientific processing
  or review, rather than silently blessing an old artifact.
- Native/runtime or final evidence failures after verified input scope save ERROR
  evidence with available log/version/warnings and no successful response counts or
  fingerprint. Early unverifiable inputs/unsafe destinations return ERROR without
  writing evidence. Failed execution is never a successful baseline.
- Trusted, server-managed artifact stores and fixed backend versions are assumed.
  Hashes/locks do not isolate another process with unrestricted OS write access.
  Local Astropy loading and verification are bounded by existing input-byte/file
  limits, not OS CPU/memory quotas.
- No localization statistics, analyzers, comprehensive reporting, cross-server tools
  or filtering were implemented or invoked. The existing report server is unchanged.

## Files, configuration and evidence

Added merged_statistics.py, tests/test_merged_statistics.py,
benchmarks/benchmark_merged_statistics.py, references/merged-trace-statistics.md,
and this report. Updated registration/discovery, the existing Step 0 discovery
count, the shared adapter's optional transcript parameter, trace_merge's additive
checksum result, configuration example, skill, AGENTS, READMEs and tool/roadmap
references. Existing Step 0/scientific approval/collection/Pearson/localization merge
logic and existing server functions remain unchanged.

Configure CHROMATIN_MERGED_STATS_OUTPUT_DIR outside original and evidence stores;
see references/merged-trace-statistics.md for interface, limits and reproducibility.
Restart the MCP connection to discover merged_trace_stats. No existing tool names
or public trace_stats arguments/result fields were removed.

Local machine-readable evidence, relative to the amel workspace:

- implementation/step1c-statistics/trace-step0.xml and report.xml: exact regressions.
- implementation/step1c-statistics/scope-integrity.json: unchanged implementations
  and AST proof that trace_merge differs only by the additive response checksum.
- acceptance/step1c_merged_statistics_2026-10-22/original-integrity.json: original,
  reference, native and localization-artifact hashes.
- acceptance/step1c_merged_statistics_2026-10-22/reference-benchmark/benchmark.json:
  direct native equivalence, approval/source hashes, timings, bytes and usage nulls.
- Same benchmark directory: direct-native.txt, mcp-response.json and full baseline
  under mcp/4bd1e131d695423589525e9d3f134a7b/ (statistics.json, native.log).

## Next stage — not implemented

After owner approval, native trace_analyzer and localization_analyzer must run on
their respective merged, unfiltered inputs. Only after both analyzers should
chromatin-report-mcp compose the comprehensive pre-filtering report incorporating
Step 0/per-ROI stats, Pearson/human approval, both merges/provenance, this merged
baseline, and analyzer statistics/warnings/figure references. Filtering follows
that report as a separate decision. Stop here for owner review.
