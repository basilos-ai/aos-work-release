"""Attempt-local search handoff. Mechanical coverage checks, not semantic judgment."""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import tempfile
import time

import runtime
from runtime import BasilError
from library.search_validation import file_id_string, plan_to_body
from library.metadata_catalog import compact_catalog, fetch_metadata_catalog


TTL = 4 * 60 * 60
ROOT = Path(tempfile.gettempdir()) / f'basil-library-review-{os.getuid()}'
COMMON = {'operation', 'attemptId', 'sessionId'}
FIELDS = {
    'catalog': {'_timeout', 'view'},
    'search': {'intent', 'plan', 'inspectPages', '_timeout'},
    'next': {'inspectPages', '_timeout'},
    'read': {'maxBytes'}, 'ack': {'receipt'},
    'review': {'decisions'}, 'refine': {'inspectPages', '_timeout'},
    'deliver': set(), 'close': set(),
}


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _binding(attempt, salt):
    # Compare only; never persist headers, tokens, or the Runtime domain.
    material = [attempt, runtime.runtime_origin(runtime.RUNTIME_DOMAIN),
                runtime.AUTH_MODE, runtime.auth_headers()]
    return hmac.new(salt.encode(), _json(material).encode(), hashlib.sha256).hexdigest()


def _save(directory, state):
    temp = directory / 'state.new'
    with temp.open('w', encoding='utf-8') as stream:
        os.chmod(temp, 0o600)
        stream.write(_json(state))
    temp.replace(directory / 'state.json')


def _load(directory, *, allow_expired=False):
    try:
        state = json.loads((directory / 'state.json').read_text(encoding='utf-8'))
        if state['version'] != 1 or type(state['created']) not in (int, float):
            raise ValueError()
        for name in ('salt', 'binding', 'intent', 'phase', 'content'):
            if not isinstance(state[name], str):
                raise ValueError()
        for name in ('plan', 'candidates', 'decisions'):
            if not isinstance(state[name], dict):
                raise ValueError()
        for name in ('confirmed', 'phaseIds', 'responses'):
            if not isinstance(state[name], list):
                raise ValueError()
        if 'catalogReadComplete' in state and type(state['catalogReadComplete']) is not bool:
            raise ValueError()
        if (type(state['readOffset']) is not int or
                not 0 <= state['readOffset'] <= len(state['content']) or
                state['phase'] not in ('catalog', 'candidates', 'refinement', 'delivered') or
                state['intent'] not in ('broad', 'targeted') or
                (state['nextPage'] is not None and
                 (type(state['nextPage']) is not int or state['nextPage'] < 1))):
            raise ValueError()
        if state['pending'] is not None and (not isinstance(state['pending'], dict) or
                not isinstance(state['pending'].get('receipt'), str) or
                type(state['pending'].get('end')) is not int or
                not state['readOffset'] <= state['pending']['end'] <= len(state['content'])):
            raise ValueError()
        for decision in state['decisions'].values():
            if (not isinstance(decision, dict) or
                    decision.get('decision') not in ('match', 'non_match', 'unresolved') or
                    not isinstance(decision.get('evidence'), str)):
                raise ValueError()
        if 'link' not in state or (state['link'] is not None and not isinstance(state['link'], str)):
            raise ValueError()
        if not allow_expired and time.time() - state['created'] > TTL:
            raise BasilError('Search review expired; close it and start a new search')
        return state
    except (OSError, ValueError, KeyError, TypeError):
        raise BasilError('Missing or damaged search review; start a new search') from None


def _prune():
    # Opportunistic cleanup, never a cross-query cache. Skip active/locked sessions.
    for directory in ROOT.glob('session-*'):
        if directory.is_symlink() or not directory.is_dir():
            continue
        try:
            with (directory / 'lock').open('a') as stream:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                state = _load(directory, allow_expired=True)
                if time.time() - state['created'] > TTL:
                    shutil.rmtree(directory)
        except (OSError, BasilError):
            continue


@contextmanager
def _locked(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise BasilError('Unknown search session')
    fd = os.open(directory / 'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        if directory.stat().st_uid != os.getuid():
            raise BasilError('Search session owner mismatch')
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def _summary(state, sid):
    phase = state['phase']
    unresolved = sum(d['decision'] == 'unresolved' for d in state['decisions'].values())
    complete = state['readOffset'] == len(state['content'])
    empty = phase == 'candidates' and not state['candidates'] and state['nextPage'] is None
    status = ('catalog_ready' if complete else 'catalog_read_required') if phase == 'catalog' else (
        'query_empty' if empty else phase)
    if phase == 'catalog':
        next_action = 'search' if complete else 'read'
    elif phase == 'delivered':
        next_action = 'close'
    elif empty:
        next_action = 'reassess_mapping'
    elif not complete:
        next_action = 'read'
    elif phase == 'refinement':
        next_action = 'next' if state['nextPage'] is not None else 'deliver'
    elif unresolved or set(state['decisions']) != set(state['candidates']):
        next_action = 'review'
    elif state['intent'] == 'broad':
        next_action = 'reassess_mapping' if any(
            d['decision'] != 'match' for d in state['decisions'].values()) else 'deliver'
    else:
        next_action = 'next' if state['nextPage'] is not None else 'refine'
    data = {
        'sessionId': sid, 'intent': state['intent'], 'phase': phase,
        'status': status, 'nextAction': next_action,
        'catalogReadComplete': state['catalogReadComplete'],
        'candidateCount': len(state['candidates']),
        'paginationComplete': state['nextPage'] is None,
        'contentReadComplete': complete,
        'reviewedCount': len(state['decisions']), 'unresolvedCount': unresolved,
        'deliveryReady': phase == 'delivered',
    }
    return {'success': True, 'data': data}


def _without_links(value):
    if isinstance(value, dict):
        return {k: _without_links(v) for k, v in value.items()
                if k not in {'snapshotLink', 'snapLinkId'}}
    if isinstance(value, list):
        return [_without_links(v) for v in value]
    return value


def _ingest(state, result, expected_page):
    pages = result['data']['pages']
    seen = set(state['phaseIds'])
    for page in pages:
        if page['page'] != expected_page:
            raise BasilError('Non-contiguous search pages; restart review')
        data = page['response']['data']
        rows = data.get('fileList', [])
        folders = data.get('folderList', [])
        if folders and state['intent'] == 'targeted':
            raise BasilError('Targeted folder candidates cannot use FILE_ID refinement; use folder_tree')
        current = {file_id_string(str(row['id'])) for row in rows}
        current.update('folder:' + file_id_string(str(row['id'])) for row in folders)
        if current and not current - seen:
            raise BasilError('Pagination repeated across batches; restart review')
        for row in rows:
            fid = file_id_string(str(row['id']))
            if state['phase'] == 'candidates':
                prior = state['candidates'].get(fid)
                if prior is not None and prior != row:
                    raise BasilError('Candidate changed during pagination; restart review')
                state['candidates'][fid] = row
            elif fid not in state['confirmed']:
                raise BasilError('Refinement returned an unconfirmed ID; no delivery')
        for row in folders:
            key = 'folder:' + file_id_string(str(row['id']))
            prior = state['candidates'].get(key)
            if prior is not None and prior != row:
                raise BasilError('Folder candidate changed during pagination; restart review')
            state['candidates'][key] = row
        seen.update(current)
        link = data.get('snapshotLink')
        if expected_page == 1:
            state['link'] = link if isinstance(link, str) and link.strip() else None
        # Append-only read stream; original full responses are separately retained.
        evidence = {'page': expected_page, 'files': rows, 'folders': folders}
        for name in ('folderNameMap', 'metadataFieldNameMap', 'metadataOptionNameMap'):
            if name in data:
                evidence[name] = data[name]
        state['content'] += _json(_without_links(evidence)) + '\n'
        state['responses'].append(page)
        expected_page += 1
    state['phaseIds'] = sorted(seen)
    state['nextPage'] = result['data']['nextPage']


def _covered(state):
    if state['nextPage'] is not None:
        raise BasilError('Pagination incomplete; call next and read all candidate pages')
    if state['readOffset'] != len(state['content']):
        raise BasilError('Content reading incomplete; read and acknowledge every chunk')


def _query(state, payload, query):
    controls = {k: payload[k] for k in ('inspectPages', '_timeout') if k in payload}
    page = state['nextPage']
    if state['phase'] == 'candidates':
        request = {'operation': 'search', 'plan': {**state['plan'], 'page': page}}
    else:
        request = {'operation': 'refine', 'acceptedPlan': state['plan'],
                   'confirmedFileIds': state['confirmed'], 'page': page}
    # Reuse the existing transport/catalog/validator on EVERY remote call.
    result = query({**request, **controls})
    _ingest(state, result, page)


def _read(state, payload, sid):
    budget = payload.get('maxBytes', 8000)
    if type(budget) is not int or not 1024 <= budget <= 12000:
        raise BasilError('maxBytes must be an integer from 1024 to 12000')
    start = state['readOffset']
    content = state['content']
    receipt = secrets.token_hex(16)
    def envelope(end):
        return {'success': True, 'data': {
            'sessionId': sid, 'phase': state['phase'], 'offset': start,
            'chunk': content[start:end], 'nextOffset': end,
            'eof': end == len(content), 'receipt': receipt,
        }}
    low, high = start, min(len(content), start + budget)
    while low < high:
        mid = (low + high + 1) // 2
        if len(json.dumps(envelope(mid), ensure_ascii=False, indent=2).encode('utf-8')) + 1 <= budget:
            low = mid
        else:
            high = mid - 1
    state['pending'] = {'receipt': receipt, 'end': low}
    return envelope(low)


def _review(state, payload):
    if state['phase'] != 'candidates':
        raise BasilError('Decisions are immutable after refinement starts; start a new search')
    if state['readOffset'] != len(state['content']):
        raise BasilError('Read and acknowledge current candidate content before reviewing')
    decisions = payload.get('decisions')
    if not isinstance(decisions, list) or not decisions:
        raise BasilError('decisions must be a non-empty array')
    seen = set()
    for item in decisions:
        if (not isinstance(item, dict) or
                set(item) - {'id', 'decision', 'evidence', 'kind'} or
                not {'id', 'decision', 'evidence'} <= set(item)):
            raise BasilError('Each decision requires id, decision, evidence and optional kind')
        fid = file_id_string(item['id'])
        if item.get('kind', 'file') not in ('file', 'folder'):
            raise BasilError('Decision kind must be file or folder')
        if item.get('kind') == 'folder':
            fid = 'folder:' + fid
        if fid not in state['candidates'] or fid in seen:
            raise BasilError('Unknown or repeated candidate ID in decisions')
        if item['decision'] not in ('match', 'non_match', 'unresolved'):
            raise BasilError('decision must be match, non_match or unresolved')
        evidence = item['evidence']
        if not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 4000:
            raise BasilError('evidence must contain 1–4000 characters')
        state['decisions'][fid] = {'decision': item['decision'], 'evidence': evidence}
        seen.add(fid)


def _checked_decisions(state):
    if set(state['decisions']) != set(state['candidates']):
        raise BasilError('Every candidate requires a decision and evidence')
    if any(d['decision'] == 'unresolved' for d in state['decisions'].values()):
        raise BasilError('Unresolved evidence prevents delivery; resolve it or report the limitation')


def execute(payload, query):
    op = payload.get('operation')
    if not isinstance(op, str) or op not in FIELDS or set(payload) - COMMON - FIELDS[op]:
        raise BasilError('Unsupported guarded search operation or input field')
    attempt = payload.get('attemptId')
    if not isinstance(attempt, str) or not 1 <= len(attempt) <= 128:
        raise BasilError('attemptId is required; generate a fresh local ID for each Run/Attempt')
    # Local reads must also match the current Runtime context and identity.
    runtime.runtime_origin(runtime.RUNTIME_DOMAIN)
    runtime.auth_headers()
    if op == 'catalog':
        if 'sessionId' in payload:
            raise BasilError('catalog starts a new session; omit sessionId')
        salt = secrets.token_hex(32)
        state = {'version': 1, 'created': time.time(), 'salt': salt,
                 'binding': _binding(attempt, salt), 'intent': 'targeted',
                 'plan': {}, 'phase': 'catalog', 'nextPage': None,
                 'candidates': {}, 'decisions': {}, 'confirmed': [],
                 'phaseIds': [], 'responses': [], 'content': '',
                 'readOffset': 0, 'pending': None, 'link': None}
        view = payload.get('view', 'full')
        if view not in ('full', 'compact'):
            raise BasilError('catalog.view must be full or compact')
        fields = fetch_metadata_catalog(timeout=payload.get('_timeout', runtime.DEFAULT_TIMEOUT))
        if view == 'compact':
            fields = compact_catalog(fields)
        state['content'] = ''.join(_json(field) + '\n' for field in fields)
        state['catalogReadComplete'] = not fields
        ROOT.mkdir(mode=0o700, exist_ok=True)
        if ROOT.is_symlink() or ROOT.stat().st_uid != os.getuid():
            raise BasilError('Unsafe search review directory')
        os.chmod(ROOT, 0o700)
        _prune()
        directory = Path(tempfile.mkdtemp(prefix='session-', dir=ROOT))
        _save(directory, state)
        return _summary(state, directory.name)
    return _continue(payload, query, attempt, op)


def _validate_plan(payload):
    if payload.get('intent') not in ('broad', 'targeted'):
        raise BasilError('search requires intent=broad|targeted')
    plan = payload.get('plan')
    plan_to_body(plan)
    if plan.get('page', 1) != 1:
        raise BasilError('Guarded search must start at page 1')
    if payload['intent'] == 'targeted' and plan.get('fileTypeFilter') == ['FOLDER']:
        raise BasilError('Targeted folders cannot use FILE_ID refinement; use folder_tree')


def _continue(payload, query, attempt, op):
    sid = payload.get('sessionId')
    if not isinstance(sid, str) or not re.fullmatch(r'session-[a-z0-9_]{8}', sid):
        raise BasilError('Invalid sessionId; start with catalog and use its returned session ID')
    directory = ROOT / sid
    with _locked(directory):
        state = _load(directory, allow_expired=op == 'close')
        if not hmac.compare_digest(state['binding'], _binding(attempt, state['salt'])):
            raise BasilError('Search belongs to another Attempt, domain or credential; start again')
        if op == 'close':
            shutil.rmtree(directory)
            return {'success': True, 'data': {'closed': True}}
        if op == 'search':
            if state['phase'] != 'catalog' or not state['catalogReadComplete']:
                raise BasilError('Read and acknowledge the complete catalog before search; do not claim no matches')
            _validate_plan(payload)
            state.update(plan=deepcopy(payload['plan']), intent=payload['intent'],
                         phase='candidates', nextPage=1, content='', readOffset=0, pending=None)
            _query(state, payload, query)
            result = _summary(state, sid)
        elif op == 'read':
            result = _read(state, payload, sid)
        elif op == 'ack':
            pending = state['pending']
            if not pending or payload.get('receipt') != pending['receipt']:
                raise BasilError('Invalid read receipt; reread the unacknowledged chunk')
            state['readOffset'] = pending['end']
            state['pending'] = None
            if state['phase'] == 'catalog':
                state['catalogReadComplete'] = state['readOffset'] == len(state['content'])
            result = _summary(state, sid)
        elif op == 'review':
            _review(state, payload)
            result = _summary(state, sid)
        elif op == 'next':
            if state['phase'] not in ('candidates', 'refinement') or state['nextPage'] is None:
                raise BasilError('No next page in the current phase')
            if state['readOffset'] != len(state['content']):
                raise BasilError('Read and acknowledge this batch before fetching more pages')
            _query(state, payload, query)
            result = _summary(state, sid)
        elif op == 'refine':
            if state['intent'] != 'targeted' or state['phase'] != 'candidates':
                raise BasilError('refine requires a targeted candidate review')
            if not state['candidates'] and state['nextPage'] is None:
                return {'success': True, 'data': {'status': 'no_matches',
                        'reason': 'query_empty', 'nextAction': 'reassess_mapping',
                        'deliveryReady': False}}
            _covered(state)
            _checked_decisions(state)
            state['confirmed'] = [fid for fid, d in state['decisions'].items() if d['decision'] == 'match']
            if not state['confirmed']:
                return {'success': True, 'data': {'status': 'no_matches', 'deliveryReady': False}}
            state.update(phase='refinement', nextPage=1, phaseIds=[], content='',
                         readOffset=0, pending=None, link=None)
            _query(state, payload, query)
            result = _summary(state, sid)
        elif op == 'deliver':
            if state['phase'] == 'delivered':
                return {'success': True, 'data': {'deliveryReady': True, 'snapshotLink': state['link']}}
            if state['intent'] == 'targeted' and state['phase'] != 'refinement':
                raise BasilError('Targeted search requires successful refinement before delivery')
            if state['intent'] == 'targeted':
                _covered(state)
                if set(state['phaseIds']) != set(state['confirmed']):
                    raise BasilError('Refinement excluded confirmed candidates; report changed results, no delivery')
            else:
                # Broad exploration needs review of the inspected batch, not all server pages.
                if state['readOffset'] != len(state['content']):
                    raise BasilError('Read and acknowledge the inspected batch before delivery')
                _checked_decisions(state)
                if any(d['decision'] != 'match' for d in state['decisions'].values()):
                    raise BasilError('Broad query contains rejected candidates; repair the query')
            if not state['phaseIds'] or not state['link']:
                return {'success': True, 'data': {'status': 'empty_or_missing_link', 'deliveryReady': False}}
            state['phase'] = 'delivered'
            result = {'success': True, 'data': {'deliveryReady': True, 'snapshotLink': state['link']}}
        else:
            raise BasilError('Unsupported operation')
        _save(directory, state)
        return result
