# Comprehensive pre-filtering QC report

Scientific execution stays in chromatin-trace-mcp. After merged trace_stats and
both native analyzers, chromatin-report-mcp composes saved evidence with one call:
`generate_experiment_qc_report(manifest_id, manifest_sha256)`.
The existing comparison Markdown/HTML/PDF tools remain unchanged. Step 0 and
ordinary Pearson reports remain in trace. No cross-server MCP calls are introduced.

## Host configuration and setup

Use the existing Python MCP environment, command `python -m chromatin_report_mcp.server`
and report package `src` on PYTHONPATH. Configure these host-owned variables:

- `CHROMATIN_QC_MANIFEST_DIR`: directory of saved, host-provisioned JSON manifests.
- `CHROMATIN_REPORT_ARTIFACT_ROOTS`: path-separated allowlist of scientific stores,
  original experiment roots and genome-reference directories needed for verification.
- `CHROMATIN_REPORT_OUTPUT_DIR`: separate report store, outside scientific run
  directories and the original experiment. The experiment view can safely link here.

The host prepares a manifest once from the existing compact workflow-response index:

```
python -m chromatin_report_mcp.prepare_manifest /authorized/artifacts.json workflow_id
```

The index contains Step 0, tracing/localization collection, Pearson, current approval,
trace/localization merge, merged_trace_stats, trace_genomic_coordinates, trace_analyzer
and localization_analyzer responses. The command prints the ID and SHA-256 for the
single report tool call. It verifies saved provenance before writing a new manifest,
refuses to overwrite existing IDs and does not call scientific tools.
This setup is local orchestration, not a new agent tool or an extra MCP call.

Manifest schema 1: `title`, `roles` and `files: [{path, sha256}]`, plus `schema_version`.
Roles are step0, pearson, approval, trace_merge, localization_merge, baseline,
annotation, trace_analysis, localization_analysis, mapping, reference,
trace_numerical and localization_numerical. Files cover original source tables,
validated collection copies/manifests, all saved stage evidence, BED, genome reference,
figures, logs and numerical artifacts. No full datasets go through model arguments.
The ID/checksum authenticates the selected host snapshot, not the researcher identity.
Keep configuration/manifests under trusted host control; the agent must not be able
to rewrite these files or expand filesystem roots. OS permissions/container mounts
remain the host's responsibility; allowlisting is not a process sandbox.

## Verification and output

Every file is streamed and SHA-256 checked. Paths must be absolute, under authorized
roots, regular and free of symlink components. JSON is bounded to 32 MiB, individual
files to 2 GiB, manifests to 512 artifacts. Full ECSV/NPY/NPZ data are hashed, never
parsed, deserialized or measured by reporting. Complete analyzer metadata are read
locally; no scientific runtime import/execution occurs.

The composer checks the current human APPROVED selection, its exact evidence
fingerprint, Pearson report/figure/matrix/parameters and collection/source bindings.
It verifies merge contributions, original ROI associations, baseline, annotation,
assembly authority and analyzer cross-references. Missing required stages, mismatched
hashes, stale approval or inconsistent provenance fail closed without a published
report. Required analyzers must be ANALYZED; missing optional numeric values are
shown as unavailable. It does not repair scientific results or grant approval.

All sources and the manifest are checked again before publication to a fresh UUID
report directory containing `report.html` and `evidence.json`. Existing runs are never
overwritten. Status COMPLETE_WITH_LIMITATIONS means composition completed, not
biological acceptance. Approval verification is point-in-time; later scientific
operations still require their own approval checks. Cooperating artifact stores must
remain immutable; local users with write access can change files after publication.

HTML uses escaped values, no scripts/external assets, and absolute verified `file:`
links so native figures work through experiment-view directory symlinks. Figures and
large arrays are not copied or embedded. The report therefore depends on its local
artifact stores and is not a portable single-file export. Browser policies can block
local file loading; automatic visual preview is not guaranteed. Print CSS is supplied,
but a comprehensive PDF export is not implemented: the existing PDF tool's dataset
comparison schema is unsuitable and is not repurposed silently.

## Scientific presentation

Separate original per-ROI counts from original merged trace_stats; distinguish global
unique Trace_IDs and ROI/Trace_ID pairs. Include pairwise Pearson coefficients,
index-to-ROI selection, both merge contributions, researcher-confirmed assembly,
complete original/replacement barcode mapping, signed native neighbor displacement
statistics and five trace figures, native localization counts and its four-panel figure.

Explicitly describe pooled localization ROIs, undeclared localization z units,
upstream filtered/registered metadata, repeated-barcode/allele limitations, native
frequency-bin limits and unavailable precision/registration/allele-resolved metrics.
Do not treat correlation as biological equivalence or invent acceptance thresholds.
Localizations retain original barcode IDs; annotated traces use BED replacements.
Use Spot_ID/Buid for spot identity, never barcode alone. Full saved warnings/findings,
versions, run IDs, artifact paths and SHA-256 checksums remain available in the report.

## Measurement limits

Record one report-generation call's elapsed time and structured/serialized bytes.
Schema discovery is a separate transport request, not scientific computation. No
provider-backed agent is required to compose this deterministic report. Actual model
tokens/cost remain unavailable unless a real provider-backed run reports them.
