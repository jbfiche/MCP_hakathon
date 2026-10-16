# Step 0 single-call reporting restoration

Date: 2026-10-16.

## Changes

- `chromatin-trace-mcp` now writes JSON evidence, Markdown and HTML Data Quality
  Reports within the same `run_experiment_validation` or `validate_ecsv_tables`
  invocation. It returns `human_report_path` and `html_report_path` without sending
  report contents through the model.
- Presentation lives in the pure `step0_reporting.py` module. Its formatter was
  moved from the report package, preserving all findings, missing barcode details
  and PASS/FAIL/ERROR/INCOMPLETE statuses. Both formats share one Markdown source.
- The obsolete Step 0-only report-server endpoint/module was removed to avoid
  duplicate ownership and a second process. Every existing richer comparison/PDF
  function and class is unchanged, verified by AST comparison and regression tests.
- `get_validation_summary` remains the accurate cached-retrieval name. Evidence
  checksums and existing JSON aliases are preserved. JSON is saved before document
  rendering; renderer failure cannot erase the scientific snapshot.
- SKILL.md, repository instructions, references, examples and agent harness now
  use the single trace-server workflow. No shared report-input directory is needed.

## Tests

- Full trace/report/workflow suite: **79 passed, 0 failed, 1 skipped**, 8.61 seconds.
  This includes the original trace suite (62 passed/1 skipped), all seven richer
  reporting tests, and ten single-call reporting checks. The optional real-data
  compatibility test was not enabled in this clean suite; real data was checked
  separately through the MCP workflow below.
- Offline SDK harness: **37 passed, 0 failed, 0 skipped**, 13.54 seconds. Real stdio
  test doubles verify both report formats from one invocation for configurations
  A and B. These tests are not autonomous model runs.
- Reference-copy stdio verification: **15/15 runs matched independently established
  counts/status**, five scientific/synthetic cases with three repeats. Each run
  generated both report files with exactly **one MCP call**. **15/15 complete
  scientific snapshots matched** the previous two-server implementation, excluding
  only the artifact-summary envelope, and remained unchanged by formatting.
- **18 scientific validator ASTs unchanged**; Traceratops algorithms untouched.
- Skill validation passed. Source inputs were read-only copies; no original data
  was used as an MCP write destination. Tests confirm unchanged input bytes and no
  duplicate ECSV reads for formatting.

Cross-server artifact-reader tests were retired with that removed interface and
replaced by single-call, format/finding preservation, pure-renderer, scientific
snapshot preservation and real stdio tests. The unrelated plugin-packaging failure
reported previously was not changed or counted as passing. Existing All-NaN and
pytest-asyncio configuration warnings remain. Previously documented scientific
validation limitations are outside this reporting-only change.

## Call count and measurements

The read-only real reference copy used one tool call, 5,059 serialized
MCP result bytes and mean tool duration 0.893006 seconds across three
trials. The preceding two-server run used two calls and 5,457 bytes. Paths affect
serialized size, and timing differences do not establish a speed improvement.
The restored workflow preserves both report formats and needs no second model-tool
round trip. Actual provider tokens were unavailable; no live model requests were
made and no token savings are claimed.

## Usage

Call trace `run_experiment_validation` once, then open either returned document
path. For cached paths/results use `get_validation_summary`; do not revalidate for
presentation. Restart/reconnect existing clients to refresh server code and tools.
The richer report-server comparison/PDF interfaces remain available as before.
Step 1 was not implemented.
