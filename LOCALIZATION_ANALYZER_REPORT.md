# localization_analyzer — implementation and real-data validation

23 October 2026. Scope: verified merged, unfiltered-by-MCP localizations only.
No filtering or comprehensive chromatin-report-mcp report was implemented or invoked.

## Implementation

Extended the **existing localization_analyzer MCP tool**, with no duplicate tool.
The old registered-dataset arguments and payload fields remain available. New
verified mode requires localization merge run ID, merged ECSV SHA-256 and provenance
SHA-256 together. An optional tracing annotation ID/checksum verifies and references
the original-to-replacement BED mapping without changing localization identifiers.

Reuse native traceratops.localization_analyzer.run and
LocalizationTable.plot_distribution_fluxes, plus existing localization-merge source
association/row validators and require_scientific_approval. Verify current exact
human approval, original experiment/ROI mappings, source collection hashes, row/
metadata contributions and native versions before execution; recheck under the
existing approval lock before publication. The worker uses an identical read-only
snapshot and its input hash must remain unchanged. Original Buid, ROI and barcode
identifiers remain untouched. Runtime failures retain ERROR logs/artifacts; early
invalid evidence publishes no scientific result.

Native execution is isolated in a worker (300 s timeout). Its one four-panel figure
and complete numerical plot inputs, native counts and returned violin/scatter
objects are saved locally as JSON/NPZ, alongside logs, a checksum manifest and
analysis provenance. Native algorithms and all previously accepted data/evidence
are unchanged. The response is compact and excludes tables, arrays, images and full
logs. Existing tool count remains 27; no report-server dependency was added.

Changed files: server.py, new localization_analysis.py and localization_analyzer_worker.py,
new test_localization_analysis.py and benchmark_localization_analysis.py; READMEs,
AGENTS, scientific roadmap, SKILL.md and references/localization-analyzer.md.
No merge, approval, Step 0, statistics, annotation, tracing analyzer or native
algorithm implementation was changed.

## Tests

Full trace-server regression: **309 passed, 1 skipped**, 111.08 s. Includes
**20 new localization tests** and the existing legacy localization interface.
The skipped test is the opt-in CHROMATIN_TRACE_ECSV real-file compatibility check;
its environment variable was not set for this suite. The separate actual approved
merged-file run below did execute and verify native loading/analysis through stdio.
Two expected native warnings remain in unrelated constant-Pearson/all-NaN matrix
edge tests. No regression failed in the final suite. Skill validation passed.

Coverage includes direct native PNG and every plotting-input array, native barcode
counts, reproducibility, metadata/source integrity, current/revoked approval,
missing/changed files, invalid IDs/provenance/ROI selection, legacy/missing columns,
nonfinite/masked plotting values, unsafe output roots, native failure logs, changed
merge or rejected approval during execution, incomplete annotation references,
MCP discovery/schema/errors and compact JSON without an extra result envelope.
Finite extreme/negative values are not silently filtered by invented thresholds.

Initial tests exposed two issues: an invalid fractional-barcode fixture was already
correctly rejected by the merge validator; it was replaced by a direct preflight
assertion rather than weakening that validator. A union return annotation caused
an SDK result envelope; bare dict then omitted structured content. The final typed
dict[str, Any] return emits top-level JSON, with each response mode still validated
by its own Pydantic result model. Both response modes passed transport tests.

SVG/PDF retain the native format options but were not separately compared in this
milestone; PNG is the real-data and byte-equivalence reference. Root plugin packaging
and unchanged reporting-server tests were not rerun in this milestone. No live
provider-backed autonomous agent benchmark was performed.

## Actual ROI 092/093 run

Pearson run: 43f648fb02464564b6f57efd609ba69a; human-approved selection [0,1],
from MCP_HOST_ELICITATION. No new decision, Step 0, collection, Pearson or merge run.
Localization merge: b91328790abe4a17a4a400ddd069e97f
Merged ECSV SHA-256: cd89b37b7cb357f37947903221a37f7ef498ca546b1af9fc031dac0376a824d6
Provenance SHA-256: ea353902cb3a731a74f256748c510cdb37a614b0616809284576d250f3243423
Analysis run: c1649f4ba0ff4d049b2210db39e85016
Evidence SHA-256: 7fe7b9a1438c0c3e88b1eb7ff6129df690c7a34ab58d4e0afca2bc07e9846dbb

**ANALYZED: 103,161 rows, 29 original barcode IDs, 2 ROIs, 103,161 unique Buid values.**
The original barcodes include 639. They were not remapped. The linked tracing
annotation uses replacement IDs 1–29; analysis.json records the exact annotation,
BED and mapping hashes. Cross-table labels must use that mapping, and individual
spot correspondence uses Spot_ID/Buid rather than barcode alone.

Native figure: localization_distribution_fluxes.png (one four-panel figure).
Complete plot evidence: numerical_outputs.json / numerical_outputs.npz.
The real PNG is **byte-identical** to independent direct native execution.
**Every native plotting-input array matches exactly**, including barcode positions,
all per-barcode SNR observations, detection counts, and both scatterplot x/y/color
arrays. Original input tables, old merges, baselines, annotation, tracing analysis,
existing approval and pinned native code all retained their hashes. Artifact hashes
were checked against the saved manifest. Native logs and all warnings are retained.

## Performance

One real MCP tool call plus one discovery request. No model-provider request by the
benchmark, so actual input/output/total/cached/reasoning tokens and cost are unavailable.
No byte-based token estimate is claimed.

| Measurement | Result |
|---|---:|
| Direct native execution, including interpreter startup | 2.764 s |
| MCP startup, separate from call | 1.440 s |
| MCP call, including verification/capture/publication | 6.301 s |
| Server execution | 6.271 s |
| Compact structured response | 2039 bytes |
| Serialized MCP result | 4503 bytes |

One trial per mode is not a performance distribution. The MCP path includes approval,
source/annotation evidence validation, snapshotting, numerical capture/compression,
artifact hashing and publication that direct execution does not include.

## Scientific limitations and interpretation

The native analyzer returns no statistics object, thresholds or biological PASS.
The saved values are available native plot inputs/counts and Matplotlib-returned
geometry, not invented scientific metrics or every private KDE intermediate.
Its historical filename contains fluxes, but its panels show SNR, zcentroid,
detection counts and roundness/skew; there is no flux histogram in this operation.

The localization tables already carry upstream filtered/registered metadata. No
**additional** filtering was applied. Localization coordinate units/assembly are not
fully declared, so z values are presented unchanged without assuming microns or
copying dm6/calibration from tracing data. The raw roundness range contains very
large finite values; native automatic axes may compress the bulk of the scatter.
Original numeric barcode gaps likewise affect native spacing. Neither is silently
corrected, clipped or filtered. Human inspection remains necessary.

Approval authorizes the original tracing ROI selection, not a separate human review
of localization bytes absent from Pearson; those exact bytes are bound for execution
by the validated localization collection/merge checksums. Trusted server-managed
stores remain required: hash checks do not isolate unrestricted external OS writers.

## Inspection and next step

The new run is linked under Ressources/mcp_results/roi092_093_dm6_43f648fb/
09-localization-analysis/, with the original native filenames. Canonical output
artifacts remain in their server-managed store; no large files are copied for the
inspection view. Publication adds no scientific calculation or MCP call.

Both analyzer stages have now been validated on this experiment. **Stop for owner
review.** The future comprehensive pre-filtering report still requires separate
approval and implementation; filtering remains later. No such work was started.
