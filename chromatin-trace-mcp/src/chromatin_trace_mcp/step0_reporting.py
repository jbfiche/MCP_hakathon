"""Pure Step 0 presentation: no scientific calculations or filesystem reads."""
import html
from pathlib import Path


def human_report(doc, summary):
    """Describe observations plainly; compare expectations only when supplied."""
    rules = doc.get("rules", {})
    expected_rois = rules.get("expected_roi_ids")
    expected_barcodes = doc.get("expected_barcodes")
    lines = ["# Experiment report", "", f"Experiment: {doc['experiment_root']}", "",
             f"ROIs: {summary['roi_count']} found",
             f"Localization table: {summary['localization_tables']} found",
             f"Traces table: {summary['tracing_tables']} found",
             f"Tables read successfully: {summary['tables_parsed']}", ""]
    if expected_rois is None and expected_barcodes is None:
        lines += ["No expected ROI or barcode lists were supplied. This report describes what was found.", ""]
    else:
        if expected_rois is not None:
            lines += ["Expected ROIs: " + ", ".join(expected_rois)]
        if expected_barcodes is not None:
            lines += ["Expected barcodes: " + ", ".join(expected_barcodes)]
        lines += [""]
    for roi in doc["rois"]:
        lines += [f"## ROI {Path(roi['directory']).name}", ""]
        for role, title in (("localization", "Localization table"), ("tracing", "Traces table")):
            lines += [f"{title}: {len(roi[role])} found"]
            for table in (t for t in roi["tables"] if t["role"] == role):
                if "record_count" in table:
                    lines += [f"- Rows: {table['record_count']:,}"]
                if "unique_trace_count" in table:
                    lines += [f"- Traces: {table['unique_trace_count']:,}"]
                if "unique_barcode_count" in table:
                    lines += [f"- Barcodes: {table['unique_barcode_count']} found",
                              "- Barcode IDs: " + ", ".join(table["observed_barcodes"])]
                if table.get("missing_barcodes") is not None:
                    lines += ["- Missing expected barcodes: " + (", ".join(table["missing_barcodes"]) or "none")]
                if table.get("unexpected_barcodes"):
                    lines += ["- Barcodes outside the expected list: " + ", ".join(table["unexpected_barcodes"])]
            lines += [""]
    bed = doc.get("bed", {})
    if bed.get("file"):
        lines += ["## BED file", "", f"File: {bed['file']}",
                  "File found: " + ("yes" if bed.get("existence") == "PASS" else "no"),
                  "Barcode mapping: " + {"PASS": "checked", "FAIL": "problems found", "INCOMPLETE": "not checked; mapping information needed"}.get(bed.get("mapping_status"), "not checked"), ""]
    lines += ["## Validation outcome", "", f"Status: {summary['status']}",
              f"Check phase: {summary['phase']}",
              "Full validation performed: " + ("yes" if summary['full_validation_performed'] else "no"),
              summary['conclusion'], "", "## All validation findings", ""]
    if not doc["findings"]:
        lines += ["No findings."]
    for item in doc["findings"]:
        context = " ".join(str(item[k]) for k in ("roi", "path") if item.get(k) is not None)
        lines += [f"- [{item['severity']}] {item['code']}" + (f" ({context})" if context else "") + ": " + item['message']]
    return "\n".join(lines)


def render_reports(doc, summary):
    """Render both supported formats from the same saved scientific observations."""
    markdown = human_report(doc, summary)
    escaped = html.escape(markdown)
    webpage = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
               '<meta name="viewport" content="width=device-width,initial-scale=1">'
               '<title>Experiment report</title><style>'
               'body{max-width:1000px;margin:2rem auto;padding:0 1rem;font:16px/1.5 system-ui,sans-serif;color:#17202a;}'
               'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f9f9;border:1px solid #d5dbdb;padding:1.25rem;border-radius:.5rem;}'
               '</style></head><body><pre>' + escaped + '</pre></body></html>')
    return markdown, webpage
