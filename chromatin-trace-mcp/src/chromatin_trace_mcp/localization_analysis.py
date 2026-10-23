"""Verified merged-input mode for the existing localization_analyzer tool."""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime,timezone
from importlib.metadata import version
from pathlib import Path
from typing import Literal
from uuid import uuid4

import numpy as np
from astropy.io.misc import yaml
from astropy.table import Table
from pydantic import BaseModel,Field
from traceratops import localization_analyzer as native

from . import approval as a,localization_merge as lm,pearsons as p
from .collection import digest
from .step0 import LOCALIZATION_COLUMNS,ROOTS_ENV

OUTPUT_ENV='CHROMATIN_LOCALIZATION_ANALYZER_OUTPUT_DIR'
PLOT_COLUMNS={'Barcode #','zcentroid','snr','skew','object_class','roundness'}
TIMEOUT_SECONDS=300


class VerifiedLocalizationAnalysisResult(BaseModel):
    status: Literal['ANALYZED','ERROR']
    run_id: str
    scope: Literal['merged_unfiltered_localization']='merged_unfiltered_localization'
    localization_merge_run_id: str
    evidence_path: str | None=None
    evidence_sha256: str | None=None
    artifact_manifest_path: str | None=None
    output_directory: str | None=None
    output_file: str | None=None
    row_count: int | None=None
    unique_barcode_count: int | None=None
    roi_count: int | None=None
    figure_count: int=0
    warnings: list[str]=Field(default_factory=list)
    warning_count: int=0
    warnings_truncated: bool=False
    execution_seconds: float
    structured_response_bytes: int=0
    error_type: str | None=None
    error: str | None=None
    next_action: str='STOP for review. No filtering or comprehensive report was invoked.'


def merge_root():
    base=Path(os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR',str(Path.cwd()/'results')))
    root=Path(os.environ.get(lm.OUTPUT_ENV,str(base/'localization_merges'))).expanduser().absolute()
    if root.is_symlink():raise PermissionError('Localization merge store must not be a symlink')
    return root


def read_merge(run_id,merged_sha256,provenance_sha256):
    with p.run_handle(merge_root(),run_id) as fd:
        raw=p.read_regular(fd,'provenance.json',p.MAX_MANIFEST_BYTES)
        data=p.read_regular(fd,'merged_localizations.ecsv',p.MAX_TOTAL_BYTES)
        log=p.read_regular(fd,'native.log',p.MAX_MANIFEST_BYTES)
    if a.sha(raw)!=provenance_sha256 or a.sha(data)!=merged_sha256:raise ValueError('Localization merge/provenance checksum mismatch')
    doc=json.loads(raw)
    expected={'schema_version':1,'phase':'localization_merge_only','run_id':run_id,'merge_policy':'native-localization-merge-v1',
              'merged_sha256':merged_sha256,'native_module_sha256':digest(Path(lm.native.__file__)),
              'native_table_module_sha256':digest(Path(inspect.getfile(native.LocalizationTable))),
              'traceratops_version':version('traceratops')}
    if any(doc.get(k)!=v for k,v in expected.items()) or doc.get('artifacts')!={'merged':'merged_localizations.ecsv','native_log':'native.log'}:
        raise ValueError('Localization merge provenance/native implementation mismatch')
    return doc,data,a.sha(log)


def context(run_id,merged_sha256,provenance_sha256):
    doc,data,log_sha=read_merge(run_id,merged_sha256,provenance_sha256)
    saved=doc['approval_snapshot']
    grant=a.require_scientific_approval(doc['pearson_run_id'],doc['results_sha256'],doc['selected_dataset_indices'],saved['evidence']['parameters'])
    if doc['approval_revision']!=grant['revision'] or doc['approval_fingerprint']!=grant['fingerprint'] or saved!=grant:
        raise PermissionError('Merged localization approval differs from current exact human approval')
    refs=[p.CollectionReference.model_validate(r) for r in doc['localization_collections']]
    mapped,roots=lm.associations(grant,refs)
    if len(mapped)!=len(doc['sources']):raise ValueError('Incomplete localization source mapping')
    for item,saved_source in zip(mapped,doc['sources']):
        if any(saved_source.get(k)!=v for k,v in item.items()):raise ValueError('Localization source identity/order differs from approved mapping')
    lm.read_selected(mapped)
    return doc,data,log_sha,grant,mapped,roots


def validate_contributions(doc,table,mapped,folder):
    inputs=[]
    for i,data in enumerate(lm.read_selected(mapped)):
        path=folder/f'source-{i}.ecsv';path.write_bytes(data);path.chmod(0o400)
        inputs.append(Table.read(path,format='ascii.ecsv'))
    contributions=lm.validate_rows(inputs,table,mapped)
    for original,actual,saved in zip(inputs,contributions,doc['sources']):
        if any(saved.get(k)!=v for k,v in actual.items()):raise ValueError('Localization row/metadata provenance differs from merge evidence')
        lo,hi=actual['row_start'],actual['row_stop_exclusive']
        np.testing.assert_array_equal(original['ROI #'],table['ROI #'][lo:hi])
    if yaml.dump(table.meta)!=doc['merged_metadata_yaml'] or yaml.dump(lm.column_metadata(table))!=doc['merged_column_metadata_yaml']:
        raise ValueError('Localization merged metadata differs from saved provenance')
    if lm.metadata_contract(inputs)!=lm.metadata_contract([table]):raise ValueError('Localization scientific metadata changed')
    counts={'row_count':len(table),'barcode_count':len(set(table['Barcode #'])),'roi_count':len(set(table['ROI #'])),
            'localization_id_count':len(set(map(str,table['Buid'])))}
    if any(doc[k]!=v for k,v in counts.items()):raise ValueError('Localization merge counts disagree with current table')
    return counts


def preflight(table):
    missing=(set(LOCALIZATION_COLUMNS)|PLOT_COLUMNS)-set(table.colnames)
    if missing:raise ValueError('Native localization QC requires current columns: '+', '.join(sorted(missing)))
    if not len(table):raise ValueError('Cannot analyze an empty localization table')
    for name in set(LOCALIZATION_COLUMNS)|PLOT_COLUMNS:
        if np.ma.getmaskarray(table[name]).any():raise ValueError('Masked required localization values: '+name)
    if table['Barcode #'].dtype.kind not in 'iu':raise ValueError('Original localization barcode IDs must be integers')
    for name in PLOT_COLUMNS-{'Barcode #'}:
        if table[name].dtype.kind not in 'iuf' or not np.isfinite(table[name]).all():
            raise ValueError('Native plotting requires finite numeric values: '+name)


def output_root(roots):
    base=Path(os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR',str(Path.cwd()/'results')))
    output=Path(os.environ.get(OUTPUT_ENV,str(base/'localization_analysis'))).expanduser().resolve()
    forbidden=set(roots)|{merge_root().resolve(),p.collection_root().resolve(),a.pearson_root().resolve()}
    for env,default in [('CHROMATIN_MERGE_OUTPUT_DIR','trace_merges'),('CHROMATIN_MERGED_STATS_OUTPUT_DIR','merged_trace_statistics'),
                        ('CHROMATIN_GENOMIC_OUTPUT_DIR','genomic_annotations'),('CHROMATIN_TRACE_ANALYZER_OUTPUT_DIR','trace_analysis')]:
        forbidden.add(Path(os.environ.get(env,str(base/default))).expanduser().resolve())
    forbidden.update(Path(v).expanduser().resolve() for v in os.environ.get(ROOTS_ENV,'').split(os.pathsep) if v)
    if any(output==v or output.is_relative_to(v) for v in forbidden):raise PermissionError('Localization analysis output must be outside input/evidence stores')
    return output


def annotation_context(run_id,checksum,grant):
    """Optional reference to tracing's barcode namespace; never rename localizations."""
    if run_id is None and checksum is None:return None
    if run_id is None or checksum is None:raise ValueError('Tracing annotation ID and checksum must be supplied together')
    from . import genomic_annotation as ga,tracing_analysis as ta
    with p.run_handle(ga.store(),run_id) as fd:raw=p.read_regular(fd,'annotation.json',p.MAX_MANIFEST_BYTES)
    if a.sha(raw)!=checksum:raise ValueError('Tracing annotation evidence checksum mismatch')
    doc=json.loads(raw);bid,bsha=doc['baseline_run_id'],doc['baseline_sha256']
    baseline,value,data,trace_grant,roots,sources,log_sha=ta.load_context(bid,bsha)
    if trace_grant!=grant:raise PermissionError('Tracing annotation and localization merge have different approvals')
    with tempfile.TemporaryDirectory(prefix='loc-trace-mapping-validation-') as temp:
        folder=Path(temp);path=folder/'trace.ecsv';path.write_bytes(data);original=Table.read(path,format='ascii.ecsv')
        contributions=ta.ms.verify_contributions(value,original,folder,grant,sources)
        if contributions!=baseline['approved_source_contributions']:raise ValueError('Tracing baseline contributions differ')
        _,verified=ga.verify_saved(run_id,checksum,bid,bsha,original,baseline,grant,roots)
    summary={'annotation_run_id':run_id,'annotation_sha256':checksum,'bed_sha256':verified['bed_sha256'],
             'mapping_path':str(ga.store()/run_id/'barcode_mapping.json'),'mapping_sha256':verified['mapping_sha256'],
             'annotated_trace_namespace':'BED replacement barcode IDs','localization_namespace':'original barcode IDs',
             'spot_identity_join':'Spot_ID/Buid, never barcode alone'}
    return summary,(baseline,value,data,roots,log_sha,doc,run_id,checksum)


def recheck_annotation(annotation,grant,current):
    if annotation is None:return
    from . import genomic_annotation as ga
    baseline,value,data,roots,log_sha,doc,run_id,checksum=annotation[1]
    ga.recheck_context(doc['baseline_run_id'],doc['baseline_sha256'],baseline,log_sha,value,grant,current)
    with tempfile.TemporaryDirectory(prefix='loc-final-mapping-validation-') as temp:
        path=Path(temp)/'trace.ecsv';path.write_bytes(data)
        ga.verify_saved(run_id,checksum,doc['baseline_run_id'],doc['baseline_sha256'],Table.read(path,format='ascii.ecsv'),baseline,grant,roots)


def run_worker(folder,output_format):
    env={**os.environ,'MPLBACKEND':'Agg','PYTHONDONTWRITEBYTECODE':'1'}
    with (folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
        run=subprocess.run([sys.executable,'-m','chromatin_trace_mcp.localization_analyzer_worker','--format',output_format],cwd=folder,env=env,stdout=out,stderr=err,timeout=TIMEOUT_SECONDS)
    if run.returncode:raise RuntimeError(f'Native localization analyzer failed (exit {run.returncode}); inspect saved logs')


def publish(folder,output,run_id,detail,start):
    snapshot=folder/'localizations.ecsv'
    if snapshot.exists():snapshot.unlink() # Private input copy only.
    manifest=[{'name':f.name,'sha256':digest(f),'size_bytes':f.stat().st_size} for f in sorted(folder.iterdir()) if f.is_file()]
    (folder/'artifacts.json').write_text(json.dumps(manifest,indent=2));detail['artifact_manifest_sha256']=digest(folder/'artifacts.json')
    detail['execution_seconds']=time.perf_counter()-start
    (folder/'analysis.json').write_text(json.dumps(detail,indent=2,allow_nan=False))
    final=output/run_id
    if final.exists():raise FileExistsError('Localization analysis run already exists')
    folder.rename(final);return final


def response(detail,folder,start):
    success=detail['status']=='ANALYZED';notes=list(dict.fromkeys(detail['warnings']))
    result=VerifiedLocalizationAnalysisResult(status=detail['status'],run_id=detail['run_id'],localization_merge_run_id=detail['localization_merge_run_id'],
       evidence_path=str(folder/'analysis.json'),evidence_sha256=digest(folder/'analysis.json'),artifact_manifest_path=str(folder/'artifacts.json'),
       output_directory=str(folder),output_file=str(folder/detail['figure']) if success else None,
       row_count=detail['counts']['row_count'] if success else None,unique_barcode_count=detail['counts']['barcode_count'] if success else None,
       roi_count=detail['counts']['roi_count'] if success else None,figure_count=int(success),warnings=[v[:320] for v in notes[:4]],
       warning_count=len(notes),warnings_truncated=len(notes)>4 or any(len(v)>320 for v in notes[:4]),
       error_type=detail.get('error_type'),error=detail.get('error'),execution_seconds=time.perf_counter()-start)
    return measured(result)


def measured(result):
    for _ in range(4):
        size=len(result.model_dump_json().encode())
        if size==result.structured_response_bytes:break
        result.structured_response_bytes=size
    return result


def execute_analysis(localization_merge_run_id,merged_sha256,provenance_sha256,output_format='png',annotation_run_id=None,annotation_sha256=None):
    start=time.perf_counter();run_id=uuid4().hex
    try:
        if output_format not in {'png','svg','pdf'}:raise ValueError('Unsupported native output format')
        doc,data,log_sha,grant,mapped,roots=context(localization_merge_run_id,merged_sha256,provenance_sha256)
        output=output_root(roots)
        with tempfile.TemporaryDirectory(prefix='localization-qc-preflight-') as temp:
            folder=Path(temp);source=folder/'merged.ecsv';source.write_bytes(data);table=Table.read(source,format='ascii.ecsv')
            counts=validate_contributions(doc,table,mapped,folder);preflight(table)
        annotation=annotation_context(annotation_run_id,annotation_sha256,grant)
        output.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.pending-localization-qc-',dir=output) as temp:
            folder=Path(temp)/'result';folder.mkdir(mode=0o700)
            source=folder/'localizations.ecsv';source.write_bytes(data);source.chmod(0o400)
            notes=list(doc.get('warnings',[]))+[
                'Localizations retain original barcode IDs. Annotated traces use BED replacement IDs; use the saved mapping for labels and Spot_ID/Buid for spot correspondence.',
                'No additional filtering, coordinate conversion or barcode replacement was applied. Supplied upstream filtered/registered metadata is retained.',
                'The native analyzer returns no statistics object. Saved numerical evidence contains native plot inputs/counts and returned Matplotlib geometry, not new acceptance metrics.',
                'Native z_centroid values use the supplied units; missing localization unit/assembly declarations are not inferred from tracing metadata.']
            detail={'schema_version':1,'status':'RUNNING','run_id':run_id,'scope':'merged_unfiltered_localization',
                'generated_at_utc':datetime.now(timezone.utc).isoformat(),'localization_merge_run_id':localization_merge_run_id,
                'merged_sha256':merged_sha256,'provenance_sha256':provenance_sha256,'merge_native_log_sha256':log_sha,
                'source_file':str(merge_root()/localization_merge_run_id/'merged_localizations.ecsv'),
                'pearson_run_id':doc['pearson_run_id'],'pearson_results_sha256':doc['results_sha256'],
                'approval_revision':grant['revision'],'approval_fingerprint':grant['fingerprint'],'selected_dataset_indices':grant['selected_dataset_indices'],
                'approved_roi_mapping':mapped,'counts':counts,'barcode_namespace':'original','tracing_annotation':annotation[0] if annotation else None,
                'native_function':'traceratops.localization_analyzer.run','traceratops_version':version('traceratops'),
                'native_module_sha256':digest(Path(native.__file__)),'native_table_module_sha256':digest(Path(inspect.getfile(native.LocalizationTable))),
                'worker_sha256':digest(Path(__file__).with_name('localization_analyzer_worker.py')),
                'parameters':{'output_format':output_format,'filtering':False,'barcode_replacement':False},
                'figure':'localization_distribution_fluxes.'+output_format,'warnings':notes}
            try:
                run_worker(folder,output_format)
                if digest(source)!=merged_sha256:raise ValueError('Native analyzer modified its input snapshot')
                figure=folder/detail['figure']
                if not figure.is_file() or not figure.stat().st_size:raise ValueError('Native localization figure missing or skipped')
                numeric=json.loads((folder/'numerical_outputs.json').read_text())
                if numeric['status']!='COMPLETE' or sum(v['count'] for v in numeric['native_barcode_counts'])!=counts['row_count']:
                    raise ValueError('Native numerical capture is incomplete or omits input observations')
                if {v['barcode'] for v in numeric['native_barcode_counts']}!=set(map(int,table['Barcode #'])):
                    raise ValueError('Native analysis changed localization barcode identities')
                with np.load(folder/'numerical_outputs.npz',allow_pickle=False) as arrays:
                    if len(arrays.files)==0:raise ValueError('Native numerical arrays missing')
                detail['warnings']+=numeric['warnings'];detail['status']='ANALYZED'
                with a.locked_state(doc['pearson_run_id']) as (current,_):
                    ev=a.evidence(doc['pearson_run_id'],doc['results_sha256'])
                    if not current or current['status']!='APPROVED' or current['revision']!=grant['revision'] or not a.state_matches(current,ev):
                        raise PermissionError('Scientific approval/evidence changed before localization analysis publication')
                    latest,last_data,last_log=read_merge(localization_merge_run_id,merged_sha256,provenance_sha256)
                    if latest!=doc or last_data!=data or last_log!=log_sha:raise ValueError('Localization merge/log changed during analysis')
                    latest_mapping,_=lm.associations(grant,[p.CollectionReference.model_validate(r) for r in doc['localization_collections']])
                    if latest_mapping!=mapped:raise ValueError('Approved localization ROI mapping changed')
                    lm.read_selected(mapped);recheck_annotation(annotation,grant,current)
                    final=publish(folder,output,run_id,detail,start)
            except Exception as exc:
                detail.update(status='ERROR',error_type=type(exc).__name__,error=str(exc)[:500])
                final=publish(folder,output,run_id,detail,start)
        return response(detail,final,start)
    except Exception as exc:
        return measured(VerifiedLocalizationAnalysisResult(status='ERROR',run_id=run_id,localization_merge_run_id=localization_merge_run_id,
            error_type=type(exc).__name__,error=str(exc)[:500],execution_seconds=time.perf_counter()-start))
