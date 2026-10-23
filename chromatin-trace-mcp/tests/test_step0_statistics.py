"""Native statistics are descriptive evidence, not additional acceptance thresholds."""
import contextlib
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

import pytest
from astropy.table import Table
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator

from chromatin_trace_mcp import step0 as s, step0_statistics as integration, trace_statistics as adapter
from chromatin_trace_mcp.server import trace_stats, _DATASETS
from test_step0 import experiment, write_roi, policy, table_at


@pytest.fixture
def anyio_backend(): return 'asyncio'


def stats(doc): return [r['trace_stats'] for r in doc['rois']]


def test_native_equivalence_per_roi_evidence_reports_and_integrity(experiment):
    first,_=write_roi(experiment,'092');second,_=write_roi(experiment,'093',barcodes=(1,2))
    paths=list(experiment.rglob('*.ecsv'));before={p:p.read_bytes() for p in paths};catalog=dict(_DATASETS)
    doc=s.evaluate(str(experiment),policy(('92','93')));results=stats(doc)
    assert doc['status']=='PASS' and len(results)==2
    for record,path in zip(results,[first,second]):
        console=io.StringIO()
        with contextlib.redirect_stdout(console): adapter.native.compute_trace_statistics(path)
        text=console.getvalue().strip()
        assert record['status']=='COMPUTED'
        assert record['unique_roi_count']==int(re.search(r'Number of unique ROIs:\s*(\d+)',text)[1])==1
        assert record['unique_trace_count']==int(re.search(r'Number of unique chromatin traces:\s*(\d+)',text)[1])==1
        assert record['unique_barcode_count']==int(re.search(r'Number of unique barcodes:\s*(\d+)',text)[1])
        assert record['traceratops_report']==text
        assert record['input_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
        assert record['source_file']==str(path) and record['scope']=='original_individual_roi_tracing'
        assert record['input_mode']=='private_read_only_snapshot' and len(record['native_module_sha256'])==64
    summary=s.save_validation_result(doc);assert summary['trace_stats_status']=='COMPLETE'
    assert summary['trace_stats_computed']==2 and summary['trace_stats_errors']==0
    stored=json.loads(Path(summary['details_path']).read_text());assert stats(stored)==results
    assert hashlib.sha256(Path(summary['details_path']).read_bytes()).hexdigest()==summary['validation_sha256']
    for key in ['human_report_path','html_report_path']:
        text=Path(summary[key]).read_text();assert 'ROI 092' in text and 'ROI 093' in text
        assert 'Native trace_stats' in text and 'Descriptive counts only' in text
    assert before=={p:p.read_bytes() for p in paths} and _DATASETS==catalog


@pytest.mark.parametrize('case',['missing','ambiguous','invalid','schema','size-limit','record-limit'])
def test_ineligible_tables_have_explicit_not_run_without_native_calls(experiment,monkeypatch,case):
    trace,_=write_roi(experiment);kw={}
    if case=='missing':trace.unlink()
    elif case=='ambiguous':trace.with_name('Trace_3D_barcode_mask-mask1_ROI-92.ecsv').write_bytes(trace.read_bytes())
    elif case=='invalid':trace.write_text('invalid')
    elif case=='schema':
        table=Table.read(trace,format='ascii.ecsv');table.remove_column('Trace_ID');table.write(trace,format='ascii.ecsv',overwrite=True)
    elif case=='size-limit':kw['max_table_bytes']=1
    elif case=='record-limit':kw['max_records']=1
    def forbidden(*args,**kwargs):raise AssertionError('Native must not run on ineligible/localization inputs')
    monkeypatch.setattr(adapter.native,'compute_trace_statistics',forbidden)
    doc=s.evaluate(str(experiment),policy(**kw));record=stats(doc)[0]
    assert record['status']=='NOT_RUN' and record['reason']
    summary=s.summarize(doc);assert summary['trace_stats_status']=='INCOMPLETE' and summary['trace_stats_not_run']==1
    assert 'unique_trace_count' not in record


def test_native_error_keeps_existing_validation_findings_and_separate_stats_status(experiment,monkeypatch):
    write_roi(experiment)
    def fail(path):raise SystemExit(1)
    monkeypatch.setattr(adapter.native,'compute_trace_statistics',fail)
    doc=s.evaluate(str(experiment),policy());assert doc['status']=='PASS'
    assert stats(doc)[0]['status']=='ERROR' and 'exit code 1' in stats(doc)[0]['reason']
    summary=s.save_validation_result(doc);assert summary['trace_stats_status']=='INCOMPLETE' and summary['trace_stats_errors']==1
    assert 'ERROR' in Path(summary['human_report_path']).read_text()
    assert not doc['findings']


def test_mutation_during_native_execution_discards_statistics(experiment,monkeypatch):
    trace,_=write_roi(experiment);original=adapter.native.compute_trace_statistics
    def mutate(snapshot):
        assert Path(snapshot)!=trace and Path(snapshot).read_bytes()==trace.read_bytes()
        original(snapshot);trace.write_text(trace.read_text()+'\n')
    monkeypatch.setattr(adapter.native,'compute_trace_statistics',mutate)
    doc=s.evaluate(str(experiment),policy());record=stats(doc)[0]
    assert record['status']=='ERROR' and 'changed since' in record['reason']
    assert 'unique_trace_count' not in record


@pytest.mark.parametrize('phase',['inspection','structure'])
def test_partial_checks_do_not_run_statistics(experiment,monkeypatch,phase):
    write_roi(experiment)
    def forbidden(*args,**kwargs):raise AssertionError('Not a statistics phase')
    monkeypatch.setattr(adapter.native,'compute_trace_statistics',forbidden)
    doc=s.evaluate(str(experiment),policy(),phase=phase)
    assert all('trace_stats' not in r for r in doc['rois'])
    assert s.summarize(doc)['trace_stats_status']=='NOT_RUN'


@pytest.mark.anyio
async def test_public_trace_stats_compatibility_and_failure_on_unparseable_native_text(experiment,monkeypatch):
    trace,_=write_roi(experiment);monkeypatch.setenv('CHROMATIN_TRACE_ECSV',str(trace))
    result=await trace_stats();assert result.unique_roi_count==1 and result.unique_trace_count==1 and result.unique_barcode_count==3
    monkeypatch.setattr(adapter.native,'compute_trace_statistics',lambda path:print('unexpected native report'))
    with pytest.raises(Exception,match='unexpected format'):await trace_stats()


@pytest.mark.anyio
async def test_real_stdio_one_validation_call_and_cached_retrieval(experiment):
    write_roi(experiment);before={p:p.read_bytes() for p in experiment.rglob('*.ecsv')}
    params=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=dict(os.environ))
    async with Client(params,read_timeout_seconds=60) as client:
        tools={t.name:t for t in (await client.list_tools()).tools};assert len(tools)==27
        result=await client.call_tool('run_experiment_validation',{'experiment_root':str(experiment),'rules':policy().model_dump()})
        value=result.structured_content;assert value['status']=='PASS' and value['trace_stats_computed']==1
        Draft202012Validator(tools['run_experiment_validation'].output_schema).validate(value)
        assert len(json.dumps(value).encode())<6500 and 'rois' not in value
        details=Path(value['details_path']);original=details.read_bytes()
        summary=await client.call_tool('get_validation_summary',{'validation_run_id':value['run_id']})
        assert summary.structured_content['trace_stats_computed']==1 and details.read_bytes()==original
    assert before=={p:p.read_bytes() for p in before}


@pytest.mark.parametrize('fail',[False,True])
def test_native_warnings_are_preserved_for_success_and_failure(experiment,monkeypatch,fail):
    import warnings
    write_roi(experiment);original=adapter.native.compute_trace_statistics
    def warned(path):
        warnings.warn('native warning fixture',RuntimeWarning)
        if fail:raise SystemExit(1)
        original(path)
    monkeypatch.setattr(adapter.native,'compute_trace_statistics',warned)
    doc=s.evaluate(str(experiment),policy());record=stats(doc)[0]
    assert record['status']==('ERROR' if fail else 'COMPUTED')
    assert record['warnings']==['RuntimeWarning: native warning fixture']
    summary=s.save_validation_result(doc)
    assert record['warnings']==stats(json.loads(Path(summary['details_path']).read_text()))[0]['warnings']
    assert 'native warning fixture' in Path(summary['human_report_path']).read_text()
