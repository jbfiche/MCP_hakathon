# Step 1a.3 — human scientific approval gate

The approval milestone added `review_pearson_approval` and a private decision
record. The review tool itself never merges anything. Step 1b.1 now separately
implements [approved trace merging](trace-merge.md). Existing `trace_pearsons`
responses, saved numerical artifacts, figures and QC reports are unchanged.

## User workflow and host requirement

1. Show the user the existing Pearson summary and links to its QC report/figure.
   Approval of implementation or tests is not scientific approval to merge datasets.
2. Call `review_pearson_approval` with the Pearson run ID and exact `results_sha256`.
   The default `request_decision=false` checks status without asking for a decision.
3. For a requested human decision, set `request_decision=true`. A **trusted MCP host
   with form elicitation support** displays counts and a bounded saved-comparison preview, all warnings,
   dataset indices/ROIs/files/collection IDs, the full QC report path,
   figure path and evidence fingerprint. It must forward the actual user's form
   response; never connect this callback to an LLM or an auto-accept handler.
4. The human chooses APPROVE or REJECT. Approval requires explicit comma-separated
   dataset indices, such as `0,2`. There is no implicit "all" choice. Rejection
   requires an empty selection. Declining the form means REJECTED. Cancelling is
   no decision and leaves the current status intact.
5. Return the status and selected indices to the chat, with the report path. Stop.
   No merge or analyzer runs. A single approved dataset is a scoped dataset grant;
   a future merge must separately require enough datasets to perform its operation.

```json
{
  "pearson_run_id": "32-lowercase-hex-run-id",
  "results_sha256": "64-lowercase-hex-results-json-checksum",
  "request_decision": true
}
```

Replace placeholders with the actual `trace_pearsons` result. Decision, selection,
review context and elicitation outcome are **not model-supplied tool arguments**.
The SDK resolves them through the host channel. A client without human form support
cannot issue a new decision; a fresh run remains AWAITING_APPROVAL, with an explicit
host-support message. Do not fall back to a boolean tool argument or direct Python
call claiming to be a human. Existing valid decisions can still be checked without
a UI. Unsupported-host status checks do not themselves revoke valid approvals.

This protects ordinary MCP tool calls. MCP trusts its client/host to supply genuine
human input; it cannot independently prove that a human clicked a button. A host
that fabricates elicitation answers, or an agent with unrestricted server-file
writing/Python execution as the server OS user, is outside this boundary. Use a
trusted human-facing host and restrict the agent's filesystem/execution access in
that deployment. The protocol tests use scripted host responses and do not prove
a live end-to-end human UI or autonomous-model deployment works.

## Evidence binding and status

The three statuses are **AWAITING_APPROVAL**, **APPROVED**, and **REJECTED**.
Missing, corrupt, changed or unavailable evidence fails closed; no successful
downstream authorization can be obtained. Invalid argument syntax produces a schema
error. An invalid/missing saved run produces awaiting status plus error evidence.

Each decision records:

- Exact Pearson run ID, `results.json` SHA-256 and saved Pearson parameters.
- QC report path/SHA-256 and native figure/matrix SHA-256 values.
- Every referenced collection run ID and manifest SHA-256.
- Every collected dataset's path, filename, index, ROI, rows and SHA-256.
- Explicit selected indices, corresponding file identities/hashes, and selected
  collection references/hashes; timestamp, revision and host-elicitation source.
- Native Pearson implementation hash and a canonical full-evidence fingerprint.

All Pearson inputs are checked, even unselected datasets: the reviewed correlation
results were computed using those inputs. The gate verifies manifest roles,
destination identity and correspondence with the saved Pearson dataset order. It
hashes bounded regular files without following file/run symlinks, but does not
recalculate Pearson correlations or parse ECSV tables again. A changed installed
Pearson implementation also requires fresh QC.

Every gate check verifies current evidence. Changed evidence clears effective
approval/selection and persists AWAITING_APPROVAL. A changed report/figure with
unchanged results requires fresh review; changed JSON needs its new exact checksum.
Decisions are revalidated after the host responds. Changed evidence or concurrent
state changes make the review stale. Restoring old files after an observed
invalidation does not restore the old decision automatically. Status is derived on
checking; the on-disk record is not a filesystem watcher and must not be consumed
as a standalone authorization token.

State lives in `<CHROMATIN_PEARSON_OUTPUT_DIR>/.scientific-approvals/<run_id>.json`,
using the Pearson directory's existing fallback when that variable is absent.
The private directory must have mode 0700, records/locks use 0600, and writes are
atomic under a per-run cross-process lock. No new output directory setting is
needed. Evidence is left intact. The current record preserves previous status on
invalidation; this is a minimal state store, not a tamper-proof historical audit
ledger. Corrupt/unreadable state produces an error and cannot authorize processing.
The implementation uses the existing POSIX/Linux runtime and validated MCP SDK 2.3.

`require_scientific_approval(...)` is an internal fail-closed check for future
workflow integration. It requires current approval, the exact selected indices
and matching saved Pearson parameters. It is not an MCP tool and cannot create a
decision. Step 1b.1 `trace_merge` calls this check and rechecks evidence under the decision
lock before publication. It has a fixed native merge policy, with no configurable
scientific parameters. Future tunable policies must bind additional parameters.
No enforcement claim for unrelated legacy tools is made.

## Scientific caveats and retrieval audit

The existing QC report already states that native Pearson keeps the last row for
repeated trace/barcode groups without allele separation, and reports the number of
affected groups. Trace_ID identifies a nucleus, not necessarily one chromosome.
Those warnings are displayed in the human review form unchanged. The form includes
at most ten comparison previews; the researcher is instructed to open the complete
saved QC report and figure before deciding. Neither the full report text nor a full
matrix is embedded in the form. See [reporting layout](pearson-reporting.md). Native plots have
a fixed 0–1 range; negative coefficients remain in numerical data. No scientific
acceptance threshold is invented, and a high correlation does not approve merging.

There is **no existing MCP tool for selected numerical retrieval from a saved
Pearson run**. `read_validation_details` and `get_validation_summary` read Step 0
artifacts only; `trace_pearsons` runs new QC and previews at most ten comparisons.
The complete saved JSON/NPY still contains the numerical evidence. The gate displays
saved comparisons to the human, but returns only status/selection/evidence paths
to the agent. Paged/selected Pearson numerical retrieval is a **future enhancement**,
not implemented here. Do not rerun science solely to retrieve saved numbers or send
full matrices into the model by default.

Provider-backed agent selection, actual token usage and a live human-facing host
trial remain pending. Protocol fixture responses and response bytes are not real
human consent, autonomous validation or measured model tokens.


Step 1b.2 now reuses this gate for the approved **tracing source ROI selection**.
Localization bytes absent from Pearson evidence are checked and recorded separately
for each merge execution; they are not represented as human-reviewed bytes. See
[localization authorization and source association](localization-merge.md).
