"""Explicit Library contracts and version handoff; no remote mutations."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from library import cli
from runtime import BasilError
from runtime.openapi import execute_operation

OK = ('{"success":true,"code":0,"data":{}}', 'application/json')


class MutationContractsTests(unittest.TestCase):
    def test_file_batch_cannot_override_lite(self):
        for value in ('PRO', None, [], {}):
            with self.subTest(value=value), patch('runtime.openapi.request') as network:
                with self.assertRaises(BasilError):
                    cli._validate_library({'operation': 'file_batch', 'query': {'planType': value}})
                network.assert_not_called()
        cli._validate_library({'operation': 'file_batch'})
        cli._validate_library({'operation': 'file_batch', 'query': {'planType': 'LITE'}})

    def test_versions_are_required_and_sent_unchanged_without_retry(self):
        for name, operation in cli.OPERATIONS.items():
            versions = [key for key in operation.required_body if 'version' in key.lower()]
            if not versions:
                continue
            body = {key: '1' for key in operation.required_body}
            body.update({key: 7 + index for index, key in enumerate(versions)})
            payload = {'operation': name, 'body': body, '_confirm': True, '_target': 'fixture'}
            for key in versions:
                for null_value in (False, True):
                    incomplete = {k: v for k, v in body.items() if k != key}
                    if null_value:
                        incomplete[key] = None
                    with self.subTest(operation=name, field=key, null=null_value), patch('runtime.openapi.request') as network:
                        with self.assertRaises(BasilError):
                            execute_operation({**payload, 'body': incomplete}, cli.OPERATIONS)
                        network.assert_not_called()
            with patch('runtime.openapi.request', return_value=OK) as network:
                execute_operation(payload, cli.OPERATIONS)
                self.assertEqual(network.call_args.kwargs['body'], body)
            with patch('runtime.openapi.request', side_effect=BasilError('version conflict')) as network:
                with self.assertRaises(BasilError):
                    execute_operation(payload, cli.OPERATIONS)
                network.assert_called_once()

    def test_folder_create_preserves_large_parent_id_and_explicit_zero_version(self):
        body = {'parentId': '2089982124722622490', 'name': '0923-14:57', 'parentVersion': 0}
        payload = {'operation': 'folder_create', 'body': body, '_confirm': True}
        with patch('runtime.openapi.request', return_value=OK) as network:
            cli._validate_library(payload)
            execute_operation(payload, cli.OPERATIONS)
        self.assertEqual(network.call_args.args, ('PUT', '/openapi/assets/folder/save'))
        self.assertEqual(network.call_args.kwargs['body'], body)
        self.assertIsInstance(network.call_args.kwargs['body']['parentId'], str)

    def test_upload_guard_precedes_file_read(self):
        with patch.object(cli, '_multipart_file') as read:
            for value in (None, False, 'true', 1):
                with self.assertRaises(BasilError):
                    cli._upload({'operation': 'file_upload', '_confirm': value})
            read.assert_not_called()

    def test_invalid_enum_containers_are_domain_errors(self):
        for query in ({'spaceType': []}, {'page': 1, 'size': 10, 'fieldType': {}},
                      {'page': 1, 'size': 10, 'sortField': []}):
            with self.assertRaises(BasilError):
                cli._validate_library({'operation': 'metadata_fields', 'query': query})


if __name__ == '__main__':
    unittest.main()
