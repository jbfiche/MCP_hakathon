# Development log

## Goal

Build the smallest useful MCP server for chromatin-tracing data: open one ECSV trace
as a resource. This milestone is intentionally about MCP plumbing, not scientific
analysis yet.

## Step 1 — Understand the input

I inspected only the header and basic file properties; the source data was not
modified or copied into this project.

The example file is an Astropy ECSV 1.0 table. Its metadata says:

- coordinate unit: micron;
- genome assembly: mm10;
- schema: astropy-2.0.

Its columns are `Spot_ID`, `Trace_ID`, `x`, `y`, `z`, `Chrom`, `Chrom_Start`,
`Chrom_End`, `ROI #`, `Mask_id`, `Barcode #`, and `label`. The file is about 7.5 MB
and contains 51,432 data rows.

This agrees with traceratops' purpose: the package works with pyHiM trace and
localization tables and uses Astropy for ECSV I/O.

## Step 2 — Choose the MCP primitive

MCP offers three relevant ideas:

- **Resource**: data that an MCP host can attach to context.
- **Tool**: an action the model can choose while reasoning.
- **Prompt**: a reusable request selected by a person.

The requested operation is “open this file”, so a resource is the simplest fit. A
future calculation such as filtering traces or computing a distance matrix should be
a tool.

## Step 3 — Choose a URI

The resource URI is:

```text
trace://current/ecsv
```

This is a logical identifier, not the physical file path. The host sees a stable URI
while the environment variable decides which local trace is “current”.

## Step 4 — Configure the file safely

`CHROMATIN_TRACE_ECSV` holds the file path. This design has two advantages:

1. Data locations are not embedded in reusable source code.
2. The server exposes only the selected trace, not an arbitrary file-reading tool.

The server checks that the value exists, points to a file, and ends in `.ecsv`.
Failures become MCP `ResourceError` responses with actionable messages.

## Step 5 — Preserve the scientific file

The resource reads UTF-8 text and returns it unchanged with the media type
`text/csv`. It does not parse, normalize, reorder, or write the table. This keeps the
ECSV header and metadata intact for Astropy and traceratops.

## Step 6 — Test through MCP

The tests create a tiny temporary ECSV file and connect an in-process MCP client.
They verify protocol-visible behavior:

- exactly one resource is listed;
- no tools exist yet;
- the ECSV contents are returned byte-for-text unchanged;
- missing configuration is reported as a resource error;
- a non-ECSV path is rejected.

Testing through an MCP client is more useful than calling the Python function
directly because it verifies what a real host will observe.

## Step 7 — Sensible next milestone

Do not make the language model ingest 7.5 MB for every question. Add read-only,
structured tools that parse the table once and return small results, for example:

1. `describe_trace()` — row count, columns, metadata, trace count, barcode range.
2. `get_trace(trace_id)` — only the localizations belonging to one trace.
3. `trace_quality_summary()` — missing/duplicate barcode and completeness metrics.
4. Later, wrappers around traceratops matrix and filtering functions.

That progression keeps the MCP interface understandable and makes each scientific
operation independently testable.

## Step 8 — Reuse traceratops for loading

The first version of the resource used Python's `Path.read_text()` because a resource
must return text. We then added an MCP tool named `inspect_current_trace` that uses
traceratops' existing `read_table_from_ecsv(path)` function. That function reads the
ECSV with Astropy and returns an `astropy.table.Table`.

The Astropy table itself cannot be returned directly through MCP: MCP results need to
be serializable. Our wrapper therefore extracts a small `TraceSummary` containing row
count, columns, metadata, and unique trace/barcode/ROI counts.

Traceratops also offers `ChromatinTraceTable.load(file)`. We deliberately use its
lower-level `read_table_from_ecsv` helper here because `load()` prints status messages
to standard output. In a stdio MCP server, standard output is reserved for protocol
messages; ordinary diagnostic text could corrupt the connection.

This illustrates the adapter pattern we will use throughout the project:

```text
MCP tool -> small wrapper -> traceratops function -> Astropy/scientific result
                              |
                              +-> wrapper converts it to compact MCP data
```

## Step 9 — Allow the traceratops Git dependency

Traceratops is referenced directly from its public GitHub repository:

```toml
"traceratops @ git+https://github.com/pyHi-M/traceratops.git@main"
```

Hatchling rejects direct URL dependencies unless the project explicitly opts in.
The first editable installation therefore failed while validating the project
metadata. We added:

```toml
[tool.hatch.metadata]
allow-direct-references = true
```

This does not download or install anything by itself. It tells the build backend
that the Git reference in our dependency list is intentional.

The error traceback also showed `/home/jb/anaconda3/.../pip`, meaning the command
was executed with Anaconda's Python rather than the MCP project's `.venv`. Checking
`which python` before installation makes that environment mix-up visible.

## Step 10 — Use asynchronous MCP handlers

After installing the dependencies, the MCP SDK's in-process client stalled while
invoking synchronous resource and tool handlers. The same behavior was reproduced
with the SDK resource demo in this environment, so it was not caused by the ECSV
file or traceratops.

The registered `inspect_current_trace` tool and `read_current_trace` resource were
changed from `def` to `async def`. Their scientific behavior is unchanged, but the
SDK can now await them directly instead of routing them through its synchronous
worker path. This also follows the MCP SDK recommendation to use asynchronous
handlers for I/O operations.

After this change, all five in-process MCP protocol tests passed.

## Step 11 — Add a terminal-only check

Running a stdio MCP server directly does not display a prompt: it waits for JSON
protocol messages from an MCP client. For an easier first check, we added
`scripts/check_server.py`. It starts an in-process MCP client, invokes
`inspect_current_trace`, and prints the returned structured JSON. This exercises
the same MCP tool contract that a host will use, without requiring the browser-based
Inspector.

## Step 12 — Define and test the traceratops compatibility boundary

Traceratops 1.0.1 installs 28 console commands. Rather than copying their scientific
code into this project, this MCP will use traceratops as its analysis backend. MCP
adapters will remain deliberately thin: validate MCP inputs, call traceratops, and
convert the result or output artifact into an explicit MCP response.

We added `tests/test_traceratops_compatibility.py` and a representative 12-column
pyHiM ECSV fixture. The suite verifies:

1. `read_table_from_ecsv` accepts the representative trace and preserves types and
   metadata;
2. `ChromatinTraceTable.load` accepts the same input;
3. traceratops can save and reload the table without changing its data or metadata;
4. traceratops' own `compute_trace_statistics` produces the expected counts;
5. the installed distribution is traceratops 1.0.1 and exposes the core commands;
6. when `CHROMATIN_TRACE_ECSV` is set, the actual configured trace loads and has the
   expected schema.

This is a compatibility contract, not a reimplementation of traceratops. If a future
traceratops update changes an expected API or trace schema, the tests fail at the
boundary before an MCP tool silently returns incorrect results.

## Step 13 — Expose traceratops `trace_stats` through MCP

We added a read-only MCP tool named `trace_stats`. It does not reproduce the
scientific calculation. It calls traceratops 1.0.1's existing
`compute_trace_statistics(trace_file)` function on the configured ECSV file.

That traceratops function is designed for a terminal: it prints its result and
returns `None`. The MCP adapter therefore:

1. resolves the configured trace file;
2. captures traceratops' standard output so it cannot corrupt MCP stdio messages;
3. invokes the native traceratops function;
4. extracts the three reported counts into a typed `TraceStatsResult`;
5. includes the original traceratops report and package version for provenance;
6. converts failures into MCP `ToolError` results.

The parsing step is deliberately tested against traceratops' native output. If a
future traceratops release changes the report format, the adapter fails explicitly
instead of silently returning incorrect statistics. A future upstream traceratops
API that returns structured statistics would allow us to remove this parsing layer.

## Step 14 — Test tools without Node.js

The MCP SDK's `mcp dev` command launches the graphical MCP Inspector through
`npx`, so it requires a separate Node.js installation. The Python server itself
does not depend on Node.js.

We extended `scripts/check_server.py` to accept `inspect_current_trace`,
`trace_stats`, or `all`. The script uses the SDK's in-process MCP client, so it
exercises the actual MCP tool schemas and responses without the Inspector:

```bash
uv run python scripts/check_server.py trace_stats
```

## Step 15 — Add filtering and matrix-generation tools

We added two write-producing MCP adapters while leaving their scientific work in
traceratops:

- `filter_traces` calls `traceratops.trace_filter.runtime` with validated barcode,
  label, coordinate, duplicate-cleanup, and minimum-length parameters;
- `trace_to_matrix` calls `traceratops.trace_to_matrix.runtime` with a distance
  threshold, worker count, and optional histogram generation.

Because `trace_filter` always writes beside its input, the adapter first copies the
configured trace into an isolated run directory. Traceratops filters that copy, and
the adapter removes the temporary copy afterward. The original trace is never
modified. `trace_to_matrix` already accepts an output directory, so it writes
directly into its isolated run directory.

Both tools use `CHROMATIN_TRACE_OUTPUT_DIR`, falling back to `mcp_outputs` beside
the source trace. Every invocation receives a unique directory to avoid overwriting
earlier analyses. Their typed MCP responses contain output paths, artifact sizes,
native traceratops reports, and key dimensions/counts.

Protocol tests confirm that filtering changes the expected rows while preserving
the input, and that matrix conversion produces the expected 3×3×2 test matrix and
seven standard traceratops artifacts.

## Step 16 — Expose the localization analyzer

The traceratops localization analyzer was still missing from the MCP tool list. We
added `localization_analyzer` as a thin adapter around the existing
`traceratops.localization_analyzer.run` function rather than reimplementing its
plots.

A localization table is distinct from a chromatin trace table, so this tool uses
the separate `CHROMATIN_LOCALIZATION_ECSV` environment variable. It loads the
table with traceratops, produces the native quality-control figure in PNG, SVG, or
PDF format, and returns the output path, row and barcode counts, artifact details,
and captured traceratops report. A representative localization ECSV fixture tests
the full operation through the MCP protocol.

## Step 17 — Make typed outputs compatible with the Inspector loader

The SDK's `mcp dev` command imports a server file dynamically. Deferred annotations
created by `from __future__ import annotations` prevented Pydantic from resolving
the nested `GeneratedArtifact` model in three result types under that loader, even
though ordinary package imports and tests succeeded. Python 3.10+ already supports
every annotation used by this project, so we removed deferred annotations from the
server. A protocol test now verifies that every published tool has an output schema.

## Step 18 — Add named datasets and comparison

The original server had one global trace/localization pair. We retained that pair
as the reserved dataset `current` and added an in-memory registry for additional
named datasets. `register_dataset` validates both ECSV paths with traceratops;
`list_datasets` and `inspect_dataset` expose the registry and table summaries.

Every analysis tool now accepts `dataset_name`, defaulting to `current`, so the
same native traceratops operations can run on any registered input without
duplicating their algorithms.

The new `compare_datasets` tool calculates objective metrics for both inputs and
checks required columns, schemas, coordinate units, barcode overlap, missing
coordinates, duplicate trace/barcode rows, dataset sizes, and localization SNR.
It returns an explainable status (`compatible`, `compatible_with_warnings`, or
`not_comparable`), explicit reasons and warnings, barcode differences, and the
per-dataset measurements. It deliberately describes technical comparability only;
no unsupported biological-quality threshold was invented.

Registrations are session-scoped and never modify input data. Protocol tests cover
registration, listing, named inspection, compatible inputs, and rejection of a
comparison with no shared barcodes.

## Step 19 — Persist dataset definitions in a local catalog

The terminal checker is intentionally a short-lived MCP client, so using it to
register a dataset would lose that registration immediately. We added an optional
JSON catalog selected by `CHROMATIN_DATASETS_JSON`. The server reads its named
trace/localization pairs alongside session registrations, with session entries
taking precedence when names overlap.

`datasets.example.json` documents the portable format. `datasets.local.json`
contains this computer's paths and is excluded from Git. The reusable
`scripts/start_inspector.sh` launcher passes the catalog and output directory
explicitly through the Inspector to avoid environment-forwarding ambiguity.
Protocol tests verify that two catalog datasets can be listed and compared without
manual registration.

## Step 20 — Make localization tables optional in catalogs

Some trace datasets have no retained localization table. Catalog parsing and
session registration now normalize an empty or whitespace-only
`localization_file` to `None`, just like JSON `null` or an omitted field. Trace-only
datasets can still be inspected, filtered, converted to matrices, and compared;
localization-derived metrics are returned as null. The terminal checker now also
accepts `compare_datasets` with explicit `--first-dataset` and
`--second-dataset` arguments.

## Step 21 — Save registered datasets to the catalog

*(2026-10-09, after moving the servers to `~/Repositories/MCP_hakathon_jb/`.)*

Registering a dataset from the conversation was lost at every restart, so a user
had to edit `datasets.local.json` by hand to keep it. `register_dataset` now also
writes the entry to the catalog when `CHROMATIN_DATASETS_JSON` is set; without a
catalog, it keeps the previous session-only behaviour. Details:

- other catalog entries and their order are kept; the file is written to a
  temporary file and then renamed, so an interrupted write cannot corrupt it;
- the catalog file is created if it does not exist yet (its folder must exist);
- registering the same name with the same files again changes nothing; using an
  existing name for different files is refused unless `overwrite=true`, so a
  dataset cannot be replaced silently;
- the result now says where the dataset was saved (`saved_to_catalog`, `note`);
- traceratops' loading of the localization table is now wrapped in
  `redirect_stdout`, as elsewhere in the server, so its occasional `print()`
  cannot reach the stdio channel used by the MCP protocol.

Tests: five new protocol tests (saved and still listed after a simulated restart,
catalog created when missing, idempotent re-registration, overwrite required,
session-only without a catalog). The test fixture now clears
`CHROMATIN_DATASETS_JSON`, so the tests can never write into a real catalog set in
the user's shell. An additional manual check started the server twice over stdio
(the way Codex launches it) and found the dataset in the second session.


## 16 October 2026 — Step 0 experiment validation

Added a deterministic validation module and seven tools to the existing trace
server. Preserved all original tools and both existing comparison-report tools.
The owner selected mask-based traces for this initial pipeline. Derived barcode
index files are excluded by a terminal ROI filename check; several masks remain
ambiguous. The supplied ROI's actual localization layout includes `data/`.

Reports persist full evidence while MCP returns bounded summaries and cached
follow-up detail. Missing expected ROI/barcode references produce INCOMPLETE;
observed sets do not become authoritative references. Inputs remain unchanged.

Added synthetic exact-result tests, a direct baseline, scripted MCP controls and
an opt-in provider-usage agent harness. No API credentials were exposed during
implementation, so no actual model-token counts or savings are claimed. Synthetic
usage records are parser tests only. The backend audit uses the source commit
already pinned in uv.lock, not the newer development checkout. See root reference
documents for output gaps and the future Step 1 plan. Traceratops was not modified.

Implementation validation used Python 3.13, MCP 2.3.0, Astropy 8.0.1 and Pydantic
2.13.5 from an existing compatible environment, with the locked Traceratops source.
The lockfile's MCP 2.2.0 environment was not provisioned because uv is not present.
New direct dependency declarations reuse the lockfile's already-resolved Astropy
and PyYAML entries; their versions were not changed. Existing PDF regression tests
used the bundled ReportLab package because the analysis environment lacked it.
