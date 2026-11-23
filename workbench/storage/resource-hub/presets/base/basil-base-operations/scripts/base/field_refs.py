"""Resolve view-compatible field references against the current table metadata."""
from __future__ import annotations

from runtime import BasilError
from runtime.openapi import execute_operation
from base.operations import OPERATIONS


def _load_fields(table_id, timeout=None):
    fields = []
    seen = set()
    for page in range(1000):
        payload = {'operation': 'field_list',
                   'query': {'tableId': table_id, 'page': page, 'size': 1000}}
        if timeout is not None:
            payload['_timeout'] = timeout
        response, _ = execute_operation(payload, OPERATIONS)
        rows = response.get('data')
        if not isinstance(rows, list):
            raise BasilError('field_list returned invalid metadata; query not executed')
        for row in rows:
            if not isinstance(row, dict) or row.get('id') is None:
                raise BasilError('field_list returned a field without an ID')
            if row.get('tableId') is not None and str(row['tableId']) != str(table_id):
                raise BasilError('field_list returned a field from a different table')
            field_id = str(row['id'])
            if field_id in seen:
                raise BasilError('field_list pagination repeated a field; query not executed')
            seen.add(field_id)
            fields.append(row)
        total = (response.get('addition') or {}).get('total')
        if isinstance(total, int) and not isinstance(total, bool):
            if len(fields) >= total:
                return fields
            if not rows:
                raise BasilError('field_list ended before its reported total')
        elif len(rows) < 1000:
            return fields
    raise BasilError('field_list pagination limit reached; query not executed')


def normalize_field_refs(query, timeout=None):
    """Mutate only already-copied filter/order/group nodes, before record query."""
    refs = []
    def visit(node):
        if node.get('fieldId') is not None:
            refs.append(node)
        for child in node.get('filterSet') or []:
            visit(child)
    if query.get('filter') is not None:
        visit(query['filter'])
    for key in ('orderBy', 'groupBy'):
        refs.extend(item for item in query.get(key, []) if item.get('fieldId') is not None)
    if not refs:
        return
    fields = _load_fields(query['tableId'], timeout)
    ids = {str(field['id']) for field in fields}
    aliases = {}
    for field in fields:
        for key in ('name', 'dbFieldName'):
            alias = field.get(key)
            if isinstance(alias, str) and alias:
                aliases.setdefault(alias, set()).add(str(field['id']))
    resolved = {}
    for node in refs:
        ref = node['fieldId']
        if ref not in resolved:
            candidates = {ref} if ref in ids else aliases.get(ref, set())
            if len(candidates) != 1:
                reason = 'ambiguous' if candidates else 'unknown'
                raise BasilError(f'{reason} field reference {ref!r}; use an exact field ID from this table')
            resolved[ref] = next(iter(candidates))
    for node in refs:
        node['fieldId'] = resolved[node['fieldId']]
