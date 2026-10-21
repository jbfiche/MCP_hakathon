"""Step 1a.2: native Pearson QC of verified collection snapshots, no approval logic."""
from __future__ import annotations
import contextlib
import importlib.metadata
import io
import json
import os
import re
import stat
import tempfile
import time
import warnings
from collections import Counter
from pathlib import Path
from typing import Literal
from uuid import uuid4

import numpy as np
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field
from traceratops import trace_pearsons as native

from .collection import OUTPUT_ENV as COLLECTION_ENV, digest, MAX_FILE_BYTES, MAX_TOTAL_BYTES
from .step0 import TRACE_COLUMNS, identifier
from .pearson_reporting import format_pearson_report, COMPARISON_PREVIEW_LIMIT, WARNING_PREVIEW_LIMIT

OUTPUT_ENV = 'CHROMATIN_PEARSON_OUTPUT_DIR'
MAX_FILES = 32
MAX_MANIFEST_BYTES = 16_000_000


class CollectionReference(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    collection_run_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    manifest_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class PearsonResult(BaseModel):
    status: Literal['COMPUTED', 'ERROR']
    run_id: str
    phase: Literal['pearson_qc_only'] = 'pearson_qc_only'
    review_required: bool = True
    dataset_count: int = 0
    datasets: list[dict] = Field(default_factory=list)
    comparison_count: int = 0
    undefined_comparisons: int = 0
    comparisons: list[dict] = Field(default_factory=list)
    comparisons_truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    warning_count: int = 0
    warnings_truncated: bool = False
    results_path: str | None = None
    report_path: str | None = None
    matrix_path: str | None = None
    figure_path: str | None = None
    results_sha256: str | None = None
    execution_seconds: float
    structured_response_bytes: int = 0
    error_type: str | None = None
    error: str | None = None
    next_action: str = 'STOP: user review required. No scientific approval or downstream processing performed.'


def collection_root():
    raw = os.environ.get(COLLECTION_ENV)
    if not raw:
        base = os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR')
        raw = str(Path(base)/'collections') if base else str(Path.cwd()/'results/collections')
    root = Path(raw).expanduser().absolute()
    if root.is_symlink(): raise PermissionError('Collection store must not be a symlink')
    return root


@contextlib.contextmanager
def run_handle(root, run_id):
    if not re.fullmatch(r'[a-f0-9]{32}', run_id): raise ValueError('Invalid collection run ID')
    top = os.open(root, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        fd = os.open(run_id, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW, dir_fd=top)
        try: yield fd
        finally: os.close(fd)
    finally: os.close(top)


def read_regular(fd, name, limit):
    if Path(name).name != name or '/' in name or '\\' in name: raise ValueError('Artifact name must be a basename')
    handle = os.open(name, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(handle, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError('Collection artifact is not a bounded regular file')
        data = stream.read(limit+1)
        after = os.fstat(stream.fileno())
        if len(data)>limit or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise ValueError('Collection artifact changed during read or exceeds limit')
    return data


def load_inputs(refs, inputs):
    import hashlib
    root = collection_root()
    records, manifests, sources, seen = [], [], [], set()
    total = 0
    for ref in refs:
        if ref.collection_run_id in seen: raise ValueError('Duplicate collection reference')
        seen.add(ref.collection_run_id)
        with run_handle(root, ref.collection_run_id) as fd:
            data = read_regular(fd, 'manifest.json', MAX_MANIFEST_BYTES)
            if hashlib.sha256(data).hexdigest()!=ref.manifest_sha256: raise ValueError('Collection manifest checksum mismatch')
            manifest = json.loads(data)
            if manifest.get('schema_version')!=1 or manifest.get('run_id')!=ref.collection_run_id or manifest.get('phase')!='collection_only' or manifest.get('table_kind')!='tracing':
                raise ValueError('Expected a schema-v1 validated tracing collection manifest')
            files = manifest.get('files')
            if not isinstance(files,list) or not files: raise ValueError('Collection manifest has no files')
            manifests.append(ref.model_dump())
            sources.append(Path(manifest['experiment_root']).resolve())
            names = set()
            for item in files:
                if len(records)>=MAX_FILES: raise ValueError('Pearson dataset limit exceeded')
                name = item['destination_name']
                if not name.endswith('.ecsv') or name in names: raise ValueError('Invalid/duplicate collected filename')
                names.add(name)
                expected = root/ref.collection_run_id/name
                if Path(item['destination'])!=expected: raise ValueError('Manifest destination escapes its collection run')
                if item.get('valid_ecsv') is not True or item.get('destination_sha256')!=item.get('sha256'):
                    raise ValueError('Manifest does not describe a verified copied ECSV')
                content = read_regular(fd, name, MAX_FILE_BYTES)
                total += len(content)
                if total>MAX_TOTAL_BYTES: raise ValueError('Pearson input byte limit exceeded')
                if hashlib.sha256(content).hexdigest()!=item['sha256']: raise ValueError('Collected file checksum mismatch')
                path = inputs/f'{len(records):03d}.ecsv'
                path.write_bytes(content)
                records.append({'label':name, 'key':str(expected), 'roi':item['roi'],
                                'collection_run_id':ref.collection_run_id, 'sha256':item['sha256'],
                                'rows':item['rows'], 'columns':item['columns'], 'snapshot':path})
    if len(records)<2: raise ValueError('At least two collected trace datasets are required for comparison')
    return records, manifests, sources


def verify_sources(records, refs):
    import hashlib
    root=collection_root()
    for ref in refs:
        with run_handle(root,ref.collection_run_id) as fd:
            if hashlib.sha256(read_regular(fd,'manifest.json',MAX_MANIFEST_BYTES)).hexdigest()!=ref.manifest_sha256:
                raise ValueError('Collection manifest changed during Pearson execution')
            for record in records:
                if record['collection_run_id']==ref.collection_run_id and hashlib.sha256(read_regular(fd,record['label'],MAX_FILE_BYTES)).hexdigest()!=record['sha256']:
                    raise ValueError('Collected input changed during Pearson execution')


def json_number(value): return float(value) if np.isfinite(value) else None


def execute_pearsons(collections, output_format='png'):
    start=time.perf_counter();run_id=uuid4().hex
    try:
        refs=[r if isinstance(r,CollectionReference) else CollectionReference.model_validate(r) for r in collections]
        if not 1<=len(refs)<=8: raise ValueError('Use 1 to 8 collection manifests')
        if output_format not in {'png','svg','pdf'}: raise ValueError('Unsupported native figure format')
        collection_store=collection_root().resolve()
        base=os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR')
        output=Path(os.environ.get(OUTPUT_ENV) or (str(Path(base)/'pearson_qc') if base else str(Path.cwd()/'results/pearson_qc'))).expanduser().resolve()
        if output==collection_store or output.is_relative_to(collection_store): raise PermissionError('Pearson output must be outside the collection store')
        with tempfile.TemporaryDirectory(prefix='pearson-inputs-') as inputtemp:
            inputs=Path(inputtemp)
            records,manifest_refs,experiments=load_inputs(refs,inputs)
            if any(output==p or output.is_relative_to(p) for p in experiments): raise PermissionError('Pearson output must be outside original experiment inputs')
            output.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.pending-pearson-',dir=output) as temp:
                results=Path(temp)/'results';results.mkdir(mode=0o700)
                maps={};datasets=[];notes=[];console=io.StringIO()
                with contextlib.redirect_stdout(console),contextlib.redirect_stderr(console),warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    for index,r in enumerate(records):
                        trace=native.ChromatinTraceTable();native.silent_load_trace(trace,str(r['snapshot']))
                        table=trace.data
                        if len(table)!=r['rows'] or list(table.colnames)!=r['columns'] or not set(TRACE_COLUMNS)<=set(table.colnames):
                            raise ValueError('Collected ECSV schema/row count disagrees with manifest')
                        if len(table) and {identifier(v) for v in table['ROI #']}!={r['roi']}: raise ValueError('ROI provenance disagrees with trace data')
                        counts=Counter((str(t),identifier(b)) for t,b in zip(table['Trace_ID'],table['Barcode #']))
                        duplicates=sum(v>1 for v in counts.values())
                        if duplicates: notes.append(f'Dataset {index}: {duplicates} repeated trace/barcode groups; native Pearson keeps the last row per barcode, without allele separation.')
                        maps[r['key']]=native.accumulate_distances(table)
                        datasets.append({'index':index,'label':r['label'],'roi':r['roi'],'collection_run_id':r['collection_run_id'],
                                         'rows':len(table),'distance_pair_count':len(maps[r['key']]),'repeated_trace_barcode_groups':duplicates})
                    files,matrix=native.compare_distance_maps(maps)
                    figure=results/f'trace_correlation_matrix.{output_format}'
                    native.plot_correlation_matrix(files,matrix,output_filename=str(figure))
                notes += sorted({f'{w.category.__name__}: {w.message}' for w in caught})
                notes.append('Native figure uses a fixed 0–1 color range; negative correlations remain in the numerical output and may be clipped visually.')
                notes.append('Trace_ID represents a segmented nucleus, not necessarily a single chromosome. Correlation is not biological equivalence or approval to merge.')
                npy=results/'trace_correlation_matrix.npy'
                if not np.array_equal(np.load(npy,allow_pickle=False),matrix,equal_nan=True): raise ValueError('Native saved matrix differs from its returned numerical result')
                if not figure.is_file() or figure.stat().st_size==0: raise ValueError('Native figure was not created')
                comparisons=[]
                for i in range(len(files)):
                    for j in range(i+1,len(files)):
                        shared=set(maps[files[i]]) & set(maps[files[j]])
                        support=sum(not np.isnan(maps[files[i]][k]) and not np.isnan(maps[files[j]][k]) for k in shared)
                        comparisons.append({'first':i,'second':j,'pearson_r':json_number(matrix[i,j]),'shared_non_nan_pairs':int(support)})
                undefined=sum(c['pearson_r'] is None for c in comparisons)
                if undefined: notes.append(f'{undefined} off-diagonal correlation(s) undefined under native handling; JSON null preserves that state, not zero.')
                verify_sources(records,refs)
                detail={'schema_version':1,'run_id':run_id,'phase':'pearson_qc_only','review_required':True,
                        'collection_references':manifest_refs,'datasets':datasets,'comparisons':comparisons,
                        'files':files,'correlation_matrix':[[json_number(v) for v in row] for row in matrix],
                        'distance_maps':[{'dataset_index':i,'pairs':[{'barcodes':[int(k[0]),int(k[1])],'median_distance':json_number(v)} for k,v in sorted(maps[f].items())]} for i,f in enumerate(files)],
                        'warnings':notes,'traceratops_version':importlib.metadata.version('traceratops'),'native_module_sha256':digest(Path(native.__file__)),
                        'native_functions':['silent_load_trace','accumulate_distances','compare_distance_maps','plot_correlation_matrix'],
                        'parameters':{'output_format':output_format,'correlation_threshold':None},
                        'artifacts':{'figure':figure.name,'native_matrix':npy.name},'next_action':'STOP_FOR_USER_REVIEW'}
                path=results/'results.json';path.write_text(json.dumps(detail,indent=2,allow_nan=False),encoding='utf-8')
                (results/'pearson_qc.md').write_text(format_pearson_report(detail),encoding='utf-8')
                (results/'native.log').write_text(console.getvalue(),encoding='utf-8')
                final=output/run_id
                if final.exists(): raise FileExistsError('Pearson run directory already exists')
                results.rename(final)
        return PearsonResult(status='COMPUTED',run_id=run_id,dataset_count=len(files),
                             datasets=[{k:d[k] for k in ('index','roi','collection_run_id')} for d in datasets],
                             comparison_count=len(comparisons),undefined_comparisons=undefined,
                             comparisons=comparisons[:COMPARISON_PREVIEW_LIMIT],comparisons_truncated=len(comparisons)>COMPARISON_PREVIEW_LIMIT,
                             warnings=notes[:WARNING_PREVIEW_LIMIT],warning_count=len(notes),warnings_truncated=len(notes)>WARNING_PREVIEW_LIMIT,
                             results_path=str(final/'results.json'),results_sha256=digest(final/'results.json'),report_path=str(final/'pearson_qc.md'),
                             matrix_path=str(final/npy.name),figure_path=str(final/figure.name),execution_seconds=time.perf_counter()-start)
    except Exception as exc:
        return PearsonResult(status='ERROR',run_id=run_id,error_type=type(exc).__name__,error=str(exc)[:500],execution_seconds=time.perf_counter()-start)


def register_pearson_tool(mcp):
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False,destructive_hint=False,idempotent_hint=False,open_world_hint=False))
    async def trace_pearsons(collections: list[CollectionReference], output_format: Literal['png','svg','pdf']='png') -> PearsonResult:
        """Step 1a.2: native Pearson QC from collection run IDs + manifest SHA-256 values.

        Uses all trace files in each referenced manifest. Returns a compact pairwise
        coefficient preview and local full-results/report/figure paths. No figures
        or full matrices sent by default. Undefined coefficients are null. Does not
        choose an acceptance threshold, approve datasets, merge, or run analyzers.
        """
        result=execute_pearsons(collections,output_format)
        for _ in range(4):
            size=len(result.model_dump_json().encode())
            if size==result.structured_response_bytes: break
            result.structured_response_bytes=size
        return result
