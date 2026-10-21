"""Human-host responses are protocol fixtures, not actual human or autonomous-agent trials."""
import json
import os
import sys
from pathlib import Path

import pytest
from astropy.table import Table
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.server.mcpserver import AcceptedElicitation
from mcp.types import ElicitResult

from chromatin_trace_mcp import approval as a, collection as c, pearsons as p
from chromatin_trace_mcp.server import mcp
from chromatin_trace_mcp.step0 import ROOTS_ENV


@pytest.fixture
def anyio_backend(): return 'asyncio'


@pytest.fixture
def qc(tmp_path, monkeypatch):
    root=tmp_path/'inputs'
    for roi,x in [(1,[0.,1.,3.]),(2,[0.,3.,1.]),(3,[0.,2.,6.])]:
        path=root/f'{roi:03d}'/f'tracing/data/Trace_ROI-{roi}.ecsv'
        path.parent.mkdir(parents=True)
        Table({'Spot_ID':['s1','s2','s3','s4'],'Trace_ID':['n1']*4,'Barcode #':[1,2,3,2],
               'ROI #':[roi]*4,'x':x+[8.],'y':[0.]*4,'z':[0.]*4},meta={'comments':['xyz_unit=micron']}).write(path,format='ascii.ecsv')
    monkeypatch.setenv(ROOTS_ENV,str(root));monkeypatch.setenv(c.OUTPUT_ENV,str(tmp_path/'collections'))
    monkeypatch.setenv(p.OUTPUT_ENV,str(tmp_path/'qc'))
    collected=c.execute_collection(str(root),'Trace_ROI-1.ecsv','1')
    assert collected.status=='PASS'
    refs=[{'collection_run_id':collected.run_id,'manifest_sha256':collected.manifest_sha256}]
    result=p.execute_pearsons(refs)
    assert result.status=='COMPUTED',result.error
    return result,collected


def args(qc, request=False):
    result,_=qc
    return {'pearson_run_id':result.run_id,'results_sha256':result.results_sha256,'request_decision':request}


def answer(decision='APPROVE',selection='0,2'):
    return AcceptedElicitation(data=a.HumanDecision(decision=decision, selected_dataset_indices=selection))


def test_scope_fingerprint_and_no_scientific_mutation(qc):
    result,collected=qc
    protected=[Path(result.results_path),Path(result.report_path),Path(result.matrix_path),Path(result.figure_path),Path(collected.manifest_path)]
    protected+=list(Path(collected.manifest_path).parent.glob('*.ecsv'))
    before={str(f):c.digest(f) for f in protected}
    prepared=a.prepare_review(**{k:v for k,v in args(qc).items() if k!='request_decision'})
    assert prepared.state['status']=='AWAITING_APPROVAL'
    approved=a.complete_review(prepared,answer())
    assert approved.status=='APPROVED' and approved.selected_dataset_indices==[0,2]
    state=a.require_scientific_approval(result.run_id,result.results_sha256,[0,2],{'output_format':'png','correlation_threshold':None})
    assert len(state['selected_datasets'])==2
    assert state['evidence']['report_sha256']==c.digest(Path(result.report_path))
    assert state['selected_collection_references']==[{'collection_run_id':collected.run_id,'manifest_sha256':collected.manifest_sha256}]
    assert state['evidence']['results_sha256']==result.results_sha256
    assert before=={str(f):c.digest(f) for f in protected}
    for indices,params in [([0,1],state['evidence']['parameters']),([0,2],{'output_format':'svg','correlation_threshold':None})]:
        with pytest.raises(PermissionError): a.require_scientific_approval(result.run_id,result.results_sha256,indices,params)


@pytest.mark.parametrize('fault',['report','results_parameters','manifest','collected_file','missing_figure','matrix'])
def test_changed_evidence_invalidates_approval(qc,fault):
    result,collected=qc
    a.complete_review(a.prepare_review(result.run_id,result.results_sha256),answer())
    if fault=='report': Path(result.report_path).write_text('changed QC report')
    elif fault=='results_parameters':
        data=json.loads(Path(result.results_path).read_text());data['parameters']['output_format']='svg'
        Path(result.results_path).write_text(json.dumps(data))
    elif fault=='manifest': Path(collected.manifest_path).write_text(Path(collected.manifest_path).read_text()+'\n')
    elif fault=='collected_file':
        file=next(Path(collected.manifest_path).parent.glob('*.ecsv'));file.write_text(file.read_text()+'\n')
    elif fault=='missing_figure': Path(result.figure_path).unlink()
    elif fault=='matrix': Path(result.matrix_path).write_bytes(b'changed')
    prepared=a.prepare_review(result.run_id,result.results_sha256)
    assert prepared.state['status']=='AWAITING_APPROVAL'
    assert prepared.state['selected_dataset_indices']==[]
    with pytest.raises(PermissionError): a.require_scientific_approval(result.run_id,result.results_sha256,[0,2],{'output_format':'png','correlation_threshold':None})
    assert json.loads((a.pearson_root()/'.scientific-approvals'/f'{result.run_id}.json').read_text())['status']=='AWAITING_APPROVAL'


def test_new_valid_checksum_cannot_reuse_prior_approval(qc):
    result,_=qc
    old=a.complete_review(a.prepare_review(result.run_id,result.results_sha256),answer())
    data=json.loads(Path(result.results_path).read_text());data['parameters']['display_note']='changed'
    Path(result.results_path).write_text(json.dumps(data))
    prepared=a.prepare_review(result.run_id,c.digest(Path(result.results_path)))
    assert prepared.state['status']=='AWAITING_APPROVAL'
    assert prepared.state['fingerprint']!=old.evidence_fingerprint


@pytest.mark.parametrize('selection',['','-1','3','0,0','all'])
def test_no_implicit_or_invalid_dataset_selection(qc,selection):
    result,_=qc;prepared=a.prepare_review(result.run_id,result.results_sha256)
    with pytest.raises(ValueError): a.complete_review(prepared,answer(selection=selection))
    assert a.prepare_review(result.run_id,result.results_sha256).state['status']=='AWAITING_APPROVAL'


def test_changed_while_human_reviews_and_concurrent_decision_fail_closed(qc):
    result,_=qc;prepared=a.prepare_review(result.run_id,result.results_sha256)
    a.complete_review(prepared,answer('REJECT',''))
    stale=a.complete_review(prepared,answer())
    assert stale.status=='AWAITING_APPROVAL'
    current=a.prepare_review(result.run_id,result.results_sha256)
    Path(result.report_path).write_text('changed while reviewing')
    assert a.complete_review(current,answer()).status=='AWAITING_APPROVAL'


@pytest.mark.anyio
async def test_agent_cannot_submit_decision_and_host_without_ui_fails_closed(qc):
    async with Client(mcp,raise_exceptions=False) as client:
        tools={t.name:t for t in (await client.list_tools()).tools}
        tool=tools['review_pearson_approval']
        assert set(tool.input_schema['properties'])=={'pearson_run_id','results_sha256','request_decision'}
        Draft202012Validator.check_schema(tool.input_schema);Draft202012Validator.check_schema(tool.output_schema)
        for payload in ({**args(qc),'decision':'APPROVE','selected_dataset_indices':[0,2]},
                        {**args(qc),'answer':{'action':'accept','data':{'decision':'APPROVE','selected_dataset_indices':'0,2'}}},
                        {**args(qc),'prepared':{'state':{'status':'APPROVED','selected_dataset_indices':[0,2]}}}):
            response=await client.call_tool('review_pearson_approval',payload)
            assert response.is_error or response.structured_content['status']=='AWAITING_APPROVAL'
        result=await client.call_tool('review_pearson_approval',args(qc,True))
        assert result.structured_content['status']=='AWAITING_APPROVAL'
        assert 'trusted human-facing' in result.structured_content['reason']
        Draft202012Validator(tool.output_schema).validate(result.structured_content)
        assert 'correlation_matrix' not in result.structured_content
        for bad in ('../bad','', 'f'*31):
            result=await client.call_tool('review_pearson_approval',{**args(qc),'pearson_run_id':bad})
            assert result.is_error
        result=await client.call_tool('review_pearson_approval',{**args(qc),'pearson_run_id':'0'*32})
        assert result.structured_content['status']=='AWAITING_APPROVAL' and result.structured_content['error']
        assert 'trace_merge' in tools and 'localization_merge' in tools
        # Existing numerical retrieval is Step 0-only, not saved Pearson-run retrieval.
        assert 'read_validation_details' in tools
        assert not any('pearson' in name and name.startswith(('get_','read_')) for name in tools)


@pytest.mark.anyio
@pytest.mark.parametrize('action,decision,selection,expected',[
    ('accept','APPROVE','0,2','APPROVED'),('accept','REJECT','','REJECTED'),
    ('decline',None,None,'REJECTED'),('cancel',None,None,'AWAITING_APPROVAL')])
async def test_real_stdio_host_review(qc,action,decision,selection,expected):
    messages=[]
    async def human_fixture(context,params):
        messages.append(params.message)
        content={'decision':decision,'selected_dataset_indices':selection} if action=='accept' else None
        return ElicitResult(action=action,content=content)
    params=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=dict(os.environ))
    async with Client(params,elicitation_callback=human_fixture,read_timeout_seconds=60) as client:
        response=await client.call_tool('review_pearson_approval',args(qc,True))
        assert response.structured_content['status']==expected
        assert len(messages)==1
        assert 'Existing QC report' in messages[0] and 'Saved numerical comparisons' in messages[0]
        assert 'without allele separation' in messages[0] and 'last row' in messages[0]
        cached=await client.call_tool('review_pearson_approval',args(qc))
        assert cached.structured_content['status']==expected
        assert len(messages)==1
        if expected!='APPROVED':
            with pytest.raises(PermissionError): a.require_scientific_approval(qc[0].run_id,qc[0].results_sha256,[0,2],{'output_format':'png','correlation_threshold':None})


def test_inconsistent_saved_selection_cannot_bypass_gate(qc):
    result,_=qc
    approved=a.complete_review(a.prepare_review(result.run_id,result.results_sha256),answer())
    path=Path(approved.decision_record_path);state=json.loads(path.read_text())
    state['selected_dataset_indices']=[0,1]  # Disagrees with the bound selected file identities.
    path.write_text(json.dumps(state))
    with pytest.raises(PermissionError):
        a.require_scientific_approval(result.run_id,result.results_sha256,[0,1],{'output_format':'png','correlation_threshold':None})
    assert a.prepare_review(result.run_id,result.results_sha256).state['status']=='AWAITING_APPROVAL'
