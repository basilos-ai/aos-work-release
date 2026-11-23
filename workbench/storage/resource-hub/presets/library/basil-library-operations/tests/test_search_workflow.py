"""Internal query/refinement helpers; public session routing is tested in test_search_review."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from library import search_workflow, structured_search
from runtime import BasilError

CATALOG = [{'id': '1', 'type': 'SINGLE_SELECT', 'enumOptionList': [{'id': '9', 'value': 'Black'}]}]
PLAN = {'keyword': 'poster', 'metadataLogic': 'OR',
        'metadataConditions': [{'fieldId': '1', 'value': ['Black'], 'sourceText': '黑色'}],
        'spaceType': 'TEAM', 'folderPath': '/Root/Design', 'includeSubfolders': True,
        'fileTypeFilter': ['IMAGE'], 'page': 4, 'size': 10,
        'sortRule': {'previewableTypeOrder': ['IMAGE']},
        'filterConditions': [{'fieldType': 'FILE_SIZE', 'operator': 'GT', 'value': ['100']}]}


def response(ids, more=False):
    return json.dumps({'success': True, 'code': 0, 'data': {
        'fileList': [{'id': value} for value in ids], 'pageInfo': {'hasMore': more},
        'snapshotLink': 'https://current.test/result'}}), 'application/json'


class SearchWorkflowTests(unittest.TestCase):
    def test_build_and_search_use_the_existing_wire_contract(self):
        source = {'operation': 'search', 'plan': copy.deepcopy(PLAN), '_timeout': 9}
        before = copy.deepcopy(source)
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG) as catalog, patch.object(structured_search, 'request', return_value=response(['42'])) as network:
            result = search_workflow.execute_query(source)
        catalog.assert_called_once_with(timeout=9)
        network.assert_called_once()
        wire = network.call_args.kwargs['body']
        self.assertEqual(wire['tagConditionList'], [{'fieldId': 1, 'value': [9]}])
        self.assertEqual(wire['tagLogicType'], 'OR')
        self.assertEqual(wire['page'], 4)
        self.assertNotIn('sourceText', json.dumps(wire))
        self.assertEqual(source, before)
        self.assertFalse(result['data']['complete'])

    def test_refinement_preserves_scope_and_intersects_all_existing_id_filters(self):
        plan = copy.deepcopy(PLAN)
        plan['filterConditions'] += [
            {'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ['00042', '43', '44']},
            {'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ['42', '44']},
        ]
        before = copy.deepcopy(plan)
        refined = search_workflow.refinement_plan(plan, ['43', '42', '00042', '99'])
        self.assertEqual(refined['filterConditions'], [PLAN['filterConditions'][0],
            {'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ['42']}])
        for key in set(plan) - {'keyword', 'page', 'filterConditions'}:
            self.assertEqual(refined[key], plan[key])
        self.assertEqual(refined['keyword'], '')
        self.assertEqual(refined['page'], 1)
        self.assertEqual(plan, before)

    def test_bad_or_empty_refinement_never_queries_broadly(self):
        for ids in (None, [], [True], [42], ['-1'], ['9223372036854775808']):
            with self.subTest(ids=ids), patch.object(structured_search, 'fetch_metadata_catalog') as catalog:
                with self.assertRaises(BasilError):
                    search_workflow.execute_query({'operation': 'refine', 'acceptedPlan': PLAN, 'confirmedFileIds': ids})
                catalog.assert_not_called()
        plan = {**PLAN, 'filterConditions': [{'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ['1']}]}
        with self.assertRaises(BasilError):
            search_workflow.refinement_plan(plan, ['2'])

    def test_refinement_still_checks_live_metadata_and_result_membership(self):
        source = {'operation': 'refine', 'acceptedPlan': PLAN, 'confirmedFileIds': ['42']}
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=[]), patch.object(structured_search, 'request') as network:
            with self.assertRaises(BasilError):
                search_workflow.execute_query(source)
            network.assert_not_called()
        for ids in (['42'], ['99']):
            with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), patch.object(structured_search, 'request', return_value=response(ids)) as network:
                if ids == ['42']:
                    result = search_workflow.execute_query(source)
                    self.assertTrue(result['data']['complete'])
                else:
                    with self.assertRaisesRegex(BasilError, 'outside'):
                        search_workflow.execute_query(source)
                self.assertEqual(network.call_args.kwargs['body']['filterConditionList'][-1]['value'], ['42'])

    def test_inspection_batches_reuse_one_catalog_and_preserve_all_pages(self):
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=[]) as catalog, patch.object(structured_search, 'request', side_effect=[response(['1'], True), response(['2'])]) as network:
            result = search_workflow.execute_query({'operation': 'search', 'plan': {'keyword': 'x'}, 'inspectPages': 2})
        self.assertEqual(catalog.call_count, 1)
        self.assertEqual(network.call_count, 2)
        self.assertTrue(result['data']['complete'])
        self.assertEqual(len(result['data']['pages']), 2)

    def test_invalid_controls_fail_before_network(self):
        for payload in ({'operation': 'search', 'plan': {}, 'inspectPages': 0},
                        {'operation': 'search', 'plan': {}, 'inspectResults': False},
                        {'operation': 'search', 'plan': {}, 'confirmedFileIds': ['1']},
                        {'operation': 'refine', 'plan': {}},
                        {'operation': 'refine', 'acceptedPlan': PLAN, 'confirmedFileIds': ['42'], 'page': None}):
            with patch.object(structured_search, 'fetch_metadata_catalog') as catalog:
                with self.assertRaises(BasilError):
                    search_workflow.execute_query(payload)
                catalog.assert_not_called()

    def test_refinement_continuation_does_not_change_constraints(self):
        source = {'operation': 'refine', 'acceptedPlan': PLAN,
                  'confirmedFileIds': ['42'], 'page': 2}
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), patch.object(structured_search, 'request', return_value=response(['42'])) as network:
            result = search_workflow.execute_query(source)
        self.assertEqual(network.call_args.kwargs['body']['page'], 2)
        self.assertEqual(network.call_args.kwargs['body']['tagLogicType'], 'OR')
        self.assertFalse(result['data']['complete'])
        self.assertIsNone(result['data']['nextPage'])


if __name__ == '__main__':
    unittest.main()
