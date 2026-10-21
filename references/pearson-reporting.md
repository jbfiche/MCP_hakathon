# Pearson QC reporting: compact interaction, complete artifacts

Keep routine Pearson QC and its human approval gate in `chromatin-trace-mcp`.
Reporting complexity, rather than ROI count alone, determines whether a future
workflow needs `chromatin-report-mcp`. No additional tool or cross-server call is
introduced by this change.

## Three presentation surfaces

| Surface | Content | Scaling rule |
|---|---|---|
| Agent tool response | Existing dataset index/ROI/collection mapping, counts, at most ten pair previews, four warning previews, truncation flags, artifact paths/hash | Same schema; no full matrix, distance maps, image or report text |
| Human approval form | All dataset choices and warnings, run/fingerprint/revision, ten saved pair previews, complete report/results/matrix/figure paths | Dataset/warning content grows linearly; pair preview is bounded and explicitly incomplete |
| Saved artifacts | Complete JSON results/median-distance maps, native NPY matrix and original figure, full Markdown QC report and native log | Complete evidence stays local; no default transfer through the agent |

The local Markdown report starts with counts, an explicit index-to-ROI mapping,
scientific warnings and a short comparison preview. For more than ten pairs,
a complete comparison table follows the artifact references. Small runs show the
complete table once. There is no scientific ranking, acceptance threshold or
inference of biological equivalence. Undefined coefficients remain undefined/null.
The first ten comparisons are in the existing saved order, not selected extremes.

The approval form tells the researcher to open the complete saved report and figure,
including pairs omitted from the preview, before deciding. Figure and report paths
are references, not promises that a particular client automatically opens them.
The terminal client prints the actual form message and those paths. All repeated-
barcode, last-row, allele-handling, nucleus-level and plot-range warnings are retained.
Human selection and the persisted approval gate are unchanged. Formatting is not
consent and never chooses or excludes datasets.

Current technical limits remain 2–32 datasets and up to 496 off-diagonal pairs.
This change scales the reporting layout within those limits; it does not increase
scientific processing capacity, memory limits or readable evidence-file limits.

## Modular formatting

`chromatin_trace_mcp/pearson_reporting.py` contains pure functions for the local QC
report and human form, plus shared presentation limits. It has no imports of MCP,
Traceratops or NumPy and performs no file access or scientific calculations.
`pearsons.py` owns native execution, structured evidence and artifact publication;
`approval.py` owns checksums, human decisions and approval state. Only formatting
is delegated to this module. The compact Pydantic response contract is preserved.

Existing saved reports, numerical artifacts and approvals are not rewritten.
New runs use the revised Markdown layout; their exact report hash is bound by the
same approval mechanism. Editing any report later still invalidates its approval.
There are no added numerical retrieval tools. Selected/paged retrieval from a saved
Pearson run remains a separately documented future enhancement.

## When to use the report server later

Use the trace server alone for one Pearson QC run, its ordinary Markdown report,
figures, compact explanation and scientific review—even with many ROIs.

Consider a separately requested report-server workflow when it needs:

- A coherent report combining different analyses: Step 0 validation, Pearson QC,
  localization QC, distance analyses, and their methods/provenance.
- Comparisons across experiments, conditions, cohorts or multiple analysis runs.
- Rich HTML/PDF composition, publication layouts, captions, reusable templates,
  or an interactive dashboard beyond the native figure and QC table.

The report server should consume completed, checksum-identified artifacts and
format them without reopening scientific source tables or recomputing measurements.
Prefer authorized artifact references; do not route full matrices/reports through
the LLM. Safe shared artifact access must be designed and approved with that future
workflow; this document does not implement it. Scientific validation and decisions
remain in the trace server, regardless of where a rich report is rendered.

If both servers eventually need the Pearson formatter, move this pure module once
into a shared presentation package and import it from both. Do not copy/paste a
second implementation or make the report server import scientific execution code.
Add a report-server call only when the requested composed output justifies it;
more ROIs alone are not a reason to add a call. There are no new report-server
imports, dependencies or calls today.

## Measurement limits

Response byte counts are not model tokens. Existing compact response previews and
schemas are unchanged. Formatting tests cover a 32-dataset/496-pair case and verify
complete artifact tables, a bounded human preview, preserved warnings/references,
and no mutation of source evidence. Native equivalence and approval regression
tests remain authoritative. Live model token consumption and human UI behavior are
not established by those deterministic tests.
