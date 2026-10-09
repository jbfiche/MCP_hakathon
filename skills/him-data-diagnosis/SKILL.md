---
name: him-data-diagnosis
description: Diagnose Hi-M trace and localization datasets, choose data-informed SNR thresholds, compare filtering effects, and prepare reproducible reports.
metadata:
  short-description: Hi-M QC, SNR sweeps, and filtering comparisons
---

# Hi-M data diagnosis

Use this skill for requests involving localization QC, SNR threshold selection,
filtering advice, duplicate review, trace/localization comparison, or a diagnosis
report. Keep the large input tables local and return compact structured summaries and
artifact paths.

## Required workflow

1. Register each trace file with its associated localization file through the
   Chromatin Trace MCP. Do not infer pairings from barcode numbers alone.
2. Call `localization_quality_summary` for each dataset before selecting SNR values.
   Inspect the SNR range and quantiles, missing values, row count, and intensity
   distributions.
3. Select a small, justified threshold set. The usual starting point is `[5, 7.5, 10]`
   when those values are represented in the data. If they are outside the observed
   range or leave no useful retained data, use nearby data-informed values based on
   the reported quantiles. Use no more than five thresholds unless the user asks for
   a larger exploration.
4. Call `snr_filter_sweep` with explicit thresholds. It evaluates localization
   retention, trace retention, intensity quantiles, and duplicate multiplicity for
   both datasets, and writes a JSON summary and plot without changing inputs.
5. Interpret the results conservatively. State both the retained fraction and the
   distribution shift. A change in intensity after SNR filtering is a selection
   effect unless the experimental design supports a biological interpretation.
6. Use `duplicate_statistics` or the sweep's per-threshold duplicate result to report
   multiplicity. Up to two detections per locus may be expected; more than two is an
   ambiguity for review, not an automatic deletion rule.
7. Only create filtered data files after the user approves the threshold and filtering
   policy. Preserve original files and write derived files into an isolated output
   directory. Pass the structured comparison and sweep summaries to the Report MCP
   for Markdown, HTML, or PDF output.

## Join and interpretation rules

- Join localization `Buid` to trace `Spot_ID` when propagating localization filtering
  to trace rows.
- Do not use barcode number alone as the join key.
- Report unmatched localization identifiers rather than silently dropping them.
- Treat row counts, retained traces, intensity quantiles, and duplicate counts as
  technical QC measurements; do not call them biological effects without supporting
  experimental context.
- Never put complete ECSV tables into the conversation.

## Expected outputs

A useful diagnosis should include:

- the selected thresholds and why they were chosen;
- localization rows and percentage retained at each threshold;
- retained Buid, barcode, ROI, cell, and trace counts;
- `mean_intensity` and `flux` quantiles, preferably p10, median, and p90;
- duplicate multiplicity counts for 0, 1, 2, and more than 2 extra occurrences;
- paths to the JSON summary and plots;
- limitations, especially missing localization files, missing joins, or thresholds
  outside the observed SNR distribution.
