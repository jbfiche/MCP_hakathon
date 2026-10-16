# Chromatin Trace MCP

## Experiment-wide Step 0 (16 October 2026)

The existing server now also validates pyHiM experiment directories. Existing
scientific/QC tools remain available. Step 0 is file/schema/metadata validation;
it never starts collection, Pearson, merging or downstream analysis.

Install this package with its existing test setup, or use `uv sync --extra test`.
Astropy and PyYAML are now explicit direct dependencies; both were already in the
resolved dependency graph. No new server, scientific backend or API SDK was added.

Configure the server's allowed input root and a separate writable output location:

```bash
export CHROMATIN_EXPERIMENT_ROOTS=/absolute/path/to/experiments
export CHROMATIN_STEP0_OUTPUT_DIR=/absolute/path/to/validation-results
python scripts/check_step0.py /absolute/path/to/experiments/experiment_A
```

An unset allowlist denies new experiment reads. Restart the MCP server after
changing environment configuration. A full run returns a compact summary plus
`summary.json`, `details.json` and `report.md` paths in a unique run directory.
It creates these for FAIL, ERROR and INCOMPLETE results as well as PASS when the
output directory is available. Supply `--rules policy.json` when authoritative
expected ROIs/barcodes and structure rules are available. Do not fill expected
sets from observations merely to make validation pass.

Defaults select **mask-based traces**, tolerate ROI zero-padding, support both
observed localization layouts and never select the first of several matches.
Read the root-level [Step 0 reference](../references/step0.md),
[identification evidence](../references/ecsv-identification.md),
[benchmark protocol](../references/step0-benchmarking.md) and
[native output audit](../references/traceratops-output-audit.md).

Run tests with `uv run --extra test pytest`. From an already activated environment,
`python -m pytest` is equivalent. Run the reproducible transport benchmark using
`benchmarks/create_fixture.py` and `benchmarks/benchmark_step0.py` as documented.
Actual agent execution is opt-in and needs client-side credentials and an explicit
model; no live model-token usage was measured in this implementation session.

The rest of this README documents the existing single/named-dataset tools, which
remain available and are separate from experiment-wide Step 0.


This small MCP server exposes one chromatin-tracing ECSV file as a **read-only
resource** and uses [traceratops](https://github.com/pyHi-M/traceratops) to open
and inspect the trace through a read-only MCP tool.

The server publishes this resource:

```text
trace://current/ecsv
```

Reading that URI returns the complete file unchanged. The server does not edit the
file. The `inspect_current_trace` tool opens the ECSV with traceratops and returns
a compact summary: rows, columns, metadata, unique traces, barcodes, and ROIs.

The `trace_stats` tool calls traceratops' native `compute_trace_statistics`
implementation and returns its three statistics as structured MCP data:

- number of unique ROIs;
- number of unique chromatin traces;
- number of unique barcodes.

The original traceratops terminal report is captured and included in the response;
it is never printed onto the MCP stdio protocol channel.

Three write-producing traceratops workflows are also exposed:

- `filter_traces` calls `traceratops.trace_filter.runtime` and writes a new filtered
  ECSV without modifying the configured input;
- `trace_to_matrix` calls `traceratops.trace_to_matrix.runtime` and writes NumPy
  matrices, a barcode index, and the standard PNG matrix plots;
- `localization_analyzer` calls `traceratops.localization_analyzer.run` and writes
  a localization quality-control plot. It requires a localization table, which is
  a different input from the chromatin trace table.

Generated files go into an isolated run directory below
`CHROMATIN_TRACE_OUTPUT_DIR`. If that variable is unset, the default is an
`mcp_outputs` directory beside the input trace. Each call gets a unique directory,
so previous results are not overwritten.

The server can also manage several datasets in one session. A dataset is a name,
a trace ECSV path, and an optional associated localization ECSV path. Use
`register_dataset`, `list_datasets`, and `inspect_dataset` to manage them, then use
`compare_datasets` for an explainable structural and quality-control comparison.
The environment-configured files remain available under the reserved name
`current`.

`compare_datasets` checks required columns, coordinate units, barcode overlap,
schema differences, missing coordinates, repeated trace/barcode rows, trace and
ROI counts, and localization SNR when localization tables are present. Its status
is `compatible`, `compatible_with_warnings`, or `not_comparable`. These are
technical compatibility checks, not claims about biological significance.

`duplicate_statistics` gives a compact multiplicity breakdown for two registered
datasets. For trace tables it groups rows by `(Trace_ID, Barcode #)`; for
localization tables it groups by `(ROI #, CellID #, Barcode #)`. It reports groups
with zero, one, two, or more than two duplicate occurrences, plus extra duplicate
rows and the largest group size. It is read-only and does not call the filtering
workflow or modify input files.

`localization_quality_summary` reports compact SNR and intensity distributions for one
registered localization table. Use it before choosing thresholds. `snr_filter_sweep`
then evaluates explicit thresholds for two datasets, joins retained localization
`Buid` values to trace `Spot_ID` values, reports localization and trace retention,
intensity quantiles, duplicate multiplicities, and writes a JSON summary plus a PNG
plot. The sweep does not modify either input file.

## 1. Install

Python 3.10 or newer is required. From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Before installing, verify that `python` belongs to this project's virtual
environment:

```bash
which python
python -m pip --version
```

Both paths should begin with this project's `chromatin-trace-mcp/.venv/`
directory. If they show `anaconda3`, reactivate the virtual environment with
`source .venv/bin/activate` before installing.

The project installs traceratops directly from its GitHub repository. Hatchling
therefore has `allow-direct-references = true` in `pyproject.toml`; this is an
explicit acknowledgement that one dependency uses a Git URL rather than PyPI.

## 2. Select the trace file

The server reads the path from an environment variable. This avoids hard-coding a
personal data location into the Python source.

```bash
export CHROMATIN_TRACE_ECSV="/home/jb/Desktop/data/Trace_3D_barcode_mask-DAPI_ROI-24.ecsv"
export CHROMATIN_LOCALIZATION_ECSV="/absolute/path/to/localizations.ecsv"
export CHROMATIN_TRACE_OUTPUT_DIR="/absolute/path/to/mcp_outputs"
```

## 3. Inspect it interactively

With the virtual environment active:

```bash
mcp dev src/chromatin_trace_mcp/server.py:mcp
```

The graphical Inspector is a Node.js application. The `mcp dev` command invokes
it through `npx`, so both Node.js and `npx` must be installed and visible on
`PATH`. This requirement belongs only to the Inspector; the Python MCP server
does not require Node.js.

The MCP Inspector opens in a browser. Choose **Resources**, select
`trace://current/ecsv`, and read it. To test the compact traceratops result,
choose **Tools**, select `inspect_current_trace`, and run it with no arguments.
You can select `trace_stats` in the same menu and run it with no arguments.

To compare two datasets in the Inspector:

1. Run `register_dataset` with `name=experiment_A` and its two file paths.
2. Run it again with `name=experiment_B` and the second pair of paths.
3. Run `list_datasets` to verify both registrations.
4. Run `compare_datasets` with `first_dataset=experiment_A` and
   `second_dataset=experiment_B`.

When a catalog is configured (`CHROMATIN_DATASETS_JSON`, as in the Codex
configuration), `register_dataset` also **saves the dataset to the catalog**, so it
is still available after the server or the assistant restarts. Other catalog
entries are kept, and an existing name is only replaced when `overwrite=true` is
passed. Without a catalog, registrations are kept in memory and disappear when the
MCP server stops. Input files are never changed.

In practice, a user can simply ask the assistant, for example: *"Register
`/path/to/merged_traces.ecsv` as exp_231 and compare it with exp_214."* A dataset
can be one ROI or a merged experiment (several ROIs in one trace file).

### Save datasets permanently for local development

For repeated Inspector sessions, put dataset paths in `datasets.local.json` instead
of registering them manually every time (or register them once with
`register_dataset` while the catalog is configured: they are written there).
Start from `datasets.example.json`. This
repository already contains a local ignored catalog with `experiment_A` filled in;
add `experiment_B` when its paths are known.

Launch the Inspector with the reusable script:

```bash
./scripts/start_inspector.sh
```

The script passes `datasets.local.json` to the MCP server through
`CHROMATIN_DATASETS_JSON` and uses
`/home/jb/Desktop/Hackaton/data/mcp_outputs` for generated files. The local catalog
is ignored by Git because it contains machine-specific paths. Once connected, run
`list_datasets`; catalog entries are already available and do not require
`register_dataset`.

The localization file is optional. When it is unavailable, use an empty string,
JSON `null`, or omit `localization_file` entirely:

```json
"experiment_A": {
  "trace_file": "/path/to/trace.ecsv",
  "localization_file": ""
}
```

To check the catalog without the graphical Inspector:

```bash
CHROMATIN_DATASETS_JSON="$PWD/datasets.local.json" \
  uv run python scripts/check_server.py list_datasets
```

Validate and compare two catalog datasets from the terminal with:

```bash
CHROMATIN_DATASETS_JSON="$PWD/datasets.local.json" \
  uv run python scripts/check_server.py compare_datasets \
  --first-dataset experiment_A --second-dataset experiment_B
```

## Use both MCPs from Codex desktop

The MCP Inspector tests one server at a time. To let Codex desktop coordinate the
analysis and reporting servers, copy the two sections in
`codex-mcp-config.example.toml` into `~/.codex/config.toml`, then restart Codex.
The trace server reads `datasets.local.json`; the report server writes reports to
the configured reports directory. In a Codex chat, type `/mcp` to confirm that
both `chromatin_trace` and `chromatin_report` are connected.

For a simpler terminal-only check, run:

```bash
python scripts/check_server.py trace_stats
```

This creates an MCP client in the same Python process, calls `trace_stats`, and
prints the structured JSON response. It still tests the MCP interface rather than
calling the underlying Python function directly, and it does not require Node.js.

Use `inspect_current_trace` instead of `trace_stats` to call only the inspection
tool, or omit the argument to run both tools:

```bash
python scripts/check_server.py inspect_current_trace
python scripts/check_server.py
```

With uv, prefix these commands with `uv run`, for example:

```bash
uv run python scripts/check_server.py trace_stats
```

The same Node-free checker can exercise the two file-generating tools with their
safe defaults:

```bash
uv run python scripts/check_server.py filter_traces
uv run python scripts/check_server.py trace_to_matrix
uv run python scripts/check_server.py localization_analyzer
```

These commands create files under `CHROMATIN_TRACE_OUTPUT_DIR`; the default checker
invocation runs only the two read-only tools.

Running `chromatin-trace-mcp` or `python -m chromatin_trace_mcp.server` directly
starts a stdio server. It will wait silently for an MCP client and should not be
used as an interactive command prompt. Stop it with `Ctrl+C`.

## 4. Run the tests

```bash
pytest
```

The tests use a tiny temporary ECSV file; they never modify the real trace.

The traceratops compatibility suite also uses a small representative pyHiM trace
in `tests/fixtures/`. It checks traceratops' native reader, high-level trace class,
ECSV round trip, `trace_stats` implementation, and installed command inventory.

To include the real configured trace in the compatibility suite:

```bash
export CHROMATIN_TRACE_ECSV="/absolute/path/to/your/trace.ecsv"
pytest tests/test_traceratops_compatibility.py
```

With uv, use `uv run pytest` instead. The real-trace test is skipped when the
environment variable is absent or the configured file is unavailable, and it
never writes to the input file.

## 5. Connect an MCP host

Use [`mcp-config.example.json`](mcp-config.example.json) as a guide. Replace the
placeholder executable path with the absolute path to this project's installed
`.venv/bin/chromatin-trace-mcp` command. MCP hosts use different settings screens,
but the command and environment-variable values are the same.

## What each file does

- `src/chromatin_trace_mcp/server.py`: defines and runs the MCP server.
- `tests/test_server.py`: verifies behavior visible to an MCP client.
- `mcp-config.example.json`: example host configuration.
- `DEVLOG.md`: explains the design and implementation step by step.

## Important limitation

The attached trace is about 7.5 MB. A host may allow reading a resource this large,
but sending all of it to a language model is inefficient and may exceed its context
limit. The `inspect_current_trace` tool demonstrates the better pattern: traceratops
loads the complete table locally, while only a small structured result is sent to the
model. A sensible next tool is “get one trace by `Trace_ID`”.

Traceratops currently installs many command-line analyses. They are the scientific
toolbox behind this MCP, but each command still needs a thin MCP adapter so that its
arguments, outputs, file-writing behavior, and errors are explicit. The scientific
implementation remains in traceratops; the adapter is only the protocol boundary.

## Step 0 Data Quality Reports

The trace server saves JSON evidence and Markdown/HTML Data Quality Reports in
one validation call. Use its `human_report_path` or `html_report_path`, or retrieve
those paths with trace `get_validation_summary`. No reporting server is required
for Step 0. The report server retains the richer comparison/PDF tools. See the
[Step 0 interface](../references/step0.md) for artifact paths and migration details.
