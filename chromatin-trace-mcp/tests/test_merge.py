"""Approved states here are synthetic test fixtures, never consent for real experiments."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from astropy.table import Table
from astropy.io.misc import yaml
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.server.mcpserver import AcceptedElicitation
from mcp.types import ElicitResult

from chromatin_trace_mcp import approval as a, collection as c, merge as m, pearsons as p
from chromatin_trace_mcp.step0 import ROOTS_ENV


@pytest.fixture
def anyio_backend(): return 'asyncio'


def prepare(tmp_path, monkeypatch, metadata=None):
    root=tmp_path/'inputs'
    for roi,x in [(1,[0.,1.,3.]),(2,[0.,3.,1.]),(3,[0.,2.,6.])]:
        path=root/f'{roi:03d}'/f'tracing/data/Trace_ROI-{roi}.ecsv';path.parent.mkdir(parents=True)
        meta=metadata[roi-1] if metadata else {'comments':['xyz_unit=micron','genome_assembly=mm10'],'lab':'lab'}
        table=Table({'Spot_ID':['long-spot1','long-spot2','long-spot3'],'Trace_ID':['nucleus-long']*3,
               'Barcode #':[1,2,3],'ROI #':[roi]*3,'x':x,'y':[0.]*3,'z':[0.]*3},meta=meta)
        table['Trace_ID'].description='Segmented nucleus identifier'
        table['Trace_ID'].meta={'identifier_scope':'nucleus'}
        table.write(path,format='ascii.ecsv')
    monkeypatch.setenv(ROOTS_ENV,str(root));monkeypatch.setenv(c.OUTPUT_ENV,str(tmp_path/'collections'))
    monkeypatch.setenv(p.OUTPUT_ENV,str(tmp_path/'pearson'));monkeypatch.setenv(m.OUTPUT_ENV,str(tmp_path/'merged'))
    return collect_qc(root)


def collect_qc(root):
    collected=c.execute_collection(str(root),'Trace_ROI-1.ecsv','1');assert collected.status=='PASS'
    refs=[{'collection_run_id':collected.run_id,'manifest_sha256':collected.manifest_sha256}]
    qc=p.execute_pearsons(refs);assert qc.status=='COMPUTED'
    return qc,collected,root


def fixture_decision(qc,decision='APPROVE',indices='0,2'):
    context=a.prepare_review(qc.run_id,qc.results_sha256)
    return a.complete_review(context,AcceptedElicitation(data=a.HumanDecision(decision=decision,selected_dataset_indices=indices)))


@pytest.fixture
def approved(tmp_path,monkeypatch):
    qc,collected,root=prepare(tmp_path,monkeypatch)
    assert fixture_decision(qc).status=='APPROVED'
    return qc,collected,root


def invoke(qc,indices=None):
    return m.execute_merge(qc.run_id,qc.results_sha256,[0,2] if indices is None else indices)


def assert_no_outputs(result):
    assert result.status=='ERROR' and result.merged_path is None
    output=Path(os.environ[m.OUTPUT_ENV])
    if output.exists(): assert not list(output.iterdir())


def native_expected(paths,output):
    traces=m.native.load_traces(paths,verbose=False)
    traces.save(str(output),comments='appended_trace_files='+str(traces.number_traces))
    return Table.read(output,format='ascii.ecsv')


def test_native_equivalence_exact_selection_metadata_integrity_and_reproducibility(approved,tmp_path):
    qc,collected,root=approved
    files=json.loads(Path(collected.manifest_path).read_text())['files'];selected=[files[i]['destination'] for i in [0,2]]
    protected=list(root.rglob('*.ecsv'))+list(Path(collected.manifest_path).parent.glob('*'))+[Path(qc.results_path),Path(qc.report_path)]
    before={path:c.digest(path) for path in protected}
    direct=tmp_path/'native.ecsv';expected=native_expected(selected,direct)
    result=invoke(qc);assert result.status=='MERGED',result.error
    assert result.source_file_count==2 and result.row_count==6 and result.barcode_count==3
    assert result.trace_count==1 and result.roi_trace_count==2 and result.roi_count==2
    assert Path(result.merged_path).read_bytes()==direct.read_bytes()
    merged=Table.read(result.merged_path,format='ascii.ecsv')
    assert set(merged['ROI #'])=={1,3} and 2 not in set(merged['ROI #'])
    assert merged.meta==expected.meta
    detail=json.loads(Path(result.provenance_path).read_text())
    assert [s['row_start'] for s in detail['sources']]==[0,3]
    assert [s['row_stop_exclusive'] for s in detail['sources']]==[3,6]
    assert [s['roi_mapping'] for s in detail['sources']]==[{'1':['1']},{'3':['3']}]
    assert detail['approval_snapshot']['status']=='APPROVED'
    assert detail['selected_dataset_indices']==[0,2]
    assert all('lab: lab' in s['source_metadata_yaml'] for s in detail['sources'])
    for source in detail['sources']:
        stored=yaml.load(source['source_column_metadata_yaml'])
        assert stored['Trace_ID']['description']=='Segmented nucleus identifier'
        assert stored['Trace_ID']['meta']=={'identifier_scope':'nucleus'}
    again=invoke(qc);assert again.status=='MERGED'
    assert again.run_id!=result.run_id and again.merged_sha256==result.merged_sha256
    assert before=={path:c.digest(path) for path in before}
    assert not list(Path(os.environ[m.OUTPUT_ENV]).glob('.pending-*'))


@pytest.mark.parametrize('fault',['awaiting','rejected','selection','one','manifest','missing','symlink','results','report'])
def test_invalid_or_changed_approval_never_merges(tmp_path,monkeypatch,fault):
    qc,collected,root=prepare(tmp_path,monkeypatch)
    if fault!='awaiting': fixture_decision(qc,'REJECT','') if fault=='rejected' else fixture_decision(qc)
    if fault=='manifest': Path(collected.manifest_path).write_text(Path(collected.manifest_path).read_text()+'\n')
    elif fault in {'missing','symlink'}:
        path=Path(json.loads(Path(collected.manifest_path).read_text())['files'][0]['destination'])
        path.unlink()
        if fault=='symlink': path.symlink_to(next(root.rglob('*.ecsv')))
    elif fault=='results': Path(qc.results_path).write_text(Path(qc.results_path).read_text()+'\n')
    elif fault=='report': Path(qc.report_path).write_text('Changed report')
    indices=[0,1] if fault=='selection' else [0] if fault=='one' else [0,2]
    assert_no_outputs(invoke(qc,indices))


@pytest.mark.parametrize('change',['revoke','input'])
def test_change_during_native_execution_cannot_publish(approved,monkeypatch,change):
    qc,collected,root=approved;original=m.native.load_traces
    def hook(*args,**kwargs):
        value=original(*args,**kwargs)
        if change=='revoke': fixture_decision(qc,'REJECT','')
        else:
            path=Path(json.loads(Path(collected.manifest_path).read_text())['files'][0]['destination'])
            path.write_text(path.read_text()+'\n')
        return value
    monkeypatch.setattr(m.native,'load_traces',hook)
    assert_no_outputs(invoke(qc))


def test_native_roi_collision_preserves_source_mapping(approved,tmp_path):
    qc,collected,root=approved
    other=c.execute_collection(str(root),'Trace_ROI-1.ecsv','1');assert other.status=='PASS'
    refs=[{'collection_run_id':r.run_id,'manifest_sha256':r.manifest_sha256} for r in [collected,other]]
    qc=p.execute_pearsons(refs);fixture_decision(qc,indices='0,3')
    result=invoke(qc,[0,3]);assert result.status=='MERGED',result.error
    detail=json.loads(Path(result.provenance_path).read_text())
    assert [s['roi_mapping'] for s in detail['sources']]==[{'1':['1']},{'1':['2']}]
    assert any('renumbered' in w for w in detail['warnings'])
    direct=tmp_path/'native-collision.ecsv'
    native_expected([s['path'] for s in detail['sources']],direct)
    assert Path(result.merged_path).read_bytes()==direct.read_bytes()


@pytest.mark.parametrize('metadata',[
    [{'comments':['xyz_unit=micron','genome_assembly=dm6']}]*3,
    [{'comments':['xyz_unit=micron','genome_assembly=mm10']},{'comments':['xyz_unit=micron','genome_assembly=mm10']},{'comments':['xyz_unit=nm','genome_assembly=mm10']}],
])
def test_scientific_metadata_conflict_fails_closed(tmp_path,monkeypatch,metadata):
    qc,_,_=prepare(tmp_path,monkeypatch,metadata);fixture_decision(qc)
    result=invoke(qc);assert_no_outputs(result)
    assert 'Conflicting' in result.error


def test_output_inside_inputs_is_rejected_before_writing(approved,monkeypatch):
    qc,_,root=approved
    monkeypatch.setenv(m.OUTPUT_ENV,str(root/'forbidden'))
    result=invoke(qc);assert result.status=='ERROR' and result.error_type=='PermissionError'
    assert not (root/'forbidden').exists()


@pytest.mark.anyio
async def test_real_stdio_approval_to_merge_schema_and_errors(tmp_path,monkeypatch):
    qc,collected,root=prepare(tmp_path,monkeypatch)
    async def host_fixture(context,params):
        return ElicitResult(action='accept',content={'decision':'APPROVE','selected_dataset_indices':'0,2'})
    params=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=dict(os.environ))
    async with Client(params,elicitation_callback=host_fixture,raise_exceptions=False,read_timeout_seconds=60) as client:
        tools={t.name:t for t in (await client.list_tools()).tools}
        assert 'trace_merge' in tools and 'localization_merge' in tools
        tool=tools['trace_merge'];Draft202012Validator.check_schema(tool.input_schema)
        Draft202012Validator.check_schema(tool.output_schema)
        args={'pearson_run_id':qc.run_id,'results_sha256':qc.results_sha256,'selected_dataset_indices':[0,2]}
        denied=await client.call_tool('trace_merge',args);assert denied.structured_content['status']=='ERROR'
        review=await client.call_tool('review_pearson_approval',{'pearson_run_id':qc.run_id,'results_sha256':qc.results_sha256,'request_decision':True})
        assert review.structured_content['status']=='APPROVED'
        for bad in ({**args,'pearson_run_id':'../bad'},{**args,'selected_dataset_indices':[True,2]},{**args,'selected_dataset_indices':[0]}):
            assert (await client.call_tool('trace_merge',bad)).is_error
        response=await client.call_tool('trace_merge',args);result=response.structured_content
        assert result['status']=='MERGED',result
        Draft202012Validator(tool.output_schema).validate(result)
        assert result['structured_response_bytes']==len(json.dumps(result,separators=(',',':'),ensure_ascii=False).encode())
        assert result['structured_response_bytes']<6000 and result['row_count']==6
        assert not any(key in result for key in ['data','table','sources','approval_snapshot'])


def test_empty_input_contribution_is_retained(approved,tmp_path):
    _,_,root=approved
    file=next((root/'001').rglob('*.ecsv'));table=Table.read(file,format='ascii.ecsv');table[:0].write(file,format='ascii.ecsv',overwrite=True)
    qc,_,_=collect_qc(root);fixture_decision(qc)
    result=invoke(qc);assert result.status=='MERGED',result.error
    detail=json.loads(Path(result.provenance_path).read_text())
    assert result.row_count==3 and detail['sources'][0]['row_count']==0
    assert detail['sources'][0]['roi_mapping']=={}
    direct=tmp_path/'native-empty.ecsv';native_expected([s['path'] for s in detail['sources']],direct)
    assert Path(result.merged_path).read_bytes()==direct.read_bytes()
    assert any('floating point' in w for w in detail['warnings'])


def test_native_failure_is_reported_without_publication(approved,monkeypatch):
    qc,_,_=approved
    def fail(*args,**kwargs): raise RuntimeError('native merge failure sentinel')
    monkeypatch.setattr(m.native,'load_traces',fail)
    result=invoke(qc);assert_no_outputs(result)
    assert result.error_type=='RuntimeError' and result.error=='native merge failure sentinel'


def test_missing_source_metadata_is_not_claimed_verified(tmp_path,monkeypatch):
    metadata=[{}, {'comments':['xyz_unit=micron','genome_assembly=mm10']}, {'comments':['xyz_unit=micron','genome_assembly=mm10']}]
    qc,_,_=prepare(tmp_path,monkeypatch,metadata);fixture_decision(qc)
    result=invoke(qc);assert result.status=='MERGED',result.error
    detail=json.loads(Path(result.provenance_path).read_text())
    assert any('not fully declared' in w for w in detail['warnings'])
    assert detail['sources'][0]['source_metadata_yaml'].strip()=='{}'
