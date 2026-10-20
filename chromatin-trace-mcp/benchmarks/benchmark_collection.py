"""Direct/native vs real MCP vs SDK orchestration; live usage is never estimated."""
import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def fingerprints(root):
    values={}
    for parent, dirs, names in os.walk(root, followlinks=False):
        if any(n in {'full_pwd','PWD_comparison'} or (Path(parent)/n).is_symlink() for n in dirs):
            raise ValueError('Benchmark requires narrow regular ECSV copies, not excluded trees or links')
        for name in names:
            path=Path(parent)/name
            if path.is_symlink():
                raise ValueError('Benchmark inputs must not contain links')
            if path.suffix=='.ecsv': values[str(path.relative_to(root))]=sha(path)
    return values


def save(path, data): path.write_text(json.dumps(data, indent=2)+'\n')


async def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--live', action='store_true')
    p.add_argument('--model')
    p.add_argument('--trials', type=int, default=3)
    a=p.parse_args()
    if not 2<=a.trials<=5: p.error('Use 2 to 5 trials')
    if a.live and (not a.model or not os.getenv('OPENAI_API_KEY')):
        p.error('--live requires a privately configured OPENAI_API_KEY and explicit --model')
    os.umask(0o077)
    config=json.loads(a.config.read_text())
    root=Path(config['experiment_root']).resolve()
    out=a.output.resolve()
    if out==root or out.is_relative_to(root): p.error('Output must be outside inputs')
    out.mkdir(parents=True, exist_ok=False)
    # Fixture inputs are narrow collection-only ECSV copies; never image/PWD trees.
    before=fingerprints(root)
    env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','SYSTEMROOT')}
    env.update(config['server_env'])
    for key in list(env):
        if any(word in key.upper() for word in ('KEY','TOKEN','SECRET','PASSWORD')): del env[key]
    env.update(CHROMATIN_EXPERIMENT_ROOTS=str(root),PYTHONDONTWRITEBYTECODE='1',MPLBACKEND='Agg',MPLCONFIGDIR=str(out/'mpl'))
    from agents import Agent, Runner, Model, ModelResponse, set_tracing_disabled
    from agents.mcp import MCPServerStdio
    from agents.usage import Usage
    from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
    from pydantic import BaseModel
    sys.path.insert(0,str(Path(__file__).parent/'agent_step0'))
    from benchmark_agent import MeasuredModel, usage_total
    set_tracing_disabled(True)

    class Answer(BaseModel):
        file_count: int
        total_rows: int
        manifest_path: str

    class ScopedCollection(MCPServerStdio):
        def __init__(self, destination):
            self.calls=[]
            super().__init__(params={'command':config['server_command'], 'args':['-m','chromatin_trace_mcp.server'],
                                     'cwd':config['server_cwd'], 'env':dict(env,CHROMATIN_COLLECTION_OUTPUT_DIR=str(destination))},
                             use_structured_content=True,client_session_timeout_seconds=30,cache_tools_list=True)
        async def list_tools(self,*args,**kwargs):
            tools=await super().list_tools(*args,**kwargs)
            selected=[t for t in tools if t.name=='collect_files']
            if len(selected)!=1: raise RuntimeError('Collection tool is missing')
            return selected
        async def call_tool(self,name,arguments,meta=None):
            if name!='collect_files' or len(self.calls)>=3 or Path(arguments.get('experiment_root','/')).resolve()!=root:
                raise PermissionError('Collection benchmark scope/budget violation')
            start=time.perf_counter()
            result=await super().call_tool(name,arguments,meta)
            self.calls.append({'tool':name,'arguments':arguments,'seconds':time.perf_counter()-start,
                               'response_bytes':len(json.dumps(result.model_dump(mode='json',by_alias=True),separators=(',',':')).encode()),
                               'result':result.structured_content})
            return result

    class ScriptedCollection(Model):
        """SDK protocol double only: never counted as a live autonomous run."""
        def __init__(self,server):self.server=server;self.turn=0
        async def get_response(self,*args,**kwargs):
            self.turn+=1
            if self.turn==1:
                outputs=[ResponseFunctionToolCall(type='function_call',name='collect_files',arguments=json.dumps(config['arguments']),call_id='offline-collection')]
            else:
                r=self.server.calls[-1]['result']
                text=json.dumps({k:r[k] for k in ('file_count','total_rows','manifest_path')})
                outputs=[ResponseOutputMessage(id='offline-final',type='message',role='assistant',status='completed',
                           content=[ResponseOutputText(type='output_text',text=text,annotations=[])])]
            return ModelResponse(output=outputs,usage=Usage(),response_id=None)
        async def stream_response(self,*a,**kw):
            raise NotImplementedError
            yield

    args=config['arguments']
    direct_code='''import json,sys,time,contextlib,io,hashlib
from pathlib import Path
from astropy.table import Table
from traceratops.collect_files import collect_files
a=json.load(sys.stdin);start=time.perf_counter()
with contextlib.redirect_stdout(io.StringIO()):
 files=collect_files(Path(a['experiment_root']),a['example_file'],Path(a['destination']),a.get('variable_part'),False,a.get('rename',False))
elapsed=time.perf_counter()-start
print(json.dumps({'execution_seconds':elapsed,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'total_rows':sum(len(Table.read(p,format='ascii.ecsv')) for p in files)}))
'''
    records=[]
    try:
        for repeat in range(a.trials):
            start=time.perf_counter()
            proc=subprocess.run([config['server_command'],'-c',direct_code],input=json.dumps(args|{'destination':str(out/f'direct-{repeat}')}),
                                text=True,capture_output=True,check=True,cwd=config['server_cwd'],env=env,timeout=60)
            reference=json.loads(proc.stdout)
            records.append({'mode':'direct_native','repeat':repeat,'seconds':reference['execution_seconds'],
                            'subprocess_seconds':time.perf_counter()-start,'provider_usage':None,'response_bytes':None,'result':reference})
            modes=['mcp','sdk_scripted']+(['live_agent'] if a.live else [])
            for mode in modes:
                async with ScopedCollection(out/f'{mode}-{repeat}') as server:
                    await server.list_tools()
                    start=time.perf_counter();answer=None;model_records=[]
                    if mode=='mcp': await server.call_tool('collect_files',args)
                    else:
                        client=None
                        if mode=='live_agent':
                            from openai import AsyncOpenAI
                            from agents import ModelSettings
                            from agents.retry import ModelRetrySettings
                            client=AsyncOpenAI(max_retries=0,timeout=60)
                            model=MeasuredModel(a.model,client)
                            settings=ModelSettings(max_tokens=1000,preserve_raw_usage=True,store=False,parallel_tool_calls=False,retry=ModelRetrySettings(max_retries=0))
                        else:
                            from agents import ModelSettings
                            model=ScriptedCollection(server);settings=ModelSettings()
                        try:
                            # New objects/no session or history for every repeat. Expected results never supplied.
                            agent=Agent(name='Collection test',model=model,output_type=Answer,mcp_servers=[server],model_settings=settings,
                                        instructions='Use MCP to collect the requested ECSV files. Report file count, total rows and manifest path. Stop after collection. Do not run other processing.')
                            result=await asyncio.wait_for(Runner.run(agent,'Collect files using these requested inputs: '+json.dumps(args),max_turns=6),timeout=180)
                            answer=result.final_output.model_dump()
                        except Exception as exc:
                            requests=getattr(model,'records',[])
                            records.append({'mode':mode,'repeat':repeat,'status':'FAILED',
                                            'error_type':type(exc).__name__,'seconds':time.perf_counter()-start,
                                            'calls':server.calls,'provider_requests':requests,
                                            'provider_usage':usage_total(requests),'exact_native_equivalence':False})
                            save(out/'records.json',records)
                            continue
                        finally:
                            if client:
                                model_records=model.records
                                await client.close()
                    elapsed=time.perf_counter()-start
                    r=server.calls[-1]['result']
                    if r['status']!='PASS': raise RuntimeError(r.get('error'))
                    manifest=json.loads(Path(r['manifest_path']).read_text())
                    copied={f['destination_name']:sha(Path(f['destination'])) for f in manifest['files']}
                    exact=copied==reference['files'] and r['total_rows']==reference['total_rows']
                    if answer:exact=exact and answer['file_count']==len(copied) and answer['total_rows']==reference['total_rows'] and answer['manifest_path']==r['manifest_path']
                    records.append({'mode':mode,'repeat':repeat,'seconds':elapsed,'tool_calls':len(server.calls),
                                    'response_bytes':sum(c['response_bytes'] for c in server.calls),'calls':server.calls,
                                    'provider_requests':model_records,'provider_usage':usage_total(model_records),
                                    'exact_native_equivalence':exact,'final_answer':answer, 'cost_usd':None,
                                    'model_steps':0 if mode=='mcp' else getattr(model,'turn',len(model_records)),
                                    'provider_model_seconds':sum(r['seconds'] for r in model_records) if model_records else None})
                    save(out/'records.json',records)
    finally:
        after=fingerprints(root)
        save(out/'integrity.json',{'inputs_unchanged':before==after,'before':before,'after':after})
        save(out/'records.json',records)
        save(out/'live_status.json',{'live_trials':sum(r['mode']=='live_agent' for r in records),'status':'EXECUTED' if a.live else 'NOT_RUN',
                                     'reason':None if a.live else 'Offline mode; provider tokens and autonomous accuracy unmeasured'})
    if any(r.get('status')=='FAILED' or r.get('exact_native_equivalence') is False for r in records):
        raise SystemExit('Benchmark contains failures; inspect records.json')
    print(json.dumps({'records':len(records),'exact_comparisons':sum(r.get('exact_native_equivalence',False) for r in records),'inputs_unchanged':before==after}))


if __name__=='__main__':asyncio.run(main())
