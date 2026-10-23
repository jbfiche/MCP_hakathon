"""Synthetic fixtures/host decisions only; real consent is never generated here."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from astropy.table import Table
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from chromatin_trace_mcp import collection as c,localization_merge as lm,localization_analysis as la
from test_merge import prepare,fixture_decision


@pytest.fixture
def anyio_backend():return 'asyncio'


def setup(tmp_path,monkeypatch,fault=None):
    qc,traces,root=prepare(tmp_path,monkeypatch)
    for roi in [1,2,3]:
        records=[]
        for i in range(12):
            records.append((f'roi{roi}-spot{i}',roi,[1,2,639][i%3],float(i),0.,float(i)/2,2.+i+roi,0.1*i,1+i%2,0.2*i))
        table=Table(rows=records,names=['Buid','ROI #','Barcode #','xcentroid','ycentroid','zcentroid','snr','skew','object_class','roundness'],
                    meta={'comments':['filtered','registered']})
        if fault=='legacy':
            table.remove_columns(['snr','skew','object_class','roundness']);table['peak']=np.arange(len(table))
        elif fault=='nan':table['snr'][0]=np.nan
        elif fault=='infinite':table['roundness'][0]=np.inf
        elif fault=='masked':table=Table(table,masked=True);table['snr'].mask[0]=True
        elif fault=='fractional-barcode':table['Barcode #']=table['Barcode #'].astype(float)+0.5
        path=root/f'{roi:03d}/localize_3d/data/localizations.ecsv';path.parent.mkdir(parents=True);table.write(path,format='ascii.ecsv')
    loc=c.execute_collection(str(root),'localizations.ecsv',table_kind='localization');assert loc.status=='PASS',loc.error
    monkeypatch.setenv(lm.OUTPUT_ENV,str(tmp_path/'localization-merges'));monkeypatch.setenv(la.OUTPUT_ENV,str(tmp_path/'localization-analysis'))
    fixture_decision(qc)
    merged=lm.execute_localization_merge(qc.run_id,qc.results_sha256,[0,2],[{'collection_run_id':loc.run_id,'manifest_sha256':loc.manifest_sha256}])
    assert merged.status=='MERGED',merged.error
    return qc,traces,loc,merged,root


@pytest.fixture
def ready(tmp_path,monkeypatch):return setup(tmp_path,monkeypatch)


def invoke(ready,**kwargs):
    merged=ready[3];return la.execute_analysis(merged.run_id,merged.merged_sha256,merged.provenance_sha256,**kwargs)


def assert_error(result):
    assert result.status=='ERROR' and result.figure_count==0 and result.row_count is None


DIRECT='''
import json,numpy as np
from matplotlib.axes import Axes
from traceratops import localization_analyzer as native
calls=[];arrays={}
for name in ['violinplot','scatter','bar']:
 original=getattr(Axes,name)
 def wrap(name,original):
  def call(self,*args,**kwargs):
   entry={'method':name}
   values={'positions':kwargs['positions'],**{f'snr_{i}':a for i,a in enumerate(args[0])}} if name=='violinplot' else {'x':args[0],'y':args[1]}
   if name=='scatter':values['c']=kwargs['c']
   for key,value in values.items():
    label=str(len(arrays));arrays[label]=np.asarray(value);entry[key]=label
   result=original(self,*args,**kwargs);calls.append(entry);return result
  return call
 setattr(Axes,name,wrap(name,original))
native.run({'localization_file':'localizations.ecsv','output_file':'localization_distribution_fluxes.png','format':'png'})
np.savez_compressed('direct-arrays.npz',**arrays)
open('direct-calls.json','w').write(json.dumps(calls))
'''


def test_native_figure_full_plot_inputs_counts_provenance_reproducibility_and_integrity(ready,tmp_path):
    qc,traces,loc,merged,root=ready
    files=list(root.rglob('*.ecsv'))+list(Path(merged.merged_path).parent.iterdir())+[Path(qc.results_path),Path(qc.report_path)]
    before={p:c.digest(p) for p in files}
    folder=tmp_path/'native';folder.mkdir();(folder/'localizations.ecsv').write_bytes(Path(merged.merged_path).read_bytes())
    run=subprocess.run([sys.executable,'-c',DIRECT],cwd=folder,capture_output=True,text=True,timeout=60)
    assert run.returncode==0,run.stderr
    result=invoke(ready);assert result.status=='ANALYZED',result.error
    out=Path(result.output_directory);assert Path(result.output_file).read_bytes()==(folder/'localization_distribution_fluxes.png').read_bytes()
    assert result.figure_count==1 and result.row_count==24 and result.unique_barcode_count==3 and result.roi_count==2
    detail=json.loads(Path(result.evidence_path).read_text());assert detail['barcode_namespace']=='original'
    assert detail['selected_dataset_indices']==[0,2] and detail['approval_revision']
    numeric=json.loads((out/'numerical_outputs.json').read_text());direct=json.loads((folder/'direct-calls.json').read_text())
    assert numeric['native_barcode_counts']==[{'barcode':1,'count':8},{'barcode':2,'count':8},{'barcode':639,'count':8}]
    with np.load(out/'numerical_outputs.npz',allow_pickle=False) as actual,np.load(folder/'direct-arrays.npz',allow_pickle=False) as expected:
        for a,b in zip(numeric['plot_calls'],direct):
            assert a['method']==b['method']
            if a['method']=='violinplot':
                np.testing.assert_equal(actual[a['positions']],expected[b['positions']])
                for i,key in enumerate(a['datasets']):np.testing.assert_equal(actual[key],expected[b[f'snr_{i}']])
            elif a['method']=='bar':
                np.testing.assert_equal(actual[a['positions']],expected[b['x']]);np.testing.assert_equal(actual[a['counts']],expected[b['y']])
            else:
                for ours,theirs in [('x','x'),('y','y'),('color','c')]:np.testing.assert_equal(actual[a[ours]],expected[b[theirs]])
    manifest=json.loads(Path(result.artifact_manifest_path).read_text());assert all(c.digest(out/v['name'])==v['sha256'] for v in manifest)
    again=invoke(ready);assert again.status=='ANALYZED' and again.run_id!=result.run_id
    assert Path(again.output_file).read_bytes()==Path(result.output_file).read_bytes()
    assert before=={p:c.digest(p) for p in before}
    assert not (out/'localizations.ecsv').exists()


@pytest.mark.parametrize('fault',['legacy','nan','infinite','masked'])
def test_scientific_input_rejection(tmp_path,monkeypatch,fault):
    result=invoke(setup(tmp_path,monkeypatch,fault));assert_error(result);assert result.output_directory is None


@pytest.mark.parametrize('fault',['revoked','missing','changed-input','wrong-provenance','wrong-selection','invalid-run','missing-source','unsafe-output'])
def test_approval_evidence_and_output_restrictions(ready,monkeypatch,fault):
    qc,traces,loc,merged,root=ready
    if fault=='revoked':fixture_decision(qc,decision='REJECT',indices='')
    elif fault=='missing':Path(merged.merged_path).unlink()
    elif fault=='changed-input':Path(merged.merged_path).write_text('changed')
    elif fault in {'wrong-provenance','wrong-selection'}:
        path=Path(merged.provenance_path);doc=json.loads(path.read_text())
        if fault=='wrong-provenance':doc['sources'][0]['roi_mapping']={'1':['999']}
        else:doc['selected_dataset_indices']=[0,1]
        path.write_text(json.dumps(doc));ready=(*ready[:3],merged.model_copy(update={'provenance_sha256':c.digest(path)}),root)
    elif fault=='invalid-run':ready=(*ready[:3],merged.model_copy(update={'run_id':'0'*32}),root)
    elif fault=='missing-source':
        manifest=json.loads(Path(loc.manifest_path).read_text());Path(manifest['files'][0]['destination']).unlink()
    elif fault=='unsafe-output':monkeypatch.setenv(la.OUTPUT_ENV,str(root/'outputs'))
    assert_error(invoke(ready))


def test_native_failure_retains_logs_without_success(ready,monkeypatch):
    def failing(folder,fmt):
        (folder/'stderr.log').write_text('native failure details');raise RuntimeError('native failure')
    monkeypatch.setattr(la,'run_worker',failing)
    result=invoke(ready);assert_error(result)
    assert (Path(result.output_directory)/'stderr.log').read_text()=='native failure details'


def test_changed_merge_during_execution_prevents_success(ready,monkeypatch):
    worker=la.run_worker
    def changing(*args,**kwargs):
        worker(*args,**kwargs);path=Path(ready[3].merged_path);path.write_bytes(path.read_bytes()+b'\n')
    monkeypatch.setattr(la,'run_worker',changing)
    result=invoke(ready);assert_error(result);assert 'checksum' in result.error


def test_annotation_requires_matching_pair_of_references(ready):
    result=invoke(ready,annotation_run_id='a'*32);assert_error(result);assert 'together' in result.error
    result=invoke(ready,annotation_run_id='a'*32,annotation_sha256='b'*64);assert_error(result)


@pytest.mark.anyio
async def test_existing_mcp_tool_new_mode_compact_schema_and_no_duplicate_tool(ready):
    merged=ready[3]
    async with Client(StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=dict(os.environ)),raise_exceptions=False,read_timeout_seconds=90) as client:
        tools={t.name:t for t in (await client.list_tools()).tools};assert len(tools)==27
        args={'localization_merge_run_id':merged.run_id,'merged_sha256':merged.merged_sha256,'provenance_sha256':merged.provenance_sha256}
        Draft202012Validator(tools['localization_analyzer'].input_schema).validate(args)
        response=await client.call_tool('localization_analyzer',args);result=response.structured_content
        assert not response.is_error and result['status']=='ANALYZED',response
        assert result['structured_response_bytes']<3500 and 'traceratops_report' not in result and 'plot_calls' not in result
        invalid=await client.call_tool('localization_analyzer',{'localization_merge_run_id':merged.run_id});assert invalid.is_error
        invalid=await client.call_tool('localization_analyzer',dict(args,dataset_name='other'));assert invalid.is_error


def test_preflight_requires_integer_barcode_ids():
    table=Table({name:[1.] for name in set(la.LOCALIZATION_COLUMNS)|la.PLOT_COLUMNS})
    table['Barcode #']=[1.5]
    with pytest.raises(ValueError,match='must be integers'):la.preflight(table)


def test_human_rejection_during_execution_prevents_publication(ready,monkeypatch):
    worker=la.run_worker
    def rejecting(*args,**kwargs):
        worker(*args,**kwargs);fixture_decision(ready[0],decision='REJECT',indices='')
    monkeypatch.setattr(la,'run_worker',rejecting)
    result=invoke(ready);assert_error(result);assert 'approval' in result.error.lower()


def test_extreme_finite_values_are_not_filtered(ready,monkeypatch):
    # Verify mathematical input validation has no invented SNR/skew/roundness threshold.
    table=Table({name:[1.] for name in set(la.LOCALIZATION_COLUMNS)|la.PLOT_COLUMNS})
    table['Barcode #']=[639];table['snr']=[-100.];table['roundness']=[3.1e8]
    la.preflight(table)
