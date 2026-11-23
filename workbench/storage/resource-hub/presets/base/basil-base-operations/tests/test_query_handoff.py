"""Separate calls preserve conditions and links across large output and retries."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import runtime
from base.cli import run_capability
from base.query_results import query, create
from runtime import BasilError

LINK = 'https://studio.test/studio/engine/multi-dim-table-embed/123/456?viewId=789'
FILTER = {'conjunction': 'and', 'filterSet': [
    {'fieldId': 'material-id', 'operator': '=', 'value': 23549}]}


def response(data):
    return json.dumps({'success': True, 'code': 0, 'data': data,
                       'addition': {'total': 1}}), 'application/json'


class QueryHandoffTests(unittest.TestCase):
    def setUp(self):
        credentials = patch.dict(os.environ, {'APP_OAUTH_BASILOS_ACCESS_TOKEN': 'fixture-access'}, clear=True)
        credentials.start()
        self.addCleanup(credentials.stop)
        metadata = patch('base.field_refs._load_fields', return_value=[{'id': 'material-id', 'name': 'material-id'}])
        metadata.start()
        self.addCleanup(metadata.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        cwd = os.getcwd()
        os.chdir(temporary.name)
        self.addCleanup(os.chdir, cwd)
        config = patch.object(runtime, 'RUNTIME_DOMAIN', 'https://current.test')
        config.start()
        self.addCleanup(config.stop)
        self.payload = {'operation': 'record_query', 'query': {
            'tableId': '456', 'filter': FILTER, 'take': 1}}

    def run_query(self, rows=None, **scope):
        with patch('runtime.openapi.request', return_value=response({'recordList':
                rows if rows is not None else [{'id': 'r', 'fields': {'material_id': 23549}}]})) as network:
            result = query({**self.payload, 'query': {**self.payload['query'], **scope}})
        self.assertEqual(network.call_count, 1)
        self.assertEqual(network.call_args.args[0], 'GET')
        return result

    def create_args(self, result):
        return {'operation': 'view_create_query_result', 'resultFile': result['resultFile'],
                'viewName': 'Products with material_id 23549'}

    def test_cross_origin_link_delivered_large_record_preserved_and_retry_no_post(self):
        rows = [{'id': 'r', 'fields': {'Assets': '图片\\"' * 50000, 'material_id': 23549}}]
        result = self.run_query(rows)
        self.assertLess(len(json.dumps(result, ensure_ascii=False, indent=2).encode()) + 1, 8001)
        self.assertFalse(result['previewComplete'])
        self.assertEqual(result['data']['recordList'][0]['fields'], {'material_id': 23549})
        self.assertEqual(result['workflow']['viewStatus'], 'pending')
        path = Path(result['resultFile'])
        self.assertEqual(json.loads(path.read_text())['result']['data']['recordList'], rows)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with patch('runtime.openapi.request', return_value=response({'id': '789', 'snapshotLink': LINK})) as network:
            created = create(self.create_args(result))
            recovered = create(self.create_args(result))
        self.assertEqual(network.call_count, 1)
        self.assertEqual(network.call_args.args[0], 'POST')
        body = network.call_args.kwargs['body']
        self.assertEqual(body['filter'], FILTER)
        self.assertFalse(body['display'])
        self.assertNotIn('enableShare', body)
        self.assertNotIn('publishToAssetsIs', body)
        self.assertEqual(created['data'], {'snapshotLink': LINK})
        self.assertEqual(created, recovered)
        self.assertLess(len(json.dumps(created).encode()), 2000)
        self.assertEqual(json.loads(path.read_text())['result']['data']['recordList'], rows)

    def test_same_label_new_queries_get_distinct_persisted_names(self):
        results = [self.run_query(), self.run_query()]
        names = []
        def post(*args, **kwargs):
            name = kwargs['body']['name']
            self.assertNotIn(name, names)
            names.append(name)
            saved = json.loads(Path(results[len(names) - 1]['resultFile']).read_text())
            self.assertEqual(saved['result']['workflow']['viewName'], name)
            self.assertEqual(saved['result']['workflow']['viewStatus'], 'failed_or_unknown')
            return response({'id': '789', 'snapshotLink': LINK})
        with patch('runtime.openapi.request', side_effect=post) as network:
            for result in results:
                first = create(self.create_args(result))
                second = create({**self.create_args(result), 'viewName': 'Changed label'})
                self.assertEqual(first, second)
                self.assertTrue(first['success'])
                self.assertEqual(first['code'], 0)
                self.assertEqual(first['workflow']['viewName'], names[-1])
        self.assertEqual(network.call_count, 2)
        for name in names:
            self.assertTrue(name.startswith('Products with material_id 23549 - '))

    def test_duplicate_error_is_not_retried_and_reports_delivery_failure(self):
        result = self.run_query()
        with patch('runtime.openapi.request', side_effect=BasilError('HTTP 400; 数据重复')) as network:
            first = create(self.create_args(result))
            second = create(self.create_args(result))
        network.assert_called_once()
        self.assertEqual(first, second)
        self.assertFalse(first['success'])
        self.assertEqual(first['code'], 'QUERY_RESULT_UNAVAILABLE')
        self.assertIn('数据重复', first['workflow']['error'])
        self.assertEqual(first['workflow']['queryStatus'], 'succeeded')

    def test_missing_link_retains_view_id_and_does_not_recreate(self):
        result = self.run_query()
        with patch('runtime.openapi.request', return_value=response({'id': '789'})) as network:
            first = create(self.create_args(result))
            second = create(self.create_args(result))
        network.assert_called_once()
        self.assertEqual(first, second)
        self.assertEqual(first['workflow']['viewStatus'], 'created')
        self.assertEqual(first['workflow']['failedStage'], 'result_link')
        self.assertEqual(first['workflow']['viewId'], '789')
        self.assertNotIn('snapshotLink', first['data'])
        self.assertFalse(first['success'])
        self.assertEqual(first['code'], 'QUERY_RESULT_UNAVAILABLE')

    def test_failed_or_interrupted_post_does_not_repeat(self):
        for error in [BasilError('HTTP 503'), KeyboardInterrupt()]:
            with self.subTest(error=type(error).__name__):
                result = self.run_query()
                with patch('runtime.openapi.request', side_effect=error) as network:
                    try:
                        create(self.create_args(result))
                    except KeyboardInterrupt:
                        pass
                    outcome = create(self.create_args(result))
                network.assert_called_once()
                self.assertEqual(outcome['workflow']['viewStatus'], 'failed_or_unknown')
                self.assertFalse(outcome['workflow']['retryAllowed'])
                self.assertFalse(outcome['success'])
                self.assertIn('viewName', outcome['workflow'])

    def test_empty_and_unsupported_scope_never_create_misleading_view(self):
        for rows, scope, status in [([], {}, 'not_created_empty_page'),
                                  ([{'id': 'r'}], {'search': 'x'}, 'not_created_unsupported_scope')]:
            result = self.run_query(rows, **scope)
            with patch('runtime.openapi.request') as network:
                outcome = create(self.create_args(result))
            network.assert_not_called()
            self.assertEqual(outcome['workflow']['viewStatus'], status)
            self.assertNotIn('snapshotLink', outcome['data'])
            self.assertFalse(outcome['success'])

    def test_handoff_cannot_replace_query_or_change_environment(self):
        result = self.run_query()
        with patch('runtime.openapi.request') as network:
            with self.assertRaises(BasilError):
                create({**self.create_args(result), 'query': {'tableId': '999'}})
            with patch.object(runtime, 'RUNTIME_DOMAIN', 'https://other.test'):
                with self.assertRaises(BasilError):
                    create(self.create_args(result))
        network.assert_not_called()

    def test_local_preflight_preserves_pending_result_for_auth_recovery(self):
        result = self.run_query()
        path = Path(result['resultFile'])
        original = path.read_bytes()
        with patch.dict(os.environ, {}, clear=True), patch('runtime.openapi.request') as network:
            with self.assertRaises(BasilError):
                create(self.create_args(result))
            network.assert_not_called()
        self.assertEqual(path.read_bytes(), original)
        with patch('runtime.openapi.request') as network:
            with self.assertRaises(BasilError):
                create({**self.create_args(result), '_timeout': 0})
            network.assert_not_called()
        self.assertEqual(path.read_bytes(), original)
        with patch('runtime.openapi.request', return_value=response({'snapshotLink': LINK})) as network:
            self.assertTrue(create(self.create_args(result))['success'])
            network.assert_called_once()

    def test_damaged_result_files_fail_before_creation(self):
        result = self.run_query()
        path = Path(result['resultFile'])
        saved = json.loads(path.read_text())
        for damaged in ('not json', '[]', '{}', json.dumps({**saved, 'result': {}})):
            path.write_text(damaged)
            with patch('runtime.openapi.request') as network:
                with self.assertRaises(BasilError):
                    create(self.create_args(result))
                network.assert_not_called()
            self.assertEqual(path.read_text(), damaged)

    def test_concurrent_creation_posts_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        import time
        result = self.run_query()
        barrier = Barrier(2)
        def invoke():
            barrier.wait(timeout=3)
            return create(self.create_args(result))
        def transport(*args, **kwargs):
            time.sleep(0.05)
            return response({'id': '789', 'snapshotLink': LINK})
        with patch('runtime.openapi.request', side_effect=transport) as network, ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(invoke) for _ in range(2)]
            outcomes = [future.result(timeout=5) for future in futures]
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertTrue(outcomes[0]['success'])
        network.assert_called_once()

    def test_many_records_and_wide_unicode_fields_fit_complete_json(self):
        rows = [{'id': str(i), 'fields': {('名字' * 100 + str(j)): '\\"' * 50 for j in range(50)}}
                for i in range(10)]
        result = self.run_query(rows)
        encoded = json.dumps(result, ensure_ascii=False, indent=2).encode()
        self.assertLessEqual(len(encoded) + 1, 8000)
        self.assertEqual(json.loads(encoded)['returnedCount'], 10)
        self.assertFalse(result['previewComplete'])

    def test_real_capability_dispatch_runs_each_stage_independently(self):
        from base.records import OPERATIONS as records
        from base.views import OPERATIONS as views
        def dispatch(payload, allowed, data):
            with patch('sys.argv', ['script']), patch('base.cli.read_json_stdin', return_value=payload), \
                 patch('runtime.openapi.request', return_value=response(data)) as network, \
                 patch('sys.stdout', new_callable=io.StringIO) as stdout:
                run_capability(allowed)
            self.assertEqual(network.call_count, 1)
            return json.loads(stdout.getvalue())
        queried = dispatch(self.payload, records, {'recordList': [{'id': 'r'}]})
        created = dispatch(self.create_args(queried), views, {'id': '789', 'snapshotLink': LINK})
        self.assertEqual(created['data']['snapshotLink'], LINK)


if __name__ == '__main__':
    unittest.main()
