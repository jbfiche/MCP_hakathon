"""Collection accuracy is byte equivalence to native Traceratops, not an AI judge."""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from astropy.table import Table
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from chromatin_trace_mcp import collection as c
from chromatin_trace_mcp.server import mcp
from chromatin_trace_mcp.step0 import ROOTS_ENV


@pytest.fixture
def anyio_backend(): return 'asyncio'


def write_roi(root, unit, role='tracing'):
    rid = int(unit)
    if role == 'tracing':
        p = root/unit/f'tracing/data/Trace_3D_barcode_mask-mask0_ROI-{rid}.ecsv'
        t = Table({'Spot_ID': ['s1', 's2'], 'Trace_ID': ['n1', 'n1'], 'x': [0., 1.], 'y': [2., 3.],
                   'z': [4., 5.], 'ROI #': [rid, rid], 'Barcode #': [1, 2]},
                  meta={'comments': ['xyz_unit=micron', 'Do not change metadata']})
    else:
        p = root/unit/'localize_3d/data/localizations_3D_barcode.ecsv'
        t = Table({'Buid': ['s1', 's2'], 'ROI #': [rid, rid], 'Barcode #': [1, 2],
                   'xcentroid': [0., 1.], 'ycentroid': [2., 3.], 'zcentroid': [4., 5.]})
    p.parent.mkdir(parents=True, exist_ok=True)
    t.write(p, format='ascii.ecsv')
    return p


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    root = tmp_path/'experiment'; root.mkdir()
    for unit in ('001', '002'):
        write_roi(root, unit);write_roi(root, unit, 'localization')
    monkeypatch.setenv(ROOTS_ENV, str(root))
    monkeypatch.setenv(c.OUTPUT_ENV, str(tmp_path/'out'))
    return root


def invoke(root, **kw):
    return c.execute_collection(str(root), 'Trace_3D_barcode_mask-mask0_ROI-1.ecsv', '1', **kw)


@pytest.mark.parametrize('role,rename', [('tracing', False), ('tracing', True), ('localization', False)])
def test_exact_native_equivalence_and_provenance(experiment, tmp_path, role, rename):
    example = 'Trace_3D_barcode_mask-mask0_ROI-1.ecsv' if role == 'tracing' else 'localizations_3D_barcode.ecsv'
    variable = '1' if role == 'tracing' else None
    before = {p: p.read_bytes() for p in experiment.rglob('*.ecsv')}
    direct = c.native.collect_files(experiment, example, tmp_path/'direct', variable_part=variable, rename=rename)
    result = c.execute_collection(str(experiment), example, variable, role, rename)
    assert result.status == 'PASS', result.error
    assert result.file_count == 2 and result.total_rows == 4
    manifest = json.loads(Path(result.manifest_path).read_text())
    assert c.digest(Path(result.manifest_path)) == result.manifest_sha256
    assert manifest['phase'] == result.phase == 'collection_only'
    assert manifest['parameters']['force'] is False
    assert {f['roi'] for f in manifest['files']} == {'1', '2'}
    assert {p.name: p.read_bytes() for p in direct} == {f['destination_name']: Path(f['destination']).read_bytes() for f in manifest['files']}
    for f in manifest['files']:
        assert f['sha256'] == f['destination_sha256'] == c.digest(Path(f['source']))
        assert f['source_relative'].startswith(f['source_roi_directory']+'/')
    assert before == {p: p.read_bytes() for p in before}
    assert not list((tmp_path/'out').glob('.pending-*'))


@pytest.mark.parametrize('fault,error', [('missing', 'FileNotFoundError'), ('ambiguous', 'ValueError'),
                                      ('invalid', 'InconsistentTableError'), ('columns', 'ValueError'),
                                      ('roi', 'ValueError'), ('width', 'FileNotFoundError')])
def test_invalid_inputs_publish_nothing(experiment, fault, error):
    p = next((experiment/'001').rglob('Trace*.ecsv'))
    if fault == 'missing': p.unlink()
    elif fault == 'ambiguous':
        q = p.parent/'nested'/p.name;q.parent.mkdir();q.write_bytes(p.read_bytes())
    elif fault == 'invalid': p.write_text('not ECSV')
    elif fault == 'columns': Table({'Barcode #': [1]}).write(p, format='ascii.ecsv', overwrite=True)
    elif fault == 'roi':
        t=Table.read(p,format='ascii.ecsv');t['ROI #']=[9,9];t.write(p,format='ascii.ecsv',overwrite=True)
    elif fault == 'width':
        p.rename(p.with_name(p.name.replace('ROI-1', 'ROI-101')))
    result = invoke(experiment)
    assert result.status == 'ERROR' and result.error_type == error
    assert result.manifest_path is None
    assert result.failure_path and Path(result.failure_path).is_file()
    assert not [p for p in Path(os.environ[c.OUTPUT_ENV]).iterdir() if p.is_dir()]


@pytest.mark.parametrize('example,variable', [('../x.ecsv', None), ('x.csv', None), ('*.ecsv', None),
                                           ('x.ecsv', ''), ('x.ecsv', 'missing'), ('11.ecsv', '1')])
def test_bad_pattern(experiment, example, variable):
    result=c.execute_collection(str(experiment), example, variable)
    assert result.status == 'ERROR' and result.error_type == 'ValueError'


def test_denied_root(experiment):
    assert invoke(experiment.parent).error_type == 'PermissionError'


def test_output_inside_input_rejected(experiment, monkeypatch):
    monkeypatch.setenv(c.OUTPUT_ENV, str(experiment/'new_outputs'))
    result=invoke(experiment)
    assert result.status == 'ERROR' and result.error_type == 'PermissionError'
    assert not (experiment/'new_outputs').exists()


@pytest.mark.parametrize('kind', ['matching_file', 'roi_directory'])
def test_symlink_inputs_refused(experiment, tmp_path, kind):
    if kind == 'matching_file':
        p=next((experiment/'001').rglob('Trace*.ecsv'));target=tmp_path/p.name;p.rename(target);p.symlink_to(target)
    else:
        target=tmp_path/'external';(experiment/'001').rename(target);(experiment/'001').symlink_to(target,target_is_directory=True)
    assert invoke(experiment).error_type == 'PermissionError'


def test_irrelevant_links_and_forbidden_trees_not_read(experiment, tmp_path):
    (experiment/'001'/'image.tif').symlink_to(tmp_path/'absent')
    forbidden=experiment/'001/full_pwd';forbidden.mkdir();(forbidden/'huge.ecsv').write_text('must not parse')
    result=invoke(experiment)
    assert result.status == 'PASS'
    assert result.skipped_symlinks == 1 and result.excluded_directories == 1


@pytest.mark.parametrize('limit,value', [('MAX_ENTRIES', 1), ('MAX_DEPTH', 1), ('MAX_FILE_BYTES', 1),
                                      ('MAX_TOTAL_BYTES', 1), ('MAX_FILES', 1)])
def test_limits_fail_closed(experiment, monkeypatch, limit, value):
    monkeypatch.setattr(c, limit, value)
    assert invoke(experiment).status == 'ERROR'


def test_reproducible_copies_distinct_runs(experiment):
    a,b=invoke(experiment),invoke(experiment)
    assert a.run_id != b.run_id
    assert [(f['roi'],f['sha256']) for f in a.files] == [(f['roi'],f['sha256']) for f in b.files]


@pytest.mark.parametrize('fault', ['changed_output', 'missing_output', 'native_failure', 'changed_source'])
def test_native_failures_and_integrity(experiment, monkeypatch, fault):
    original=c.native.collect_files
    def native_call(*a, **kw):
        if fault == 'native_failure': raise OSError('injected native failure')
        files=original(*a,**kw)
        if fault == 'changed_output': files[0].write_bytes(files[0].read_bytes()+b'\n')
        if fault == 'missing_output': return []
        if fault == 'changed_source':
            p=next((experiment/'001').rglob('Trace*.ecsv'));p.write_bytes(p.read_bytes()+b'\n')
        return files
    monkeypatch.setattr(c.native,'collect_files',native_call)
    result=invoke(experiment)
    assert result.status == 'ERROR' and result.manifest_path is None
    assert not list(Path(os.environ[c.OUTPUT_ENV]).glob('*/manifest.json'))


def test_native_called_and_no_downstream(experiment, monkeypatch):
    calls=[];original=c.native.collect_files
    def wrapped(*a,**kw): calls.append(kw);return original(*a,**kw)
    monkeypatch.setattr(c.native,'collect_files',wrapped)
    import traceratops.trace_pearsons as pearsons
    import traceratops.trace_merge as merge
    def forbidden(*a,**k):raise AssertionError('Downstream work forbidden')
    monkeypatch.setattr(pearsons,'main',forbidden);monkeypatch.setattr(merge,'main',forbidden)
    assert invoke(experiment).status == 'PASS'
    assert len(calls)==1 and calls[0]['force'] is False
    assert not list(experiment.rglob('manifest.json'))


def test_non_roi_and_duplicate_roi_directories(experiment):
    (experiment/'notes').mkdir()
    assert invoke(experiment).status == 'ERROR'
    (experiment/'notes').rmdir();(experiment/'1').mkdir()
    assert invoke(experiment).status == 'ERROR'


def test_empty_valid_ecsv(experiment):
    p=next((experiment/'001').rglob('Trace*.ecsv'));t=Table.read(p,format='ascii.ecsv');t[:0].write(p,format='ascii.ecsv',overwrite=True)
    result=invoke(experiment)
    assert result.status=='PASS' and result.total_rows==2
    assert any(f['empty_table'] for f in json.loads(Path(result.manifest_path).read_text())['files'])


def test_native_collision_rejected(experiment):
    p=next((experiment/'002').rglob('Trace*.ecsv'))
    p.rename(p.with_name(p.name.replace('ROI-2', 'ROI-1')))
    result=invoke(experiment)
    assert result.status=='ERROR' and result.error_type=='FileExistsError'


@pytest.mark.anyio
async def test_manifest_preview_is_bounded(experiment):
    for unit in range(3,13):write_roi(experiment,f'{unit:03d}','localization')
    async with Client(mcp) as client:
        result=await client.call_tool('collect_files',{'experiment_root':str(experiment), 'example_file':'localizations_3D_barcode.ecsv','table_kind':'localization'})
        payload=result.structured_content
        assert payload['file_count']==12 and len(payload['files'])<=10
        assert payload['files_truncated']
        assert len(json.loads(Path(payload['manifest_path']).read_text())['files'])==12
        assert payload['structured_response_bytes']<12000


def test_step0_agent_surface_still_excludes_collection():
    path=Path(__file__).parents[1]/'benchmarks/agent_step0'
    # Static allowlist inspection avoids importing an optional agent SDK in the science environment.
    import ast
    tree=ast.parse((path/'benchmark_agent.py').read_text())
    assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='STEP0' for t in n.targets))
    assert 'collect_files' not in ast.literal_eval(assignment.value.args[0])


@pytest.mark.anyio
async def test_mcp_schema_errors_and_response_size(experiment):
    async with Client(mcp,raise_exceptions=False) as client:
        tools={t.name:t for t in (await client.list_tools()).tools}
        assert 'collect_files' in tools
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(tools['collect_files'].input_schema)
        bad=await client.call_tool('collect_files',{'experiment_root':str(experiment)})
        assert bad.is_error
        bad=await client.call_tool('collect_files',{'experiment_root':str(experiment),'example_file':'x.ecsv','table_kind':'anything'})
        assert bad.is_error
        result=await client.call_tool('collect_files',{'experiment_root':str(experiment),'example_file':'Trace_3D_barcode_mask-mask0_ROI-1.ecsv','variable_part':'1'})
        payload=result.structured_content
        assert payload['status']=='PASS' and payload['phase']=='collection_only'
        assert payload['structured_response_bytes']==len(json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode())
        assert payload['structured_response_bytes'] < 10000
        Draft202012Validator(tools['collect_files'].output_schema).validate(payload)
        assert 'get_validation_summary' in tools


@pytest.mark.anyio
async def test_real_stdio_collection_only(experiment):
    params=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=dict(os.environ))
    async with Client(params,read_timeout_seconds=30) as client:
        result=await client.call_tool('collect_files',{'experiment_root':str(experiment),'example_file':'Trace_3D_barcode_mask-mask0_ROI-1.ecsv','variable_part':'1'})
        assert result.structured_content['status']=='PASS'
        assert Path(result.structured_content['manifest_path']).is_file()
    assert not list(Path(os.environ[c.OUTPUT_ENV]).rglob('*.png'))
