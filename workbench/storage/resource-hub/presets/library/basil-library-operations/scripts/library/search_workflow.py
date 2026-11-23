#!/usr/bin/env python3
"""Mechanical search execution; relevance and evidence remain Agent decisions."""
from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import BasilError, print_json, read_json_stdin, run_script
from library.build_structured_search import build_structured_search
from library.metadata_catalog import metadata_id
from library.search_validation import file_id_string, plan_to_body
from library.structured_search import execute as execute_search


def refinement_plan(accepted_plan, confirmed_ids):
    """Preserve every accepted constraint; only narrow the existing FILE_ID set."""
    plan_to_body(accepted_plan)  # Validate before transforming; no network.
    if not isinstance(confirmed_ids, list) or not confirmed_ids:
        raise BasilError('Refinement requires a non-empty array of confirmed file ID strings')
    ids = list(dict.fromkeys(file_id_string(value) for value in confirmed_ids))
    result = deepcopy(accepted_plan)
    filters = result.get('filterConditions') or []
    retained = []
    for condition in filters:
        if condition['fieldType'] == 'FILE_ID':
            allowed = {file_id_string(value) for value in condition['value']}
            ids = [value for value in ids if value in allowed]
        else:
            retained.append(condition)
    if not ids:
        raise BasilError('No confirmed IDs remain within the accepted FILE_ID scope; do not return the ordinary link')
    result.update(keyword='', page=1, filterConditions=[*retained, {
        'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ids,
    }])
    return build_structured_search(**result)


def execute_query(payload):
    allowed = {'operation', 'plan', 'acceptedPlan', 'confirmedFileIds',
               'inspectPages', 'page', '_timeout'}
    if set(payload) - allowed:
        raise BasilError('Unsupported search workflow input field')
    operation = payload.get('operation')
    if operation == 'search':
        if 'acceptedPlan' in payload or 'confirmedFileIds' in payload or 'page' in payload:
            raise BasilError('search accepts plan, not refinement inputs')
        if not isinstance(payload.get('plan'), dict):
            raise BasilError('search requires a plan object from Agent semantic mapping')
        plan = build_structured_search(**payload['plan'])
    elif operation == 'refine':
        if 'plan' in payload:
            raise BasilError('refine accepts acceptedPlan and confirmedFileIds only')
        plan = refinement_plan(payload.get('acceptedPlan'), payload.get('confirmedFileIds'))
        if 'page' in payload:
            if type(payload['page']) is not int or payload['page'] < 1:
                raise BasilError('Refinement page must be a positive integer')
            plan['page'] = payload['page']  # Continuation of this same refinement.
    else:
        raise BasilError('operation must be search or refine')
    request = {'operation': 'structured_search', 'plan': plan,
               'inspectResults': True, 'inspectPages': payload.get('inspectPages', 1)}
    if '_timeout' in payload:
        request['_timeout'] = payload['_timeout']
    # The existing boundary still performs live catalog validation on every call.
    # Its bounded-page response is unchanged; do not claim semantic completeness.
    result = execute_search(request)
    if operation == 'refine':
        allowed_ids = set(plan['filterConditions'][-1]['value'])
        for page in result['data']['pages']:
            for row in page['response']['data'].get('fileList', []):
                if str(metadata_id(row['id'])) not in allowed_ids:
                    raise BasilError('Refinement returned a file outside the confirmed ID set; do not deliver its link')
    return result


def execute(payload):
    from library.search_review import execute as guarded_execute
    return guarded_execute(payload, execute_query)


def main():
    print_json(execute(read_json_stdin()))


if __name__ == "__main__":
    raise SystemExit(run_script(main))
