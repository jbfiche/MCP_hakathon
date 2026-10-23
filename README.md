# pyHiM / Traceratops MCP servers

This repository contains two local MCP servers for pyHiM and Traceratops:

- **chromatin-trace-mcp** validates experiment files and runs native Traceratops calculations. It records hashes and provenance and requires human approval before merging.
- **chromatin-report-mcp** formats verified saved results into readable reports. It does not recalculate scientific measurements.

MCP (Model Context Protocol) lets an AI host discover and call tools exposed by a local program. Traceratops remains the scientific engine; the servers add a consistent interface, evidence checks and saved records.

## Installation and MCP Host Setup

See [docs/installation.md](docs/installation.md) for prerequisites, virtual environments, configuration, Codex CLI setup, read-only checks, approval-form requirements, troubleshooting and the comparison with native Bash.

Install and register the servers separately. Give the trace server access only to authorized experiment roots and put generated output outside original experiment files. Each run gets its own output directory. An experiment-level `mcp_results/` view can expose results through safe links without copying large files.

## Workflow

The trace server checks files and ECSV contents, collects ROI tables, calculates Pearson QC and saves results and figures. A researcher reviews those exact results and explicitly selects or rejects datasets. Only a valid decision tied to those results allows merging and later analysis. This is a scientific approval gate; a successful software test is not approval.

The report server is for reports that combine several completed analyses. For a single validation or Pearson report, use the report produced by the trace server. Comprehensive HTML reports are local files; open the experiment-level report directly in Firefox:

```bash
firefox "/absolute/path/to/experiment/mcp_results/<workflow-run>/Comprehensive_QC_Report.html"
```

## MCP versus native Traceratops commands

Traceratops has CLI commands for collection, Pearson QC, merging, statistics, genomic-coordinate assignment and both analyzers. The MCP wrappers call these native implementations and have been checked against direct native results. The native CLI does not provide Step 0 validation, hash-bound evidence, persisted human approval, guarded merge authorization or the wrappers' provenance checks. Directly running `trace_merge` does not enforce approval.

In the real ROI 092/093 post-approval run, five MCP calls took 19.93 s (19.86 s inside the tools); direct native runs took 12.51 s for the same stages. Results were equivalent, while MCP also recorded approval, hashes and provenance. One MCP startup took 1.57 s. The five calls returned 7,289 structured bytes (16,632 serialized bytes). This is a historical single run, not a repeated performance study. Memory, disk I/O and exact repeated ECSV-read counts were not measured. Actual model tokens were unavailable because no provider-backed agent was used.

The current recommendation is to keep the validated stages. A fixed deterministic runner might later reduce agent orchestration, but it must retain the human approval checkpoint and call the guarded operations. Generating an ad hoc Bash script adds no such protection. No replacement architecture is implemented here.
