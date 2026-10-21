"""Step 1b.2: native localization merging scoped to approved source tracing ROIs."""
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
from traceratops import localization_merge as native

from . import approval as a, pearsons as p
from .collection import digest, MAX_FILES as COLLECTION_MAX_FILES, MAX_TOTAL_BYTES
from .merge import column_metadata, output_identifier, validate_rows
from .step0 import LOCALIZATION_COLUMNS, identifier

OUTPUT_ENV = 'CHROMATIN_LOCALIZATION_MERGE_OUTPUT_DIR'


class LocalizationMergeResult(BaseModel):
    status: Literal['MERGED', 'ERROR']
    run_id: str
    phase: Literal['localization_merge_only'] = 'localization_merge_only'
    merged_path: str | None = None
    provenance_path: str | None = None
    merged_sha256: str | None = None
    provenance_sha256: str | None = None
    source_file_count: int = 0
    row_count: int = 0
    barcode_count: int = 0
    roi_count: int = 0
    localization_id_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    warning_count: int = 0
    warnings_truncated: bool = False
    execution_seconds: float
    structured_response_bytes: int = 0
    error_type: str | None = None
    error: str | None = None
    next_action: str = 'STOP. Review localization merge and provenance. No analyzer, statistics workflow or filtering was invoked.'


def manifest(ref, kind):
    with p.run_handle(p.collection_root(), ref.collection_run_id) as fd:
        content = p.read_regular(fd, 'manifest.json', p.MAX_MANIFEST_BYTES)
    if a.sha(content) != ref.manifest_sha256:
        raise ValueError('Collection manifest checksum mismatch')
    value = json.loads(content)
    if (value.get('schema_version') != 1 or value.get('run_id') != ref.collection_run_id
            or value.get('phase') != 'collection_only' or value.get('table_kind') != kind):
        raise ValueError(f'Expected a validated {kind} collection manifest')
    if not isinstance(value.get('files'), list) or not 1 <= len(value['files']) <= COLLECTION_MAX_FILES:
        raise ValueError('Invalid collection file count')
    return value


def source_key(value, item):
    """Identity is the original experiment plus its ROI directory, never renamed output."""
    root = Path(value['experiment_root'])
    rel = Path(item['source_relative'])
    directory = item['source_roi_directory']
    if (not root.is_absolute() or not rel.parts or rel.is_absolute() or '..' in rel.parts
            or rel.parts[0] != directory or not directory.isdecimal()
            or identifier(directory) != item['roi'] or Path(item['source']) != root / rel):
        raise ValueError('Inconsistent original experiment/source ROI provenance')
    return str(root.resolve()), identifier(directory)


def associations(grant, refs):
    """Resolve an exact one-to-one source mapping from hash-verified manifests."""
    tracing = {}
    for raw in grant['selected_collection_references']:
        ref = p.CollectionReference.model_validate(raw)
        value = manifest(ref, 'tracing')
        tracing[ref.collection_run_id] = value
    approved = []
    for selected in grant['selected_datasets']:
        value = tracing[selected['collection_run_id']]
        items = [item for item in value['files'] if item['destination_name'] == selected['filename']]
        if len(items) != 1 or items[0]['sha256'] != selected['sha256']:
            raise ValueError('Approved trace source provenance is ambiguous or changed')
        approved.append((selected, source_key(value, items[0]), items[0]))
    keys = [key for _, key, _ in approved]
    if len(set(keys)) != len(keys):
        raise ValueError('Multiple approved tracing datasets map to the same original experiment ROI')
    if len({key[1] for key in keys}) != len(keys):
        raise ValueError('Colliding source ROI IDs across experiments: native localization merging does not renumber ROIs, unlike trace merging; cannot publish aligned output')
    candidates = {}
    roots = set()
    for ref in refs:
        value = manifest(ref, 'localization')
        roots.add(Path(value['experiment_root']).resolve())
        names = set()
        for item in value['files']:
            name = item['destination_name']
            if (Path(name).name != name or not name.endswith('.ecsv') or name in names
                    or Path(item['destination']) != p.collection_root()/ref.collection_run_id/name
                    or item.get('valid_ecsv') is not True or item.get('sha256') != item.get('destination_sha256')):
                raise ValueError('Invalid localization collection entry')
            names.add(name)
            key = source_key(value, item)
            candidates.setdefault(key, []).append((ref, item))
    mapped = []
    for selected, key, trace in approved:
        matches = candidates.get(key, [])
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one localization table for approved original ROI {key[1]}; found {len(matches)}')
        ref, item = matches[0]
        mapped.append({'approved_trace_index': selected['index'], 'trace_collection_run_id': selected['collection_run_id'],
                       'trace_filename': selected['filename'], 'trace_sha256': selected['sha256'],
                       'trace_source': trace['source'], 'experiment_root': key[0],
                       'source_roi_directory': item['source_roi_directory'], 'source_relative': item['source_relative'],
                       'source': item['source'], 'roi': key[1], 'collection_run_id': ref.collection_run_id,
                       'manifest_sha256': ref.manifest_sha256, 'filename': item['destination_name'],
                       'sha256': item['sha256'], 'rows': item['rows']})
    roots.update(Path(key[0]) for key in keys)
    return mapped, roots


def read_selected(mapped):
    total = 0
    contents = []
    for item in mapped:
        with p.run_handle(p.collection_root(), item['collection_run_id']) as fd:
            data = p.read_regular(fd, item['filename'], p.MAX_FILE_BYTES)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError('Localization input byte limit exceeded')
        if a.sha(data) != item['sha256']:
            raise ValueError('Collected localization checksum mismatch')
        contents.append(data)
    return contents


def metadata_contract(tables):
    declared = {'xyz_unit': set(), 'genome_assembly': set()}
    for table in tables:
        for key in declared:
            if key in table.meta:
                declared[key].add(str(table.meta[key]))
            comments = table.meta.get('comments', [])
            if isinstance(comments, str): comments = [comments]
            for comment in comments:
                if isinstance(comment, str) and comment.startswith(key+'='):
                    declared[key].add(comment.split('=', 1)[1].strip())
        for axis in ('xcentroid', 'ycentroid', 'zcentroid'):
            if table[axis].unit is not None:
                declared['xyz_unit'].add(str(table[axis].unit))
    for key, values in declared.items():
        if len(values) > 1:
            raise ValueError(f'Conflicting {key} declarations; no scientific conversion is performed')
    for name in set().union(*(set(t.colnames) for t in tables)):
        units = {str(t[name].unit) for t in tables if name in t.colnames and t[name].unit is not None}
        if len(units) > 1:
            raise ValueError(f'Conflicting column units: {name}')
    return declared


def execute_localization_merge(pearson_run_id, results_sha256, selected_dataset_indices, localization_collections):
    start = time.perf_counter(); run_id = uuid4().hex
    try:
        if any(type(i) is not int for i in selected_dataset_indices) or not 2 <= len(selected_dataset_indices) <= p.MAX_FILES:
            raise ValueError('Native localization merging requires at least two approved tracing datasets')
        refs = [p.CollectionReference.model_validate(r) for r in localization_collections]
        if not 1 <= len(refs) <= 8 or len({r.collection_run_id for r in refs}) != len(refs):
            raise ValueError('Use 1 to 8 unique localization collection references')
        context = a.prepare_review(pearson_run_id, results_sha256)
        parameters = context.evidence['binding']['parameters'] if context.evidence else {}
        grant = a.require_scientific_approval(pearson_run_id, results_sha256, selected_dataset_indices, parameters)
        mapped, source_roots = associations(grant, refs)
        base = Path(os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR', str(Path.cwd()/'results')))
        output = Path(os.environ.get(OUTPUT_ENV, str(base/'localization_merges'))).expanduser().resolve()
        forbidden = source_roots | {p.collection_root().resolve(), a.pearson_root().resolve()}
        if any(output == root or output.is_relative_to(root) for root in forbidden):
            raise PermissionError('Localization merge output must be outside original inputs and evidence stores')
        data = read_selected(mapped)
        with tempfile.TemporaryDirectory(prefix='approved-localization-inputs-') as temporary:
            snapshots, tables = [], []
            for i, (item, content) in enumerate(zip(mapped, data)):
                path = Path(temporary)/f'{i:03d}.ecsv'; path.write_bytes(content); path.chmod(0o400)
                table = Table.read(path, format='ascii.ecsv')
                if not set(LOCALIZATION_COLUMNS) <= set(table.colnames) or len(table) != item['rows']:
                    raise ValueError('Localization schema or row count disagrees with collection provenance')
                if len(table) and {identifier(v) for v in table['ROI #']} != {item['roi']}:
                    raise ValueError('Localization table ROI disagrees with original source provenance')
                snapshots.append(str(path)); tables.append(table)
            declared = metadata_contract(tables)
            notes = ['Approval covers the tracing source ROI selection. Localization bytes are bound by collection hashes for this execution, not by the earlier Pearson human decision.']
            if any(any(not values for values in metadata_contract([t]).values()) for t in tables):
                notes.append('Coordinate unit or genome assembly is not fully declared; no metadata inference or conversion was performed.')
            for key in sorted(set().union(*(t.meta for t in tables)) - {'comments','xyz_unit','genome_assembly'}):
                if len({yaml.dump(t.meta[key]) for t in tables if key in t.meta}) > 1:
                    notes.append(f'Native metadata reconciliation for {key!r}; full source metadata is preserved in provenance.')
            output.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.pending-localization-merge-', dir=output) as work:
                results = Path(work)/'results'; results.mkdir(mode=0o700)
                path = results/'merged_localizations.ecsv'; console = io.StringIO()
                with contextlib.redirect_stdout(console), contextlib.redirect_stderr(console), warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    native.run({'loc_files': snapshots, 'outputFolder': str(results), 'output_file': path.name})
                notes += sorted({f'{w.category.__name__}: {w.message}' for w in caught})
                merged = Table.read(path, format='ascii.ecsv')
                contributions = validate_rows(tables, merged, mapped)
                offset = 0
                for table in tables:
                    np.testing.assert_array_equal(table['ROI #'], merged['ROI #'][offset:offset+len(table)])
                    offset += len(table)
                if metadata_contract([merged]) != declared:
                    raise ValueError('Native output changed declared scientific metadata')
                ids = {str(v) for v in merged['Buid']}
                if len(ids) < len(merged):
                    notes.append('Buid values repeat in merged localizations; preserve source/row provenance when joining Spot_ID to Buid. No identifiers were relabeled.')
                detail = {'schema_version':1, 'phase':'localization_merge_only', 'run_id':run_id,
                          'pearson_run_id':pearson_run_id, 'results_sha256':results_sha256,
                          'approval_revision':grant['revision'], 'approval_fingerprint':grant['fingerprint'], 'approval_snapshot':grant,
                          'selected_dataset_indices':selected_dataset_indices, 'localization_collections':[r.model_dump() for r in refs],
                          'authorization_scope':'human-approved-original-experiment-and-tracing-ROI-selection',
                          'localization_evidence_scope':'execution-snapshot-hashes-not-Pearson-reviewed-localization-bytes',
                          'merge_policy':'native-localization-merge-v1', 'sources':contributions,
                          'native_functions':['localization_merge.run','LocalizationTable.append','LocalizationTable.save'],
                          'native_module_sha256':digest(Path(native.__file__)),
                          'native_table_module_sha256':digest(Path(inspect.getfile(native.LocalizationTable))),
                          'traceratops_version':importlib.metadata.version('traceratops'),
                          'merged_sha256':digest(path), 'row_count':len(merged),
                          'barcode_count':len({output_identifier(v) for v in merged['Barcode #']}),
                          'roi_count':len({output_identifier(v) for v in merged['ROI #']}), 'localization_id_count':len(ids),
                          'merged_metadata_yaml':yaml.dump(merged.meta), 'merged_column_metadata_yaml':yaml.dump(column_metadata(merged)),
                          'warnings':notes, 'artifacts':{'merged':'merged_localizations.ecsv','native_log':'native.log'}}
                (results/'provenance.json').write_text(json.dumps(detail, indent=2, allow_nan=False))
                (results/'native.log').write_text(console.getvalue())
                latest = a.require_scientific_approval(pearson_run_id, results_sha256, selected_dataset_indices, parameters)
                if latest['revision'] != grant['revision']:
                    raise PermissionError('Scientific approval changed during localization merging')
                with a.locked_state(pearson_run_id) as (current, _):
                    ev = a.evidence(pearson_run_id, results_sha256)
                    if not current or current['revision'] != grant['revision'] or current['status'] != 'APPROVED' or not a.state_matches(current, ev):
                        raise PermissionError('Approval/evidence changed before publication')
                    latest_mapped, _ = associations(grant, refs)
                    if latest_mapped != mapped: raise ValueError('Localization association changed before publication')
                    read_selected(latest_mapped)
                    final = output/run_id
                    if final.exists(): raise FileExistsError('Localization merge run already exists')
                    results.rename(final)
        return LocalizationMergeResult(status='MERGED', run_id=run_id, merged_path=str(final/path.name),
                 provenance_path=str(final/'provenance.json'), merged_sha256=detail['merged_sha256'],
                 provenance_sha256=digest(final/'provenance.json'), source_file_count=len(mapped), row_count=detail['row_count'],
                 barcode_count=detail['barcode_count'], roi_count=detail['roi_count'], localization_id_count=len(ids),
                 warnings=notes[:4], warning_count=len(notes), warnings_truncated=len(notes)>4, execution_seconds=time.perf_counter()-start)
    except (Exception, SystemExit) as exc:
        return LocalizationMergeResult(status='ERROR', run_id=run_id, error_type=type(exc).__name__, error=str(exc)[:500], execution_seconds=time.perf_counter()-start)


def register_localization_merge_tool(mcp):
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
    def localization_merge(pearson_run_id: Annotated[str, Field(pattern=a.RUN_PATTERN)],
                           results_sha256: Annotated[str, Field(pattern=a.SHA_PATTERN)],
                           selected_dataset_indices: Annotated[list[StrictInt], Field(min_length=2, max_length=p.MAX_FILES)],
                           localization_collections: Annotated[list[p.CollectionReference], Field(min_length=1, max_length=8)]) -> LocalizationMergeResult:
        """Merge localization collections for the exact human-approved tracing source ROIs.

        Match original experiment/ROI provenance, hash-check snapshots and approval,
        then run native Traceratops. Return compact counts/artifact paths only.
        No trace merge, statistics workflow, filtering or analyzers are invoked.
        """
        result = execute_localization_merge(pearson_run_id, results_sha256, selected_dataset_indices, localization_collections)
        for _ in range(4):
            size = len(result.model_dump_json().encode())
            if size == result.structured_response_bytes: break
            result.structured_response_bytes = size
        return result
