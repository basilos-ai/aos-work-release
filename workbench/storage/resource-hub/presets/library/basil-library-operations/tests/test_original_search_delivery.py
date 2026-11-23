"""Original discovery/build/search/refinement wire chain retains final links."""
import copy
import json
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from library.build_structured_search import build_structured_search
from library import structured_search
import runtime
from runtime import BasilError

CATALOG = [{'id': '1', 'type': 'SINGLE_SELECT',
            'enumOptionList': [{'id': '9', 'value': 'Black'}]}]


def response(ids, link, more=False):
    return json.dumps({'success': True, 'code': 0, 'data': {
        'fileList': [{'id': fid, 'description': 'fixture content'} for fid in ids],
        'pageInfo': {'hasMore': more}, 'snapshotLink': link}}), 'application/json'


class OriginalSearchDeliveryTests(TestCase):
    def setUp(self):
        domain = patch.object(runtime, 'RUNTIME_DOMAIN', 'https://workbench.test')
        domain.start()
        self.addCleanup(domain.stop)

    def test_targeted_two_pages_then_refinement_retains_only_final_link(self):
        candidate = build_structured_search(keyword='trousers', spaceType='TEAM',
            metadataConditions=[{'fieldId': '1', 'value': ['Black'], 'sourceText': '黑色'}])
        final_link = 'https://library.test:8443/query/refined?x=1&y=2#results'
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG) as catalog, patch.object(structured_search, 'request', side_effect=[
            response(['101', '102'], 'https://current.test/query/candidates', True),
            response(['103'], 'https://current.test/query/page2'),
            response(['101', '103'], final_link)]) as network:
            result = structured_search.execute({'operation': 'structured_search',
                'plan': candidate, 'inspectResults': True, 'inspectPages': 2})
            self.assertTrue(result['data']['complete'])
            # Relevance is an Agent decision; this fixture supplies its accepted IDs.
            refined = copy.deepcopy(candidate)
            refined.update(keyword='', page=1, filterConditions=[{
                'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ['101', '103']}])
            refined = build_structured_search(**refined)
            delivered = structured_search.execute({'operation': 'structured_search',
                'plan': refined, 'inspectResults': True})
        self.assertEqual(delivered['data']['snapshotLink'], final_link)
        self.assertEqual([f['id'] for f in delivered['data']['fileList']], ['101', '103'])
        self.assertEqual(catalog.call_count, 2)
        body = network.call_args.kwargs['body']
        self.assertEqual(body['tagConditionList'], [{'fieldId': 1, 'value': [9]}])
        self.assertEqual(body['spaceType'], 'TEAM')
        self.assertEqual(body['filterConditionList'][-1]['value'], ['101', '103'])
        self.assertFalse(body['enableAI'])

    def test_broad_link_only_compatibility_uses_exact_server_link(self):
        link = 'https://library.test/query/broad?x=1&y=2#results'
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=[]), patch.object(structured_search, 'request', return_value=response(['101'], link)):
            result = structured_search.execute({'operation': 'structured_search',
                'plan': build_structured_search(keyword='inspiration')})
        self.assertEqual(result['data'], {'snapshotLink': link})

    def test_failed_refinement_does_not_return_candidate_link(self):
        plan = build_structured_search(filterConditions=[{
            'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ['101']}])
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=[]), patch.object(structured_search, 'request', side_effect=BasilError('fixture transport failure')):
            with self.assertRaisesRegex(BasilError, 'fixture transport failure'):
                structured_search.execute({'operation': 'structured_search',
                    'plan': plan, 'inspectResults': True})
