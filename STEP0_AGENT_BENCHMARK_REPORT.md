# Step 0 autonomous agent harness — implementation report

Date: 2026-10-16. Scope: Step 0 evaluation only. Step 1 was not implemented.

## Result

**Offline implementation validated; live autonomous evaluation NOT RUN.** No
`OPENAI_API_KEY` was configured in the execution environment. Actual model tokens,
autonomous accuracy, provider latency and cost are unavailable. The script includes
a real provider execution path, but no claim is made that this unexercised path
passed against a live model. No A/B agent token-saving conclusion is supported yet.

## Implementation

Added `chromatin-trace-mcp/benchmarks/agent_step0/` containing:

- `benchmark_agent.py`: OpenAI Agents SDK client, fresh conversations, dynamic MCP
  discovery, both tool configurations, scoped dispatch, execution limits, telemetry,
  repeated live-trial scheduling and evidence reports.
- `reference.py`: independent stdlib CSV oracle, blinded synthetic fixtures,
  read-only scientific-table copying and input fingerprints.
- `test_agent_benchmark.py`: unit and real SDK/stdio integration tests.
- `requirements.lock.txt`, `config.example.json`, `README.md`: isolated pinned
  dependencies and exact offline/live setup instructions.

Added `references/step0-agent-benchmarking.md` and updated the existing diagnosis
skill with a short link and evidence requirements. No scientific server source,
Traceratops algorithm or global tool registration was modified for this task.
Existing owner changes and the historical acceptance report were preserved.

The server still uses its validated interpreter and pinned Traceratops source.
The separate agent environment uses openai-agents 0.24.0, openai 3.31.0 and mcp 2.3.0.
No Traceratops scientific function is needed for Step 0: the deterministic baseline
calls the existing validator in a separate subprocess. Existing server regression
tests exercise their pre-existing operations on test fixtures; they are not agent
workflow calls or a new scientific processing step.

## Exact checks run

- New harness suite: **35 passed, 0 failed, 0 skipped**, 9.34 s. Includes two
  parameterized SDK/stdio tests, each running two fresh scripted conversations.
  Those four conversations are protocol doubles, not autonomous model trials.
- Existing trace-server suite: **62 passed, 0 failed, 1 skipped**, 4.71 s, one
  existing All-NaN matrix warning. Optional real-dataset test was not enabled.
- Skill frontmatter validation: passed.
- Independent scientific comparisons: **15/15 passed**, **105/105 field checks**:
  five direct subprocess controls and ten actual stdio MCP controls, across five
  cases and both configurations.
- Dynamic discovery found 19 server tools. A exposed exactly six Step 0 tools;
  B exposed only `run_experiment_validation`. Fifty deliberate processing/root/
  policy violations across ten connections were rejected before dispatch.
- Unit checks additionally cover call/response budgets, invalid arguments, cached
  run scope, no inherited API keys, altered inputs, exact factual scoring and raw
  provider-usage capture using explicitly synthetic objects.
- Live autonomous trials: **0**. Five requested prompts × four synthetic cases ×
  two configurations × three repeats are recorded as **120 NOT_RUN_OFFLINE** plans.
  Real-data inclusion is opt-in and adds 30 trials at the same repeat count.

The initial sandbox stdio handshake timed out. The same local test connection
succeeded outside that sandbox with permission. This was an execution-environment
restriction, not evidence of a provider connection or live model success.

## Scientific findings and data integrity

The real experiment contains two discovered ROIs (92 and 93), two selected mask-based
trace tables, two localization tables and 184,357 selected records. The benchmark
server only saw verified read-only copies of those four selected tables, not the
original experiment directory or its complete inventory. The real result remains
**INCOMPLETE** because authoritative expected ROI/barcode design references are
unavailable. Observed coverage is not proof that all intended acquisitions exist.

Synthetic complete, missing-file, missing-barcode and invalid-ECSV cases matched
independent expected results: PASS, FAIL, PASS-with-warning and ERROR respectively.
Missing barcode 2 was localized to ROI 2's trace table. Missing localization was
localized to ROI 2. A warning-only missing-barcode case must not be described as
biological failure. No acceptance thresholds were invented.

Before/after fingerprints matched for all 1,394 original regular files
(10,188,096,952 bytes) and 61 symbolic-link records. Symlinks were not followed.
All five benchmark copies were unchanged, and copied inputs had no write bits.
Reports were written outside input trees. Only authorized copied roots were supplied
to the MCP server. All recorded benchmark dispatches were Step 0 tools.

## Limits and next action

- Agent factual answers are typed for deterministic scoring; prose remains available
  for independent human review. Typed scores cannot certify every narrative claim.
- Provider usage is captured before SDK normalization; missing fields stay null.
  Cost is null because pricing was not assumed. Usage-recorder test numbers are
  synthetic and excluded from all actual-usage totals.
- Read-only permissions and application allowlists are not a kernel sandbox against
  hostile same-user code. Stronger deployment isolation requires a restricted
  process/container with read-only mounts. This implementation does not claim that.
- Live tests default to sanitized synthetic fixtures. Real-data mode can disclose
  paths/metadata; it requires `--include-real`. Tracing and response storage are off,
  but provider retention policy still needs to be reviewed by the operator.
- The CSV oracle is specific to the reviewed ECSV 1.0 subset and generated fixtures;
  it is not a general replacement for an ECSV parser or independent biological QC.
- The next action is configuring an API key privately, choosing an accessible model
  and running the repeated live Step 0 benchmark. **Do not start trace_pearsons or
  any Step 1 implementation without explicit owner approval.**

## Recorded offline measurements

| Fixture | Mode | Status | Seconds | MCP result bytes | Oracle checks |
|---|---|---|---:|---:|---|
| complete | direct subprocess | PASS | 0.7410 | n/a | 7/7 |
| complete | A | PASS | 0.0494 | 13027 | 7/7 |
| complete | B | PASS | 0.0491 | 13023 | 7/7 |
| missing_file | direct subprocess | FAIL | 0.6459 | n/a | 7/7 |
| missing_file | A | FAIL | 0.0470 | 11590 | 7/7 |
| missing_file | B | FAIL | 0.0502 | 11586 | 7/7 |
| missing_barcode | direct subprocess | PASS | 0.6845 | n/a | 7/7 |
| missing_barcode | A | PASS | 0.0520 | 13552 | 7/7 |
| missing_barcode | B | PASS | 0.0495 | 13548 | 7/7 |
| invalid_ecsv | direct subprocess | ERROR | 0.6446 | n/a | 7/7 |
| invalid_ecsv | A | ERROR | 0.0478 | 11957 | 7/7 |
| invalid_ecsv | B | ERROR | 0.0494 | 11953 | 7/7 |
| real_selected_copy | direct subprocess | INCOMPLETE | 1.5718 | n/a | 7/7 |
| real_selected_copy | A | INCOMPLETE | 0.9168 | 20513 | 7/7 |
| real_selected_copy | B | INCOMPLETE | 0.9144 | 20509 | 7/7 |

A exposes six separate Step 0 tools. B exposes only run_experiment_validation.
Provider raw usage, per-request model ID, latency, calls/arguments and result byte sizes are retained in records.json.
Bytes are canonical serialized MCP result sizes (including structured/text duplication), not network frames or token estimates.
Cost is unavailable: no pricing assumptions are applied. Free-text answers require independent human review; typed claim scores do not certify every narrative sentence.
Real-copy scope: four selected trace/localization tables; not the full source directory inventory. No authoritative real ROI/barcode design was available.
Filesystem controls are allowlists and read-only fixture permissions, not an OS sandbox; a compromised server running as the same user is outside this protection.
Live tests default to synthetic fixtures; real metadata/paths require --include-real. SDK tracing is disabled; Responses storage is disabled. Provider retention policies still apply.
No Step 1 tools are exposed or dispatched. Step 1 has not been implemented.
