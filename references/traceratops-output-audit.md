# Native Traceratops output audit

Audited Traceratops 1.0.1 at locked source commit
`261a48fe92498abcb154891fe6e5a5ca8219b610`. The separate development checkout
was at `be1821037848bd95059f46381444815a9421c23d`; it was not used for these runs.
The package lock resolves MCP 2.2.0, while the available test runtime used MCP
2.3.0 (within the declared >=2.1,<3 range). This is not a full frozen-environment
installation test. No backend files or experimental inputs were modified.

`chromatin-trace-mcp/benchmarks/audit_traceratops_outputs.py` inspected signatures
and ran each native CLI on two generated, seeded fixtures: 180 trace rows and
180 localization rows per fixture. All six completed with exit code 0 using
PNG defaults and safe isolated output directories. This is an output smoke audit,
not a validation of every scientific measurement or a Step 1 MCP implementation.
A portable machine-readable summary is in `benchmarks/native_output_audit.json`.

## Inputs, outputs and side effects

| Tool | Verified interface | Visual outputs | Numerical / machine-readable outputs | Side effects / gaps |
|---|---|---|---|---|
| collect_files | collect_files(root: Path, example_file: str, copy_to: Path, variable_part: str\|None=None, force=False, rename=False); CLI --root, --example-file, --copy-to, --variable-part, --force, --rename | None | Returns copied Path list; copies ECSV inputs | Creates destination and copies files; no persistent source-to-destination JSON manifest |
| trace_pearsons | CLI --input <files> or --pipe; --output, --vmin, --vmax, --output_format, --verbose. Native accumulate_distances(table), compare_distance_maps(maps), plot_correlation_matrix(files,matrix,output_filename,vmin,vmax) | trace_correlation_matrix.png (or selected format) | trace_correlation_matrix.npy; native comparison function returns file order plus correlation array | CLI prints matrix only with verbose; no JSON/CSV label manifest. Numeric NPY should be reused, not recovered from pixels |
| trace_merge | CLI stdin paths via --pipe (default true); --traces, --name, --folder, --verbose. load_traces(trace_files, verbose=False) returns ChromatinTraceTable | None | merged_traces.ecsv; smoke result 360 rows | Creates output directory, writes merged table/comments; future wrapper must check identity/ROI provenance and collision policy |
| localization_merge | run(p) with loc_files, outputFolder, output_file. CLI reads stdin, --output_file, --output_folder | None | merged_localizations.ecsv; smoke result 360 rows | Creates directory and writes table/comments; no explicit JSON provenance manifest |
| trace_analyzer | process_traces(p) / analyze_trace(trace,trace_file,plotXYZ=False,format='png',neighbor_distance_range='1'); CLI --input or --pipe, --rootFolder, --plotXYZ, --output_format, --neighbor_distance_range | Five observed plots: trace statistics, barcode detection, first-neighbor distances, relative barcode frequencies, KDE projections; optional XYZ plot is separate | CLI prints selected means/counts. plot_neighbor_distances returns six mean/std arrays/scalars, but analyze_trace returns None. No newly emitted numerical table in this smoke run | Writes beside input basename. Existing input copy is not a generated numerical result. Internal barcode/detection arrays are not exposed as files |
| localization_analyzer | run(p) with localization_file, output_file, format; CLI --localization_file, --output_file, --output_format/--format | One multi-panel localization_qc.png in smoke run; PNG/SVG/PDF supported | No new numerical file; run and plot_distribution_fluxes return None | Loads via LocalizationTable, writes figure. Existing MCP wrapper returns row/barcode counts, terminal text and figure artifacts, but no distribution table |

The existing localization wrapper correctly calls native `run` and is retained,
not duplicated. It opens the localization table separately for wrapper counts,
then native run reads it again. This could be optimized upstream later, after an
API contract is agreed, without duplicating scientific calculations in MCP.

## Relevant implementation limitations

- collect_files variable matching uses a **fixed-length** substring, not integer
  ROI normalization. Different padding/lengths can fail its matching policy;
  Step 0 handles padding independently and does not copy files.
- trace_pearsons constructs one coordinate per barcode per Trace_ID using a Python
  dictionary. Repeated spots overwrite earlier spots. A future wrapper must not
  silently apply this to ambiguous multi-spot groups; agree a scientific policy.
- Native Pearson matches barcode-pair keys, not independently verified genome
  intervals. It is insensitive to global scaling. No acceptance threshold or
  automatic merge approval can be inferred from a large correlation.
- Native Pearson plot color limits are hardcoded 0–1 despite vmin/vmax arguments;
  negative values remain in the NPY array. Use numerical output for interpretation.
- trace_merge's --pipe defaults true and the code checks it before --traces;
  stdin lists are the verified route in this audit. Folder-option behavior needs
  upstream clarification before wrapping it.
- localization_merge's loader only initializes its result for more than one file;
  single-file behavior is an apparent source-level gap, not supported behavior
  established by this two-file smoke run.
- trace_analyzer derives a basename using `trace_file.split('.')[0]`. An initial
  smoke invocation with a dotted absolute parent directory tried to write a plot
  outside its intended directory and was blocked. A retry with a **relative input
  basename and isolated child-process working directory** succeeded. This was a
  path-handling issue, not a need for broader write permission. Future wrappers
  must preserve safe output placement or request an upstream pathlib fix.
- Current localization plotting can skip legacy column layouts with a warning;
  a future wrapper should verify an actual artifact, as the existing wrapper does.

## Minimal backward-compatible upstream proposals (not implemented)

1. Preserve figures and default CLI behavior; add optional summary/table destinations
   or structured return objects to the analyzers.
2. Save already-calculated barcode statistics, barcode detection estimates and
   uncertainty, neighbor statistics and localization distribution/count arrays.
   Do not reimplement their scientific formulas in MCP or read values from pixels.
3. Add Pearson labels/parameters/source provenance alongside its existing NPY array;
   fix its plotting limits independently from scientific calculations.
4. Make trace_analyzer output-directory and basename handling explicit and safe.
5. Return source/destination mappings from collection/merge and resolve the noted
   file-count/CLI edge cases with native tests.

## Future workflow, intentionally not implemented

Collect files with native collect_files; compare with native trace_pearsons;
show numerical QC and stop for explicit user approval tied to files, report and
parameters; merge selected trace/localization tables using native merge tools;
analyze them through trace_analyzer and the existing localization_analyzer wrapper.
Persisted approval states and numerical-output extensions belong to a later milestone.
No experimental Step 1 processing was executed in this implementation.
