"""One deterministic composition versus one real stdio MCP call; no LLM/science."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import sys
import time

from mcp import Client, StdioServerParameters
from chromatin_report_mcp.workflow_report import generate, regular


async def benchmark(manifest_id,manifest_sha256,output):
    output.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter()
    direct=generate(manifest_id,manifest_sha256)
    deterministic_seconds=time.perf_counter()-start
    start=time.perf_counter()
    async with Client(StdioServerParameters(command=sys.executable,args=['-m','chromatin_report_mcp.server'],env=dict(os.environ)),read_timeout_seconds=60,raise_exceptions=False) as client:
        startup=time.perf_counter()-start
        tools=(await client.list_tools()).tools
        tool=next(t for t in tools if t.name=='generate_experiment_qc_report')
        assert tool.output_schema is not None
        args={'manifest_id':manifest_id,'manifest_sha256':manifest_sha256}
        start=time.perf_counter()
        response=await client.call_tool(tool.name,args)
        latency=time.perf_counter()-start
        assert not response.is_error, response
        result=response.structured_content
        from jsonschema import validate
        validate(result,tool.output_schema)
        error=await client.call_tool(tool.name,{'manifest_id':manifest_id,'manifest_sha256':'0'*64})
        assert error.is_error
    def normalize(text):
        return re.sub(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+\+00:00','TIMESTAMP',text)
    assert normalize(Path(direct['path']).read_text())==normalize(Path(result['path']).read_text())
    evidence=json.loads(Path(result['evidence_path']).read_text())
    roots=[Path(x) for x in os.environ['CHROMATIN_REPORT_ARTIFACT_ROOTS'].split(os.pathsep)]
    assert all(regular(Path(x['path']),roots)[0]==x['sha256'] for x in evidence['source_artifacts'])
    (output/'mcp-response.json').write_text(json.dumps(response.model_dump(mode='json'),indent=2)+'\n')
    (output/'error-response.json').write_text(json.dumps(error.model_dump(mode='json'),indent=2)+'\n')
    record={'deterministic_seconds':deterministic_seconds,'mcp_startup_seconds':startup,
        'mcp_call_seconds':latency,'server_execution_seconds':result['execution_seconds'],
        'structured_response_bytes':len(json.dumps(result,separators=(',',':'),ensure_ascii=False).encode()),
        'serialized_response_bytes':len(json.dumps(response.model_dump(mode='json'),separators=(',',':'),ensure_ascii=False).encode()),
        'generation_tool_calls':1,'negative_control_calls':1,'discovery_calls':1,
        'tools_discovered':[t.name for t in tools],'deterministic_html_equivalence_ignoring_timestamp':True,
        'all_sources_unchanged':True,'scientific_calculations_run':0,'verified_artifacts':len(evidence['source_artifacts']),
        'report':result,'direct_baseline':direct,'provider_requests':0,'provider_usage':None,'provider_model':None,
        'actual_input_tokens':None,'actual_output_tokens':None,'actual_total_tokens':None,'cost':None,
        'autonomous_agent_validation':'NOT_RUN','visual_browser_validation':'NOT_RUN_LOCAL_FILE_POLICY_BLOCK',
        'notes':['Single trial; includes filesystem hashing.','Bytes and timing are not model tokens.','No scientific equivalence rerun: source outputs are formatted without recalculation.']}
    (output/'benchmark.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:v for k,v in record.items() if k not in ['report','direct_baseline']},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest-id',required=True)
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    asyncio.run(benchmark(args.manifest_id,args.manifest_sha256,args.output))
