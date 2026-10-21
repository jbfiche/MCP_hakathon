# Hi-M diagnosis assistant

This repository contains the local Chromatin Trace MCP and Chromatin Report MCP.
The assistant supports reproducible Hi-M data diagnosis, quality control, filtering,
comparison, and reporting.

Keep this file limited to stable repository and laboratory conventions. Experiment-
specific paths, barcode meanings, controls, thresholds, and renamed barcodes belong
in that experiment's `experiment.yaml`.

## Repository structure

- `chromatin-trace-mcp/`: traceratops-backed analysis MCP for dataset registration,
  inspection, comparison, duplicate statistics, filtering, matrices, and localization QC.
- `chromatin-report-mcp/`: reporting MCP for Markdown, HTML, and PDF comparison reports.
- `skills/him-data-diagnosis/SKILL.md`: workflow for localization QC, data-informed
  SNR sweeps, filtering comparisons, and diagnosis reports.
- Each MCP repository has its own `pyproject.toml`, tests, and terminal checker.

## Data safety

- Treat raw data and pyHiM outputs as read-only.
- Write generated artifacts only to the output directory configured for the run or MCP.
- Never put complete trace, localization, image, or PWD tables into the conversation.
  Use MCP tools to return compact summaries and artifact paths.
- Never read, copy, or process the very large `full_pwd/` or `PWD_comparison/` tables
  unless the user explicitly requests that work and the relevant workflow is designed
  for it.
- Do not commit raw data, machine-specific paths, credentials, or experiment-specific
  configuration files containing server paths.

## Data locations

Common local data may be under `/home/jb/Desktop/Hackaton/data/`.
On the lab compute setup, raw data and pyHiM outputs may also be mounted under:

- `/mnt/aguila/rawData_<YEAR>/Experiment_<N>_<Name>_<date>/`
- `/mnt/aguila/AnalyzedData_<YEAR>/Experiment_<N>_<Name>_<date>/`

Use the paths provided by the experiment configuration rather than guessing paths.
Tracing and traceratops analysis run locally on the configured analysis host. Upstream
deconvolution, localization, and cellpose jobs on other compute systems are outside
the scope of this assistant unless explicitly requested.

## Hi-M scientific conventions

- Coordinates are in microns only when confirmed by ECSV metadata such as `xyz_unit`.
- `Spot_ID` in trace tables corresponds to `Buid` in localization tables. Join quality
  metrics on this identifier, never on barcode number alone.
- A `Trace_ID` represents a segmented nucleus, not necessarily one chromosome.
  Distances computed from a nucleus-level trace must be described accordingly.
- Up to two detections per locus may be expected because of the two alleles.
  More than two detections are an ambiguity requiring review.
- Repeated trace/barcode groups are diagnostic observations, not automatically errors.
  Report their multiplicity and preserve the user's ability to decide on filtering.
- Barcode numbers come from the experiment BED file and may be renamed or assigned
  special control meanings in the experiment Excel file. Read `experiment.yaml` before
  interpreting barcode identities.

## MCP workflow

- For experiment-wide Step 0 requests prefer `run_experiment_validation` and compact
  output. Use cached `read_validation_details` to inspect further evidence.
  Trace saves JSON evidence and Markdown/HTML Step 0 reports in that same call.
  Return artifact paths; retrieve cached summaries through `get_validation_summary`.
  The report server is reserved for richer comparison/PDF reporting.
- Step 0 uses configured mask-based traces; ambiguous masks require an explicit
  policy. Expected ROI/barcode sets must come from authoritative experiment metadata.
- Explicitly requested Step 1a.1 uses `collect_files`, backed by native Traceratops.
  Configure `CHROMATIN_COLLECTION_OUTPUT_DIR` outside inputs; retain manifest/ROI
  provenance and stop after collection. No automatic Pearson/merge processing.
- Requested Step 1a.2 uses `trace_pearsons` on validated collection run IDs and
  manifest hashes. Preserve native numeric results/figures, return the QC report
  and stop for user review. No scientific acceptance thresholds or merging.
- Routine Pearson reporting stays in trace: compact agent response, bounded human
  preview, complete local artifacts. Formatting is pure/modular; use the report
  server later for multi-analysis/experiment composition or rich exports, not ROI
  count alone. See `references/pearson-reporting.md`; no extra call is needed now.
- Step 1a.3 uses `review_pearson_approval` for status and trusted host form review.
  Only the human form response may approve/reject and select datasets. Ordinary
  model arguments cannot grant approval. Changed evidence requires fresh review;
  See `references/scientific-approval.md`.
- Step 1b.1 `trace_merge` requires the exact existing human-approved selection
  and delegates to native Traceratops on verified snapshots. Recheck approval before
  publication, preserve row/ROI/metadata provenance, and stop. See `references/trace-merge.md`.
- Step 1b.2 `localization_merge` maps validated localization collections to the exact
  approved tracing selection using original experiment/source ROI provenance. Check
  localization hashes before execution and publication; reject ambiguous mappings
  and colliding source ROI IDs. Human approval covers ROI selection, not localization
  bytes absent from Pearson review. See `references/localization-merge.md`.
- Future per-ROI Step 0 and merged pre-filtering Step 1c statistics reuse existing
  `trace_stats`; these reporting workflows are not implemented. Read
  `references/trace-stats-integration.md` before planning them. No analyzers or filtering
  are added by localization merging.
- Step 0 is validation only. Do not invoke collection, Pearson, merge or analyzer
  processing automatically. Scientific processing must delegate to Traceratops.
- Keep provider-reported client token usage separate from server-side bytes, timing
  and estimates. Scripted transport controls are not live agent benchmarks.
- Later merging requires explicit human approval tied to the relevant QC report,
  input files and parameters. Changed inputs/parameters require fresh approval.
- See `references/step0.md` and `references/step0-benchmarking.md` for interfaces,
  configuration and measurement limits. Existing QC tools remain available.

- Use `skills/him-data-diagnosis/SKILL.md` for QC, SNR-threshold, filtering-comparison,
  and diagnosis-report requests.
- Register new datasets through the Chromatin Trace MCP rather than bypassing its
  validation with ad-hoc analysis scripts.
- Use `compare_datasets` for structural comparison of two registered datasets.
- Use `duplicate_statistics` for the 0/1/2/>2 multiplicity summary. For trace tables,
  the grouping key is `(Trace_ID, Barcode #)`; for localization tables it is
  `(ROI #, CellID #, Barcode #)`.
- Use filtering, matrix, and localization-QC MCP tools when they cover the requested
  operation. Record tool parameters, retained-row counts, warnings, and artifact paths.
- Use the Report MCP for Markdown, HTML, and PDF reports. Pass the complete structured
  comparison result to the report tool; the report MCP formats results and does not
  recalculate scientific measurements.
- Never claim that an analysis or report succeeded without checking the returned result
  and generated artifact.

## Decision and approval rules

- Do not exclude ROIs, barcodes, traces, or thresholds without explicit user approval.
- Do not interpret technical compatibility as biological significance.
- Distinguish clearly between observed data-quality warnings, proposed filtering, and
  decisions the user has approved.
- Preserve the original input files when filtering or cleaning; write derived files to
  isolated output directories.
- If a requested workflow would require a missing localization file, metadata file, or
  experiment configuration, report the limitation instead of silently substituting data.

## Verification

Run tests from the relevant MCP repository:

```text
cd chromatin-trace-mcp && uv run pytest
cd chromatin-report-mcp && uv run pytest
```

Use the local terminal checker when useful:

```text
uv run python scripts/check_server.py <tool>
```

For PDF reports, render the generated PDF and inspect the pages before delivery.
