"""Compose pre-filtering QC from saved evidence. No scientific runtime imports."""
from __future__ import annotations

import hashlib
import html
import json
import os
from pathlib import Path
import re
import stat
import time
from datetime import datetime, timezone
from uuid import uuid4

ROLES = ('step0', 'pearson', 'approval', 'trace_merge', 'localization_merge',
         'baseline', 'annotation', 'trace_analysis', 'localization_analysis',
         'mapping', 'reference', 'trace_numerical', 'localization_numerical')
MAX_JSON = 32 * 1024 * 1024


def check(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular(path: Path, roots: list[Path], capture=False):
    """Open every component without following symlinks; hash bounded regular files."""
    check(path.is_absolute() and '..' not in path.parts, 'Noncanonical artifact path')
    check(any(path.is_relative_to(root) for root in roots), 'Artifact outside authorized roots')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        source = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(source)
            check(stat.S_ISREG(before.st_mode), 'Artifact is not a regular file')
            limit = MAX_JSON if capture else 2 * 1024**3
            check(before.st_size <= limit, 'Artifact exceeds size limit')
            sha = hashlib.sha256()
            chunks = []
            total = 0
            while chunk := os.read(source, 1024 * 1024):
                total += len(chunk)
                check(total <= limit, 'Artifact exceeds size limit')
                sha.update(chunk)
                if capture:
                    chunks.append(chunk)
            after = os.fstat(source)
            check((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                  (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                  'Artifact changed during read')
            return sha.hexdigest(), b''.join(chunks) if capture else None
        finally:
            os.close(source)
    finally:
        os.close(fd)


class Evidence:
    def __init__(self, manifest, roots):
        self.manifest = manifest
        self.roots = roots
        self.refs = {item['path']: item['sha256'] for item in manifest['files']}
        check(len(self.refs) == len(manifest['files']) <= 512, 'Duplicate or excessive artifacts')
        check(all(re.fullmatch('[a-f0-9]{64}', v) for v in self.refs.values()), 'Invalid checksum')
        self.docs = {}
        self.roles = manifest['roles']
        check(set(self.roles) == set(ROLES), 'Missing or unknown workflow roles')
        for role, path in self.roles.items():
            check(path in self.refs, f'Unbound role: {role}')
            self.docs[role] = self.read_json(path)
        self.verify_all()
        self.validate_links()

    def verify_all(self):
        for path, sha in self.refs.items():
            check(regular(Path(path), self.roots)[0] == sha, f'Checksum mismatch: {path}')

    def read_json(self, path):
        check(str(path) in self.refs, f'Unbound JSON: {path}')
        sha, raw = regular(Path(path), self.roots, capture=True)
        check(sha == self.refs[str(path)], f'Checksum mismatch: {path}')
        return json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))

    def bound(self, path, sha):
        check(self.refs.get(str(path)) == sha and sha is not None, f'Unbound evidence edge: {path}')

    def peer(self, role, field, target, target_field=None):
        value = self.docs[target].get(target_field) if target_field else self.refs[self.roles[target]]
        check(value is not None and self.docs[role].get(field) == value, f'Provenance mismatch: {role}.{field}')

    def sibling(self, role, name):
        check(Path(name).name == name and name not in ('.', '..'), 'Unsafe artifact filename')
        return Path(self.roles[role]).parent / name

    def validate_links(self):
        d = self.docs
        approval, pearson = d['approval'], d['pearson']
        check(approval.get('status') == 'APPROVED' and approval.get('decision_source') == 'MCP_HOST_ELICITATION',
              'Current human approval is not APPROVED')
        selected = approval['selected_dataset_indices']
        check(bool(selected) and selected == sorted(set(selected)), 'Invalid approved selection')
        binding = approval['evidence']
        check(digest(json.dumps(binding, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()) == approval['fingerprint'],
              'Approval evidence fingerprint mismatch')
        check(binding['pearson_run_id'] == pearson['run_id'], 'Approval Pearson run mismatch')
        self.bound(self.roles['pearson'], binding['results_sha256'])
        self.bound(binding['report_path'], binding['report_sha256'])
        for name, key in [('figure', 'figure_sha256'), ('native_matrix', 'native_matrix_sha256')]:
            self.bound(self.sibling('pearson', pearson['artifacts'][name]), binding[key])
        check(binding['parameters'] == pearson['parameters'] and
              binding['native_module_sha256'] == pearson['native_module_sha256'] and
              binding['collection_references'] == pearson['collection_references'], 'Approval parameters changed')
        datasets = {x['index']: x for x in binding['datasets']}
        check(set(selected) <= set(datasets), 'Approved dataset index missing')
        for item in binding['datasets']:
            self.bound(item['path'], item['sha256'])
            match = [x for x in pearson['datasets'] if x['index'] == item['index']]
            check(len(match) == 1 and all(match[0][k] == item[k] for k in ['roi','rows','collection_run_id']), 'Pearson dataset mismatch')
        collections = {}
        for path in self.refs:
            if Path(path).name == 'manifest.json':
                doc = self.read_json(path)
                collections[doc['run_id']] = (path, doc)
                for item in doc['files']:
                    self.bound(item['source'], item['sha256'])
                    self.bound(item['destination'], item['destination_sha256'])
                    check(item['sha256'] == item['destination_sha256'], 'Collection copy mismatch')
        for ref in pearson['collection_references'] + d['localization_merge']['localization_collections']:
            path, _ = collections[ref['collection_run_id']]
            self.bound(path, ref['manifest_sha256'])
        for role in ['trace_merge','localization_merge','baseline','annotation','trace_analysis','localization_analysis']:
            doc = d[role]
            check(doc['pearson_run_id'] == pearson['run_id'] and
                  doc['approval_revision'] == approval['revision'] and
                  doc['approval_fingerprint'] == approval['fingerprint'] and
                  doc['selected_dataset_indices'] == selected, f'Approval provenance mismatch: {role}')
        for role in ['trace_merge','localization_merge']:
            doc = d[role]
            check(doc['approval_snapshot'] == approval, f'Approval snapshot mismatch: {role}')
            check(doc['results_sha256'] == self.refs[self.roles['pearson']], 'Merge Pearson hash mismatch')
            self.bound(self.sibling(role, doc['artifacts']['merged']), doc['merged_sha256'])
        ts, ls = d['trace_merge']['sources'], d['localization_merge']['sources']
        check([x['index'] for x in ts] == selected and [x['approved_trace_index'] for x in ls] == selected, 'Merge selection mismatch')
        for t, loc in zip(ts, ls):
            item = datasets[t['index']]
            check(all(t[k] == item[k] for k in ['collection_run_id','filename','sha256','roi','rows']), 'Tracing contribution mismatch')
            self.bound(t['path'], t['sha256'])
            _, coll = collections[t['collection_run_id']]
            original = next(x for x in coll['files'] if x['destination_name'] == t['filename'])
            check(loc['trace_source'] == original['source'] and loc['trace_sha256'] == t['sha256'] and
                  loc['source_roi_directory'] == original['source_roi_directory'] and loc['roi'] == t['roi'], 'Localization ROI association mismatch')
            _, lcoll = collections[loc['collection_run_id']]
            source = next(x for x in lcoll['files'] if x['destination_name'] == loc['filename'])
            check(all(loc[k] == source[k] for k in ['source','source_relative','source_roi_directory','roi','rows','sha256']), 'Localization collection mismatch')
            self.bound(loc['source'], loc['sha256'])
        # Step 0 evidence describes original inputs, not renamed annotated traces.
        check(d['step0']['experiment_root'] == d['annotation']['experiment_root'], 'Experiment root mismatch')
        for roi in d['step0']['rois']:
            for table in roi['tables']:
                self.bound(Path(d['step0']['experiment_root']) / table['path'], table['sha256'])
            stats = roi.get('trace_stats', {})
            if stats.get('status') == 'COMPUTED':
                self.bound(stats['source_file'], stats['input_sha256'])
        for role, edges in {
            'baseline': [('trace_merge_run_id','trace_merge','run_id'),('merged_sha256','trace_merge','merged_sha256'),('provenance_sha256','trace_merge',None)],
            'annotation': [('baseline_run_id','baseline','run_id'),('baseline_sha256','baseline',None),('baseline_fingerprint','baseline','baseline_fingerprint'),('merged_sha256','trace_merge','merged_sha256'),('merge_provenance_sha256','trace_merge',None),('mapping_sha256','mapping',None),('reference_sha256','reference',None)],
            'trace_analysis': [('baseline_run_id','baseline','run_id'),('baseline_sha256','baseline',None),('annotation_run_id','annotation','run_id'),('annotation_sha256','annotation',None),('analysis_input_sha256','annotation','annotated_sha256'),('trace_merge_run_id','trace_merge','run_id'),('merge_provenance_sha256','trace_merge',None)],
            'localization_analysis': [('localization_merge_run_id','localization_merge','run_id'),('merged_sha256','localization_merge','merged_sha256'),('provenance_sha256','localization_merge',None)],
        }.items():
            for field, target, target_field in edges:
                self.peer(role, field, target, target_field)
        for role, expected_scope in [('trace_analysis','merged_unfiltered_tracing'), ('localization_analysis','merged_unfiltered_localization')]:
            check(d[role]['status'] == 'ANALYZED' and d[role]['scope'] == expected_scope, f'Analysis incomplete or wrong scope: {role}')
        for numeric, analysis in [('trace_numerical','trace_analysis'), ('localization_numerical','localization_analysis')]:
            check(Path(self.roles[numeric]) == self.sibling(analysis,'numerical_outputs.json'), 'Numerical artifact role mismatch')
        check(Path(self.roles['mapping']) == self.sibling('annotation','barcode_mapping.json'), 'Mapping role mismatch')
        check(d['baseline']['source_file'] == str(self.sibling('trace_merge',d['trace_merge']['artifacts']['merged'])), 'Baseline input path mismatch')
        check(d['localization_analysis']['source_file'] == str(self.sibling('localization_merge',d['localization_merge']['artifacts']['merged'])), 'Localization analyzer input path mismatch')
        check(d['baseline']['approved_source_contributions'] == d['annotation']['approved_source_contributions'] == d['trace_analysis']['approved_source_contributions'], 'Approved source contributions changed')
        ann = d['annotation']
        check(ann['status'] == 'ANNOTATED' and d['baseline']['status'] == 'COMPUTED', 'Annotation or baseline incomplete')
        check(self.roles['reference'] == ann['reference_path'], 'Reference role mismatch')
        check(d['step0']['bed']['sha256'] == ann['bed_sha256'], 'Step 0 BED evidence mismatch')
        self.bound(ann['bed_path'], ann['bed_sha256'])
        self.bound(ann['reference_path'], ann['reference_sha256'])
        check(ann['assembly'] == d['reference']['assembly'] and ann['reference'] == d['reference'], 'Assembly evidence mismatch')
        check(ann['native_barcode_replacement'] is True and ann['native_mapping_override'] is False, 'Unexpected barcode behavior')
        for name, key in [('annotated_traces.ecsv','annotated_sha256'),('native_annotated.ecsv','native_output_sha256'),('native.log','native_log_sha256')]:
            self.bound(self.sibling('annotation',name), ann[key])
        for role, filename in [('baseline','statistics.json'),('trace_merge','provenance.json'),('localization_merge','provenance.json')]:
            # Existing downstream evidence supplies native log hashes for these stages.
            carrier, key = {'baseline':('trace_analysis','baseline_native_log_sha256'), 'trace_merge':('baseline','merge_native_log_sha256'), 'localization_merge':('localization_analysis','merge_native_log_sha256')}[role]
            self.bound(self.sibling(role,'native.log'), d[carrier][key])
        for role in ['trace_analysis','localization_analysis']:
            doc = d[role]
            path = self.sibling(role,'artifacts.json')
            self.bound(path, doc['artifact_manifest_sha256'])
            for item in self.read_json(path):
                self.bound(self.sibling(role,item['name']),item['sha256'])
        check(d['localization_analysis']['approved_roi_mapping'] == [
            {k:v for k,v in x.items() if k not in ['row_start','row_stop_exclusive','row_count','roi_mapping','source_metadata_yaml','source_column_metadata_yaml']} for x in ls], 'Analyzer ROI mapping mismatch')
        link = d['localization_analysis']['tracing_annotation']
        check(link['annotation_run_id'] == ann['run_id'] and link['annotation_sha256'] == self.refs[self.roles['annotation']] and link['mapping_sha256'] == self.refs[self.roles['mapping']], 'Localization barcode mapping mismatch')
        self.bound(link['mapping_path'],link['mapping_sha256'])


def esc(value):
    if value is None:
        return 'Unavailable'
    return html.escape(str(value))


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th>'+esc(x)+'</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in rows) + '</tbody></table></div>'


def render(ev, output, generated):
    d = ev.docs
    def link(path, label=None):
        check(str(path) in ev.refs, 'Unverified link')
        return '<a href="'+html.escape(Path(path).as_uri())+'">'+esc(label or Path(path).name)+'</a>'
    def figures(role):
        paths = [p for p in ev.refs if Path(p).parent == Path(ev.roles[role]).parent and p.endswith('.png')]
        return ''.join('<figure><a href="'+html.escape(Path(p).as_uri())+'"><img loading="lazy" src="'+html.escape(Path(p).as_uri())+'" alt="'+esc(Path(p).stem)+'"></a><figcaption>'+esc(Path(p).name)+'</figcaption></figure>' for p in sorted(paths))
    s,b,a = d['step0']['summary'],d['baseline'],d['annotation']
    approval = d['approval']
    title = ev.manifest['title']
    parts = ['<header><p class="eyebrow">PRE-FILTERING EXPERIMENT QC</p><h1>'+esc(title)+'</h1><p>Saved scientific evidence · '+esc(generated)+'</p></header>',
        '<section class="notice"><strong>Completed analyses; scientific limitations remain.</strong><p>This report composes saved native results. Execution success and Step 0 PASS are not biological acceptance. No additional filtering was applied; supplied localization metadata already says filtered / registered.</p></section>',
        '<nav><a href="#initial">Initial datasets</a><a href="#pearson">Pearson & approval</a><a href="#merged">Merging & baseline</a><a href="#genome">Genomic mapping</a><a href="#traces">Trace analysis</a><a href="#localizations">Localization analysis</a><a href="#limits">Limitations</a><a href="#evidence">Evidence</a></nav>',
        '<section id="initial"><h2>1 · Initial datasets</h2><p>Step 0: <strong>'+esc(s['status'])+'</strong> within the saved validation policy. '+esc(s['warning_count'])+' warnings, '+esc(s['error_count'])+' errors, '+esc(s['incomplete_count'])+' incomplete checks. '+esc(s['tracing_tables'])+' tracing tables and '+esc(s['localization_tables'])+' localization tables found.</p>']
    rows=[]
    for roi in d['step0']['rois']:
        stats=roi.get('trace_stats',{})
        tr=next((x for x in roi['tables'] if x['role']=='tracing'),{})
        loc=next((x for x in roi['tables'] if x['role']=='localization'),{})
        rows.append([roi['directory'],tr.get('record_count'),loc.get('record_count'),stats.get('status'),stats.get('unique_trace_count'),stats.get('unique_barcode_count'),(', '.join(tr['missing_barcodes']) or 'None reported') if 'missing_barcodes' in tr else None])
    parts += [table(['Original ROI','Trace rows','Localization rows','Native trace_stats','Global Trace_IDs within ROI','Barcodes','Missing trace barcodes'],rows), '<p>These are original per-ROI statistics. Native trace_stats provides counts, not precision estimates, distributions or filtering thresholds.</p></section>', '<section id="pearson"><h2>2 · Pearson correlation and human review</h2>']
    ds={x['index']:x for x in d['pearson']['datasets']}
    parts += [table(['Dataset indices','Compared ROIs','Pearson r','Shared barcode pairs'],[[str(x['first'])+' / '+str(x['second']),str(ds[x['first']]['roi'])+' / '+str(ds[x['second']]['roi']),format(x['pearson_r'],'.4f') if x.get('pearson_r') is not None else 'Undefined',x.get('shared_non_nan_pairs')] for x in d['pearson']['comparisons']]),
        '<p>Human decision: <strong>'+esc(approval['status'])+'</strong>. Selected dataset indices '+esc(approval['selected_dataset_indices'])+'. Current approval matches the exact saved evidence.</p>',
        table(['Dataset index','ROI','Approved'],[[x['index'],x['roi'],x['index'] in approval['selected_dataset_indices']] for x in d['pearson']['datasets']]),figures('pearson'), '</section>',
        '<section id="merged"><h2>3 · Merging and unfiltered baseline</h2>',
        table(['Dataset','Rows','ROIs','Barcodes','Global unique Trace_IDs','ROI / Trace_ID pairs'],[
            ['Original merged traces',b.get('row_count'),b.get('unique_roi_count'),b.get('unique_barcode_count'),b.get('global_unique_trace_id_count'),b.get('roi_trace_count')],
            ['Merged localizations',d['localization_merge']['row_count'],d['localization_merge']['roi_count'],d['localization_merge']['barcode_count'],'Not applicable','Not applicable']]),
        '<p>Step 1c statistics remain bound to the original merged, unfiltered tracing artifact. Global unique Trace_ID values, ROI/Trace_ID pairs and original per-ROI counts are distinct definitions; they are not allele counts.</p>',
        table(['Approved index','Original ROI directory','Trace ROI mapping','Trace source rows','Localization source rows'],[[t['index'],loc['source_roi_directory'],json.dumps(t['roi_mapping']),t['row_count'],loc['row_count']] for t,loc in zip(d['trace_merge']['sources'],d['localization_merge']['sources'])]),'</section>',
        '<section id="genome"><h2>4 · Genomic coordinates and barcode identities</h2><p>Assembly: <strong>'+esc(a['assembly'])+'</strong>. '+esc(d['reference']['authority'])+' Original inherited mm10 metadata is preserved in old artifacts; it is not assembly authority. Only the annotated derivative carries the confirmed assembly.</p><p>Native five-column BED assignment with barcode replacement. Mapping coverage: '+esc(a['mapping_coverage']['mapped_rows'])+' / '+esc(a['mapping_coverage']['total_rows'])+' rows. Localizations retain original barcode IDs; annotated traces use replacement IDs. Join spot identities with Spot_ID / Buid, never barcode alone.</p>']
    mapping=d['mapping']
    parts += [table(list(mapping[0]) if mapping else ['Mapping unavailable'],[[json.dumps(v) if isinstance(v,(dict,list)) else v for v in x.values()] for x in mapping]),'</section>',
        '<section id="traces"><h2>5 · Native trace analysis</h2><p>Status: '+esc(d['trace_analysis']['status'])+'. Verified annotated, unfiltered traces. Native grouping uses global Trace_ID; cross-ROI collisions were checked by scientific execution.</p>']
    ns=d['trace_analysis'].get('neighbor_statistics',{})
    parts += ['<p>Neighbor measurements: '+esc(ns.get('status'))+'; '+esc(ns.get('observation_count'))+' observations. The following are signed coordinate displacements, not scalar Euclidean distance. Coordinate units: '+esc(', '.join(d['trace_analysis']['input_checks'].get('coordinate_units',[])))+'.</p>',table(['Axis','Native mean displacement','Native standard deviation'],[[ax,ns.get('mean_d'+ax) if ns.get('status')=='AVAILABLE' else None,ns.get('std_d'+ax) if ns.get('status')=='AVAILABLE' else None] for ax in 'xyz']),figures('trace_analysis'),'</section>',
        '<section id="localizations"><h2>6 · Native localization analysis</h2><p>Status: '+esc(d['localization_analysis']['status'])+'. <strong>ROIs are pooled</strong> in the native plots; this is not a per-ROI comparison. Localization z units are undeclared; raw z values are shown without inferred calibration.</p><p>Four panels: SNR by original barcode; SNR versus raw z centroid colored by object class; localization counts by original barcode; roundness versus skew colored by original barcode. The filename mentions fluxes, but these are the actual panels. Native execution returns no statistics object; plotting data and counts are saved.</p>',
        table(['Original barcode','Native localization count'],[[x['barcode'],x['count']] for x in d['localization_numerical'].get('native_barcode_counts',[])]),figures('localization_analysis'),'</section>',
        '<section id="limits"><h2>7 · Limitations and unavailable QC evidence</h2><ul><li>Trace_ID represents a segmented nucleus, not necessarily one chromosome or allele. Repeated-barcode observations remain; Pearson retains the last row per barcode and does not separate alleles.</li><li>Localization ROIs are pooled; z units and assembly are not fully declared. Do not infer localization calibration from tracing metadata.</li><li>Localization precision, fiducial registration residuals, biological equivalence and allele-resolved QC are unavailable in these saved analyses.</li><li>No filtering statistics or scientific acceptance thresholds were generated. The native relative-frequency figure bins multiplicities 1–8; complete returned values remain saved.</li><li>The native figure can compress extreme roundness values; original barcode labels are non-contiguous. No outlier filtering or new summary statistics are applied here.</li></ul>']
    for role in ['pearson','trace_merge','localization_merge','baseline','annotation','trace_analysis','localization_analysis','trace_numerical','localization_numerical']:
        parts.append('<details><summary>'+esc(role)+' · saved warnings</summary><ul>'+''.join('<li>'+esc(w)+'</li>' for w in d[role].get('warnings',[]))+'</ul></details>')
    parts.append('<details><summary>Step 0 · complete saved findings</summary>'+table(['Severity','Code','Message','Path'],[[f.get(k) for k in ['severity','code','message','path']] for f in d['step0']['findings']])+'</details></section>')
    parts += ['<section id="evidence"><h2>8 · Provenance and complete evidence</h2><p>All listed files were SHA-256 verified before composition and rechecked before publication. Report generation reads saved values and never runs Traceratops. Approval status is a point-in-time evidence check, not permission for subsequent processing. Native arrays are referenced, not embedded. Approval is a trusted-host record, not an independent human-identity signature.</p>',table(['Stage','Run ID','Native version','Saved status'],[[r,d[r].get('run_id'),d[r].get('traceratops_version'),d[r].get('status',d[r].get('phase'))] for r in ['pearson','trace_merge','localization_merge','baseline','annotation','trace_analysis','localization_analysis']]),'<details><summary>Artifact links and SHA-256 checksums</summary><ul>'+''.join('<li>'+link(p)+' <code>'+esc(sha)+'</code></li>' for p,sha in sorted(ev.refs.items()))+'</ul></details></section>']
    style = '''body{margin:0;background:#f5f3ed;color:#222c35;font:16px/1.6 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:36px 28px}header{padding:26px 0}h1{font:42px/1.2 Georgia,serif}h2{font:28px Georgia,serif;color:#225e63}.eyebrow{letter-spacing:.12em;color:#426a6d;font-size:13px}section{background:white;border:1px solid #dedfd8;border-radius:10px;padding:26px;margin:24px 0}.notice{border-left:5px solid #ab7136;background:#fffaf1}nav{display:flex;flex-wrap:wrap;gap:14px}a{color:#225e63}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd;vertical-align:top}th{background:#edf3f2}.scroll{overflow:auto}figure{margin:26px 0}img{width:100%;height:auto;max-height:760px;object-fit:contain}figcaption{font-size:13px;color:#59616a}details{margin:15px 0}summary{cursor:pointer;font-weight:600}code{font-size:11px;overflow-wrap:anywhere}li{margin:7px 0}#evidence li{overflow-wrap:anywhere}@media print{body{background:white}main{padding:0}section{break-inside:avoid}nav{display:none}details{display:block}img{max-height:600px}}'''
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\' file:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><title>'+esc(title)+'</title><style>'+style+'</style></head><body><main>'+''.join(parts)+'</main></body></html>'


def generate(manifest_id, manifest_sha256):
    start=time.perf_counter()
    check(re.fullmatch('[A-Za-z0-9_-]{1,80}',manifest_id) is not None, 'Invalid manifest ID')
    check(re.fullmatch('[a-f0-9]{64}',manifest_sha256) is not None, 'Invalid manifest checksum')
    manifest_root=Path(os.environ['CHROMATIN_QC_MANIFEST_DIR']).absolute()
    roots=[Path(x).absolute() for x in os.environ['CHROMATIN_REPORT_ARTIFACT_ROOTS'].split(os.pathsep) if x]
    check(bool(roots), 'No authorized artifact roots configured')
    path=manifest_root/(manifest_id+'.json')
    sha, raw=regular(path,[manifest_root],capture=True)
    check(sha==manifest_sha256,'Manifest checksum mismatch')
    manifest=json.loads(raw)
    check(manifest.get('schema_version') == 1, 'Unsupported manifest version')
    ev=Evidence(manifest,roots)
    output_root=Path(os.environ['CHROMATIN_REPORT_OUTPUT_DIR']).absolute()
    protected=[Path(ev.roles[r]).parent for r in ROLES if r not in ['reference']]
    protected.append(Path(ev.docs['step0']['experiment_root']))
    check(not any(output_root.is_relative_to(p) or p.is_relative_to(output_root) for p in protected), 'Output overlaps scientific inputs')
    for part in [output_root, *output_root.parents]:
        check(not part.is_symlink(), 'Output root contains a symlink')
    output_root.mkdir(parents=True,exist_ok=True)
    run_id=uuid4().hex
    pending=output_root/(run_id+'.pending')
    final=output_root/run_id
    pending.mkdir(mode=0o700)
    try:
        generated=datetime.now(timezone.utc).isoformat()
        content=render(ev,final/'report.html',generated)
        (pending/'report.html').write_text(content,encoding='utf-8')
        record={'schema_version':1,'run_id':run_id,'status':'COMPLETE_WITH_LIMITATIONS','generated_at_utc':generated,
                'manifest_id':manifest_id,'manifest_sha256':sha,'report_sha256':digest(content.encode()),
                'source_artifacts':manifest['files'],'approval_revision':ev.docs['approval']['revision'],
                'scientific_calculations_run':0,'provider_usage':None}
        (pending/'evidence.json').write_text(json.dumps(record,indent=2)+'\n')
        ev.verify_all()
        check(regular(path,[manifest_root])[0]==sha,'Manifest changed during generation')
        pending.rename(final)
    except BaseException:
        for f in pending.iterdir():
            f.unlink()
        pending.rmdir()
        raise
    return {'run_id':run_id,'status':'COMPLETE_WITH_LIMITATIONS','path':str(final/'report.html'),
            'report_sha256':record['report_sha256'],'evidence_path':str(final/'evidence.json'),
            'verified_artifacts':len(ev.refs),'size_bytes':len(content.encode()),
            'execution_seconds':time.perf_counter()-start}
