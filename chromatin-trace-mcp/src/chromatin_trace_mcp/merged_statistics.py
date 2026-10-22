"""Step 1c: checksum-bound descriptive baseline for an approved, unfiltered trace merge."""
from __future__ import annotations

import contextlib
import inspect
from importlib.metadata import version
from datetime import datetime, timezone
import io
import json
import os
import tempfile
import time
import warnings
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from astropy.table import Table
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import approval as a, merge as m, pearsons as p, trace_statistics as statistics
from .collection import digest
from .step0 import TRACE_COLUMNS, ROOTS_ENV

OUTPUT_ENV = 'CHROMATIN_MERGED_STATS_OUTPUT_DIR'


class MergedStatisticsResult(BaseModel):
    status: Literal['COMPUTED', 'ERROR']
    run_id: str
    scope: Literal['merged_unfiltered_tracing'] = 'merged_unfiltered_tracing'
    evidence_path: str | None = None
    evidence_sha256: str | None = None
    baseline_fingerprint: str | None = None
    native_log_path: str | None = None
    trace_merge_run_id: str
    row_count: int | None = None
    unique_roi_count: int | None = None
    global_unique_trace_id_count: int | None = None
    roi_trace_count: int | None = None
    unique_barcode_count: int | None = None
    warnings: list[str] = Field(default_factory=list)
    warning_count: int = 0
    warnings_truncated: bool = False
    execution_seconds: float
    structured_response_bytes: int = 0
    error_type: str | None = None
    error: str | None = None
    next_action: str = 'STOP for review. No analyzers, comprehensive report or filtering were invoked.'


def merge_root():
    base = Path(os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR', str(Path.cwd()/'results')))
    root = Path(os.environ.get(m.OUTPUT_ENV, str(base/'trace_merges'))).expanduser().absolute()
    if root.is_symlink(): raise PermissionError('Trace merge store must not be a symlink')
    return root


def read_merge(run_id, merged_sha256, provenance_sha256):
    with p.run_handle(merge_root(), run_id) as fd:
        raw = p.read_regular(fd, 'provenance.json', p.MAX_MANIFEST_BYTES)
        data = p.read_regular(fd, 'merged_traces.ecsv', p.MAX_TOTAL_BYTES)
        if a.sha(raw) != provenance_sha256: raise ValueError('Trace merge provenance checksum mismatch')
        if a.sha(data) != merged_sha256: raise ValueError('Merged tracing ECSV checksum mismatch')
        value = json.loads(raw)
        if (value.get('schema_version') != 1 or value.get('phase') != 'trace_merge_only'
                or value.get('run_id') != run_id or value.get('merge_policy') != 'native-trace-merge-v1'
                or value.get('merged_sha256') != merged_sha256
                or value.get('artifacts', {}).get('merged') != 'merged_traces.ecsv'):
            raise ValueError('Expected native unfiltered Step 1b.1 trace merge provenance')
        log = p.read_regular(fd, value['artifacts']['native_log'], p.MAX_MANIFEST_BYTES)
    return value, data, a.sha(log)


def verify_approval(value):
    grant = a.require_scientific_approval(value['pearson_run_id'], value['results_sha256'],
                value['selected_dataset_indices'], value['pearson_parameters'])
    if (value['approval_revision'] != grant['revision'] or value['approval_fingerprint'] != grant['fingerprint']
            or value['approval_snapshot'] != grant or value['collection_references'] != grant['selected_collection_references']):
        raise PermissionError('Merge approval evidence differs from current exact human approval')
    if (value['native_module_sha256'] != digest(Path(m.native.__file__))
            or value['native_table_module_sha256'] != digest(Path(inspect.getfile(m.native.ChromatinTraceTable)))):
        raise ValueError('Native merge implementation differs from recorded provenance')
    roots = set()
    sources = {}
    for ref in grant['selected_collection_references']:
        with p.run_handle(p.collection_root(), ref['collection_run_id']) as fd:
            raw = p.read_regular(fd, 'manifest.json', p.MAX_MANIFEST_BYTES)
            if a.sha(raw) != ref['manifest_sha256']: raise ValueError('Collection manifest changed')
            manifest = json.loads(raw)
        roots.add(Path(manifest['experiment_root']).resolve())
        for item in manifest['files']:
            sources[ref['collection_run_id'], item['destination_name']] = {
                'experiment_root': manifest['experiment_root'], 'original_source':item['source'],
                'source_relative':item['source_relative'], 'source_roi_directory':item['source_roi_directory']}
    return grant, roots, sources


def output_root(roots):
    base = Path(os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR', str(Path.cwd()/'results')))
    root = Path(os.environ.get(OUTPUT_ENV, str(base/'merged_trace_statistics'))).expanduser().resolve()
    localization_store = Path(os.environ.get('CHROMATIN_LOCALIZATION_MERGE_OUTPUT_DIR', str(base/'localization_merges'))).expanduser().resolve()
    forbidden = set(roots) | {merge_root().resolve(), localization_store, p.collection_root().resolve(), a.pearson_root().resolve()}
    forbidden.update(Path(v).expanduser().resolve() for v in os.environ.get(ROOTS_ENV, '').split(os.pathsep) if v)
    if any(root == source or root.is_relative_to(source) for source in forbidden):
        raise PermissionError('Statistics output must be outside original inputs and merge/approval/collection stores')
    return root


def verify_contributions(value, merged, snapshots, grant, source_paths):
    selected = grant['selected_datasets']
    if len(value['sources']) != len(selected): raise ValueError('Merge source selection is incomplete')
    tables = []
    for i, (selected_source, saved) in enumerate(zip(selected, value['sources'])):
        if any(saved.get(k) != v for k, v in selected_source.items()):
            raise ValueError('Merge source order/identity differs from approved datasets')
        with p.run_handle(p.collection_root(), selected_source['collection_run_id']) as fd:
            data = p.read_regular(fd, selected_source['filename'], p.MAX_FILE_BYTES)
        if a.sha(data) != selected_source['sha256']: raise ValueError('Approved source changed')
        path = snapshots/f'source-{i:03d}.ecsv';path.write_bytes(data);path.chmod(0o400)
        tables.append(Table.read(path, format='ascii.ecsv'))
    observed = m.validate_rows(tables, merged, selected)
    contributions = []
    for actual, saved in zip(observed, value['sources']):
        for key in ['row_start','row_stop_exclusive','row_count','roi_mapping','source_metadata_yaml']:
            if actual[key] != saved.get(key): raise ValueError(f'Merge contribution provenance mismatch: {key}')
        if 'source_column_metadata_yaml' in saved and actual['source_column_metadata_yaml'] != saved['source_column_metadata_yaml']:
            raise ValueError('Source column metadata differs from merge provenance')
        contributions.append({k:actual[k] for k in ['index','collection_run_id','manifest_sha256','filename','sha256','roi','rows','roi_mapping']})
        contributions[-1].update(source_paths[actual['collection_run_id'], actual['filename']])
    pairs = len({(m.output_identifier(r),str(t)) for r,t in zip(merged['ROI #'],merged['Trace_ID'])})
    if len(merged) != value['row_count'] or pairs != value['roi_trace_count']:
        raise ValueError('Merged row or ROI/Trace_ID count disagrees with provenance')
    return contributions


def execute_statistics(trace_merge_run_id, merged_sha256, provenance_sha256):
    start = time.perf_counter();run_id = uuid4().hex
    output = None; detail = None; console = io.StringIO(); caught = []
    try:
        source_path = str(merge_root()/trace_merge_run_id/'merged_traces.ecsv')
        value, data, log_sha = read_merge(trace_merge_run_id, merged_sha256, provenance_sha256)
        grant, roots, source_paths = verify_approval(value)
        # Failures are persisted only after the input scope/output directory is verified.
        safe_output = output_root(roots)
        with tempfile.TemporaryDirectory(prefix='merged-trace-statistics-') as temporary:
            snapshots = Path(temporary); path = snapshots/'merged_traces.ecsv';path.write_bytes(data);path.chmod(0o400)
            merged = Table.read(path, format='ascii.ecsv')
            if not set(TRACE_COLUMNS) <= set(merged.colnames): raise ValueError('Merged trace schema is incomplete')
            contributions = verify_contributions(value, merged, snapshots, grant, source_paths)
            output = safe_output
            detail = {'schema_version':1, 'run_id':run_id, 'generated_at_utc':datetime.now(timezone.utc).isoformat(), 'status':'RUNNING', 'scope':'merged_unfiltered_tracing',
                'trace_merge_run_id':trace_merge_run_id,'source_file':source_path,'merged_sha256':merged_sha256,
                'provenance_sha256':provenance_sha256,'merge_native_log_sha256':log_sha,
                'pearson_run_id':value['pearson_run_id'],'pearson_results_sha256':value['results_sha256'],
                'approval_revision':grant['revision'],'approval_fingerprint':grant['fingerprint'],
                'selected_dataset_indices':grant['selected_dataset_indices'],
                'approved_source_contributions':contributions, 'input_mode':'private_read_only_snapshot',
                'row_count':value['row_count'],'roi_trace_count':value['roi_trace_count'],
                'roi_trace_count_source':'verified_step1b1_provenance',
                'original_per_roi_statistics':{'status':'RETAINED_SEPARATELY_IN_STEP0',
                  'note':'This run does not recompute, sum or claim to incorporate original per-ROI native statistics.'},
                'traceratops_version':version('traceratops'),
                'parameters':{},'native_function':'traceratops.trace_stats.compute_trace_statistics',
                'native_module_sha256':digest(Path(statistics.native.__file__)),
                'native_table_module_sha256':digest(Path(inspect.getfile(m.native.ChromatinTraceTable))),
                'warnings':list(value.get('warnings', []))}
            with contextlib.redirect_stderr(console), warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                transcript = io.StringIO()
                try:
                    result = statistics.compute_statistics(path, transcript=transcript)
                finally:
                    console.write(transcript.getvalue().replace(str(path), source_path))
            result['source_file'] = source_path
            result['traceratops_report'] = result['traceratops_report'].replace(str(path), source_path)
            for native_key, provenance_key in [('unique_roi_count','roi_count'),('unique_trace_count','trace_count'),('unique_barcode_count','barcode_count')]:
                if result[native_key] != value[provenance_key]:
                    raise ValueError('Native statistics disagree with saved trace merge counts')
            detail.update(result, status='COMPUTED', global_unique_trace_id_count=result['unique_trace_count'])
            detail['warnings'] += [f'{w.category.__name__}: {w.message}' for w in caught]
            detail['warnings'].append('Trace_ID is nucleus-level; global unique IDs and ROI/Trace_ID pairs are distinct counts, not allele counts.')
            core = {k:detail[k] for k in ['scope','trace_merge_run_id','merged_sha256','provenance_sha256',
                'approval_revision','approval_fingerprint','parameters','native_module_sha256','native_table_module_sha256',
                'traceratops_version','unique_roi_count','global_unique_trace_id_count','unique_barcode_count','roi_trace_count']}
            detail['baseline_fingerprint'] = a.sha(json.dumps(core, sort_keys=True, separators=(',',':')).encode())
            with a.locked_state(value['pearson_run_id']) as (current, _):
                evidence = a.evidence(value['pearson_run_id'], value['results_sha256'])
                if not current or current['revision'] != grant['revision'] or current['status'] != 'APPROVED' or not a.state_matches(current,evidence):
                    raise PermissionError('Scientific approval changed before statistics publication')
                _, _, final_log_sha = read_merge(trace_merge_run_id, merged_sha256, provenance_sha256)
                if final_log_sha != log_sha: raise ValueError('Merge native log changed during statistics execution')
                final = publish(output, run_id, detail, console.getvalue(), start)
        return response(detail, final, start)
    except Exception as exc:
        if detail is not None:
            detail.update(status='ERROR', error_type=type(exc).__name__, error=str(exc)[:500])
            detail['warnings'] += [f'{w.category.__name__}: {w.message}' for w in caught if f'{w.category.__name__}: {w.message}' not in detail['warnings']]
            # Failed/stale runs expose no successful counts or baseline fingerprint.
            for key in ['baseline_fingerprint','global_unique_trace_id_count','unique_trace_count','unique_roi_count','unique_barcode_count']:
                detail.pop(key,None)
            try:
                final = publish(output, run_id, detail, console.getvalue(), start)
                return response(detail, final, start)
            except Exception as saving:
                return MergedStatisticsResult(status='ERROR',run_id=run_id,trace_merge_run_id=trace_merge_run_id,
                    error_type=type(exc).__name__,error=f'{str(exc)[:300]}; failure evidence could not be saved: {str(saving)[:150]}',execution_seconds=time.perf_counter()-start)
        return MergedStatisticsResult(status='ERROR',run_id=run_id,trace_merge_run_id=trace_merge_run_id,
                    error_type=type(exc).__name__,error=str(exc)[:500],execution_seconds=time.perf_counter()-start)


def publish(output, run_id, detail, log, start):
    output.mkdir(parents=True,exist_ok=True)
    detail['execution_seconds'] = time.perf_counter()-start
    with tempfile.TemporaryDirectory(prefix='.pending-merged-statistics-',dir=output) as temporary:
        folder = Path(temporary)/'result';folder.mkdir(mode=0o700)
        (folder/'statistics.json').write_text(json.dumps(detail,indent=2,allow_nan=False))
        (folder/'native.log').write_text(log)
        final = output/run_id
        if final.exists(): raise FileExistsError('Statistics run already exists')
        folder.rename(final)
    return final


def response(detail, final, start):
    notes = detail['warnings']
    success = detail['status']=='COMPUTED'
    return MergedStatisticsResult(status=detail['status'],run_id=detail['run_id'],trace_merge_run_id=detail['trace_merge_run_id'],
        evidence_path=str(final/'statistics.json'),evidence_sha256=digest(final/'statistics.json'),native_log_path=str(final/'native.log'),
        baseline_fingerprint=detail.get('baseline_fingerprint'),row_count=detail['row_count'] if success else None,
        unique_roi_count=detail.get('unique_roi_count'),global_unique_trace_id_count=detail.get('global_unique_trace_id_count'),
        roi_trace_count=detail['roi_trace_count'] if success else None,unique_barcode_count=detail.get('unique_barcode_count'),
        warnings=[n[:320] for n in notes[:4]],warning_count=len(notes),warnings_truncated=len(notes)>4 or any(len(n)>320 for n in notes[:4]),
        error_type=detail.get('error_type'),error=detail.get('error'),execution_seconds=time.perf_counter()-start)


def register_merged_statistics_tool(mcp):
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False,destructive_hint=False,idempotent_hint=False,open_world_hint=False))
    def merged_trace_stats(trace_merge_run_id: Annotated[str,Field(pattern=a.RUN_PATTERN)],
                           merged_sha256: Annotated[str,Field(pattern=a.SHA_PATTERN)],
                           provenance_sha256: Annotated[str,Field(pattern=a.SHA_PATTERN)]) -> MergedStatisticsResult:
        """Save native pre-filtering statistics for an exact approved Step 1b.1 trace merge.

        Verify artifact hashes, source contributions and current human approval.
        Return compact counts and evidence references; no analyzers/report/filtering.
        """
        result = execute_statistics(trace_merge_run_id,merged_sha256,provenance_sha256)
        for _ in range(4):
            size=len(result.model_dump_json().encode())
            if size==result.structured_response_bytes:break
            result.structured_response_bytes=size
        return result
