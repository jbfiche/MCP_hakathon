"""Attach native per-ROI trace statistics to existing Step 0 evidence only."""
import hashlib
import io
import os
import stat
import tempfile
import warnings
from contextlib import redirect_stderr
from pathlib import Path

from . import trace_statistics as statistics


def read_snapshot_bytes(path, maximum, expected_sha256):
    """Bounded non-symlink read, checked against the already-validated ECSV hash."""
    handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(handle, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            raise ValueError('Statistics input is not a bounded regular file')
        data = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    if (len(data) > maximum or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
            or hashlib.sha256(data).hexdigest() != expected_sha256):
        raise ValueError('Tracing input changed since Step 0 validation')
    return data


def attach_statistics(root, rules, doc, checked_path):
    """One small evidence record per discovered ROI; localization tables never run."""
    for roi in doc['rois']:
        record = {'status':'NOT_RUN', 'roi':roi['roi'], 'roi_directory':roi['directory'],
                  'scope':'original_individual_roi_tracing', 'reason':None}
        roi['trace_stats'] = record
        candidates = roi['tracing']
        if len(candidates) != 1:
            record['reason'] = 'No tracing table found' if not candidates else 'Ambiguous tracing tables; no dataset selected'
            continue
        relative = candidates[0]
        record['source_relative'] = relative
        table = next((t for t in roi['tables'] if t['role']=='tracing' and t['path']==relative), {})
        if not table.get('valid') or 'sha256' not in table:
            record['reason'] = 'Tracing table invalid, unreadable or outside validation limits; see validation findings'
            continue
        record['input_sha256'] = table['sha256']
        console = io.StringIO()
        caught = []
        try:
            path = checked_path(root, relative)
            record['source_file'] = str(path)
            data = read_snapshot_bytes(path, rules.max_table_bytes, table['sha256'])
            with tempfile.TemporaryDirectory(prefix='step0-trace-statistics-') as directory:
                snapshot = Path(directory)/'trace.ecsv'
                snapshot.write_bytes(data); snapshot.chmod(0o400)
                with redirect_stderr(console), warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    result = statistics.compute_statistics(snapshot)
                # Source display paths refer to the verified original; native reads only identical snapshot bytes.
                result['source_file'] = str(path)
                result['traceratops_report'] = result['traceratops_report'].replace(str(snapshot), str(path))
            read_snapshot_bytes(checked_path(root, relative), rules.max_table_bytes, table['sha256'])
            record.update(status='COMPUTED', reason=None, **result,
                          input_mode='private_read_only_snapshot',
                          native_module_sha256=hashlib.sha256(Path(statistics.native.__file__).read_bytes()).hexdigest(),
                          warnings=[f'{w.category.__name__}: {w.message}' for w in caught],
                          native_stderr=console.getvalue())
        except Exception as exc:
            record.update(status='ERROR', reason=f'{type(exc).__name__}: {str(exc)[:400]}', native_stderr=console.getvalue(),
                          warnings=[f'{w.category.__name__}: {w.message}' for w in caught])
