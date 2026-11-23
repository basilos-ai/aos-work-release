"""Reject invalid documented batch shapes before sending a write."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from base import cli
from runtime import BasilError


class MutationContractsTests(unittest.TestCase):
    def dispatch(self, payload):
        with patch.object(cli, 'read_json_stdin', return_value=payload), patch.object(sys, 'argv', ['records.py']), patch.object(cli, 'print_json'):
            cli.run_capability()

    def test_batch_collections_must_be_nonempty_arrays(self):
        for operation, field in (('record_batch_update', 'records'), ('record_batch_delete', 'recordIds')):
            for value in (None, [], {}, 'records', 1, True):
                with self.subTest(operation=operation, value=value), patch('runtime.openapi.request') as network:
                    with self.assertRaises(BasilError):
                        self.dispatch({'operation': operation, 'body': {'tableId': '1', field: value}, '_confirm': True, '_target': 'fixture'})
                    network.assert_not_called()

    def test_batch_update_items_require_record_and_fields(self):
        for row in (None, [], 'row', {}, {'recordId': 'r'}, {'recordId': 'r', 'fields': []}):
            with self.subTest(row=row), patch('runtime.openapi.request') as network:
                with self.assertRaises(BasilError):
                    self.dispatch({'operation': 'record_batch_update', 'body': {'tableId': '1', 'records': [row]}, '_confirm': True})
                network.assert_not_called()

    def test_valid_batch_update_preserves_user_fields(self):
        records = [{'recordId': 'r', 'fields': {'tableId': 'user text', 'price': 12}}]
        with patch('runtime.openapi.request', return_value=('{"success":true,"code":0}', 'application/json')) as network:
            self.dispatch({'operation': 'record_batch_update', 'body': {'tableId': '1', 'records': records}, '_confirm': True})
        self.assertEqual(network.call_args.kwargs['body'], {'tableId': 1, 'records': records})

    def test_enum_containers_are_controlled_errors(self):
        for operation in ('field_create', 'view_create'):
            with self.assertRaises(BasilError):
                cli._validate_base({'operation': operation, 'body': {'type': []}})


if __name__ == '__main__':
    unittest.main()
