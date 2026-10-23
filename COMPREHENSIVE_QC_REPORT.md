# Comprehensive pre-filtering QC — implementation and validation

The report server now composes the completed ROI 092/093 workflow into HTML using
`generate_experiment_qc_report(manifest_id, manifest_sha256)`. This is the only new
MCP entry point. Scientific execution, approval and simple Step 0/Pearson reports
remain unchanged in the trace server.

## Implementation

- New pure `workflow_report.py` verifies saved artifacts and provenance, then formats
  native measurements, figures, warnings, mapping and evidence links without science.
- `prepare_manifest.py` is host-only setup from existing compact workflow responses;
  the agent supplies only the saved ID/checksum. No cross-server tool calls.
- Existing comparison Markdown/HTML/PDF tools and latest-report resource are retained.
- Original per-ROI and merged statistics stay distinct. Localization original IDs,
  tracing replacement IDs, pooled localization ROIs, undeclared z units, repeated
  barcode/allele handling and missing precision/registration evidence are explicit.
- HTML references existing seven figures and full artifacts; no arrays or images
  are returned to the model or duplicated. Unique output directories preserve runs.
- Updated READMEs, AGENTS.md, skill and statistics roadmap; configuration and trust
  boundaries are in references/comprehensive-qc-report.md.

## Validation

- Reporting suite: **37 passed**, including seven prior comparison-report tests;
  invalid/missing/tampered evidence, current approval, cross-stage provenance,
  authorized paths, source integrity, unavailable measurements, escaping, safe-link
  navigation, host manifest preparation and MCP discovery/schema/call errors.
- Unchanged scientific server suite: **309 passed, 1 skipped**, 107.63 s. The skipped
  opt-in real trace-analyzer compatibility test was not silently treated as passed.
  Two expected warnings came from constant Pearson input and an all-NaN fixture.
- Real report-server stdio: discovery, schema validation, successful composition and
  wrong-checksum rejection passed. Direct deterministic and MCP HTML match apart
  from generation timestamp. All 55 scientific/evidence artifacts verified.
- Real report values match saved native evidence: Pearson r 0.8691053986549377
  (display 0.8691), 406 shared pairs, 81196 tracing rows, 103161 localization rows,
  12609 global Trace_IDs and ROI/Trace_ID pairs, 34140 neighbor observations and
  29 original/replacement mappings. No scientific equivalence rerun was necessary:
  this change formats previously validated native outputs without recalculation.
- All protected original inputs, native code, saved scientific artifacts and human
  approval remain unchanged. No collection, merge, annotation, analyzer or filtering
  was run on the real experiment by report generation.
- HTML structure and 69 file/figure links checked, including all seven figures.
  Browser visual inspection was blocked by local-file policy; it is **not validated**.

## Measured performance

One real report invocation: **0.113753 s** MCP call, **0.090136 s** server work,
**653 bytes** structured result, **1602 bytes** serialized MCP response. Direct
composition took **0.091115 s**; MCP startup **0.361348 s**. One successful report
call, one separate wrong-checksum negative control and one discovery request.
These are single-trial measurements, not a latency distribution or model tokens.

No provider-backed autonomous agent was run. Actual input/output/cached/reasoning
model tokens and cost are **unavailable**. No claim of agent token savings is made.

## Limits and review

COMPLETE_WITH_LIMITATIONS describes completed report composition, not biological
QC acceptance. Missing required evidence fails closed; missing optional metrics
remain unavailable. Local trusted-host approval is not a researcher identity signature;
scientific operations must recheck approval when they execute. Artifacts must remain
immutable after publication. The HTML depends on the original local artifact stores;
PDF export and portable bundling are not implemented for this new workflow. Existing
comparison PDF functionality is preserved.

Report links and complete machine-readable evidence are published in the existing
experiment view under `10-comprehensive-qc/`. Filtering remains unimplemented by
this milestone. Stop for researcher review.
