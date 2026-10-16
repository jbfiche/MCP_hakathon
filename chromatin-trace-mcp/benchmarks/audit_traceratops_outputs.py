#!/usr/bin/env python3
"""Smoke-audit native tools on generated data only; not a Step 1 MCP pipeline."""
import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from astropy.table import Table
import traceratops

TOOLS = ['collect_files', 'trace_pearsons', 'trace_merge', 'localization_merge', 'trace_analyzer', 'localization_analyzer']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(142)
    inputs = out / 'synthetic_inputs'
    traces, locs = [], []
    for rid in [92, 93]:
        directory = inputs / str(rid)
        directory.mkdir(parents=True, exist_ok=True)
        n = 180
        barcodes = np.tile(np.arange(1, 7), 30)
        xyz = rng.normal(size=(n, 3)) + barcodes[:, None] * .2
        trace = Table({'Spot_ID': [f's{rid}-{i}' for i in range(n)], 'Trace_ID': [f'n{rid}-{i//6}' for i in range(n)],
                       'x': xyz[:, 0], 'y': xyz[:, 1], 'z': xyz[:, 2], 'Chrom': ['chr2L'] * n,
                       'Chrom_Start': barcodes * 100, 'Chrom_End': barcodes * 100 + 99,
                       'ROI #': [rid] * n, 'Mask_id': [1] * n, 'Barcode #': barcodes, 'label': ['synthetic'] * n},
                      meta={'comments': ['xyz_unit=micron', 'genome_assembly=synthetic']})
        trace_path = directory / 'trace.ecsv'
        trace.write(trace_path, format='ascii.ecsv', overwrite=True)
        traces.append(trace_path)
        loc = Table({'Buid': [f's{rid}-{i}' for i in range(n)], 'ROI #': [rid] * n, 'CellID #': [1] * n,
                     'Barcode #': barcodes, 'id': np.arange(n), 'zcentroid': xyz[:, 2], 'xcentroid': xyz[:, 0], 'ycentroid': xyz[:, 1],
                     'snr': rng.uniform(4, 12, n), 'spot_pixel_percentage': rng.uniform(.2, .9, n),
                     'skew': rng.uniform(-.2, .2, n), 'patch_size': [7] * n, 'object_class': [1] * n,
                     'mean_intensity': rng.uniform(800, 1200, n), 'flux': rng.uniform(3000, 7000, n), 'roundness': rng.uniform(.5, .9, n)})
        loc_path = directory / 'localizations.ecsv'
        loc.write(loc_path, format='ascii.ecsv', overwrite=True)
        locs.append(loc_path)
    source = Path(traceratops.__file__).parent
    report = {'source_directory': str(source), 'tools': []}
    for name in TOOLS:
        directory = out / name
        directory.mkdir(exist_ok=True)
        p = source / (name + '.py')
        tree = ast.parse(p.read_text())
        signatures = {node.name: ast.unparse(node.args) for node in tree.body if isinstance(node, ast.FunctionDef)}
        argv = [sys.executable, '-m', 'traceratops.' + name]
        stdin = None
        if name == 'collect_files':
            argv += ['--root', str(inputs), '--example-file', 'trace.ecsv', '--copy-to', str(directory / 'collected')]
        elif name == 'trace_pearsons':
            argv += ['--input', *map(str, traces), '--output', str(directory)]
        elif name == 'trace_merge':
            argv += ['--folder', str(directory), '--name', 'merged_traces.ecsv']
            stdin = '\n'.join(map(str, traces)) + '\n'
        elif name == 'localization_merge':
            argv += ['--output_folder', str(directory)]
            stdin = '\n'.join(map(str, locs)) + '\n'
        elif name == 'trace_analyzer':
            # This command writes figures beside its input; copy a synthetic fixture only.
            copy = directory / 'trace.ecsv'
            copy.write_bytes(traces[0].read_bytes())
            argv += ['--input', copy.name, '--neighbor_distance_range', 'auto']
        else:
            argv += ['--localization_file', str(locs[0]), '--output_file', str(directory / 'localization_qc.png')]
        try:
            run = subprocess.run(argv, input=stdin, text=True, capture_output=True, cwd=directory, timeout=45, env=os.environ.copy())
            (directory / 'stdout.log').write_text(run.stdout)
            (directory / 'stderr.log').write_text(run.stderr)
            record = {'tool': name, 'returncode': run.returncode, 'function_signatures': signatures, 'source_sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        except subprocess.TimeoutExpired:
            record = {'tool': name, 'returncode': None, 'error': '45-second smoke-test timeout', 'function_signatures': signatures}
        record['artifacts'] = [{'path': str(f.relative_to(out)), 'bytes': f.stat().st_size} for f in sorted(directory.rglob('*')) if f.is_file()]
        record['input_copies'] = ['trace_analyzer/trace.ecsv'] if name == 'trace_analyzer' else []
        record['numerical_files'] = [f['path'] for f in record['artifacts'] if Path(f['path']).suffix in {'.ecsv', '.csv', '.json', '.npy'} and f['path'] not in record['input_copies']]
        record['visual_files'] = [f['path'] for f in record['artifacts'] if Path(f['path']).suffix in {'.png', '.pdf', '.svg'}]
        report['tools'].append(record)
        print(json.dumps({'tool': name, 'returncode': record['returncode'], 'numeric_files': record['numerical_files'], 'visual_files': record['visual_files']}), flush=True)
    (out / 'audit.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
