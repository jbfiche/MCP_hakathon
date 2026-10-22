"""Checked native trace_analyzer on exact merged/unfiltered Step 1c evidence."""
from __future__ import annotations

import inspect
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import numpy as np
from astropy import units as u
from astropy.table import Table
from astropy.io.misc import yaml
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, StrictInt
import matplotlib

# The native module sets global plotting defaults on import. Keep those inside its worker.
with matplotlib.rc_context():
    from traceratops import trace_analyzer as native

from . import approval as a, merged_statistics as ms, pearsons as p, merge as m
from .collection import digest
from .step0 import TRACE_COLUMNS, ROOTS_ENV

OUTPUT_ENV='CHROMATIN_TRACE_ANALYZER_OUTPUT_DIR'
FIGURES=['trace_trace_statistics','trace_barcode_detection','trace_first_neighbor_distances',
         'trace_relative_barcode_frequencies','trace_kde_projections']
TIMEOUT_SECONDS=300


class AnalysisResult(BaseModel):
    status: Literal['ANALYZED','ERROR']
    run_id: str
    scope: Literal['merged_unfiltered_tracing']='merged_unfiltered_tracing'
    baseline_run_id: str
    evidence_path: str | None=None
    evidence_sha256: str | None=None
    artifact_manifest_path: str | None=None
    output_directory: str | None=None
    figure_count: int=0
    neighbor_statistics: dict | None=None
    warnings: list[str]=Field(default_factory=list)
    warning_count: int=0
    warnings_truncated: bool=False
    execution_seconds: float
    structured_response_bytes: int=0
    error_type: str | None=None
    error: str | None=None
    next_action: str='STOP for review. Localization analysis, comprehensive reporting and filtering were not invoked.'


def baseline_root():
    base=Path(os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR',str(Path.cwd()/'results')))
    root=Path(os.environ.get(ms.OUTPUT_ENV,str(base/'merged_trace_statistics'))).expanduser().absolute()
    if root.is_symlink():raise PermissionError('Baseline store must not be a symlink')
    return root


def read_baseline(run_id, checksum):
    with p.run_handle(baseline_root(),run_id) as fd:
        raw=p.read_regular(fd,'statistics.json',p.MAX_MANIFEST_BYTES)
        if a.sha(raw)!=checksum:raise ValueError('Step 1c baseline checksum mismatch')
        value=json.loads(raw)
        log=p.read_regular(fd,'native.log',p.MAX_MANIFEST_BYTES)
    if (value.get('schema_version')!=1 or value.get('run_id')!=run_id or value.get('status')!='COMPUTED'
            or value.get('scope')!='merged_unfiltered_tracing'):
        raise ValueError('Expected a successful merged, unfiltered Step 1c baseline')
    return value,a.sha(log)


def load_context(run_id,checksum):
    baseline,baseline_log_sha=read_baseline(run_id,checksum)
    value,data,merge_log_sha=ms.read_merge(baseline['trace_merge_run_id'],baseline['merged_sha256'],baseline['provenance_sha256'])
    grant,roots,sources=ms.verify_approval(value)
    if any(baseline.get(k)!=v for k,v in {
        'approval_revision':grant['revision'],'approval_fingerprint':grant['fingerprint'],
        'pearson_run_id':value['pearson_run_id'],'pearson_results_sha256':value['results_sha256'],
        'selected_dataset_indices':value['selected_dataset_indices'], 'row_count':value['row_count'],
        'unique_roi_count':value['roi_count'],'global_unique_trace_id_count':value['trace_count'],
        'unique_trace_count':value['trace_count'],'unique_barcode_count':value['barcode_count'],
        'roi_trace_count':value['roi_trace_count'],'merge_native_log_sha256':merge_log_sha,
        'native_module_sha256':digest(Path(ms.statistics.native.__file__)),
        'native_table_module_sha256':digest(Path(inspect.getfile(m.native.ChromatinTraceTable)))
    }.items()):raise ValueError('Baseline disagrees with current merge/approval/native evidence')
    return baseline,value,data,grant,roots,sources,baseline_log_sha


def validate_analysis_input(table):
    required=set(TRACE_COLUMNS)|{'Chrom','Chrom_Start','Chrom_End'}
    missing=required-set(table.colnames)
    if missing:raise ValueError('Analyzer requires columns: '+', '.join(sorted(missing)))
    if not len(table):raise ValueError('Cannot analyze an empty merged trace table')
    for name in required:
        if np.ma.getmaskarray(table[name]).any():raise ValueError(f'Masked values in required analyzer column {name}')
    for name in ['x','y','z']:
        if table[name].dtype.kind not in 'iuf' or not np.isfinite(table[name]).all():
            raise ValueError(f'Analyzer coordinates must be finite numeric values: {name}')
    if table['Barcode #'].dtype.kind not in 'iu':raise ValueError('Native neighbor analysis requires integer barcode identities')
    pairs={(m.output_identifier(r),str(t)) for r,t in zip(table['ROI #'],table['Trace_ID'])}
    ids={str(t) for t in table['Trace_ID']}
    if len(pairs)!=len(ids):
        raise ValueError('Trace_ID collisions across ROIs: native analyzer groups globally by Trace_ID. No relabeling or combining is permitted.')
    if any(not str(v).strip() for v in table['Trace_ID']):raise ValueError('Empty Trace_ID values are not analyzable')
    declared=m.scientific_metadata([table])
    if not declared['xyz_unit'] or any(u.Unit(v)!=u.um for v in declared['xyz_unit']):
        raise ValueError('Native distance plots require explicitly declared micron coordinates; no conversion or assumed calibration')
    for name in ['Chrom_Start','Chrom_End']:
        if table[name].dtype.kind not in 'iu':raise ValueError('Genomic interval coordinates must be integers')
    if np.any(table['Chrom_Start']<0) or np.any(table['Chrom_End']<=table['Chrom_Start']):
        raise ValueError('Invalid genomic intervals: require nonnegative start and end > start')
    chromosomes={str(v).strip() for v in table['Chrom']}
    if len(chromosomes)!=1 or chromosomes & {'','xxxxx','unknown','None','nan','.'}:
        raise ValueError('Genomic-neighbor analysis requires one declared non-placeholder chromosome')
    order=native._get_genomic_barcode_order(table)  # Reuse native barcode-to-genome consistency validation.
    intervals={}
    for row in table:
        intervals[row['Barcode #']]=(str(row['Chrom']),int(row['Chrom_Start']),int(row['Chrom_End']))
    if len(set(intervals.values()))!=len(intervals):
        raise ValueError('Genomic order is ambiguous: distinct barcodes share identical intervals')
    notes=['Native trace grouping is global Trace_ID; cross-ROI collisions are rejected, and IDs are never relabeled.',
           'Repeated barcodes are preserved; native neighbor pairing can be ambiguous and does not separate alleles.',
           'Native relative-frequency figure bins cover multiplicities 1–8; complete native returned multiplicities are saved separately.']
    if not declared['genome_assembly']:notes.append('Genome assembly is not declared; the analyzer does not independently verify assembly identity.')
    return {'global_trace_id_count':len(ids),'roi_trace_count':len(pairs),'genomic_barcode_order':list(map(int,order)),
            'chromosome':next(iter(chromosomes)),'coordinate_units':sorted(declared['xyz_unit'])},notes


def verify_source_units(value):
    notes=[]
    for source in value['sources']:
        # Metadata serialized by the existing merge validator; never infer raw units from native constructor defaults.
        metadata=yaml.load(source['source_metadata_yaml'])
        columns=yaml.load(source.get('source_column_metadata_yaml','{}'))
        dummy=Table({'x':[], 'y':[], 'z':[]},meta=metadata)
        for axis in ['x','y','z']:
            if columns.get(axis,{}).get('unit') is not None:dummy[axis].unit=columns[axis]['unit']
        declared=m.scientific_metadata([dummy])
        if not declared['xyz_unit'] or any(u.Unit(v)!=u.um for v in declared['xyz_unit']):
            raise ValueError('Approved source coordinate units must explicitly be microns; native merge defaults are insufficient')
        if not declared['genome_assembly']:notes.append('At least one original source lacks declared genome assembly; merged constructor defaults do not verify it.')
    return list(dict.fromkeys(notes))


def output_root(roots):
    base=Path(os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR',str(Path.cwd()/'results')))
    root=Path(os.environ.get(OUTPUT_ENV,str(base/'trace_analysis'))).expanduser().resolve()
    forbidden=set(roots)|{ms.merge_root().resolve(),baseline_root().resolve(),p.collection_root().resolve(),a.pearson_root().resolve(),
        Path(os.environ.get('CHROMATIN_LOCALIZATION_MERGE_OUTPUT_DIR',str(base/'localization_merges'))).expanduser().resolve()}
    forbidden.update(Path(v).expanduser().resolve() for v in os.environ.get(ROOTS_ENV,'').split(os.pathsep) if v)
    if any(root==v or root.is_relative_to(v) for v in forbidden):raise PermissionError('Analyzer output must be outside input/evidence stores')
    return root


def run_worker(folder,output_format,distance_range,seed):
    env=dict(os.environ);env['MPLBACKEND']='Agg';env['PYTHONDONTWRITEBYTECODE']='1'
    with (folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
        process=subprocess.run([sys.executable,'-m','chromatin_trace_mcp.trace_analyzer_worker','--format',output_format,
                '--distance-range',distance_range,'--seed',str(seed)],cwd=folder,env=env,stdout=out,stderr=err,timeout=TIMEOUT_SECONDS)
    if process.returncode:raise RuntimeError(f'Native trace analyzer failed (exit code {process.returncode}); inspect saved logs and partial artifacts')


def execute_analysis(baseline_run_id,baseline_sha256,output_format='png',neighbor_distance_range='1',random_seed=0):
    start=time.perf_counter();run_id=uuid4().hex;detail=None;final=None
    try:
        if output_format not in {'png','svg','pdf'}:raise ValueError('Unsupported native figure format')
        if neighbor_distance_range!='auto' and (not math.isfinite(float(neighbor_distance_range)) or float(neighbor_distance_range)<=0):
            raise ValueError('Neighbor plotting range must be auto or finite positive microns')
        if type(random_seed) is not int or not 0<=random_seed<2**32:raise ValueError('Invalid NumPy random seed')
        baseline,value,data,grant,roots,sources,baseline_log_sha=load_context(baseline_run_id,baseline_sha256)
        output=output_root(roots)
        with tempfile.TemporaryDirectory(prefix='trace-analyzer-validation-') as temp:
            snapshots=Path(temp);path=snapshots/'merged.ecsv';path.write_bytes(data)
            table=Table.read(path,format='ascii.ecsv')
            contributions=ms.verify_contributions(value,table,snapshots,grant,sources)
            if contributions!=baseline['approved_source_contributions']:raise ValueError('Baseline source contributions differ from verified merge')
            source_notes=verify_source_units(value)
            checks,notes=validate_analysis_input(table)
            notes+=source_notes
        output.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.pending-trace-analysis-',dir=output) as temp:
            folder=Path(temp)/'results';folder.mkdir(mode=0o700)
            trace=folder/'trace.ecsv';trace.write_bytes(data);trace.chmod(0o400)
            detail={'schema_version':1,'run_id':run_id,'status':'RUNNING','scope':'merged_unfiltered_tracing',
                'generated_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_run_id':baseline_run_id,'baseline_sha256':baseline_sha256,
                'baseline_fingerprint':baseline['baseline_fingerprint'],'baseline_native_log_sha256':baseline_log_sha,
                'trace_merge_run_id':baseline['trace_merge_run_id'],'merged_sha256':baseline['merged_sha256'],
                'merge_provenance_sha256':baseline['provenance_sha256'],'approval_revision':grant['revision'],
                'approval_fingerprint':grant['fingerprint'],'pearson_run_id':value['pearson_run_id'],
                'pearson_results_sha256':value['results_sha256'],'selected_dataset_indices':grant['selected_dataset_indices'],
                'approved_source_contributions':contributions,'input_checks':checks,'warnings':notes,
                'native_function':'traceratops.trace_analyzer.process_traces','traceratops_version':baseline['traceratops_version'],
                'native_analyzer_sha256':digest(Path(native.__file__)),
                'native_table_module_sha256':digest(Path(inspect.getfile(native.ChromatinTraceTable))),
                'worker_sha256':digest(Path(__file__).with_name('trace_analyzer_worker.py')),
                'parameters':{'output_format':output_format,'neighbor_distance_range':neighbor_distance_range,'random_seed':random_seed,'plotXYZ':False},
                'numerical_capture':'Unmodified native return values and inputs/results supplied to native plotting calls; no scientific recalculation.'}
            try:
                run_worker(folder,output_format,neighbor_distance_range,random_seed)
                if digest(trace)!=baseline['merged_sha256']:raise ValueError('Native analyzer modified its input snapshot')
                for stem in FIGURES:
                    figure=folder/f'{stem}.{output_format}'
                    if not figure.is_file() or not figure.stat().st_size:raise ValueError(f'Native figure missing: {figure.name}')
                numeric=json.loads((folder/'numerical_outputs.json').read_text())
                if numeric['status']!='COMPLETE':raise ValueError('Native numerical capture is incomplete')
                with np.load(folder/'numerical_outputs.npz',allow_pickle=False) as arrays:
                    hist=[c for c in numeric['plot_calls'] if c['stage']=='neighbor_distances' and c['method']=='hist']
                    if len(hist)!=3:raise ValueError('Unsupported native neighbor plotting interface')
                    pair_count=len(arrays[hist[0]['arrays']['observations']])
                detail['warnings']+=numeric['warnings']
                neighbor={'status':'AVAILABLE' if pair_count else 'UNAVAILABLE_NO_ELIGIBLE_NEIGHBORS',
                          'observation_count':pair_count,**numeric['returned_values']['neighbor_statistics']}
                if not pair_count:detail['warnings'].append('Native neighbor statistics return zeros when no eligible barcode pairs exist; these are placeholders, not measured zero distances.')
                detail['neighbor_statistics']=neighbor
                detail['status']='ANALYZED'
                with a.locked_state(value['pearson_run_id']) as (current,_):
                    ev=a.evidence(value['pearson_run_id'],value['results_sha256'])
                    if not current or current['revision']!=grant['revision'] or current['status']!='APPROVED' or not a.state_matches(current,ev):
                        raise PermissionError('Approval/evidence changed before analyzer publication')
                    last,log_sha=read_baseline(baseline_run_id,baseline_sha256)
                    if last!=baseline or log_sha!=baseline_log_sha:raise ValueError('Baseline evidence changed during analysis')
                    _,_,log_sha=ms.read_merge(baseline['trace_merge_run_id'],baseline['merged_sha256'],baseline['provenance_sha256'])
                    if log_sha!=baseline['merge_native_log_sha256']:raise ValueError('Merge log changed during analysis')
                    final=publish(folder,output,run_id,detail,start)
            except Exception as exc:
                detail.update(status='ERROR',error_type=type(exc).__name__,error=str(exc)[:500]);detail.pop('neighbor_statistics',None)
                numeric=folder/'numerical_outputs.json'
                if numeric.exists():
                    try:detail['warnings']+=json.loads(numeric.read_text()).get('warnings',[])
                    except (ValueError,OSError):
                        detail['warnings'].append('Native numerical metadata is incomplete/unreadable; partial files and logs are retained as failed-run artifacts.')
                final=publish(folder,output,run_id,detail,start)
        return make_response(detail,final,start)
    except Exception as exc:
        return AnalysisResult(status='ERROR',run_id=run_id,baseline_run_id=baseline_run_id,error_type=type(exc).__name__,error=str(exc)[:500],execution_seconds=time.perf_counter()-start)


def publish(folder,output,run_id,detail,start):
    snapshot=folder/'trace.ecsv'
    if snapshot.exists():snapshot.unlink()  # Private copied input only; never touch an original artifact.
    artifacts=[{'name':f.name,'sha256':digest(f),'size_bytes':f.stat().st_size} for f in sorted(folder.iterdir()) if f.is_file()]
    (folder/'artifacts.json').write_text(json.dumps(artifacts,indent=2))
    detail['artifact_manifest_sha256']=digest(folder/'artifacts.json');detail['execution_seconds']=time.perf_counter()-start
    detail['artifacts']={'manifest':'artifacts.json','numerical_metadata':'numerical_outputs.json','numerical_arrays':'numerical_outputs.npz'}
    (folder/'analysis.json').write_text(json.dumps(detail,indent=2,allow_nan=False))
    final=output/run_id
    if final.exists():raise FileExistsError('Analyzer run already exists')
    folder.rename(final)
    return final


def make_response(detail,final,start):
    notes=list(dict.fromkeys(detail['warnings']))
    return AnalysisResult(status=detail['status'],run_id=detail['run_id'],baseline_run_id=detail['baseline_run_id'],
        evidence_path=str(final/'analysis.json'),evidence_sha256=digest(final/'analysis.json'),
        artifact_manifest_path=str(final/'artifacts.json'),output_directory=str(final),figure_count=5 if detail['status']=='ANALYZED' else 0,
        neighbor_statistics=detail.get('neighbor_statistics'),warnings=[v[:320] for v in notes[:4]],warning_count=len(notes),
        warnings_truncated=len(notes)>4 or any(len(v)>320 for v in notes[:4]),error_type=detail.get('error_type'),error=detail.get('error'),execution_seconds=time.perf_counter()-start)


def register_trace_analyzer_tool(mcp):
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False,destructive_hint=False,idempotent_hint=False,open_world_hint=False))
    def trace_analyzer(baseline_run_id: Annotated[str,Field(pattern=a.RUN_PATTERN)],
                       baseline_sha256: Annotated[str,Field(pattern=a.SHA_PATTERN)],
                       output_format: Literal['png','svg','pdf']='png',
                       neighbor_distance_range: str='1',
                       random_seed: Annotated[StrictInt,Field(ge=0,lt=2**32)]=0) -> AnalysisResult:
        """Run native trace_analyzer on a verified merged, unfiltered Step 1c baseline.

        Reject cross-ROI Trace_ID collisions and ambiguous genomic metadata.
        Save native figures/numerical outputs locally; no filtering or other analyzer.
        """
        result=execute_analysis(baseline_run_id,baseline_sha256,output_format,neighbor_distance_range,random_seed)
        for _ in range(4):
            size=len(result.model_dump_json().encode())
            if size==result.structured_response_bytes:break
            result.structured_response_bytes=size
        return result
