"""Direct native vs real MCP merge using an EXISTING approval. Never creates approval."""
import argparse
import asyncio
import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from chromatin_trace_mcp import approval as a, merge as m, pearsons as p
from chromatin_trace_mcp.collection import digest


async def benchmark(options):
    context=a.prepare_review(options.pearson_run_id,options.results_sha256)
    parameters=context.evidence['binding']['parameters'] if context.evidence else {}
    grant=a.require_scientific_approval(options.pearson_run_id,options.results_sha256,options.indices,parameters)
    forbidden=[p.collection_root().resolve(),a.pearson_root().resolve()]
    protected=[Path(f['path']) for f in grant['evidence']['datasets']]
    for ref in grant['evidence']['collection_references']:
        manifest=p.collection_root()/ref['collection_run_id']/'manifest.json';protected.append(manifest)
        metadata=json.loads(manifest.read_text());forbidden.append(Path(metadata['experiment_root']).resolve())
        protected.extend(Path(item['source']) for item in metadata['files'])
    pearson=a.pearson_root()/options.pearson_run_id
    protected.extend(file for file in pearson.iterdir() if file.is_file())
    protected.append(a.pearson_root()/'.scientific-approvals'/f'{options.pearson_run_id}.json')
    output=options.output.resolve()
    if any(output==root or output.is_relative_to(root) for root in forbidden):
        raise ValueError('Benchmark output must be outside inputs, collection and Pearson stores')
    before={str(file):digest(file) for file in protected}
    output.mkdir(parents=True,exist_ok=False)
    console=io.StringIO();start=time.perf_counter()
    with contextlib.redirect_stdout(console),contextlib.redirect_stderr(console):
        traces=m.native.load_traces([f['path'] for f in grant['selected_datasets']],verbose=False)
        traces.save(str(output/'direct.ecsv'),comments='appended_trace_files='+str(traces.number_traces))
    native_seconds=time.perf_counter()-start
    (output/'direct.log').write_text(console.getvalue())
    env=dict(os.environ);env[m.OUTPUT_ENV]=str(output/'mcp')
    server=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=env)
    start=time.perf_counter()
    async with Client(server,read_timeout_seconds=120) as client:
        startup=time.perf_counter()-start
        assert 'trace_merge' in {t.name for t in (await client.list_tools()).tools}
        start=time.perf_counter()
        response=await client.call_tool('trace_merge',{'pearson_run_id':options.pearson_run_id,'results_sha256':options.results_sha256,'selected_dataset_indices':options.indices})
        latency=time.perf_counter()-start
    result=response.structured_content
    (output/'mcp-response.json').write_text(json.dumps(response.model_dump(mode='json'),indent=2))
    if result['status']!='MERGED': raise AssertionError(result)
    assert (output/'direct.ecsv').read_bytes()==Path(result['merged_path']).read_bytes()
    assert all(digest(Path(path))==h for path,h in before.items())
    detail=json.loads(Path(result['provenance_path']).read_text())
    assert result['row_count']==sum(s['rows'] for s in grant['selected_datasets'])
    record={'native_seconds':native_seconds,'mcp_call_seconds':latency,'mcp_startup_seconds':startup,
        'mcp_server_execution_seconds':result['execution_seconds'],'mcp_tool_calls':1,'discovery_calls':1,
        'structured_response_bytes':result['structured_response_bytes'],
        'serialized_mcp_response_bytes':len(json.dumps(response.model_dump(mode='json'),separators=(',',':'),ensure_ascii=False).encode()),
        'row_count':result['row_count'],'barcode_count':result['barcode_count'],'trace_count':result['trace_count'],
        'roi_trace_count':result['roi_trace_count'],'roi_count':result['roi_count'],
        'selected_dataset_indices':options.indices,'approval_revision':grant['revision'],
        'approval_source':grant['decision_source'],'native_ecsv_byte_equivalence':True,
        'inputs_and_approval_record_unchanged':True,'protected_sha256':before,
        'provider_model':None,'provider_input_tokens':None,'provider_output_tokens':None,'provider_total_tokens':None,
        'provider_cached_tokens':None,'provider_reasoning_tokens':None,'provider_requests':0,
        'autonomous_agent_validation':'PENDING_NOT_RUN','cost':None,
        'api_key_configured_in_environment':bool(os.environ.get('OPENAI_API_KEY')),
        'notes':['One trial per mode, not a performance distribution.',
                 'Native baseline excludes wrapper approval, snapshots, validation and provenance work.',
                 'No LLM was invoked. Response bytes are not provider tokens.'],
        'warnings':detail['warnings'],'merged_path':result['merged_path'],'provenance_path':result['provenance_path']}
    (output/'benchmark.json').write_text(json.dumps(record,indent=2))
    print(json.dumps({k:v for k,v in record.items() if k!='protected_sha256'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pearson-run-id',required=True)
    parser.add_argument('--results-sha256',required=True)
    parser.add_argument('--indices',type=int,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(benchmark(parser.parse_args()))
