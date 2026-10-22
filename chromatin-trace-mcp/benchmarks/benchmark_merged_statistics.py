"""Direct native vs one checked stdio statistics call; never creates approval."""
import argparse
import asyncio
import contextlib
import io
import json
import os
import re
import sys
import time
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from chromatin_trace_mcp import approval as a, merged_statistics as ms, pearsons as p, trace_statistics as adapter
from chromatin_trace_mcp.collection import digest


async def benchmark(options):
    value, _, _ = ms.read_merge(options.trace_merge_run_id,options.merged_sha256,options.provenance_sha256)
    grant, roots, _ = ms.verify_approval(value)
    output = options.output.resolve()
    if any(output==root or output.is_relative_to(root) for root in roots|{ms.merge_root().resolve(),p.collection_root().resolve(),a.pearson_root().resolve()}):
        raise ValueError('Benchmark output must be outside inputs and evidence stores')
    protected = list((ms.merge_root()/options.trace_merge_run_id).iterdir())
    for ref in grant['evidence']['collection_references']:
        manifest=p.collection_root()/ref['collection_run_id']/'manifest.json';protected.append(manifest)
        data=json.loads(manifest.read_text())
        protected += [Path(item['source']) for item in data['files']]+[Path(item['destination']) for item in data['files']]
    protected += [file for file in (a.pearson_root()/value['pearson_run_id']).iterdir() if file.is_file()]
    protected.append(a.pearson_root()/'.scientific-approvals'/f'{value["pearson_run_id"]}.json')
    before={str(file):digest(file) for file in protected if file.is_file()}
    output.mkdir(parents=True,exist_ok=False)
    source=ms.merge_root()/options.trace_merge_run_id/'merged_traces.ecsv';console=io.StringIO();start=time.perf_counter()
    with contextlib.redirect_stdout(console):adapter.native.compute_trace_statistics(source)
    native_seconds=time.perf_counter()-start
    native_text=console.getvalue();(output/'direct-native.txt').write_text(native_text)
    expected={k:int(re.search(r'Number of '+label+r':\s*(\d+)',native_text)[1]) for k,label in
        [('unique_roi_count','unique ROIs'),('global_unique_trace_id_count','unique chromatin traces'),('unique_barcode_count','unique barcodes')]}
    env=dict(os.environ);env[ms.OUTPUT_ENV]=str(output/'mcp')
    params=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=env)
    start=time.perf_counter()
    async with Client(params,read_timeout_seconds=120) as client:
        startup=time.perf_counter()-start
        assert 'merged_trace_stats' in {tool.name for tool in (await client.list_tools()).tools}
        start=time.perf_counter()
        response=await client.call_tool('merged_trace_stats',{'trace_merge_run_id':options.trace_merge_run_id,
            'merged_sha256':options.merged_sha256,'provenance_sha256':options.provenance_sha256})
        elapsed=time.perf_counter()-start
    result=response.structured_content
    (output/'mcp-response.json').write_text(json.dumps(response.model_dump(mode='json'),indent=2))
    assert result['status']=='COMPUTED',result
    assert {key:result[key] for key in expected}==expected
    assert result['roi_trace_count']==value['roi_trace_count'] and result['row_count']==value['row_count']
    assert before=={name:digest(Path(name)) for name in before}
    record={'direct_native_seconds':native_seconds,'mcp_call_seconds':elapsed,'mcp_startup_seconds':startup,
        'server_execution_seconds':result['execution_seconds'],'mcp_tool_calls':1,'discovery_calls':1,
        'structured_response_bytes':result['structured_response_bytes'],
        'serialized_mcp_response_bytes':len(json.dumps(response.model_dump(mode='json'),separators=(',',':'),ensure_ascii=False).encode()),
        'native_counts':expected,'roi_trace_count':result['roi_trace_count'],'row_count':result['row_count'],
        'native_equivalence':True,'protected_inputs_and_merge_approval_unchanged':True,'protected_sha256':before,
        'trace_merge_run_id':options.trace_merge_run_id,'merged_sha256':options.merged_sha256,'provenance_sha256':options.provenance_sha256,
        'approval_revision':grant['revision'],'approval_source':grant['decision_source'],
        'evidence_path':result['evidence_path'],'evidence_sha256':result['evidence_sha256'],'baseline_fingerprint':result['baseline_fingerprint'],
        'provider_requests':0,'provider_model':None,'provider_input_tokens':None,'provider_output_tokens':None,
        'provider_total_tokens':None,'provider_cached_tokens':None,'provider_reasoning_tokens':None,'provider_cost':None,
        'autonomous_agent_validation':'PENDING_NOT_RUN',
        'notes':['One trial per mode, not a performance distribution.',
        'Native timing omits provenance/approval checks, snapshots, source-contribution verification and evidence writing.',
        'No LLM invoked. Response bytes are not provider tokens.']}
    (output/'benchmark.json').write_text(json.dumps(record,indent=2))
    print(json.dumps({k:v for k,v in record.items() if k!='protected_sha256'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace-merge-run-id',required=True);parser.add_argument('--merged-sha256',required=True)
    parser.add_argument('--provenance-sha256',required=True);parser.add_argument('--output',type=Path,required=True)
    asyncio.run(benchmark(parser.parse_args()))
