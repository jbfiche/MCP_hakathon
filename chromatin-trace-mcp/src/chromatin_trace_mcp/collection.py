"""Step 1a.1: safety/provenance adapter around native Traceratops collection."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.metadata
import io
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Literal
from uuid import uuid4

from astropy.table import Table
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from traceratops import collect_files as native

from .step0 import authorized_root, checked_path, identifier, TRACE_COLUMNS, LOCALIZATION_COLUMNS

OUTPUT_ENV = 'CHROMATIN_COLLECTION_OUTPUT_DIR'
SKIP = {'full_pwd', 'PWD_comparison', '.git', '.venv'}
MAX_ENTRIES = 100000
MAX_DEPTH = 12
MAX_FILES = 256
MAX_FILE_BYTES = 100_000_000
MAX_TOTAL_BYTES = 1_000_000_000


class CollectionResult(BaseModel):
    status: Literal['PASS', 'ERROR']
    run_id: str
    phase: Literal['collection_only'] = 'collection_only'
    file_count: int = 0
    total_rows: int = 0
    manifest_path: str | None = None
    manifest_sha256: str | None = None
    files: list[dict] = Field(default_factory=list)
    files_truncated: bool = False
    skipped_symlinks: int = 0
    excluded_directories: int = 0
    execution_seconds: float
    structured_response_bytes: int = 0
    error_type: str | None = None
    error: str | None = None
    failure_path: str | None = None
    next_action: str = 'STOP: review collected files; no Pearson, merge or analyzer was run.'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def collection_output(root):
    raw = os.environ.get(OUTPUT_ENV)
    if not raw:
        trace_output = os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR')
        raw = str(Path(trace_output)/'collections') if trace_output else str(Path.cwd()/'results/collections')
    output = Path(raw).expanduser().resolve()
    if output == root or output.is_relative_to(root):
        raise PermissionError('Collection output must be outside the experiment input tree')
    output.mkdir(parents=True, exist_ok=True)
    return output


def safe_candidates(root, pattern):
    """Bound traversal; native FilePattern alone decides filename matches.

    Non-numeric immediate directories require review rather than silent exclusion.
    Symlinks and excluded output trees are never followed. They do not become
    source files in the explicitly scoped native input view.
    """
    units, files, seen_rois = [], [], set()
    entries = links = excluded = total = 0
    for parent, dirs, names in os.walk(root, followlinks=False):
        here = Path(parent)
        depth = len(here.relative_to(root).parts)
        dirs.sort(); names.sort()
        entries += len(dirs) + len(names)
        if entries > MAX_ENTRIES or depth > MAX_DEPTH:
            raise ValueError('Collection traversal limit exceeded; nothing published')
        for name in list(dirs):
            p = here/name
            if p.is_symlink():
                if here == root and name.isdecimal():
                    raise PermissionError('ROI directory symlinks are not accepted')
                links += 1; dirs.remove(name)
            elif name in SKIP:
                excluded += 1; dirs.remove(name)
            elif here == root:
                if not name.isdecimal():
                    raise ValueError('Immediate collection units must be numeric ROI directories')
                rid = identifier(name)
                if rid in seen_rois:
                    raise ValueError('Duplicate normalized ROI directories')
                seen_rois.add(rid); units.append(name)
        for name in names:
            p = here/name
            if p.is_symlink():
                if here != root and pattern.matches(name):
                    raise PermissionError('Matching symlink inputs are not accepted')
                links += 1
                continue
            if here == root or not pattern.matches(name):
                continue
            checked_path(root, str(p.relative_to(root)))
            if not p.is_file():
                raise ValueError('Selected source is not a regular file')
            size = p.stat().st_size
            total += size
            if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES or len(files) >= MAX_FILES:
                raise ValueError('Collection input byte/file limit exceeded; nothing published')
            files.append(p)
    if not units:
        raise FileNotFoundError('No numeric ROI collection units found')
    return units, files, links, excluded


def snapshot_inputs(root, inputs, sources, kind):
    """Snapshot only eligible ECSV files, preserving relative paths and metadata."""
    records = {}
    required = TRACE_COLUMNS if kind == 'tracing' else LOCALIZATION_COLUMNS
    for source in sources:
        rel = source.relative_to(root)
        before = source.stat()
        checksum = digest(source)
        table = Table.read(source, format='ascii.ecsv')
        if not set(required).issubset(table.colnames):
            raise ValueError(f'Missing required {kind} columns: {rel}')
        roi = identifier(rel.parts[0])
        if len(table) and {identifier(v) for v in table['ROI #']} != {roi}:
            raise ValueError(f'Table ROI identifiers disagree with source directory: {rel}')
        target = inputs/rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or digest(target) != checksum or digest(source) != checksum:
            raise ValueError('Source changed while creating collection snapshot')
        records[str(rel)] = {'source': str(source), 'source_relative': str(rel), 'roi': roi,
                             'source_roi_directory': rel.parts[0], 'sha256': checksum,
                             'size_bytes': before.st_size, 'mtime_ns': before.st_mtime_ns,
                             'rows': len(table), 'columns': list(table.colnames),
                             'empty_table': len(table) == 0}
    return records


def execute_collection(experiment_root, example_file, variable_part=None, table_kind='tracing', rename=False):
    """No Step 0 approval is inferred; collection is an explicit independent call."""
    start = time.perf_counter()
    run_id = uuid4().hex
    output = None
    console = io.StringIO()
    try:
        root = authorized_root(experiment_root)
        if Path(example_file).name != example_file or '/' in example_file or '\\' in example_file or not example_file.endswith('.ecsv'):
            raise ValueError('example_file must be an ECSV basename, not a path or glob')
        if any(c in example_file for c in '*?[]'):
            raise ValueError('Filename globs are not accepted by native collect_files')
        if table_kind not in {'tracing', 'localization'}:
            raise ValueError('table_kind must be tracing or localization')
        pattern = native.build_pattern(example_file, variable_part)
        units, sources, links, excluded = safe_candidates(root, pattern)
        output = collection_output(root)
        with tempfile.TemporaryDirectory(prefix='.pending-collection-', dir=output) as temp:
            work = Path(temp)
            inputs, copied_dir = work/'inputs', work/'collected'
            inputs.mkdir(); copied_dir.mkdir(mode=0o700)
            for unit in units:
                (inputs/unit).mkdir()
            records = snapshot_inputs(root, inputs, sources, table_kind)
            # Native selection/ambiguity/missing/collision/renaming/copy logic.
            with contextlib.redirect_stdout(console), contextlib.redirect_stderr(console):
                copied = native.collect_files(inputs, example_file, copied_dir,
                                              variable_part=variable_part, force=False, rename=rename)
            scan = native.scan_subdirectories(inputs, pattern)
            rename_effective = rename or variable_part is None
            by_name = {native.dest_name(p, unit, rename_effective): records[str(p.relative_to(inputs))]
                       for unit, p in scan.unique.items()}
            if not copied or len(copied) != len(by_name) or {p.name for p in copied} != set(by_name):
                raise ValueError('Native collection output set differs from the selected inputs')
            manifest_files = []
            for target in copied:
                if target.is_symlink() or target.parent != copied_dir:
                    raise PermissionError('Native output escapes the private collection directory')
                record = dict(by_name[target.name])
                table = Table.read(target, format='ascii.ecsv')
                checksum = digest(target)
                if checksum != record['sha256'] or len(table) != record['rows'] or list(table.colnames) != record['columns']:
                    raise ValueError('Collected table differs from its source')
                record.update(destination=str(output/run_id/target.name), destination_name=target.name,
                              destination_sha256=checksum, valid_ecsv=True)
                manifest_files.append(record)
            # Check all inputs again before atomic publication, including native errors/races.
            for record in records.values():
                if digest(Path(record['source'])) != record['sha256']:
                    raise ValueError('Original source changed before collection publication')
            manifest = {'schema_version': 1, 'run_id': run_id, 'phase': 'collection_only',
                        'experiment_root': str(root), 'table_kind': table_kind,
                        'parameters': {'example_file': example_file, 'variable_part': variable_part,
                                       'force': False, 'rename': rename_effective},
                        'scope': {'skipped_symlinks': links, 'excluded_directories': excluded},
                        'traceratops_version': importlib.metadata.version('traceratops'),
                        'native_module_sha256': digest(Path(native.__file__)),
                        'native_functions': ['build_pattern', 'collect_files', 'scan_subdirectories', 'dest_name'],
                        'files': manifest_files, 'next_action': 'STOP_REVIEW_COLLECTION'}
            manifest_file = copied_dir/'manifest.json'
            manifest_file.write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding='utf-8')
            (copied_dir/'native.log').write_text(console.getvalue(), encoding='utf-8')
            checksum = digest(manifest_file)
            copied_dir.rename(output/run_id)
        return CollectionResult(status='PASS', run_id=run_id, file_count=len(manifest_files),
                                total_rows=sum(f['rows'] for f in manifest_files),
                                manifest_path=str(output/run_id/'manifest.json'), manifest_sha256=checksum,
                                files=[{k: f[k] for k in ('roi', 'source_relative', 'destination_name', 'rows', 'sha256')} for f in manifest_files[:10]],
                                files_truncated=len(manifest_files)>10, skipped_symlinks=links,
                                excluded_directories=excluded, execution_seconds=time.perf_counter()-start)
    except Exception as exc:
        failure = None
        if output is not None:
            failure = output/(run_id+'.failure.json')
            try:
                failure.write_text(json.dumps({'run_id': run_id, 'status': 'ERROR', 'error_type': type(exc).__name__,
                                              'error': str(exc), 'native_log': console.getvalue()}), encoding='utf-8')
            except OSError:
                failure = None
        return CollectionResult(status='ERROR', run_id=run_id, error_type=type(exc).__name__,
                                error=str(exc)[:500], failure_path=str(failure) if failure else None,
                                execution_seconds=time.perf_counter()-start)


def register_collection_tool(mcp):
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                         idempotent_hint=False, open_world_hint=False))
    async def collect_files(experiment_root: str, example_file: str,
                            variable_part: str | None = None,
                            table_kind: Literal['tracing', 'localization'] = 'tracing',
                            rename: bool = False) -> CollectionResult:
        """Step 1a.1 only: collect ROI ECSV files using native Traceratops; return provenance.

        Exact names are automatically ROI-renamed. Variable matching has fixed
        substring length. Missing/ambiguous matches fail; force-skipping is disabled.
        A fresh configured output directory is used, never caller-selected inputs.
        Does not run Pearson, merging, analyzers, or imply scientific approval.
        """
        result = execute_collection(experiment_root, example_file, variable_part, table_kind, rename)
        while len(result.model_dump_json().encode()) > 12000 and result.files:
            result.files.pop()
            result.files_truncated = True
        for _ in range(4):
            size = len(result.model_dump_json().encode())
            if size == result.structured_response_bytes:
                break
            result.structured_response_bytes = size
        return result
