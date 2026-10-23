# Installation and MCP Host Setup

This guide covers local Linux/macOS setup and Codex CLI. Replace every `/path/to/…` with an absolute path on your computer.

## Requirements and installation

You need Python 3.10 or newer, Git, a virtual environment for each server, an MCP host that supports local stdio servers, and a separate writable results directory. The trace package declares Traceratops, Astropy, NumPy, PyYAML, Pydantic and the MCP SDK. The report package declares the MCP SDK, Pydantic, Matplotlib and ReportLab. Traceratops is installed from its Git repository, so initial installation needs access to Python package sources and GitHub. The package metadata is the source of truth for exact dependency versions.

Install the trace server:

```bash
cd /path/to/MCP_hakathon/chromatin-trace-mcp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Install the report server separately:

```bash
cd /path/to/MCP_hakathon/chromatin-report-mcp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Each environment installs its own console command at `.venv/bin/chromatin-trace-mcp` or `.venv/bin/chromatin-report-mcp`. If using uv, each package includes a lock file: run `uv sync --locked --extra test` from that package directory.

Check the trace environment:

```bash
/path/to/MCP_hakathon/chromatin-trace-mcp/.venv/bin/python -c 'import mcp, traceratops, astropy, numpy; print("trace dependencies import successfully")'
```

## Paths, permissions and outputs

Use absolute paths. Keep original experiment files read-only and configure output elsewhere. `CHROMATIN_EXPERIMENT_ROOTS` is the trace server's Step 0 input allowlist; separate multiple roots with `:` on Linux/macOS.

Set `CHROMATIN_TRACE_OUTPUT_DIR` as the common output root. Stage-specific roots can be set when desired: `CHROMATIN_STEP0_OUTPUT_DIR`, `CHROMATIN_COLLECTION_OUTPUT_DIR`, `CHROMATIN_PEARSON_OUTPUT_DIR`, `CHROMATIN_MERGE_OUTPUT_DIR`, `CHROMATIN_LOCALIZATION_MERGE_OUTPUT_DIR`, `CHROMATIN_MERGED_STATS_OUTPUT_DIR`, `CHROMATIN_GENOMIC_OUTPUT_DIR`, `CHROMATIN_TRACE_ANALYZER_OUTPUT_DIR` and `CHROMATIN_LOCALIZATION_ANALYZER_OUTPUT_DIR`. When omitted, stage output is placed below the common root.

Optional inputs are `CHROMATIN_TRACE_ECSV` and `CHROMATIN_LOCALIZATION_ECSV` for the reserved `current` dataset, and `CHROMATIN_DATASETS_JSON` for a named-dataset catalog. Set `CHROMATIN_GENOME_REFERENCE` only when the assembly has been confirmed by the researcher. Do not infer assembly from defaults.

Step 0 reads and reports the experiment; it does not start collection or analysis. Collection copies selected tables into its own run directory. Later tools write new run directories and do not edit original tables. A configured experiment-level `mcp_results/` view can expose authoritative files through safe links instead of large duplicate copies.

## Register in Codex CLI

Codex CLI uses this syntax for a local stdio server: `codex mcp add NAME --env KEY=VALUE -- COMMAND`. Register the trace server with your actual paths:

```bash
codex mcp add chromatin-trace \
  --env "CHROMATIN_EXPERIMENT_ROOTS=/path/to/experiment" \
  --env "CHROMATIN_TRACE_OUTPUT_DIR=/path/to/results/chromatin-trace" \
  --env "CHROMATIN_STEP0_OUTPUT_DIR=/path/to/results/chromatin-trace/step0" \
  --env "CHROMATIN_TRACE_ECSV=/path/to/experiment/ROI/tracing/data/trace.ecsv" \
  -- "/path/to/MCP_hakathon/chromatin-trace-mcp/.venv/bin/chromatin-trace-mcp"
```

Register the report server separately. Its authorized artifact roots must contain every source and saved evidence file referenced by a report:

```bash
codex mcp add chromatin-report \
  --env "CHROMATIN_REPORT_OUTPUT_DIR=/path/to/results/chromatin-reports" \
  --env "CHROMATIN_REPORT_ARTIFACT_ROOTS=/path/to/experiment:/path/to/results/chromatin-trace" \
  --env "CHROMATIN_QC_MANIFEST_DIR=/path/to/results/chromatin-qc-manifests" \
  -- "/path/to/MCP_hakathon/chromatin-report-mcp/.venv/bin/chromatin-report-mcp"
```

The colon separates Linux/macOS paths. Keep the report output and manifest directories outside the input experiment and protected scientific artifact directories. The host-only helper `python -m chromatin_report_mcp.prepare_manifest INDEX_JSON MANIFEST_ID` binds an existing workflow index to checksummed artifacts; it performs no scientific calculations. See [comprehensive report requirements](../references/comprehensive-qc-report.md).

Alternatively, copy the two server sections from [codex-mcp-config.example.toml](../chromatin-trace-mcp/codex-mcp-config.example.toml) into `~/.codex/config.toml`. Use one method, then restart the Codex TUI.

Check registration and active connections:

```bash
codex mcp list
codex mcp get chromatin-trace
codex mcp get chromatin-report
```

Start Codex and enter `/mcp` to see active servers. Then ask: “Use chromatin-trace-mcp to call `list_datasets` and show only the registered names. Do not run write-producing tools.” This read-only call also confirms the host can discover and invoke a trace tool.

For a direct local read-only check of the trace server:

```bash
cd /path/to/MCP_hakathon/chromatin-trace-mcp
CHROMATIN_TRACE_ECSV=/path/to/experiment/ROI/tracing/data/trace.ecsv \
  .venv/bin/python scripts/check_server.py inspect_current_trace
```

The package's MCP integration tests can additionally check its stdio client/server path: run `python -m pytest` from the trace package after installing the test extra.

## Human approval form

After `trace_pearsons`, the researcher inspects the saved QC report and figure. The client then calls `review_pearson_approval` with the exact run ID and results checksum and requests a decision. A client that supports MCP form elicitation displays ROI-to-dataset mapping, correlations, warnings and explicit choices. Only the user's submitted selection is recorded. Cancellation leaves the run awaiting approval, and merging checks the saved decision and evidence again.

The current Codex CLI MCP documentation covers stdio setup and tool discovery but does not document form elicitation. Treat approval-form support as unverified for a particular Codex CLI version until tested. The repositories do not package a general interactive elicitation client. Use a client that declares form support and renders the received schema; test cancellation first. Never let the model supply the decision. See [the approval protocol and trust boundary](../references/scientific-approval.md). A client without form support may read an existing status but cannot create a human decision.

## Open a local report

After a comprehensive report is generated and published to the experiment results view, open it directly:

```bash
firefox "/path/to/experiment/mcp_results/<workflow-run>/Comprehensive_QC_Report.html"
```

Use the exact path returned by the report tool if the workflow uses a different name. The HTML is intended to work as a local `file://` document without a web server.

## Troubleshooting and removal

- **Server missing:** use `codex mcp list` and `codex mcp get NAME`; verify the executable path and restart Codex.
- **Tools missing:** confirm that the process imports from the server's own `.venv`, then use `/mcp` and try the read-only call. MCP stdio uses stdout for protocol messages; diagnostics belong on stderr.
- **Python/Traceratops import error:** rerun the import check and reinstall dependencies into the same `.venv`.
- **Experiment access denied:** use an absolute path under `CHROMATIN_EXPERIMENT_ROOTS`; restart after changing configuration.
- **Files missing:** check the exact filename and layout. Step 0 skips symlinks and reports them as warnings.
- **Form not shown:** cancel without submitting. Confirm that the client supports MCP form elicitation; status must remain `AWAITING_APPROVAL`.
- **Stdio error:** launch the installed console command directly and inspect host/server stderr.

Remove a registration without deleting its data:

```bash
codex mcp remove chromatin-trace
codex mcp remove chromatin-report
```

To uninstall, activate each environment and run `python -m pip uninstall chromatin-trace-mcp` or `python -m pip uninstall chromatin-report-mcp`. Removing the configuration does not remove saved results.

## Native commands and wrapper responsibilities

| Workflow operation | Native Traceratops CLI | Extra MCP responsibilities |
|---|---|---|
| Step 0 validation/report | None | Safe directory inspection, ECSV/schema/barcode/BED checks, per-ROI statistics and saved validation evidence/report. |
| Collection | `collect_files` | Authorized roots, ROI/source mapping, checksums, immutable manifest and compact response. |
| Pearson QC | `trace_pearsons` | Verified collection references, saved results, compact ROI mapping and review evidence. |
| Human approval | None | Form elicitation, explicit ROI selection and persisted checksum-bound decision. |
| Trace merge | `trace_merge` | Approval enforcement, hash/provenance checks and source protection. |
| Localization merge | `localization_merge` | Approved tracing-to-localization ROI mapping, integrity checks and provenance. |
| Merged statistics | `trace_stats` | Uses verified merged data and binds result to the merge evidence. |
| Genomic annotation | `trace_genomic_coordinates` | Researcher-confirmed assembly, full barcode mapping/coverage, replacement checks and immutable derivative. |
| Trace/localization analyzers | `trace_analyzer`, `localization_analyzer` | Verify approved inputs, provenance and source integrity; save complete results and return compact summaries. |
| Comprehensive report | None | Formats checksum-identified artifacts without scientific recalculation. |

The native CLIs can run the calculations, but do not enforce the MCP approval and evidence rules. For example, genomic-coordinate CLI options include continuing with unmatched barcodes; the wrapper applies stricter validation.

## Performance evidence and recommendation

Three approaches were considered:

| Approach | Behavior | Assessment |
|---|---|---|
| **A. Current MCP stages** | Validated call per stage; human review before merging. | Real post-approval run used five calls, 19.93 s wall time and 16,632 serialized response bytes. It preserved approval, hashes and provenance. |
| **B. Native Bash** | Fixed shell pipeline of native Traceratops CLI commands. | Direct scientific runs were faster, but a script does not provide Step 0 checks, persistent approval or hash-bound evidence unless these are rebuilt. |
| **C. Hybrid runner** | MCP handles validation/approval/provenance; a fixed deterministic runner executes approved operations. | Could reduce agent turns, but is not implemented or benchmarked end-to-end. It must recheck approved hashes and retain evidence; shelling out alone is insufficient. |

For biologists, A is easiest to inspect one stage at a time. B is familiar to shell users but requires manual checking of inputs and decisions. C could simplify execution if it keeps visible checkpoints.

Historical single-run timings from the real experiment before human approval:

| MCP tool | Server/call time | Structured response | Serialized response |
|---|---:|---:|---:|
| Step 0 run_experiment_validation | 1.21 s | 5,017 B | 12,160 B |
| Trace collect_files | 0.57 s | 1,181 B | 2,869 B |
| Localization collect_files | 0.89 s | 1,158 B | 2,823 B |
| trace_pearsons | 2.17 s | 2,171 B | 4,941 B |
| Approval status check (request_decision=false) | 0.02 s | 741 B | 1,781 B |

The approval form wait and the human's decision time were not benchmarked. A separate real localization-analyzer validation took 6.30 s at the MCP call (6.27 s server execution) versus 2.76 s direct native, with 2,039 structured / 4,503 serialized response bytes; its figure matched native exactly. A real report-generation validation verified 55 artifacts and produced a 1.14 MB standalone HTML file in 0.09 s, with a 654 B structured response (1,604 B serialized). Reporting ran no scientific calculations. Each result is a historical single run.

Historical single-run ROI 092/093 timing after genuine human approval:

| Stage | MCP server time | Direct native time | Structured response |
|---|---:|---:|---:|
| Trace merge | 1.67 s | 0.70 s | 1,162 B |
| Localization merge | 2.36 s | 1.03 s | 1,361 B |
| Merged trace statistics | 1.02 s | 0.27 s | 1,348 B |
| Genomic annotation | 2.98 s | 1.84 s | 1,478 B |
| Trace analyzer | 11.83 s | 8.66 s | 1,940 B |
| **Total** | **19.86 s** | **12.51 s** | **7,289 B** |

The outputs were equivalent: native merge and annotation ECSV files matched byte-for-byte, and analyzer figures matched byte-for-byte. Across calls, serialized responses were 16,632 B. MCP startup was 1.57 s; discovery was not repeated in the resumed session. Wrapper time includes validation, hashes, provenance and publication. This is one historical run, not a stable speed estimate.

Peak memory, disk I/O and exact ECSV read counts were not recorded. Each native operation must read the inputs it analyzes; integrity checks also read files for hashing. A single orchestrating call would reduce model/host turns but would not automatically remove those reads.

A separate historical Step 0 benchmark ran 18 synthetic two-ROI trials per strategy (three repeats of six prompts). Scripted five-call validation averaged 12.6 ms; aggregate validation averaged 6.3 ms. Accuracy was 100% against its fixture oracle. This was not autonomous-agent testing and gives no measured provider tokens or scientific-pipeline speedup.

**Recommendation:** retain A for now. It is already validated and keeps the human gate and evidence checks. A fixed versioned hybrid runner is the smallest future candidate to reduce orchestration, but should be evaluated separately. Current evidence shows no actual model-token savings, so it does not justify implementing that runner yet.
