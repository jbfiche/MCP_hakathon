"""One direct/native vs real stdio trial; requires existing human ROI approval."""
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
from chromatin_trace_mcp import approval as a, localization_merge as lm, pearsons as p
from chromatin_trace_mcp.collection import digest


async def benchmark(options):
    refs=[p.CollectionReference.model_validate(r) for r in json.loads(options.collections_json.read_text())]
    review=a.prepare_review(options.pearson_run_id,options.results_sha256)
    parameters=review.evidence['binding']['parameters'] if review.evidence else {}
    grant=a.require_scientific_approval(options.pearson_run_id,options.results_sha256,options.indices,parameters)
    mapped,roots=lm.associations(grant,refs);lm.read_selected(mapped)
    output=options.output.resolve()
    if any(output==root or output.is_relative_to(root) for root in roots|{p.collection_root().resolve(),a.pearson_root().resolve()}):
        raise ValueError('Benchmark output must be outside input/evidence stores')
    protected=[]
    for item in mapped:
        protected += [Path(item['source']),p.collection_root()/item['collection_run_id']/item['filename']]
    for ref in refs+[p.CollectionReference.model_validate(r) for r in grant['evidence']['collection_references']]:
        manifest=p.collection_root()/ref.collection_run_id/'manifest.json';protected.append(manifest)
        protected += [Path(f['source']) for f in json.loads(manifest.read_text())['files']]
        protected += [Path(f['destination']) for f in json.loads(manifest.read_text())['files']]
    protected += [f for f in (a.pearson_root()/options.pearson_run_id).iterdir() if f.is_file()]
    protected.append(a.pearson_root()/'.scientific-approvals'/f'{options.pearson_run_id}.json')
    before={str(f):digest(f) for f in protected}
    output.mkdir(parents=True,exist_ok=False)
    paths=[str(p.collection_root()/f['collection_run_id']/f['filename']) for f in mapped]
    console=io.StringIO();start=time.perf_counter()
    with contextlib.redirect_stdout(console),contextlib.redirect_stderr(console):
        lm.native.run({'loc_files':paths,'outputFolder':str(output),'output_file':'direct.ecsv'})
    native_seconds=time.perf_counter()-start;(output/'direct.log').write_text(console.getvalue())
    env=dict(os.environ);env[lm.OUTPUT_ENV]=str(output/'mcp')
    server=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=env)
    start=time.perf_counter()
    async with Client(server,read_timeout_seconds=120) as client:
        startup=time.perf_counter()-start
        assert 'localization_merge' in {t.name for t in (await client.list_tools()).tools}
        start=time.perf_counter()
        response=await client.call_tool('localization_merge',{'pearson_run_id':options.pearson_run_id,'results_sha256':options.results_sha256,
              'selected_dataset_indices':options.indices,'localization_collections':[r.model_dump() for r in refs]})
        latency=time.perf_counter()-start
    result=response.structured_content
    (output/'mcp-response.json').write_text(json.dumps(response.model_dump(mode='json'),indent=2))
    assert result['status']=='MERGED',result
    assert (output/'direct.ecsv').read_bytes()==Path(result['merged_path']).read_bytes()
    assert before=={name:digest(Path(name)) for name in before}
    detail=json.loads(Path(result['provenance_path']).read_text())
    record={'native_seconds':native_seconds,'mcp_call_seconds':latency,'mcp_startup_seconds':startup,
       'mcp_server_execution_seconds':result['execution_seconds'],'mcp_tool_calls':1,'discovery_calls':1,
       'structured_response_bytes':result['structured_response_bytes'],
       'serialized_mcp_response_bytes':len(json.dumps(response.model_dump(mode='json'),separators=(',',':'),ensure_ascii=False).encode()),
       'row_count':result['row_count'],'barcode_count':result['barcode_count'],'roi_count':result['roi_count'],
       'localization_id_count':result['localization_id_count'],'source_file_count':result['source_file_count'],
       'native_ecsv_byte_equivalence':True,'protected_inputs_and_approval_unchanged':True,'protected_sha256':before,
       'approval_revision':grant['revision'],'approval_source':grant['decision_source'],
       'selected_dataset_indices':options.indices,'source_roi_mapping':[{k:f[k] for k in ['experiment_root','roi','source_relative']} for f in mapped],
       'merged_path':result['merged_path'],'provenance_path':result['provenance_path'],'warnings':detail['warnings'],
       'provider_requests':0,'provider_model':None,'provider_input_tokens':None,'provider_output_tokens':None,
       'provider_total_tokens':None,'provider_cached_tokens':None,'provider_reasoning_tokens':None,'cost':None,
       'autonomous_agent_validation':'PENDING_NOT_RUN',
       'notes':['One trial per mode, not a performance distribution.','Native timing excludes wrapper checks, snapshots and provenance.',
                'No LLM was invoked. Response bytes are not provider tokens.']}
    (output/'benchmark.json').write_text(json.dumps(record,indent=2))
    print(json.dumps({k:v for k,v in record.items() if k!='protected_sha256'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pearson-run-id',required=True);parser.add_argument('--results-sha256',required=True)
    parser.add_argument('--indices',type=int,nargs='+',required=True);parser.add_argument('--collections-json',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(benchmark(parser.parse_args()))
