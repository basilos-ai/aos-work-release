"""Sanitized HTTP diagnostics through real request and script error boundaries."""
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import runtime


class HttpDiagnosticsTests(unittest.TestCase):
    def execute(self, raw, status=400):
        error = HTTPError('https://example.test', status, 'rejected', {}, io.BytesIO(raw))
        with patch.dict(os.environ, {runtime.PERSONAL_TOKEN_ENV: 'private-token'}, clear=True), \
             patch.object(runtime, 'AUTH_MODE', 'personal_token'), \
             patch.object(runtime, 'service_api_base', return_value='https://example.test/typekey/api/v1'), \
             patch.object(runtime, '_perform_request', side_effect=error) as network, \
             patch.object(sys, 'argv', ['script']), \
             patch.object(sys, 'stdout', new_callable=io.StringIO) as output:
            result = runtime.run_script(lambda: runtime.request('POST', '/openapi/assets/file/metadata/operate', body={}))
        self.assertEqual(result, 1)
        network.assert_called_once()
        return json.loads(output.getvalue())

    def test_safe_business_fields_reach_output_without_secrets(self):
        result = self.execute(json.dumps({
            'success': False, 'code': 'FIELD_NOT_FOUND', 'message': 'Unknown field private-token Bearer other-secret https://example.test/?sig=secret',
            'errorKey': 'field.notFound', 'traceId': 'trace-123',
            'data': {'secret': 'never-echo'}, 'stack': 'never-echo'
        }).encode())
        self.assertEqual(result['error'], 'Basil request failed with HTTP 400')
        self.assertEqual(result['details']['code'], 'FIELD_NOT_FOUND')
        self.assertEqual(result['details']['traceId'], 'trace-123')
        for secret in ('private-token', 'other-secret', 'sig=secret', 'never-echo'):
            self.assertNotIn(secret, json.dumps(result))

    def test_nonbusiness_and_oversized_bodies_are_not_exposed(self):
        for raw in (b'<html>secret</html>', b'{bad json', b'[]', b'x' * 17000,
                    b'{"message":"secret"}'):
            with self.subTest(raw=raw[:30]):
                self.assertEqual(self.execute(raw)['details'], {'httpStatus': 400})

    def test_existing_auth_recovery_is_unchanged(self):
        result = self.execute(b'{"success":false,"message":"secret"}', status=401)
        self.assertIn('next_action', result)
        self.assertNotIn('details', result)


if __name__ == '__main__':
    unittest.main()
