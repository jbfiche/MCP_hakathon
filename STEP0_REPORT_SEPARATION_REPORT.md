# Step 0 validation/report separation — implementation and acceptance

Date: 2026-10-16. Scope: scientific validation and document ownership only.
No Step 1 functionality or Traceratops scientific algorithm was implemented or changed.

## Implementation

- Trace keeps all directory/ECSV/ROI/BED/barcode checks, statuses and structured
  evidence. Its internal persistence function is now `save_validation_result`.
  It writes `summary.json` and `details.json`, not Markdown.
- Report owns the moved `human_report()` formatter in `step0_reports.py` and the
  genuine `generate_data_quality_report` MCP tool. It supports Markdown and HTML,
  preserves the saved validation outcome, and lists every persisted finding,
  including warnings, errors and unavailable-reference/incomplete findings.
- Trace's old summary-only tool is renamed `get_validation_summary`. No duplicate
  old-name tool remains in the trace server. Existing comparison writer/PDF APIs
  and trace validation inputs/scientific result fields are unchanged.
- Validation returns a run ID and SHA-256 of the exact saved evidence bytes. The
  report tool takes those two values, never full JSON or arbitrary file paths.
  Its administrator must configure `CHROMATIN_VALIDATION_INPUT_DIR` to the trace
  result directory. It reads only that run's bounded regular `details.json` via
  Linux no-follow file/directory handles and verifies the checksum and contract.
- Report output is restricted to outside validation evidence and experiment inputs.
  The report code opens source evidence read-only, never opens ECSV inputs and
  never imports the trace package or Traceratops. A read-only shared-results mount
  is recommended for process-level isolation; this change does not create an OS
  sandbox against other same-user programs.
- The skill, repository instructions, interface reference, setup examples and
  client benchmarks now distinguish trace validation from report writing. Both
  agent configurations expose the same single report writer. Their trial references,
  eight-call limit and byte limits are shared across both server connections.

## Client migration

```text
trace.run_experiment_validation(...) -> run_id, validation_sha256, compact findings
report.generate_data_quality_report(validation_run_id=run_id,
                                    validation_sha256=validation_sha256)
```

To retrieve cached numerical evidence, call trace `get_validation_summary` or
`read_validation_details`. Do not rerun scientific validation merely to format it.
`report_path` remains a legacy alias of the JSON `summary_path`. Trace no longer
returns `human_report_path` or automatically creates `report.md`; use the `path`
returned by the report tool. Old schema-v1 snapshots remain renderable with their
checksum from the new summary getter. A restart/tool rediscovery is necessary for
clients already running the old server processes. The two processes need the same
local filesystem or shared mount; unrelated remote filesystems are not supported.
The existing comparison report/PDF callers need no changes. Step 0 PDF support was
not added; the moved format is Markdown, with existing HTML rendering reused.

## Exact test results

- Combined trace + report + new workflow suite: **89 passed, 0 failed, 1 skipped**,
  7.35 s. This comprises trace 62 passed/1 skipped, existing report 7 passed, and
  new cross-server workflow 20 passed. Step 0 validator/benchmark subset: 37 passed.
- Optional real-table Traceratops compatibility check: **1 passed, 5 deselected**,
  1.71 s, run separately against a read-only scientific copy. This exercises the
  test skipped for lack of a configured dataset in the clean combined run.
- Agent-harness suite: **38 passed, 0 failed, 0 skipped**, 14.85 s. Scripted SDK
  doubles exercise both real subprocess servers; these are NOT live model trials.
- Offline agent benchmark: **15/15 independent deterministic/MCP comparisons**,
  original data and all five read-only copies unchanged; zero provider requests.
- Historical Step 0 acceptance driver, adapted only for renamed retrieval and
  read-only-copy paths: **21/21 real-table oracle checks**, **10/10 damaged-fixture
  outcomes**, **9/9 negative requests rejected**, **19/19 trace tool schemas valid**,
  zero downstream-scientific tripwire attempts. Historical natural-language routes
  in this driver remain scripted transport controls, not autonomy evidence.
- The report workflow tests cover PASS/FAIL/ERROR/INCOMPLETE, warning-only missing
  barcodes, full finding preservation, Markdown/HTML, cached summaries, deleted
  source tables, source-byte preservation, actual two-process stdio, and rejection
  of traversal/missing runs, checksum changes, symlink runs/files, missing shared
  configuration, oversized evidence, corrupt/unsupported/inconsistent snapshots,
  and output directories inside source/evidence trees.
- Before/after comparison: **15/15 scientific snapshots identical** across five
  cases and three repeats, excluding only the persistence summary envelope.
  Every post-refactor snapshot remained byte-identical after report generation.
- Source audit: **18/18 validator class/function ASTs unchanged**, including policy,
  discovery, all scientific checks, evaluation and summary status/count logic.
  The pre-existing trace `server.py` is byte-identical. Traceratops is untouched.
- Skill validation: passed.

The broader pre-existing `tests/test_plugin_structure.py` check fails because it
cannot find a plugin manifest when resolving the repository root. The same failure
was reproduced in the original repository and the staged refactor. It was not
changed or counted as passing. The test environment also reports the existing
All-NaN matrix warning and a missing pytest-asyncio configuration-plugin warning;
these are recorded, not fixed as part of reporting. Existing regression tests may
invoke scientific functions on toy fixtures; no benchmark workflow invoked Step 1.

## Scientific findings and integrity

The real selected-table copy still yields INCOMPLETE: two ROIs, two trace tables,
two localization tables, 184,357 selected records. Authoritative expected real
acquisition ROI/barcode lists remain unavailable. Missing observations are warnings
under the default policy; the synthetic missing-barcode case remains PASS with its
warning. Neither report writing nor a warning-only PASS approves scientific merging.

All 1,394 original regular files (10,188,096,952 bytes), plus 61 symlink records,
match the pre-refactor fingerprint. Scientific workflows used read-only copies,
not the original experiment directory. No original scientific data was modified.
Previously documented validator limitations remain: assembly/coordinate-unit
annotations are recorded rather than validated, the full-validation flag is phase
based, the trace output contract is permissive, and some catalog tests depend on
ambient default-dataset configuration. Reporting does not conceal or fix those gaps.

## Performance and actual model usage

Three independent subprocess connections per condition, five fixture cases.
Each row below is the mean of three SDK tool-call timings; process startup is
excluded. The post-refactor total is validation plus report writing. Bytes are
canonical UTF-8 MCP CallToolResult serialization, including text/structured
content duplication and excluding JSON-RPC framing; they are not token counts.
Absolute artifact-path lengths contribute to these local byte measurements.

| Case | Calls before → after | Bytes before → after | Tool seconds before → after |
|---|---:|---:|---:|
| complete | 1 → 2 | 3186 → 4565 | 0.057362 → 0.065015 |
| invalid_ecsv | 1 → 2 | 3884 → 5265 | 0.006037 → 0.008156 |
| missing_barcode | 1 → 2 | 3657 → 5036 | 0.007145 → 0.009198 |
| missing_file | 1 → 2 | 3877 → 5256 | 0.006609 → 0.008604 |
| real_selected_copy | 1 → 2 | 4066 → 5457 | 0.888921 → 0.889352 |

Validation-only requests still use **one call** and no document rendering. For the
real copy, the validation response changed from 4,066 to 4,239 bytes because the
reference/checksum fields replace the old document-path field. Requested reports
add one bounded artifact-metadata response; the complete evidence/report is never
sent through the LLM. An extra report-tool/model turn may be required for a report
request. These timings do not establish a speed improvement or cold-start cost.

**Actual provider input/output/cached/reasoning/total tokens, live autonomous
accuracy, provider latency and cost: unavailable.** No API credentials were
configured; zero live agent trials were run. Offline SDK doubles and response bytes
are not substituted for actual model usage. No claim of token savings is made.

## Outcome and remaining action

The responsibility split is implemented and passes the functional/Step 0 acceptance
checks above. The existing packaging-check failure and scientific limitations remain
explicit. Configure the shared results directory on both server deployments and
restart/reconnect clients to discover the renamed/moved tool. Live autonomous A/B
measurements remain pending credentials. Stop here: no Step 1 work is authorized
by this reporting refactor.
