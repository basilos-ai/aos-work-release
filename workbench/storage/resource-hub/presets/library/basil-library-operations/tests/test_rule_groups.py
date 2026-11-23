"""Rule Group wire contracts and transport safety; no live service."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import runtime
from library import rule_groups as rules

ID = '2043983195929710592'
FIELD = '2043982949296246784'
BODY = {'name': '发票自动打标', 'conditionGroupList': [
    {'logicType': 'AND', 'conditionList': [
        {'fieldType': 'FOLDER', 'operator': 'IN', 'value': [ID]}], 'childGroupList': []}],
    'metadataFieldIdList': [FIELD]}
OK = ('{"success":true,"code":0,"data":true}', 'application/json')


class RuleGroupsTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'APP_OAUTH_BASILOS_ACCESS_TOKEN': 'fixture-token'}, clear=True)
        env.start()
        domain = patch.object(runtime, 'RUNTIME_DOMAIN', 'https://fixture.invalid')
        domain.start()
        self.addCleanup(env.stop)
        self.addCleanup(domain.stop)

    def test_all_routes_and_exact_wire_encoding(self):
        cases = [
            ({'operation': 'pageRuleGroup', 'query': {'page': 1, 'size': 10, 'name': '发票'}}, 'GET', '/page', None),
            ({'operation': 'getRuleGroupDetail', 'path': {'id': ID}}, 'GET', '/' + ID, None),
            ({'operation': 'saveRuleGroup', 'body': BODY, '_confirm': True}, 'POST', '/save', BODY),
            ({'operation': 'updateRuleGroup', 'body': {**BODY, 'id': ID}, '_confirm': True}, 'PUT', '/update', {**BODY, 'id': ID}),
            ({'operation': 'deleteBatchRuleGroup', 'query': {'idList': [ID, FIELD]}, '_confirm': True, '_target': 'two inspected groups'}, 'DELETE', '/deleteBatch', None),
        ]
        for payload, method, suffix, body in cases:
            with self.subTest(operation=payload['operation']), patch.object(runtime, '_perform_request', return_value=OK) as network:
                self.assertTrue(rules.execute(copy.deepcopy(payload))['success'])
                network.assert_called_once()
                args, kwargs = network.call_args
                self.assertEqual(args[0], method)
                url = urlsplit(args[1])
                self.assertEqual(url.netloc, 'fixture.invalid')
                self.assertEqual(url.path, '/typekey/api/v1/assets/rule/group' + suffix)
                self.assertEqual(json.loads(kwargs['payload']) if kwargs['payload'] else None, body)
                self.assertEqual(kwargs['headers']['Authorization'], 'Bearer fixture-token')
                self.assertNotIn('auth-token', kwargs['headers'])
                if method == 'DELETE':
                    self.assertEqual(parse_qs(url.query), {'idList': [ID, FIELD]})
                if suffix == '/page':
                    self.assertEqual(parse_qs(url.query), {'page': ['1'], 'size': ['10'], 'name': ['发票']})

    def test_invalid_inputs_and_guards_never_send(self):
        invalid = [
            {'operation': 'pageRuleGroup', 'query': {'page': True, 'size': 10}},
            {'operation': 'pageRuleGroup', 'query': {'page': 1, 'size': 1001}},
            {'operation': 'pageRuleGroup', 'query': {'page': 1, 'size': 10, 'sortField': []}},
            {'operation': 'getRuleGroupDetail', 'path': {'id': int(ID)}},
            {'operation': 'getRuleGroupDetail', 'path': {'id': '../save'}},
            {'operation': 'saveRuleGroup', 'body': BODY},
            {'operation': 'saveRuleGroup', 'body': BODY, '_confirm': 1},
            {'operation': 'updateRuleGroup', 'body': {'id': ID, 'name': 'rename'}, '_confirm': True},
            {'operation': 'updateRuleGroup', 'body': {**BODY, 'id': ID, 'metadataFieldIdList': None}, '_confirm': True},
            {'operation': 'deleteBatchRuleGroup', 'query': {'idList': []}, '_confirm': True, '_target': 'all'},
            {'operation': 'deleteBatchRuleGroup', 'query': {'idList': [ID]}, '_confirm': True},
            {'operation': 'deleteBatchRuleGroup', 'query': {'idList': [ID]}, 'body': [ID], '_confirm': True, '_target': 'one'},
        ]
        for changes in ({'metadataFieldIdList': []}, {'metadataFieldIdList': [int(FIELD)]},
                        {'name': ' '}, {'folderNameMap': {}}, {'id': ID}, {'conditionGroupList': [{}]}):
            invalid.append({'operation': 'saveRuleGroup', 'body': {**BODY, **changes}, '_confirm': True})
        for changes in ({'fieldType': 'METADATA_FIELD'}, {'operator': 'EQUALS'}, {'value': [123]},
                        {'value': 'PDF'}, {'value': []}, {'id': ID}):
            body = copy.deepcopy(BODY)
            body['conditionGroupList'][0]['conditionList'][0].update(changes)
            invalid.append({'operation': 'saveRuleGroup', 'body': body, '_confirm': True})
        for payload in invalid:
            with self.subTest(payload=payload), patch.object(runtime, '_perform_request') as network:
                with self.assertRaises(runtime.BasilError):
                    rules.execute(payload)
                network.assert_not_called()

    def test_nested_update_preserves_ids_arrays_and_explicit_clears(self):
        body = copy.deepcopy(BODY)
        body.update(id=ID, description='', prompt=None)
        group = body['conditionGroupList'][0]
        group.update(id=FIELD, parentId='0')
        group['conditionList'][0]['id'] = ID
        group['childGroupList'] = [{'logicType': 'OR', 'conditionList': [
            {'fieldType': 'FILE_TYPE', 'operator': 'NOT_IN', 'value': ['PDF']}]}]
        for update in (body, {'id': ID, 'conditionGroupList': [], 'metadataFieldIdList': []}):
            with patch.object(runtime, '_perform_request', return_value=OK) as network:
                rules.execute({'operation': 'updateRuleGroup', 'body': update, '_confirm': True})
                self.assertEqual(json.loads(network.call_args.kwargs['payload']), update)

    def test_depth_boundary(self):
        group = copy.deepcopy(BODY['conditionGroupList'][0])
        for _ in range(15):
            group = {'logicType': 'AND', 'childGroupList': [group]}
        payload = {'operation': 'saveRuleGroup', 'body': {**BODY, 'conditionGroupList': [group]}, '_confirm': True}
        with patch.object(runtime, '_perform_request', return_value=OK) as network:
            rules.execute(payload)
            network.assert_called_once()
        payload['body']['conditionGroupList'] = [{'logicType': 'OR', 'childGroupList': [group]}]
        with patch.object(runtime, '_perform_request') as network:
            with self.assertRaises(runtime.BasilError):
                rules.execute(payload)
            network.assert_not_called()

    def test_failure_never_replays_and_business_success_is_required(self):
        payload = {'operation': 'saveRuleGroup', 'body': BODY, '_confirm': True}
        for response in ('{"success":false,"code":0,"data":true}',
                         '{"success":true,"code":1002,"data":true}',
                         '{"success":true,"code":0,"data":{}}', 'invalid'):
            with patch.object(runtime, '_perform_request', return_value=(response, 'application/json')) as network:
                with self.assertRaises(runtime.BasilError):
                    rules.execute(payload)
                network.assert_called_once()
        with patch.object(runtime, '_perform_request', side_effect=TimeoutError) as network:
            with self.assertRaises(runtime.BasilError):
                rules.execute(payload)
            network.assert_called_once()

    def test_non_openapi_allowlist_and_domain_remain_closed(self):
        for method, path in (('GET', '/assets/rule/group/save'), ('POST', '/assets/rule/group/page'),
                             ('DELETE', '/assets/rule/group/' + ID), ('GET', '/assets/other'),
                             ('GET', '/assets/rule/group/1?x=1'), ('GET', '/assets/rule/group/%31')):
            with self.subTest(path=path), patch.object(runtime, '_perform_request') as network:
                with self.assertRaises(runtime.BasilError):
                    runtime.request(method, path)
                network.assert_not_called()
        with patch.object(runtime, 'RUNTIME_DOMAIN', None), patch.object(runtime, '_perform_request') as network:
            with self.assertRaises(runtime.BasilError):
                rules.execute({'operation': 'getRuleGroupDetail', 'path': {'id': ID}})
            network.assert_not_called()


if __name__ == '__main__':
    unittest.main()
