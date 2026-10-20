"""Numerical ground truth is native Traceratops; no model judges scientific accuracy."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from astropy.table import Table
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from chromatin_trace_mcp import collection as c, pearsons as p
from chromatin_trace_mcp.server import mcp
from chromatin_trace_mcp.step0 import ROOTS_ENV


@pytest.fixture
def anyio_backend(): return 'asyncio'


def write_trace(root, roi, positions):
    path=root/f'{roi:03d}'/f'tracing/data/Trace_ROI-{roi}.ecsv'
    path.parent.mkdir(parents=True)
    n=len(positions)
    Table({'Spot_ID':[f's{i}' for i in range(n)],'Trace_ID':['n1']*n,
           'Barcode #':list(range(1,n+1)),'ROI #':[roi]*n,
           'x':positions,'y':[0.]*n,'z':[0.]*n},meta={'comments':['xyz_unit=micron']}).write(path,format='ascii.ecsv')
    return path


@pytest.fixture
def experiment(tmp_path,monkeypatch):
    root=tmp_path/'experiment'
    write_trace(root,1,[0.,1.,3.]);write_trace(root,2,[0.,3.,1.])
    monkeypatch.setenv(ROOTS_ENV,str(root))
    monkeypatch.setenv(c.OUTPUT_ENV,str(tmp_path/'collections'))
    monkeypatch.setenv(p.OUTPUT_ENV,str(tmp_path/'qc'))
    return root


def collect(root):
    result=c.execute_collection(str(root),'Trace_ROI-1.ecsv','1')
    assert result.status=='PASS',result.error
    return result, [{'collection_run_id':result.run_id,'manifest_sha256':result.manifest_sha256}]


def direct(manifest,output):
    maps={}
    for item in json.loads(Path(manifest).read_text())['files']:
        trace=p.native.ChromatinTraceTable()
        p.native.silent_load_trace(trace,item['destination'])
        maps[item['destination']]=p.native.accumulate_distances(trace.data)
    files,matrix=p.native.compare_distance_maps(maps)
    p.native.plot_correlation_matrix(files,matrix,output_filename=str(output))
    return maps,matrix


@pytest.mark.parametrize('fmt',['png','svg','pdf'])
def test_native_equivalence_figures_integrity_and_reproducibility(experiment,tmp_path,fmt):
    collected,refs=collect(experiment)
    before={path:c.digest(path) for path in list(experiment.rglob('*.ecsv'))+list(Path(collected.manifest_path).parent.glob('*'))}
    maps,expected=direct(collected.manifest_path,tmp_path/f'direct.{fmt}')
    result=p.execute_pearsons(refs,fmt)
    assert result.status=='COMPUTED',result.error
    saved=json.loads(Path(result.results_path).read_text())
    np.testing.assert_array_equal(np.load(result.matrix_path,allow_pickle=False),expected)
    assert result.comparisons[0]['pearson_r']==pytest.approx(-1.)
    assert result.comparisons[0]['shared_non_nan_pairs']==3
    for i,key in enumerate(saved['files']):
        assert saved['distance_maps'][i]['pairs']==[{'barcodes':list(k),'median_distance':v} for k,v in sorted(maps[key].items())]
    assert Path(result.figure_path).suffix=='.'+fmt and Path(result.figure_path).stat().st_size>100
    if fmt=='png': assert Path(result.figure_path).read_bytes()==(tmp_path/'direct.png').read_bytes()
    assert before=={path:c.digest(path) for path in before}
    assert result.review_required and saved['parameters']['correlation_threshold'] is None
    assert any('0–1' in note for note in saved['warnings'])
    assert 'No approval state' in Path(result.report_path).read_text()
    again=p.execute_pearsons(refs,fmt)
    np.testing.assert_array_equal(np.load(again.matrix_path),expected)
    assert again.run_id!=result.run_id
    assert not list(Path(os.environ[p.OUTPUT_ENV]).glob('.pending-*'))


@pytest.mark.parametrize('case',['constant','one_pair','disjoint','duplicate'])
def test_native_edge_cases_preserve_undefined_and_duplicate_behavior(experiment,tmp_path,case):
    paths=sorted(experiment.rglob('*.ecsv'))
    t=Table.read(paths[1],format='ascii.ecsv')
    if case=='constant': t['x']=[0.,0.,0.]
    if case=='one_pair': t=t[:2]
    if case=='disjoint': t['Barcode #']=[4,5,6]
    if case=='duplicate':
        t.add_row(['extra','n1',2,2,8.,0.,0.])
    t.write(paths[1],format='ascii.ecsv',overwrite=True)
    collected,refs=collect(experiment)
    _,expected=direct(collected.manifest_path,tmp_path/'direct.png')
    result=p.execute_pearsons(refs)
    assert result.status=='COMPUTED',result.error
    np.testing.assert_array_equal(np.load(result.matrix_path),expected)
    if case!='duplicate':
        assert result.comparisons[0]['pearson_r'] is None and result.undefined_comparisons==1
        assert 'undefined' in Path(result.report_path).read_text()
    else: assert 'last row' in Path(result.report_path).read_text()


@pytest.mark.parametrize('fault',['manifest_hash','file_hash','missing','symlink','localization','single','duplicate_ref','output_in_input','output_in_collection'])
def test_unsafe_or_stale_inputs_publish_nothing(experiment,monkeypatch,fault):
    collected,refs=collect(experiment)
    manifest=Path(collected.manifest_path);data=json.loads(manifest.read_text());file=Path(data['files'][0]['destination'])
    if fault=='manifest_hash': refs[0]['manifest_sha256']='0'*64
    elif fault=='file_hash': file.write_text(file.read_text()+'\n')
    elif fault=='missing': file.unlink()
    elif fault=='symlink':
        file.unlink();file.symlink_to(Path(data['files'][0]['source']))
    elif fault in {'localization','single'}:
        if fault=='localization': data['table_kind']='localization'
        else: data['files']=data['files'][:1]
        manifest.write_text(json.dumps(data));refs[0]['manifest_sha256']=c.digest(manifest)
    elif fault=='duplicate_ref': refs*=2
    elif fault=='output_in_input': monkeypatch.setenv(p.OUTPUT_ENV,str(experiment/'must-not-exist'))
    elif fault=='output_in_collection': monkeypatch.setenv(p.OUTPUT_ENV,str(manifest.parent/'must-not-exist'))
    result=p.execute_pearsons(refs)
    assert result.status=='ERROR' and result.results_path is None
    assert not Path(os.environ[p.OUTPUT_ENV]).exists()


def test_native_failure_does_not_publish(experiment,monkeypatch):
    _,refs=collect(experiment)
    def broken(*args,**kwargs): raise RuntimeError('native failure sentinel')
    monkeypatch.setattr(p.native,'compare_distance_maps',broken)
    result=p.execute_pearsons(refs)
    assert result.status=='ERROR' and result.error=='native failure sentinel'
    assert not list(Path(os.environ[p.OUTPUT_ENV]).iterdir())


@pytest.mark.anyio
async def test_real_stdio_schema_collection_to_pearson_and_errors(experiment):
    params=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=dict(os.environ))
    async with Client(params,read_timeout_seconds=60,raise_exceptions=False) as client:
        tools={t.name:t for t in (await client.list_tools()).tools}
        tool=tools['trace_pearsons']
        Draft202012Validator.check_schema(tool.input_schema)
        Draft202012Validator.check_schema(tool.output_schema)
        for args in ({},{'collections':[{'collection_run_id':'../bad','manifest_sha256':'0'*64}]},{'collections':[],'output_format':'exe'}):
            assert (await client.call_tool('trace_pearsons',args)).is_error
        result=await client.call_tool('collect_files',{'experiment_root':str(experiment),'example_file':'Trace_ROI-1.ecsv','variable_part':'1'})
        collection=result.structured_content
        args={'collections':[{'collection_run_id':collection['run_id'],'manifest_sha256':collection['manifest_sha256']}]}
        result=await client.call_tool('trace_pearsons',args)
        payload=result.structured_content
        assert payload['status']=='COMPUTED',payload
        Draft202012Validator(tool.output_schema).validate(payload)
        assert payload['comparisons'][0]['pearson_r']==pytest.approx(-1.)
        assert [d['roi'] for d in payload['datasets']]==['1','2']
        assert payload['structured_response_bytes']==len(json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode())
        assert payload['structured_response_bytes']<6000
        assert 'correlation_matrix' not in payload and 'distance_maps' not in payload
        assert (await client.call_tool('trace_pearsons',{'collections':[]})).structured_content['status']=='ERROR'
        args['collections'][0]['manifest_sha256']='0'*64
        assert (await client.call_tool('trace_pearsons',args)).structured_content['status']=='ERROR'
