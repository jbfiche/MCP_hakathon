# Native trace_analyzer integration and validation

Date: 22 October 2026. Scope: trace_analyzer on an exact merged/unfiltered tracing
input linked to Step 1c. No localization analyzer integration, filtering,
comprehensive reporting, cross-server mechanism, native algorithm or scientific
approval change was implemented.

**Outcome:** implementation/native equivalence validated on generated genomic
fixtures. The actual ROI 092/093 reference experiment is **blocked at scientific
preflight** because its genomic metadata is placeholder data. No native analyzer
ran on that actual reference, and no scientific success is claimed for it.

## Inspection and implementation

Inspection found no registered trace_analyzer MCP wrapper; the repository contained
an earlier native-output audit only. Reused native process_traces, existing
merged_statistics validators, merge row/metadata contribution checks, saved Step 1c
evidence and require_scientific_approval. Existing localization wrapper, scientific
algorithms and approval mechanism remain unchanged.

Added trace_analyzer(baseline_run_id, baseline_sha256, output_format="png",
neighbor_distance_range="1", random_seed=0) to chromatin-trace-mcp, now 26 tools.
The exact successful Step 1c evidence supplies merge/provenance/checksum references;
no path override, filtering, dataset selection or new approval is exposed. PNG,
SVG and PDF are native format choices. The positive-micron or auto neighbor range
controls display axes, not scientific selection/acceptance. Default 1 retains
native behavior. A recorded NumPy seed controls native bootstrap reproducibility.

Before execution, verify baseline checksum/status/scope, exact merge/provenance
hashes, native implementation hashes, current Pearson/approval evidence, revision,
parameters, selected sources, their original metadata, contribution rows and ROI
mappings. Before successful publication, recheck baseline/log, merge/provenance/log,
current approval and bound Pearson/collection evidence under the existing lock.
Changes/rejection cannot publish ANALYZED. Source files and previous artifacts are
never destinations.

Native execution is isolated in a separate Python worker with relative input
basename trace.ecsv. This avoids native input.split('.')[0] mishandling dotted
parent paths and keeps process-local plotting/RNG changes out of the MCP host.
The worker receives unchanged read-only snapshot bytes. Its 300-second timeout
bounds elapsed execution; it is not an OS memory/network sandbox. The private
input copy is removed before publication; the exact original remains referenced.

## Scientific grouping, metadata and options

Several native calculations group only by Trace_ID: trace histograms, detection
bootstrap, neighbor distances, multiplicities and centered projections. A global
Trace_ID belonging to multiple output ROIs is therefore rejected. No IDs are
reassigned and no ROI is filtered to circumvent the ambiguity. Repeated barcodes
within a nucleus are retained with explicit native pairing/allele limitations.
Trace_ID and reported distances remain nucleus-level observations, not resolved
single-chromosome or allele measurements.

Required unmasked fields include standard tracing identifiers/coordinates and
Chrom, Chrom_Start, Chrom_End. Coordinates must be finite, barcodes integer,
intervals integer/nonnegative with end > start. Require explicit original-source
micron units; merged constructor defaults cannot supply missing source calibration.
The current native neighbor analysis requires one non-placeholder chromosome,
consistent genomic coordinates per barcode and no identical intervals assigned to
different barcodes. Native barcode ordering/consistency checks are reused.

Native neighbors must be consecutive both numerically and in genomic rank. With
no eligible pairs, native returns six zeros; these are explicitly labeled
UNAVAILABLE_NO_ELIGIBLE_NEIGHBORS, not measured zero distances. No genomic order,
BED coordinates, assembly identity, scientific cutoff or acceptance threshold is
invented. Missing original assembly declarations are warned about, not certified
by native merge defaults.

Optional native plotXYZ is not exposed: its entry point hard-codes pixel sizes
[0.1,0.1,0.25] and emits very large additional plots. Correct calibration requires
an explicit upstream interface/scientific review. Standard five-figure analysis
remains unchanged. Native relative-frequency bins cover multiplicities 1–8;
complete returned multiplicities remain available locally, including values outside
those displayed bins. Native multiplicity lists omit absent traces and are not a
zero-filled barcode-detection matrix.

## Numerical/visual artifacts

Transparent worker wrappers copy existing native function returns and numerical
inputs/results already supplied to native histogram, violin, image and hexbin
calls; original objects/results are returned unchanged. No scientific formula,
bootstrap, histogram, distance, normalization or projection algorithm is reimplemented.
No scientific calculation is rerun merely to capture its numbers.

Preserved local numerical evidence includes full-precision returned neighbor
mean/std values; complete native barcode multiplicity lists; per-trace histogram
observations/counts/bin edges; every native bootstrap sample with barcode labels;
neighbor vectors/density bins; the native multiplicity frequency matrix; and
centered-projection plotting coordinates/bins. Mask arrays are saved when supplied.
This captures available native returns and plot data, not every private intermediate
variable. Nothing is estimated from figure pixels.

Each run saves analysis.json, artifacts.json with filenames/sizes/SHA-256 values,
numerical_outputs.json plus pickle-free numerical_outputs.npz, stdout/stderr logs,
and five original native figures. Evidence records baseline/merge/approval/source
links, checks, native/worker hashes, parameters, warnings and execution status.
Output store: CHROMATIN_TRACE_ANALYZER_OUTPUT_DIR, outside original/evidence stores.
Default is trace output/trace_analysis, otherwise ./results/trace_analysis.

Compact MCP output contains ANALYZED/ERROR, evidence path/hash, manifest/output
references, five-figure count, small native neighbor summary, bounded warnings,
seconds and response bytes. No images, tables, bootstrap distributions, matrices
or full reports are sent by default. ANALYZED is execution success, not biological
PASS. Preflight failures create no native output. Native exceptions/timeouts or
post-execution evidence failures preserve available partial outputs/logs with ERROR,
not a successful measurement summary.

## Tests and equivalence

| Suite | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Main trace/Step 0 regressions | 269 | 0 | 1 |
| Existing report server | 7 | 0 | 0 |
| Main combined result | **276** | **0** | **1** |
| Additional no-neighbor scientific edge case | **1** | **0** | **0** |
| Additional interrupted-metadata failure case | **1** | **0** | **0** |

Main trace suite: 86.68 s; report suite: 1.12 s. Additional edge case: 2.95 s,
27 unrelated cases deselected. This yields 278 distinct passed test cases across
those runs, with one existing optional skip. Includes 29 new analyzer cases in total.

Verified direct native numerical returns and byte-identical standard PNG figures;
same-seed complete numerical arrays are reproducible. Tests cover explicit genomic
fixtures, repeated barcodes, global ID collisions, missing/placeholder/inconsistent/
tied genomic coordinates, invalid intervals and coordinates, missing original
calibration, malformed options, changed baseline/merge/provenance/collection evidence,
invalid approval, timeout, unsafe output placement, partial-failure artifacts and
post-native baseline changes preventing success publication. Real stdio verifies
26-tool discovery, schemas, strict seed typing, SVG execution and compact references.

The full suite ran before a small import-context isolation adjustment restoring
host Matplotlib defaults. The final source was then exercised by the actual stdio
native-equivalence benchmark and no-neighbor edge test; a fresh-process assertion
confirmed importing the analyzer preserves existing host plotting defaults. No
scientific formulas or worker calculations changed in that adjustment. A subsequent
focused failure test also verified that corrupt/partial native JSON cannot discard
available logs/artifacts; only failed-run metadata handling changed in that fix.

The skipped test is the existing optional real-trace compatibility check requiring
CHROMATIN_TRACE_ECSV. Existing asyncio_mode, native constant-input and All-NaN
warnings remain. Skill validation passed. The unrelated packaging and optional
Agents SDK suites were not rerun. Tests use explicitly generated scientific fixtures
and synthetic test approvals; these are not real researcher consent.

## Actual ROI 092/093 reference: blocked, not analyzed

One real stdio request referenced the existing Step 1c baseline
4bd1e131d695423589525e9d3f134a7b and saved manual approval. No new human decision
was requested or generated.

Returned ERROR before native execution:

> Genomic-neighbor analysis requires one declared non-placeholder chromosome

The merged tracing ECSV has Chrom=xxxxx and repeated placeholder intervals
0–999999999 across barcodes. These do not define scientifically meaningful genomic
neighbor ordering. The wrapper did not substitute numeric barcode order, infer a
BED mapping, edit existing artifacts, filter rows or bypass this check. Output
figure count is zero and native_execution is NOT_RUN_PREFLIGHT_REJECTED.
Preflight took 0.857 s and returned 646 structured-response bytes.

Successful analyzer results for this reference therefore remain unavailable.
An authoritative barcode-to-genome mapping and reviewed source metadata are needed
before analysis. Any correction must be a separately authorized provenance-bound
workflow with fresh input/evidence hashes and appropriate approval; do not edit an
already-approved merged artifact in place. The scientific identity/assembly of a
mapping is not established by native default metadata.

## Measured benchmark — generated genomic fixtures only

One direct-native trial and one real stdio analyzer trial, seed 0, PNG, auto range,
explicit generated genomic mapping. Approval is a labeled synthetic test fixture,
not a real human decision. All five PNGs are byte-identical to native execution;
full native neighbor returns and barcode multiplicities match. Input/evidence
hashes are unchanged.

| Measurement | Result |
|---|---:|
| Direct native process, including Python startup | 1.390 s |
| MCP analyzer call | 1.513 s |
| Server wrapper execution | 1.493 s |
| MCP server startup, separate | 1.467 s |
| Scientific MCP calls | 1 |
| Structured JSON response | 1,720 bytes |
| Serialized MCP result | 3,912 bytes |

The generated fixture has 24 unambiguous nucleus IDs and 46 native neighbor
observations. These are synthetic validation outputs, not measurements of the actual
reference experiment. One trial per mode is not a performance distribution. MCP
result sizes exclude JSON-RPC framing and include text/structured duplication.

No model provider/LLM was invoked. Actual model identifier, input/output/total/
cached/reasoning tokens and cost are null/unavailable. Autonomous-agent validation
remains PENDING_NOT_RUN; bytes are not actual model tokens or token estimates.

## Integrity, changed files and remaining limits

Hash checks confirmed unchanged actual scientific ECSV files/reference copies,
existing tracing/localization merged artifacts, Step 1c baseline, saved manual
approval and native Python source. The synthetic benchmark additionally verified
its own scientific inputs, merge/baseline/Pearson/approval files. This is scoped
file-hash verification, not a scan of all raw images or unrelated files.

Added tracing_analysis.py, trace_analyzer_worker.py, tests/test_trace_analyzer.py,
benchmarks/benchmark_trace_analyzer.py, references/trace-analyzer.md and this report.
Updated registration/discovery counts, config example, skill, AGENTS, READMEs,
tool catalog, roadmap and historical output-audit status. Existing server functions,
Step 0, collection/Pearson, approval, both merges, merged statistics and the report
server remain unchanged. No native source file changed.

Capture relies on the pinned native/Matplotlib interface and must be checked after
backend updates. Only globally unique trace IDs, one chromosome, explicit micron
calibration and unambiguous genomic mappings are supported by this operation.
Cross-ROI collisions and ambiguous inputs fail rather than invoke a new scientific
policy. PNG direct equivalence and SVG transport were tested; PDF is exposed through
the unchanged native formatter but not separately exercised in this milestone.

Local evidence relative to the amel workspace:

- implementation/trace-analyzer/trace-step0.xml and report.xml: exact regressions.
- implementation/trace-analyzer/no-neighbor-edge.xml: additional scientific edge case.
- implementation/trace-analyzer/partial-failure-edge.xml: interrupted metadata/log preservation.
- implementation/trace-analyzer/scope-integrity.json: unchanged completed stages.
- acceptance/trace_analyzer_2026-10-22/source-integrity.json: protected original hashes.
- Same acceptance directory, actual-reference-preflight.json: actual rejection.
- synthetic-benchmark/benchmark.json: explicitly synthetic native-equivalence/timing/
  byte records and protected hashes; corresponding native figures/returns/logs.
- synthetic-benchmark/mcp/0103ea7fbb0e453ba545a72b1b00fd3a/: complete successful
  synthetic analysis evidence, numerical arrays and five figures.

## Stop and next milestone

Stop for owner review. Next is separately approved verification/integration of
localization_analyzer on merged unfiltered localization data. After both analyzers
have validated outputs, chromatin-report-mcp may compose the comprehensive
pre-filtering report from Step 0/per-ROI stats, Pearson/approval, both merges,
Step 1c and analyzer numerical/figure/warning artifacts. Missing trace analysis of
the actual reference must remain explicit, never reported as complete. Filtering
comes afterward. No later stage was implemented or invoked here.
