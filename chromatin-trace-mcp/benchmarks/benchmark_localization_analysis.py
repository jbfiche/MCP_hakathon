"""Real native-vs-MCP localization QC; requires existing exact human approval."""
import argparse,asyncio,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
import numpy as np
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from chromatin_trace_mcp import localization_analysis as la,approval as a,pearsons as p
from chromatin_trace_mcp.collection import digest

DIRECT='''
import json,numpy as np
from matplotlib.axes import Axes
from traceratops import localization_analyzer as native
calls=[];arrays={}
for name in ['violinplot','scatter','bar']:
 original=getattr(Axes,name)
 def wrap(name,original):
  def call(self,*args,**kwargs):
   entry={'method':name}
   values={'positions':kwargs['positions'],**{f'snr_{i}':a for i,a in enumerate(args[0])}} if name=='violinplot' else {'x':args[0],'y':args[1]}
   if name=='scatter':values['c']=kwargs['c']
   for key,value in values.items():
    label=str(len(arrays));arrays[label]=np.asarray(value);entry[key]=label
   result=original(self,*args,**kwargs);calls.append(entry);return result
  return call
 setattr(Axes,name,wrap(name,original))
native.run({'localization_file':'localizations.ecsv','output_file':'localization_distribution_fluxes.png','format':'png'})
np.savez_compressed('direct-arrays.npz',**arrays)
open('direct-calls.json','w').write(json.dumps(calls))
'''

async def benchmark(options):
    doc,data,log_sha,grant,mapped,roots=la.context(options.merge_run_id,options.merged_sha256,options.provenance_sha256)
    destination=options.output.resolve()
    forbidden=roots|{la.merge_root().resolve(),p.collection_root().resolve(),a.pearson_root().resolve(),la.output_root(roots)}
    if any(destination==root or destination.is_relative_to(root) for root in forbidden):raise ValueError('Unsafe benchmark output directory')
    destination.mkdir(parents=True,exist_ok=False)
    protected=[]
    for ref in grant['selected_collection_references']+doc['localization_collections']:
        manifest=p.collection_root()/ref['collection_run_id']/'manifest.json';protected.append(manifest)
        for item in json.loads(manifest.read_text())['files']:protected += [Path(item['source']),Path(item['destination'])]
    protected += list((la.merge_root()/options.merge_run_id).iterdir())+list((a.pearson_root()/doc['pearson_run_id']).iterdir())
    protected += [a.pearson_root()/'.scientific-approvals'/f"{doc['pearson_run_id']}.json"]
    before={str(f):digest(f) for f in protected if f.is_file()}
    native=destination/'direct-native';native.mkdir();source=native/'localizations.ecsv';source.write_bytes(data);source.chmod(0o400)
    start=time.perf_counter();process=subprocess.run([sys.executable,'-c',DIRECT],cwd=native,env=dict(os.environ),capture_output=True,text=True,timeout=300)
    native_seconds=time.perf_counter()-start
    (native/'stdout.log').write_text(process.stdout);(native/'stderr.log').write_text(process.stderr)
    if process.returncode:raise RuntimeError('Direct native analysis failed: '+process.stderr[-1000:])
    source.unlink() # Private duplicate scientific input, not an original artifact.
    args={'localization_merge_run_id':options.merge_run_id,'merged_sha256':options.merged_sha256,'provenance_sha256':options.provenance_sha256}
    if options.annotation_run_id:args.update(annotation_run_id=options.annotation_run_id,annotation_sha256=options.annotation_sha256)
    start=time.perf_counter()
    async with Client(StdioServerParameters(command=sys.executable,args=['-m','chromatin_trace_mcp.server'],env=dict(os.environ)),read_timeout_seconds=360) as client:
        startup=time.perf_counter()-start
        tools=(await client.list_tools()).tools
        assert sum(t.name=='localization_analyzer' for t in tools)==1
        start=time.perf_counter();reply=await client.call_tool('localization_analyzer',args);elapsed=time.perf_counter()-start
    (destination/'mcp-response.json').write_text(json.dumps(reply.model_dump(mode='json'),indent=2))
    result=reply.structured_content
    if reply.is_error or not result or result['status']!='ANALYZED':raise RuntimeError(result or reply.model_dump(mode='json'))
    output=Path(result['output_directory']);numeric=json.loads((output/'numerical_outputs.json').read_text());direct=json.loads((native/'direct-calls.json').read_text())
    assert digest(Path(result['output_file']))==digest(native/'localization_distribution_fluxes.png')
    with np.load(output/'numerical_outputs.npz',allow_pickle=False) as actual,np.load(native/'direct-arrays.npz',allow_pickle=False) as expected:
        assert len(numeric['plot_calls'])==len(direct)==4
        for ours,theirs in zip(numeric['plot_calls'],direct):
            assert ours['method']==theirs['method']
            if ours['method']=='violinplot':
                np.testing.assert_equal(actual[ours['positions']],expected[theirs['positions']])
                for i,key in enumerate(ours['datasets']):np.testing.assert_equal(actual[key],expected[theirs[f'snr_{i}']])
            elif ours['method']=='bar':
                np.testing.assert_equal(actual[ours['positions']],expected[theirs['x']]);np.testing.assert_equal(actual[ours['counts']],expected[theirs['y']])
            else:
                for key,direct_key in [('x','x'),('y','y'),('color','c')]:np.testing.assert_equal(actual[ours[key]],expected[theirs[direct_key]])
    manifest=json.loads(Path(result['artifact_manifest_path']).read_text());assert all(digest(output/v['name'])==v['sha256'] for v in manifest)
    assert before=={name:digest(Path(name)) for name in before}
    record={'input_scope':'existing-approved-merged-localization-experiment','approval_source':grant['decision_source'],'approved_selection':grant['selected_dataset_indices'],
        'localization_merge_run_id':options.merge_run_id,'merged_sha256':options.merged_sha256,'provenance_sha256':options.provenance_sha256,
        'direct_native_seconds':native_seconds,'mcp_startup_seconds':startup,'mcp_call_seconds':elapsed,'server_execution_seconds':result['execution_seconds'],
        'mcp_tool_calls':1,'discovery_calls':1,'structured_response_bytes':result['structured_response_bytes'],
        'serialized_response_bytes':len(json.dumps(reply.model_dump(mode='json'),separators=(',',':'),ensure_ascii=False).encode()),
        'native_figure_byte_identical':True,'all_native_plot_input_arrays_exact':True,'native_barcode_counts':numeric['native_barcode_counts'],
        'input_barcodes_unchanged':True,'protected_sources_and_approval_unchanged':True,'protected_sha256':before,
        'evidence_path':result['evidence_path'],'evidence_sha256':result['evidence_sha256'],'output_directory':result['output_directory'],
        'row_count':result['row_count'],'barcode_count':result['unique_barcode_count'],'roi_count':result['roi_count'],
        'provider_requests':0,'provider_model':None,'provider_input_tokens':None,'provider_output_tokens':None,'provider_total_tokens':None,'provider_cached_tokens':None,'provider_reasoning_tokens':None,'cost':None,
        'autonomous_agent_validation':'PENDING_NOT_RUN','notes':['One trial per mode, not a performance distribution.','Native duration includes separate interpreter startup.','Bytes are not actual model tokens.']}
    (destination/'benchmark.json').write_text(json.dumps(record,indent=2));print(json.dumps({k:v for k,v in record.items() if k not in ['protected_sha256','native_barcode_counts']},indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--merge-run-id',required=True);parser.add_argument('--merged-sha256',required=True);parser.add_argument('--provenance-sha256',required=True)
    parser.add_argument('--annotation-run-id');parser.add_argument('--annotation-sha256');parser.add_argument('--output',type=Path,required=True)
    asyncio.run(benchmark(parser.parse_args()))
