# Native genomic annotation before trace analysis

## Interface and assembly authority

`trace_genomic_coordinates(baseline_run_id, baseline_sha256, experiment_root,
bed_relative, bed_sha256)` creates a new derivative of the exact original merged,
unfiltered tracing ECSV linked to Step 1c. It does not merge, recalculate baseline
statistics, alter approval, or run an analyzer. The BED must be inside the authorized
original experiment root belonging to the approved collections. It stays unchanged.

Configure `CHROMATIN_GENOME_REFERENCE` to a host-controlled JSON file containing:

```json
{"assembly":"dm6", "authority":"Researcher-confirmed assembly, with experiment and decision reference",
 "chromosome_sizes":{"chr2L":23513712},
 "chromosome_sizes_source":"https://hgdownload.soe.ucsc.edu/goldenPath/dm6/bigZips/dm6.chrom.sizes"}
```

This is an example for an explicitly confirmed dm6 experiment, not an assembly
default. Require assembly authority before execution; chromosome names, interval
bounds and inherited Traceratops metadata do not independently identify an assembly.
The reference file and BED are hashed and rechecked before publication and whenever
the analyzer consumes annotation. Reference or BED changes invalidate the derivative.
The host controls this file; an ordinary tool argument cannot change assembly policy.
A partial chromosome-size reference supports only its listed contigs.

## Native behavior and validation

Use unmodified native `load_bed_file` and `impute_genomic_coordinates`. Require
five columns: chromosome, start, end, original barcode and replacement barcode.
Native accepts integer or barcode_N identities. No replacement is disabled,
substituted or recursively applied; each original row is mapped once. Reject native
skipped/malformed rows, duplicate original IDs (even identical duplicates), duplicate
replacement IDs, missing observed originals, invalid/noninteger identifiers, invalid
or out-of-bounds intervals, repeated/overlapping intervals, and integer overflow or
fixed-width chromosome truncation. Additional unused BED mappings are recorded;
replacement IDs need not be consecutive in general. No scientific acceptance
threshold, genome inference, liftover or coordinate convention conversion is added.
Coordinates are assigned exactly as written in the authoritative BED.

Complete barcode coverage is required before native execution; no partial-coverage
prompt or force-continuation route is exposed. Reuse the exact current scientific
approval and source-contribution checks. Under the existing approval lock, recheck
all parent evidence, BED and assembly reference before publishing success.

## Artifacts and metadata correction

`CHROMATIN_GENOMIC_OUTPUT_DIR` defaults to `<CHROMATIN_TRACE_OUTPUT_DIR>/genomic_annotations`
(or `./results/genomic_annotations`). It must be separate from experiment inputs,
collection/Pearson/merge/baseline/localization/analyzer stores. A fresh UUID run holds:

- `native_annotated.ecsv`: complete unchanged native result, including inherited metadata.
- `annotated_traces.ecsv`: same native scientific values, with only the assembly
  declaration explicitly corrected to the host-configured authority. Native itself
  does not correct inherited assembly metadata. Both versions are retained and hashed.
- `barcode_mapping.json`: full original-to-replacement IDs and chromosome intervals.
- `native.log`: complete native stdout/stderr; warnings also appear in evidence.
- `annotation.json`: parent merge/baseline checksums, approval revision/fingerprint,
  selected dataset indices, native version/module/table hashes, input and output
  metadata, BED/reference/artifact hashes, row/barcode coverage, warnings and timing.

Verify exact row order/count, ROI/Trace_ID/Spot_ID, x/y/z, all other nonannotation
columns, masks, dtypes and column metadata. Only Chrom, Chrom_Start, Chrom_End,
Barcode #, the native save comment cleanup/addition and explicit assembly correction
may differ. Error responses publish no successful derivative. Native failure logs
are captured while executing but currently are not published if annotation fails.

Return only compact counts, warnings and artifact paths/hashes. Repeat explicit
calls create independent versioned runs; the workflow annotates its merged input
once and passes that saved artifact to the analyzer. No automatic per-ROI annotation.

## Analyzer and localization consistency

`trace_analyzer` accepts optional `annotation_run_id` and `annotation_sha256`, which
must be supplied together. Its original successful Step 1c baseline ID/checksum is
still required. Original merge approval, native implementation, source contributions,
units and integrity remain checked against the original merge. Separately validate
annotation checksums, mapping, reference, allowed row changes and native output.
The worker receives the verified annotated bytes. Recheck both chains before
publication; never weaken the generic merge row validator to allow annotation.
Existing clients with already valid genomic inputs may omit the optional reference.

Merged localizations retain original barcode IDs. Equal numbers across annotated
traces and unmodified localizations can now mean different loci. Use the saved
mapping (including its inverse, guaranteed unique) to translate barcode meanings;
use Spot_ID/Buid for spot correspondence, not barcode-only joins. Source Pearson
and per-ROI/merged baseline statistics retain original barcode identity and artifacts.
Counts are invariant under bijective renaming, but labels and native numerical
adjacency/genomic-neighbor eligibility can change intentionally. Future comprehensive
reports must identify which identifier namespace each artifact uses.

Approval continues to cover the exact tracing dataset selection; researcher assembly
confirmation and BED authority are separately identified, not fabricated by the agent.
Do not reuse approval from older Pearson/collection runs for newly generated evidence.
