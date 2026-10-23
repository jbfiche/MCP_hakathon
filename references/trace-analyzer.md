# Native trace_analyzer on merged, unfiltered data

Explicit trace-server integration only. No new localization analyzer, filtering,
comprehensive report or cross-server mechanism is introduced. No previous registered
trace_analyzer wrapper existed; reuse includes the native entry point, merge/baseline
validators, approval gate and configured artifact stores.

## One-call interface

`trace_analyzer(baseline_run_id, baseline_sha256, output_format="png",
neighbor_distance_range="1", random_seed=0)` accepts a saved Step 1c run and its
statistics.json checksum. It obtains the exact merge/provenance references from
that evidence. No arbitrary path, dataset override, filtering, collision policy or
approval argument is exposed. Formats: png/svg/pdf. Distance plotting range is
native `auto` or a finite positive number in microns; it controls axes, not sample
selection or an acceptance threshold. Default 1 preserves the native default and
can clip displayed density; select auto when appropriate. NumPy seed is recorded,
0 by default, making the native 1000-resample bootstrap reproducible on the pinned
runtime. No formula or resampling algorithm is changed.

The optional native plotXYZ route is deliberately not exposed: process_traces
hard-codes pixel calibration [0.1,0.1,0.25] and creates very large extra plots. A
scientifically reviewed upstream calibration interface is needed before exposing
it. This integration preserves the five standard native figures.

## Provenance and source protection

Verify successful merged-unfiltered Step 1c evidence/checksum; exact merge ECSV and
provenance hashes; native merge and statistics versions/hashes; current approved
Pearson selection/revision/fingerprint and source collection hashes. Reuse
merged_statistics verification functions and the merge row-contribution validator.
Native execution receives identical private read-only input bytes, not a newly
registered path. No scientific input or existing artifact is edited.

Before success publication, recheck approval and all bound collection/Pearson
artifacts, baseline bytes/log, merge/provenance/log hashes under the existing
approval lock. Changed or revoked evidence cannot publish ANALYZED. Application
hashes/locks do not isolate another unrestricted OS writer. Trusted artifact stores
and a pinned scientific environment remain prerequisites.

## Scientific preflight and native limitations

Required: existing trace columns (Spot_ID, Trace_ID, ROI #, Barcode #, x/y/z), plus
Chrom, Chrom_Start, Chrom_End. Required fields must be unmasked; Trace_ID nonempty;
coordinates finite numeric; barcodes integer; intervals integer/nonnegative with
end > start. One non-placeholder chromosome is required for this native neighbor
analysis; multi-chromosome behavior needs an agreed upstream policy.

Each global Trace_ID must belong to one output ROI. Multiple native routines group
only by Trace_ID: trace distributions, bootstrap detection, neighbor distances,
barcode multiplicities and trace-centering projections. Cross-ROI collisions are
rejected, never silently combined, excluded or relabeled. Original units must be
explicitly microns in approved source metadata/columns, not supplied by native
merge constructor defaults. Assembly metadata is recorded, not independently
certified; missing original assembly declarations are warned about.

The native genomic-order function checks consistent coordinates per barcode. The
wrapper rejects identical intervals assigned to different barcodes because they
do not establish an order. Chrom=xxxxx/unknown and similar placeholders are rejected.
No BED mapping is inferred or inserted. Native neighbor pairs must be consecutive
**both numerically and in genomic rank**; gaps may yield no pairs. Native zero
returns when there are no eligible pairs are labeled UNAVAILABLE_NO_ELIGIBLE_NEIGHBORS,
not measured zero distances. Barcode multiplicities remain unchanged: no allele
separation or automatic rejection of repeated barcode observations. Their native
neighbor pairing can be ambiguous; this is explicitly warned about.

The native relative-frequency figure uses multiplicity bins 1–8. Complete returned
barcode multiplicity lists are preserved even when the displayed bins omit larger
values. Those lists include only traces in which the barcode was observed; they
are not a zero-filled detection matrix.

## Native execution and numerical preservation

Execute unmodified traceratops.trace_analyzer.process_traces in a separate Python
process using relative input basename trace.ecsv in a private output directory.
This avoids the native input.split('.')[0] parent-path bug. Native import changes
to Matplotlib defaults are isolated from the MCP host, and process-local NumPy
seeding does not alter host RNG state. A 300-second child timeout bounds elapsed
execution; existing input-byte/file limits are not OS RAM/CPU quotas.

Capture native values without rerunning calculations: transparent wrappers return
the original objects from native neighbor-distance and barcode-statistics functions.
The worker copies arrays already passed to native histogram, violin, image and
hexbin calls, along with native histogram/bin results. This retains full-precision
neighbor mean/std values; complete returned barcode multiplicities; per-trace
histogram observations and bins; all bootstrap samples with native barcode labels;
neighbor raw vectors and density bins; native relative-frequency matrix; and native
centered-projection coordinates/bins. Mask arrays are retained when supplied.

The native plotting calls execute unchanged; capture performs no distance,
bootstrap, histogram, KDE, normalization or scientific-threshold calculation.
This preserves numerical values the native entry point returns or supplies to plots,
not every private intermediate variable. No values are reconstructed from pixels.
The capture boundary is version-sensitive: source hashes, five expected figures,
expected neighbor histogram interface and native equivalence tests guard it.

## Local artifacts and compact MCP response

Configure CHROMATIN_TRACE_ANALYZER_OUTPUT_DIR outside original experiments,
collection/Pearson/merge/localization-merge and Step 1c stores. Default:
<CHROMATIN_TRACE_OUTPUT_DIR>/trace_analysis, otherwise ./results/trace_analysis.
Use the same collection/Pearson/merge/baseline stores as approved previous stages.
Each run has a fresh UUID directory containing:

- analysis.json: status, baseline/merge/approval links, source contributions,
  checks, parameters, native/worker hashes, warnings and small numerical summary.
- artifacts.json: every generated artifact's filename, size and SHA-256;
  manifest hash is bound by analysis.json, whose checksum is returned.
- numerical_outputs.json and numerical_outputs.npz: native return/plot-call mapping,
  labels, warnings, NumPy/Matplotlib versions, masks and complete numerical arrays.
  Load NPZ with allow_pickle=False. No raw scientific table is returned or copied
  into the published output; the temporary input is removed.
- stdout.log/stderr.log: native processing messages and errors.
- Five native figures: trace statistics, barcode detection, neighbor distances,
  relative barcode frequencies and trace-centered projections.

ANALYZED means execution/evidence/artifact checks succeeded, not biological PASS.
Compact JSON contains evidence path/hash, artifact manifest/output directory,
figure count, six available native neighbor values plus availability/count,
bounded warning previews, execution seconds and structured-response bytes.
No tables, images, full reports or raw plot arrays enter default model context.

Native exceptions, timeout or evidence changes after execution preserve available
logs/numerical files/partial figures with status ERROR and no success summary.
Scientific preflight failures return ERROR before execution/output creation. Full
warnings remain local. No report-server call is needed just to return artifacts.

## Benchmark and next stage

Run benchmarks/benchmark_trace_analyzer.py with an existing approved baseline and
trusted checksum, plus a fresh output directory. It never grants real approval.
Direct native execution and MCP use seed 0/PNG/auto; compare full native returns and
all five PNG bytes. One trial records elapsed time and response sizes, not a
performance distribution. Synthetic fixtures and synthetic approval tests must be
identified as such; they are not successful analysis of an actual experiment.
Provider-backed agent validation/tokens remain pending unless actually measured.

After owner review, the next milestone is verification/integration of the existing
localization_analyzer wrapper on merged unfiltered localizations. Only after both
analyzers are valid may chromatin-report-mcp compose the comprehensive pre-filtering
report from Step 0/Pearson/approval/merges/baseline and both analyzer artifacts.
Filtering comes afterward. None of those later stages is implemented here.


## Verified genomic derivative

Optional `annotation_run_id` / `annotation_sha256` select a checked native annotation
derivative while retaining the original Step 1c baseline. Both references are required
together. See [annotation evidence and barcode namespaces](genomic-annotation.md).
Original merge/source validators still check the original table; separate exact
derivation checks permit only native genomic/barcode assignments and documented
assembly metadata correction. Both evidence chains are rechecked before publication.
