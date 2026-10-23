"""Native annotation derivative; the approved merge/baseline remain immutable."""
from __future__ import annotations

import contextlib
import copy
import inspect
import io
import json
import os
import stat
import tempfile
import time
import warnings
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import numpy as np
from astropy.io.misc import yaml
from astropy.table import Table
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from traceratops import trace_genomic_coordinates as native

from . import approval as a, merge as m, merged_statistics as ms, pearsons as p
from .collection import digest
from .step0 import authorized_root, checked_path

OUTPUT_ENV = 'CHROMATIN_GENOMIC_OUTPUT_DIR'
REFERENCE_ENV = 'CHROMATIN_GENOME_REFERENCE'
ANNOTATION_COLUMNS = {'Chrom', 'Chrom_Start', 'Chrom_End', 'Barcode #'}


class AnnotationResult(BaseModel):
    status: Literal['ANNOTATED', 'ERROR']
    run_id: str
    baseline_run_id: str
    evidence_path: str | None = None
    evidence_sha256: str | None = None
    annotated_path: str | None = None
    annotated_sha256: str | None = None
    mapping_path: str | None = None
    row_count: int | None = None
    barcode_count: int | None = None
    assembly: str | None = None
    warnings: list[str] = Field(default_factory=list)
    execution_seconds: float
    structured_response_bytes: int = 0
    error_type: str | None = None
    error: str | None = None


def store():
    base = Path(os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR', str(Path.cwd()/'results')))
    path = Path(os.environ.get(OUTPUT_ENV, str(base/'genomic_annotations'))).expanduser().absolute()
    if path.is_symlink(): raise PermissionError('Annotation store must not be a symlink')
    return path


def read_file(path, maximum=p.MAX_MANIFEST_BYTES):
    """Bounded, no-follow regular file read; evidence stores are host-controlled."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise ValueError('Expected a bounded regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(maximum+1)
        if len(raw)>maximum: raise ValueError('Input exceeds byte limit')
        return raw
    finally: os.close(fd)


def reference():
    path = Path(os.environ[REFERENCE_ENV]).expanduser().absolute()
    raw = read_file(path)
    doc = json.loads(raw)
    if not doc.get('assembly') or not doc.get('authority') or not doc.get('chromosome_sizes_source'):
        raise ValueError('Explicit assembly authority and chromosome-size source are required')
    sizes = doc.get('chromosome_sizes', {})
    if not sizes or any(type(n) is not int or n<=0 for n in sizes.values()):
        raise ValueError('Reference chromosome sizes must be positive integers')
    return doc, str(path), a.sha(raw)


def bed_input(experiment_root, bed_relative, checksum, approved_roots):
    root = authorized_root(experiment_root)
    if root not in approved_roots: raise PermissionError('BED experiment must match an approved original experiment root')
    path = checked_path(root, bed_relative)
    raw = read_file(path)
    if a.sha(raw)!=checksum: raise ValueError('BED checksum mismatch')
    return raw, str(path)


def mapping_from_bed(raw, reference_doc, table):
    rows = [line.split() for line in raw.decode('utf-8').splitlines() if line.strip()]
    if not rows or any(len(r)!=5 for r in rows):
        raise ValueError('Require the native five-column BED with explicit replacement IDs on every row')
    # Parse with native code, but reject rows native would skip or silently overwrite.
    with tempfile.TemporaryDirectory(prefix='native-bed-parse-') as temporary:
        path = Path(temporary)/'input.bed';path.write_bytes(raw)
        with contextlib.redirect_stdout(io.StringIO()): mapping = native.load_bed_file(str(path))
    if len(mapping)!=len(rows): raise ValueError('BED has malformed rows or duplicate original barcode mappings')
    replacements = [v['New_Barcode'] for v in mapping.values()]
    if any(type(v) is not int or v<0 for v in replacements) or any(k<0 for k in mapping):
        raise ValueError('Invalid or missing original/replacement barcode identifiers')
    if len(set(replacements))!=len(replacements): raise ValueError('Replacement barcode collision')
    required = {'Barcode #','Chrom','Chrom_Start','Chrom_End'}
    if not required <= set(table.colnames) or table['Barcode #'].dtype.kind not in 'iu':
        raise ValueError('Required native annotation columns/integer barcode identifiers are missing')
    if not len(table) or any(np.ma.getmaskarray(table[n]).any() for n in required):
        raise ValueError('Empty/masked native annotation inputs are unsupported')
    observed = set(map(int, table['Barcode #']))
    if observed-set(mapping): raise ValueError('BED is missing observed original barcodes: '+str(sorted(observed-set(mapping))))
    intervals = []
    for original, entry in mapping.items():
        chrom, start, end = entry['Chrom'], entry['Chrom_Start'], entry['Chrom_End']
        if chrom not in reference_doc['chromosome_sizes']:
            raise ValueError('BED chromosome absent from declared assembly reference: '+chrom)
        if not 0<=start<end<=reference_doc['chromosome_sizes'][chrom]:
            raise ValueError('BED coordinates invalid or outside declared chromosome bounds')
        if table['Chrom'].dtype.kind not in 'US' or np.asarray([chrom], dtype=table['Chrom'].dtype)[0]!=chrom:
            raise ValueError('Native chromosome assignment would truncate or misrepresent chromosome names')
        for name, number in [('Chrom_Start',start),('Chrom_End',end),('Barcode #',entry['New_Barcode'])]:
            dtype=table[name].dtype
            if dtype.kind not in 'iu' or not np.iinfo(dtype).min<=number<=np.iinfo(dtype).max:
                raise ValueError('Native assignment would overflow or change identifier/coordinate type: '+name)
        intervals.append((chrom,start,end))
    if len(set(intervals))!=len(intervals): raise ValueError('Ambiguous identical genomic intervals for distinct barcodes')
    ordered=sorted(intervals)
    if any(x[0]==y[0] and y[1]<x[2] for x,y in zip(ordered,ordered[1:])):
        raise ValueError('Overlapping BED intervals require scientific review')
    records=[{'original_barcode':int(k),'replacement_barcode':v['New_Barcode'],
              'chromosome':v['Chrom'],'start':v['Chrom_Start'],'end':v['Chrom_End']} for k,v in mapping.items()]
    coverage={'observed_original_barcodes':len(observed),'mapped_original_barcodes':len(observed),
              'mapped_rows':len(table),'total_rows':len(table),'unused_bed_barcodes':sorted(set(mapping)-observed)}
    return mapping, records, coverage


def corrected_metadata(meta, assembly):
    result=copy.deepcopy(meta)
    if 'genome_assembly' in result: result['genome_assembly']=assembly
    comments=list(result.get('comments',[]))
    comments=[v for v in comments if not str(v).strip().startswith('genome_assembly=')]
    result['comments']=comments+['genome_assembly='+assembly]
    return result


def expected_native_metadata(original):
    meta=copy.deepcopy(original.meta)
    comments=list(dict.fromkeys(v for v in meta.get('comments',[]) if v))
    comments.append(f'Genomic coordinates imputed from BED file. {len(original)}/{len(original)} rows matched.')
    meta['comments']=comments
    return meta


def verify_derivative(original, annotated, mapping, expected_meta):
    if original.colnames!=annotated.colnames or len(original)!=len(annotated):
        raise ValueError('Annotation changed row count, column order or schema')
    if yaml.dump(m.column_metadata(original))!=yaml.dump(m.column_metadata(annotated)):
        raise ValueError('Annotation changed column metadata/units')
    if yaml.dump(annotated.meta)!=yaml.dump(expected_meta): raise ValueError('Unexpected annotation metadata changes')
    for name in original.colnames:
        left, right=original[name],annotated[name]
        if left.dtype!=right.dtype: raise ValueError('Annotation changed column type: '+name)
        np.testing.assert_array_equal(np.ma.getmaskarray(left), np.ma.getmaskarray(right))
        if name not in ANNOTATION_COLUMNS:
            valid=~np.ma.getmaskarray(left)
            np.testing.assert_equal(np.asarray(left)[valid],np.asarray(right)[valid],err_msg='Annotation changed '+name)
    for original_barcode in set(map(int,original['Barcode #'])):
        mask=np.asarray(original['Barcode #'])==original_barcode; entry=mapping[original_barcode]
        for name,key in [('Barcode #','New_Barcode'),('Chrom','Chrom'),('Chrom_Start','Chrom_Start'),('Chrom_End','Chrom_End')]:
            if not np.all(annotated[name][mask]==entry[key]): raise ValueError('Native annotation values disagree with BED mapping: '+name)


def recheck_context(baseline_id, checksum, baseline, baseline_log_sha, value, grant, current):
    """Called under approval lock; never recursively acquire that lock."""
    from . import tracing_analysis as ta
    ev=a.evidence(value['pearson_run_id'],value['results_sha256'])
    if not current or current['revision']!=grant['revision'] or current['status']!='APPROVED' or not a.state_matches(current,ev):
        raise PermissionError('Scientific approval/evidence changed before annotation publication')
    last, log=ta.read_baseline(baseline_id,checksum)
    if last!=baseline or log!=baseline_log_sha: raise ValueError('Baseline changed during annotation')
    _,_,log=ms.read_merge(baseline['trace_merge_run_id'],baseline['merged_sha256'],baseline['provenance_sha256'])
    if log!=baseline['merge_native_log_sha256']: raise ValueError('Merge log changed during annotation')


def verify_saved(run_id,checksum,baseline_id,baseline_sha,original,baseline,grant,roots):
    """Validate a derivative without replacing or weakening original merge checks."""
    with p.run_handle(store(),run_id) as fd:
        raw=p.read_regular(fd,'annotation.json',p.MAX_MANIFEST_BYTES)
        if a.sha(raw)!=checksum: raise ValueError('Annotation evidence checksum mismatch')
        doc=json.loads(raw)
        data=p.read_regular(fd,'annotated_traces.ecsv',p.MAX_TOTAL_BYTES)
        mapping_raw=p.read_regular(fd,'barcode_mapping.json',p.MAX_MANIFEST_BYTES)
        native_raw=p.read_regular(fd,'native_annotated.ecsv',p.MAX_TOTAL_BYTES)
        log=p.read_regular(fd,'native.log',p.MAX_MANIFEST_BYTES)
    expected={'schema_version':1,'status':'ANNOTATED','run_id':run_id,'baseline_run_id':baseline_id,
              'baseline_sha256':baseline_sha,'merged_sha256':baseline['merged_sha256'],
              'merge_provenance_sha256':baseline['provenance_sha256'],'baseline_fingerprint':baseline['baseline_fingerprint'],
              'approval_revision':grant['revision'],'approval_fingerprint':grant['fingerprint'],
              'native_module_sha256':digest(Path(native.__file__)),
              'native_table_module_sha256':digest(Path(inspect.getfile(native.ChromatinTraceTable))),
              'traceratops_version':version('traceratops')}
    if any(doc.get(k)!=v for k,v in expected.items()): raise ValueError('Annotation provenance differs from verified baseline/approval/native evidence')
    if any(doc.get(k)!=a.sha(v) for k,v in [('annotated_sha256',data),('mapping_sha256',mapping_raw),('native_output_sha256',native_raw),('native_log_sha256',log)]):
        raise ValueError('Annotation artifact checksum mismatch')
    ref,ref_path,ref_sha=reference()
    if doc['reference_path']!=ref_path or doc['reference_sha256']!=ref_sha or doc['assembly']!=ref['assembly']:
        raise ValueError('Assembly reference changed')
    raw,_=bed_input(doc['experiment_root'],doc['bed_relative'],doc['bed_sha256'],roots)
    mapping,records,coverage=mapping_from_bed(raw,ref,original)
    if records!=json.loads(mapping_raw) or coverage!=doc['mapping_coverage']:
        raise ValueError('Saved barcode mapping/coverage differs from BED')
    with tempfile.TemporaryDirectory(prefix='verify-annotated-traces-') as temp:
        path=Path(temp)/'trace.ecsv';path.write_bytes(data);table=Table.read(path,format='ascii.ecsv')
        path.write_bytes(native_raw);native_table=Table.read(path,format='ascii.ecsv')
    native_meta=expected_native_metadata(original)
    verify_derivative(original,native_table,mapping,native_meta)
    verify_derivative(original,table,mapping,corrected_metadata(native_meta,ref['assembly']))
    return data,doc


def execute_annotation(baseline_run_id,baseline_sha256,experiment_root,bed_relative,bed_sha256):
    from . import tracing_analysis as ta
    start=time.perf_counter();run_id=uuid4().hex
    try:
        baseline,value,data,grant,roots,sources,baseline_log_sha=ta.load_context(baseline_run_id,baseline_sha256)
        bed,bed_path=bed_input(experiment_root,bed_relative,bed_sha256,roots)
        ref,ref_path,ref_sha=reference()
        output=store().resolve(); safe=ta.output_root(roots)
        if output==safe or output.is_relative_to(safe) or safe.is_relative_to(output):
            raise PermissionError('Annotation and analyzer stores must be separate')
        # Reuse the existing complete exclusion checks, with the annotation output as candidate.
        with contextlib.ExitStack() as stack:
            # No environment mutation: explicit forbidden stores supplement analyzer checks.
            forbidden=roots|{ms.merge_root().resolve(),ta.baseline_root().resolve(),p.collection_root().resolve(),a.pearson_root().resolve()}
            base=Path(os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR',str(Path.cwd()/'results')))
            forbidden.add(Path(os.environ.get('CHROMATIN_LOCALIZATION_MERGE_OUTPUT_DIR',str(base/'localization_merges'))).resolve())
            forbidden.update(Path(v).resolve() for v in os.environ.get('CHROMATIN_EXPERIMENT_ROOTS','').split(os.pathsep) if v)
            if any(output==v or output.is_relative_to(v) for v in forbidden): raise PermissionError('Annotation output must be outside all scientific input/evidence stores')
            temporary=stack.enter_context(tempfile.TemporaryDirectory(prefix='annotation-inputs-'))
            snapshots=Path(temporary);path=snapshots/'merged.ecsv';path.write_bytes(data);path.chmod(0o400)
            table=Table.read(path,format='ascii.ecsv')
            contributions=ms.verify_contributions(value,table,snapshots,grant,sources)
            if contributions!=baseline['approved_source_contributions']: raise ValueError('Baseline contributions disagree')
            mapping,records,coverage=mapping_from_bed(bed,ref,table)
            output.mkdir(parents=True,exist_ok=True)
            work=stack.enter_context(tempfile.TemporaryDirectory(prefix='.pending-annotation-',dir=output))
            folder=Path(work)/'result';folder.mkdir(mode=0o700)
            native_path=folder/'native_annotated.ecsv';console=io.StringIO()
            with contextlib.redirect_stdout(console),contextlib.redirect_stderr(console),warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                native.impute_genomic_coordinates(str(path),mapping,str(native_path),{'auto_continue':False})
            if digest(path)!=baseline['merged_sha256']: raise ValueError('Native annotation modified its input')
            result=Table.read(native_path,format='ascii.ecsv')
            verify_derivative(table,result,mapping,expected_native_metadata(table))
            result.meta=corrected_metadata(result.meta,ref['assembly'])
            annotated=folder/'annotated_traces.ecsv';result.write(annotated,format='ascii.ecsv')
            verify_derivative(table,Table.read(annotated,format='ascii.ecsv'),mapping,corrected_metadata(expected_native_metadata(table),ref['assembly']))
            mapping_path=folder/'barcode_mapping.json';mapping_path.write_text(json.dumps(records,indent=2))
            (folder/'native.log').write_text(console.getvalue())
            notes=['Barcode IDs were replaced by native Traceratops using BED column five; localization barcode IDs remain original. Use barcode_mapping.json for cross-table interpretation and Spot_ID/Buid for spot identity.',
                   'Assembly is supplied by the configured researcher-confirmed reference, not inferred from native defaults; inherited assembly metadata is corrected only in the new derivative.']
            notes += [str(w.message) for w in caught]
            doc={'schema_version':1,'status':'ANNOTATED','run_id':run_id,'baseline_run_id':baseline_run_id,'baseline_sha256':baseline_sha256,
                 'baseline_fingerprint':baseline['baseline_fingerprint'],'merged_sha256':baseline['merged_sha256'],
                 'merge_provenance_sha256':baseline['provenance_sha256'],'approval_revision':grant['revision'],'approval_fingerprint':grant['fingerprint'],
                 'pearson_run_id':value['pearson_run_id'],'selected_dataset_indices':grant['selected_dataset_indices'],
                 'experiment_root':str(Path(experiment_root).resolve()),'bed_relative':bed_relative,'bed_path':bed_path,'bed_sha256':bed_sha256,
                 'reference_path':ref_path,'reference_sha256':ref_sha,'reference':ref,'assembly':ref['assembly'],
                 'input_metadata_yaml':yaml.dump(table.meta),'output_metadata_yaml':yaml.dump(result.meta),
                 'native_function':'traceratops.trace_genomic_coordinates.impute_genomic_coordinates',
                 'native_module_sha256':digest(Path(native.__file__)), 'native_table_module_sha256':digest(Path(inspect.getfile(native.ChromatinTraceTable))),
                 'traceratops_version':version('traceratops'),'native_barcode_replacement':True,'native_mapping_override':False,
                 'native_output_sha256':digest(native_path),'annotated_sha256':digest(annotated),'mapping_sha256':digest(mapping_path),
                 'native_log_sha256':digest(folder/'native.log'),'mapping_coverage':coverage,'row_count':len(table),
                 'barcode_count':len(set(map(int,result['Barcode #']))),'approved_source_contributions':contributions,
                 'warnings':notes,'execution_seconds':time.perf_counter()-start}
            with a.locked_state(value['pearson_run_id']) as (current,_):
                recheck_context(baseline_run_id,baseline_sha256,baseline,baseline_log_sha,value,grant,current)
                bed_input(experiment_root,bed_relative,bed_sha256,roots)
                if reference()[2]!=ref_sha: raise ValueError('Assembly reference changed during annotation')
                (folder/'annotation.json').write_text(json.dumps(doc,indent=2,allow_nan=False))
                final=output/run_id
                if final.exists(): raise FileExistsError('Annotation run exists')
                folder.rename(final)
        return AnnotationResult(status='ANNOTATED',run_id=run_id,baseline_run_id=baseline_run_id,
            evidence_path=str(final/'annotation.json'),evidence_sha256=digest(final/'annotation.json'),
            annotated_path=str(final/'annotated_traces.ecsv'),annotated_sha256=digest(final/'annotated_traces.ecsv'),
            mapping_path=str(final/'barcode_mapping.json'),row_count=doc['row_count'],barcode_count=doc['barcode_count'],
            assembly=ref['assembly'],warnings=notes[:2],execution_seconds=time.perf_counter()-start)
    except Exception as exc:
        return AnnotationResult(status='ERROR',run_id=run_id,baseline_run_id=baseline_run_id,
            error_type=type(exc).__name__,error=str(exc)[:500],execution_seconds=time.perf_counter()-start)


def register_genomic_annotation_tool(mcp):
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False,destructive_hint=False,idempotent_hint=False,open_world_hint=False))
    async def trace_genomic_coordinates(baseline_run_id: Annotated[str,Field(pattern=a.RUN_PATTERN)],
                                  baseline_sha256: Annotated[str,Field(pattern=a.SHA_PATTERN)],
                                  experiment_root: str,bed_relative: str,
                                  bed_sha256: Annotated[str,Field(pattern=a.SHA_PATTERN)]) -> AnnotationResult:
        """Create a native five-column BED annotation derivative, including barcode replacement.

        Require current human approval, exact Step 1c baseline and host-configured assembly evidence.
        Preserve original merged traces, baseline, localizations and BED. Never run analyzers automatically.
        """
        result=execute_annotation(baseline_run_id,baseline_sha256,experiment_root,bed_relative,bed_sha256)
        for _ in range(4):
            size=len(result.model_dump_json().encode())
            if size==result.structured_response_bytes: break
            result.structured_response_bytes=size
        return result
