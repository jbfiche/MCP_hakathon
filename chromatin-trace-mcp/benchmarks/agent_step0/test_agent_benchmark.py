"""Offline tests; scripted Model objects test plumbing, never autonomy/usage."""
import asyncio
import json
import os
from pathlib import Path

import pytest
from agents import Agent, Model, ModelResponse, Runner, set_tracing_disabled
from agents.usage import Usage
from mcp.types import CallToolResult, TextContent
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from benchmark_agent import (Answer, INSTRUCTION, ScopedServer, STEP0, allowed, child_env,
                             MeasuredModel, direct_matches, encoded, score, usage_total)
from reference import fingerprint, make_fixtures, oracle


@pytest.fixture
def case(tmp_path):
    return make_fixtures(tmp_path/'fixtures')[0]


def config():
    return {'server_command': 'unused', 'server_args': [], 'server_cwd': '/tmp', 'server_env': {}}


@pytest.mark.parametrize('name,status,records', [('complete', 'PASS', 8), ('missing_file', 'FAIL', 6),
                                               ('missing_barcode', 'PASS', 7), ('invalid_ecsv', 'ERROR', 6)])
def test_independent_fixture_oracle(tmp_path, name, status, records):
    c = next(c for c in make_fixtures(tmp_path) if c['name'] == name)
    truth = oracle(Path(c['root']), c['rules'])
    assert truth['status'] == status
    assert truth['records'] == records
    assert truth['roi_count'] == 2
    if name == 'missing_barcode':
        assert truth['missing_barcodes'] == [{'roi': '2', 'role': 'tracing', 'barcodes': ['2']}]


def test_allowlists():
    assert len(allowed('A')) == 6
    assert allowed('B') == {'run_experiment_validation'}
    assert allowed('A') | allowed('B') == STEP0


@pytest.mark.parametrize('tool', ['collect_files', 'trace_merge', 'trace_analyzer', 'localization_analyzer',
                                 'filter_traces', 'trace_to_matrix', 'compare_datasets', 'unknown'])
def test_block_processing_before_dispatch(case, tmp_path, tool):
    server = ScopedServer(config(), case, tmp_path/'out', 'B')
    with pytest.raises(PermissionError):
        asyncio.run(server.call_tool(tool, {}))
    assert not server.calls[0]['dispatched']


@pytest.mark.parametrize('args', [{'experiment_root': '/etc'}, {'experiment_root': '/tmp/../etc'},
                                  {'validation_run_id': 'another-trial'},
                                  {'experiment_root': None}])
def test_root_and_cached_run_scope(case, tmp_path, args):
    server = ScopedServer(config(), case, tmp_path/'out', 'B')
    with pytest.raises((PermissionError, TypeError)):
        asyncio.run(server.call_tool('run_experiment_validation', args))
    assert not server.calls[0]['dispatched']


def test_policy_is_immutable(case, tmp_path):
    server = ScopedServer(config(), case, tmp_path/'out', 'B')
    with pytest.raises(PermissionError):
        asyncio.run(server.call_tool('run_experiment_validation', {'experiment_root': case['root'], 'rules': {'expected_barcodes': []}}))


def test_call_budget(case, tmp_path):
    server = ScopedServer(config(), case, tmp_path/'out', 'B', {'calls': 0, 'response_bytes': 1, 'total_bytes': 1})
    with pytest.raises(PermissionError, match='budget'):
        asyncio.run(server.call_tool('run_experiment_validation', {}))


@pytest.mark.parametrize('per_response,total', [(1, 100000), (100000, 1)])
def test_response_budgets(case, tmp_path, monkeypatch, per_response, total):
    from agents.mcp import MCPServerStdio
    async def response(*args, **kwargs):
        return CallToolResult(content=[TextContent(type='text', text='{}')], structuredContent={'status': 'PASS'})
    monkeypatch.setattr(MCPServerStdio, 'call_tool', response)
    server = ScopedServer(config(), case, tmp_path/'out', 'B', {'calls': 8, 'response_bytes': per_response, 'total_bytes': total})
    server.schemas['run_experiment_validation'] = {'type': 'object'}
    with pytest.raises(PermissionError, match='response budget'):
        asyncio.run(server.call_tool('run_experiment_validation', {'experiment_root': case['root']}))
    assert server.calls[0]['dispatched']


def test_invalid_arguments_rejected(case, tmp_path):
    from jsonschema import ValidationError
    server = ScopedServer(config(), case, tmp_path/'out', 'B')
    server.schemas['run_experiment_validation'] = {'type': 'object', 'required': ['experiment_root']}
    with pytest.raises(ValidationError):
        asyncio.run(server.call_tool('run_experiment_validation', {}))
    assert not server.calls[0]['dispatched']


def test_secret_environment_not_inherited(case, tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-test-only')
    monkeypatch.setenv('CHROMATIN_TRACE_ECSV', '/unrelated')
    env = child_env(config(), case, tmp_path)
    assert 'OPENAI_API_KEY' not in env
    assert 'CHROMATIN_TRACE_ECSV' not in env
    assert env['CHROMATIN_EXPERIMENT_ROOTS'] == case['root']


def test_usage_null_not_zero():
    assert all(v is None for v in usage_total([]).values())
    result = usage_total([{'usage': {'input_tokens': 3, 'output_tokens': 2, 'total_tokens': 5}}])
    assert result == {'input_tokens': 3, 'output_tokens': 2, 'total_tokens': 5, 'cached_tokens': None, 'reasoning_tokens': None}


def test_provider_usage_details():
    r = {'usage': {'input_tokens': 5, 'output_tokens': 7, 'total_tokens': 12,
                   'input_tokens_details': {'cached_tokens': 2}, 'output_tokens_details': {'reasoning_tokens': 3}}}
    assert usage_total([r, r]) == {'input_tokens': 10, 'output_tokens': 14, 'total_tokens': 24, 'cached_tokens': 4, 'reasoning_tokens': 6}


@pytest.mark.parametrize('failure', [False, True])
def test_capture_provider_object_without_normalized_usage(monkeypatch, failure):
    from agents.models.openai_responses import OpenAIResponsesModel
    from openai import AsyncOpenAI
    from types import SimpleNamespace
    class RawUsage:
        def model_dump(self, **kwargs):
            assert kwargs == {'exclude_unset': True}
            return {'input_tokens': 12, 'output_tokens': 3, 'total_tokens': 15}
    async def fake_fetch(*args, **kwargs):
        if failure:
            raise TimeoutError('synthetic timeout')
        return SimpleNamespace(model='synthetic-provider-model', id='synthetic-response', usage=RawUsage())
    monkeypatch.setattr(OpenAIResponsesModel, '_fetch_response', fake_fetch)
    async def run():
        async with AsyncOpenAI(api_key='fake-test-only') as client:
            measured = MeasuredModel('requested-name', client)
            if failure:
                with pytest.raises(TimeoutError):
                    await measured._fetch_response()
                assert usage_total(measured.records)['total_tokens'] is None
            else:
                await measured._fetch_response()
                assert measured.records[0]['model'] == 'synthetic-provider-model'
                assert usage_total(measured.records)['total_tokens'] == 15
                assert usage_total(measured.records)['cached_tokens'] is None
    asyncio.run(run())


def test_fingerprint_detects_changes(case):
    root = Path(case['root'])
    before = fingerprint(root)
    assert before == fingerprint(root)
    next(root.rglob('*.ecsv')).write_text('damaged')
    assert before != fingerprint(root)


def answer_dict(**changes):
    answer = {'answer': 'Two ROIs observed.', 'roi_count': 2, 'required_files_present': None,
              'missing_files': None, 'missing_barcodes': None, 'status': None,
              'ready_within_step0_policy': None, 'report_path': None,
              'evidence_tools': ['inspect_experiment_directory'], 'scientific_conclusions': []}
    answer.update(changes)
    return answer


@pytest.mark.parametrize('change,passes', [({}, True), ({'roi_count': 3}, False),
                                        ({'scientific_conclusions': ['biologically normal']}, False),
                                        ({'evidence_tools': ['trace_merge']}, False)])
def test_deterministic_scoring(case, tmp_path, change, passes):
    truth = oracle(Path(case['root']), case['rules'])
    calls = [{'tool': 'inspect_experiment_directory', 'dispatched': True}]
    assert score(answer_dict(**change), truth, 0, calls, tmp_path)['typed_claims_pass'] == passes


def test_no_oracle_in_system_prompt():
    assert 'oracle' not in INSTRUCTION.lower()
    assert 'cheaper' not in INSTRUCTION.lower()
    assert '2 ROIs' not in INSTRUCTION




class ScriptedModel(Model):
    """Explicit protocol double. Its tool route is NOT autonomous evidence."""
    def __init__(self, root, tool):
        self.root, self.tool, self.inputs = root, tool, []

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema,
                           handoffs, tracing, **kwargs):
        self.inputs.append(input)
        assert kwargs.get('previous_response_id') is None
        assert kwargs.get('conversation_id') is None
        if len(self.inputs) == 1:
            out = [ResponseFunctionToolCall(type='function_call', name=self.tool, arguments=json.dumps({'experiment_root': self.root}), call_id='offline-call-1')]
        else:
            out = [ResponseOutputMessage(id='offline-message', type='message', role='assistant', status='completed',
                    content=[ResponseOutputText(type='output_text', text=json.dumps(answer_dict(evidence_tools=[self.tool])), annotations=[])])]
        return ModelResponse(output=out, usage=Usage(), response_id=None)

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError
        yield


@pytest.mark.parametrize('strategy', ['A', 'B'])
def test_real_sdk_runner_with_stdio(tmp_path, strategy):
    """Requires local validated config; skip honestly in unrelated environments."""
    path = os.getenv('STEP0_AGENT_TEST_CONFIG')
    if not path:
        pytest.skip('Set STEP0_AGENT_TEST_CONFIG for real SDK/stdio integration')
    c = make_fixtures(tmp_path/'fixtures')[0]
    cfg = json.loads(Path(path).read_text())
    async def run():
        tool = 'inspect_experiment_directory' if strategy == 'A' else 'run_experiment_validation'
        for repeat in range(2):
            model = ScriptedModel(c['root'], tool)
            async with ScopedServer(cfg, c, tmp_path/f'run-{repeat}', strategy) as server:
                agent = Agent(name='offline SDK test', instructions=INSTRUCTION, model=model,
                              mcp_servers=[server], output_type=Answer)
                result = await Runner.run(agent, 'How many ROIs?', max_turns=4)
                assert result.final_output.roi_count == 2
                assert len(model.inputs) == 2
                assert len(model.inputs[0]) == 1  # exactly the new user message
                assert len(server.calls) == 1
                assert server.calls[0]['tool'] == tool
                assert server.calls[0]['result']['roi_count'] == 2
    set_tracing_disabled(True)
    asyncio.run(run())


@pytest.mark.parametrize('strategy', ['A', 'B'])
def test_sdk_report_uses_one_call(tmp_path, strategy):
    """A scripted protocol double verifies one tool call, not autonomous accuracy."""
    path = os.getenv('STEP0_AGENT_TEST_CONFIG')
    if not path:
        pytest.skip('Set STEP0_AGENT_TEST_CONFIG for real SDK/stdio integration')
    c = make_fixtures(tmp_path/'fixtures')[0]
    cfg = json.loads(Path(path).read_text())
    async def run():
        tool = 'validate_ecsv_tables' if strategy == 'A' else 'run_experiment_validation'
        async with ScopedServer(cfg, c, tmp_path/'trial', strategy) as trace:
            model = ScriptedModel(c['root'], tool)
            result = await Runner.run(Agent(name='single-server report test', instructions=INSTRUCTION,
                                           model=model, mcp_servers=[trace], output_type=Answer),
                                      'Generate a Data Quality Report.', max_turns=3)
            assert len(trace.calls) == 1
            payload = trace.calls[0]['result']
            assert Path(payload['human_report_path']).is_file()
            assert Path(payload['html_report_path']).is_file()
            assert len(model.inputs) == 2
    set_tracing_disabled(True)
    asyncio.run(run())
