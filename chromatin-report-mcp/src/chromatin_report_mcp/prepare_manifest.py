"""Host-only setup: bind existing compact workflow responses to a report manifest.

Run once with python -m chromatin_report_mcp.prepare_manifest INDEX_JSON ID.
This is not an MCP tool and never runs scientific processing.
"""
import json
import os
from pathlib import Path
import sys

from .workflow_report import Evidence, check, digest, regular


def prepare(index_path, manifest_id):
    import re
    check(re.fullmatch('[A-Za-z0-9_-]{1,80}', manifest_id) is not None, 'Invalid manifest ID')
    roots=[Path(x).absolute() for x in os.environ['CHROMATIN_REPORT_ARTIFACT_ROOTS'].split(os.pathsep) if x]
    _, raw=regular(Path(index_path).absolute(),roots,capture=True)
    index=json.loads(raw)
    roles={
        'step0': index['step0']['details_path'], 'pearson': index['pearson']['results_path'],
        'approval': index['approval']['decision_record_path'],
        'trace_merge': index['trace_merge']['provenance_path'],
        'localization_merge': index['localization_merge']['provenance_path'],
        'baseline': index['merged_trace_stats']['evidence_path'],
        'annotation': index['trace_genomic_coordinates']['evidence_path'],
        'trace_analysis': index['trace_analyzer']['evidence_path'],
        'localization_analysis': index['localization_analyzer']['evidence_path'],
    }
    _, raw=regular(Path(roles['annotation']),roots,capture=True)
    annotation=json.loads(raw)
    roles.update(mapping=str(Path(roles['annotation']).parent/'barcode_mapping.json'),
                 reference=annotation['reference_path'],
                 trace_numerical=str(Path(roles['trace_analysis']).parent/'numerical_outputs.json'),
                 localization_numerical=str(Path(roles['localization_analysis']).parent/'numerical_outputs.json'))
    paths=set()
    for role,path in roles.items():
        if role not in ['approval','reference']:
            paths.update(f for f in Path(path).parent.iterdir() if f.is_file())
        paths.add(Path(path))
    for key in ['tracing_collection','localization_collection']:
        path=Path(index[key]['manifest_path'])
        paths.update(f for f in path.parent.iterdir() if f.is_file())
        _,raw=regular(path,roots,capture=True)
        paths.update(Path(item['source']) for item in json.loads(raw)['files'])
    paths.add(Path(annotation['bed_path']))
    manifest={'schema_version':1,'title':'Pre-filtering experiment QC · '+annotation['assembly'],
              'roles':roles,'files':[{'path':str(p),'sha256':regular(p,roots)[0]} for p in sorted(paths)]}
    Evidence(manifest,roots)  # Reject missing, stale or inconsistent evidence before saving.
    root=Path(os.environ['CHROMATIN_QC_MANIFEST_DIR']).absolute()
    for part in [root,*root.parents]:
        check(not part.is_symlink(),'Manifest directory contains a symlink')
    check(not root.is_relative_to(Path(annotation['experiment_root'])), 'Manifest directory overlaps experiment inputs')
    root.mkdir(parents=True,exist_ok=True)
    path=root/(manifest_id+'.json')
    raw=(json.dumps(manifest,indent=2)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(raw)
    return {'manifest_id':manifest_id,'manifest_sha256':digest(raw),'path':str(path)}


if __name__ == '__main__':
    if len(sys.argv)!=3:
        raise SystemExit('Usage: python -m chromatin_report_mcp.prepare_manifest INDEX_JSON MANIFEST_ID')
    print(json.dumps(prepare(sys.argv[1],sys.argv[2]),indent=2))
