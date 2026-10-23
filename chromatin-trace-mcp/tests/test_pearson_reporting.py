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


def test_two_roi_report_focuses_on_rounded_correlation_without_mutating_evidence():
    detail=evidence(2)
    detail['datasets'][0]['roi']='92';detail['datasets'][1]['roi']='93'
    detail['comparisons'][0].update(pearson_r=0.8691053986549377,shared_non_nan_pairs=406)
    before=copy.deepcopy(detail);rendered=format_pearson_report(detail)
    assert '# Pearson QC — ROI 092 vs ROI 093' in rendered
    assert '**Pearson r = 0.8691**' in rendered
    assert 'Shared barcode pairs: 406' in rendered
    assert '0 = ROI 092; 1 = ROI 093' in rendered
    assert '[matrix.png](matrix.png)' in rendered and '![' not in rendered
    assert '[results.json](results.json)' in rendered
    assert not any(w in rendered for w in detail['warnings'])
    assert 'Notes' not in rendered and 'preview' not in rendered
    assert len(rendered.splitlines())<=14 and detail==before


def test_large_report_shows_each_pair_once_with_saved_dataset_indices():
    detail=evidence(32);before=copy.deepcopy(detail);rendered=format_pearson_report(detail)
    assert len(detail['comparisons'])==496
    assert 'Showing 10' not in rendered and 'preview' not in rendered
    assert '| ROI 030 (index 30) | ROI 031 (index 31) | -0.5000 | 3 |' in rendered
    assert '| ROI 001 (index 1) | ROI 002 (index 2) | undefined | 3 |' in rendered
    assert sum(line.startswith('| ROI ') for line in rendered.splitlines())==496
    assert '| 31 | ROI 031 |' in rendered
    assert all(w not in rendered for w in detail['warnings'])
    assert detail==before


def test_undefined_coefficient_stays_undefined_and_zero_stays_zero():
    detail=evidence(2);detail['comparisons'][0]['pearson_r']=None
    assert '**Pearson r = undefined**' in format_pearson_report(detail)
    detail['comparisons'][0]['pearson_r']=0.0
    assert '**Pearson r = 0.0000**' in format_pearson_report(detail)


def test_duplicate_roi_labels_remain_distinguishable_by_dataset_indices():
    detail=evidence(3)
    for d in detail['datasets']:d['roi']='92'
    rendered=format_pearson_report(detail)
    assert '| ROI 092 (index 0) | ROI 092 (index 2) | -0.5000 | 3 |' in rendered
    assert '| 0 | ROI 092 |' in rendered and '| 2 | ROI 092 |' in rendered


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


def test_roi_labels_cannot_break_report_table_rows():
    detail=evidence(3);detail['datasets'][0]['roi']='name|with\nnewline'
    assert r'ROI name\|with newline' in format_pearson_report(detail)
