"""Compact Metadata projection and complete-catalog name lookup; no live access."""
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from library import cli, metadata_catalog, search_review, search_workflow
from runtime import BasilError


def page(rows, total=None, number=1):
    return json.dumps({
        'success': True, 'code': 0, 'data': rows,
        'addition': {'page': number, 'size': 1000,
                     'total': len(rows) if total is None else total},
    })


def full_catalog():
    return [{
        'id': '2074770461966864384',
        'name': 'visual_color',
        'description': '记录画面主色',
        'type': 'MULTI_SELECT',
        'planType': 'LITE',
        'groupId': '11',
        'groupName': '视觉',
        'sort': 3,
        'createdBy': 'user-a',
        'updatedBy': 'user-b',
        'createdAt': '2026-01-01T00:00:00Z',
        'updatedAt': '2026-01-02T00:00:00Z',
        'enumOptionList': [{
            'id': '2074770461966864385', 'fieldId': '2074770461966864384',
            'value': 'Black', 'description': '黑色',
            'sort': 1, 'createdAt': '2026-01-01T00:00:00Z', 'updatedAt': '2026-01-01T00:00:00Z',
        }],
    }, {
        'id': '2097987580342702080',
        'name': 'Color',
        'description': '',
        'type': 'NOT_ENUM',
        'createdAt': '2026-01-01T00:00:00Z',
    }]


class CompactProjectionTests(unittest.TestCase):
    def test_compact_keeps_semantic_values_and_drops_audit_keys(self):
        compact = metadata_catalog.compact_catalog(full_catalog())
        first = compact[0]
        self.assertEqual(first['id'], '2074770461966864384')
        self.assertEqual(first['name'], 'visual_color')
        self.assertEqual(first['type'], 'MULTI_SELECT')
        self.assertEqual(first['description'], '记录画面主色')
        self.assertEqual(first['groupId'], '11')
        self.assertEqual(first['groupName'], '视觉')
        self.assertEqual(first['enumOptionList'], [{
            'id': '2074770461966864385', 'value': 'Black', 'description': '黑色',
        }])
        for dropped in ('createdAt', 'updatedAt', 'createdBy', 'updatedBy', 'sort', 'planType'):
            self.assertNotIn(dropped, first)
        self.assertNotIn('fieldId', first['enumOptionList'][0])
        self.assertNotIn('createdAt', first['enumOptionList'][0])

    def test_compact_is_much_smaller_than_full(self):
        full = json.dumps(full_catalog(), ensure_ascii=False, indent=2)
        compact = json.dumps(metadata_catalog.compact_catalog(full_catalog()),
                             ensure_ascii=False, separators=(',', ':'))
        self.assertLess(len(compact.encode()), len(full.encode()) * 0.6)

    def test_case_insensitive_name_collisions_are_exposed(self):
        fields = full_catalog() + [{'id': '3', 'name': 'color', 'type': 'NOT_ENUM'}]
        self.assertEqual(metadata_catalog.name_collisions(fields), [['Color', 'color']])
        self.assertEqual(metadata_catalog.name_collisions(full_catalog()), [])

    def test_catalog_cli_compact_and_full_contracts(self):
        fields = full_catalog() + [{'id': '3', 'name': 'color', 'type': 'NOT_ENUM'}]
        for view, expect_audit in (('compact', False), ('full', True)):
            payload = {'operation': 'metadata_catalog'}
            if view == 'compact':
                payload['view'] = 'compact'
            output = io.StringIO()
            with patch.object(cli, 'read_json_stdin', return_value=payload), \
                 patch.object(cli, 'fetch_metadata_catalog', return_value=fields) as fetch, \
                 redirect_stdout(output):
                cli.run_capability({'metadata_catalog'})
            fetch.assert_called_once()
            body = json.loads(output.getvalue())
            self.assertEqual(body['addition']['total'], 3)
            if expect_audit:
                self.assertIn('createdAt', body['data'][0])
                self.assertEqual(set(body['addition']), {'total'})
                self.assertGreater(len(output.getvalue().splitlines()), 1)
            else:
                self.assertEqual(len(output.getvalue().splitlines()), 1)
                self.assertNotIn('createdAt', body['data'][0])
                self.assertEqual(body['addition']['view'], 'compact')
                self.assertIn('nameCollisions', body['addition'])

    def test_catalog_view_is_not_sent_to_the_api(self):
        raw = page(full_catalog())
        output = io.StringIO()
        with patch.object(cli, 'read_json_stdin',
                          return_value={'operation': 'metadata_catalog', 'view': 'compact'}), \
             patch.object(metadata_catalog, 'request', return_value=(raw, 'application/json')) as network, \
             redirect_stdout(output):
            cli.run_capability({'metadata_catalog'})
        self.assertEqual(network.call_args.kwargs['query'], {'page': 1, 'size': 1000})
        self.assertNotIn('view', network.call_args.kwargs)
        self.assertEqual(json.loads(output.getvalue())['addition']['view'], 'compact')

    def test_invalid_view_fails_before_network(self):
        for view in ('', 'COMPACT', None, ['compact']):
            with self.subTest(view=view), \
                 patch.object(cli, 'read_json_stdin',
                              return_value={'operation': 'metadata_catalog', 'view': view}), \
                 patch.object(cli, 'fetch_metadata_catalog') as fetch:
                with self.assertRaisesRegex(BasilError, 'full or compact'):
                    cli.run_capability({'metadata_catalog'})
                fetch.assert_not_called()

    def test_metadata_fields_view_never_reaches_the_api_query(self):
        payload = {'operation': 'metadata_fields', 'query': {'page': 1, 'size': 10},
                   'view': 'compact'}
        raw = json.dumps({'success': True, 'code': 0, 'data': full_catalog(),
                          'addition': {'page': 1, 'size': 10, 'total': 2}})
        output = io.StringIO()
        with patch.object(cli, 'read_json_stdin', return_value=payload), \
             patch('runtime.openapi.request', return_value=(raw, 'application/json')) as network, \
             redirect_stdout(output):
            cli.run_capability({'metadata_fields'})
        self.assertEqual(network.call_args.kwargs['query'], {'page': 1, 'size': 10})
        self.assertNotIn('view', network.call_args.kwargs)
        self.assertNotIn('createdAt', output.getvalue())

    def test_metadata_fields_view_is_a_local_projection(self):
        payload = {'operation': 'metadata_fields', 'query': {'page': 1, 'size': 10},
                   'view': 'compact'}
        result = {'success': True, 'code': 0, 'data': full_catalog(),
                  'addition': {'page': 1, 'size': 10, 'total': 2}}
        output = io.StringIO()
        with patch.object(cli, 'read_json_stdin', return_value=payload), \
             patch.object(cli, 'execute_operation', return_value=(result, 'application/json')) as execute, \
             redirect_stdout(output):
            cli.run_capability({'metadata_fields'})
        sent = execute.call_args.args[0]
        self.assertNotIn('view', sent)
        body = json.loads(output.getvalue())
        self.assertNotIn('createdAt', body['data'][0])
        self.assertEqual(body['addition'], {'page': 1, 'size': 10, 'total': 2, 'view': 'compact'})


class NameLookupTests(unittest.TestCase):
    def setUp(self):
        payload = {'operation': 'file_metadata_operate', '_confirm': True,
                   'body': {'operationType': 'ADD', 'fileId': '2097542604630659072',
                            'fieldName': 'season', 'value': '["summer"]'}}
        patches = [patch.object(cli, 'read_json_stdin', return_value=payload),
                   patch.object(cli, 'print_json'),
                   patch.object(cli, 'execute_operation',
                                return_value=({'success': True, 'code': 0}, 'application/json'))]
        for item in patches:
            result = item.start()
            self.addCleanup(item.stop)
        self.execute = result

    def test_name_only_write_reads_all_pages_without_name_filter(self):
        first = [{'id': str(index), 'name': 'season-other'} for index in range(1000)]
        second = [{'id': '999999', 'name': 'season'}]
        responses = [(page(first, total=1001), 'application/json'),
                     (page(second, total=1001, number=2), 'application/json')]
        with patch.object(metadata_catalog, 'request', side_effect=responses) as network:
            cli.run_capability({'file_metadata_operate'})
        self.assertEqual([call.kwargs['query'] for call in network.call_args_list],
                         [{'page': 1, 'size': 1000}, {'page': 2, 'size': 1000}])
        self.execute.assert_called_once()
        body = self.execute.call_args.args[0]['body']
        self.assertEqual(body['fieldId'], '999999')
        self.assertNotIn('fieldName', body)

    def test_duplicate_exact_name_on_later_page_blocks_write(self):
        first = [{'id': str(index), 'name': 'other'} for index in range(1000)]
        first[0]['name'] = 'season'
        second = [{'id': '999999', 'name': 'season'}]
        responses = [(page(first, total=1001), 'application/json'),
                     (page(second, total=1001, number=2), 'application/json')]
        with patch.object(metadata_catalog, 'request', side_effect=responses):
            with self.assertRaisesRegex(BasilError, 'exactly one'):
                cli.run_capability({'file_metadata_operate'})
        self.execute.assert_not_called()

    def test_incomplete_catalog_blocks_write(self):
        with patch.object(metadata_catalog, 'request', return_value=(
                page([{'id': '1', 'name': 'season'}], total=2), 'application/json')):
            with self.assertRaisesRegex(BasilError, 'Incomplete'):
                cli.run_capability({'file_metadata_operate'})
        self.execute.assert_not_called()

    def test_catalog_errors_stop_without_fallback_or_write(self):
        for status in (400, 422, 401, 403, 405, 500, None):
            details = None if status is None else {'httpStatus': status}
            with self.subTest(status=status), patch.object(
                    metadata_catalog, 'request',
                    side_effect=BasilError('failure', details=details)) as network:
                with self.assertRaisesRegex(BasilError, 'failure'):
                    cli.run_capability({'file_metadata_operate'})
                network.assert_called_once()
                self.assertEqual(network.call_args.kwargs['query'], {'page': 1, 'size': 1000})
                self.execute.assert_not_called()


class SessionCompactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patches = [patch.object(search_review, 'ROOT', Path(self.temp.name) / 'sessions'),
                   patch.object(search_review.runtime, 'RUNTIME_DOMAIN', 'https://current.test'),
                   patch.object(search_review.runtime, 'AUTH_MODE', 'oauth2'),
                   patch.dict(os.environ, {'APP_OAUTH_BASILOS_ACCESS_TOKEN': 'unit-test-credential'})]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def test_session_catalog_rejects_unknown_view_before_network(self):
        with patch.object(metadata_catalog, 'request') as network:
            with self.assertRaisesRegex(BasilError, 'full or compact'):
                search_workflow.execute({'operation': 'catalog', 'attemptId': 'attempt',
                                         'view': 'lean'})
            network.assert_not_called()

    def test_session_catalog_compact_handoff_keeps_semantics(self):
        raw = json.dumps({'success': True, 'code': 0, 'data': full_catalog(),
                          'addition': {'page': 1, 'size': 1000, 'total': 2}})
        with patch.object(metadata_catalog, 'request', return_value=(raw, 'application/json')):
            result = search_workflow.execute({'operation': 'catalog', 'attemptId': 'attempt',
                                             'view': 'compact'})
        sid = result['data']['sessionId']
        self.assertFalse(result['data']['catalogReadComplete'])
        chunks = []
        while True:
            read = search_workflow.execute({'operation': 'read', 'attemptId': 'attempt',
                                           'sessionId': sid})
            chunks.append(read['data']['chunk'])
            ack = search_workflow.execute({'operation': 'ack', 'attemptId': 'attempt',
                                           'sessionId': sid,
                                           'receipt': read['data']['receipt']})
            if read['data']['eof']:
                self.assertTrue(ack['data']['catalogReadComplete'])
                break
        fields = [json.loads(line) for line in ''.join(chunks).splitlines()]
        self.assertEqual(fields[0]['id'], '2074770461966864384')
        self.assertEqual(fields[0]['enumOptionList'][0]['value'], 'Black')
        self.assertNotIn('createdAt', fields[0])


if __name__ == '__main__':
    unittest.main()
