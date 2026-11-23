#!/usr/bin/env python3
"""Asset Rule Group contracts; shared runtime owns credentials and mutation guards."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import BasilError, print_json, read_json_stdin, run_script
from runtime.openapi import Operation, execute_operation

PREFIX = '/assets/rule/group'
OPERATIONS = {
    'pageRuleGroup': Operation('GET', PREFIX + '/page', required_query=('page', 'size')),
    'getRuleGroupDetail': Operation('GET', PREFIX + '/{id}', required_path=('id',)),
    'saveRuleGroup': Operation('POST', PREFIX + '/save', 'object',
                               required_body=('name', 'conditionGroupList', 'metadataFieldIdList'), mutating=True),
    'updateRuleGroup': Operation('PUT', PREFIX + '/update', 'object',
                                 required_body=('id', 'conditionGroupList', 'metadataFieldIdList'), mutating=True),
    'deleteBatchRuleGroup': Operation('DELETE', PREFIX + '/deleteBatch',
                                      required_query=('idList',), mutating=True, destructive=True),
}


def object_fields(value: Any, allowed: set[str], label: str) -> dict:
    if not isinstance(value, dict):
        raise BasilError(f'{label} must be an object')
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise BasilError(f'unsupported {label} field(s): {", ".join(unknown)}')
    return value


def decimal_id(value: Any, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r'[0-9]+', value) is None:
        raise BasilError(f'{label} must be a decimal ID string from a real result')


def array(value: Any, label: str, *, nonempty: bool = False) -> list:
    if not isinstance(value, list) or (nonempty and not value):
        raise BasilError(f'{label} must be {"a non-empty" if nonempty else "an"} array')
    return value


def ids(value: Any, label: str, *, nonempty: bool = False) -> None:
    for item in array(value, label, nonempty=nonempty):
        decimal_id(item, label)


def groups(value: Any, *, updating: bool, depth: int = 0) -> None:
    if depth > 15:
        raise BasilError('condition group depth exceeds 15 (top level is 0)')
    for group in array(value, 'conditionGroupList'):
        extra = {'id', 'parentId'} if updating else set()
        object_fields(group, {'logicType', 'conditionList', 'childGroupList'} | extra, 'condition group')
        for key in extra & group.keys():
            decimal_id(group[key], key)
        if group.get('logicType') not in ('AND', 'OR'):
            raise BasilError('logicType must be AND or OR')
        conditions = array(group.get('conditionList', []), 'conditionList')
        children = array(group.get('childGroupList', []), 'childGroupList')
        if not conditions and not children:
            raise BasilError('condition group must contain a condition or child group')
        for condition in conditions:
            object_fields(condition, {'fieldType', 'operator', 'value'} | ({'id'} if updating else set()), 'condition')
            if 'id' in condition:
                decimal_id(condition['id'], 'condition.id')
            if condition.get('fieldType') not in ('CHANNEL', 'FILE_TYPE', 'FOLDER'):
                raise BasilError('fieldType must be CHANNEL, FILE_TYPE or FOLDER; METADATA_FIELD has no matcher')
            if condition.get('operator') not in ('IN', 'NOT_IN'):
                raise BasilError('operator must be IN or NOT_IN')
            values = array(condition.get('value'), 'condition.value', nonempty=True)
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise BasilError('condition.value must contain non-empty strings from authoritative options')
            if condition['fieldType'] == 'FOLDER':
                ids(values, 'FOLDER value')
        if children:
            groups(children, updating=updating, depth=depth + 1)


def execute(payload: dict) -> dict:
    name = payload.get('operation')
    if not isinstance(name, str) or name not in OPERATIONS:
        raise BasilError('operation must name a supported Rule Group operation')
    path = object_fields(payload.get('path', {}), {'id'} if name == 'getRuleGroupDetail' else set(), 'path')
    allowed_query = {'page', 'size', 'name', 'sortField', 'sortDirection'} if name == 'pageRuleGroup' else ({'idList'} if name == 'deleteBatchRuleGroup' else set())
    query = object_fields(payload.get('query', {}), allowed_query, 'query')
    if name == 'getRuleGroupDetail':
        decimal_id(path.get('id'), 'path.id')
    if name == 'pageRuleGroup':
        for key in ('page', 'size'):
            value = query.get(key)
            if type(value) is not int or value < 1 or (key == 'size' and value > 1000):
                raise BasilError(f'query.{key} must be a positive integer; size is at most 1000')
        if 'name' in query and not isinstance(query['name'], str):
            raise BasilError('query.name must be a string')
        for key, choices in (('sortField', ('name', 'createdAt', 'updatedAt')), ('sortDirection', ('ASC', 'DESC'))):
            if key in query and query[key] not in choices:
                raise BasilError(f'unsupported query.{key}')
    if name == 'deleteBatchRuleGroup':
        ids(query.get('idList'), 'query.idList', nonempty=True)
    if name in ('saveRuleGroup', 'updateRuleGroup'):
        updating = name == 'updateRuleGroup'
        body = object_fields(payload.get('body'), {'name', 'description', 'prompt', 'conditionGroupList', 'metadataFieldIdList'} | ({'id'} if updating else set()), 'body')
        if updating:
            decimal_id(body.get('id'), 'body.id')
        for key in ('name', 'description', 'prompt'):
            if key in body and not (updating and body[key] is None):
                if not isinstance(body[key], str) or (key == 'name' and not body[key].strip()):
                    raise BasilError(f'body.{key} must be a string; name cannot be blank')
        if not updating and not body.get('name'):
            raise BasilError('saveRuleGroup requires name')
        # Requiring both arrays on update prevents accidental server-side clearing.
        array(body.get('conditionGroupList'), 'body.conditionGroupList', nonempty=not updating)
        groups(body['conditionGroupList'], updating=updating)
        ids(body.get('metadataFieldIdList'), 'body.metadataFieldIdList', nonempty=not updating)
    result, _ = execute_operation(payload, OPERATIONS)
    if name in ('saveRuleGroup', 'updateRuleGroup', 'deleteBatchRuleGroup') and result.get('data') is not True:
        raise BasilError('Rule Group mutation response must contain data=true; outcome unverified, do not replay')
    return result


def main() -> None:
    print_json(execute(read_json_stdin()))


if __name__ == '__main__':
    raise SystemExit(run_script(main))
