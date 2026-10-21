"""Synthetic host decisions are fixtures; they do not authorize any real data."""
import json
import os
import sys
from pathlib import Path

import pytest
from astropy.table import Table
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.types import ElicitResult

from chromatin_trace_mcp import collection as c, localization_merge as lm
from test_merge import prepare, fixture_decision


@pytest.fixture
def anyio_backend(): return 'asyncio'


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    qc, traces, root = prepare(tmp_path, monkeypatch)
    for roi in [1,2,3]:
        path=root/f'{roi:03d}'/'localize_3d/data/localizations.ecsv';path.parent.mkdir(parents=True)
        table=Table({'Buid':[f'roi{roi}-spot{i}' for i in range(4)],'ROI #':[roi]*4,'Barcode #':[1,2,3,3],
                     'xcentroid':[1.,2.,3.,4.], 'ycentroid':[0.]*4, 'zcentroid':[0.]*4, 'CellID #':[1]*4},
                     meta={'comments':['xyz_unit=pixel','genome_assembly=dm6'],'lab':'lab'})
        table['Buid'].description='Original localization identifier'
        table.write(path, format='ascii.ecsv')
    localization=c.execute_collection(str(root),'localizations.ecsv',table_kind='localization');assert localization.status=='PASS',localization.error
    monkeypatch.setenv(lm.OUTPUT_ENV,str(tmp_path/'localization-output'))
    return qc,traces,localization,root


def refs(loc): return [{'collection_run_id':loc.run_id,'manifest_sha256':loc.manifest_sha256}]


def invoke(fixture, indices=None, references=None):
    qc,_,loc,_=fixture
    return lm.execute_localization_merge(qc.run_id,qc.results_sha256,[0,2] if indices is None else indices, refs(loc) if references is None else references)


def no_output(result):
    assert result.status=='ERROR' and result.merged_path is None, result
    output=Path(os.environ[lm.OUTPUT_ENV]);assert not output.exists() or not list(output.iterdir())


def rewrite_manifest(loc, change):
    path=Path(loc.manifest_path);value=json.loads(path.read_text());change(value)
    path.write_text(json.dumps(value));return [{'collection_run_id':loc.run_id,'manifest_sha256':c.digest(path)}]


def native_output(paths, output):
    lm.native.run({'loc_files':paths,'outputFolder':str(output.parent),'output_file':output.name})


def test_native_exact_subset_reproducibility_metadata_provenance_integrity(fixture, tmp_path):
    qc,traces,loc,root=fixture;fixture_decision(qc)
    protected=list(root.rglob('*.ecsv'))+list(Path(loc.manifest_path).parent.glob('*'))+list(Path(traces.manifest_path).parent.glob('*'))+[Path(qc.results_path),Path(qc.report_path)]
    before={p:c.digest(p) for p in protected}
    files=json.loads(Path(loc.manifest_path).read_text())['files']
    direct=tmp_path/'native.ecsv';native_output([files[i]['destination'] for i in [0,2]],direct)
    result=invoke(fixture);assert result.status=='MERGED',result.error
    assert result.source_file_count==2 and result.row_count==8 and result.roi_count==2 and result.barcode_count==3
    assert result.localization_id_count==8 and Path(result.merged_path).read_bytes()==direct.read_bytes()
    assert result.provenance_sha256==c.digest(Path(result.provenance_path))
    detail=json.loads(Path(result.provenance_path).read_text())
    assert [s['roi_mapping'] for s in detail['sources']]==[{'1':['1']},{'3':['3']}]
    assert [s['approved_trace_index'] for s in detail['sources']]==[0,2]
    assert all(s['experiment_root']==str(root) for s in detail['sources'])
    assert all('Original localization identifier' in s['source_column_metadata_yaml'] for s in detail['sources'])
    assert detail['approval_snapshot']['status']=='APPROVED'
    assert detail['authorization_scope']=='human-approved-original-experiment-and-tracing-ROI-selection'
    assert all('source_relative' in s and 'trace_source' in s for s in detail['sources'])
    again=invoke(fixture);assert again.status=='MERGED' and again.merged_sha256==result.merged_sha256 and again.run_id!=result.run_id
    assert before=={p:c.digest(p) for p in protected}


@pytest.mark.parametrize('fault',['awaiting','rejected','selection','one','missing','modified','manifest','wrong-kind','wrong-root','wrong-source','wrong-roi','wrong-directory','duplicate','missing-map','invalid-id','trace-modified'])
def test_invalid_inputs_and_associations_fail_closed(fixture, fault):
    qc,traces,loc,root=fixture
    if fault!='awaiting': fixture_decision(qc, 'REJECT' if fault=='rejected' else 'APPROVE', '' if fault=='rejected' else '0,2')
    references=refs(loc);indices=[0,2]
    files=json.loads(Path(loc.manifest_path).read_text())['files']
    if fault in {'missing','modified'}:
        path=Path(files[0]['destination'])
        if fault=='missing': path.unlink()
        else: path.write_text(path.read_text()+'\n')
    elif fault=='manifest': Path(loc.manifest_path).write_text(Path(loc.manifest_path).read_text()+'\n')
    elif fault=='wrong-kind': references=refs(traces)
    elif fault=='wrong-root':
        def change(v):
            v['experiment_root']=str(root.parent/'foreign-experiment')
            for item in v['files']: item['source']=str(Path(v['experiment_root'])/item['source_relative'])
        references=rewrite_manifest(loc,change)
    elif fault=='wrong-source': references=rewrite_manifest(loc,lambda v: v['files'][0].update(source='/foreign/001/localizations.ecsv'))
    elif fault=='wrong-roi': references=rewrite_manifest(loc,lambda v: v['files'][0].update(roi='3'))
    elif fault=='wrong-directory': references=rewrite_manifest(loc,lambda v: v['files'][0].update(source_roi_directory='002'))
    elif fault=='duplicate': references=references*2
    elif fault=='missing-map': references=rewrite_manifest(loc,lambda v: v['files'].pop(0))
    elif fault=='selection': indices=[0,1]
    elif fault=='one': indices=[0]
    elif fault=='invalid-id': qc=qc.model_copy(update={'run_id':'0'*32});fixture=(qc,traces,loc,root)
    elif fault=='trace-modified':
        path=Path(json.loads(Path(traces.manifest_path).read_text())['files'][0]['destination']);path.write_text(path.read_text()+'\n')
    no_output(invoke(fixture,indices,references))


@pytest.mark.parametrize('fault',['localization','manifest','trace','rejection'])
def test_changes_during_native_run_prevent_publication(fixture, monkeypatch, fault):
    qc,traces,loc,_=fixture;fixture_decision(qc);original=lm.native.run
    def hook(*args,**kwargs):
        original(*args,**kwargs)
        if fault=='rejection': fixture_decision(qc,'REJECT','')
        elif fault=='manifest': Path(loc.manifest_path).write_text(Path(loc.manifest_path).read_text()+'\n')
        else:
            value=loc if fault=='localization' else traces
            path=Path(json.loads(Path(value.manifest_path).read_text())['files'][0]['destination']);path.write_text(path.read_text()+'\n')
    monkeypatch.setattr(lm.native,'run',hook)
    no_output(invoke(fixture))


@pytest.mark.parametrize('fault',['unit','assembly','rows','roi','invalid-ecsv','schema'])
def test_invalid_scientific_snapshot_with_consistent_manifest_is_rejected(fixture, fault):
    qc,_,loc,_=fixture;fixture_decision(qc)
    files=json.loads(Path(loc.manifest_path).read_text())['files'];path=Path(files[2]['destination'])
    table=Table.read(path,format='ascii.ecsv')
    if fault=='unit': table.meta['comments']=['xyz_unit=micron','genome_assembly=dm6']
    elif fault=='assembly': table.meta['comments']=['xyz_unit=pixel','genome_assembly=mm10']
    elif fault=='rows': table=table[:1]
    elif fault=='roi': table['ROI #']=[2]*len(table)
    elif fault=='schema': table.remove_column('Buid')
    table.write(path,format='ascii.ecsv',overwrite=True)
    if fault=='invalid-ecsv': path.write_text('not ECSV')
    def change(v): v['files'][2].update(sha256=c.digest(path),destination_sha256=c.digest(path))
    reference=rewrite_manifest(loc,change)
    no_output(invoke(fixture,references=reference))


@pytest.mark.parametrize('failure',[RuntimeError('native sentinel'),SystemExit(1)])
def test_native_failure_never_publishes(fixture, monkeypatch, failure):
    fixture_decision(fixture[0])
    def fail(*args,**kwargs): raise failure
    monkeypatch.setattr(lm.native,'run',fail);result=invoke(fixture);no_output(result)
    assert result.error_type==type(failure).__name__


def test_output_under_original_inputs_is_blocked(fixture,monkeypatch):
    fixture_decision(fixture[0]);root=fixture[3];monkeypatch.setenv(lm.OUTPUT_ENV,str(root/'forbidden'))
    no_output(invoke(fixture));assert not (root/'forbidden').exists()


def test_ambiguous_duplicate_localization_mapping_is_blocked(fixture):
    qc,_,loc,root=fixture;fixture_decision(qc)
    other=c.execute_collection(str(root),'localizations.ecsv',table_kind='localization');assert other.status=='PASS'
    result=invoke(fixture,references=refs(loc)+refs(other));no_output(result)
    assert 'found 2' in result.error


def test_source_roi_collisions_across_experiments_fail_safely(fixture,monkeypatch,tmp_path):
    from chromatin_trace_mcp import pearsons as p
    qc,traces,loc,root=fixture
    # Independently collect a second experiment having the same original ROI IDs.
    import shutil
    other=tmp_path/'other';shutil.copytree(root,other)
    monkeypatch.setenv('CHROMATIN_EXPERIMENT_ROOTS',os.pathsep.join([str(root),str(other)]))
    trace2=c.execute_collection(str(other),'Trace_ROI-1.ecsv','1');assert trace2.status=='PASS'
    qc=p.execute_pearsons(refs(traces)+refs(trace2));assert qc.status=='COMPUTED'
    fixture_decision(qc,indices='0,3')
    result=lm.execute_localization_merge(qc.run_id,qc.results_sha256,[0,3],refs(loc));no_output(result)
    assert 'does not renumber ROIs' in result.error


@pytest.mark.anyio
async def test_real_stdio_discovery_schema_human_fixture_and_merge(fixture):
    qc,_,loc,_=fixture
    async def host_fixture(context,params):
        return ElicitResult(action='accept',content={'decision':'APPROVE','selected_dataset_indices':'0,2'})
    parameters=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=dict(os.environ))
    async with Client(parameters,elicitation_callback=host_fixture,raise_exceptions=False,read_timeout_seconds=60) as client:
        tools={t.name:t for t in (await client.list_tools()).tools};tool=tools['localization_merge']
        Draft202012Validator.check_schema(tool.input_schema);Draft202012Validator.check_schema(tool.output_schema)
        args={'pearson_run_id':qc.run_id,'results_sha256':qc.results_sha256,'selected_dataset_indices':[0,2],'localization_collections':refs(loc)}
        denied=await client.call_tool('localization_merge',args);assert denied.structured_content['status']=='ERROR'
        decision=await client.call_tool('review_pearson_approval',{'pearson_run_id':qc.run_id,'results_sha256':qc.results_sha256,'request_decision':True});assert decision.structured_content['status']=='APPROVED'
        bad=await client.call_tool('localization_merge',{**args,'selected_dataset_indices':[True,2]});assert bad.is_error
        result=(await client.call_tool('localization_merge',args)).structured_content
        assert result['status']=='MERGED',result;Draft202012Validator(tool.output_schema).validate(result)
        assert result['row_count']==8 and result['structured_response_bytes']<5000
        assert result['structured_response_bytes']==len(json.dumps(result,separators=(',',':'),ensure_ascii=False).encode())
        assert not set(result)&{'table','data','sources','approval_snapshot'}
