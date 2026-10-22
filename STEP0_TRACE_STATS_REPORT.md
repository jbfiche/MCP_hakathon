# Step 0 — native per-ROI trace_stats enhancement

Completed: 22 October 2026. Tests and reference measurements were recorded on
21 October; completion resumed after an interruption. Scope: Step 0 statistics
and roadmap documentation only. No analyzer, comprehensive report, filtering,
native algorithm or scientific approval changes.

## Implementation

Both existing Step 0 table/full validation calls now run native Traceratops
trace_stats for each selected, valid, within-limit individual ROI tracing ECSV.
They never run it on localization tables. Missing, ambiguous, invalid or over-limit
tracing inputs have explicit NOT_RUN statistics records; native failures or changed
input hashes produce ERROR statistics. Processing of other ROIs continues.

The existing public trace_stats(dataset_name) tool and Step 0 share a single native
adapter. Public arguments/result fields remain compatible. The adapter delegates
all statistical counting to native compute_trace_statistics, captures stdout for
stdio safety, and extracts its three integers: unique ROI values, globally unique
Trace_ID values, and unique barcode values. No statistical formula is duplicated.

Step 0 retains its existing file, schema, ROI, barcode and BED/metadata validation.
Those validation routines and their findings/status logic are unchanged. Native
statistics availability is reported separately as COMPLETE/INCOMPLETE/NOT_RUN;
computed counts do not establish scientific acceptance or replace validation.
Native trace_stats produces no figure, distribution or saved numerical artifact.

Native execution uses private read-only snapshots checked against the already
validated tracing ECSV SHA-256. Source hashes are checked again after execution.
Evidence records source experiment/ROI/path/hash, native version/module hash,
counts, terminal text, warnings and stderr. Temporary paths in native terminal text
are mapped to the verified original source path; counts are unchanged. Original
scientific inputs are never written.

Markdown/HTML reports include each ROI's native counts or unavailable reason, plus
native warnings even when execution fails. Full records remain in checksum-identified
details.json and existing cached ROI detail retrieval. Default MCP responses add
statistics coverage counts only, preserving one validation/report call without
per-ROI agent calls, catalog registrations or a second reporting server.

## Tests

| Suite | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Trace server and Step 0 workflow regressions | 220 | 0 | 1 |
| Report server regressions | 7 | 0 | 0 |
| Total | **227** | **0** | **1** |

The trace suite took 57.09 s and report suite 1.12 s. Includes 15 new statistics
checks covering direct-native equivalence, per-ROI identity/hash provenance,
unchanged scientific inputs/catalog, missing/ambiguous/invalid/over-limit inputs,
native SystemExit/format errors, source mutation, native warnings, partial-check
restrictions, public-tool compatibility and real stdio single-call validation with
cached retrieval. No downstream processing is required for this workflow.

A subsequent presentation-only correction made failed-run native warnings visible
in the human report. The affected statistics/report tests then passed: **22 passed,
0 failed, 3 deselected in 1.84 s**. The three deselections exclude stdio cases already
covered by the full regression and reference runs; they are not additional skips
in the main result. The subsequent reference test also used the final formatter
through real stdio.

The one main-suite skip is the existing optional test requiring a configured
CHROMATIN_TRACE_ECSV. Existing asyncio_mode, native constant-input Pearson and
All-NaN warnings remain. Skill validation passed. Unrelated plugin packaging and
optional Agents SDK suites were not rerun; no claim is made about fixing them.

## Reference experiment — original ROI tracing tables

Compared direct native execution with the enhanced Step 0 MCP call on the protected
ROI 092/093 reference copies:

| Original ROI | Native unique ROIs | Native unique Trace_ID values | Native unique barcodes |
|---|---:|---:|---:|
| 092 | 1 | 6,776 | 29 |
| 093 | 1 | 5,833 | 29 |

Every count agrees with direct native execution. Existing validation findings and
ROI table evidence are identical to the pre-enhancement implementation, excluding
the added native-statistics records. Scientific reference inputs, corresponding
original ECSV files and native source hashes remain unchanged, including a fresh
check after resuming on 22 October.

No authoritative expected barcode/BED policy was supplied in this reference run:
validation remains INCOMPLETE, while statistics coverage is COMPLETE. This is
intentional and demonstrates that successful descriptive statistics cannot promote
incomplete validation to PASS. Trace_ID describes nuclei, not necessarily single
chromosomes/alleles; global IDs may repeat across ROIs and cannot simply be summed
and interpreted as a merged-experiment trace count.

## Performance and actual usage

One real stdio call per mode, same inputs/native backend:

| Measurement | Previous Step 0 | Enhanced Step 0 |
|---|---:|---:|
| Validation/report MCP calls | 1 | 1 |
| Tool-call latency | 0.937 s | 1.246 s |
| Structured response | 2,168 bytes | 2,272 bytes |
| Serialized MCP result | 4,980 bytes | 5,218 bytes |
| Server startup, separate | 1.455 s | 1.449 s |

The direct native statistics baseline for both ROI files took 0.304 s. Additional
local snapshot/read/verification work is expected; the agent does not need extra
per-ROI tool calls. These are single trials, not a performance distribution.
Serialized MCP result sizes exclude JSON-RPC framing and include text/structured
duplication. Complete native text/tables stay outside default responses.

No LLM/provider call was made. Actual input/output/total/cached/reasoning tokens,
model identifier, cost and autonomous-agent validation remain unavailable/pending.
Response bytes are not estimated or actual model tokens.

## Clarified roadmap — not implemented here

After separately approved merged-trace statistics, run native trace_analyzer on
merged unfiltered tracing data and localization_analyzer on the corresponding
merged unfiltered localization data, with scientific execution in trace MCP.
Neither native analyzer requires prior filtering, but their input schemas, native
limitations and output availability must be verified in their own milestones.

The final comprehensive human-readable QC report belongs in chromatin-report-mcp
**after both analyzers and before filtering**. It must combine Step 0 validation
and original per-ROI stats; Pearson QC and human approval; both merges, source ROI
mappings and provenance; merged trace_stats; both analyzers' available numerical
results, warnings and saved figure references. Preserve missing/incomplete evidence.

The report server will format validated, checksum-identified artifacts without
recalculating measurements or changing data. Do not pass full matrices, tables,
figures or reports through the LLM by default. Existing simple Step 0/Pearson reports
remain in trace. Detailed requirements, provenance gaps and separate approval
boundaries are in references/trace-stats-integration.md. No new cross-server
mechanism or comprehensive-report tool was implemented.

## Changes and evidence

Added trace_statistics.py, step0_statistics.py, tests/test_step0_statistics.py and
this report. Updated Step 0 orchestration/summary and pure report formatting; routed
the existing trace_stats wrapper through the shared adapter; adjusted the workflow
test's expected table-read count for the deliberate native snapshot reread; updated
README, tool reference, AGENTS, SKILL and Step 0/statistics roadmap references.
No tool names, public trace_stats arguments or existing result fields were removed.
The trace server still has 24 tools; the report server is unchanged.

Local evidence, relative to the amel workspace:

- implementation/step0-roi-stats/trace-step0.xml and report.xml: regression results.
- implementation/step0-roi-stats/format-regression.xml: final report correction checks.
- implementation/step0-roi-stats/scope-integrity.json: unchanged validation routines,
  scientific approval, collection/Pearson/merge code and report-server implementation.
- acceptance/step0_roi_statistics_2026-10-21/benchmark.json: native counts, before/after
  latency/bytes, explicit provider-usage nulls and protected-file hashes.
- Same acceptance directory: direct native terminal outputs and baseline/enhanced
  JSON/Markdown/HTML reports. Enhanced validation run:
  bda0205b82af46ad986e11df8c565e24.

Stop for owner review. Merged statistics, analyzers, comprehensive reporting and
filtering require separate approval and were not implemented or invoked here.
