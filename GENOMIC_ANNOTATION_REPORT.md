# Genomic annotation implementation and real-experiment validation

2026-10-22. Native Traceratops 1.0.1, pinned commit
261a48fe92498abcb154891fe6e5a5ca8219b610. Native algorithms unchanged.

## Implementation

Added trace_genomic_coordinates on a verified original Step 1c baseline/merge and
current human-approved Pearson selection. Use the untouched five-column BED and
native parser/coordinate assignment including replacement IDs, with no mapping
override. Preflight rejects duplicate/missing/conflicting originals, replacement
collisions, malformed rows, invalid/out-of-reference coordinates, overlapping/tied
intervals, integer overflow and chromosome truncation. Assembly comes from an
explicit host-controlled researcher reference; defaults cannot establish authority.

New immutable run artifacts retain the unchanged native output and a second ECSV
whose only extra change is the documented assembly metadata correction, plus full
barcode mapping, hashes, native version/log and baseline/approval provenance.
The analyzer optionally accepts annotation ID/checksum; original merge contribution
checks remain unchanged and a separate strict derivative check validates native
assignments, all other row values/masks/types/metadata and both evidence chains.
No original BED, ECSV, Step 1c baseline, localization output or approval is edited.

Changes: genomic_annotation.py, tracing_analysis.py, server registration; new
annotation tests; four discovery-expectation updates (27 tools); references,
READMEs, AGENTS and skill; manual-only existing-run terminal review client.
No Step 0 logic, approval implementation, native science or report-server code changes.
See references/genomic-annotation.md for the complete contract and configuration.

## Test results

- Full trace suite: **287 passed, 1 skipped**, 97.24 s; 26 annotation cases included.
  The optional real-input compatibility check was then explicitly run on ROI 092:
  **1 passed**, 1.83 s. Its original skip is therefore separately covered.
- Final async-wrapper stdio check: **1 passed**, 6.36 s; repeated existing test, not
  an additional distinct passing test. Annotation replacement, derivative analyzer,
  all five direct-native PNGs and neighbor values match; modified output is rejected.
- Report-server regression: **7 passed**, 1.34 s using bundled reportlab on the
  test import path. Initial science environment lacked reportlab (5 passed, 2
  dependency failures); no dependency or report-server code was modified.
- Repository Step 0 workflow checks: **10 passed**. Existing plugin-structure guard:
  **1 failed** because its root discovery searches the tests directory and finds no
  root plugin manifest. This guard and plugin files are unchanged; no packaging fix
  is included. Root suite also warns about unavailable asyncio_mode plugin support.
- Skill validator: passed. Initial trace run had four obsolete discovery assertions
  expecting 26 tools; updated to the intentionally added 27th tool, with no scientific
  validation logic changed. Sandbox stdio initialization timed out; real stdio checks
  passed outside that sandbox. These failed/aborted attempts are not successes.

Tests cover direct native scientific equivalence with replacement (including source/
replacement ID overlap), reproducibility, unchanged nonannotation data, invalid BED
mappings/reference/paths/checksums/approval, native failures, altered parent evidence,
changed BED during execution, stale assembly reference, tampering, original source
integrity and final analyzer publication rejection after BED changes.

## Real ROI 092/093 execution

Completed through fresh Pearson QC and **AWAITING_APPROVAL** only. Step 0 PASS with
61 retained skipped-symlink warnings and two successful native ROI-statistics records.
Trace collections: 81,196 rows; localization collections: 103,161 rows. ROI Trace_ID
counts: 6,776 and 5,833; 29 original barcodes each. Independent counts and direct
native statistics match. New Pearson r=0.8691053986549377, 406 pairs: matrix, full
native distance-map medians and figure exactly match direct native execution.

Pearson run: 43f648fb02464564b6f57efd609ba69a
Results SHA-256: faf70a50073f49a8909ab0897db6054daf10be2b044d2bf1e0b940808939e77d
Indices: 0=ROI092, 1=ROI093. Human selection is currently empty.

No approval was fabricated or reused. Both new merges, merged stats, real annotation
and real trace analysis are **BLOCKED**, not passed or failed scientific calculations.
The real BED preflight has complete bijective mapping to 1–29 and valid dm6 chr2L
bounds; the researcher declaration is the assembly authority, not inherited mm10.
Merged localizations will retain original barcode IDs. Cross-table barcode semantics
must use the saved mapping; physical spot joins use Spot_ID/Buid.

Inspect acceptance/full_pipeline_roi092_093_dm6/README.md in the task workspace for
verified report copies, exact manual approval command, states and all measured evidence.
Authoritative artifacts remain in their configured server-managed stores. Every
protected source/evidence/native-code hash was unchanged after this real run.

## Performance

| Real MCP tool | Call seconds | Structured bytes | Serialized result bytes |
|---|---:|---:|---:|
| run_experiment_validation | 1.208 | 5017 | 12160 |
| collect_files | 0.574 | 1181 | 2869 |
| collect_files | 0.889 | 1158 | 2823 |
| trace_pearsons | 2.177 | 2171 | 4941 |
| review_pearson_approval | 0.016 | 741 | 1781 |

Five calls; one discovery. Direct native Pearson: 1.944 s vs checked MCP Pearson
2.177 s for this trial. It omits wrapper validation/provenance/report persistence.
Synthetic final annotation MCP trial: 0.040 s (server 0.032 s), 1,291 structured
bytes, one annotation call. This is generated-fixture performance, not real annotation
performance; the real run stopped before merging. Provider-backed autonomous agent
validation and provider input/output/total tokens/cost are **NOT RUN / unavailable**.
No token estimate is presented as actual usage.

## Remaining limitations and next action

- Genuine review of the exact new Pearson evidence is required before downstream work.
- Real-experiment annotation/analyzer native equivalence and performance remain pending.
- Annotation failure returns ERROR without publishing partial native logs/artifacts;
  successful evidence retains full native output/log and warnings.
- Native allele handling/repeated barcode limitations remain in Pearson/analyzer QC.
- Source mm10 metadata remains untouched; only a derived output may record the explicit
  researcher-confirmed dm6 correction. The supplied localization metadata already
  says filtered/registered; this MCP workflow applies no additional filtering.
- Artifact checks assume trusted host-managed stores and cannot prevent arbitrary
  unrestricted OS writers; hashes are rechecked before publication/consumption.
- Existing plugin packaging guard remains failing; report PDF tests require reportlab.

Stop for human review. Do not implement localization analysis, filtering or the future
comprehensive report. Approval of this implementation does not approve these datasets.
