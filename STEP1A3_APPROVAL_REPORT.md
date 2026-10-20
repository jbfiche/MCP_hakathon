# Step 1a.3 — scientific approval gate

Date: 2026-10-20. Implemented and tested at the deterministic/MCP protocol level.
No merging, localization merging, downstream analyzers or Traceratops algorithm
changes. Stop before Step 1b; further development requires owner approval.

## Implementation

Added one trace MCP tool: `review_pearson_approval(pearson_run_id,
results_sha256, request_decision=false)`. There are now 22 trace tools.
Default calls verify evidence and return **AWAITING_APPROVAL**, **APPROVED** or
**REJECTED**. `request_decision=true` asks a trusted, human-facing MCP host to show
the existing QC report, saved numerical comparisons, dataset choices and figure
path. The human explicitly chooses APPROVE/REJECT and selected indices. No decision
or selection is accepted as an agent tool argument. There is no implicit approval
of all datasets. Declining rejects; cancelling makes no decision.

A persisted decision binds the exact Pearson run/results SHA-256, report path/hash,
figure and matrix hashes, all collection manifests/hashes, collected dataset
identities/hashes, saved parameters, native implementation hash and explicit
selected files/manifest references. Every check revalidates evidence. Changes clear
the effective approval and selection. Fresh reviews are required after invalidation;
restoring old evidence does not resurrect a previously invalidated decision.
Checks after the form response also reject stale evidence/concurrent decisions.

Private state uses mode-0700 `.scientific-approvals` beside the Pearson runs,
mode-0600 records/locks, atomic writes and cross-process locking. An internal
`require_scientific_approval` check rejects unapproved/rejected/stale evidence,
inconsistent saved selections, and different requested selections or saved Pearson
parameters. It performs no scientific processing. Future merge code must integrate
this check and its own execution-time input integrity checks; none is implemented.

The host is a necessary trust boundary: it must forward the actual human's form
response and must never auto-answer via an LLM. Clients without form support cannot
issue new approval. The mechanism blocks ordinary agent tool arguments; it cannot
prove human identity against a malicious host or an agent with unrestricted
server-file writing/Python execution as the server OS user. This limitation is
explicit in the setup instructions. Existing legacy tools are not retrofitted with
a global processing gate.

Changed/added files: `approval.py`, trace server registration and discovery test,
`tests/test_approval.py`, `references/scientific-approval.md`, trace README,
`MCP_TOOL_REFERENCE.md`, `AGENTS.md`, the existing diagnosis `SKILL.md`, and this
report. The skill passed its validator. Scientific approval is explicitly distinct
from approval of implementation/tests.

## Verification

Final combined trace/report/Step 0 workflow suite: **155 passed, 0 failed,
1 skipped in 31.66 seconds**, including **20 new approval checks**. Four cases use
real stdio client/server exchanges with scripted host responses: approval with a
subset, rejection, decline and cancellation. These protocol fixtures are not live
human consent or autonomous-agent validation.

Tests cover evidence/file integrity, selection and manifest binding, approved and
rejected states, missing/invalid run IDs, changed reports/parameters/manifests/
collected files/figures/matrices, changed checksums, stale concurrent reviews,
invalid/implicit selections, forged model decision/context arguments, an unsupported
host, response schemas, and an inconsistent saved selection attempting to bypass
the gate. Existing native Pearson accuracy and Step 0 tests pass in the same run.

The skipped test is the pre-existing optional real-trace compatibility test, which
requires `CHROMATIN_TRACE_ECSV`. The reference Pearson artifacts were checked
separately below. Expected native constant-input/All-NaN warnings and the existing
pytest `asyncio_mode` warning remain. The initial sandboxed client run stalled and
was interrupted; authoritative protocol/regression results were obtained outside
that sandbox. The unrelated plugin-packaging and separate SDK suites were not
rerun; this is not a claim that every repository test was run.

## Saved reference run and performance

The existing reference Pearson run is **AWAITING_APPROVAL**. No scientific approval
was issued. It remains ROI 92 versus ROI 93, r = **0.8691053986549377** over **406**
shared barcode pairs. Existing QC warnings are already clear: 1,330 and 603 repeated
trace/barcode groups; native last-row handling without allele separation; nucleus-
level Trace_ID; fixed 0–1 figure color scale. The gate displays those warnings;
there was no need to rewrite the approved QC report.

The real stdio check used a host without a form callback and correctly left the
run awaiting approval. One tool call plus separate discovery took **0.037374 s**
(tool latency), with **1.476879 s** startup measured separately. The status response
was **807 bytes** compact JSON / **1,913 bytes** serialized MCP result. This is one
status-check measurement, not a human-interaction latency distribution or a token
benchmark. Human review waiting time is not measured.

Before/after hashes show reference results, QC report, native figure/matrix/log,
collected tables and manifest unchanged; both actual original trace files still
match the approved hashes. The new decision-state files are separate from those
scientific artifacts. The `pearsons.py` implementation and original compact response
contract are unchanged, as are Step 0, collection, dependency locks, report-server
code and native Traceratops source.

**Provider requests: 0.** Autonomous-agent validation, a live human-facing host
trial and actual provider input/output/total/cached/reasoning tokens remain pending.
Usage fields are null, not estimated from response bytes. Scripted host exchanges
do not establish a real human UI works in the user's current client.

## Numerical retrieval audit and limitations

There is no existing MCP tool for selected numerical retrieval from saved Pearson
runs. `read_validation_details` and `get_validation_summary` are Step 0-only;
`trace_pearsons` creates new results. Full numerical JSON/NPY artifacts remain
available. The approval form displays saved comparisons to the human, while its
agent response contains status/selection/paths only. Paged/selected Pearson retrieval
is documented as a future enhancement; **no retrieval tool was added**, and no full
distance matrix is sent to the AI by default.

On-disk status is refreshed on gate checks, not by a file watcher. Future callers
must use the validating helper rather than trust a raw JSON status. The state store
is a minimal current-decision record, not a tamper-proof historical ledger. Limits
reuse the Pearson file/dataset bounds; checks are not OS resource isolation. Future
merge-specific parameters and execution-time races must be handled when merge code
is separately authorized. No scientific acceptance threshold was invented.

Evidence in the project workspace:
`acceptance/step1a3_approval_2026-10-20/regression-final.xml`,
`reference-check.json`, `reference-mcp-response.json`, and `source_integrity.json`.
Configuration, user flow and trust assumptions are in
[scientific approval](references/scientific-approval.md).

Step 1a.3 is ready for owner review at this tested scope. **Step 1b is not started.**
