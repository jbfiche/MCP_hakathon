"""Human-only terminal MCP elicitation on an existing run, without copying evidence."""
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.types import ElicitResult


async def run(options):
    config=json.loads(options.connection.read_text())
    if not options.check and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise RuntimeError('Run manually in an interactive terminal. Piped or automatic decisions are refused.')
    responses=[]

    async def human_form(context,params):
        if responses: raise RuntimeError('A decision may not be replayed; start a new human review.')
        if getattr(params,'mode','form')!='form': raise RuntimeError('Only MCP form elicitation is supported')
        if set(params.requested_schema.get('properties',{}))!={'decision','selected_dataset_indices'}:
            raise RuntimeError('Unexpected approval form schema; no decision sent')
        print('\n--- Actual MCP server scientific review ---\n'+params.message+'\n')
        while True:
            decision=(await asyncio.to_thread(input,'Type APPROVE, REJECT or CANCEL (no default): ')).strip().upper()
            if decision in {'APPROVE','REJECT','CANCEL'}: break
        selection=''
        if decision=='APPROVE':
            while True:
                selection=(await asyncio.to_thread(input,'Explicit dataset indices to approve (see form), or CANCEL: ')).strip()
                if selection.upper()=='CANCEL': decision='CANCEL';selection='';break
                if re.fullmatch(r'\d+(\s*,\s*\d+)*',selection):
                    indices=[int(v.strip()) for v in selection.split(',')]
                    if len(indices)==len(set(indices)): break
                print('No response sent. Enter distinct indices or CANCEL.')
        responses.append({'decision':decision,'selected_dataset_indices':selection})
        if decision=='CANCEL': return ElicitResult(action='cancel')
        return ElicitResult(action='accept',content={'decision':decision,'selected_dataset_indices':selection})

    parameters=StdioServerParameters(command=config['command'],args=config['args'],cwd=config['cwd'],env={**os.environ,**config['env']})
    callback=None if options.check else human_form
    async with Client(parameters,elicitation_callback=callback,read_timeout_seconds=None) as client:
        tools={t.name for t in (await client.list_tools()).tools}
        if 'review_pearson_approval' not in tools: raise RuntimeError('Current approval tool not found')
        arguments={'pearson_run_id':options.run_id,'results_sha256':options.results_sha256}
        if options.check:
            status=await client.call_tool('review_pearson_approval',dict(arguments,request_decision=False))
            print(json.dumps(status.structured_content,indent=2));print('Connection checked; no human decision requested or sent.');return
        previous=await client.call_tool('review_pearson_approval',dict(arguments,request_decision=False))
        response=await client.call_tool('review_pearson_approval',dict(arguments,request_decision=True))
        status=await client.call_tool('review_pearson_approval',dict(arguments,request_decision=False))
    if len(responses)!=1: raise RuntimeError('No human form response occurred; approval was not tested')
    expected={'APPROVE':'APPROVED','REJECT':'REJECTED','CANCEL':previous.structured_content['status']}[responses[0]['decision']]
    first=response.structured_content;second=status.structured_content
    if first['status']!=expected or second['status']!=expected: raise RuntimeError('Decision not saved as expected: '+json.dumps(second))
    saved=json.loads(Path(second['decision_record_path']).read_text())
    indices=sorted(int(v.strip()) for v in responses[0]['selected_dataset_indices'].split(',')) if responses[0]['selected_dataset_indices'] else []
    if responses[0]['decision']=='CANCEL':indices=previous.structured_content['selected_dataset_indices']
    if saved['status']!=expected or saved['selected_dataset_indices']!=indices or second['selected_dataset_indices']!=indices:
        raise RuntimeError('Persisted state differs from explicit terminal decision')
    record={'human_terminal_response':responses[0],'request_result':first,'status_query':second,'saved_status_verified':True,
            'downstream_processing_invoked':False,'provider_requests':0}
    if options.record:
        with options.record.open('x') as output: json.dump(record,output,indent=2)
    print('Verified saved status:',expected,'; selected dataset indices:',indices)
    print('Decision record:',second['decision_record_path'])
    print('No merging, annotation or analysis was invoked.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection',type=Path,required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--results-sha256',required=True)
    parser.add_argument('--record',type=Path)
    parser.add_argument('--check',action='store_true',help='Discovery/status only; never submit a human decision.')
    asyncio.run(run(parser.parse_args()))
