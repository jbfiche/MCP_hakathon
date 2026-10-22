"""Direct native vs checked MCP trace analyzer; requires existing scientific approval."""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from astropy.table import Table
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from chromatin_trace_mcp import tracing_analysis as ta, approval as a, pearsons as p
from chromatin_trace_mcp.collection import digest

DIRECT="""
import numpy as np,json
from traceratops import trace_analyzer as native
np.random.seed(0)
output={};neighbor=native.plot_neighbor_distances
barcode=native.ChromatinTraceTable.barcode_statistics
def capture_neighbor(*args,**kwargs):
 value=neighbor(*args,**kwargs);output['neighbor']=list(map(float,value));return value
native.plot_neighbor_distances=capture_neighbor
def capture_barcode(self,*args,**kwargs):
 value=barcode(self,*args,**kwargs);output['barcode']=value;return value
native.ChromatinTraceTable.barcode_statistics=capture_barcode
native.process_traces({'trace_files':['trace.ecsv'],'plotXYZ':False,'format':'png','neighbor_distance_range':'auto'})
open('returned.json','w').write(json.dumps(output))
"""


async def benchmark(options):
    baseline,value,data,grant,roots,sources,_=ta.load_context(options.baseline_run_id,options.baseline_sha256)
    # Parent preflight uses a private read-only copy, never repairs metadata.
    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        file=Path(temporary)/'trace.ecsv';file.write_bytes(data)
        ta.validate_analysis_input(Table.read(file,format='ascii.ecsv'));ta.verify_source_units(value)
    output=options.output.resolve()
    forbidden=roots|{ta.baseline_root().resolve(),ta.ms.merge_root().resolve(),p.collection_root().resolve(),a.pearson_root().resolve()}
    if any(output==root or output.is_relative_to(root) for root in forbidden):raise ValueError('Unsafe benchmark output')
    protected=list((ta.baseline_root()/options.baseline_run_id).iterdir())
    protected+=list((ta.ms.merge_root()/baseline['trace_merge_run_id']).iterdir())
    for ref in grant['evidence']['collection_references']:
        path=p.collection_root()/ref['collection_run_id']/'manifest.json';protected.append(path)
        manifest=json.loads(path.read_text());protected += [Path(item[k]) for item in manifest['files'] for k in ['source','destination']]
    protected+=list((a.pearson_root()/value['pearson_run_id']).iterdir())
    protected.append(a.pearson_root()/'.scientific-approvals'/f'{value["pearson_run_id"]}.json')
    before={str(path):digest(path) for path in protected if path.is_file()}
    output.mkdir(parents=True,exist_ok=False);direct=output/'native';direct.mkdir();(direct/'trace.ecsv').write_bytes(data)
    start=time.perf_counter()
    run=subprocess.run([sys.executable,'-c',DIRECT],cwd=direct,capture_output=True,text=True,timeout=300)
    native_seconds=time.perf_counter()-start
    (direct/'stdout.log').write_text(run.stdout);(direct/'stderr.log').write_text(run.stderr)
    assert run.returncode==0,run.stderr[-1000:]
    expected=json.loads((direct/'returned.json').read_text())
    env=dict(os.environ);env[ta.OUTPUT_ENV]=str(output/'mcp');start=time.perf_counter()
    async with Client(StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=env),read_timeout_seconds=360) as client:
        startup=time.perf_counter()-start;start=time.perf_counter()
        response=await client.call_tool('trace_analyzer',{'baseline_run_id':options.baseline_run_id,'baseline_sha256':options.baseline_sha256,'neighbor_distance_range':'auto'})
        elapsed=time.perf_counter()-start
    result=response.structured_content;(output/'mcp-response.json').write_text(json.dumps(response.model_dump(mode='json'),indent=2))
    assert result['status']=='ANALYZED',result
    actual=result['neighbor_statistics'];assert [actual[k] for k in ['mean_dx','mean_dy','mean_dz','std_dx','std_dy','std_dz']]==expected['neighbor']
    folder=Path(result['output_directory'])
    assert all((folder/(stem+'.png')).read_bytes()==(direct/(stem+'.png')).read_bytes() for stem in ta.FIGURES)
    metadata=json.loads((folder/'numerical_outputs.json').read_text())
    with np.load(folder/'numerical_outputs.npz',allow_pickle=False) as arrays:
        assert {k:arrays[v].tolist() for k,v in metadata['returned_values']['barcode_multiplicities'].items()}==expected['barcode']
    assert before=={name:digest(Path(name)) for name in before}
    record={'input_scope':options.input_scope,'native_seconds':native_seconds,'mcp_call_seconds':elapsed,
        'mcp_startup_seconds':startup,'server_execution_seconds':result['execution_seconds'],'mcp_tool_calls':1,
        'structured_response_bytes':result['structured_response_bytes'],
        'serialized_mcp_result_bytes':len(json.dumps(response.model_dump(mode='json'),separators=(',',':'),ensure_ascii=False).encode()),
        'native_neighbor_statistics':result['neighbor_statistics'],'native_numerical_equivalence':True,'five_native_pngs_byte_identical':True,
        'protected_source_and_evidence_unchanged':True,'protected_sha256':before,'evidence_path':result['evidence_path'],
        'approval_kind':options.approval_kind,'provider_requests':0,'provider_model':None,'provider_input_tokens':None,
        'provider_output_tokens':None,'provider_total_tokens':None,'provider_cached_tokens':None,'provider_reasoning_tokens':None,
        'provider_cost':None,'autonomous_agent_validation':'PENDING_NOT_RUN',
        'notes':['One trial per mode, not a performance distribution.','Native timing includes its isolated Python startup.',
                 'MCP timing includes checked evidence, isolated native worker, numerical capture and artifact publication.',
                 'Provider tokens are not measured or estimated from bytes.']}
    (output/'benchmark.json').write_text(json.dumps(record,indent=2));print(json.dumps({k:v for k,v in record.items() if k!='protected_sha256'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-run-id',required=True);parser.add_argument('--baseline-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--input-scope',default='user-provided-approved-experiment')
    parser.add_argument('--approval-kind',default='existing-human-approval')
    asyncio.run(benchmark(parser.parse_args()))
