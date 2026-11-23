"""Small query handoffs; complete responses stay in private workspace files."""
from __future__ import annotations

import copy
import fcntl
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from base.query_workflow import query_records, create_result_view, result_view_name
from runtime import BasilError, service_api_base, auth_headers, validate_timeout, DEFAULT_TIMEOUT

# Budget the actual pretty-printed stdout, including escaped/multibyte fields.
OUTPUT_BYTES = 8000


def _root():
    root = Path.cwd() / '.basil-query-results'
    root.mkdir(mode=0o700, exist_ok=True)
    return root.resolve()


def _write(path, value):
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_result(result):
    path = _root() / (uuid4().hex + '.json')
    _write(path, {'apiBase': service_api_base(), 'result': result})
    return str(path)


def summary(result, path, *, delivery=False):
    """Keep status/link intact; include only whole preview values that fit."""
    workflow = {k: v for k, v in result['workflow'].items()
                if k not in {'effectiveQuery', 'originalSnapshotLink'}}
    rows = result['data']['recordList']
    out = {'success': result.get('success'), 'code': result.get('code'),
           'resultFile': path, 'workflow': workflow,
           'data': {'recordList': []}, 'returnedCount': len(rows),
           'previewComplete': False}
    if delivery:
        ready = (workflow.get('viewStatus') == 'created'
                 and bool(result['data'].get('snapshotLink'))
                 and workflow.get('linkStatus') in {'legacy_route_corrected', 'returned_unverified'})
        out['success'] = ready
        out['code'] = 0 if ready else 'QUERY_RESULT_UNAVAILABLE'
    if 'snapshotLink' in result['data']:
        out['data']['snapshotLink'] = result['data']['snapshotLink']
    addition = result.get('addition')
    if isinstance(addition, dict) and 'total' in addition:
        out['addition'] = {'total': addition['total']}

    def fits():
        return len(json.dumps(out, ensure_ascii=False, indent=2).encode('utf-8')) + 1 <= OUTPUT_BYTES

    # Even pathological provider metadata must not produce broken stdout JSON.
    if not fits():
        return {'success': False, 'resultFile': path,
                'error': 'Result metadata exceeds output budget; read the saved result. Do not recreate the view.'}
    complete = True
    for row in rows[:5]:
        preview = {}
        out['data']['recordList'].append(preview)
        for key, value in row.items():
            if key == 'fields' and isinstance(value, dict):
                preview[key] = {}
                for field, cell in value.items():
                    preview[key][field] = cell
                    if not fits():
                        del preview[key][field]
                        complete = False
            else:
                preview[key] = value
                if not fits():
                    del preview[key]
                    complete = False
        if not fits():
            out['data']['recordList'].pop()
            complete = False
            break
    out['previewComplete'] = complete and len(rows) <= 5
    return out


def query(payload):
    unknown = set(payload) - {'operation', 'query', '_timeout'}
    if unknown or payload.get('operation') != 'record_query':
        raise BasilError('record_query accepts operation, query and _timeout only')
    result = query_records({**payload, 'operation': 'record_query_snapshot'})
    return summary(result, save_result(result))


def _load_result(path):
    """Reject damaged handoffs before persisting an outcome or contacting the API."""
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError):
        raise BasilError('Invalid saved query result; do not recreate its view') from None
    if not isinstance(saved, dict) or not isinstance(saved.get('apiBase'), str):
        raise BasilError('Invalid saved query result environment')
    result = saved.get('result')
    if not isinstance(result, dict):
        raise BasilError('Invalid saved query result')
    data, workflow = result.get('data'), result.get('workflow')
    if (not isinstance(data, dict) or not isinstance(data.get('recordList'), list)
            or any(not isinstance(row, dict) for row in data['recordList'])
            or not isinstance(workflow, dict)
            or workflow.get('viewStatus') not in (
                'pending', 'created', 'failed_or_unknown',
                'not_created_empty_page', 'not_created_unsupported_scope')):
        raise BasilError('Invalid saved query result structure; do not recreate its view')
    if workflow['viewStatus'] == 'pending':
        effective = workflow.get('effectiveQuery')
        if not isinstance(effective, dict) or effective.get('tableId') is None:
            raise BasilError('Saved query result has no effective query')
    return saved


def create(payload):
    if set(payload) - {'operation', 'resultFile', 'viewName', '_timeout'}:
        raise BasilError('query-result creation accepts resultFile, viewName and _timeout only')
    if payload.get('operation') != 'view_create_query_result':
        raise BasilError('operation must be view_create_query_result')
    name = payload.get('viewName', 'Query results')
    if not isinstance(name, str) or not name.strip():
        raise BasilError('viewName must be a non-empty string')
    reference = payload.get('resultFile')
    if not isinstance(reference, str):
        raise BasilError('resultFile must be returned by record_query')
    path = Path(reference).resolve()
    if path.parent != _root() or path.suffix != '.json' or not path.is_file():
        raise BasilError('resultFile must be an existing query result in this workspace')
    # Serialize callers and persist an intent before POST. A lost response must
    # not turn a retry into another hidden view.
    with path.with_suffix('.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        saved = _load_result(path)
        if saved['apiBase'] != service_api_base():
            raise BasilError('query result belongs to a different API environment')
        result = saved['result']
        if result['workflow']['viewStatus'] == 'pending':
            # No POST has begun: local preflight failures must leave the result
            # pending and preserve the normal auth helper/error contract.
            validate_timeout(payload.get('_timeout', DEFAULT_TIMEOUT))
            auth_headers()
            result_view_name(result, name)
            pending = copy.deepcopy(saved)
            pending['result']['workflow'].update(viewStatus='failed_or_unknown',
                failedStage='view_create', retryAllowed=False,
                error='Creation started; response not yet saved. Do not repeat creation.')
            _write(path, pending)
            result = create_result_view(result, name, payload.get('_timeout'))
            saved['result'] = result
            _write(path, saved)
        # Do not send record data again on the create call.
        out = summary({**result, 'data': {**result['data'], 'recordList': []}}, str(path), delivery=True)
        out.pop('returnedCount', None)
        out.pop('previewComplete', None)
        if 'data' in out:
            out['data'].pop('recordList', None)
        return out
