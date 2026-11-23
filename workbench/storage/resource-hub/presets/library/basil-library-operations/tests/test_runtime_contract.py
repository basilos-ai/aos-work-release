"""Offline entrypoint and operation guard invariants."""
import io
import json
import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import runtime
from runtime import BasilError
from runtime.openapi import execute_operation
from library import cli


class RuntimeContractTests(TestCase):
    def test_nonstring_operations_return_controlled_errors(self):
        for operation in (None, [], {}, True, 1):
            with self.subTest(operation=operation), patch.object(sys, 'stdin', io.StringIO(json.dumps({'operation': operation}))), patch.object(sys, 'stdout', new_callable=io.StringIO) as output, patch.object(sys, 'argv', ['script']), patch.object(runtime, '_perform_request') as network:
                code = runtime.run_script(cli.main)
                self.assertEqual(code, 1)
                self.assertFalse(json.loads(output.getvalue())['success'])
                network.assert_not_called()

    def test_invalid_timeouts_fail_before_transport(self):
        for timeout in (True, 0, -1, None, '30', float('nan'), float('inf')):
            with self.subTest(timeout=timeout), patch.object(runtime, '_perform_request') as network:
                with self.assertRaises(BasilError):
                    runtime.request('GET', '/openapi/base/page', timeout=timeout)
                network.assert_not_called()

    def test_all_catalog_mutations_require_confirmation_and_delete_target(self):
        for name, operation in cli.OPERATIONS.items():
            if not operation.mutating:
                continue
            payload = {'operation': name,
                       'path': {key: '1' for key in operation.required_path},
                       'query': {key: '1' for key in operation.required_query}}
            if operation.body_kind == 'object':
                payload['body'] = {key: '1' for key in operation.required_body}
            with self.subTest(operation=name), patch('runtime.openapi.request', return_value=('{"success":true,"code":0,"data":{}}', 'application/json')) as network:
                for confirmation in (None, False, 'true', 1):
                    with self.assertRaises(BasilError):
                        execute_operation({**payload, '_confirm': confirmation}, cli.OPERATIONS)
                network.assert_not_called()
                payload['_confirm'] = True
                if operation.destructive:
                    for target in (None, '', ' ', 1):
                        with self.assertRaises(BasilError):
                            execute_operation({**payload, '_target': target}, cli.OPERATIONS)
                    network.assert_not_called()
                    payload['_target'] = 'Confirmed fixture resource'
                execute_operation(payload, cli.OPERATIONS)
                network.assert_called_once()


if __name__ == '__main__':
    main()
