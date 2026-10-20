"""One deterministic native-vs-real-stdio comparison. No LLM/token estimates."""
import argparse
import asyncio
import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from chromatin_trace_mcp import pearsons as p
from chromatin_trace_mcp.collection import digest


async def run(refs, output):
    output.mkdir(parents=True, exist_ok=False)
    files=[];protected=[]
    for ref in refs:
        manifest=p.collection_root()/ref['collection_run_id']/'manifest.json'
        if digest(manifest)!=ref['manifest_sha256']: raise ValueError('Wrong manifest hash')
        protected.append(manifest)
        for item in json.loads(manifest.read_text())['files']:
            files.append(Path(item['destination']));protected.append(Path(item['source']))
    protected+=files
    before={str(f):digest(f) for f in protected}
    maps={};console=io.StringIO()
    start=time.perf_counter()
    with contextlib.redirect_stdout(console),contextlib.redirect_stderr(console):
        for f in files:
            trace=p.native.ChromatinTraceTable();p.native.silent_load_trace(trace,str(f))
            maps[str(f)]=p.native.accumulate_distances(trace.data)
        labels,expected=p.native.compare_distance_maps(maps)
        p.native.plot_correlation_matrix(labels,expected,output_filename=str(output/'direct.png'))
    native_seconds=time.perf_counter()-start
    (output/'direct.log').write_text(console.getvalue())
    env=dict(os.environ);env[p.OUTPUT_ENV]=str(output/'mcp')
    params=StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=env)
    start=time.perf_counter()
    async with Client(params,read_timeout_seconds=300) as client:
        startup=time.perf_counter()-start
        tools=[t.name for t in (await client.list_tools()).tools]
        assert 'trace_pearsons' in tools
        start=time.perf_counter()
        response=await client.call_tool('trace_pearsons',{'collections':refs})
        elapsed=time.perf_counter()-start
    result=response.structured_content
    (output/'mcp_response.json').write_text(json.dumps(response.model_dump(mode='json'),indent=2))
    if result['status']!='COMPUTED': raise AssertionError(result)
    actual=np.load(result['matrix_path'],allow_pickle=False)
    np.testing.assert_array_equal(actual,expected)
    detail=json.loads(Path(result['results_path']).read_text())
    for i,label in enumerate(labels):
        assert detail['distance_maps'][i]['pairs']==[{'barcodes':[int(k[0]),int(k[1])],'median_distance':p.json_number(v)} for k,v in sorted(maps[label].items())]
    assert (output/'direct.png').read_bytes()==Path(result['figure_path']).read_bytes()
    assert before=={str(f):digest(f) for f in protected}
    record={'native_seconds':native_seconds,'mcp_startup_seconds':startup,'mcp_call_seconds':elapsed,
            'mcp_server_execution_seconds':result['execution_seconds'],'mcp_tool_calls':1,'discovery_calls':1,
            'mcp_structured_response_bytes':result['structured_response_bytes'],
            'mcp_serialized_response_bytes':len(json.dumps(response.model_dump(mode='json'),separators=(',',':'),ensure_ascii=False).encode()),
            'datasets':len(files),'comparisons':result['comparisons'],
            'native_matrix_exact':True,'native_distance_maps_exact':True,'native_png_exact':True,
            'protected_files_unchanged':True,'protected_sha256':before,'collection_references':refs,
            'model_identifier':None,'provider_input_tokens':None,'provider_output_tokens':None,
            'provider_total_tokens':None,'provider_cached_tokens':None,'provider_reasoning_tokens':None,
            'cost':None,'autonomous_agent_validation':'PENDING_NOT_RUN','live_provider_requests':0,
            'notes':['One real-experiment trial per mode, not a statistical performance claim.',
                     'Native baseline omits snapshotting, validation, provenance and report formatting.',
                     'No model was invoked. Response bytes are not token measurements.'],
            'report_path':result['report_path'],'results_path':result['results_path']}
    (output/'benchmark.json').write_text(json.dumps(record,indent=2,allow_nan=False))
    print(json.dumps({k:v for k,v in record.items() if k not in {'protected_sha256','collection_references'}},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--references',required=True,type=Path,help='JSON list of collection_run_id/manifest_sha256 objects')
    parser.add_argument('--output',required=True,type=Path,help='New directory outside original inputs and collection store')
    args=parser.parse_args()
    collection_store=p.collection_root().resolve();out=args.output.resolve()
    refs=[p.CollectionReference.model_validate(r).model_dump() for r in json.loads(args.references.read_text())]
    # Reject unsafe benchmark destinations before baseline writes anything.
    original_roots=[Path(json.loads((collection_store/r['collection_run_id']/'manifest.json').read_text())['experiment_root']).resolve() for r in refs]
    if any(out==r or out.is_relative_to(r) for r in [collection_store,*original_roots]):
        raise ValueError('Benchmark output must be outside all scientific inputs')
    asyncio.run(run(refs,out))
