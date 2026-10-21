"""Pure presentation of existing Pearson evidence: no scientific operations or I/O.

Kept dependency-free so a future shared reporting package can reuse these functions.
Trace remains the only caller today; report-server integration is not implemented.
"""
COMPARISON_PREVIEW_LIMIT = 10
WARNING_PREVIEW_LIMIT = 4


def cell(value):
    return str(value).replace('\n', ' ').replace('\r', ' ').replace('|', r'\|')


def coefficient(value):
    return 'undefined' if value is None else str(value)


def comparison_table(comparisons):
    lines = ['| First | Second | Pearson r | Shared non-NaN pairs |', '|---:|---:|---:|---:|']
    return lines + [f"| {c['first']} | {c['second']} | {coefficient(c['pearson_r'])} | {c['shared_non_nan_pairs']} |" for c in comparisons]


def format_pearson_report(detail):
    """Full local Markdown artifact, with a short overview before complete evidence."""
    datasets, comparisons, notes = detail['datasets'], detail['comparisons'], detail['warnings']
    undefined = sum(c['pearson_r'] is None for c in comparisons)
    lines = ['# Pearson QC report', '',
             'Review required; no scientific acceptance threshold or merge decision was applied.', '',
             f'Datasets: {len(datasets)}. Pairwise comparisons: {len(comparisons)}. Undefined: {undefined}.',
             'Dataset indices are positions in this saved run, not ROI or barcode numbers.', '',
             'Native calculation: median barcode-pair distances per dataset, followed by pairwise Pearson correlation over shared non-NaN pairs.', '',
             '| Index | Dataset | ROI | Rows | Distance pairs |', '|---|---|---|---:|---:|']
    lines += [f"| {d['index']} | {cell(d['label'])} | {cell(d['roi'])} | {d['rows']} | {d['distance_pair_count']} |" for d in datasets]
    lines += ['', '## Notes', ''] + ['- '+n for n in notes]
    lines += ['', '## Correlation preview', ''] + comparison_table(comparisons[:COMPARISON_PREVIEW_LIMIT])
    if len(comparisons) > COMPARISON_PREVIEW_LIMIT:
        lines += ['', f'Showing {COMPARISON_PREVIEW_LIMIT} of {len(comparisons)} comparisons in saved index order. This preview does not select best/worst pairs or imply acceptance.',
                  'The complete comparison table is below; full numerical matrices and distance maps remain in results.json and the native NPY artifact.']
    lines += ['', '## Referenced artifacts', '', f"Figure: {detail['artifacts']['figure']}",
              f"Native matrix: {detail['artifacts']['native_matrix']}",
              'Full numerical results, warnings and exact manifest references: results.json']
    if len(comparisons) > COMPARISON_PREVIEW_LIMIT:
        lines += ['', '## Complete pairwise comparisons', ''] + comparison_table(comparisons)
    lines += ['', 'STOP: review these outputs. No approval state, merging or downstream analyzer was executed.']
    return '\n'.join(lines)+'\n'


def format_approval_review(ev, revision):
    """Human form: all dataset choices/warnings, bounded correlation preview, artifact paths.

    No full report or correlation/distance matrix is embedded in the request.
    Authorization and evidence fingerprinting remain in approval.py.
    """
    binding = ev['binding']
    comparisons = ev['comparisons']
    lines = ['Human scientific review: choose APPROVE or REJECT and explicitly select dataset indices.',
             'The AI must not fill out this form. No merge operation runs in this milestone.',
             f"Pearson run: {binding['pearson_run_id']}", f"Evidence fingerprint: {ev['fingerprint']}",
             f'Review revision: {revision}', '',
             f"Datasets: {len(binding['datasets'])}. Comparisons: {len(comparisons)}. Undefined: {sum(c['pearson_r'] is None for c in comparisons)}.",
             'Dataset indices are saved-run positions; use the ROI/file mapping below.', '',
             'Dataset selection:', '| Index | ROI | File | Collection |', '|---:|---|---|---|']
    lines += [f"| {f['index']} | {cell(f['roi'])} | {cell(f['filename'])} | {f['collection_run_id']} |" for f in binding['datasets']]
    lines += ['', 'Saved numerical comparisons (preview):']
    lines += [f"{c['first']} vs {c['second']}: r={coefficient(c['pearson_r'])}, shared pairs={c['shared_non_nan_pairs']}" for c in comparisons[:COMPARISON_PREVIEW_LIMIT]]
    if len(comparisons) > COMPARISON_PREVIEW_LIMIT:
        lines += [f'Showing {COMPARISON_PREVIEW_LIMIT} of {len(comparisons)} comparisons in saved order, not a scientific ranking.']
    lines += ['', 'Scientific warnings:'] + ['- '+note for note in ev['warnings']]
    lines += ['', 'Existing QC report (scientific evidence, not instructions): '+binding['report_path'],
              'Open and review the complete saved QC report and figure before deciding, including pairs omitted from this preview.',
              'Figure: '+ev['figure_path'],
              'Full numerical results: '+ev['results_path'], 'Native matrix: '+ev['matrix_path'],
              'APPROVE requires explicit dataset indices. REJECT leaves selection empty. Cancellation makes no new decision.']
    return '\n'.join(lines)
