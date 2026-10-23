"""Reviewed saved-result fixtures; scientific binaries are opaque test placeholders."""
import hashlib
import json
from pathlib import Path

import pytest
from mcp import Client

from chromatin_report_mcp import server
from chromatin_report_mcp import workflow_report as report


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rewrite(value, mapping):
    if isinstance(value,str):
        return mapping.get(value,value)
    if isinstance(value,list):
        return [rewrite(x,mapping) for x in value]
    if isinstance(value,dict):
        return {k:rewrite(v,mapping) for k,v in value.items()}
    return value


@pytest.fixture
def evidence(tmp_path,monkeypatch):
    root=tmp_path/'inputs'
    root.mkdir()
    bundle=json.loads((Path(__file__).parent/'fixtures/saved_workflow.json').read_text().replace('@FIXTURE@',str(root)))
    template=bundle['manifest']
    for rel,item in bundle['files'].items():
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(item['data'],indent=2)+'\n' if item['format']=='json' else item['data'])
    old={x['path']:x['sha256'] for x in template['files']}
    for p in root.rglob('*.json'):
        p.write_text(p.read_text().replace('@FIXTURE@',str(root)))
    # Rebind paths, opaque bytes and approval snapshots together until the DAG settles.
    for _ in range(24):
        mapping={old[p]:sha(Path(p)) for p in old if old[p]!=sha(Path(p))}
        approval=json.loads(Path(template['roles']['approval']).read_text())
        fp=hashlib.sha256(json.dumps(approval['evidence'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if fp!=approval['fingerprint']:
            mapping[approval['fingerprint']]=fp
        if not mapping:
            break
        old={p:sha(Path(p)) for p in old}
        for p in root.rglob('*.json'):
            doc=rewrite(json.loads(p.read_text()),mapping)
            p.write_text(json.dumps(doc,indent=2)+'\n')
    else:
        raise AssertionError('Fixture evidence graph did not settle')
    template['files']=[{'path':p,'sha256':sha(Path(p))} for p in old]
    mroot=tmp_path/'manifests';mroot.mkdir()
    mp=mroot/'test.json';mp.write_text(json.dumps(template,indent=2)+'\n')
    monkeypatch.setenv('CHROMATIN_QC_MANIFEST_DIR',str(mroot))
    monkeypatch.setenv('CHROMATIN_REPORT_ARTIFACT_ROOTS',str(root))
    monkeypatch.setenv('CHROMATIN_REPORT_OUTPUT_DIR',str(tmp_path/'reports'))
    return template,mp,root


def test_saved_results_content_and_source_integrity(evidence):
    m,mp,root=evidence
    before={x['path']:sha(Path(x['path'])) for x in m['files']}
    result=report.generate('test',sha(mp))
    text=Path(result['path']).read_text()
    for value in ['0.8691','406','46296','34900','6776','5833','12609','81196','103161','dm6','34140']:
        assert value in text
    for value in ['ROIs are pooled','z units are undeclared','Repeated-barcode','signed coordinate displacements','Spot_ID / Buid','original barcode IDs']:
        assert value in text
    assert text.count('<img ')==7
    assert 'base64' not in text
    assert result['status']=='COMPLETE_WITH_LIMITATIONS'
    assert before=={p:sha(Path(p)) for p in before}
    assert json.loads(Path(result['evidence_path']).read_text())['scientific_calculations_run']==0
    again=report.generate('test',sha(mp));assert again['path']!=result['path']
    assert len(json.dumps(result).encode())<1500


@pytest.mark.parametrize('role',['step0','approval','pearson','trace_merge','localization_merge','baseline','annotation','trace_analysis','localization_analysis','mapping','reference'])
def test_tampered_stage_fails_closed(evidence,role):
    m,mp,_=evidence
    Path(m['roles'][role]).write_text('{}')
    with pytest.raises(ValueError,match='Checksum mismatch'):
        report.generate('test',sha(mp))


def test_missing_figure(evidence):
    m,mp,_=evidence
    Path(next(x['path'] for x in m['files'] if x['path'].endswith('trace_barcode_detection.png'))).unlink()
    with pytest.raises(OSError):report.generate('test',sha(mp))


def test_symlink_escape(evidence,tmp_path):
    m,mp,_=evidence;p=Path(m['roles']['step0']);backup=tmp_path/'escaped.json';p.rename(backup);p.symlink_to(backup)
    with pytest.raises(OSError):report.generate('test',sha(mp))


def test_unauthorized_root(evidence,monkeypatch,tmp_path):
    _,mp,_=evidence;monkeypatch.setenv('CHROMATIN_REPORT_ARTIFACT_ROOTS',str(tmp_path/'other'))
    with pytest.raises(ValueError,match='outside authorized'):report.generate('test',sha(mp))


@pytest.mark.parametrize('value',['../test','/test','test.json',''])
def test_bad_manifest_id(evidence,value):
    with pytest.raises(ValueError,match='Invalid manifest ID'):report.generate(value,'0'*64)


def rebind_role(m,mp,role,update):
    p=Path(m['roles'][role]);doc=json.loads(p.read_text());update(doc);p.write_text(json.dumps(doc,indent=2)+'\n')
    for x in m['files']:
        if x['path']==str(p):x['sha256']=sha(p)
    mp.write_text(json.dumps(m,indent=2)+'\n')


def test_pending_human_approval(evidence):
    m,mp,_=evidence
    rebind_role(m,mp,'approval',lambda x:x.update(status='AWAITING_APPROVAL'))
    with pytest.raises(ValueError,match='not APPROVED'):report.generate('test',sha(mp))
    assert json.loads(Path(m['roles']['approval']).read_text())['status']=='AWAITING_APPROVAL'


def test_wrong_provenance_despite_matching_file_hash(evidence):
    m,mp,_=evidence
    rebind_role(m,mp,'trace_analysis',lambda x:x.update(annotation_run_id='wrong'))
    with pytest.raises(ValueError,match='Provenance mismatch'):report.generate('test',sha(mp))


def test_missing_required_stage(evidence):
    m,mp,_=evidence;m['roles'].pop('localization_analysis');mp.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Missing or unknown'):report.generate('test',sha(mp))


def test_output_cannot_overlap_inputs(evidence,monkeypatch):
    m,mp,_=evidence;monkeypatch.setenv('CHROMATIN_REPORT_OUTPUT_DIR',str(Path(m['roles']['trace_merge']).parent/'reports'))
    with pytest.raises(ValueError,match='overlaps'):report.generate('test',sha(mp))


def test_escaped_title_and_unavailable_metric(evidence):
    m,mp,root=evidence
    ev=report.Evidence(m,[root]);ev.manifest['title']='<script>alert(1)</script>'
    ev.docs['trace_analysis']['neighbor_statistics'].pop('mean_dx')
    html=report.render(ev,root.parent/'report.html','test')
    assert '<script>' not in html and '&lt;script&gt;' in html and 'Unavailable' in html


def test_changed_during_render_is_not_published(evidence,monkeypatch):
    m,mp,_=evidence;original=report.render
    def mutate(*args):
        content=original(*args);Path(m['roles']['mapping']).write_text('[]');return content
    monkeypatch.setattr(report,'render',mutate)
    with pytest.raises(ValueError,match='Checksum mismatch'):report.generate('test',sha(mp))
    assert not list((mp.parent.parent/'reports').glob('*'))


@pytest.mark.anyio
async def test_mcp_discovery_invocation_and_errors(evidence):
    _,mp,_=evidence
    async with Client(server.mcp,raise_exceptions=False) as client:
        tools=(await client.list_tools()).tools
        tool=next(x for x in tools if x.name=='generate_experiment_qc_report')
        assert set(tool.input_schema['properties'])=={'manifest_id','manifest_sha256'}
        result=await client.call_tool(tool.name,{'manifest_id':'test','manifest_sha256':sha(mp)})
        assert not result.is_error
        assert result.structured_content['status']=='COMPLETE_WITH_LIMITATIONS'
        error=await client.call_tool(tool.name,{'manifest_id':'test','manifest_sha256':'invalid'})
        assert error.is_error
        error=await client.call_tool(tool.name,{'manifest_id':'test','manifest_sha256':'0'*64})
        assert error.is_error


@pytest.fixture
def anyio_backend():return 'asyncio'


def test_figure_and_evidence_links_resolve_from_symlink_view(evidence):
    from html.parser import HTMLParser
    from urllib.parse import urlparse, unquote
    m,mp,root=evidence
    result=report.generate('test',sha(mp))
    view=root.parent/'experiment-results';view.symlink_to(Path(result['path']).parent,target_is_directory=True)
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ['src','href'] and not value.startswith('#'):
                    parsed=urlparse(value)
                    assert parsed.scheme=='file'
                    assert Path(unquote(parsed.path)).is_file()
    Links().feed((view/'report.html').read_text())


def test_host_manifest_preparation_and_immutable_ids(evidence,monkeypatch):
    from chromatin_report_mcp.prepare_manifest import prepare
    m,mp,root=evidence
    index={
        'step0':{'details_path':m['roles']['step0']},'pearson':{'results_path':m['roles']['pearson']},
        'approval':{'decision_record_path':m['roles']['approval']},
        'trace_merge':{'provenance_path':m['roles']['trace_merge']},
        'localization_merge':{'provenance_path':m['roles']['localization_merge']},
        'merged_trace_stats':{'evidence_path':m['roles']['baseline']},
        'trace_genomic_coordinates':{'evidence_path':m['roles']['annotation']},
        'trace_analyzer':{'evidence_path':m['roles']['trace_analysis']},
        'localization_analyzer':{'evidence_path':m['roles']['localization_analysis']},
    }
    collections=list(root.glob('stores/collections/*/manifest.json'))
    index['tracing_collection']={'manifest_path':str(next(p for p in collections if '3139' in str(p)))}
    index['localization_collection']={'manifest_path':str(next(p for p in collections if 'b44b' in str(p)))}
    ip=root/'index.json';ip.write_text(json.dumps(index))
    ref=prepare(ip,'prepared')
    assert report.generate(ref['manifest_id'],ref['manifest_sha256'])['verified_artifacts']==55
    with pytest.raises(FileExistsError):prepare(ip,'prepared')


def test_no_scientific_runtime_imports_or_execution():
    import ast
    tree=ast.parse(Path(report.__file__).read_text())
    imports=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):imports.extend(x.name for x in node.names)
        if isinstance(node,ast.ImportFrom):imports.append(node.module)
    assert not any(x.startswith(('traceratops','chromatin_trace_mcp','numpy','astropy','subprocess')) for x in imports)


def test_unavailable_native_neighbor_placeholders_are_not_measurements(evidence):
    m,_,root=evidence
    ev=report.Evidence(m,[root])
    ev.docs['trace_analysis']['neighbor_statistics']={'status':'UNAVAILABLE','observation_count':0,'mean_dx':0,'std_dx':0}
    html=report.render(ev,root.parent/'report.html','test')
    assert '<td>x</td><td>Unavailable</td><td>Unavailable</td>' in html
