# Development log

## Step 1 — Define the boundary

The report server does not read trace files or calculate quality metrics. Its input
is the typed structured result produced by the analysis MCP. This makes provenance
clear and prevents the presentation layer from silently changing scientific logic.

## Step 2 — Define the MCP contract

`write_comparison_report` accepts nested Pydantic models matching
`compare_datasets`. MCP therefore publishes a precise input schema that an LLM host
can inspect. The typed `ReportArtifact` output records the file path, format, byte
size, comparison status, and UTC generation time.

## Step 3 — Write reports safely

Reports receive unique filenames and are written below
`CHROMATIN_REPORT_OUTPUT_DIR`. Markdown and self-contained HTML are supported.
Every report preserves the supplied reasons, warnings, barcode differences,
quality metrics, optional scientist notes, and an explicit interpretation boundary.
It now also has dedicated `Summary of data`, `Recommendations`, and `Conclusion`
sections. Recommendations and conclusions may be supplied by the scientist; when
omitted, conservative text is derived from compatibility status and warnings.

## Step 4 — Publish and test the result

The latest report is exposed as the `report://latest` resource. In-process MCP
tests verify the published schemas and both output formats. A terminal checker and
Inspector launcher provide beginner-friendly manual testing paths.
