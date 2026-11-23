"""Incident regressions using the real dispatcher and offline transport."""
import copy
import io
import json
import os
import subprocess
from pathlib import Path
import sys
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import runtime
from base.cli import OPERATIONS
from base.query_snapshot import execute, _result_link
from runtime import BasilError
from runtime.openapi import execute_operation

FILTER = {'conjunction': 'and', 'filterSet': [
    {'fieldId': 'price-id', 'operator': '>', 'value': 50}]}
LINK = 'https://current.test/studio/engine/multi-dim-table-embed/123/456?viewId=789#grid'
PREFIXED_LINK = LINK.replace('/studio/', '/basilos/studio/')


def response(data, addition=None):
    return json.dumps({'success': True, 'code': 0, 'data': data, 'addition': addition}), 'application/json'


def payload(**query):
    return {'operation': 'record_query_snapshot', 'query': {'tableId': '456', **query}}


class QueryResultTests(unittest.TestCase):
    def setUp(self):
        metadata = patch('base.field_refs._load_fields', return_value=[{'id': 'price-id', 'name': 'price-id'}, {'id': 'price', 'name': 'price'}, {'id': 'material', 'name': 'material'}, {'id': 'field', 'name': 'field'}, {'id': 'text', 'name': 'text'}, {'id': 'f', 'name': 'f'}])
        metadata.start()
        self.addCleanup(metadata.stop)
        config = patch.object(runtime, 'RUNTIME_DOMAIN', 'https://current.test')
        config.start()
        self.addCleanup(config.stop)

    def test_incident_success_retains_rows_total_filter_and_returned_link(self):
        source = payload(filter=json.dumps(FILTER), take=1)
        before = copy.deepcopy(source)
        rows = [{'id': 'row-1', 'fields': {'price': 51}}]
        with patch('runtime.openapi.request', side_effect=[
            response({'recordList': rows}, {'total': 2}),
            response({'snapshotLink': LINK}),
        ]) as transport:
            result = execute(source)
        self.assertEqual(source, before)
        self.assertEqual(result['data']['recordList'], rows)
        self.assertEqual(result['addition']['total'], 2)
        self.assertEqual(result['data']['snapshotLink'], LINK)
        self.assertEqual(result['workflow']['originalSnapshotLink'], LINK)
        self.assertFalse(result['workflow']['browserVerified'])
        self.assertEqual(result['workflow']['viewScope'], 'all_matching_records')
        self.assertEqual([c.args[0] for c in transport.call_args_list], ['GET', 'POST'])
        self.assertEqual(json.loads(transport.call_args_list[0].kwargs['query']['filter']), FILTER)
        self.assertEqual(transport.call_args_list[1].kwargs['body']['filter'], FILTER)
        self.assertFalse(transport.call_args_list[1].kwargs['body']['display'])
        self.assertNotIn('options', transport.call_args_list[1].kwargs['body'])

    def test_real_transport_encodes_one_json_filter_and_object_view_body(self):
        # Patch only the socket boundary, exercising request(), urlencode(), and
        # POST serialization that the dispatcher-level mocks previously skipped.
        for supplied in [copy.deepcopy(FILTER), json.dumps(FILTER)]:
            with self.subTest(input_type=type(supplied).__name__), \
                 patch.object(runtime, 'auth_headers', return_value={}), \
                 patch.object(runtime, '_perform_request', side_effect=[
                     response({'recordList': [{'id': 'r'}]}, {'total': 1}),
                     response({'snapshotLink': LINK}),
                 ]) as network:
                result = execute(payload(filter=supplied))
            self.assertEqual(network.call_count, 2)
            get_call, post_call = network.call_args_list
            self.assertEqual(get_call.args[0], 'GET')
            params = urllib.parse.parse_qs(urllib.parse.urlsplit(get_call.args[1]).query)
            self.assertEqual(len(params['filter']), 1)
            self.assertEqual(json.loads(params['filter'][0]), FILTER)
            self.assertIsNone(get_call.kwargs['payload'])
            self.assertEqual(post_call.args[0], 'POST')
            body = json.loads(post_call.kwargs['payload'])
            self.assertEqual(body['filter'], FILTER)
            self.assertNotIn('options', body)
            self.assertEqual(body['tableId'], 456)
            self.assertEqual(result['workflow']['effectiveQuery']['filter'], FILTER)
            self.assertEqual(result['data']['snapshotLink'], LINK)

    def test_sort_group_and_large_integer_ids_at_transport_boundary(self):
        big = '2096889744620392448'
        source = payload(tableId=big, viewId='123', ignoreViewQuery=True,
                         orderBy=[{'fieldId': 'price', 'order': 'DESC'}],
                         groupBy=[{'fieldId': 'material', 'order': 'ASC'}])
        with patch.object(runtime, 'auth_headers', return_value={}), \
             patch.object(runtime, '_perform_request', side_effect=[
                 response({'recordList': [{'id': 'r'}]}), response({'id': '321'}),
             ]) as network:
            result = execute(source)
        get, post = network.call_args_list
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(get.args[1]).query)
        body = json.loads(post.kwargs['payload'])
        self.assertEqual(params['tableId'], [big])
        self.assertEqual(params['ignoreViewQuery'], ['true'])
        self.assertEqual(body['tableId'], int(big))
        self.assertEqual(body['sort']['sortObjs'], json.loads(params['orderBy'][0]))
        self.assertEqual(body['groupMeta'], json.loads(params['groupBy'][0]))
        self.assertEqual(body['sort']['sortObjs'][0]['order'], 'desc')
        self.assertEqual(body['groupMeta'][0]['order'], 'asc')
        self.assertEqual(result['workflow']['viewId'], '321')
        self.assertEqual(result['workflow']['failedStage'], 'result_link')
        self.assertEqual(source['query']['tableId'], big)

    def test_aggregation_uses_shared_json_encoding_and_repeated_lists(self):
        with patch.object(runtime, 'auth_headers', return_value={}), \
             patch.object(runtime, '_perform_request', return_value=response({})) as network:
            execute_operation({'operation': 'record_aggregate', 'query': {
                'tableId': '456', 'filter': FILTER, 'aggregations': {'price': 'sum'},
                'search': ['one', 'two'], 'selectedRecordIds': ['r1', 'r2'],
            }}, OPERATIONS)
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(network.call_args.args[1]).query)
        self.assertEqual(json.loads(params['filter'][0]), FILTER)
        self.assertEqual(json.loads(params['aggregations'][0]), {'price': 'sum'})
        self.assertEqual(params['search'], ['one', 'two'])
        self.assertEqual(params['selectedRecordIds'], ['r1', 'r2'])

    def test_integer_body_contract_preserves_record_ids_and_user_fields(self):
        fields = {'tableId': 'user-entered-text', 'price': 50}
        original = {'tableId': '2096889744620392448', 'recordId': 'record123', 'fields': fields}
        with patch('runtime.openapi.request', return_value=response({})) as network:
            execute_operation({'operation': 'record_update', 'body': original, '_confirm': True}, OPERATIONS)
        body = network.call_args.kwargs['body']
        self.assertEqual(body['tableId'], 2096889744620392448)
        self.assertEqual(body['recordId'], 'record123')
        self.assertEqual(body['fields'], fields)
        self.assertEqual(original['tableId'], '2096889744620392448')
        for bad in [True, 123.0, '1e6', 'tbl_example']:
            with patch('runtime.openapi.request') as network:
                with self.assertRaises(BasilError):
                    execute_operation({'operation': 'view_create', '_confirm': True,
                                       'body': {'tableId': bad, 'type': 'GRID'}}, OPERATIONS)
                network.assert_not_called()

    def test_cli_positional_json_reports_stdin_contract(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/base/databases.py'
        result = subprocess.run([sys.executable, '-B', str(script), '{"operation":"base_list"}'],
                                input='', text=True, capture_output=True, env={})
        self.assertEqual(result.returncode, 1)
        self.assertIn('standard input', json.loads(result.stdout)['error'])
        self.assertEqual(result.stderr, '')

    def test_empty_page_keeps_total_without_creating_view(self):
        with patch('runtime.openapi.request', return_value=response({'recordList': []}, {'total': 2})) as transport:
            result = execute(payload(skip=20))
        transport.assert_called_once()
        self.assertEqual(result['addition']['total'], 2)
        self.assertEqual(result['workflow']['viewStatus'], 'not_created_empty_page')
        self.assertNotIn('snapshotLink', result['data'])

    def test_invalid_filters_fail_before_any_network(self):
        bad = [[], 'not json', {'conjunction': 'xor'}, {'filterSet': 'bad'}, {'isSymbol': 'true'}]
        for key, values in {'operator': ['', 3],
                            'value': [float('nan'), float('inf')],
                            'fieldId': ['', 123]}.items():
            for value in values:
                f = copy.deepcopy(FILTER)
                f['filterSet'][0][key] = value
                bad.append(f)
        for f in bad:
            with self.subTest(f=f), patch('runtime.openapi.request') as network:
                with self.assertRaises(BasilError):
                    execute(payload(filter=f))
                network.assert_not_called()

    def test_uppercase_conjunction_normalized_before_query(self):
        f = copy.deepcopy(FILTER)
        f['conjunction'] = 'AND'
        with patch('runtime.openapi.request', return_value=response({'recordList': []})) as network:
            execute(payload(filter=f))
        self.assertEqual(json.loads(network.call_args.kwargs['query']['filter']), FILTER)
        self.assertEqual(f['conjunction'], 'AND')

    def test_general_filter_schema_preserves_values_and_symbols(self):
        for condition in [
            {'fieldId': 'price', 'operator': '<=', 'value': 100, 'isSymbol': True},
            {'fieldId': 'text', 'operator': 'server_defined_operator', 'value': ['a', 'b']},
            {'fieldId': 'field', 'operator': '=', 'value': {'key': 'value'}},
            {'conjunction': 'OR', 'filterSet': [copy.deepcopy(FILTER)]},
            {},
        ]:
            with patch('runtime.openapi.request', return_value=response({'recordList': []})) as network:
                execute(payload(filter=condition))
            actual = json.loads(network.call_args.kwargs['query']['filter'])
            expected = {**condition}
            if expected.get('conjunction') == 'OR':
                expected['conjunction'] = 'or'
            self.assertEqual(actual, expected)

    def test_unmapped_scope_queries_without_creating_broader_view(self):
        for query in [{'viewId': '123'}, {'search': 'steel'}, {'projection': ['price']},
                      {'selectedRecordIds': ['r']}, {'collapsedGroupIds': ['g']}]:
            with self.subTest(query=query), patch('runtime.openapi.request',
                 return_value=response({'recordList': [{'id': 'r'}]}, {'total': 1})) as network:
                result = execute(payload(**query))
            network.assert_called_once()
            self.assertEqual(result['workflow']['viewStatus'], 'not_created_unsupported_scope')
            self.assertNotIn('snapshotLink', result['data'])
            self.assertEqual(result['data']['recordList'], [{'id': 'r'}])

    def test_invalid_scope_type_and_name_fail_before_network(self):
        for query in [{'unknown': True}, {'ignoreViewQuery': 'false'}, {'projection': {}},
                      {'search': []}, {'orderBy': {}}, {'groupBy': [{'fieldId': 'f', 'order': 'up'}]}]:
            with patch('runtime.openapi.request') as network:
                with self.assertRaises(BasilError):
                    execute(payload(**query))
                network.assert_not_called()
        with patch('runtime.openapi.request') as network:
            with self.assertRaises(BasilError):
                execute({**payload(), 'viewName': ''})
            network.assert_not_called()

    def test_view_failure_retains_records_and_does_not_retry(self):
        with patch('runtime.openapi.request', side_effect=[
            response({'recordList': [{'id': 'row-1'}]}, {'total': 1}),
            BasilError('HTTP 403'),
        ]) as network:
            result = execute(payload())
        self.assertEqual(network.call_count, 2)
        self.assertEqual(result['workflow']['failedStage'], 'view_create')
        self.assertEqual(result['workflow']['viewStatus'], 'failed_or_unknown')
        self.assertFalse(result['workflow']['retryAllowed'])
        self.assertEqual(result['data']['recordList'], [{'id': 'row-1'}])
        self.assertNotIn('snapshotLink', result['data'])

    def test_missing_or_invalid_link_is_not_a_query_failure(self):
        for link in [None, '', 'javascript:alert(1)', 'https://u:p@example.test/view',
                     'https://example.test:invalid/view', 'https://example.test:65536/view',
                     'https://[broken/view', 'https://example.test/a\\b',
                     'https://example.test/a b', 'https://example.test/a\nb',
                     '/relative/view', 'file:///tmp/view']:
            with self.subTest(link=link), patch('runtime.openapi.request', side_effect=[
                response({'recordList': [{'id': 'r'}]}), response({'snapshotLink': link}),
            ]) as network:
                result = execute(payload())
                self.assertEqual(result['workflow']['failedStage'], 'result_link')
                self.assertEqual(result['workflow']['viewStatus'], 'created')
                self.assertEqual(result['data']['recordList'], [{'id': 'r'}])
                self.assertNotIn('snapshotLink', result['data'])
                self.assertEqual(network.call_count, 2)

    def test_result_links_preserve_provider_origin_route_query_and_fragment(self):
        for link in [LINK, PREFIXED_LINK,
                     LINK.replace('current.test', 'studio.aos.work'),
                     LINK.replace('current.test', 'studio.test:8443'),
                     LINK.replace('https:', 'http:'),
                     LINK.replace('123/456', 'abc/456'),
                     LINK.replace('/studio/', '/other/')]:
            with self.subTest(link=link):
                self.assertEqual(_result_link(link), (link, 'returned_unverified'))

    def test_api_origin_and_result_frontend_are_independent(self):
        link = LINK.replace('current.test', 'studio.aos.work')
        for origin in ['https://workbench.aos.work', 'https://second.test:8443', 'https://third.test:8080']:
            runtime.RUNTIME_DOMAIN = origin
            with self.subTest(origin=origin), \
                 patch.object(runtime, 'auth_headers', return_value={}), \
                 patch.object(runtime, '_perform_request', side_effect=[
                     response({'recordList': [{'id': 'r'}]}), response({'snapshotLink': link}),
                 ]) as network:
                result = execute(payload(filter=FILTER))
            self.assertEqual(network.call_count, 2)
            for call in network.call_args_list:
                self.assertTrue(call.args[1].startswith(origin + '/typekey/api/v1/openapi/'))
            self.assertEqual(result['data']['snapshotLink'], link)
            self.assertEqual(result['workflow']['originalSnapshotLink'], link)
            self.assertEqual(result['workflow']['linkStatus'], 'returned_unverified')

    def test_query_errors_or_invalid_response_never_create_view(self):
        for first in [BasilError('HTTP 400'), response({}), response({'recordList': None}),
                      response({'recordList': 'bad'}), response({'recordList': [None]})]:
            with self.subTest(first=first), patch('runtime.openapi.request', side_effect=[first]) as network:
                with self.assertRaises(BasilError):
                    execute(payload())
                network.assert_called_once()

    def test_mutation_guards_remain(self):
        with patch('runtime.openapi.request') as network:
            with self.assertRaises(BasilError):
                execute_operation({'operation': 'view_create', 'body': {'tableId': 't', 'type': 'GRID'}}, OPERATIONS)
            for key in ['body', 'display', 'enableShare', 'publishToAssetsIs']:
                with self.assertRaises(BasilError):
                    execute({**payload(), key: True})
            network.assert_not_called()

    def test_legacy_confirmation_and_input_validation(self):
        for confirmed in [True, False]:
            with patch('runtime.openapi.request', return_value=response({'recordList': []})):
                execute({**payload(), '_confirm': confirmed})
        for p in [{**payload(), '_confirm': 'true'}, payload(take=0), payload(skip=-1),
                  payload(cellFormat=[]), payload(fieldKeyType={})]:
            with patch('runtime.openapi.request') as network:
                with self.assertRaises(BasilError):
                    execute(p)
                network.assert_not_called()

    def test_http_400_diagnostics_are_bounded_and_redacted(self):
        secret = 'fixture-secret-token'
        for data in [
            {'code': 'BAD_FILTER', 'field': 'filter.filterSet[0].value',
             'requestId': 'trace-123', 'traceId': secret, 'message': 'tableId validation failed ' + secret,
             'stack': 'private stack', 'input': 'private input'},
            {'message': 'x' * 5000},
        ]:
            error = urllib.error.HTTPError('https://private.test', 400, 'bad', {}, io.BytesIO(json.dumps(data).encode()))
            with patch.dict(os.environ, {'APP_OAUTH_BASILOS_ACCESS_TOKEN': secret}), \
                 patch.object(runtime, '_perform_request', side_effect=error):
                with self.assertRaises(BasilError) as caught:
                    runtime.request('GET', '/openapi/record/queryRecord')
            message = str(caught.exception)
            self.assertNotIn(secret, message)
            self.assertNotIn('private', message)
            self.assertLess(len(message), 600)
            if data.get('code'):
                self.assertIn('message=tableId validation failed [REDACTED]', message)
                self.assertIn('code=BAD_FILTER', message)
                self.assertIn('requestId=trace-123', message)
                self.assertIn('filter.filterSet[0].value', message)


if __name__ == '__main__':
    unittest.main()
