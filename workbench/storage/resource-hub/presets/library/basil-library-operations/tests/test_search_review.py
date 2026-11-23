"""Guarded workflow tests through the existing API transport boundary."""
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import runtime
from library import metadata_catalog, search_review, search_workflow, structured_search
from runtime import BasilError


def response(rows, more=False, link='https://current.test/result'):
    return json.dumps({'success': True, 'code': 0, 'data': {
        'fileList': rows, 'pageInfo': {'hasMore': more}, 'snapshotLink': link}}), 'application/json'


class SearchReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patches = [patch.object(search_review, 'ROOT', Path(self.temp.name) / 'sessions'),
                   patch.object(runtime, 'RUNTIME_DOMAIN', 'https://current.test'),
                   patch.object(runtime, 'AUTH_MODE', 'oauth2'),
                   patch.dict(os.environ, {'APP_OAUTH_BASILOS_ACCESS_TOKEN': 'unit-test-credential'}),
                   patch.object(structured_search, 'fetch_metadata_catalog', return_value=[]),
                   patch.object(structured_search, 'request')]
        started = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        self.catalog, self.network = started[-2:]
        self.sid = None

    def call(self, op, **kw):
        payload = {'operation': op, 'attemptId': 'test-attempt', **kw}
        if op != 'catalog':
            payload.setdefault('sessionId', self.sid)
        return search_workflow.execute(payload)

    def start(self, rows, more=False, intent='targeted', **plan):
        self.catalog_start([])
        self.network.return_value = response(rows, more)
        result = self.call('search', intent=intent, plan=plan or {'keyword': '黑色裤子'})
        self.assertEqual(result['data']['sessionId'], self.sid)
        self.assertTrue(result['data']['catalogReadComplete'])
        self.assertNotIn('snapshotLink', json.dumps(result))
        self.assertNotIn('current.test/result', json.dumps(result))
        return result

    def consume(self, budget=8000):
        chunks = []
        while True:
            result = self.call('read', maxBytes=budget)
            self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, indent=2).encode()) + 1, budget)
            data = result['data']
            chunks.append(data['chunk'])
            self.call('ack', receipt=data['receipt'])
            if data['eof']:
                return ''.join(chunks)

    def decide(self, values):
        return self.call('review', decisions=[{'id': fid, 'decision': decision,
            'evidence': 'Observed image or explicit conflicting description'} for fid, decision in values])

    def catalog_start(self, fields):
        raw = json.dumps({'success': True, 'code': 0, 'data': fields,
                          'addition': {'page': 1, 'size': 1000, 'total': len(fields)}})
        with patch.object(metadata_catalog, 'request', return_value=(raw, 'application/json')) as network:
            result = search_workflow.execute({'operation': 'catalog', 'attemptId': 'test-attempt'})
            self.assertEqual(network.call_args.args[:2], ('GET', '/openapi/assets/metadata/field/page'))
        self.sid = result['data']['sessionId']
        return result['data']

    def test_large_catalog_handoff_gate_and_live_validation(self):
        fields = [{'id': '2074770461966864384', 'name': 'visual_color',
                   'description': '黑色\\"\n🙂' * 4000, 'type': 'MULTI_SELECT',
                   'enumOptionList': [{'id': '2074770461966864385', 'value': 'Black',
                                       'description': 'Black garment color'}]}]
        result = self.catalog_start(fields)
        self.assertEqual(result['status'], 'catalog_read_required')
        self.assertFalse(result['catalogReadComplete'])
        plan = {'metadataConditions': [{'fieldId': fields[0]['id'],
                'value': ['Black'], 'sourceText': '黑色'}], 'keyword': '长裤', 'spaceType': 'TEAM'}
        with self.assertRaisesRegex(BasilError, 'complete catalog'):
            self.call('search', sessionId=self.sid, intent='targeted', plan=plan)
        self.network.assert_not_called()
        first = self.call('read')['data']
        smaller = self.call('read', maxBytes=1024)['data']
        self.assertEqual(smaller['offset'], first['offset'])
        with self.assertRaisesRegex(BasilError, 'receipt'):
            self.call('ack', receipt=first['receipt'])
        content = self.consume(2048)
        self.assertEqual([json.loads(line) for line in content.splitlines()], fields)
        self.catalog.return_value = fields
        self.network.return_value = response([{'id': '99', 'description': 'Black trousers'}])
        result = self.call('search', sessionId=self.sid, intent='targeted', plan=plan)['data']
        self.assertTrue(result['catalogReadComplete'])
        self.assertFalse(result['contentReadComplete'])
        self.assertEqual(result['candidateCount'], 1)
        self.catalog.assert_called_once()
        wire = self.network.call_args.kwargs['body']
        self.assertEqual(wire['spaceType'], 'TEAM')
        self.assertEqual(wire['keyword'], '长裤')
        self.assertFalse(wire['enableAI'])
        with self.assertRaisesRegex(BasilError, 'complete catalog'):
            self.call('search', sessionId=self.sid, intent='targeted', plan=plan)

    def test_catalog_context_expiry_cleanup_and_incomplete_server_page(self):
        self.catalog_start([{'id': '1', 'name': 'color'}])
        with patch.object(runtime, 'RUNTIME_DOMAIN', 'https://other.test'), self.assertRaises(BasilError):
            self.call('read')
        with patch.dict(os.environ, {'APP_OAUTH_BASILOS_ACCESS_TOKEN': 'changed'}), self.assertRaises(BasilError):
            self.call('read')
        with self.assertRaises(BasilError):
            self.call('read', attemptId='other-attempt')
        with patch.object(search_review.time, 'time', return_value=search_review.time.time() + search_review.TTL + 1):
            with self.assertRaisesRegex(BasilError, 'expired'):
                self.call('read')
            self.call('close')
        self.assertFalse((search_review.ROOT / self.sid).exists())
        raw = json.dumps({'success': True, 'code': 0, 'data': [], 'addition': {'page': 1, 'size': 1000, 'total': 2}})
        with patch.object(metadata_catalog, 'request', return_value=(raw, 'application/json')):
            with self.assertRaisesRegex(BasilError, 'Incomplete'):
                search_workflow.execute({'operation': 'catalog', 'attemptId': 'test-attempt'})
        self.network.assert_not_called()

    def test_empty_query_has_diagnostic_status_and_no_refinement_request(self):
        result = self.catalog_start([])
        self.assertTrue(result['catalogReadComplete'])
        self.network.return_value = response([])
        result = self.call('search', sessionId=self.sid, intent='targeted',
                           plan={'keyword': '黑色长裤'})['data']
        self.assertEqual(result['status'], 'query_empty')
        self.assertEqual(result['nextAction'], 'reassess_mapping')
        self.assertFalse(result['deliveryReady'])
        self.network.reset_mock()
        result = self.call('refine')['data']
        self.assertEqual(result['reason'], 'query_empty')
        self.assertFalse(result['deliveryReady'])
        self.network.assert_not_called()
        with self.assertRaises(BasilError):
            self.call('deliver')
        self.call('close')

    def test_targeted_flow_filters_and_preserves_scope(self):
        self.start([{'id': '1', 'description': '黑色裤子'}, {'id': '2', 'description': '白色上衣'}],
                   spaceType='TEAM', folderPath='/Root/Design', keyword='黑色裤子',
                   filterConditions=[{'fieldType': 'FILE_SIZE', 'operator': 'GT', 'value': ['100']}])
        with self.assertRaisesRegex(BasilError, 'refinement'):
            self.call('deliver')
        with self.assertRaisesRegex(BasilError, 'reading incomplete'):
            self.call('refine')
        text = self.consume()
        self.assertNotIn('snapshotLink', text)
        self.decide([('1', 'match'), ('2', 'non_match')])
        self.network.return_value = response([{'id': '1'}], link='https://current.test/refined')
        result = self.call('refine')
        self.assertNotIn('snapshotLink', json.dumps(result))
        wire = self.network.call_args.kwargs['body']
        self.assertEqual(wire['spaceType'], 'TEAM')
        self.assertEqual(wire['folderPath'], '/Root/Design')
        self.assertEqual(wire['filterConditionList'][-1], {'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ['1']})
        self.assertFalse(wire.get('keyword'))
        with self.assertRaisesRegex(BasilError, 'reading incomplete'):
            self.call('deliver')
        self.consume()
        delivered = self.call('deliver')['data']
        self.assertTrue(delivered['deliveryReady'])
        self.assertEqual(delivered['snapshotLink'], 'https://current.test/refined')
        self.assertEqual(self.catalog.call_count, 2)
        self.call('close')
        self.assertFalse((search_review.ROOT / self.sid).exists())

    def test_huge_unicode_escaped_output_is_lossless_and_rereadable(self):
        description = '黑色裤子\\"\n🙂' * 6000
        self.start([{'id': '1', 'description': description}])
        first = self.call('read')['data']
        smaller = self.call('read', maxBytes=1024)['data']
        self.assertEqual(smaller['offset'], 0)
        self.assertNotEqual(first['receipt'], smaller['receipt'])
        with self.assertRaises(BasilError):
            self.call('ack', receipt=first['receipt'])
        with self.assertRaises(BasilError):
            self.decide([('1', 'match')])
        content = self.consume(2048)
        self.assertEqual(json.loads(content)['files'][0]['description'], description)
        self.assertEqual(self.network.call_count, 1)

    def test_pagination_and_unresolved_evidence_block_refine_without_network(self):
        self.start([{'id': '1'}], more=True, size=1)
        self.consume()
        self.decide([('1', 'match')])
        self.network.reset_mock()
        with self.assertRaisesRegex(BasilError, 'Pagination incomplete'):
            self.call('refine')
        self.network.assert_not_called()
        self.network.return_value = response([{'id': '2'}])
        self.call('next')
        self.assertEqual(self.network.call_args.kwargs['body']['page'], 2)
        self.assertEqual(self.network.call_args.kwargs['body']['size'], 1)
        self.consume()
        with self.assertRaisesRegex(BasilError, 'Every candidate'):
            self.call('refine')
        self.decide([('2', 'unresolved')])
        with self.assertRaisesRegex(BasilError, 'Unresolved'):
            self.call('refine')
        with self.assertRaisesRegex(BasilError, 'Unknown'):
            self.decide([('999', 'match')])

    def test_refinement_next_and_membership_exclusions(self):
        self.start([{'id': '1'}, {'id': '2'}])
        self.consume()
        self.decide([('1', 'match'), ('2', 'match')])
        self.network.return_value = response([{'id': '99'}])
        with self.assertRaisesRegex(BasilError, 'outside'):
            self.call('refine')
        self.network.return_value = response([{'id': '1'}], more=True)
        self.call('refine')
        self.consume()
        with self.assertRaisesRegex(BasilError, 'Pagination incomplete'):
            self.call('deliver')
        self.network.return_value = response([{'id': '2'}])
        self.call('next')
        self.assertEqual(self.network.call_args.kwargs['body']['page'], 2)
        self.consume()
        self.assertTrue(self.call('deliver')['data']['deliveryReady'])
        self.start([{'id': '1'}, {'id': '2'}])
        self.consume()
        self.decide([('1', 'match'), ('2', 'match')])
        self.network.return_value = response([{'id': '1'}])
        self.call('refine')
        self.consume()
        with self.assertRaisesRegex(BasilError, 'excluded'):
            self.call('deliver')

    def test_no_matches_and_failed_refine_never_expose_ordinary_link(self):
        self.start([{'id': '1'}])
        self.consume()
        self.decide([('1', 'non_match')])
        self.network.reset_mock()
        self.assertEqual(self.call('refine')['data']['status'], 'no_matches')
        self.network.assert_not_called()
        self.decide([('1', 'match')])
        self.network.side_effect = BasilError('backend failure')
        with self.assertRaisesRegex(BasilError, 'backend failure'):
            self.call('refine')
        with self.assertRaisesRegex(BasilError, 'refinement'):
            self.call('deliver')

    def test_broad_review_can_deliver_without_exhausting_server(self):
        self.start([{'id': '1'}], more=True, intent='broad')
        self.consume()
        self.decide([('1', 'match')])
        self.assertTrue(self.call('deliver')['data']['deliveryReady'])
        self.assertEqual(self.network.call_count, 1)

    def test_provider_frontend_link_is_preserved_for_broad_and_targeted_delivery(self):
        for intent in ('broad', 'targeted'):
            with self.subTest(intent=intent):
                self.network.reset_mock()
                self.catalog_start([])
                candidate_link = 'https://library.test/query/candidates?x=1#results'
                self.network.return_value = response([{'id': '1'}], link=candidate_link)
                started = self.call('search', intent=intent, plan={'keyword': 'poster'})
                self.sid = started['data']['sessionId']
                self.consume()
                self.decide([('1', 'match')])
                expected = candidate_link
                if intent == 'targeted':
                    expected = 'https://library.test:8443/query/refined?x=1&y=2#results'
                    self.network.return_value = response([{'id': '1'}], link=expected)
                    self.call('refine')
                    self.consume()
                delivered = self.call('deliver')
                self.assertTrue(delivered['data']['deliveryReady'])
                self.assertEqual(delivered['data']['snapshotLink'], expected)
                self.assertEqual(self.call('deliver'), delivered)
                self.assertEqual(self.network.call_count, 2 if intent == 'targeted' else 1)
                self.call('close')

    def test_broad_folder_hits_remain_supported_without_file_id_confusion(self):
        self.catalog_start([])
        self.network.return_value = (json.dumps({'success': True, 'code': 0, 'data': {
            'fileList': [{'id': '1'}], 'folderList': [{'id': '1', 'name': 'Design'}],
            'pageInfo': {'hasMore': False}, 'snapshotLink': 'https://current.test/broad'}}), 'application/json')
        result = self.call('search', intent='broad', plan={'keyword': 'Design'})
        self.sid = result['data']['sessionId']
        self.assertEqual(result['data']['candidateCount'], 2)
        self.assertEqual(json.loads(self.consume())['folders'][0]['name'], 'Design')
        self.decide([('1', 'match')])
        with self.assertRaisesRegex(BasilError, 'Every candidate'):
            self.call('deliver')
        self.call('review', decisions=[{'id': '1', 'kind': 'folder', 'decision': 'match', 'evidence': 'Relevant folder name'}])
        self.assertEqual(self.call('deliver')['data']['snapshotLink'], 'https://current.test/broad')

    def test_search_requires_catalog_session_before_network_or_state_creation(self):
        for session in ({}, {'sessionId': None}, {'sessionId': ''},
                        {'sessionId': '../bad'}, {'sessionId': 'session-abcdefgh'}):
            with self.subTest(session=session), patch.object(search_review, 'fetch_metadata_catalog') as catalog:
                with self.assertRaisesRegex(BasilError, 'sessionId|Unknown search session'):
                    search_workflow.execute({'operation': 'search', 'attemptId': 'test-attempt',
                                             'intent': 'targeted', 'plan': {'keyword': 'poster'}, **session})
                catalog.assert_not_called()
                self.catalog.assert_not_called()
                self.network.assert_not_called()
                self.assertFalse(search_review.ROOT.exists())

    def test_context_changes_invalid_controls_corruption_and_expiry(self):
        self.catalog_start([])
        with self.assertRaises(BasilError):
            self.call('search', plan={})
        self.network.assert_not_called()
        self.start([{'id': '1'}])
        for changes in ({'attemptId': 'other'}, {'sessionId': '../bad'}):
            with self.assertRaises(BasilError):
                self.call('read', **changes)
        with patch.object(runtime, 'RUNTIME_DOMAIN', 'https://other.test'), self.assertRaises(BasilError):
            self.call('read')
        with patch.dict(os.environ, {'APP_OAUTH_BASILOS_ACCESS_TOKEN': 'new-token'}), self.assertRaises(BasilError):
            self.call('read')
        with self.assertRaises(BasilError):
            self.call('refine', confirmedFileIds=['1'])
        directory = search_review.ROOT / self.sid
        serialized = (directory / 'state.json').read_text()
        self.assertNotIn('unit-test-credential', serialized)
        self.assertEqual((directory.stat().st_mode & 0o777), 0o700)
        self.assertEqual(((directory / 'state.json').stat().st_mode & 0o777), 0o600)
        with patch.object(search_review.time, 'time', return_value=search_review.time.time() + search_review.TTL + 1):
            with self.assertRaisesRegex(BasilError, 'expired'):
                self.call('read')
            self.call('close')
        self.start([{'id': '1'}])
        (search_review.ROOT / self.sid / 'state.json').write_text('{}')
        with self.assertRaisesRegex(BasilError, 'damaged'):
            self.call('read')

    def test_repeated_pages_across_batches_block_progress(self):
        self.start([{'id': '1'}], more=True)
        self.consume()
        self.network.return_value = response([{'id': '1'}], more=True)
        with self.assertRaisesRegex(BasilError, 'repeated'):
            self.call('next')

    def test_separate_process_read_uses_runtime_controls_and_exact_output_budget(self):
        self.start([{'id': '1', 'description': '黑色\\"\n🙂' * 3000}])
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        # Exercise the real stdin parser/main/printer in a fresh interpreter.
        code = ("import sys, pathlib, runpy; sys.path.insert(0, sys.argv[1]); "
                "from library import search_review; search_review.ROOT=pathlib.Path(sys.argv[2]); "
                "script=sys.argv[3]; sys.argv=[script]; "
                "runpy.run_path(script, run_name='__main__')")
        payload = {'operation': 'read', 'attemptId': 'test-attempt', 'sessionId': self.sid,
                   '_runtimeDomain': 'https://current.test', '_authMode': 'oauth2', 'maxBytes': 2048}
        result = subprocess.run([sys.executable, '-c', code, str(scripts), str(search_review.ROOT),
                                 str(scripts / 'library/search_workflow.py')],
                                input=json.dumps(payload), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLessEqual(len(result.stdout.encode()), 2048)
        data = json.loads(result.stdout)['data']
        self.call('ack', receipt=data['receipt'])
        self.assertEqual(self.call('read')['data']['offset'], data['nextOffset'])

    def test_missing_link_empty_and_changed_candidate_do_not_deliver(self):
        self.start([])
        self.consume()
        self.assertEqual(self.call('refine')['data']['status'], 'no_matches')
        self.start([{'id': '1'}])
        self.consume()
        self.decide([('1', 'match')])
        self.network.return_value = response([{'id': '1'}], link=None)
        self.call('refine')
        self.consume()
        self.assertFalse(self.call('deliver')['data']['deliveryReady'])
        self.start([{'id': '1', 'description': 'original'}], more=True)
        self.consume()
        self.network.return_value = response([{'id': '1', 'description': 'changed'}, {'id': '2'}])
        with self.assertRaisesRegex(BasilError, 'changed'):
            self.call('next')

    def test_expired_state_cleanup_and_rejected_review_are_atomic(self):
        self.start([{'id': '1'}])
        old = search_review.ROOT / self.sid
        self.consume()
        with self.assertRaises(BasilError):
            self.decide([('1', 'match'), ('2', 'match')])
        self.assertEqual(search_review._load(old)['decisions'], {})
        with patch.object(search_review.time, 'time', return_value=search_review.time.time() + search_review.TTL + 1):
            self.start([{'id': '2'}])
        self.assertFalse(old.exists())


if __name__ == '__main__':
    unittest.main()
