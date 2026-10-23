# MCP_hakathon


## Incremental development roadmap

Step 0 per-ROI statistics, both merges and Step 1c merged statistics are owner-approved.
Native trace_analyzer integration is implemented for review; see
[the analyzer reference](references/trace-analyzer.md) and
[validation report](TRACE_ANALYZER_REPORT.md). Actual inputs must satisfy grouping,
unit and genomic metadata requirements. Next, after separate approval, verify the
existing localization_analyzer wrapper on merged unfiltered localizations. Only
after both analyzer stages are valid will chromatin-report-mcp compose the
comprehensive pre-filtering report. Filtering follows as a separate decision.
No localization-analysis integration, comprehensive report or filter is added here.

Genomic annotation is available through `trace_genomic_coordinates` before the analyzer, using native five-column BED barcode replacement and host-confirmed assembly evidence. See [genomic annotation](references/genomic-annotation.md). Original merges, baselines and localization identifiers remain unchanged.

The existing `localization_analyzer` supports approved, checksum-verified localization merges while retaining its registered-dataset interface. It preserves native figures, numerical plot evidence, original barcode IDs and source integrity. See [localization analyzer](references/localization-analyzer.md). Comprehensive reporting and filtering remain separately approved future work.

## Comprehensive pre-filtering experiment QC

The report server now exposes `generate_experiment_qc_report` for a host-provisioned
manifest ID/checksum after both native analyzers. One call verifies the saved
scientific evidence and current approval, then formats HTML without recalculation.
Simple Step 0/Pearson reports stay in trace. See [configuration and evidence rules](references/comprehensive-qc-report.md).
