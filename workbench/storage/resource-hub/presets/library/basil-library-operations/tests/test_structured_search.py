"""Offline contract tests; no credentials or live Library access required."""
import copy
import json
from pathlib import Path
import sys
import subprocess
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import runtime
from runtime import BasilError
from library import cli, metadata_catalog, structured_search
from library.build_structured_search import build_structured_search
from library.search_validation import plan_to_body, validate_metadata, validate_search

CATALOG = [
    {'id': 1, 'type': 'SINGLE_SELECT', 'enumOptionList': [{'id': '101', 'fieldId': '1', 'value': 'Black', 'description': '黑色'}]},
    {'id': 2, 'type': 'MULTI_SELECT', 'enumOptionList': [{'id': 201, 'value': 'Summer'}, {'id': 202, 'value': 'Winter'}]},
    {'id': 3, 'type': 'NOT_ENUM'}, {'id': 4, 'type': 'NUMBER'},
    {'id': 5, 'type': 'STRING'}, {'id': 6, 'type': 'TIME'},
]


def response(data, addition=None):
    return json.dumps({'success': True, 'code': 0, 'data': data, 'addition': addition}), 'application/json'


def plan():
    return build_structured_search(keyword='海报', metadataConditions=[
        {'fieldId': '1', 'value': ['Black'], 'sourceText': '黑色'}])


class SearchTests(unittest.TestCase):
    def setUp(self):
        domain = patch.object(runtime, "RUNTIME_DOMAIN", "https://current.test")
        domain.start()
        self.addCleanup(domain.stop)

    def test_script_entrypoints_use_json_and_controlled_errors(self):
        built = subprocess.run(
            [sys.executable, str(SCRIPTS / 'library/build_structured_search.py')],
            input=json.dumps({'keyword': 'poster'}), text=True, capture_output=True,
        )
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertEqual(json.loads(built.stdout)['metadataLogic'], 'AND')
        rejected = subprocess.run(
            [sys.executable, str(SCRIPTS / 'library/structured_search.py')],
            input=json.dumps({'operation': 'structured_search', 'plan': {'conditionGroupList': []}}),
            text=True, capture_output=True,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertNotIn('Traceback', rejected.stderr)
        self.assertIn('unsupported intermediate plan', rejected.stdout + rejected.stderr)

    def test_adapter_does_not_validate_or_infer(self):
        self.assertEqual(build_structured_search(metadataLogic='INVALID')['metadataLogic'], 'INVALID')

    def test_builder_defaults_do_not_change_cli_body(self):
        plans = [
            {},
            {'keyword': '海报'},
            {'keyword': ''},
            {'keyword': '   '},
            {'spaceType': 'MY'},
            {'metadataConditions': [
                {'fieldId': '1', 'value': ['Black'], 'sourceText': '黑色'}]},
            {'keyword': '海报', 'metadataLogic': 'OR', 'metadataConditions': [
                {'fieldId': '1', 'value': ['Black'], 'sourceText': '黑色'}]},
            {'keyword': '', 'spaceType': '', 'folderPath': '', 'fileTypeFilter': [],
             'filterConditions': [
                 {'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ['42', '0042']}]},
        ]
        for plan in plans:
            with self.subTest(plan=plan):
                self.assertEqual(
                    plan_to_body(plan),
                    plan_to_body(build_structured_search(**plan)),
                )

    def test_conversion_preserves_residual_and_source(self):
        original = plan()
        before = copy.deepcopy(original)
        body = plan_to_body(original)
        self.assertEqual(body['keyword'], '海报')
        self.assertEqual(body['tagLogicType'], 'AND')
        self.assertFalse(body['enableAI'])
        self.assertNotIn('sourceText', json.dumps(body))
        self.assertEqual(original, before)

    def test_non_enum_fields_do_not_require_options(self):
        for key, value in ((3, ['custom', 'tags']), (4, ['42']), (5, ['自由文本']), (6, ['2026-09-05'])):
            with self.subTest(key=key):
                body = {'tagConditionList': [{'fieldId': key, 'value': value}]}
                validate_search(body)
                validate_metadata(body, CATALOG)

    def test_enum_checks_reject_unknown_labels_and_foreign_ids(self):
        for key, value in ((1, '黑色'), (1, '101'), (2, 'Autumn'), (999, 'Black'), (1, 201)):
            with self.subTest(key=key, value=value), self.assertRaises(BasilError):
                validate_metadata({'tagConditionList': [{'fieldId': key, 'value': [value]}]}, CATALOG)

    def test_scalar_cardinality(self):
        with self.assertRaises(BasilError):
            validate_metadata({'tagConditionList': [{'fieldId': 4, 'value': ['1', '2']}]}, CATALOG)

    def test_bad_inputs_fail_as_domain_errors(self):
        invalid = [
            {'conditionGroupList': []}, {'enableAI': 'false'}, {'naturalLanguage': ''},
            {'enableAI': True, 'naturalLanguage': 'test', 'page': 1},
            {'enableAI': True, 'naturalLanguage': 'test', 'keyword': ''},
            {'enableAI': True, 'naturalLanguage': 'test', 'filterConditionList': []},
            {'enableAI': True, 'naturalLanguage': 3}, {'spaceType': {}},
            {'folderPath': '/Root', 'folderIdList': []}, {'folderPath': 'relative'},
            {'folderPath': None}, {'includeSubfolders': 'yes'}, {'includeSubfolders': True},
            {'folderIdList': [True]}, {'page': True}, {'size': 1001},
            {'fileTypeFilter': {}}, {'fileTypeFilter': [{}]}, {'fileTypeFilter': ['FOLDER', 'IMAGE']},
            {'tagLogicType': 'NOT_IN'}, {'tagConditionList': [{'fieldId': True, 'value': ['a']}]},
            {'tagConditionList': [{'fieldId': 1, 'value': []}]},
            {'filterConditionList': [{'fieldType': 'METADATA_FIELD_TYPE', 'operator': 'EQUALS', 'value': ['1']}]},
            {'filterConditionList': [{'fieldType': 'FILE_SIZE', 'operator': 'BETWEEN', 'value': ['1']}]},
        ]
        for body in invalid:
            with self.subTest(body=body), self.assertRaises(BasilError):
                validate_search(body)

    def test_optional_empty_plan_fields_and_explicit_or(self):
        body = plan_to_body({**plan(), 'metadataLogic': 'OR', 'spaceType': '', 'folderPath': '', 'fileTypeFilter': []})
        self.assertEqual(body['tagLogicType'], 'OR')
        self.assertNotIn('spaceType', body)
        self.assertNotIn('folderPath', body)

    def test_unified_plan_rejects_api_and_pro_fields(self):
        for key in ('tagConditionList', 'conditionGroupList', 'enableAI', 'naturalLanguage', 'folderIdList'):
            with self.subTest(key=key), self.assertRaises(BasilError):
                plan_to_body({**plan(), key: []})

    def test_database_range_filter(self):
        condition = {'fieldType': 'FILE_SIZE', 'operator': 'BETWEEN', 'value': ['100', '1000']}
        self.assertEqual(plan_to_body({'filterConditions': [condition]})['filterConditionList'], [condition])

    def test_order_and_endpoint_specific_lite_contract(self):
        calls = []
        def transport(method, endpoint, **kwargs):
            calls.append((method, endpoint, kwargs))
            if method == 'GET':
                return response(CATALOG, {'page': 1, 'size': 1000, 'total': 6})
            return response({'fileList': [{'id': 42}], 'snapshotLink': 'https://example.test/view', 'pageInfo': {'hasMore': False}})
        with patch.object(metadata_catalog, 'request', side_effect=transport), patch.object(structured_search, 'request', side_effect=transport):
            result = structured_search.execute({'operation': 'structured_search', 'plan': plan()})
        self.assertEqual([c[0] for c in calls], ['GET', 'POST'])
        self.assertEqual(calls[0][2]['query'], {'page': 1, 'size': 1000})
        self.assertEqual(calls[1][2]['query'], {'planType': 'LITE'})
        self.assertNotIn('sourceText', json.dumps(calls[-1][2]['body']))
        self.assertEqual(result['data'], {'snapshotLink': 'https://example.test/view'})

    def test_invalid_live_enum_blocks_post_including_legacy(self):
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=[]), patch.object(structured_search, 'request') as post:
            for payload in ({'plan': plan()}, {'body': plan_to_body(plan())}):
                with self.assertRaises(BasilError):
                    structured_search.execute({'operation': 'structured_search', **payload})
            post.assert_not_called()

    def test_keyword_only_also_loads_catalog(self):
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=[]) as fetch, patch.object(structured_search, 'request', return_value=response({'fileList': []})):
            structured_search.execute({'operation': 'structured_search', 'plan': {'keyword': 'poster'}})
            fetch.assert_called_once()

    def test_ai_and_internal_fields_never_reach_post(self):
        bodies = [
            {'enableAI': True}, {'enableAI': True, 'naturalLanguage': 'poster'},
            {'conditionGroupList': []}, {'naturalLanguage': ''}, plan(),
            *({key: None} for key in ('operation', 'plan', 'inspectResults', 'sourceText')),
            {'tagConditionList': [{'fieldId': '1', 'value': ['Black'], 'sourceText': '黑色'}]},
        ]
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), patch.object(structured_search, 'request') as post:
            for body in bodies:
                with self.subTest(body=body), self.assertRaises(BasilError):
                    structured_search.execute({'operation': 'structured_search', 'body': body})
            post.assert_not_called()

    def test_inspection_retains_hits_and_pagination(self):
        result = {'data': {'fileList': [{'id': 7}], 'snapshotLink': 'https://example.test/view', 'pageInfo': {'hasMore': True}}}
        with patch.object(structured_search, 'search_assets_structured', return_value=result):
            self.assertEqual(structured_search.execute({'operation': 'structured_search', 'plan': plan(), 'inspectResults': True}), result)

    def test_generic_catalog_has_no_search_bypass(self):
        self.assertNotIn('structured_search', cli.OPERATIONS)

    def test_failed_catalog_never_posts(self):
        with patch.object(structured_search, 'fetch_metadata_catalog', side_effect=BasilError('incomplete')), patch.object(structured_search, 'request') as post:
            with self.assertRaises(BasilError):
                structured_search.execute({'operation': 'structured_search', 'plan': plan()})
            post.assert_not_called()

    def test_repair_preserves_reliable_conditions_and_keyword(self):
        original = build_structured_search(keyword='海报', metadataConditions=[
            {'fieldId': '1', 'value': ['Black'], 'sourceText': '黑色'},
            {'fieldId': '2', 'value': ['Summer'], 'sourceText': '夏日风格'}])
        # Agent decides which mapping is unreliable; CLI performs no semantic retry.
        repaired = build_structured_search(keyword=original['keyword'] + ' ' + original['metadataConditions'][1]['sourceText'],
                                          metadataConditions=original['metadataConditions'][:1])
        body = plan_to_body(repaired)
        self.assertEqual(body['keyword'], '海报 夏日风格')
        self.assertEqual(body['tagConditionList'], [{'fieldId': '1', 'value': ['Black']}])

    def test_plan_mapping_reaches_exact_api_body_without_mutation(self):
        original = build_structured_search(
            **{**plan(), 'metadataLogic': 'OR'}, spaceType='TEAM', folderPath='/Root/Design',
            includeSubfolders=True, fileTypeFilter=['IMAGE'],
            filterConditions=[{'fieldType': 'FILE_SIZE', 'operator': 'GT', 'value': ['100']}],
        )
        before = copy.deepcopy(original)
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), patch.object(structured_search, 'request', return_value=response({})) as post:
            structured_search.execute({'operation': 'structured_search', 'plan': original, 'inspectResults': True})
        self.assertEqual(post.call_args.kwargs['body'], {
            'enableAI': False, 'keyword': '海报', 'tagLogicType': 'OR',
            'tagConditionList': [{'fieldId': 1, 'value': [101]}],
            'spaceType': 'TEAM', 'folderPath': '/Root/Design', 'includeSubfolders': True,
            'fileTypeFilter': ['IMAGE'],
            'filterConditionList': [{'fieldType': 'FILE_SIZE', 'operator': 'GT', 'value': ['100']}],
            'page': 1, 'size': 50,
        })
        self.assertEqual(original, before)

    def test_empty_fields_and_invalid_space_are_omitted_in_both_inputs(self):
        for space in ('', ' ', 'INVALID', None, {}, 'TEAM'):
            for source in ('plan', 'body'):
                supplied = {'keyword': ' ', 'spaceType': space, 'folderPath': '',
                            'fileTypeFilter': [], 'sortRule': {'previewableTypeOrder': []}, 'page': None}
                supplied.update({'metadataConditions': [], 'filterConditions': []} if source == 'plan'
                                else {'tagConditionList': [], 'tagLogicType': 'AND',
                                      'filterConditionList': [], 'folderIdList': []})
                with self.subTest(space=space, source=source), patch.object(structured_search, 'fetch_metadata_catalog', return_value=[]), patch.object(structured_search, 'request', return_value=response({})) as post:
                    structured_search.execute({'operation': 'structured_search', source: supplied})
                    expected = {'enableAI': False, 'page': 1, 'size': 50}
                    if space == 'TEAM':
                        expected['spaceType'] = space
                    self.assertEqual(post.call_args.kwargs['body'], expected)

    def test_conflicting_scope_and_invalid_metadata_block_post(self):
        bodies = [
            {'folderPath': '/Root', 'folderIdList': [1]},
            {'tagConditionList': [{'fieldId': '999', 'value': ['Black']}]},
            {'tagConditionList': [{'fieldId': '1', 'value': ['黑色']}]},
            {'tagConditionList': [{'fieldId': '1', 'value': []}]},
        ]
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), patch.object(structured_search, 'request') as post:
            for body in bodies:
                with self.subTest(body=body), self.assertRaises(BasilError):
                    structured_search.execute({'operation': 'structured_search', 'body': body})
            post.assert_not_called()

    def test_field_ids_are_strings_in_function_and_plan(self):
        schema = json.loads((SCRIPTS.parent / 'references/build-structured-search.function.json').read_text())
        field = schema['function']['parameters']['properties']['metadataConditions']['items']['properties']['fieldId']
        self.assertEqual(field['type'], 'string')
        for value in (1, 9007199254740993, 1.0, True, None):
            conditions = [{'fieldId': value, 'value': ['Black'], 'sourceText': '黑色'}]
            for build in (build_structured_search, lambda **args: plan_to_body(args)):
                with self.subTest(value=value, build=build), self.assertRaises(BasilError):
                    build(metadataConditions=conditions)

    def test_int64_digits_survive_catalog_plan_and_real_json_transport(self):
        for field_id, option_id in (('2095366385088729088', '2095366385113894912'),
                                    ('9007199254740993', '9223372036854775807')):
            original = build_structured_search(metadataConditions=[
                {'fieldId': field_id, 'value': ['Black'], 'sourceText': '黑色'}])
            before = copy.deepcopy(original)
            rows = [{'id': int(field_id), 'type': 'SINGLE_SELECT',
                     'enumOptionList': [{'id': option_id, 'value': 'Black'}]}]
            with self.subTest(field_id=field_id), patch.object(runtime, 'auth_headers', return_value={}), patch.object(
                runtime, '_perform_request', side_effect=[response(rows, {'page': 1, 'size': 1000, 'total': 1}), response({})]
            ) as transport:
                structured_search.execute({'operation': 'structured_search', 'plan': original})
                self.assertIn('/openapi/assets/metadata/field/page?', transport.call_args_list[0].args[1])
                self.assertTrue(transport.call_args.args[1].endswith('/openapi/assets/search/structured?planType=LITE'))
                wire = transport.call_args.kwargs['payload'].decode('utf-8')
                self.assertIn('"fieldId": ' + field_id, wire)
                self.assertEqual(json.loads(wire)['tagConditionList'][0]['fieldId'], int(field_id))
                self.assertIn('"value": [' + option_id + ']', wire)
                self.assertEqual(json.loads(wire)['tagConditionList'][0]['value'], [int(option_id)])
                self.assertNotIn('Black', wire)
                self.assertEqual(original, before)

    def test_enum_labels_and_direct_ids_reach_api_as_integers(self):
        for source, values in (('plan', ['Summer', 'Winter']), ('body', ['Summer', 'Winter']),
                               ('body', [201, 202])):
            condition = {'fieldId': '2', 'value': values}
            supplied = {'tagConditionList': [condition]}
            if source == 'plan':
                condition['sourceText'] = '夏冬'
                supplied = build_structured_search(metadataConditions=[condition])
            before = copy.deepcopy(supplied)
            with self.subTest(source=source, values=values), patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), patch.object(structured_search, 'request', return_value=response({'fileList': []})) as post:
                result = structured_search.execute({'operation': 'structured_search', source: supplied})
                self.assertEqual(post.call_args.kwargs['body']['tagConditionList'], [{'fieldId': 2, 'value': [201, 202]}])
                self.assertEqual(supplied, before)
                self.assertEqual(result['data']['fileList'], [])
                post.assert_called_once()

    def test_bad_enum_catalog_or_value_blocks_post(self):
        bad_options = [
            [{'value': 'Black'}], [{'id': True, 'value': 'Black'}],
            [{'id': 1.5, 'value': 'Black'}], [{'id': '9223372036854775808', 'value': 'Black'}],
            [{'id': 101, 'fieldId': '2', 'value': 'Black'}],
            [{'id': 101, 'value': 'Black'}, {'id': 102, 'value': 'Black'}],
            [{'id': 101, 'value': 'Black'}, {'id': 101, 'value': 'White'}],
        ]
        for options in bad_options:
            with self.subTest(options=options), patch.object(structured_search, 'fetch_metadata_catalog', return_value=[
                {'id': 1, 'type': 'SINGLE_SELECT', 'enumOptionList': options}
            ]), patch.object(structured_search, 'request') as post:
                with self.assertRaises(BasilError):
                    structured_search.execute({'operation': 'structured_search', 'plan': plan()})
                post.assert_not_called()
        for field_id, value in (('1', True), ('1', 101.0), ('1', 201), ('1', 999), ('3', 101)):
            with self.subTest(field_id=field_id, value=value), patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), patch.object(structured_search, 'request') as post:
                with self.assertRaises(BasilError):
                    structured_search.execute({'operation': 'structured_search', 'body': {
                        'tagConditionList': [{'fieldId': field_id, 'value': [value]}]}})
                post.assert_not_called()

    def test_numeric_label_is_resolved_as_label_and_plan_ids_are_rejected(self):
        catalog = [{'id': 1, 'type': 'SINGLE_SELECT', 'enumOptionList': [{'id': 102, 'value': '101'}]}]
        body = {'tagConditionList': [{'fieldId': '1', 'value': ['101']}]}
        validate_metadata(body, catalog)
        self.assertEqual(body['tagConditionList'][0]['value'], [102])
        with self.assertRaises(BasilError):
            plan_to_body({'metadataConditions': [{'fieldId': '1', 'value': [101], 'sourceText': '黑色'}]})

    def test_subtype_filters_reach_api_and_invalid_pairs_fail(self):
        for field_type in ('MIME_SUB_TYPE', 'DOC_SUB_TYPE'):
            for op in ('EQUALS', 'NOT_EQUALS', 'IN', 'NOT_IN'):
                values = ['code-a'] if op in ('EQUALS', 'NOT_EQUALS') else ['code-a', 'code-b', 'code-c']
                condition = {'fieldType': field_type, 'operator': op, 'value': values}
                with self.subTest(field_type=field_type, op=op), patch.object(structured_search, 'fetch_metadata_catalog', return_value=[]), patch.object(structured_search, 'request', return_value=response({})) as post:
                    structured_search.execute({'operation': 'structured_search', 'plan': {'filterConditions': [condition]}})
                    self.assertEqual(post.call_args.kwargs['body']['filterConditionList'], [condition])
        invalid = [('MIME_SUB_TYPE', 'GT', ['a']), ('DOC_SUB_TYPE', 'BETWEEN', ['a', 'b']),
                   ('DOC_SUB_TYPE', 'EQUALS', ['a', 'b']), ('MIME_SUB_TYPE', 'IN', []),
                   ('FILE_SIZE', 'IN', ['1']), ('METADATA_FIELD_VALUE_TYPE', 'IN', ['101'])]
        for field_type, op, values in invalid:
            with self.subTest(field_type=field_type, op=op), self.assertRaises(BasilError):
                plan_to_body({'filterConditions': [{'fieldType': field_type, 'operator': op, 'value': values}]})

    def test_invalid_int64_ids_fail_before_request(self):
        for value in ('9223372036854775808', '-1', '1.0', '1e3', '１２', '', '9' * 5000):
            with self.subTest(value=value[:30]), patch.object(structured_search, 'request') as post, self.assertRaises(BasilError):
                structured_search.execute({'operation': 'structured_search', 'plan': {
                    'metadataConditions': [{'fieldId': value, 'value': ['Black'], 'sourceText': '黑色'}],
                }})
            post.assert_not_called()


class RefinementTests(unittest.TestCase):
    def test_file_ids_remain_strings_on_wire_and_deduplicate_without_mutation(self):
        condition = {'fieldType': 'FILE_ID', 'operator': 'IN',
                     'value': ['9007199254740993', '00042', '42', '9223372036854775807']}
        for source in ('plan', 'body'):
            supplied = {'filterConditions' if source == 'plan' else 'filterConditionList': [condition]}
            before = copy.deepcopy(supplied)
            with self.subTest(source=source), patch.object(runtime, 'RUNTIME_DOMAIN', 'https://current.test'), \
                 patch.object(runtime, 'auth_headers', return_value={}), \
                 patch.object(structured_search, 'fetch_metadata_catalog', return_value=[]), \
                 patch.object(runtime, '_perform_request', return_value=response({'fileList': []})) as transport:
                structured_search.execute({'operation': 'structured_search', source: supplied})
                wire = json.loads(transport.call_args.kwargs['payload'])
                self.assertEqual(wire['filterConditionList'][0]['value'],
                                 ['9007199254740993', '42', '9223372036854775807'])
                self.assertFalse(wire['enableAI'])
                self.assertEqual(supplied, before)

    def test_invalid_file_id_filters_block_before_catalog_or_post(self):
        invalid_values = [[], [''], [' '], ['-1'], ['1.0'], ['1e3'], ['１２'],
                          ['9223372036854775808'], ['9' * 5000], [1], [True], [1.5], [None]]
        cases = [('IN', v) for v in invalid_values]
        cases += [(op, ['42']) for op in ('NOT_IN', 'EQUALS', 'GT', 'BETWEEN')]
        for source in ('plan', 'body'):
            for operator, values in cases:
                supplied = {'filterConditions' if source == 'plan' else 'filterConditionList': [
                    {'fieldType': 'FILE_ID', 'operator': operator, 'value': values}]}
                with self.subTest(source=source, operator=operator, values=str(values)[:60]), \
                     patch.object(structured_search, 'fetch_metadata_catalog') as fetch, \
                     patch.object(structured_search, 'request') as post, self.assertRaises(BasilError):
                    structured_search.execute({'operation': 'structured_search', source: supplied})
                fetch.assert_not_called()
                post.assert_not_called()
        with self.assertRaises(BasilError):
            plan_to_body({'fileTypeFilter': ['FOLDER'], 'filterConditions': [
                {'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ['42']}]})

    def test_accepted_query_refinement_preserves_metadata_or_and_scope(self):
        accepted = build_structured_search(**{
            **plan(), 'metadataLogic': 'OR', 'page': 3, 'size': 50,
            'spaceType': 'TEAM', 'folderPath': '/Root/Design', 'includeSubfolders': True,
            'fileTypeFilter': ['IMAGE'], 'sortRule': {'previewableTypeOrder': ['IMAGE']},
            'filterConditions': [{'fieldType': 'FILE_SIZE', 'operator': 'GT', 'value': ['100']}],
        })
        accepted['metadataConditions'].append(
            {'fieldId': '2', 'value': ['Summer'], 'sourceText': '夏日'})
        before = copy.deepcopy(accepted)
        # Semantic review stays with the Agent; exercise its resulting plan through
        # the real builder, live validation, conversion, and output boundary.
        refined = build_structured_search(**{
            **accepted, 'keyword': '', 'page': 1,
            'filterConditions': [*accepted['filterConditions'],
                                 {'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ['42', '43']}],
        })
        results = [response({'fileList': [{'id': 99}], 'snapshotLink': 'https://example.test/abandoned'}),
                   response({'fileList': [{'id': 42}, {'id': 43}, {'id': 44}], 'snapshotLink': 'https://example.test/accepted'}),
                   response({'fileList': [{'id': 42}, {'id': 43}], 'snapshotLink': 'https://example.test/refined'})]
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG) as fetch, \
             patch.object(structured_search, 'request', side_effect=results) as post:
            for query in (plan(), accepted, refined):
                result = structured_search.execute({'operation': 'structured_search', 'plan': query})
            self.assertEqual(fetch.call_count, 3)
            body = post.call_args.kwargs['body']
            self.assertEqual(body['tagLogicType'], 'OR')
            self.assertEqual(body['tagConditionList'], [
                {'fieldId': 1, 'value': [101]}, {'fieldId': 2, 'value': [201]}])
            self.assertEqual(body['filterConditionList'], refined['filterConditions'])
            self.assertNotIn('keyword', body)
            self.assertNotIn('sourceText', json.dumps(body))
            for key in ('spaceType', 'folderPath', 'includeSubfolders', 'fileTypeFilter', 'sortRule', 'size'):
                self.assertEqual(body[key], accepted[key])
            self.assertEqual(body['page'], 1)
            self.assertEqual(result['data'], {'snapshotLink': 'https://example.test/refined'})
        self.assertEqual(accepted, before)
        self.assertEqual(refined['metadataConditions'], accepted['metadataConditions'])

    def test_refinement_keeps_live_validation_and_does_not_fall_back(self):
        refined = {**plan(), 'keyword': '', 'filterConditions': [
            {'fieldType': 'FILE_ID', 'operator': 'IN', 'value': ['42']}]}
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=[]), \
             patch.object(structured_search, 'request') as post, self.assertRaises(BasilError):
            structured_search.execute({'operation': 'structured_search', 'plan': refined})
        post.assert_not_called()
        for data in ({'fileList': []}, {'fileList': [{'id': 42}]}):
            with self.subTest(data=data), patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), \
                 patch.object(structured_search, 'request', return_value=response(data)) as post:
                result = structured_search.execute({'operation': 'structured_search', 'plan': refined})
                self.assertEqual(result['data'], data)
                post.assert_called_once()
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), \
             patch.object(structured_search, 'request', side_effect=BasilError('refinement failed')) as post, \
             self.assertRaisesRegex(BasilError, 'refinement failed'):
            structured_search.execute({'operation': 'structured_search', 'plan': refined})
        post.assert_called_once()


class CandidateInspectionTests(unittest.TestCase):
    @staticmethod
    def page(ids, more, **extra):
        return response({'fileList': [{'id': i} for i in ids],
                         'pageInfo': {'hasMore': more}, **extra})

    def inspect(self, query=None, count=3):
        return structured_search.execute({'operation': 'structured_search', 'plan': query or plan(),
                                          'inspectResults': True, 'inspectPages': count})

    def test_batch_reuses_validation_and_stops_at_end_without_changing_query(self):
        pages = [self.page([1], True, snapshotLink='https://example.test/page1'),
                 self.page([1, 2], False, snapshotLink='https://example.test/page2')]
        query = {**plan(), 'size': 2}
        before = copy.deepcopy(query)
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG) as fetch, \
             patch.object(structured_search, 'request', side_effect=pages) as post:
            result = self.inspect(query)
        fetch.assert_called_once()
        self.assertEqual(post.call_count, 2)
        bodies = [call.kwargs['body'] for call in post.call_args_list]
        self.assertEqual(bodies[1], {**bodies[0], 'page': 2})
        self.assertFalse(set(bodies[0]) & {'inspectPages', 'inspectResults'})
        self.assertEqual(result['data']['pages'], [
            {'page': i + 1, 'response': json.loads(raw[0])} for i, raw in enumerate(pages)])
        self.assertTrue(result['data']['complete'])
        self.assertIsNone(result['data']['nextPage'])
        self.assertEqual(query, before)

    def test_limit_and_continuation_never_claim_full_coverage(self):
        for start, more, next_page in ((1, True, 2), (4, True, 5), (4, False, None)):
            with self.subTest(start=start, more=more), \
                 patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), \
                 patch.object(structured_search, 'request', return_value=self.page([42], more)) as post:
                result = self.inspect({**plan(), 'page': start}, count=1)
                self.assertFalse(result['data']['complete'])
                self.assertEqual(result['data']['nextPage'], next_page)
                post.assert_called_once()

    def test_bad_pagination_or_ids_cannot_appear_complete(self):
        invalid = [response({}), response({'pageInfo': {'hasMore': False}}),
                   response({'fileList': []}), self.page([], True), self.page([True], False),
                   self.page(['9223372036854775808'], False), self.page([1], 'false'),
                   response({'fileList': None, 'pageInfo': {'hasMore': False}}),
                   response({'fileList': [{}], 'pageInfo': {'hasMore': False}})]
        for raw in invalid:
            with self.subTest(raw=raw), patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), \
                 patch.object(structured_search, 'request', return_value=raw), self.assertRaises(BasilError):
                self.inspect()
        for last in (self.page([1], True), self.page([1], False)):
            with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), \
                 patch.object(structured_search, 'request', side_effect=[self.page([1], True), last]), \
                 self.assertRaisesRegex(BasilError, 'no progress'):
                self.inspect()

    def test_folder_progress_is_separate_from_file_ids_and_empty_end_is_valid(self):
        pages = [self.page([1], True),
                 response({'folderList': [{'id': 1}], 'pageInfo': {'hasMore': True}}),
                 self.page([], False)]
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), \
             patch.object(structured_search, 'request', side_effect=pages):
            result = self.inspect()
        self.assertTrue(result['data']['complete'])
        self.assertEqual(len(result['data']['pages']), 3)

    def test_later_request_error_does_not_return_partial_success(self):
        with patch.object(structured_search, 'fetch_metadata_catalog', return_value=CATALOG), \
             patch.object(structured_search, 'request', side_effect=[self.page([1], True), BasilError('unavailable')]), \
             self.assertRaisesRegex(BasilError, 'unavailable'):
            self.inspect()

    def test_inspection_controls_fail_before_network(self):
        for inspect, count in ((False, 2), (True, True), (True, 0), (True, 21), (True, None), (True, '2')):
            with self.subTest(inspect=inspect, count=count), \
                 patch.object(structured_search, 'fetch_metadata_catalog') as fetch, \
                 patch.object(structured_search, 'request') as post, self.assertRaises(BasilError):
                structured_search.execute({'operation': 'structured_search', 'plan': plan(),
                                           'inspectResults': inspect, 'inspectPages': count})
            fetch.assert_not_called()
            post.assert_not_called()


class MetadataFieldsTests(unittest.TestCase):
    def run_fields(self, query, result=None):
        payload = {'operation': 'metadata_fields', 'query': query}
        with patch.object(cli, 'read_json_stdin', return_value=payload), patch.object(
            cli, 'print_json'
        ) as output, patch('runtime.openapi.request', return_value=response(
            [] if result is None else result, {'page': 1, 'size': 50, 'total': 0 if result is None else len(result)}
        )) as get:
            cli.run_capability({'metadata_fields'})
        return get, output

    def test_group_filter_and_response_are_preserved(self):
        query = {'page': 1, 'size': 50, 'groupName': '  活动 Campaign  ', 'fieldType': 'SINGLE_SELECT'}
        rows = [{'id': 1, 'groupId': 30001, 'groupName': '活动 Campaign', 'type': 'SINGLE_SELECT'}]
        get, output = self.run_fields(query, rows)
        self.assertEqual(get.call_args.args, ('GET', '/openapi/assets/metadata/field/page'))
        self.assertEqual(get.call_args.kwargs['query'], query)
        self.assertIsNone(get.call_args.kwargs['body'])
        self.assertEqual(output.call_args.args[0]['data'], rows)

    def test_valid_filters_and_empty_pages(self):
        for extra in ({}, {'groupName': 'a' * 100}, {'groupName': '不存在'},
                      {'groupName': '   ', 'ungrouped': True}, {'groupName': '', 'ungrouped': True},
                      {'ungrouped': True}, {'groupName': 'Campaign', 'ungrouped': False},
                      *({'fieldType': t} for t in ('STRING', 'TIME', 'NUMBER'))):
            with self.subTest(extra=extra):
                get, output = self.run_fields({'page': 1, 'size': 50, **extra})
                self.assertNotIn('planType', get.call_args.kwargs['query'])
                self.assertEqual(output.call_args.args[0]['data'], [])
                self.assertEqual(output.call_args.args[0]['addition'], {'page': 1, 'size': 50, 'total': 0})

    def test_invalid_or_removed_filters_fail_before_request(self):
        for extra in ({'groupName': 'a' * 101}, {'groupName': 123},
                      {'groupName': ' Campaign ', 'ungrouped': True}, {'ungrouped': 'true'},
                      {'planType': 'LITE'}, {'planType': 'PRO'}, {'groupId': 30001},
                      {'page': True}, {'size': 1001}, {'fieldType': 'INVALID'},
                      {'sortField': 'id'}, {'sortDirection': 'invalid'}):
            with self.subTest(extra=extra), patch('runtime.openapi.request') as get:
                with self.assertRaises(BasilError):
                    cli._validate_library({'operation': 'metadata_fields', 'query': {'page': 1, 'size': 50, **extra}})
                get.assert_not_called()


class PaginationTests(unittest.TestCase):
    def test_follows_server_size_without_filters(self):
        pages = [response(CATALOG[:2], {'page': 1, 'size': 2, 'total': 3}),
                 response(CATALOG[2:3], {'page': 2, 'size': 2, 'total': 3})]
        with patch.object(metadata_catalog, 'request', side_effect=pages) as get:
            self.assertEqual(metadata_catalog.fetch_metadata_catalog(), CATALOG[:3])
            self.assertEqual(get.call_args_list[1].kwargs['query'], {'page': 2, 'size': 2})

    def test_empty_catalog_is_valid(self):
        with patch.object(metadata_catalog, 'request', return_value=response([], {'page': 1, 'size': 1000, 'total': 0})):
            self.assertEqual(metadata_catalog.fetch_metadata_catalog(), [])

    def test_repeated_page_duplicate_changed_total_or_short_page_fail(self):
        first = response(CATALOG[:2], {'page': 1, 'size': 2, 'total': 3})
        bad_pages = [
            response(CATALOG[2:3], {'page': 1, 'size': 2, 'total': 3}),
            response(CATALOG[:1], {'page': 2, 'size': 2, 'total': 3}),
            response(CATALOG[2:3], {'page': 2, 'size': 2, 'total': 4}),
            response([], {'page': 2, 'size': 2, 'total': 3}),
            response([], None),
        ]
        for second in bad_pages:
            with self.subTest(second=second), patch.object(metadata_catalog, 'request', side_effect=[first, second]):
                with self.assertRaises(BasilError):
                    metadata_catalog.fetch_metadata_catalog()

    def test_backend_failure_propagates(self):
        with patch.object(metadata_catalog, 'request', return_value=(json.dumps({'success': False, 'code': 403, 'message': 'denied'}), 'application/json')):
            with self.assertRaises(BasilError):
                metadata_catalog.fetch_metadata_catalog()


if __name__ == '__main__':
    unittest.main()
