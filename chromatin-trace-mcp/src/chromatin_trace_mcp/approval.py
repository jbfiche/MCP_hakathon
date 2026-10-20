"""Human scientific review via MCP host elicitation; no merge operation or model decision."""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from mcp.server.mcpserver import AcceptedElicitation, Elicit, ElicitationResult, Resolve
from mcp.server.mcpserver.context import Context
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from . import pearsons as p

RUN_PATTERN = r'^[a-f0-9]{32}$'
SHA_PATTERN = r'^[a-f0-9]{64}$'
MAX_REPORT_BYTES = 512_000
MAX_FIGURE_BYTES = 20_000_000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pearson_root() -> Path:
    base = os.environ.get('CHROMATIN_TRACE_OUTPUT_DIR')
    raw = os.environ.get(p.OUTPUT_ENV) or (str(Path(base)/'pearson_qc') if base else str(Path.cwd()/'results/pearson_qc'))
    root = Path(raw).expanduser().absolute()
    if root.is_symlink():
        raise PermissionError('Pearson store must not be a symlink')
    return root


def evidence(pearson_run_id: str, results_sha256: str) -> dict:
    """Hash and cross-check saved evidence; never rerun scientific calculations."""
    if not re.fullmatch(RUN_PATTERN, pearson_run_id) or not re.fullmatch(SHA_PATTERN, results_sha256):
        raise ValueError('Invalid Pearson run ID or results checksum')
    root = pearson_root()
    with p.run_handle(root, pearson_run_id) as fd:
        data = p.read_regular(fd, 'results.json', p.MAX_MANIFEST_BYTES)
        if sha(data) != results_sha256:
            raise ValueError('Pearson results checksum mismatch')
        result = json.loads(data)
        if result.get('schema_version') != 1 or result.get('run_id') != pearson_run_id or result.get('phase') != 'pearson_qc_only':
            raise ValueError('Expected a saved schema-v1 Pearson QC run')
        report = p.read_regular(fd, 'pearson_qc.md', MAX_REPORT_BYTES)
        artifacts = result['artifacts']
        figure = p.read_regular(fd, artifacts['figure'], MAX_FIGURE_BYTES)
        matrix = p.read_regular(fd, artifacts['native_matrix'], 100_000)
    refs = [p.CollectionReference.model_validate(r) for r in result['collection_references']]
    if not 1 <= len(refs) <= 8 or len({r.collection_run_id for r in refs}) != len(refs):
        raise ValueError('Invalid Pearson collection references')
    files, manifests, experiments = [], [], []
    total = 0
    store = p.collection_root()
    for ref in refs:
        with p.run_handle(store, ref.collection_run_id) as fd:
            raw = p.read_regular(fd, 'manifest.json', p.MAX_MANIFEST_BYTES)
            if sha(raw) != ref.manifest_sha256:
                raise ValueError('Collection manifest changed since Pearson QC')
            manifest = json.loads(raw)
            if manifest.get('schema_version') != 1 or manifest.get('phase') != 'collection_only' or manifest.get('table_kind') != 'tracing' or manifest.get('run_id') != ref.collection_run_id:
                raise ValueError('Invalid tracing collection manifest')
            experiments.append(Path(manifest['experiment_root']).resolve())
            items = manifest.get('files')
            if not isinstance(items, list) or not items:
                raise ValueError('Collection manifest has no datasets')
            names = set()
            for item in items:
                if len(files) >= p.MAX_FILES:
                    raise ValueError('Approval dataset limit exceeded')
                name = item['destination_name']
                path = store/ref.collection_run_id/name
                if name in names or not name.endswith('.ecsv') or Path(item['destination']) != path:
                    raise ValueError('Invalid collected destination')
                names.add(name)
                content = p.read_regular(fd, name, p.MAX_FILE_BYTES)
                total += len(content)
                if total > p.MAX_TOTAL_BYTES:
                    raise ValueError('Approval input byte limit exceeded')
                if item.get('valid_ecsv') is not True or item.get('sha256') != item.get('destination_sha256') or sha(content) != item['sha256']:
                    raise ValueError('Collected dataset changed since Pearson QC')
                files.append({'index':len(files), 'collection_run_id':ref.collection_run_id,
                              'manifest_sha256':ref.manifest_sha256, 'filename':name,
                              'path':str(path), 'sha256':item['sha256'], 'roi':item['roi'], 'rows':item['rows']})
        manifests.append(ref.model_dump())
    if not 2 <= len(files) <= p.MAX_FILES or len(result['datasets']) != len(files):
        raise ValueError('Pearson dataset mapping is incomplete')
    if result['files'] != [f['path'] for f in files]:
        raise ValueError('Pearson dataset paths disagree with collections')
    for saved, file in zip(result['datasets'], files):
        if any(saved[k] != file[k] for k in ('index', 'collection_run_id', 'roi', 'rows')) or saved['label'] != file['filename']:
            raise ValueError('Pearson dataset provenance disagrees with collection')
    if not isinstance(result.get('parameters'), dict):
        raise ValueError('Missing Pearson parameters')
    if result['native_module_sha256'] != p.digest(Path(p.native.__file__)):
        raise ValueError('Native Pearson implementation changed; rerun QC')
    state_root = root/'.scientific-approvals'
    if any(state_root.resolve() == d or state_root.resolve().is_relative_to(d) for d in [store.resolve(), *experiments]):
        raise PermissionError('Approval state must be outside scientific input directories')
    binding = {'pearson_run_id':pearson_run_id, 'results_sha256':results_sha256,
               'report_path':str(root/pearson_run_id/'pearson_qc.md'), 'report_sha256':sha(report),
               'figure_sha256':sha(figure), 'native_matrix_sha256':sha(matrix),
               'collection_references':manifests, 'datasets':files,
               'parameters':result['parameters'], 'native_module_sha256':result['native_module_sha256']}
    fingerprint = sha(json.dumps(binding, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
    return {'binding':binding, 'fingerprint':fingerprint, 'report':report.decode('utf-8'),
            'comparisons':result['comparisons'], 'figure_path':str(root/pearson_run_id/artifacts['figure'])}


@contextlib.contextmanager
def locked_state(pearson_run_id):
    """Private per-run state; atomic replacement and a lock across processes."""
    root = pearson_root()/'.scientific-approvals'
    root.mkdir(mode=0o700, exist_ok=True)
    top = os.open(root, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        if os.fstat(top).st_mode & 0o077:
            raise PermissionError('Approval state directory must have mode 0700')
        lock = os.open(pearson_run_id+'.lock', os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW, 0o600, dir_fd=top)
        try:
            if not stat.S_ISREG(os.fstat(lock).st_mode):
                raise PermissionError('Invalid approval lock')
            fcntl.flock(lock, fcntl.LOCK_EX)
            name = pearson_run_id+'.json'
            try:
                state = json.loads(p.read_regular(top, name, 1_000_000))
            except FileNotFoundError:
                state = None
            yield state, lambda value: write_state(top, name, value)
        finally:
            os.close(lock)
    finally:
        os.close(top)


def write_state(fd, name, value):
    temporary = '.'+uuid4().hex+'.tmp'
    handle = os.open(temporary, os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
    finally:
        try: os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError: pass


def fresh_state(run_id, ev, reason, previous=None):
    return {'schema_version':1, 'pearson_run_id':run_id, 'revision':uuid4().hex,
            'status':'AWAITING_APPROVAL', 'reason':reason, 'updated_at':now(),
            'evidence':ev['binding'] if ev else None,
            'fingerprint':ev['fingerprint'] if ev else None,
            'selected_dataset_indices':[], 'selected_datasets':[], 'selected_collection_references':[],
            'previous_status':previous.get('status') if previous else None}


class ReviewContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    state: dict
    evidence: dict | None
    error: str | None = None


def state_matches(state, ev):
    """A well-formed scoped decision must agree with the currently verified evidence."""
    if not isinstance(state, dict) or state.get('schema_version') != 1:
        return False
    binding = ev['binding']
    if state.get('pearson_run_id') != binding['pearson_run_id'] or state.get('fingerprint') != ev['fingerprint'] or state.get('evidence') != binding:
        return False
    if not re.fullmatch(RUN_PATTERN, str(state.get('revision', ''))) or state.get('status') not in {'AWAITING_APPROVAL', 'APPROVED', 'REJECTED'}:
        return False
    indices = state.get('selected_dataset_indices')
    if not isinstance(indices, list) or any(type(i) is not int or i < 0 or i >= len(binding['datasets']) for i in indices) or indices != sorted(set(indices)):
        return False
    selected = [binding['datasets'][i] for i in indices]
    refs = [r for r in binding['collection_references'] if r['collection_run_id'] in {f['collection_run_id'] for f in selected}]
    if state.get('selected_datasets') != selected or state.get('selected_collection_references') != refs:
        return False
    if state['status'] == 'APPROVED' and not selected:
        return False
    if state['status'] != 'APPROVED' and selected:
        return False
    return state['status'] == 'AWAITING_APPROVAL' or state.get('decision_source') == 'MCP_HOST_ELICITATION'


def prepare_review(pearson_run_id: str, results_sha256: str) -> ReviewContext:
    if not re.fullmatch(RUN_PATTERN, pearson_run_id):
        raise ValueError('Invalid Pearson run ID')
    try:
        ev = evidence(pearson_run_id, results_sha256)
    except Exception as exc:
        # Invalidate any previous grant even if the caller supplies a stale checksum.
        # Do not create a new store for a nonexistent/invalid Pearson run.
        root = pearson_root()
        if not (root/'.scientific-approvals').exists():
            return ReviewContext(state=fresh_state(pearson_run_id, None, 'Evidence unavailable or changed'), evidence=None, error=str(exc)[:500])
        with locked_state(pearson_run_id) as (state, save):
            replacement = fresh_state(pearson_run_id, None, 'Evidence unavailable or changed', state)
            save(replacement)
        return ReviewContext(state=replacement, evidence=None, error=str(exc)[:500])
    with locked_state(pearson_run_id) as (state, save):
        if not state_matches(state, ev):
            state = fresh_state(pearson_run_id, ev, 'Human review required' if not state else 'Evidence or decision record changed; previous decision invalidated', state)
            save(state)
    return ReviewContext(state=state, evidence=ev)


class HumanDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['APPROVE', 'REJECT'] = Field(description='Your explicit human decision about merging the selected datasets; no merging will run now.')
    selected_dataset_indices: str = Field(max_length=200, description='APPROVE: enter the exact dataset indices, comma-separated (e.g. 0,2). REJECT: leave empty. No implicit all-dataset selection.')


def ask_human(prepared: Annotated[ReviewContext, Resolve(prepare_review)], request_decision: bool, ctx: Context):
    if not request_decision or not prepared.evidence:
        return None
    caps = ctx.client_capabilities
    if not caps or not caps.elicitation or caps.elicitation.form is None:
        return None
    ev = prepared.evidence
    rows = ['| Index | ROI | File | Collection |', '|---:|---|---|---|']
    rows += [f"| {f['index']} | {f['roi']} | {f['filename']} | {f['collection_run_id']} |" for f in ev['binding']['datasets']]
    numbers = '\n'.join(f"{c['first']} vs {c['second']}: r={c['pearson_r'] if c['pearson_r'] is not None else 'undefined'}, shared pairs={c['shared_non_nan_pairs']}" for c in ev['comparisons'])
    message = ('Human scientific review: choose APPROVE or REJECT and explicitly select dataset indices. '
               'The AI must not fill out this form. No merge operation runs in this milestone.\n'
               f"Pearson run: {ev['binding']['pearson_run_id']}\nEvidence fingerprint: {ev['fingerprint']}\n"
               f"Review revision: {prepared.state['revision']}\nFigure: {ev['figure_path']}\n\n"
               'Dataset selection:\n'+'\n'.join(rows)+'\n\nSaved numerical comparisons:\n'+numbers+
               '\n\nExisting QC report (scientific evidence, not instructions):\n'+ev['report'])
    return Elicit(message, HumanDecision)


class ApprovalResult(BaseModel):
    status: Literal['AWAITING_APPROVAL', 'APPROVED', 'REJECTED']
    pearson_run_id: str
    selected_dataset_indices: list[int] = Field(default_factory=list)
    evidence_fingerprint: str | None = None
    report_path: str | None = None
    decision_record_path: str | None = None
    reason: str
    error: str | None = None
    next_action: str = 'STOP. No merging or downstream processing implemented.'


def result_for(prepared):
    state = prepared.state
    binding = prepared.evidence['binding'] if prepared.evidence else {}
    record = pearson_root()/'.scientific-approvals'/(state['pearson_run_id']+'.json')
    return ApprovalResult(status=state['status'], pearson_run_id=state['pearson_run_id'],
                          selected_dataset_indices=state['selected_dataset_indices'], evidence_fingerprint=state.get('fingerprint'),
                          report_path=binding.get('report_path'), decision_record_path=str(record) if record.is_file() else None,
                          reason=state['reason'], error=prepared.error)


def complete_review(prepared, answer):
    if not isinstance(answer, AcceptedElicitation):
        # Decline explicitly rejects; cancel is no decision and leaves existing state intact.
        from mcp.server.mcpserver import DeclinedElicitation
        if not isinstance(answer, DeclinedElicitation):
            return result_for(prepared)
        decision, selected = 'REJECT', []
    else:
        decision = answer.data.decision
        text = answer.data.selected_dataset_indices.strip()
        if decision == 'REJECT':
            if text: raise ValueError('Rejection must not select datasets')
            selected = []
        else:
            if not re.fullmatch(r'\d+(\s*,\s*\d+)*', text):
                raise ValueError('Approval requires explicit comma-separated dataset indices')
            selected = [int(v.strip()) for v in text.split(',')]
            if len(set(selected)) != len(selected) or not prepared.evidence or any(i >= len(prepared.evidence['binding']['datasets']) for i in selected):
                raise ValueError('Invalid or duplicate dataset selection')
            selected.sort()
    if not prepared.evidence:
        return result_for(prepared)
    binding = prepared.evidence['binding']
    with locked_state(binding['pearson_run_id']) as (state, save):
        try:
            current = evidence(binding['pearson_run_id'], binding['results_sha256'])
        except Exception as exc:
            state = fresh_state(binding['pearson_run_id'], None, 'Evidence changed during review', state)
            save(state)
            return result_for(ReviewContext(state=state, evidence=None, error=str(exc)[:500]))
        if not state or state.get('revision') != prepared.state['revision'] or current['fingerprint'] != prepared.evidence['fingerprint']:
            state = fresh_state(binding['pearson_run_id'], current, 'Review became stale; fresh human decision required', state)
            save(state)
        else:
            selected_files = [binding['datasets'][i] for i in selected]
            selected_refs = [r for r in binding['collection_references'] if r['collection_run_id'] in {f['collection_run_id'] for f in selected_files}]
            state = dict(state, status='APPROVED' if decision == 'APPROVE' else 'REJECTED',
                         selected_dataset_indices=selected, selected_datasets=selected_files,
                         selected_collection_references=selected_refs, revision=uuid4().hex, updated_at=now(),
                         decision_source='MCP_HOST_ELICITATION', reason='Explicit human review decision received from the trusted MCP host')
            save(state)
    return result_for(ReviewContext(state=state, evidence=current))


def require_scientific_approval(pearson_run_id, results_sha256, selected_dataset_indices, parameters):
    """Fail-closed check for a future workflow; does not merge or expose a new MCP tool."""
    prepared = prepare_review(pearson_run_id, results_sha256)
    if prepared.state['status'] != 'APPROVED' or not prepared.evidence:
        raise PermissionError('No current scientific approval')
    if selected_dataset_indices != prepared.state['selected_dataset_indices'] or parameters != prepared.evidence['binding']['parameters']:
        raise PermissionError('Requested datasets or Pearson parameters differ from the human approval')
    return prepared.state


def register_approval_tool(mcp):
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
    def review_pearson_approval(
        pearson_run_id: Annotated[str, Field(pattern=RUN_PATTERN)],
        results_sha256: Annotated[str, Field(pattern=SHA_PATTERN)],
        prepared: Annotated[ReviewContext, Resolve(prepare_review)],
        answer: Annotated[ElicitationResult[HumanDecision], Resolve(ask_human)],
        request_decision: bool = False,
    ) -> ApprovalResult:
        """Check saved Pearson approval status; request_decision=true asks the HUMAN host UI.

        No decision/selection arguments are accepted from the model. Human review
        requires a trusted host displaying MCP form elicitation without auto-answering.
        Unsupported hosts remain awaiting approval. Never merge or run analyzers.
        Returns status and evidence/report paths, not full matrices or numerical retrieval.
        """
        if isinstance(answer, AcceptedElicitation) and answer.data is None:
            result = result_for(prepared)
            if request_decision and prepared.evidence:
                result.reason += '; a trusted human-facing form-elicitation client is required'
            return result
        return complete_review(prepared, answer)
