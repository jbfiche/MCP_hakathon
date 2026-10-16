# Chromatin Report MCP

This is the presentation half of the chromatin analysis workflow. It receives the
structured result returned by the analysis MCP's `compare_datasets` tool and writes
a reproducible Markdown, HTML, or PDF report. It does not run traceratops or recalculate
scientific measurements. Reports include a summary of the input data, compatibility
and warnings, recommendations, a conclusion, provenance notes and an interpretation
boundary. Recommendations and conclusions can be supplied explicitly by the scientist;
otherwise conservative text is generated from the comparison status and warnings.

## Install

From this directory:

```bash
uv sync --extra test
```

## Test from the terminal

```bash
uv run pytest -q
uv run python scripts/check_server.py
```

The second command generates a sample report through the MCP protocol. Reports go
to `CHROMATIN_REPORT_OUTPUT_DIR`, or to `reports/` by default.

## Open the Inspector

```bash
./scripts/start_inspector.sh
```

In **Tools**, choose `write_comparison_report` for Markdown/HTML or
`write_comparison_pdf` for PDF. Their `comparison` input has the same schema as the
analysis server's `compare_datasets` output. After writing a report,
the **Resources** tab exposes it as `report://latest`.

## How the two MCPs work together

An MCP host connected to both servers performs the orchestration:

1. Call `compare_datasets` on the Chromatin Trace MCP.
2. Pass its complete structured result to `write_comparison_report` or
   `write_comparison_pdf` on this MCP.
3. Present the generated report path to the user.

The report tool accepts optional `recommendations` and `conclusion` text. Use these
fields for scientist-approved next steps, thresholds or interpretation. Pass the complete
structured result from `snr_filter_sweep` as the optional `sweep` argument to
`write_comparison_pdf`; the PDF will then embed the retention/intensity figure, generate
a duplicate-multiplicity figure, and include formatted per-threshold QC tables. Every
generated report contains `Summary of data`, `Recommendations`, and `Conclusion` headings.

The MCP servers do not call each other directly. This separation keeps scientific
calculation in the traceratops-backed server and document formatting here.

## Step 0 Data Quality Reports

The trace server saves JSON evidence and Markdown/HTML Data Quality Reports in
one validation call. Use its `human_report_path` or `html_report_path`, or retrieve
those paths with trace `get_validation_summary`. No reporting server is required
for Step 0. The report server retains the richer comparison/PDF tools. See the
[Step 0 interface](../references/step0.md) for artifact paths and migration details.
