# Step 0 acceptance report — pyHiM MCP Copilot

Date: 16 October 2026 (Europe/Monaco)

## Recommendation: NOT READY for full copilot acceptance

The file-discovery, ECSV/schema and counting functions have strong positive evidence for **supervised Step 0 inspection**. The real experiment matched all 21 independently checked fields. Supported fault cases and real MCP request/error tests behaved as expected.

Full acceptance is not established: **autonomous agent-level natural-language runs were not executed**, and no provider-reported token measurements were available. There are also demonstrated metadata-validation gaps, an inaccurate execution flag and environment-sensitive tests. These are recorded below rather than counted as successful checks. Missing token telemetry alone is not treated as a scientific failure.

No product fixes or scientific-validation changes were made during this evaluation. **Step 1 was not started on the reference experiment.**

## Scope and reproducibility

- Repository: `/home/zidoum/Repositories/MCP_traceratops/MCP_hakathon`, branch `Test`, HEAD `9afd60a2dc7dd9c693f1d370fe706a2d0466b017`.
- The existing uncommitted changes to the report formatter and its reference documentation were included in the evaluation. They were not reverted or edited.
- `./Ressources/` does not exist inside the Git checkout. The supplied reference experiment is at the sibling directory `/home/zidoum/Repositories/MCP_traceratops/Ressources` and now contains both `092` and `093`.
- Runtime: Python 3.13, MCP 2.3.0, Astropy 8.0.1, Pydantic 2.13.5, pytest 9.1.1. Existing compatible dependencies were used; the package's frozen MCP 2.2.0 environment was not installed because `uv` was unavailable.
- Traceratops: 1.0.1, source export at the lockfile's commit `261a48fe92498abcb154891fe6e5a5ca8219b610`. No backend modifications.
- Independence means a separate CSV-based counting oracle and a separate subprocess MCP client. This is not a blinded external audit by a different author. The current assistant had prior implementation context.

All evaluation scripts, logs, manifests, reports and isolated test copies are saved in:

`/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/`

[Machine-readable acceptance summary](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/acceptance_summary.json) · [Product version and hashes](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/product_state.json)

## 1. Exact automated test results

| Run | Collected/selected | Passed | Failed | Skipped | Notes |
|---|---:|---:|---:|---:|---|
| Complete trace-server suite, clean default-dataset environment | 63 | 62 | 0 | 1 | Optional real-trace test needs its environment variable |
| Step 0-specific tests within that suite | 37 | 37 | 0 | 0 | A subset of the 63, not additional tests |
| Optional real-trace test, run separately with the actual ROI 092 trace configured | 1 | 1 | 0 | 0 | Five other tests deselected by the targeted command |
| Complete report-server suite | 7 | 7 | 0 | 0 | Bundled ReportLab supplied to the existing runtime |
| Environment-sensitivity run: full trace suite with a default real trace configured globally | 63 | 60 | 3 | 0 | Three catalog/list tests fail on the extra `current` dataset |

The normal suites give **69 passed, one skipped**. The skipped check passed separately. This covers 70 distinct test cases in their documented contexts; repeated runs are not additional test cases. The environment-sensitivity run still contains three real test failures and must not be described as an all-pass run.

The three failures are:

- `test_register_list_inspect_and_read_named_dataset`
- `test_persistent_json_catalog_loads_and_compares_datasets`
- `test_registered_dataset_is_saved_and_survives_a_restart`

These tests expect only their own named datasets. With `CHROMATIN_TRACE_ECSV` set, the server also lists `current`. Their fixtures do not isolate this setting. The failures concern list expectations, not corrupted experimental data. No tests or production logic were edited to remove them.

The existing synthetic matrix test emitted one `All-NaN slice encountered` warning. The optional real trace's schema/readability check passed. Legacy tests exercised existing scientific wrappers on test fixtures; this was not a downstream run on the reference experiment.

Exact command/output and JUnit evidence:

- [Clean trace-suite log](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/trace_tests_clean.txt) · [JUnit](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/trace_tests_clean.xml)
- [Configured-environment failure log](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/trace_tests_configured_environment.txt)
- [Isolated real-trace check](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/optional_real_trace.txt)
- [Report-suite log](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/report_tests.txt)

## 2. Real experiment: what was found

- ROIs: **2 found** — `092` and `093`.
- Localization tables: **2 found** — one per ROI.
- Mask-based traces tables: **2 found** — one per ROI.
- Selected tables read successfully: **4**.

| ROI | Table | Rows | Trace_ID values | Barcode IDs observed |
|---|---|---:|---:|---:|
| 092 | Traces | 46,296 | 6,776 | 29 |
| 092 | Localization | 61,420 | Not applicable | 29 |
| 093 | Traces | 34,900 | 5,833 | 29 |
| 093 | Localization | 41,741 | Not applicable | 29 |
| Total | Four selected tables | **184,357** | Reported per ROI/table | Not summed across tables |

The filesystem contains **1,394 regular files**, including 134 ECSV files. Most ECSV files are intermediate or other-purpose outputs; they are not all selected analysis inputs. There are 61 skipped symlinks. The mask-based discovery rule excludes KD-tree tables and derived barcode indexes.

The machine-readable validation result is `INCOMPLETE`, with **0 errors, 61 warnings and 2 incomplete checks**. The warnings are skipped symlinks. The incomplete checks concern unavailable expected ROI and barcode lists. The simple human report describes the files found rather than presenting those unknown lists as missing scientific files.

No authoritative expected acquisition ROI list, associated BED, or intended probe list was supplied to this run. Consequently the observed count of 29 barcodes is not proof that every intended barcode was detected. Genome assembly, tissue and the biological meaning of barcode identifiers were not independently established.

**Data Quality Report:** [Simple report from the real experiment](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/DATA_QUALITY_REPORT.md)

[Real MCP summary and independent comparisons](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/real_experiment_result.json)

## 3. Independent scientific count check

`reference_oracle.py` does not import the MCP server, its validation helpers, its Pydantic rules or its scientific counting functions. It uses a separate filesystem walk, an explicit reviewed mask filename rule and Python's CSV reader on the observed space-delimited ECSV 1.0 files. It counts data records, ROI IDs, barcode IDs and distinct Trace_ID values directly.

All **21/21 comparisons matched**: ROI and selected-file counts, all regular-file extension counts, total selected records, exact selected paths, each table's row count, exact barcode identifier sets, exact ROI identifier sets and both trace counts. The independent expected results here describe the supplied files; they do not invent an experimental design. The reference parser is specific to the reviewed ECSV layout and is not a replacement for a general ECSV parser.

[Independent script](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/reference_oracle.py) · [Independent oracle output](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/independent_oracle.json)

## 4. Deliberately damaged copies

Only isolated copies of the real ROI 092 mask-based trace and localization tables were changed. The fixture policy explicitly expects the copied baseline's barcode set to make deletion detection testable. That synthetic test policy is not assigned to the real experiment.

| Case | Observed status | Exact warning/error code | Assessment |
|---|---|---|---|
| Untouched copy | PASS | None | Baseline accepted |
| Trace file removed | FAIL | ERROR `MISSING_TRACING` | Correct ROI 92 association |
| Localization file removed | FAIL | ERROR `MISSING_LOCALIZATION` | Correct ROI 92 association |
| Barcode 3 removed from trace rows | PASS | WARNING `MISSING_BARCODE_OBSERVATIONS` | Exact missing list `['3']`; 43,691 rows remain |
| Invalid ECSV text | ERROR | ERROR `INVALID_ECSV` | Parsing failure recorded; report saved |
| Trace ROI values changed to 999 | FAIL | ERROR `ROI_TABLE_CONFLICT` | Mismatch with directory ROI 92 detected |
| Second mask table added | FAIL | ERROR `AMBIGUOUS_TRACING` | Neither trace candidate silently selected |
| Invalid `experiment.yaml:step0` structure | ERROR | ERROR `VALIDATION_EXECUTION_ERROR` | Configuration parsing/validation failure recorded |
| Assembly changed to `DELIBERATELY_INVALID_ASSEMBLY` | PASS | None | **Not validated; metadata gap** |
| Unit changed to `DELIBERATELY_INVALID_UNIT` | PASS | None | **Not validated; metadata gap** |

The eight supported baseline/fault outcomes matched their predeclared status, severity, code, ROI and path expectations exactly. Full returned messages are preserved in the evidence. The two invalid unit/assembly probes are **not successful scientific-validity checks**: the validator recorded the bad strings but did not reject or flag them. Missing barcode observations are warnings under the default fixture policy, so their PASS status is intentional.

[Mutation definitions and independent expectations](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/mutation_manifest.json) · [Exact results/messages](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/acceptance_client_results.json) · [Invalid metadata retained in results](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/unsupported_metadata_evidence.json)

## 5. Real MCP client integration

The high-level MCP SDK Client launched a separate server process and communicated through **stdio**, rather than calling validation functions in process. Both the unmodified module entrypoint and a second process with audit-only scientific-operation tripwires connected successfully. The negotiated protocol was **2026-07-28**.

- 19 trace-server tools discovered, including all seven Step 0 tools.
- All 19 input schemas and 19 output schemas were structurally valid JSON Schema.
- 37 positive tool invocations in the acceptance driver had schema-valid arguments/results.
- 9/9 negative tests were rejected: unknown tool, absent required argument, invalid finding limit, invalid discovery mode, rule path escape, unauthorized root, invalid cached-run ID, nonexistent cached run and invalid page size.
- The same connection remained usable after the errors.
- The real experiment matched the independent oracle with and without the tripwires.

Protocol argument/unknown-tool errors returned `is_error=true`. Some execution failures instead returned a normal MCP result with `status='ERROR'` and `is_error=false`. Rejection was verified, but consumers must examine the structured status as well as the protocol error flag.

The initial sandboxed stdio connection timed out during initialization. Repeating outside the sandbox connected; the particular process restriction was not identified. A preliminary outside-sandbox probe then exposed an evaluation setup error: its allowlist included a not-yet-created fixture directory. Creating the fixture directory corrected that setup before the full run. The implementation resolves every allowlist entry strictly, so configured roots must exist.

The existing comparison-report server's seven tests passed; its own stdio deployment was not separately exercised because Step 0 runs in the trace server and writes its validation report there.

[Subprocess client/driver](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/acceptance_client.py) · [Catalog](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/tool_catalog.json) · [All calls and responses](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/mcp_calls.json)

## 6. Natural-language agent checks: partial evidence only

Six prompt fixtures were exercised through the real MCP client: ROI count, required files, missing barcodes, affected ROIs, report creation and downstream readiness. The current assistant supplied example answers using that evidence. All six examples' structured factual claims matched the independent reference facts.

However, the acceptance driver used **fixed tool routes**. It did not submit these prompts to a fresh autonomous model and observe that model selecting tools, following up or producing its final answer. Those examples therefore **do not count as six passing autonomous agent tests**. Autonomous selection accuracy, unsupported narrative claims, agent repeatability, model identifiers, per-prompt model latency and provider tokens remain **NOT MEASURED**. No provider-backed agent client/model credentials were configured.

[Prompt evidence, example answers and factual grading](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/prompt_smoke_checks.json)

## 7. Separate versus aggregate benchmark

Both approaches used the same real experiment and default rules, over the same persistent stdio connection. Three repeats per approach alternated execution order. The separate route called inspection, discovery, structure validation, ECSV validation and saved-report retrieval. The aggregate route called `run_experiment_validation` once.

| Approach | Runs | MCP calls/run | Mean response bytes/run | Mean client-observed time | Range | Oracle agreement |
|---|---:|---:|---:|---:|---|---|
| Separate calls | 3 | 5 | 21,320 | 1.099 s | 1.045–1.206 s | 21/21 fields in every run |
| Aggregate tool | 3 | 1 | 5,222 | 0.951 s | 0.871–1.030 s | 21/21 fields in every run |

In this small warm-process sample, aggregation reduced returned bytes by **75.51%** and calls from five to one. This is not a measured token saving.

Bytes mean compact UTF-8 JSON serialization of `MCP CallToolResult`, excluding the outer JSON-RPC envelope. These measurements include tool result content and structured content; they are not provider input tokens. Timing is client-observed tool/workflow latency, not model inference latency. This is a transport/validator benchmark with fixed routes and no controlled model inference.

**Actual provider-reported input/output/total/cached/reasoning tokens: unavailable. Model cost and token reduction: unavailable.** No proxy based on bytes, tokenizer estimates or synthetic usage-parser tests is presented as actual usage. Both routes preserved the observed result; the repeated field comparisons are not additional independent datasets. Three repeats on two ROIs do not establish large-experiment scaling or statistical significance.

[Raw benchmark records](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/acceptance_client_results.json) · [Benchmark summary](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/acceptance_summary.json)

## 8. Original-data integrity and Step 1 boundary

Before/after streamed SHA-256 fingerprints matched for **all 1,394 regular files**, totalling **10,188,096,952 bytes**. File sizes and modification times also matched. All 61 symlink paths and target strings were unchanged. No directories were excluded from these regular-file fingerprints; symlink targets outside the root were not followed or fingerprinted.

The tripwire process blocked native collection, Pearson, merge and analyzer functions, as well as existing scientific-wrapper aliases. **Zero such calls were attempted during guarded Step 0 runs.** All positive acceptance invocations selected Step 0 tools. Its output directory contains JSON, JSONL and Markdown only. The unmodified entrypoint and guarded process returned matching real-data counts. Original product Python file hashes were unchanged by the evaluation.

Legacy automated tests separately ran scientific wrappers on their test fixtures. The real experiment was used for inspection, validation, independent counting and byte fingerprinting only. No automatic experimental collection, merging, Pearson QC, analyzer pipeline or Step 1 approval workflow was triggered.

[Before/after integrity comparison](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/data_integrity_comparison.json) · [Fingerprint script](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/fingerprint_inputs.py) · [Tripwire bootstrap](/home/zidoum/.codex/.chatgpt-projects/g-p-6aabdff34aa88191bbca7bea777c801a/acceptance/step0_2026-10-16/server_guard.py)

## 9. Remaining bugs and limitations

1. **Execution flag overstates completed work.** An unauthorized-root request returned `status=ERROR`, zero inspected files and `full_validation_performed=true`. The flag is derived from the requested phase, not from completion of its checks. It should not be used as proof that validation ran. Reproduction is the `denied_root` record in the negative tests.
2. **Three tests depend on ambient configuration.** The globally configured `current` dataset breaks catalog assertions. Their test fixtures should isolate this setting; the production validation logic should not be changed to satisfy those assertions.
3. **Unit and assembly annotations are unverified.** Invalid strings are retained with PASS under the constructed fixture policy. Structural PASS cannot establish correct physical units, genome assembly or biological interpretation.
4. **Output schemas are permissive.** Step 0's `Step0Result` defines an optional status and allows other properties without typed count/ROI contracts. Formal schema validity is useful but does not ensure the numerical fields are present or well typed. The independent comparison checks were necessary.
5. **Error signalling has two layers.** Clients checking only `is_error` miss some execution failures that are conveyed solely through `status=ERROR`. Both fields must currently be handled.
6. **Autonomous agent acceptance remains untested.** Fixed-route prompt evidence and assistant-authored examples cannot validate independent agent behaviour or model-token efficiency. The existing usage-parser tests use synthetic responses.
7. **Deployment coverage is bounded.** Stdio worked outside the restricted sandbox; its initialization timeout inside was not diagnosed. The exact frozen MCP 2.2.0 environment, concurrent hostile filesystem mutation and OS resource isolation were not tested here.
8. **Real experimental completeness remains unknown.** Observed counts were verified, but an acquisition/probe reference was not available. Outside-root symlink targets were deliberately not assessed.

## 10. Required next acceptance work

Before full copilot sign-off, run fresh provider-backed agent prompts against an independent oracle; retain actual selected calls, final answers and provider usage where exposed. Address the completion-flag semantics and test isolation. Agree explicit metadata-validation scope and typed output/error contracts before treating these results as an automatic scientific-readiness gate. Re-run the relevant acceptance checks after any changes.

These are recommendations only. **No fixes were applied, no scientific validation logic was changed, and no Step 1 implementation or real-experiment downstream processing was performed. Evaluation stops with this report.**
