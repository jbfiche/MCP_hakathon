"""Create reproducible reports from chromatin analysis MCP results."""

import html
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

REPORT_OUTPUT_ENV = "CHROMATIN_REPORT_OUTPUT_DIR"
LATEST_REPORT_URI = "report://latest"
_latest_report: Path | None = None

mcp = MCPServer(
    "Chromatin Report Writer",
    instructions=(
        "Writes reproducible Markdown or HTML reports from structured results "
        "returned by a chromatin-analysis MCP server and can draft the same "
        "comparison as a PDF. It does not recalculate or "
        "reinterpret scientific measurements. For comprehensive pre-filtering QC, "
        "use generate_experiment_qc_report with a host-provisioned manifest reference."
    ),
)


class DatasetQualityMetrics(BaseModel):
    dataset_name: str
    trace_row_count: int
    trace_count: int | None
    roi_count: int | None
    barcode_count: int | None
    barcodes: list[str]
    median_rows_per_trace: float | None
    coordinate_missing_fraction: float | None
    duplicate_trace_barcode_rows: int | None
    localization_row_count: int | None
    localization_barcode_count: int | None
    median_localization_snr: float | None


class DatasetComparison(BaseModel):
    """Contract matching the analysis MCP's compare_datasets output."""

    first: DatasetQualityMetrics
    second: DatasetQualityMetrics
    status: Literal["compatible", "compatible_with_warnings", "not_comparable"]
    comparable: bool
    shared_barcodes: list[str]
    only_in_first: list[str]
    only_in_second: list[str]
    same_columns: bool
    columns_only_in_first: list[str]
    columns_only_in_second: list[str]
    coordinate_unit_first: str | None
    coordinate_unit_second: str | None
    reasons: list[str]
    warnings: list[str]


class NumericDistribution(BaseModel):
    column: str
    finite_count: int
    missing_or_nonfinite_count: int
    minimum: float | None
    p10: float | None
    median: float | None
    p90: float | None
    maximum: float | None


class DuplicateMultiplicityStats(BaseModel):
    table_kind: Literal["trace", "localization"]
    grouping_columns: list[str]
    row_count: int
    unique_group_count: int
    zero_duplicate_groups: int
    one_duplicate_groups: int
    two_duplicate_groups: int
    more_than_two_duplicate_groups: int
    duplicate_rows: int
    maximum_group_size: int


class CopyMultiplicityRetention(BaseModel):
    multiplicity: Literal["1", "2", "3", "4+"]
    groups_before: int
    groups_after: int
    rows_before: int
    rows_retained: int
    rows_dropped: int


class SNRFilterPoint(BaseModel):
    threshold: float
    localization_rows_before: int
    localization_rows_retained: int
    localization_retained_fraction: float
    unique_buids_retained: int
    unique_barcodes_retained: int
    unique_rois_retained: int
    unique_cells_retained: int | None
    trace_rows_before: int
    trace_rows_retained: int
    trace_retained_fraction: float
    unique_traces_retained: int
    unmatched_localization_buids: int
    intensity_distributions: list[NumericDistribution]
    duplicate_statistics: DuplicateMultiplicityStats
    trace_copy_multiplicity: list[CopyMultiplicityRetention]


class SNRFilterDatasetResult(BaseModel):
    dataset_name: str
    localization_file: str
    trace_file: str
    points: list[SNRFilterPoint]


class SNRFilterSweep(BaseModel):
    thresholds: list[float]
    intensity_columns: list[str]
    first: SNRFilterDatasetResult
    second: SNRFilterDatasetResult
    artifacts: list[dict[str, object]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ReportArtifact(BaseModel):
    path: str
    format: Literal["markdown", "html"]
    size_bytes: int
    comparison_status: str
    generated_at_utc: str


class PdfReportArtifact(BaseModel):
    """Metadata for a generated PDF comparison report."""

    path: str
    format: Literal["pdf"]
    size_bytes: int
    comparison_status: str
    generated_at_utc: str


def _output_directory() -> Path:
    raw_path = os.environ.get(REPORT_OUTPUT_ENV)
    directory = Path(raw_path).expanduser() if raw_path else Path.cwd() / "reports"
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ToolError(f"Could not create report directory {directory}: {exc}") from exc
    return directory.resolve()


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-.")
    return stem[:80] or "chromatin-comparison"


def _display(value: object) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _markdown_list(items: list[str], empty_message: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else f"- {empty_message}"


def _default_recommendations(comparison: DatasetComparison) -> str:
    """Give conservative next steps without claiming a biological result."""
    recommendations = []
    if comparison.only_in_first or comparison.only_in_second:
        recommendations.append(
            "For a matched comparison, analyze the shared barcode panel first and report dataset-specific barcodes separately."
        )
    if comparison.warnings:
        recommendations.append(
            "Review each warning and document the filtering or quality-control decision before interpreting differences."
        )
    if comparison.first.localization_row_count is None or comparison.second.localization_row_count is None:
        recommendations.append(
            "Add localization tables or another validated quality measure before making localization-quality claims."
        )
    recommendations.append(
        "Record the analysis parameters, software version, input paths and retained-row counts for reproducibility."
    )
    return _markdown_list(recommendations, "No additional recommendation was generated.")


def _default_conclusion(comparison: DatasetComparison) -> str:
    if comparison.status == "not_comparable" or not comparison.comparable:
        return (
            "The datasets should not be treated as directly comparable under the checks performed. "
            "Resolve the listed incompatibilities before drawing conclusions."
        )
    if comparison.status == "compatible_with_warnings":
        return (
            "The datasets are structurally comparable with qualifications. The reported warnings "
            "must be addressed or carried into the interpretation; this report does not establish "
            "biological significance."
        )
    return (
        "The datasets pass the reported structural compatibility checks. This technical result "
        "does not establish biological equivalence or biological significance."
    )


def _markdown_report(
    title: str,
    comparison: DatasetComparison,
    generated_at: str,
    notes: str | None,
    recommendations: str | None,
    conclusion: str | None,
) -> str:
    first = comparison.first
    second = comparison.second
    metric_rows = [
        ("Trace rows", first.trace_row_count, second.trace_row_count),
        ("Traces", first.trace_count, second.trace_count),
        ("ROIs", first.roi_count, second.roi_count),
        ("Barcodes", first.barcode_count, second.barcode_count),
        ("Median rows per trace", first.median_rows_per_trace, second.median_rows_per_trace),
        ("Missing coordinate fraction", first.coordinate_missing_fraction, second.coordinate_missing_fraction),
        ("Repeated trace/barcode rows", first.duplicate_trace_barcode_rows, second.duplicate_trace_barcode_rows),
        ("Localization rows", first.localization_row_count, second.localization_row_count),
        ("Localization barcodes", first.localization_barcode_count, second.localization_barcode_count),
        ("Median localization SNR", first.median_localization_snr, second.median_localization_snr),
    ]
    table = "\n".join(
        f"| {name} | {_display(a)} | {_display(b)} |" for name, a, b in metric_rows
    )
    note_section = f"\n## Scientist notes\n\n{notes.strip()}\n" if notes and notes.strip() else ""
    recommendations_section = recommendations.strip() if recommendations and recommendations.strip() else _default_recommendations(comparison)
    conclusion_text = conclusion.strip() if conclusion and conclusion.strip() else _default_conclusion(comparison)
    return f"""# {title}

Generated: {generated_at}  
Comparison status: **{comparison.status}**  
Structurally comparable: **{'Yes' if comparison.comparable else 'No'}**

## Summary of data

This report compares the two named datasets below using the structured result supplied by the chromatin analysis MCP. File paths and experimental provenance are not included in the comparison payload; provide them in scientist notes when they are needed for the record.

| Metric | {first.dataset_name} | {second.dataset_name} |
| --- | ---: | ---: |
{table}

The analysis used the trace and, when available, associated localization measurements represented in the table. The report preserves the source MCP measurements and does not recalculate them.

## Compatibility assessment

{_markdown_list(comparison.reasons, 'No reason supplied.')}

## Warnings

{_markdown_list(comparison.warnings, 'No warnings reported.')}

## Barcode comparison

- Shared barcodes ({len(comparison.shared_barcodes)}): {', '.join(comparison.shared_barcodes) or 'None'}
- Only in {first.dataset_name}: {', '.join(comparison.only_in_first) or 'None'}
- Only in {second.dataset_name}: {', '.join(comparison.only_in_second) or 'None'}

## Schema and coordinates

- Identical trace columns: {'Yes' if comparison.same_columns else 'No'}
- Coordinate unit for {first.dataset_name}: {_display(comparison.coordinate_unit_first)}
- Coordinate unit for {second.dataset_name}: {_display(comparison.coordinate_unit_second)}
- Columns only in {first.dataset_name}: {', '.join(comparison.columns_only_in_first) or 'None'}
- Columns only in {second.dataset_name}: {', '.join(comparison.columns_only_in_second) or 'None'}
{note_section}
## Recommendations

{recommendations_section}

## Conclusion

{conclusion_text}

## Interpretation boundary

This report reproduces the technical comparison supplied by the analysis MCP. It does not establish biological significance or replace review of experimental design and quality-control thresholds.
"""


def _html_report(markdown: str, title: str) -> str:
    """Create a safe, readable HTML rendering without adding a Markdown dependency."""
    escaped = html.escape(markdown)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body {{ max-width: 1000px; margin: 2rem auto; padding: 0 1rem; font: 16px/1.5 system-ui, sans-serif; color: #17202a; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #f7f9f9; border: 1px solid #d5dbdb; padding: 1.25rem; border-radius: .5rem; }}
</style>
</head>
<body><pre>{escaped}</pre></body>
</html>
"""


def _sweep_plot_paths(sweep: SNRFilterSweep) -> list[Path]:
    """Return available analysis MCP figures in report order."""
    order = {
        "snr_filter_sweep.png": 0,
        "snr_filter_histogram_mean_intensity.png": 1,
        "snr_filter_histogram_flux.png": 2,
        "snr_filter_copy_multiplicity.png": 3,
    }
    paths = []
    for artifact in sweep.artifacts:
        raw_path = artifact.get("path")
        if raw_path and Path(str(raw_path)).name in order:
            path = Path(str(raw_path)).expanduser()
            if path.is_file():
                paths.append(path)
    return sorted(paths, key=lambda path: order[path.name])


def _write_duplicate_plot(sweep: SNRFilterSweep, output_path: Path) -> None:
    """Create a clear per-threshold duplicate multiplicity figure."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ToolError(
            "Duplicate-statistics figures require matplotlib. Install the report MCP "
            "dependencies and restart the server."
        ) from exc

    categories = ["1", "2", "3", "4+"]
    colors = ["#D9E6F2", "#9FC2E3", "#5D8FC5", "#234F84"]
    figure, axes = plt.subplots(2, 2, figsize=(11, 8.2), squeeze=False)
    for row, dataset in enumerate((sweep.first, sweep.second)):
        composition_axis, fate_axis = axes[row]
        x = list(range(len(dataset.points)))
        bottom = [0.0] * len(dataset.points)
        for category_name, color in zip(categories, colors, strict=True):
            values = []
            for point in dataset.points:
                item = next(item for item in point.trace_copy_multiplicity if item.multiplicity == category_name)
                total = sum(part.groups_after for part in point.trace_copy_multiplicity) or 1
                values.append(100 * item.groups_after / total)
            composition_axis.bar(x, values, bottom=bottom, color=color, label=f"{category_name} copies")
            bottom = [left + value for left, value in zip(bottom, values, strict=True)]
        composition_axis.set_title(f"{dataset.dataset_name}: copy composition", fontsize=10, fontweight="bold")
        composition_axis.set_xticks(x, [f"SNR >= {point.threshold:g}" for point in dataset.points], rotation=20, ha="right")
        composition_axis.set_ylabel("Trace/barcode groups (%)", fontsize=8)
        composition_axis.set_ylim(0, 100)
        composition_axis.grid(axis="y", alpha=0.25)
        composition_axis.legend(fontsize=7, frameon=False)

        x = list(range(len(categories)))
        width = 0.8 / max(len(dataset.points), 1)
        for index, point in enumerate(dataset.points):
            retained = [
                item.rows_retained for item in point.trace_copy_multiplicity
            ]
            dropped = [
                item.rows_dropped for item in point.trace_copy_multiplicity
            ]
            offset = (index - (len(dataset.points) - 1) / 2) * width
            fate_axis.bar([value + offset for value in x], retained, width=width, label=f"kept, SNR >= {point.threshold:g}")
            fate_axis.bar([value + offset for value in x], dropped, width=width, bottom=retained, alpha=0.35, color="#777777", label=f"dropped, SNR >= {point.threshold:g}")
        fate_axis.set_title(f"{dataset.dataset_name}: copy fate", fontsize=10, fontweight="bold")
        fate_axis.set_xticks(x, categories)
        fate_axis.set_xlabel("Copies per trace/barcode group", fontsize=8)
        fate_axis.set_ylabel("Rows", fontsize=8)
        fate_axis.grid(axis="y", alpha=0.25)
        fate_axis.legend(fontsize=6.5, frameon=False, ncol=2)
    figure.suptitle("Trace-level copy multiplicity after SNR filtering", fontsize=13, fontweight="bold")
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def _image_flowable(path: Path, width: float, max_height: float, image_cls):
    """Scale an image without distorting it or exceeding the page."""
    from reportlab.lib.utils import ImageReader

    image_reader = ImageReader(str(path))
    image_width, image_height = image_reader.getSize()
    height = width * image_height / image_width
    if height > max_height:
        width = max_height * image_width / image_height
        height = max_height
    return image_cls(str(path), width=width, height=height, hAlign="LEFT")


def _sweep_table(sweep: SNRFilterSweep, p, make_table, small_style: str):
    """Build a compact, formatted table of all threshold-level QC values."""
    from reportlab.lib.units import mm

    rows = [[
        p("Dataset", small_style), p("SNR", small_style), p("Loc. retained", small_style),
        p("Trace retained", small_style), p("Traces", small_style),
        p("Mean intensity median", small_style), p("Flux median", small_style),
        p(">2 duplicates", small_style),
    ]]
    for dataset in (sweep.first, sweep.second):
        for point in dataset.points:
            distributions = {item.column: item for item in point.intensity_distributions}
            mean_intensity = distributions.get("mean_intensity")
            flux = distributions.get("flux")
            rows.append([
                p(dataset.dataset_name, small_style),
                p(f"{point.threshold:g}", small_style),
                p(f"{point.localization_retained_fraction * 100:.1f}%", small_style),
                p(f"{point.trace_retained_fraction * 100:.1f}%", small_style),
                p(point.unique_traces_retained, small_style),
                p(_display(mean_intensity.median if mean_intensity else None), small_style),
                p(_display(flux.median if flux else None), small_style),
                p(point.duplicate_statistics.more_than_two_duplicate_groups, small_style),
            ])
    return make_table(rows, [31 * mm, 14 * mm, 25 * mm, 25 * mm, 19 * mm, 28 * mm, 20 * mm, 22 * mm])


def _pdf_report(
    output_path: Path,
    title: str,
    comparison: DatasetComparison,
    generated_at: str,
    notes: str | None,
    recommendations: str | None,
    conclusion: str | None,
    sweep: SNRFilterSweep | None,
) -> None:
    """Render a compact, human-readable PDF from structured comparison data."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ToolError(
            "PDF generation requires the reportlab dependency. Install the report MCP "
            "with its declared dependencies and restart the server."
        ) from exc

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=27, textColor=colors.HexColor("#102A43"),
        alignment=TA_CENTER, spaceAfter=5 * mm,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle", parent=styles["Normal"], fontSize=9.5,
        leading=13, textColor=colors.HexColor("#486581"), alignment=TA_CENTER,
        spaceAfter=5 * mm,
    ))
    styles.add(ParagraphStyle(
        name="ReportH1", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=14, leading=17, textColor=colors.HexColor("#102A43"),
        spaceBefore=4 * mm, spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="ReportBody", parent=styles["BodyText"], fontSize=9,
        leading=12.5, textColor=colors.HexColor("#243B53"), spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="ReportSmall", parent=styles["BodyText"], fontSize=7.5,
        leading=9.5, textColor=colors.HexColor("#486581"),
    ))

    def p(value: object, style: str = "ReportBody") -> Paragraph:
        return Paragraph(html.escape(_display(value)), styles[style])

    def bullet(value: str) -> Paragraph:
        return Paragraph(f"- {html.escape(value)}", styles["ReportBody"])

    def make_table(rows: list[list[Paragraph]], widths: list[float]) -> Table:
        table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2EC")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return table

    first, second = comparison.first, comparison.second
    duplicate_plot: Path | None = None
    rows = [[p("Metric", "ReportSmall"), p(first.dataset_name, "ReportSmall"), p(second.dataset_name, "ReportSmall")]]
    for label, left, right in (
        ("Trace rows", first.trace_row_count, second.trace_row_count),
        ("Unique traces", first.trace_count, second.trace_count),
        ("ROIs", first.roi_count, second.roi_count),
        ("Barcodes", first.barcode_count, second.barcode_count),
        ("Median rows per trace", first.median_rows_per_trace, second.median_rows_per_trace),
        ("Missing coordinate fraction", first.coordinate_missing_fraction, second.coordinate_missing_fraction),
        ("Repeated trace/barcode rows", first.duplicate_trace_barcode_rows, second.duplicate_trace_barcode_rows),
        ("Localization rows", first.localization_row_count, second.localization_row_count),
        ("Median localization SNR", first.median_localization_snr, second.median_localization_snr),
    ):
        rows.append([p(label, "ReportSmall"), p(left, "ReportSmall"), p(right, "ReportSmall")])

    story = [
        Spacer(1, 7 * mm),
        p(title, "ReportTitle"),
        p("Chromatin dataset comparison | Generated " + generated_at, "ReportSubtitle"),
        p(f"Comparison status: {comparison.status} | Structurally comparable: {'Yes' if comparison.comparable else 'No'}"),
        p("Summary of data", "ReportH1"),
        make_table(rows, [68 * mm, 52 * mm, 52 * mm]),
        p("Compatibility assessment", "ReportH1"),
    ]
    story.extend(bullet(item) for item in comparison.reasons)
    story.append(p("Warnings", "ReportH1"))
    story.extend(bullet(item) for item in comparison.warnings) if comparison.warnings else story.append(bullet("No warnings reported."))
    story.append(p("Barcode comparison", "ReportH1"))
    story.extend([
        bullet(f"Shared barcodes ({len(comparison.shared_barcodes)}): {', '.join(comparison.shared_barcodes) or 'None'}"),
        bullet(f"Only in {first.dataset_name}: {', '.join(comparison.only_in_first) or 'None'}"),
        bullet(f"Only in {second.dataset_name}: {', '.join(comparison.only_in_second) or 'None'}"),
    ])
    story.append(p("Schema and coordinates", "ReportH1"))
    story.extend([
        bullet(f"Identical trace columns: {'Yes' if comparison.same_columns else 'No'}"),
        bullet(f"Coordinate units: {comparison.coordinate_unit_first or 'Not available'} / {comparison.coordinate_unit_second or 'Not available'}"),
        bullet(f"Columns only in {first.dataset_name}: {', '.join(comparison.columns_only_in_first) or 'None'}"),
        bullet(f"Columns only in {second.dataset_name}: {', '.join(comparison.columns_only_in_second) or 'None'}"),
    ])
    if notes and notes.strip():
        story.extend([p("Scientist notes", "ReportH1"), p(notes.strip())])
    if sweep is not None:
        story.append(p("SNR filtering and intensity distributions", "ReportH1"))
        story.append(p(
            "The analysis MCP evaluated the explicit thresholds below. The retention curve shows row loss; "
            "the histogram panels show the original distribution in grey, removed localizations in red, "
            "and retained localizations in blue.",
        ))
        sweep_plot_paths = _sweep_plot_paths(sweep)
        intensity_plot_paths = [
            path for path in sweep_plot_paths
            if path.name in {"snr_filter_sweep.png", "snr_filter_histogram_mean_intensity.png", "snr_filter_histogram_flux.png"}
        ]
        if intensity_plot_paths:
            for path in intensity_plot_paths:
                story.append(_image_flowable(path, 174 * mm, 105 * mm, Image))
        else:
            story.append(p("The analysis sweep figures were not available at report-generation time."))
        story.append(Spacer(1, 3 * mm))
        story.append(_sweep_table(sweep, p, make_table, "ReportSmall"))
        story.append(PageBreak())
        story.append(p("Duplicate multiplicity statistics", "ReportH1"))
        story.append(p(
            "These figures use trace-level (Trace_ID, Barcode #) groups: panel A shows the copy composition "
            "after filtering, and panel C shows kept versus dropped rows by the original copy multiplicity. "
            "This is a technical proxy for duplicate review, not an allele-splitting outcome.",
        ))
        # Render the report-specific A/C-style layout so the PDF remains readable
        # even when an analysis-server preview uses a different aspect ratio.
        with tempfile.NamedTemporaryFile(prefix="chromatin-duplicates-", suffix=".png", delete=False) as handle:
            duplicate_plot = Path(handle.name)
        _write_duplicate_plot(sweep, duplicate_plot)
        story.append(_image_flowable(duplicate_plot, 174 * mm, 105 * mm, Image))
        duplicate_rows = [[
            p("Dataset", "ReportSmall"), p("SNR", "ReportSmall"), p("1 copy", "ReportSmall"),
            p("2 copies", "ReportSmall"), p("3 copies", "ReportSmall"), p("4+ copies", "ReportSmall"),
            p("Kept rows", "ReportSmall"), p("Dropped rows", "ReportSmall"),
        ]]
        for dataset in (sweep.first, sweep.second):
            for point in dataset.points:
                multiplicity = {item.multiplicity: item for item in point.trace_copy_multiplicity}
                duplicate_rows.append([
                    p(dataset.dataset_name, "ReportSmall"), p(f"{point.threshold:g}", "ReportSmall"),
                    p(multiplicity["1"].groups_after, "ReportSmall"),
                    p(multiplicity["2"].groups_after, "ReportSmall"),
                    p(multiplicity["3"].groups_after, "ReportSmall"),
                    p(multiplicity["4+"].groups_after, "ReportSmall"),
                    p(sum(item.rows_retained for item in multiplicity.values()), "ReportSmall"),
                    p(sum(item.rows_dropped for item in multiplicity.values()), "ReportSmall"),
                ])
        story.append(make_table(duplicate_rows, [29 * mm, 13 * mm, 20 * mm, 22 * mm, 20 * mm, 22 * mm, 22 * mm, 24 * mm]))
    story.append(p("Recommendations", "ReportH1"))
    recommendation_text = recommendations.strip() if recommendations and recommendations.strip() else _default_recommendations(comparison)
    story.extend(bullet(line[2:].strip()) if line.startswith("- ") else p(line) for line in recommendation_text.splitlines() if line.strip())
    story.extend([p("Conclusion", "ReportH1"), p(conclusion.strip() if conclusion and conclusion.strip() else _default_conclusion(comparison))])
    story.extend([Spacer(1, 3 * mm), p("This report preserves the structured measurements supplied by the analysis MCP. It does not establish biological significance.", "ReportSmall")])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
        canvas.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#627D98"))
        canvas.drawString(18 * mm, 9 * mm, "Chromatin Report MCP")
        canvas.drawRightString(192 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    try:
        SimpleDocTemplate(
            str(output_path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
            topMargin=14 * mm, bottomMargin=18 * mm, title=title,
            author="Chromatin Report MCP",
        ).build(story, onFirstPage=footer, onLaterPages=footer)
    except OSError as exc:
        raise ToolError(f"Could not write PDF report {output_path}: {exc}") from exc
    finally:
        if duplicate_plot is not None:
            duplicate_plot.unlink(missing_ok=True)


@mcp.tool(
    name="write_comparison_pdf",
    title="Write a chromatin dataset comparison PDF",
    description=(
        "Draft a polished PDF report from the complete structured output of the "
        "analysis MCP's compare_datasets tool. Includes summary metrics, compatibility "
        "checks, warnings, barcode coverage, recommendations, and conclusion. The "
        "tool formats the supplied result and does not recalculate measurements."
    ),
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=False,
    ),
)
async def write_comparison_pdf(
    comparison: Annotated[
        DatasetComparison,
        Field(description="Complete structured result from compare_datasets."),
    ],
    report_title: Annotated[
        str, Field(min_length=1, max_length=200, description="PDF report title.")
    ] = "Chromatin dataset comparison",
    scientist_notes: Annotated[
        str | None, Field(max_length=10000, description="Optional contextual notes.")
    ] = None,
    recommendations: Annotated[
        str | None, Field(max_length=10000, description="Optional Markdown recommendations.")
    ] = None,
    conclusion: Annotated[
        str | None, Field(max_length=10000, description="Optional Markdown conclusion.")
    ] = None,
    sweep: Annotated[
        SNRFilterSweep | None,
        Field(description="Optional complete structured result from snr_filter_sweep. Embed its intensity/retention plot and duplicate statistics."),
    ] = None,
) -> PdfReportArtifact:
    """Write one uniquely named PDF comparison report and return its path."""
    generated_at = datetime.now(timezone.utc).isoformat()
    output_path = _output_directory() / f"{_safe_stem(report_title)}-{uuid4().hex[:12]}.pdf"
    _pdf_report(output_path, report_title, comparison, generated_at, scientist_notes, recommendations, conclusion, sweep)
    if not output_path.is_file():
        raise ToolError(f"PDF report generation did not create {output_path}.")
    # report://latest is a text resource; keep it reserved for Markdown/HTML.
    # The PDF path is returned in the structured tool result instead.
    return PdfReportArtifact(
        path=str(output_path),
        format="pdf",
        size_bytes=output_path.stat().st_size,
        comparison_status=comparison.status,
        generated_at_utc=generated_at,
    )


@mcp.tool(
    name="write_comparison_report",
    title="Write a chromatin dataset comparison report",
    description=(
        "Turn the structured output of the analysis MCP's compare_datasets tool "
        "into a reproducible Markdown or HTML report. Preserve the supplied "
        "measurements, reasons, and warnings without inventing scientific claims."
    ),
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=False,
    ),
)
async def write_comparison_report(
    comparison: Annotated[
        DatasetComparison,
        Field(description="Complete structured result from compare_datasets."),
    ],
    report_title: Annotated[
        str, Field(min_length=1, max_length=200, description="Report heading.")
    ] = "Chromatin dataset comparison",
    output_format: Annotated[
        Literal["markdown", "html"], Field(description="Output document format.")
    ] = "markdown",
    scientist_notes: Annotated[
        str | None, Field(max_length=10000, description="Optional contextual notes.")
    ] = None,
    recommendations: Annotated[
        str | None,
        Field(
            max_length=10000,
            description="Optional scientist-authored next steps and recommended analysis parameters. Markdown is allowed.",
        ),
    ] = None,
    conclusion: Annotated[
        str | None,
        Field(
            max_length=10000,
            description="Optional scientist-authored conclusion. Markdown is allowed.",
        ),
    ] = None,
) -> ReportArtifact:
    """Write one uniquely named comparison report and remember it as latest."""
    global _latest_report
    generated_at = datetime.now(timezone.utc).isoformat()
    markdown = _markdown_report(
        report_title,
        comparison,
        generated_at,
        scientist_notes,
        recommendations,
        conclusion,
    )
    suffix = ".md" if output_format == "markdown" else ".html"
    content = markdown if output_format == "markdown" else _html_report(markdown, report_title)
    output_path = _output_directory() / (
        f"{_safe_stem(report_title)}-{uuid4().hex[:12]}{suffix}"
    )
    try:
        output_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"Could not write report {output_path}: {exc}") from exc
    _latest_report = output_path
    return ReportArtifact(
        path=str(output_path),
        format=output_format,
        size_bytes=output_path.stat().st_size,
        comparison_status=comparison.status,
        generated_at_utc=generated_at,
    )


class WorkflowReportArtifact(BaseModel):
    run_id: str
    status: Literal["COMPLETE_WITH_LIMITATIONS"]
    path: str
    report_sha256: str
    evidence_path: str
    verified_artifacts: int
    size_bytes: int
    execution_seconds: float


@mcp.tool(
    name="generate_experiment_qc_report",
    description="Compose a pre-filtering experiment HTML report from a host-provisioned, checksum-bound workflow manifest. Verify scientific evidence and current human approval; never run calculations. Returns compact report references only.",
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                idempotent_hint=False, open_world_hint=False),
)
async def generate_experiment_qc_report(
    manifest_id: Annotated[str, Field(min_length=1, max_length=80)],
    manifest_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")],
) -> WorkflowReportArtifact:
    global _latest_report
    from .workflow_report import generate
    try:
        artifact = WorkflowReportArtifact(**generate(manifest_id, manifest_sha256))
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        raise ToolError(f"QC report evidence verification failed: {exc}") from exc
    _latest_report = Path(artifact.path)
    return artifact


@mcp.resource(
    LATEST_REPORT_URI,
    name="latest_chromatin_report",
    title="Latest chromatin report",
    description="Most recent report written during this MCP server session.",
    mime_type="text/plain",
)
async def read_latest_report() -> str:
    """Read the latest generated report."""
    if _latest_report is None or not _latest_report.is_file():
        raise ResourceError("No report has been generated in this server session yet.")
    try:
        return _latest_report.read_text(encoding="utf-8")
    except OSError as exc:
        raise ResourceError(f"Could not read the latest report: {exc}") from exc


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
