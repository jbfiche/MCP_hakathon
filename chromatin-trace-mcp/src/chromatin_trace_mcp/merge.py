"""Step 1b.1: merge exact human-approved snapshots through native Traceratops."""
from __future__ import annotations

import contextlib
import importlib.metadata
import inspect
import io
import json
import os
import tempfile
import time
import warnings
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import numpy as np
from astropy.io.misc import yaml
from astropy.table import Table
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, StrictInt
from traceratops import trace_merge as native

from . import approval as a, pearsons as p
from .collection import digest
from .step0 import TRACE_COLUMNS, identifier

OUTPUT_ENV = 'CHROMATIN_MERGE_OUTPUT_DIR'


class MergeResult(BaseModel):
    status: Literal['MERGED', 'ERROR']
    run_id: str
    phase: Literal['trace_merge_only'] = 'trace_merge_only'
    merged_path: str | None = None
    provenance_path: str | None = None
    merged_sha256: str | None = None
    source_file_count: int = 0
    row_count: int = 0
    barcode_count: int = 0
    trace_count: int = 0
    roi_trace_count: int = 0
    roi_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    warning_count: int = 0
    warnings_truncated: bool = False
    execution_seconds: float
    structured_response_bytes: int = 0
    error_type: str | None = None
    error: str | None = None
    next_action: str = 'STOP. Review the trace merge. Localization merging and analyzers are not invoked.'


def scientific_metadata(tables):
    """Only compatibility checks, no conversion or inferred biological metadata."""
    declared = {'xyz_unit':set(), 'genome_assembly':set()}
    for table in tables:
        for key in declared:
            if key in table.meta:
                declared[key].add(str(table.meta[key]))
            comments = table.meta.get('comments', [])
            if isinstance(comments, str): comments = [comments]
            for comment in comments:
                if isinstance(comment, str) and comment.startswith(key+'='):
                    declared[key].add(comment.split('=', 1)[1].strip())
        for axis in ('x','y','z'):
            unit = table[axis].unit
            if unit is not None:
                declared['xyz_unit'].add(str(unit))
    for key, values in declared.items():
        if len(values)>1:
            raise ValueError(f'Conflicting {key} declarations; no scientific conversion or correction is performed')
    return declared


def output_identifier(value):
    """Label native integer-valued float IDs in summaries; never alter table values."""
    if isinstance(value, (float, np.floating)) and np.isfinite(value) and float(value).is_integer():
        return str(int(value))
    return identifier(value)


def column_metadata(table):
    return {name:{'unit':table[name].unit, 'description':table[name].description,
                  'format':table[name].format, 'meta':table[name].meta} for name in table.colnames}


def validate_rows(inputs, merged, selected):
    if len(merged) != sum(len(t) for t in inputs):
        raise ValueError('Native merged row count differs from approved input contributions')
    contributions, offset = [], 0
    for table, source in zip(inputs, selected):
        end = offset+len(table)
        part = merged[offset:end]
        if not set(table.colnames) <= set(merged.colnames):
            raise ValueError('Native merge lost input columns')
        for name in table.colnames:
            if table[name].unit is not None and table[name].unit != merged[name].unit:
                raise ValueError(f'Native merge changed scientific unit for column {name}')
            if name == 'ROI #':
                continue
            left, right = np.ma.asarray(table[name]), np.ma.asarray(part[name])
            np.testing.assert_array_equal(np.ma.getmaskarray(left), np.ma.getmaskarray(right))
            valid = ~np.ma.getmaskarray(left)
            np.testing.assert_equal(np.asarray(left)[valid], np.asarray(right)[valid], err_msg=f'Native merge changed {name}')
        mapping = {}
        for old, new in zip(table['ROI #'], part['ROI #']):
            mapping.setdefault(identifier(old), set()).add(output_identifier(new))
        mapping = {key:sorted(values) for key,values in mapping.items()}
        contributions.append({**source, 'row_start':offset, 'row_stop_exclusive':end,
                              'row_count':len(table), 'roi_mapping':mapping,
                              'source_metadata_yaml':yaml.dump(table.meta),
                              'source_column_metadata_yaml':yaml.dump(column_metadata(table))})
        offset = end
    return contributions


def execute_merge(pearson_run_id, results_sha256, selected_dataset_indices):
    start = time.perf_counter(); run_id = uuid4().hex
    try:
        if any(type(i) is not int for i in selected_dataset_indices) or len(selected_dataset_indices)<2:
            raise ValueError('Merge requires at least two explicitly approved dataset indices')
        context = a.prepare_review(pearson_run_id, results_sha256)
        parameters = context.evidence['binding']['parameters'] if context.evidence else {}
        grant = a.require_scientific_approval(pearson_run_id, results_sha256, selected_dataset_indices, parameters)
        selected = grant['selected_datasets']
        base = os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR')
        output = Path(os.environ.get(OUTPUT_ENV) or (str(Path(base)/'trace_merges') if base else str(Path.cwd()/'results/trace_merges'))).expanduser().resolve()
        forbidden = [p.collection_root().resolve(), a.pearson_root().resolve()]
        for ref in grant['evidence']['collection_references']:
            with p.run_handle(p.collection_root(), ref['collection_run_id']) as fd:
                manifest = json.loads(p.read_regular(fd, 'manifest.json', p.MAX_MANIFEST_BYTES))
                forbidden.append(Path(manifest['experiment_root']).resolve())
        if any(output == root or output.is_relative_to(root) for root in forbidden):
            raise PermissionError('Merge output must be outside original inputs, collections and Pearson/approval evidence')
        with tempfile.TemporaryDirectory(prefix='approved-merge-inputs-') as temporary:
            inputs = Path(temporary); snapshots=[]; tables=[]
            for number, source in enumerate(selected):
                with p.run_handle(p.collection_root(), source['collection_run_id']) as fd:
                    data = p.read_regular(fd, source['filename'], p.MAX_FILE_BYTES)
                if a.sha(data) != source['sha256']:
                    raise ValueError('Approved input changed before snapshot')
                snapshot = inputs/f'{number:03d}.ecsv'; snapshot.write_bytes(data); snapshot.chmod(0o400)
                table = Table.read(snapshot, format='ascii.ecsv')
                if not set(TRACE_COLUMNS)<=set(table.colnames) or len(table)!=source['rows']:
                    raise ValueError('Approved input schema or rows changed')
                if len(table) and {identifier(v) for v in table['ROI #']} != {source['roi']}:
                    raise ValueError('Approved input ROI provenance disagrees with table')
                snapshots.append(str(snapshot)); tables.append(table)
            declared = scientific_metadata(tables)
            notes=[]
            if any(any(not values for values in scientific_metadata([table]).values()) for table in tables):
                notes.append('Input coordinate unit or genome assembly is not fully declared; native defaults are not independent scientific verification.')
            metadata_keys = set().union(*(table.meta for table in tables)) - {'comments','xyz_unit','genome_assembly'}
            for key in sorted(metadata_keys):
                values = {yaml.dump(table.meta[key]) for table in tables if key in table.meta}
                if len(values)>1:
                    notes.append(f'Native reconciliation of differing metadata {key!r}; complete per-source metadata is preserved in provenance.')
            output.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.pending-trace-merge-', dir=output) as work:
                results = Path(work)/'results'; results.mkdir(mode=0o700)
                console=io.StringIO()
                with contextlib.redirect_stdout(console), contextlib.redirect_stderr(console), warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    traces = native.load_traces(snapshots, verbose=False)
                    path = results/'merged_traces.ecsv'
                    traces.save(str(path), comments='appended_trace_files='+str(traces.number_traces))
                notes += sorted({f'{w.category.__name__}: {w.message}' for w in caught})
                merged = Table.read(path, format='ascii.ecsv')
                if traces.number_traces != len(selected):
                    raise ValueError('Native merge did not include every selected dataset')
                contributions = validate_rows(tables, merged, selected)
                output_metadata = scientific_metadata([merged])
                for key, values in declared.items():
                    if values and output_metadata[key] != values:
                        raise ValueError(f'Native merge introduced conflicting {key} metadata; output is not published')
                if any(any(values != [old] for old,values in c['roi_mapping'].items()) for c in contributions):
                    notes.append('Native merge renumbered colliding ROI IDs; exact input-to-output mappings and row ranges are in provenance.')
                if merged['ROI #'].dtype.kind == 'f':
                    notes.append('Native merge promoted ROI IDs to floating point (for example with empty inputs); integer-valued labels are normalized only in summaries, not in the ECSV.')
                trace_ids = {str(v) for v in merged['Trace_ID']}
                roi_traces = {(output_identifier(r),str(t)) for r,t in zip(merged['ROI #'],merged['Trace_ID'])}
                if len(roi_traces)>len(trace_ids):
                    notes.append('Trace_ID values repeat across output ROIs. Global unique-ID count differs from ROI/Trace_ID count; identifiers were not relabeled.')
                notes.append('Trace_ID is nucleus-level; merge preserves repeated barcodes and does not separate alleles or filter observations.')
                detail = {'schema_version':1, 'run_id':run_id, 'phase':'trace_merge_only',
                          'pearson_run_id':pearson_run_id, 'results_sha256':results_sha256,
                          'approval_revision':grant['revision'], 'approval_fingerprint':grant['fingerprint'],
                          'approval_snapshot':grant,
                          'selected_dataset_indices':selected_dataset_indices, 'collection_references':grant['selected_collection_references'],
                          'pearson_parameters':parameters, 'merge_policy':'native-trace-merge-v1',
                          'native_functions':['trace_merge.load_traces','ChromatinTraceTable.save'],
                          'native_module_sha256':digest(Path(native.__file__)),
                          'native_table_module_sha256':digest(Path(inspect.getfile(native.ChromatinTraceTable))),
                          'traceratops_version':importlib.metadata.version('traceratops'),
                          'sources':contributions, 'merged_metadata_yaml':yaml.dump(merged.meta),
                          'merged_column_metadata_yaml':yaml.dump(column_metadata(merged)),
                          'merged_sha256':digest(path), 'row_count':len(merged), 'output_roi_dtype':str(merged['ROI #'].dtype),
                          'barcode_count':len(set(output_identifier(v) for v in merged['Barcode #'])),
                          'trace_count':len(trace_ids), 'roi_trace_count':len(roi_traces),
                          'roi_count':len(set(output_identifier(v) for v in merged['ROI #'])),
                          'warnings':notes, 'artifacts':{'merged':'merged_traces.ecsv','native_log':'native.log'}}
                (results/'provenance.json').write_text(json.dumps(detail, indent=2, allow_nan=False))
                (results/'native.log').write_text(console.getvalue())
                latest = a.require_scientific_approval(pearson_run_id, results_sha256, selected_dataset_indices, parameters)
                if latest['revision'] != grant['revision']:
                    raise PermissionError('Scientific approval changed during merging')
                with a.locked_state(pearson_run_id) as (current, _):
                    # Hash again under the decision lock; immutable snapshots supply all native input.
                    ev = a.evidence(pearson_run_id, results_sha256)
                    if not current or current['revision'] != grant['revision'] or not a.state_matches(current, ev) or current['status']!='APPROVED':
                        raise PermissionError('Scientific approval or evidence changed before publication')
                    final=output/run_id
                    if final.exists(): raise FileExistsError('Merge run already exists')
                    results.rename(final)
        return MergeResult(status='MERGED',run_id=run_id,merged_path=str(final/'merged_traces.ecsv'),
                           provenance_path=str(final/'provenance.json'), merged_sha256=detail['merged_sha256'],
                           source_file_count=len(selected), row_count=detail['row_count'], barcode_count=detail['barcode_count'],
                           trace_count=detail['trace_count'],roi_trace_count=detail['roi_trace_count'],roi_count=detail['roi_count'],
                           warnings=notes[:4],warning_count=len(notes),warnings_truncated=len(notes)>4,
                           execution_seconds=time.perf_counter()-start)
    except Exception as exc:
        return MergeResult(status='ERROR',run_id=run_id,error_type=type(exc).__name__,error=str(exc)[:500],execution_seconds=time.perf_counter()-start)


def register_merge_tool(mcp):
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
    def trace_merge(pearson_run_id: Annotated[str,Field(pattern=a.RUN_PATTERN)],
                    results_sha256: Annotated[str,Field(pattern=a.SHA_PATTERN)],
                    selected_dataset_indices: Annotated[list[StrictInt],Field(min_length=2,max_length=p.MAX_FILES)]) -> MergeResult:
        """Merge only the exact human-approved tracing selection, using native Traceratops.

        Revalidates Pearson/collection evidence and approval before publication.
        Returns counts and ECSV/provenance paths, never full tables. No new decision,
        localization merge, filtering, allele separation or analyzer is performed.
        """
        result=execute_merge(pearson_run_id,results_sha256,selected_dataset_indices)
        for _ in range(4):
            size=len(result.model_dump_json().encode())
            if size==result.structured_response_bytes: break
            result.structured_response_bytes=size
        return result
