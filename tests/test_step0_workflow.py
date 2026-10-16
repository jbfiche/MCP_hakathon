"""Two-server Step 0 contract: formatting never repeats or alters validation."""
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from astropy.table import Table
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from chromatin_trace_mcp.server import mcp as trace_mcp
from chromatin_trace_mcp.step0 import save_validation_result, evaluate, StructureRules
from chromatin_report_mcp.server import mcp as report_mcp
from chromatin_trace_mcp.step0_reporting import render_reports


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    root = tmp_path/'experiment'
    trace = root/'001/tracing/data/Trace_3D_barcode_mask-mask0_ROI-1.ecsv'
    loc = root/'001/localize_3d/data/localizations_3D_barcode.ecsv'
    trace.parent.mkdir(parents=True)
    loc.parent.mkdir(parents=True)
    Table({'Spot_ID': ['spot1'], 'Trace_ID': ['nucleus1'], 'x': [0.], 'y': [0.], 'z': [0.],
           'ROI #': [1], 'Barcode #': [1]}).write(trace, format='ascii.ecsv')
    Table({'Buid': ['spot1'], 'ROI #': [1], 'Barcode #': [1],
           'xcentroid': [0.], 'ycentroid': [0.], 'zcentroid': [0.]}).write(loc, format='ascii.ecsv')
    storage = tmp_path/'validation'
    output = tmp_path/'reports'
    monkeypatch.setenv('CHROMATIN_EXPERIMENT_ROOTS', str(root))
    monkeypatch.setenv('CHROMATIN_STEP0_OUTPUT_DIR', str(storage))
    monkeypatch.setenv('CHROMATIN_VALIDATION_INPUT_DIR', str(storage))
    monkeypatch.setenv('CHROMATIN_REPORT_OUTPUT_DIR', str(output))
    return root, trace, loc, storage, output


def rules(barcodes=('1',)):
    return StructureRules(expected_roi_ids=['1'], expected_barcodes=list(barcodes), barcode_source='Explicit toy fixture design')


def args(summary):
    return {'validation_run_id': summary['run_id'], 'validation_sha256': summary['validation_sha256']}


@pytest.mark.anyio
@pytest.mark.parametrize('case,status,code', [('complete', 'PASS', None), ('missing_barcode', 'PASS', 'MISSING_BARCODE_OBSERVATIONS'),
                                           ('missing_file', 'FAIL', 'MISSING_LOCALIZATION'), ('invalid_ecsv', 'ERROR', 'INVALID_ECSV'),
                                           ('incomplete', 'INCOMPLETE', 'EXPECTED_BARCODES_UNAVAILABLE')])
async def test_single_call_reports_preserve_all_findings(experiment, monkeypatch, case, status, code):
    root, trace, loc, storage, output = experiment
    if case == 'missing_file': loc.unlink()
    if case == 'invalid_ecsv': trace.write_text('invalid ECSV')
    policy = None if case == 'incomplete' else rules(('1', '2') if case == 'missing_barcode' else ('1',)).model_dump()
    inputs = {p: p.read_bytes() for p in root.rglob('*.ecsv')}
    reads = []
    original = Table.read
    def counted(*a, **kw):
        reads.append(1)
        return original(*a, **kw)
    monkeypatch.setattr(Table, 'read', counted)
    async with Client(trace_mcp, raise_exceptions=True) as client:
        # One invocation creates evidence and BOTH human report formats.
        result = await client.call_tool('run_experiment_validation', {'experiment_root': str(root), 'rules': policy})
        payload = result.structured_content
        assert payload['status'] == status
        assert len(reads) == (1 if case == 'missing_file' else 2)
        snapshot = Path(payload['details_path']).read_bytes()
        assert hashlib.sha256(snapshot).hexdigest() == payload['validation_sha256']
        document = json.loads(snapshot)
        for key in ('human_report_path', 'html_report_path'):
            text = Path(payload[key]).read_text()
            assert f'Status: {status}' in text
            if code: assert code in text
            for finding in document['findings']:
                assert finding['code'] in text
                if key == 'human_report_path': assert finding['message'] in text
            if case == 'missing_barcode': assert 'Missing expected barcodes: 2' in text
        cached = await client.call_tool('get_validation_summary', {'validation_run_id': payload['run_id']})
        assert cached.structured_content['human_report_path'] == payload['human_report_path']
        assert Path(payload['details_path']).read_bytes() == snapshot
        assert len(reads) == (1 if case == 'missing_file' else 2)
    assert inputs == {p: p.read_bytes() for p in inputs}
    assert not output.exists()  # No reporting server/configuration was needed.


def test_formatter_is_pure_and_escapes_html(experiment):
    import copy
    root, *_ = experiment
    doc = evaluate(str(root), rules(('1', '2')))
    doc['findings'].append({'severity': 'WARNING', 'code': 'TEST', 'message': '<script>alert(1)</script>'})
    before = copy.deepcopy(doc)
    from chromatin_trace_mcp.step0 import summarize
    summary = summarize(doc)
    saved = copy.deepcopy(summary)
    markdown, html = render_reports(doc, summary)
    assert '<script>alert(1)</script>' in markdown
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert doc == before and summary == saved


def test_rendering_failure_preserves_scientific_evidence(experiment, monkeypatch):
    import chromatin_trace_mcp.step0 as step0
    root, trace, loc, storage, output = experiment
    monkeypatch.setattr(step0, 'render_reports', lambda *a: (_ for _ in ()).throw(OSError('test renderer failure')))
    with pytest.raises(OSError):
        save_validation_result(evaluate(str(root), rules()))
    evidence = next(storage.rglob('details.json'))
    assert json.loads(evidence.read_text())['status'] == 'PASS'
    assert evidence.with_name('summary.json').is_file()


@pytest.mark.anyio
async def test_report_server_keeps_only_richer_writers():
    async with Client(report_mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert names == {'write_comparison_report', 'write_comparison_pdf'}


@pytest.mark.anyio
@pytest.mark.parametrize('tool', ['run_experiment_validation', 'validate_ecsv_tables'])
async def test_stdio_one_trace_server_and_one_invocation(experiment, tool):
    root, trace, loc, storage, output = experiment
    env = dict(os.environ)
    env.pop('CHROMATIN_VALIDATION_INPUT_DIR', None)
    env.pop('CHROMATIN_REPORT_OUTPUT_DIR', None)
    params = StdioServerParameters(command=sys.executable, args=['-m', 'chromatin_trace_mcp.server'], env=env)
    async with Client(params, read_timeout_seconds=30) as client:
        result = await client.call_tool(tool, {'experiment_root': str(root), 'rules': rules().model_dump()})
        payload = result.structured_content
        assert payload['status'] == 'PASS'
        assert Path(payload['human_report_path']).is_file()
        assert Path(payload['html_report_path']).is_file()
    metrics = [json.loads(line) for line in (storage/'tool_metrics.jsonl').read_text().splitlines()]
    assert len(metrics) == 1 and metrics[0]['tool_name'] == tool
