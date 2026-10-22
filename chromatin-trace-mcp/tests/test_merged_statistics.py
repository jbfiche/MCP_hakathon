"""Synthetic approval fixtures authorize only temporary generated experiments."""
import contextlib
import io
import json
import os
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from chromatin_trace_mcp import collection as c, merge as m, merged_statistics as ms, trace_statistics as adapter
from test_merge import prepare, fixture_decision


@pytest.fixture
def anyio_backend():return 'asyncio'


@pytest.fixture
def merged(tmp_path,monkeypatch):
    qc,collection,root=prepare(tmp_path,monkeypatch);fixture_decision(qc)
    result=m.execute_merge(qc.run_id,qc.results_sha256,[0,2]);assert result.status=='MERGED',result.error
    assert result.provenance_sha256==c.digest(Path(result.provenance_path))
    monkeypatch.setenv(ms.OUTPUT_ENV,str(tmp_path/'statistics'))
    return qc,collection,root,result


def invoke(merged):
    result=merged[3]
    return ms.execute_statistics(result.run_id,result.merged_sha256,result.provenance_sha256)


def check_error(result):
    assert result.status=='ERROR' and result.baseline_fingerprint is None
    assert result.global_unique_trace_id_count is None and result.roi_trace_count is None
    for path in Path(os.environ[ms.OUTPUT_ENV]).glob('*/statistics.json'):
        assert json.loads(path.read_text())['status']=='ERROR'


def test_native_equivalence_reproducible_baseline_scope_and_unchanged_artifacts(merged):
    qc,collection,root,merge=merged
    protected=list(root.rglob('*.ecsv'))+list(Path(collection.manifest_path).parent.glob('*'))
    protected+=list(Path(merge.merged_path).parent.glob('*'))+[Path(qc.results_path),Path(qc.report_path)]
    before={p:c.digest(p) for p in protected}
    direct=io.StringIO()
    with contextlib.redirect_stdout(direct):adapter.native.compute_trace_statistics(merge.merged_path)
    result=invoke(merged);assert result.status=='COMPUTED',result.error
    assert result.row_count==6 and result.unique_roi_count==2 and result.unique_barcode_count==3
    assert result.global_unique_trace_id_count==1 and result.roi_trace_count==2
    detail=json.loads(Path(result.evidence_path).read_text())
    assert detail['traceratops_report']==direct.getvalue().strip()
    assert detail['scope']=='merged_unfiltered_tracing' and detail['status']=='COMPUTED'
    assert detail['traceratops_version']=='1.0.1' and len(detail['native_module_sha256'])==64
    assert detail['merged_sha256']==merge.merged_sha256 and detail['provenance_sha256']==merge.provenance_sha256
    assert [s['roi'] for s in detail['approved_source_contributions']]==['1','3']
    assert all(s['experiment_root']==str(root) for s in detail['approved_source_contributions'])
    assert detail['original_per_roi_statistics']['status']=='RETAINED_SEPARATELY_IN_STEP0'
    assert 'Number of unique chromatin traces: 1' in Path(result.native_log_path).read_text()
    assert result.evidence_sha256==c.digest(Path(result.evidence_path))
    again=invoke(merged);assert again.status=='COMPUTED'
    assert again.run_id!=result.run_id and again.baseline_fingerprint==result.baseline_fingerprint
    assert before=={p:c.digest(p) for p in before}


@pytest.mark.parametrize('fault',['missing-merge','modified-merge','missing-provenance','provenance-hash','approval','source','log-symlink','wrong-run','unsafe-output'])
def test_invalid_evidence_prevents_native_execution(merged,monkeypatch,fault):
    qc,collection,root,result=merged
    if fault=='missing-merge':Path(result.merged_path).unlink()
    elif fault=='modified-merge':Path(result.merged_path).write_text(Path(result.merged_path).read_text()+'\n')
    elif fault=='missing-provenance':Path(result.provenance_path).unlink()
    elif fault=='provenance-hash':Path(result.provenance_path).write_text(Path(result.provenance_path).read_text()+'\n')
    elif fault=='approval':fixture_decision(qc,'REJECT','')
    elif fault=='source':
        item=json.loads(Path(collection.manifest_path).read_text())['files'][0];Path(item['destination']).write_text('changed')
    elif fault=='log-symlink':
        log=Path(result.merged_path).parent/'native.log';log.unlink();log.symlink_to(result.merged_path)
    elif fault=='wrong-run':result.run_id='0'*32
    elif fault=='unsafe-output':monkeypatch.setenv(ms.OUTPUT_ENV,str(root/'forbidden'))
    def forbidden(*args,**kwargs):raise AssertionError('Native statistics must not execute')
    monkeypatch.setattr(adapter.native,'compute_trace_statistics',forbidden)
    response=invoke(merged);check_error(response)
    assert response.error_type!='AssertionError'


@pytest.mark.parametrize('fault',['selection','mapping','row-count','phase','roi-trace-count'])
def test_rehashed_inconsistent_provenance_is_rejected(merged,fault):
    _,_,_,result=merged
    path=Path(result.provenance_path);value=json.loads(path.read_text())
    if fault=='selection':value['selected_dataset_indices']=[0,1]
    elif fault=='mapping':value['sources'][0]['roi_mapping']={'1':['99']}
    elif fault=='row-count':value['sources'][0]['row_count']=99
    elif fault=='phase':value['phase']='filtered_tracing'
    elif fault=='roi-trace-count':value['roi_trace_count']=99
    path.write_text(json.dumps(value));result.provenance_sha256=c.digest(path)
    check_error(invoke(merged))


@pytest.mark.parametrize('fault',['approval','merged','provenance','source','log'])
def test_change_during_statistics_cannot_publish_success(merged,monkeypatch,fault):
    qc,collection,_,result=merged;original=adapter.native.compute_trace_statistics
    def hook(snapshot):
        original(snapshot)
        if fault=='approval':fixture_decision(qc,'REJECT','')
        else:
            if fault=='merged':path=Path(result.merged_path)
            elif fault=='provenance':path=Path(result.provenance_path)
            elif fault=='source':path=Path(json.loads(Path(collection.manifest_path).read_text())['files'][0]['destination'])
            else:path=Path(result.merged_path).parent/'native.log'
            path.write_text(path.read_text()+'\n')
    monkeypatch.setattr(adapter.native,'compute_trace_statistics',hook)
    response=invoke(merged);check_error(response)
    assert response.evidence_path is not None
    assert json.loads(Path(response.evidence_path).read_text())['status']=='ERROR'


def test_native_failure_saves_status_version_warnings_and_log(merged,monkeypatch):
    import warnings
    def fail(path):
        print('native failure transcript')
        warnings.warn('native warning sentinel',RuntimeWarning)
        raise SystemExit(1)
    monkeypatch.setattr(adapter.native,'compute_trace_statistics',fail)
    result=invoke(merged);check_error(result)
    detail=json.loads(Path(result.evidence_path).read_text())
    assert detail['traceratops_version']=='1.0.1' and detail['status']=='ERROR'
    assert any('native warning sentinel' in w for w in detail['warnings'])
    assert 'native failure transcript' in Path(result.native_log_path).read_text()


@pytest.mark.anyio
async def test_real_stdio_single_call_schema_and_compact_response(merged):
    result=merged[3]
    parameters=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=dict(os.environ))
    async with Client(parameters,raise_exceptions=False,read_timeout_seconds=60) as client:
        tools={t.name:t for t in (await client.list_tools()).tools};assert len(tools)==26
        tool=tools['merged_trace_stats'];Draft202012Validator.check_schema(tool.input_schema);Draft202012Validator.check_schema(tool.output_schema)
        args={'trace_merge_run_id':result.run_id,'merged_sha256':result.merged_sha256,'provenance_sha256':result.provenance_sha256}
        assert (await client.call_tool('merged_trace_stats',{**args,'trace_merge_run_id':'../escape'})).is_error
        value=(await client.call_tool('merged_trace_stats',args)).structured_content
        Draft202012Validator(tool.output_schema).validate(value)
        assert value['status']=='COMPUTED' and value['global_unique_trace_id_count']==1 and value['roi_trace_count']==2
        assert value['structured_response_bytes']==len(json.dumps(value,separators=(',',':'),ensure_ascii=False).encode())
        assert value['structured_response_bytes']<6500
        assert not set(value)&{'traceratops_report','approved_source_contributions','approval_snapshot','tables','matrix'}
