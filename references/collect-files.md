# Step 1a.1 — native Traceratops collection

This is an explicitly invoked collection operation, independent of the ongoing
Step 0 agent validation. No persisted Step 0 approval gate is asserted or invented.
Step 0 never calls it, and the existing Step 0 agent allowlist excludes it. At the collection milestone, the
server had 20 tools; `collect_files` was its only additional tool.

```text
collect_files(
  experiment_root="/authorized/experiment",
  example_file="Trace_3D_barcode_mask-mask0_ROI-92.ecsv",
  variable_part="92",
  table_kind="tracing",
  rename=false
)
```

For localization tables use `example_file="localizations_3D_barcode.ecsv"`,
`variable_part=null` and `table_kind="localization"`. Exact-name collection
automatically appends the source ROI directory to destination filenames, exactly
as Traceratops does. Explicit `rename=true` also works for variable-name collection.
One call collects one table kind; a trace and localization collection need two calls.

**Native semantics:** immediate subdirectories are independent collection units;
matching is recursive within each unit. `variable_part` occurs exactly once in the
example and denotes a fixed-length substring, not a numeric wildcard. ROI-92 and
ROI-93 match together; ROI-100 does not match that example. The wrapper does not
invent different matching rules or resolve ambiguous masks. Missing/ambiguous
matches and filename collisions fail without publication. Force-skipping is always
false and is not exposed as a parameter. Mixed-width panels may therefore fail;
review the collection design rather than treating them as complete.

## Safety, validation and provenance

Roots use the existing `CHROMATIN_EXPERIMENT_ROOTS` administrator allowlist. Set
`CHROMATIN_COLLECTION_OUTPUT_DIR` outside experimental inputs. It defaults to
`<CHROMATIN_TRACE_OUTPUT_DIR>/collections`, or `./results/collections` otherwise.
Callers cannot supply a destination or overwrite an existing dataset.

The adapter creates a private temporary snapshot of matching regular ECSV inputs,
preserving original relative paths and ROI directory names. It uses native
`build_pattern`/`FilePattern.matches`; actual selection, ambiguity, missing-file,
collision, renaming and collection decisions are delegated to native
`collect_files`. A final native scan and `dest_name` associate outputs with sources.
The original files are not passed as writable destinations or changed.

This extra snapshot prevents native recursive traversal from following unrelated
experiment links or reading excluded data. Matching file symlinks and immediate
ROI-directory symlinks fail. Other links are skipped and counted; `full_pwd`,
`PWD_comparison`, `.git` and `.venv` trees are excluded without reading their
contents. Equivalence is defined for this explicit eligible-input scope, not for
files hidden inside excluded trees. Non-numeric immediate directories and duplicate
normalized ROI folders fail rather than silently dropping collection units.

ECSV files must have the Step 0 required columns for the requested kind. Nonempty
tables must contain the source folder's ROI identifier. Empty but valid tables are
retained and marked `empty_table`; their ROI provenance comes from the folder,
not an invented observation. No biological thresholds or filters are introduced.
Source and destination bytes, rows and columns are verified; byte identity also
preserves all coordinates, identifiers and metadata. Sources are rehashed before
publication to detect concurrent changes. Native stdout/stderr stays in `native.log`,
never in the MCP protocol output.

Limits: 100,000 traversal entries, depth 12, 256 selected files, 100 MB per file and
1 GB selected bytes. Astropy parsing is sequential but in memory; these limits are
not an OS resource sandbox. Do not edit sources during collection. Input snapshots
add I/O and temporary disk space; keep sufficient free space. Additional users or
processes running as the same OS user are not isolated by these application checks.

Only fully verified outputs are atomically renamed into the final run directory.
Temporary copies are cleaned on errors; failure JSON contains the error/native log.
`status=ERROR` is the structured runtime-failure convention; invalid MCP arguments
also produce MCP protocol errors. A failure to write failure telemetry may leave
`failure_path=null`, while still returning the original error. No partial collection
is advertised as successful.

## Output contract

```text
<collection-output>/<run_id>/<native destination filenames>.ecsv
<collection-output>/<run_id>/manifest.json
<collection-output>/<run_id>/native.log
<collection-output>/<failed_run_id>.failure.json  # failures only, when writable
```

The full manifest includes source paths, original ROI folders, normalized ROI IDs,
rows/columns, original size/mtime/SHA-256, destination paths/checksums, native module
hash/version, parameters and excluded-input counts. It is the authoritative
source-to-output mapping. The MCP result includes counts, at most ten file previews,
`files_truncated`, manifest path/hash and execution time. Long previews are reduced
to keep structured responses bounded around 12 KB; full evidence stays local.
`structured_response_bytes` measures only Pydantic JSON, not JSON-RPC framing or
actual model tokens. The benchmark separately records full serialized MCP results.

Every result has `phase=collection_only` and a stop/review instruction. It neither
approves downstream processing nor calls Pearson, merge, localization merge or
analyzers. The separately invoked Pearson wrapper is documented in [Pearson QC](trace-pearsons.md);
merge/analyzer pipeline wrappers remain future work. Existing unrelated
scientific tools remain for compatibility; collection does not invoke them.

## Reproducible benchmark

Use the already isolated Agents SDK benchmark environment documented in
`chromatin-trace-mcp/benchmarks/agent_step0/README.md`. Save a private configuration
outside Git with `server_command`, `server_cwd`, `server_env.PYTHONPATH`,
`experiment_root` and `arguments` matching the tool input above. Point it at narrow
read-only ECSV copies, not full image/matrix directories. `PYTHONPATH` must resolve
the MCP package and the validated Traceratops version. No key belongs in this file.

```sh
/path/to/agent-env/bin/python chromatin-trace-mcp/benchmarks/benchmark_collection.py \
  --config /private/collection.local.json --output /private/new-benchmark-run
```

Three repeats compare direct native copying, real MCP invocation and the real SDK
Runner with an explicitly scripted Model. Copies and final typed answers are scored
against direct native file hashes/row counts. Scripted routing is plumbing evidence,
not autonomous AI evidence. Native timing covers copying only; the MCP additionally
snapshots, parses, hashes, validates and writes provenance. It is not a like-for-like
measure of transport overhead. Server startup is outside these tool timings.

For live trials, privately configure `OPENAI_API_KEY`, choose an accessible model
and add `--live --model YOUR_MODEL`. Every trial uses a fresh Agent/conversation;
the model sees requested inputs, never expected output counts/hashes. Discovery and
dispatch expose only collection on the authorized root, capped at three calls and
six turns. Provider requests and tokens come from the existing usage recorder;
missing measurements remain null. Tracing and response storage are disabled. Live
input paths and outputs can reach the provider; review them before opting in.
Do not claim live accuracy or actual token usage from the scripted runs. No prices
are assumed, so monetary cost is not measured. Stop after the collection report.
