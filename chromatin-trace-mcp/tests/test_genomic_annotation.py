"""Generated inputs and explicit synthetic consent; never consent for real experiments."""
import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np
import pytest
from astropy.table import Table
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from chromatin_trace_mcp import genomic_annotation as ga, tracing_analysis as ta, approval as a
from chromatin_trace_mcp.collection import digest
from test_trace_analyzer import prepare, DIRECT_SCRIPT
from test_merge import fixture_decision


@pytest.fixture
def anyio_backend(): return 'asyncio'


@pytest.fixture
def ready(tmp_path,monkeypatch):
    context=prepare(tmp_path,monkeypatch)
    qc,collected,merged,baseline,root=context
    bed=root/'mapping.bed'
    # Replacement values overlap source IDs; native applies each row exactly once.
    bed.write_text('\n'.join(f'chr1\t{b*1000}\t{b*1000+100}\t{b}\tbarcode_{5-b}' for b in range(1,5))+'\n')
    ref=tmp_path/'reference.json'
    ref.write_text(json.dumps({'assembly':'fixture-assembly','authority':'Explicit synthetic fixture, not real assembly evidence',
          'chromosome_sizes':{'chr1':100000},'chromosome_sizes_source':'synthetic fixture'}))
    monkeypatch.setenv(ga.REFERENCE_ENV,str(ref));monkeypatch.setenv(ga.OUTPUT_ENV,str(tmp_path/'annotation'))
    return context,bed,ref


def args(ready):
    context,bed,_=ready;baseline=context[3]
    return dict(baseline_run_id=baseline.run_id,baseline_sha256=baseline.evidence_sha256,
                experiment_root=str(context[4]),bed_relative=bed.name,bed_sha256=digest(bed))


def annotate(ready): return ga.execute_annotation(**args(ready))


def assert_error(result):
    assert result.status=='ERROR' and result.annotated_path is None and result.evidence_path is None


def test_direct_native_replacement_equivalence_integrity_and_reproducibility(ready,tmp_path):
    context,bed,ref=ready;merged=context[2];baseline=context[3]
    protected=[bed,ref]+list(context[4].rglob('*.ecsv'))+list(Path(merged.merged_path).parent.iterdir())+list(Path(baseline.evidence_path).parent.iterdir())
    before={p:digest(p) for p in protected if p.is_file()}
    direct=tmp_path/'native.ecsv'
    mapping=ga.native.load_bed_file(str(bed))
    ga.native.impute_genomic_coordinates(merged.merged_path,mapping,str(direct),{'auto_continue':False})
    result=annotate(ready);assert result.status=='ANNOTATED',result.error
    output=Path(result.annotated_path).parent
    assert (output/'native_annotated.ecsv').read_bytes()==direct.read_bytes()
    expected=Table.read(direct,format='ascii.ecsv');actual=Table.read(result.annotated_path,format='ascii.ecsv')
    assert result.assembly=='fixture-assembly'
    assert actual.meta==ga.corrected_metadata(expected.meta,'fixture-assembly')
    for name in expected.colnames: np.testing.assert_equal(expected[name],actual[name])
    records=json.loads(Path(result.mapping_path).read_text());assert [r['replacement_barcode'] for r in records]==[4,3,2,1]
    original=Table.read(merged.merged_path,format='ascii.ecsv')
    np.testing.assert_array_equal(actual['Barcode #'],5-original['Barcode #'])
    again=annotate(ready);assert again.status=='ANNOTATED',again.error
    assert Path(again.annotated_path).read_bytes()==Path(result.annotated_path).read_bytes()
    assert before=={p:digest(p) for p in before}


@pytest.mark.parametrize('fault',['duplicate-original','duplicate-replacement','missing','malformed','negative','out-of-bounds','unknown-chromosome','overlap','missing-replacement','noninteger'])
def test_mapping_failures(fault):
    table=Table({'Barcode #':[1,2],'Chrom':['xxxxx']*2,'Chrom_Start':[0,0],'Chrom_End':[99,99]})
    rows=['chr1 0 10 1 barcode_3','chr1 20 30 2 barcode_4']
    if fault=='duplicate-original':rows[1]='chr1 20 30 1 barcode_4'
    elif fault=='duplicate-replacement':rows[1]='chr1 20 30 2 barcode_3'
    elif fault=='missing':rows=rows[:1]
    elif fault=='malformed':rows[1]+=' extra'
    elif fault=='negative':rows[1]='chr1 -2 30 2 barcode_4'
    elif fault=='out-of-bounds':rows[1]='chr1 20 3000 2 barcode_4'
    elif fault=='unknown-chromosome':rows[1]='chrX 20 30 2 barcode_4'
    elif fault=='overlap':rows[1]='chr1 5 30 2 barcode_4'
    elif fault=='missing-replacement':rows[1]='chr1 20 30 2'
    elif fault=='noninteger':rows[1]='chr1 20 30 2 barcode_bad'
    with pytest.raises(ValueError):ga.mapping_from_bed('\n'.join(rows).encode(),{'chromosome_sizes':{'chr1':1000}},table)


def test_truncation_rejected():
    table=Table({'Barcode #':[1],'Chrom':['xxx'],'Chrom_Start':[0],'Chrom_End':[99]})
    with pytest.raises(ValueError,match='truncate'):
        ga.mapping_from_bed(b'chr2L 0 10 1 barcode_2',{'chromosome_sizes':{'chr2L':1000}},table)


@pytest.mark.parametrize('fault',['bad-hash','missing-file','outside-root','missing-reference','incomplete-reference','revoked','changed-merge','changed-baseline'])
def test_evidence_failures(ready,monkeypatch,fault):
    context,bed,ref=ready;kw=args(ready)
    if fault=='bad-hash':kw['bed_sha256']='0'*64
    elif fault=='missing-file':bed.unlink()
    elif fault=='outside-root':kw['bed_relative']='../reference.json'
    elif fault=='missing-reference':monkeypatch.delenv(ga.REFERENCE_ENV)
    elif fault=='incomplete-reference':ref.write_text('{"assembly":"dm6"}')
    elif fault=='revoked':fixture_decision(context[0],decision='REJECT',indices='')
    elif fault=='changed-merge':Path(context[2].merged_path).write_text('changed')
    elif fault=='changed-baseline':Path(context[3].evidence_path).write_text('changed')
    assert_error(ga.execute_annotation(**kw))


def test_native_failure_and_changed_bed_during_execution(ready,monkeypatch):
    original=ga.native.impute_genomic_coordinates
    def failing(*args,**kw):raise RuntimeError('native failure')
    monkeypatch.setattr(ga.native,'impute_genomic_coordinates',failing)
    result=annotate(ready);assert_error(result);assert 'native failure' in result.error
    def changed(*args,**kw):
        result=original(*args,**kw);ready[1].write_text(ready[1].read_text()+'\n');return result
    monkeypatch.setattr(ga.native,'impute_genomic_coordinates',changed)
    result=annotate(ready);assert_error(result);assert 'checksum' in result.error


@pytest.mark.anyio
async def test_real_mcp_annotation_analyzer_chain_and_tamper_rejection(ready,monkeypatch):
    context,bed,ref=ready
    async with Client(StdioServerParameters(command=os.sys.executable,args=['-m','chromatin_trace_mcp.server'],env=dict(os.environ)),read_timeout_seconds=120) as client:
        tools={t.name:t for t in (await client.list_tools()).tools}
        Draft202012Validator(tools['trace_genomic_coordinates'].input_schema).validate(args(ready))
        start=time.perf_counter()
        response=await client.call_tool('trace_genomic_coordinates',args(ready));result=response.structured_content
        elapsed=time.perf_counter()-start
        assert result['status']=='ANNOTATED',result
        assert len(json.dumps(result).encode())<3500
        call={'baseline_run_id':context[3].run_id,'baseline_sha256':context[3].evidence_sha256,
              'annotation_run_id':result['run_id'],'annotation_sha256':result['evidence_sha256'],'neighbor_distance_range':'auto'}
        response=await client.call_tool('trace_analyzer',call);analysis=response.structured_content
        assert analysis['status']=='ANALYZED',analysis
        assert analysis['figure_count']==5
        direct=Path(result['annotated_path']).parent/'direct-analyzer';direct.mkdir()
        (direct/'trace.ecsv').write_bytes(Path(result['annotated_path']).read_bytes())
        run=subprocess.run([os.sys.executable,'-c',DIRECT_SCRIPT],cwd=direct,capture_output=True,text=True,timeout=60)
        assert run.returncode==0,run.stderr
        expected=json.loads((direct/'expected.json').read_text())
        assert [analysis['neighbor_statistics'][k] for k in ['mean_dx','mean_dy','mean_dz','std_dx','std_dy','std_dz']]==expected['neighbor']
        for stem in ta.FIGURES:assert (direct/(stem+'.png')).read_bytes()==(Path(analysis['output_directory'])/(stem+'.png')).read_bytes()
        if os.environ.get('GENOMIC_BENCHMARK_RECORD'):
            Path(os.environ['GENOMIC_BENCHMARK_RECORD']).write_text(json.dumps({'scope':'generated fixture; synthetic approval, not real-experiment consent',
                'annotation_mcp_call_seconds':elapsed,'annotation_server_seconds':result['execution_seconds'],
                'annotation_structured_response_bytes':len(json.dumps(result,separators=(',',':')).encode()),
                'annotation_tool_calls':1,'downstream_analyzer_equivalence':True,'all_five_native_figures_exact':True,
                'provider_requests':0,'provider_input_tokens':None,'provider_output_tokens':None},indent=2))
        path=Path(result['annotated_path']);table=Table.read(path,format='ascii.ecsv');table['x'][0]+=1;table.write(path,format='ascii.ecsv',overwrite=True)
        response=await client.call_tool('trace_analyzer',call)
        assert response.structured_content['status']=='ERROR'
        assert 'checksum' in response.structured_content['error']


def test_nonannotation_changes_rejected_even_if_values_otherwise_valid(ready):
    context,bed,ref=ready
    original=Table.read(context[2].merged_path,format='ascii.ecsv')
    result=annotate(ready);assert result.status=='ANNOTATED',result.error
    table=Table.read(result.annotated_path,format='ascii.ecsv');table['Trace_ID'][0]='changed'
    mapping=ga.native.load_bed_file(str(bed))
    with pytest.raises(AssertionError):ga.verify_derivative(original,table,mapping,table.meta)


def test_annotation_reference_and_approval_rechecked_by_analyzer(ready):
    result=annotate(ready);assert result.status=='ANNOTATED',result.error
    context,bed,ref=ready;baseline=context[3]
    kw=dict(annotation_run_id=result.run_id,annotation_sha256=result.evidence_sha256)
    document=json.loads(ref.read_text());document['authority']='changed authority';ref.write_text(json.dumps(document))
    analysis=ta.execute_analysis(baseline.run_id,baseline.evidence_sha256,**kw)
    assert analysis.status=='ERROR' and 'reference changed' in analysis.error
    fixture_decision(context[0],decision='REJECT',indices='')
    analysis=ta.execute_analysis(baseline.run_id,baseline.evidence_sha256,**kw)
    assert analysis.status=='ERROR' and analysis.figure_count==0


def test_changed_bed_before_analyzer_publication_fails_closed(ready,monkeypatch):
    result=annotate(ready);assert result.status=='ANNOTATED',result.error
    context,bed,_=ready;baseline=context[3];worker=ta.run_worker
    def changing(*args,**kwargs):
        worker(*args,**kwargs);bed.write_text(bed.read_text()+'\n')
    monkeypatch.setattr(ta,'run_worker',changing)
    analysis=ta.execute_analysis(baseline.run_id,baseline.evidence_sha256,annotation_run_id=result.run_id,annotation_sha256=result.evidence_sha256)
    assert analysis.status=='ERROR' and analysis.figure_count==0 and 'checksum' in analysis.error


def test_invalid_annotation_references(ready):
    baseline=ready[0][3]
    result=ta.execute_analysis(baseline.run_id,baseline.evidence_sha256,annotation_run_id='0'*32,annotation_sha256='0'*64)
    assert result.status=='ERROR' and result.figure_count==0
    result=ta.execute_analysis(baseline.run_id,baseline.evidence_sha256,annotation_run_id='0'*32)
    assert result.status=='ERROR' and 'together' in result.error
