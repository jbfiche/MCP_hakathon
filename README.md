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
