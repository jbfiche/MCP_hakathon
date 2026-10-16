# ECSV file-role identification evidence

Inspected 16 October 2026. Backend audited at Traceratops 1.0.1, source commit
`261a48fe92498abcb154891fe6e5a5ca8219b610` recorded in the trace server's lockfile.
The separate development checkout was at a newer commit; audit execution used a
read-only export of the locked source, not that checkout's current contents.

## Verified observations

Repository fixtures and the supplied real ROI `092` share these column signatures:

- Tracing: `Spot_ID`, `Trace_ID`, `x`, `y`, `z`, `ROI #`, `Barcode #`.
- Localization: `Buid`, `ROI #`, `Barcode #`, `xcentroid`, `ycentroid`, `zcentroid`.

The complete real trace also has `Chrom`, `Chrom_Start`, `Chrom_End`, `Mask_id`,
and `label`. Its metadata comments contain `xyz_unit=micron` and
`genome_assembly=mm10`. These strings are observations, not independently verified
biological annotations. Localization metadata says `filtered` and `registered`;
it does not supply a file-role standard. No metadata role tag was found.

The real localization file is under `092/localize_3d/data/`, whereas the provided
simplified structure omitted `data/`. Filename discovery supports both layouts
explicitly. If both canonical localization files exist, the association is
ambiguous and neither is chosen.

A directory called `092` corresponds to filename `ROI-92` and table ROI integer 92.
The real tracing directory also contains a KD-tree trace and derived
`*_Matrix_uniqueBarcodes.ecsv` tables. Derived barcode indexes are not trace
records and must not match a trace role.

## Filename assumptions (default first pipeline)

The owner selected mask-based traces. The default role pattern is
`tracing/data/Trace_3D_barcode_mask-*_ROI-*.ecsv`, additionally anchored to a final
`ROI-<integer>.ecsv` suffix. Mask0 is not hardcoded. Multiple masks are ambiguous.
KD-tree traces remain inventoried but are not selected by this default policy.

Localization patterns are `localize_3d/data/localizations_3D_barcode.ecsv` and
`localize_3d/localizations_3D_barcode.ecsv`. Versioned and per-cycle localization
files are not equivalent filename matches. These conventions are configurable;
they are not claims about every pyHiM release or experiment.

## Implemented column-signature mode

Metadata discovery reads at most 256 KiB of ECSV header using Astropy, requiring
exact observed column signatures above. It reports `column_signature`, rather
than claiming an invented metadata tag. A table satisfying both signatures is
not uniquely identified. All matching files are reported, so versioned tables
or different tracing algorithms can remain ambiguous. Full record-level ROI and
barcode checks occur during table validation, not header discovery.

Automatic mode tries configured filenames first and uses signatures only when no
match exists. It never uses header evidence to choose between multiple masks.

## Unverified or deliberately unsupported assumptions

- The schema alone does not establish experiment identity, final processing stage,
  genome assembly correctness, tissue, barcode meaning, mask selection or readiness.
- No expected barcode or ROI list was present in the supplied sample. Observations
  cannot serve as the expected experimental design without an explicit policy.
- A BED name or location alone does not establish its association. Existing
  Traceratops readers demonstrate barcode column 4 in specific workflows and an
  optional remapped barcode convention; the validator requires an explicit column.
- Additional pyHiM/4DN schemas are not silently treated as these ECSV schemas.
  Extend tested column rules/signatures after obtaining representative evidence.
