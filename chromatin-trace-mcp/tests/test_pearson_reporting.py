"""Presentation scalability does not change native scientific evidence or approval binding."""
import copy
import itertools
import json

from chromatin_trace_mcp.pearson_reporting import format_pearson_report, format_approval_review


def evidence(count):
    datasets=[{'index':i,'label':f'ROI-{i}.ecsv','filename':f'ROI-{i}.ecsv','roi':str(i),
               'collection_run_id':'a'*32,'rows':3,'distance_pair_count':3} for i in range(count)]
    pairs=[{'first':i,'second':j,'pearson_r':None if i==1 else -0.5,'shared_non_nan_pairs':3} for i,j in itertools.combinations(range(count),2)]
    warnings=['Repeated barcodes use the last row without allele separation.', 'The native figure has a fixed 0–1 color scale.']
    return {'datasets':datasets,'comparisons':pairs,'warnings':warnings,'artifacts':{'figure':'matrix.png','native_matrix':'matrix.npy'}}


def test_small_report_keeps_all_results_and_warnings_without_mutation():
    detail=evidence(2);before=copy.deepcopy(detail)
    rendered=format_pearson_report(detail)
    assert '| 0 | 1 | -0.5 | 3 |' in rendered
    assert 'Datasets: 2. Pairwise comparisons: 1. Undefined: 0.' in rendered
    assert all(w in rendered for w in detail['warnings'])
    assert 'results.json' in rendered and 'matrix.npy' in rendered and 'matrix.png' in rendered
    assert detail==before


def test_large_saved_report_preserves_complete_pairwise_evidence():
    detail=evidence(32);rendered=format_pearson_report(detail)
    assert len(detail['comparisons'])==496
    assert 'Showing 10 of 496' in rendered
    assert '## Complete pairwise comparisons' in rendered
    assert '| 30 | 31 | -0.5 | 3 |' in rendered
    assert '| 1 | 2 | undefined | 3 |' in rendered
    appendix=rendered.split('## Complete pairwise comparisons')[1]
    assert sum(line.startswith('| ') for line in appendix.splitlines())==497  # header + all pairs


def test_human_form_has_all_choices_bounded_preview_and_exact_artifact_references():
    detail=evidence(32)
    ev={'binding':{'pearson_run_id':'b'*32,'datasets':detail['datasets'],'report_path':'/saved/pearson_qc.md'},
        'fingerprint':'c'*64,'comparisons':detail['comparisons'],'warnings':detail['warnings'],
        'report':'FULL_REPORT_SENTINEL'*100000,'correlation_matrix':'MATRIX_SENTINEL',
        'figure_path':'/saved/matrix.png','matrix_path':'/saved/matrix.npy','results_path':'/saved/results.json'}
    before=copy.deepcopy(ev)
    message=format_approval_review(ev,'d'*32)
    assert 'Showing 10 of 496' in message
    assert message.count(', shared pairs=')==10
    assert '30 vs 31:' not in message and '| 31 | 31 | ROI-31.ecsv |' in message
    assert 'FULL_REPORT_SENTINEL' not in message and 'MATRIX_SENTINEL' not in message
    assert all(v in message for v in ['/saved/pearson_qc.md','/saved/matrix.npy','/saved/results.json','/saved/matrix.png'])
    assert all(w in message for w in detail['warnings'])
    assert ev==before
    assert len(message.encode())<16000


def test_file_labels_cannot_break_report_table_rows():
    detail=evidence(2);detail['datasets'][0]['label']='name|with\nnewline'
    assert r'name\|with newline' in format_pearson_report(detail)
