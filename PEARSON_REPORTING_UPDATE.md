# Pearson QC reporting update

Routine Pearson QC and human approval remain in `chromatin-trace-mcp`. No report-
server calls, new MCP tools, numerical retrieval tools or Step 1b implementation.

## Changes
- Extracted presentation into dependency-free `pearson_reporting.py`. It formats
  existing evidence only, with no MCP/backend/NumPy imports, file I/O or scientific
  calculations. Future reuse should move this module into one shared package,
  rather than duplicate its implementation in the report server.
- Kept the existing compact response schema and limits: dataset/ROI mapping, counts,
  ten pair previews, four warning previews, truncation flags and artifact references.
- Local Markdown starts with counts, dataset mapping, all warnings and a short
  preview. Larger reports retain every comparison in a complete table below the
  overview. JSON distance maps/matrices, native NPY data and original figures remain
  complete, separate artifacts.
- Human review forms include all dataset choices/warnings, ten pair previews, and
  exact report/results/matrix/figure references. They no longer repeat every pair
  plus the entire report. Researchers are explicitly directed to open the complete
  report and figure before deciding. Preview order is saved order, not a ranking.
- The approval schema, decision/state functions and evidence binding are unchanged.
  Existing saved reports/artifacts/approvals are not rewritten. New report hashes
  are handled by the existing approval mechanism.

Changed files: `pearsons.py`, the presentation-only portion of `approval.py`, new
`pearson_reporting.py`, four tests in `test_pearson_reporting.py`, trace README,
`AGENTS.md`, diagnosis `SKILL.md`, Pearson/approval references, new
`references/pearson-reporting.md`, and this report. The report server is unchanged.

## Future report-server criteria
ROI count alone does not justify another server call. Use trace alone for one
Pearson QC run and its ordinary report/approval. Consider separately requested
report-server workflows for multi-analysis composition, comparisons across
experiments/conditions/cohorts, or rich HTML/PDF/publication/dashboard outputs.
Those future workflows should consume authorized, checksum-identified saved
artifacts, reuse the same formatter, and never recompute science or grant approval.
No cross-server artifact-access mechanism is implemented now.

The existing 32-dataset processing limit remains. Reporting is scalable within that
limit (496 off-diagonal pairs); processing capacity was not increased. Full reports
and matrices are not sent to the agent by default. Selected numerical retrieval
remains a future enhancement.

## Validation
**159 passed, 0 failed, 1 skipped in 31.63 seconds** in the combined trace/report/
Step 0 workflow suite, including four new formatting checks. Tests cover small and
32-dataset reports, complete pair tables, undefined values, retained warnings and
artifact references, unchanged evidence, bounded human previews, and table-cell
escaping. Existing native scientific equivalence, saved-approval and real stdio
protocol tests passed in the same run.

The skipped case is the existing optional real-trace compatibility test requiring
`CHROMATIN_TRACE_ECSV`. Existing native constant-input/All-NaN and pytest
`asyncio_mode` warnings remain. The unrelated packaging and separate SDK suites
were not rerun. Skill validation passed.

Structural checks verify unchanged native scientific call expressions, compact
response model, approval decision/state functions and fingerprint binding. Hashes
confirm existing reference reports, numerical artifacts, collected tables and
original scientific inputs are unchanged. Evidence is in the project workspace:
`acceptance/pearson_reporting_2026-10-20/regression.xml` and `integrity.json`.

No provider/model trial or live human approval was performed. No actual token
savings are claimed. The human interaction still requires a supporting client.

See [reporting rules and future criteria](references/pearson-reporting.md).
Step 1b remains unimplemented.
