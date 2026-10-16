"""Independent, bounded fixture oracle: stdlib CSV; no MCP/validator imports.

Reviewed against the selected mask-based ECSV 1.0 space-delimited format.
This deliberately does not claim to implement a general ECSV parser.
"""
import csv
import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4

SKIP = {'full_pwd', 'PWD_comparison', '.git', '.venv'}
TRACE = ['Spot_ID', 'Trace_ID', 'x', 'y', 'z', 'ROI #', 'Barcode #']
LOCAL = ['Buid', 'ROI #', 'Barcode #', 'xcentroid', 'ycentroid', 'zcentroid']


def fingerprint(root):
    result = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in list(dirs):
            p = Path(parent) / name
            if name in SKIP or p.is_symlink():
                dirs.remove(name)
                result[str(p.relative_to(root))] = {'excluded': True, 'link': os.readlink(p) if p.is_symlink() else None}
        for name in files:
            p = Path(parent) / name
            if p.is_symlink():
                value = {'link': os.readlink(p)}
            else:
                stat = p.stat()
                digest = hashlib.sha256()
                with p.open('rb') as f:
                    for block in iter(lambda: f.read(1024 * 1024), b''):
                        digest.update(block)
                if (stat.st_size, stat.st_mtime_ns) != (p.stat().st_size, p.stat().st_mtime_ns):
                    raise RuntimeError('Input changed while fingerprinting')
                value = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'sha256': digest.hexdigest()}
            result[str(p.relative_to(root))] = value
    return result


def table(path, required):
    with path.open(newline='') as f:
        if f.readline().strip() != '# %ECSV 1.0':
            raise ValueError('Not reviewed ECSV 1.0 format')
        for line in f:
            if not line.startswith('#'):
                header = next(csv.reader([line], delimiter=' ', skipinitialspace=True))
                break
        else:
            raise ValueError('No header')
        if not set(required) <= set(header):
            raise ValueError('Missing required columns')
        barcodes, rois, records = set(), set(), 0
        for row in csv.reader(f, delimiter=' ', skipinitialspace=True):
            if not row:
                continue
            if len(row) != len(header):
                raise ValueError('Column count mismatch')
            d = dict(zip(header, row))
            barcodes.add(str(int(d['Barcode #'])))
            rois.add(str(int(d['ROI #'])))
            records += 1
    return {'barcodes': sorted(barcodes, key=int), 'rois': sorted(rois, key=int), 'records': records}


def oracle(root, rules=None):
    """Rules here are fixture-design references, never learned from MCP results."""
    root = Path(root)
    rules = rules or {}
    expected = rules.get('expected_barcodes')
    rois = sorted((p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and p.name.isdecimal()), key=lambda p: int(p.name))
    missing_files, missing_barcodes, invalid, tables = [], [], [], []
    trace_count = local_count = 0
    for roi in rois:
        rid = str(int(roi.name))
        traces = [p for p in (roi/'tracing/data').glob('*.ecsv') if re.fullmatch(r'Trace_3D_barcode_mask-[^/]+_ROI-\d+\.ecsv', p.name) and not p.is_symlink()]
        locs = [p for p in (roi/'localize_3d/data/localizations_3D_barcode.ecsv', roi/'localize_3d/localizations_3D_barcode.ecsv') if p.is_file() and not p.is_symlink()]
        trace_count += len(traces)
        local_count += len(locs)
        for role, paths, required in [('tracing', traces, TRACE), ('localization', locs, LOCAL)]:
            if len(paths) != 1:
                missing_files.append({'roi': rid, 'role': role})
                continue
            p = paths[0]
            try:
                t = table(p, required)
                if t['rois'] != [rid]:
                    raise ValueError('ROI mismatch')
                tables.append({'path': str(p.relative_to(root)), 'role': role, 'roi': rid, **t})
                if expected is not None:
                    missing = sorted(set(expected) - set(t['barcodes']), key=int)
                    if missing:
                        missing_barcodes.append({'roi': rid, 'role': role, 'barcodes': missing})
            except (ValueError, KeyError, StopIteration):
                invalid.append(str(p.relative_to(root)))
    # Scope intentionally limited to reviewed real files and generated fixtures.
    status = 'ERROR' if invalid else 'FAIL' if missing_files or (missing_barcodes and rules.get('require_each_barcode')) else 'INCOMPLETE' if expected is None or rules.get('expected_roi_ids') is None else 'PASS'
    if rules.get('expected_roi_ids') is not None and set(rules['expected_roi_ids']) != {str(int(p.name)) for p in rois}:
        status = 'FAIL'
    return {'roi_count': len(rois), 'tracing_tables': trace_count, 'localization_tables': local_count,
            'status': status, 'required_files_present': not missing_files,
            'missing_files': missing_files, 'missing_barcodes': None if expected is None else missing_barcodes,
            'invalid_tables': invalid, 'records': sum(t['records'] for t in tables), 'tables': tables}


def make_fixtures(directory):
    """Two ROIs, two known barcodes; explicit toy experiment, no copied science."""
    cases = []
    for name in ('complete', 'missing_file', 'missing_barcode', 'invalid_ecsv'):
        # Mutation labels belong only to evaluation records, never model-visible paths.
        root = Path(directory)/('experiment-'+uuid4().hex[:12])
        root.mkdir(parents=True, exist_ok=False)
        for rid in ('1', '2'):
            for role, columns in [('tracing', TRACE), ('localization', LOCAL)]:
                p = root/rid/(f'tracing/data/Trace_3D_barcode_mask-mask0_ROI-{rid}.ecsv' if role == 'tracing' else 'localize_3d/data/localizations_3D_barcode.ecsv')
                p.parent.mkdir(parents=True, exist_ok=True)
                if name == 'missing_file' and rid == '2' and role == 'localization':
                    continue
                lines = ['# %ECSV 1.0', '# ---', '# datatype:']
                for col in columns:
                    dtype = 'string' if col in ('Spot_ID', 'Trace_ID', 'Buid') else 'int64' if col in ('ROI #', 'Barcode #') else 'float64'
                    lines.append(f'# - {{name: "{col}", datatype: {dtype}}}')
                lines += ['# schema: astropy-2.0']
                with p.open('w', newline='') as f:
                    f.write('\n'.join(lines)+'\n')
                    writer = csv.writer(f, delimiter=' ', lineterminator='\n')
                    writer.writerow(columns)
                    for bc in ('1', '2'):
                        if name == 'missing_barcode' and rid == '2' and role == 'tracing' and bc == '2':
                            continue
                        writer.writerow([rid if c == 'ROI #' else bc if c == 'Barcode #' else 'nucleus1' if c == 'Trace_ID' else f'spot{bc}' if c in ('Spot_ID', 'Buid') else '0.5' for c in columns])
                if name == 'invalid_ecsv' and rid == '2' and role == 'tracing':
                    p.write_text('deliberately not ECSV\n')
        cases.append({'name': name, 'root': str(root.resolve()), 'rules': {'expected_roi_ids': ['1', '2'], 'expected_barcodes': ['1', '2'], 'barcode_source': 'Explicit synthetic fixture design'}})
    return cases
