"""Generated scientific fixtures and synthetic host approvals only."""
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

from chromatin_trace_mcp import approval as a, collection as c, merge as m, merged_statistics as ms, pearsons as p, tracing_analysis as ta
from test_merge import fixture_decision


@pytest.fixture
def anyio_backend():return 'asyncio'


def prepare(tmp_path,monkeypatch,fault=None):
    root=tmp_path/'experiment.with.dots';rng=np.random.default_rng(33)
    for roi in [1,2,3]:
        records=[]
        for t in range(12):
            for b in [1,2,3,4]:
                if (t+b)%5==0:continue
                trace=f'roi{roi}-nucleus{t}' if fault!='collision' else f'nucleus{t}'
                point=rng.normal(size=3)*.12+b*.2
                records.append((f'spot-{roi}-{t}-{b}',trace,*point,'chr1',b*1000,b*1000+100,roi,b))
        table=Table(rows=records,names=['Spot_ID','Trace_ID','x','y','z','Chrom','Chrom_Start','Chrom_End','ROI #','Barcode #'],
                    meta={'comments':['xyz_unit=micron','genome_assembly=mm10']})
        if fault=='missing-source-unit':table.meta['comments']=['genome_assembly=mm10']
        elif fault=='missing-genome':table.remove_column('Chrom_Start')
        elif fault=='placeholder':table['Chrom']=['xxxxx']*len(table)
        elif fault=='tied-intervals':table['Chrom_Start']=[0]*len(table);table['Chrom_End']=[999999999]*len(table)
        elif fault=='inconsistent-genome':table['Chrom_Start'][0]+=10
        elif fault=='nonfinite':table['x'][0]=np.nan
        elif fault=='bad-interval':table['Chrom_End']=table['Chrom_Start']
        elif fault=='multiple-chromosomes':table['Chrom'][0]='chr2'
        elif fault=='repeated-barcode':table.add_row(table[0])
        elif fault=='no-numeric-neighbors':table['Barcode #']*=2
        path=root/f'{roi:03d}/tracing/data/Trace_ROI-{roi}.ecsv';path.parent.mkdir(parents=True);table.write(path,format='ascii.ecsv')
    monkeypatch.setenv('CHROMATIN_EXPERIMENT_ROOTS',str(root));monkeypatch.setenv(c.OUTPUT_ENV,str(tmp_path/'collections'))
    monkeypatch.setenv(p.OUTPUT_ENV,str(tmp_path/'pearson'));monkeypatch.setenv(m.OUTPUT_ENV,str(tmp_path/'merges'))
    monkeypatch.setenv(ms.OUTPUT_ENV,str(tmp_path/'baselines'));monkeypatch.setenv(ta.OUTPUT_ENV,str(tmp_path/'analysis.with.dots'))
    collected=c.execute_collection(str(root),'Trace_ROI-1.ecsv','1');assert collected.status=='PASS',collected.error
    qc=p.execute_pearsons([{'collection_run_id':collected.run_id,'manifest_sha256':collected.manifest_sha256}]);assert qc.status=='COMPUTED',qc.error
    fixture_decision(qc)
    merged=m.execute_merge(qc.run_id,qc.results_sha256,[0,2]);assert merged.status=='MERGED',merged.error
    baseline=ms.execute_statistics(merged.run_id,merged.merged_sha256,merged.provenance_sha256);assert baseline.status=='COMPUTED',baseline.error
    return qc,collected,merged,baseline,root


@pytest.fixture
def ready(tmp_path,monkeypatch):return prepare(tmp_path,monkeypatch)


def invoke(ready,**kwargs):
    baseline=ready[3];return ta.execute_analysis(baseline.run_id,baseline.evidence_sha256,neighbor_distance_range='auto',**kwargs)


def assert_error(result):
    assert result.status=='ERROR' and result.neighbor_statistics is None and result.figure_count==0


DIRECT_SCRIPT="""
import json,numpy as np
np.random.seed(0)
from traceratops import trace_analyzer as n
capture={}
original=n.plot_neighbor_distances
def neighbor(*a,**kw):
    value=original(*a,**kw);capture['neighbor']=list(map(float,value));return value
n.plot_neighbor_distances=neighbor
barcode=n.ChromatinTraceTable.barcode_statistics
def barcodes(self,*a,**kw):
    value=barcode(self,*a,**kw);capture['barcodes']=value;return value
n.ChromatinTraceTable.barcode_statistics=barcodes
n.process_traces({'trace_files':['trace.ecsv'],'plotXYZ':False,'format':'png','neighbor_distance_range':'auto'})
open('expected.json','w').write(json.dumps(capture))
"""


def test_native_equivalence_figures_full_numerics_reproducibility_and_integrity(ready,tmp_path):
    qc,collected,merged,baseline,root=ready
    protected=list(root.rglob('*.ecsv'))+list(Path(collected.manifest_path).parent.glob('*'))
    protected+=list(Path(merged.merged_path).parent.glob('*'))+list(Path(baseline.evidence_path).parent.glob('*'))+[Path(qc.results_path)]
    before={path:c.digest(path) for path in protected}
    direct=tmp_path/'native.with.dots';direct.mkdir();(direct/'trace.ecsv').write_bytes(Path(merged.merged_path).read_bytes())
    native=subprocess.run([sys.executable,'-c',DIRECT_SCRIPT],cwd=direct,capture_output=True,text=True,timeout=90)
    assert native.returncode==0,native.stderr
    expected=json.loads((direct/'expected.json').read_text())
    result=invoke(ready);assert result.status=='ANALYZED',result.error
    output=Path(result.output_directory);detail=json.loads(Path(result.evidence_path).read_text())
    assert result.figure_count==5 and detail['baseline_sha256']==baseline.evidence_sha256
    assert detail['merged_sha256']==merged.merged_sha256 and detail['input_checks']['global_trace_id_count']==24
    assert not (output/'trace.ecsv').exists()
    actual=result.neighbor_statistics
    assert [actual[k] for k in ['mean_dx','mean_dy','mean_dz','std_dx','std_dy','std_dz']]==expected['neighbor']
    for stem in ta.FIGURES:
        assert (output/(stem+'.png')).read_bytes()==(direct/(stem+'.png')).read_bytes()
    numeric=json.loads((output/'numerical_outputs.json').read_text())
    with np.load(output/'numerical_outputs.npz',allow_pickle=False) as arrays:
        assert {k:arrays[v].tolist() for k,v in numeric['returned_values']['barcode_multiplicities'].items()}==expected['barcodes']
        assert len([v for v in numeric['plot_calls'] if v['method']=='hist'])==5
        boot=[v for v in numeric['plot_calls'] if v['method']=='violinplot']
        assert boot[0]['barcode_labels']==['1','2','3','4']
        assert all(len(arrays[key])==1000 for key in boot[0]['datasets'])
    manifest=json.loads(Path(result.artifact_manifest_path).read_text())
    assert all(c.digest(output/v['name'])==v['sha256'] for v in manifest)
    again=invoke(ready);assert again.status=='ANALYZED'
    with np.load(output/'numerical_outputs.npz',allow_pickle=False) as left,np.load(Path(again.output_directory)/'numerical_outputs.npz',allow_pickle=False) as right:
        assert set(left.files)==set(right.files)
        for key in left.files:np.testing.assert_array_equal(left[key],right[key])
    assert before=={path:c.digest(path) for path in before}


@pytest.mark.parametrize('fault',['collision','missing-genome','placeholder','tied-intervals','inconsistent-genome','nonfinite','bad-interval','multiple-chromosomes','missing-source-unit'])
def test_scientific_ambiguities_reject_before_native_execution(tmp_path,monkeypatch,fault):
    ready=prepare(tmp_path,monkeypatch,fault)
    def forbidden(*args,**kwargs):raise AssertionError('Native must not run')
    monkeypatch.setattr(ta,'run_worker',forbidden)
    result=invoke(ready);assert_error(result);assert result.error_type!='AssertionError'
    assert result.output_directory is None


@pytest.mark.parametrize('fault',['baseline','merge','provenance','approval','source','scope'])
def test_invalid_or_changed_evidence_rejects(ready,monkeypatch,fault):
    qc,collected,merged,baseline,root=ready
    if fault=='baseline':Path(baseline.evidence_path).write_text(Path(baseline.evidence_path).read_text()+'\n')
    elif fault=='merge':Path(merged.merged_path).write_text(Path(merged.merged_path).read_text()+'\n')
    elif fault=='provenance':Path(merged.provenance_path).write_text(Path(merged.provenance_path).read_text()+'\n')
    elif fault=='approval':fixture_decision(qc,'REJECT','')
    elif fault=='source':Path(json.loads(Path(collected.manifest_path).read_text())['files'][0]['destination']).write_text('changed')
    elif fault=='scope':
        path=Path(baseline.evidence_path);value=json.loads(path.read_text());value['scope']='filtered';path.write_text(json.dumps(value));baseline.evidence_sha256=c.digest(path)
    def forbidden(*args,**kwargs):raise AssertionError('Native must not run')
    monkeypatch.setattr(ta,'run_worker',forbidden)
    result=invoke(ready);assert_error(result);assert result.error_type!='AssertionError'


@pytest.mark.parametrize('fault',['baseline','merge','approval'])
def test_changes_during_execution_save_error_not_success(ready,monkeypatch,fault):
    qc,_,merged,baseline,_=ready
    def hook(folder,*args):
        (folder/'stdout.log').write_text('native test transcript')
        if fault=='approval':fixture_decision(qc,'REJECT','')
        elif fault=='merge':Path(merged.merged_path).write_text('changed')
        else:Path(baseline.evidence_path).write_text('changed')
        # Failures must preserve available artifacts; no fabricated success figures.
        raise RuntimeError('evidence changed during worker fixture')
    monkeypatch.setattr(ta,'run_worker',hook)
    result=invoke(ready);assert_error(result)
    assert json.loads(Path(result.evidence_path).read_text())['status']=='ERROR'
    assert 'native test transcript' in (Path(result.output_directory)/'stdout.log').read_text()


def test_post_native_evidence_change_prevents_publication(ready,monkeypatch):
    original=ta.run_worker;baseline=ready[3]
    def hook(*args,**kwargs):
        original(*args,**kwargs)
        Path(baseline.evidence_path).write_text(Path(baseline.evidence_path).read_text()+'\n')
    monkeypatch.setattr(ta,'run_worker',hook)
    result=invoke(ready);assert_error(result)
    assert json.loads(Path(result.evidence_path).read_text())['status']=='ERROR'


def test_repeated_barcodes_preserved_with_native_warning(tmp_path,monkeypatch):
    ready=prepare(tmp_path,monkeypatch,'repeated-barcode');result=invoke(ready);assert result.status=='ANALYZED',result.error
    detail=json.loads(Path(result.evidence_path).read_text());assert any('Repeated barcodes' in w for w in detail['warnings'])
    numeric=json.loads((Path(result.output_directory)/'numerical_outputs.json').read_text())
    with np.load(Path(result.output_directory)/'numerical_outputs.npz',allow_pickle=False) as arrays:
        assert 2 in arrays[numeric['returned_values']['barcode_multiplicities']['1']]


@pytest.mark.parametrize('field,value',[('neighbor_distance_range','0'),('neighbor_distance_range','nan'),('output_format','exe'),('random_seed',-1)])
def test_invalid_options_reject(ready,field,value):
    result=ta.execute_analysis(ready[3].run_id,ready[3].evidence_sha256,**{field:value});assert_error(result)


def test_native_timeout_and_safe_output(ready,monkeypatch):
    monkeypatch.setattr(ta,'TIMEOUT_SECONDS',.001)
    result=invoke(ready);assert_error(result);assert result.error_type=='TimeoutExpired'
    monkeypatch.setenv(ta.OUTPUT_ENV,str(ready[4]/'forbidden'))
    result=invoke(ready);assert_error(result);assert result.output_directory is None


@pytest.mark.anyio
async def test_real_stdio_schema_options_and_compact_references(ready):
    baseline=ready[3]
    params=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=dict(os.environ))
    async with Client(params,raise_exceptions=False,read_timeout_seconds=120) as client:
        tools={t.name:t for t in (await client.list_tools()).tools};assert len(tools)==27
        tool=tools['trace_analyzer'];Draft202012Validator.check_schema(tool.input_schema);Draft202012Validator.check_schema(tool.output_schema)
        args={'baseline_run_id':baseline.run_id,'baseline_sha256':baseline.evidence_sha256,'neighbor_distance_range':'auto','output_format':'svg'}
        assert (await client.call_tool('trace_analyzer',{**args,'random_seed':True})).is_error
        value=(await client.call_tool('trace_analyzer',args)).structured_content
        assert value['status']=='ANALYZED',value
        Draft202012Validator(tool.output_schema).validate(value)
        assert value['figure_count']==5 and value['structured_response_bytes']<6500
        assert value['structured_response_bytes']==len(json.dumps(value,separators=(',',':'),ensure_ascii=False).encode())
        assert not set(value)&{'tables','images','plot_calls','barcode_multiplicities','traceratops_report'}


def test_no_eligible_neighbors_are_unavailable_not_measured_zero(tmp_path,monkeypatch):
    ready=prepare(tmp_path,monkeypatch,'no-numeric-neighbors')
    result=invoke(ready);assert result.status=='ANALYZED',result.error
    assert result.neighbor_statistics['status']=='UNAVAILABLE_NO_ELIGIBLE_NEIGHBORS'
    assert result.neighbor_statistics['observation_count']==0
    detail=json.loads(Path(result.evidence_path).read_text())
    assert any('placeholders, not measured zero distances' in note for note in detail['warnings'])


def test_corrupt_partial_native_metadata_does_not_discard_logs(ready,monkeypatch):
    def failed(folder,*args):
        (folder/'stdout.log').write_text('partial native transcript')
        (folder/'numerical_outputs.json').write_text('{"unfinished":')
        raise RuntimeError('native failed while saving numerical evidence')
    monkeypatch.setattr(ta,'run_worker',failed)
    result=invoke(ready);assert_error(result)
    assert result.evidence_path is not None
    folder=Path(result.output_directory)
    assert (folder/'stdout.log').read_text()=='partial native transcript'
    assert (folder/'numerical_outputs.json').read_text()=='{"unfinished":'
    assert json.loads(Path(result.evidence_path).read_text())['status']=='ERROR'
