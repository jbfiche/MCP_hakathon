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


def report_coefficient(value):
    """Round presentation only; complete native precision stays in results.json."""
    return 'undefined' if value is None else f'{value:.4f}'


def roi_name(value):
    label = str(value)
    return 'ROI ' + cell(label.zfill(3) if label.isdecimal() else label)


def format_pearson_report(detail):
    """Minimal local correlation report; evidence and approval formatting unchanged."""
    datasets, comparisons = detail['datasets'], detail['comparisons']
    by_index = {d['index']: roi_name(d['roi']) for d in datasets}
    if len(datasets) == 2 and len(comparisons) == 1:
        pair = comparisons[0]
        lines = [f"# Pearson QC — {by_index[pair['first']]} vs {by_index[pair['second']]}", '',
                 f"**Pearson r = {report_coefficient(pair['pearson_r'])}**", '',
                 f"Shared barcode pairs: {pair['shared_non_nan_pairs']}"]
    else:
        lines = ['# Pearson QC', '',
                 '| First ROI | Second ROI | Pearson r | Shared barcode pairs |',
                 '|---|---|---:|---:|']
        lines += [f"| {by_index[c['first']]} (index {c['first']}) | {by_index[c['second']]} (index {c['second']}) | {report_coefficient(c['pearson_r'])} | {c['shared_non_nan_pairs']} |"
                  for c in comparisons]
    lines += ['', f"Figure: [{detail['artifacts']['figure']}]({detail['artifacts']['figure']})", '']
    if len(datasets) == 2:
        lines += ['Dataset indices: ' + '; '.join(f"{d['index']} = {by_index[d['index']]}" for d in datasets) + '.']
    else:
        lines += ['| Dataset index | ROI |', '|---:|---|']
        lines += [f"| {d['index']} | {by_index[d['index']]} |" for d in datasets]
    lines += ['', 'Complete numerical results, scientific warnings and provenance: [results.json](results.json).']
    return '\n'.join(lines) + '\n'


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
