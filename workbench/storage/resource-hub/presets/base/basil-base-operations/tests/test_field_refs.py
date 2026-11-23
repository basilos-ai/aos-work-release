"""Regression: NAME query results must not store names in view fieldId."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from base.query_snapshot import execute
from runtime import BasilError
import runtime

ID = '2066348765152940032'
TABLE = '2066348680000180224'
FIELD = {'id': ID, 'name': 'product_material_code',
         'dbFieldName': 'field' + ID, 'tableId': TABLE}
LINK = 'https://current.test/result?viewId=123'


def response(data, total=None):
    return json.dumps({'success': True, 'code': 0, 'data': data,
                       'addition': {'total': total} if total is not None else None}), 'application/json'


def payload(ref):
    return {'operation': 'record_query_snapshot', 'query': {
        'tableId': TABLE, 'fieldKeyType': 'NAME', 'cellFormat': 'TEXT',
        'filter': {'conjunction': 'and', 'filterSet': [
            {'fieldId': ref, 'operator': '=', 'value': 'AM2417.000.A3001'}]}}}


class FieldReferenceTests(unittest.TestCase):
    def setUp(self):
        config = patch.object(runtime, 'RUNTIME_DOMAIN', 'https://current.test')
        config.start()
        self.addCleanup(config.stop)

    def test_normal_and_failed_incident_inputs_produce_identical_filters(self):
        filters = []
        for ref in [ID, FIELD['name'], FIELD['dbFieldName']]:
            source = payload(ref)
            before = copy.deepcopy(source)
            with patch('runtime.openapi.request', side_effect=[
                response([FIELD], 1), response({'recordList': [{'id': 'r'}]}, 3),
                response({'id': '123', 'snapshotLink': LINK}),
            ]) as network:
                result = execute(source)
            self.assertEqual(source, before)
            self.assertEqual([c.args[1] for c in network.call_args_list],
                             ['/openapi/field/page', '/openapi/record/queryRecord', '/openapi/view'])
            query = network.call_args_list[1].kwargs['query']
            self.assertEqual(query['fieldKeyType'], 'NAME')
            parsed = json.loads(query['filter'])
            self.assertEqual(parsed['filterSet'][0]['fieldId'], ID)
            self.assertEqual(network.call_args_list[2].kwargs['body']['filter'], parsed)
            self.assertEqual(result['workflow']['effectiveQuery']['filter'], parsed)
            self.assertEqual(result['data']['snapshotLink'], LINK)
            filters.append(parsed)
        self.assertTrue(all(f == filters[0] for f in filters))

    def test_nested_filter_sort_group_resolve_with_one_metadata_load(self):
        source = payload(FIELD['name'])
        source['query']['filter']['filterSet'] = [copy.deepcopy(source['query']['filter'])]
        source['query']['orderBy'] = [{'fieldId': FIELD['dbFieldName'], 'order': 'desc'}]
        source['query']['groupBy'] = [{'fieldId': ID, 'order': 'asc'}]
        with patch('runtime.openapi.request', side_effect=[
            response([FIELD], 1), response({'recordList': [{'id': 'r'}]}),
            response({'snapshotLink': LINK}),
        ]) as network:
            execute(source)
        self.assertEqual(network.call_count, 3)
        body = network.call_args.kwargs['body']
        self.assertEqual(body['filter']['filterSet'][0]['filterSet'][0]['fieldId'], ID)
        self.assertEqual(body['sort']['sortObjs'][0]['fieldId'], ID)
        self.assertEqual(body['groupMeta'][0]['fieldId'], ID)

    def test_unknown_ambiguous_or_foreign_fields_stop_before_record_query(self):
        cases = [(payload('missing'), [FIELD]),
                 (payload(FIELD['name']), [FIELD, {**FIELD, 'id': '999'}]),
                 (payload(ID), [{**FIELD, 'tableId': '999'}])]
        for source, fields in cases:
            with self.subTest(source=source), patch('runtime.openapi.request',
                    return_value=response(fields, len(fields))) as network:
                with self.assertRaises(BasilError):
                    execute(source)
            network.assert_called_once()
            self.assertEqual(network.call_args.args[1], '/openapi/field/page')

    def test_metadata_pagination_resolves_field_on_later_page(self):
        with patch('runtime.openapi.request', side_effect=[
            response([{'id': '123', 'name': 'other', 'tableId': TABLE}], 2),
            response([FIELD], 2), response({'recordList': []}),
        ]) as network:
            execute(payload(FIELD['name']))
        self.assertEqual([c.kwargs['query']['page'] for c in network.call_args_list[:2]], [0, 1])
        self.assertEqual(json.loads(network.call_args.kwargs['query']['filter'])['filterSet'][0]['fieldId'], ID)

    def test_metadata_failure_or_repeated_page_stops_without_writes(self):
        for responses in [[BasilError('HTTP 403')], [response([FIELD], 2), response([FIELD], 2)]]:
            with patch('runtime.openapi.request', side_effect=responses) as network:
                with self.assertRaises(BasilError):
                    execute(payload(ID))
            self.assertTrue(all(c.args[1] == '/openapi/field/page' for c in network.call_args_list))

    def test_query_without_field_refs_does_not_fetch_metadata(self):
        with patch('runtime.openapi.request', return_value=response({'recordList': []})) as network:
            execute({'operation': 'record_query_snapshot', 'query': {'tableId': TABLE}})
        network.assert_called_once()
        self.assertEqual(network.call_args.args[1], '/openapi/record/queryRecord')


if __name__ == '__main__':
    unittest.main()
