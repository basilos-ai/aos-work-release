"""Offline auth boundaries. Synthetic values only; no provider or host calls."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import runtime
from auth import policy


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        runtime.AUTH_MODE = 'auto'
        runtime.RUNTIME_DOMAIN = 'https://example.invalid'

    def oauth(self, seconds=None, refresh=False):
        os.environ['APP_OAUTH_BASILOS_ACCESS_TOKEN'] = 'synthetic-oauth'
        if seconds is not None:
            os.environ['APP_OAUTH_BASILOS_EXPIRES_AT'] = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
        if refresh:
            os.environ['APP_OAUTH_BASILOS_REFRESH_TOKEN'] = 'synthetic-refresh'

    def test_special_card_and_static_binding_are_exact(self):
        card = runtime.oauth_card_action()['arguments']
        self.assertEqual(card['authorization'], {'type': 'app_oauth', 'appKey': 'library'})
        self.assertEqual(card['fields'], [])
        self.assertNotIn('credentialKey', card)
        form = runtime.personal_token_action(explicit_request=True)['arguments']
        self.assertEqual(form['credentialKey'], 'app.basilos.personal-token')
        self.assertEqual(form['fields'][0]['environmentName'], 'APP_BASILOS_PERSONAL_TOKEN')
        self.assertTrue(form['fields'][0]['secret'])
        self.assertIn('https://example.invalid/library', form['description'])

    def test_collection_requires_explicit_request_even_when_mode_is_pinned(self):
        runtime.AUTH_MODE = 'personal_token'
        self.assertNotIn('next_action', runtime.status())
        with self.assertRaises(runtime.BasilError):
            runtime.personal_token_action()
        with self.assertRaises(runtime.BasilError):
            runtime.personal_token_action(explicit_request='true')

    def test_replacement_budget(self):
        self.assertEqual(runtime.personal_token_action(explicit_request=True, replacement=True, replacement_attempts=0)['tool'], 'request_user_input')
        with self.assertRaises(runtime.BasilError):
            runtime.personal_token_action(explicit_request=True, replacement=True, replacement_attempts=1)
        with self.assertRaises(runtime.BasilError):
            runtime.personal_token_action(explicit_request=True, replacement_attempts=True)

    def test_oauth_preferred_and_existing_static_reused_only_initially(self):
        os.environ['APP_BASILOS_PERSONAL_TOKEN'] = 'synthetic-static'
        self.assertEqual(runtime.status()['auth_mode'], 'personal_token')
        self.oauth()
        self.assertEqual(runtime.auth_headers(), {'Authorization': 'Bearer synthetic-oauth'})
        runtime.AUTH_MODE = 'personal_token'
        self.assertEqual(runtime.auth_headers(), {'auth-token': 'synthetic-static'})

    def test_expiring_and_expired_grants_prefer_refresh_over_static(self):
        os.environ['APP_BASILOS_PERSONAL_TOKEN'] = 'synthetic-static'
        for remaining in (30, -30):
            self.oauth(remaining, refresh=True)
            result = runtime.status()
            self.assertEqual(result['auth_mode'], 'oauth2')
            self.assertFalse(result['configured'])
            self.assertTrue(result['managed_refresh_required'])
            self.assertFalse(result['managed_refresh_adapter_verified'])
            with self.assertRaises(runtime.BasilError):
                runtime.auth_headers()

    def test_refresh_only_and_new_injection(self):
        os.environ['APP_OAUTH_BASILOS_REFRESH_TOKEN'] = 'synthetic-refresh'
        self.assertEqual(runtime.status()['state'], 'refresh_only')
        self.assertTrue(runtime.status()['managed_refresh_required'])
        self.oauth(300, refresh=True)
        self.assertTrue(runtime.status()['configured'])
        self.assertFalse(runtime.status()['verified'])

    def test_expiring_without_refresh_remains_valid_until_expiry(self):
        self.oauth(30)
        self.assertTrue(runtime.status()['configured'])
        self.oauth(-30)
        self.assertFalse(runtime.status()['configured'])

    def test_invalid_metadata_does_not_fallback_or_send(self):
        self.oauth()
        os.environ['APP_BASILOS_PERSONAL_TOKEN'] = 'synthetic-static'
        for value in ('invalid', '2026-01-01T00:00:00'):
            os.environ['APP_OAUTH_BASILOS_EXPIRES_AT'] = value
            self.assertEqual(runtime.status()['state'], 'invalid_expiry')
            with patch.object(runtime, '_perform_request') as wire:
                with self.assertRaises(runtime.BasilError):
                    runtime.verify()
                wire.assert_not_called()

    def test_read_only_verification_does_not_expose_unneeded_fields(self):
        self.oauth()
        raw = json.dumps({'success': True, 'code': 0, 'data': {'id': '7', 'username': 'fixture', 'password': 'excluded', 'email': 'excluded'}})
        with patch.object(runtime, '_perform_request', return_value=(raw, 'application/json')) as wire:
            result = runtime.verify()
        self.assertEqual(wire.call_args.args[:2], ('GET', 'https://example.invalid/typekey/api/v1/user/readAuthCurrentUser'))
        self.assertEqual(result['user'], {'id': '7', 'username': 'fixture'})
        self.assertTrue(result['verified'])

    def test_null_identity_is_not_verified(self):
        self.oauth()
        raw = json.dumps({'success': True, 'code': 0, 'data': None})
        with patch.object(runtime, '_perform_request', return_value=(raw, 'application/json')):
            with self.assertRaises(runtime.BasilError):
                runtime.verify()

    def test_status_and_redaction_do_not_leak_credentials(self):
        self.oauth(refresh=True)
        os.environ['APP_BASILOS_PERSONAL_TOKEN'] = 'synthetic-static'
        text = json.dumps(runtime.status())
        for value in ('synthetic-oauth', 'synthetic-refresh', 'synthetic-static'):
            self.assertNotIn(value, text)
            self.assertEqual(runtime._redact(value), '[REDACTED]')

    def test_api_key_alias_and_domain_reset(self):
        with patch('sys.stdin', io.StringIO('{"_authMode":"api_key","_runtimeDomain":"https://example.invalid"}')):
            self.assertEqual(runtime.read_json_stdin(), {})
        self.assertEqual(runtime.AUTH_MODE, 'personal_token')
        with patch('sys.stdin', io.StringIO('{}')):
            runtime.read_json_stdin()
        self.assertIsNone(runtime.RUNTIME_DOMAIN)
        self.assertEqual(runtime.AUTH_MODE, 'auto')

    def test_invalid_domain_fails_before_network(self):
        self.oauth()
        for domain in ('http://example.invalid', 'https://user:pass@example.invalid', 'https://example.invalid/path', 'https://example.invalid?x=1'):
            with self.assertRaises(runtime.BasilError):
                runtime.runtime_origin(domain)

    def test_helper_rejects_secret_inputs_and_reports_no_dispatch(self):
        env = {'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1'}
        cmd = [sys.executable, 'scripts/auth/recovery.py']
        for payload in ({'refresh_token': 'synthetic-do-not-echo'}, {'state': 'expired', 'refresh_capability': 'available'}):
            result = subprocess.run(cmd, cwd=ROOT, env=env, input=json.dumps(payload), text=True, capture_output=True)
            self.assertNotIn('synthetic-do-not-echo', result.stdout)
            value = json.loads(result.stdout)
            if 'refresh_token' in payload:
                self.assertEqual(result.returncode, 1)
            else:
                self.assertEqual(result.returncode, 0)
                self.assertEqual(value['action'], 'managed_refresh')
                self.assertFalse(value['dispatched'])


class RecoveryTests(unittest.TestCase):
    def decide(self, state, **kwargs):
        return policy.oauth_decision(state, refresh_capability='available', **kwargs).action

    def test_refresh_first_and_host_unknown(self):
        for state in ('expired', 'expiring', 'invalid_token', 'missing'):
            self.assertEqual(self.decide(state), 'managed_refresh')
        self.assertEqual(policy.oauth_decision('expired', refresh_capability='unknown').action, 'blocked')
        self.assertEqual(policy.oauth_decision('expired', refresh_capability='unavailable').action, 'authorization_card')

    def test_transient_unknown_and_revoked_are_distinct(self):
        for state, expected in [('temporary_error', 'retry_later'), ('refresh_unknown', 'reconcile'), ('refresh_rejected', 'authorization_card'), ('permission_error', 'blocked'), ('injection_pending', 'resume')]:
            self.assertEqual(self.decide(state), expected)

    def test_refused_card_stops_and_budgets_survive_resume(self):
        for state in ('declined', 'skipped', 'timed_out', 'authorization_failed'):
            self.assertEqual(self.decide(state), 'stop')
        self.assertEqual(self.decide('invalid_token', refresh_attempts=1), 'stop')
        self.assertEqual(self.decide('refresh_rejected', reauth_attempts=1), 'stop')
        self.assertEqual(policy.oauth_decision('missing', refresh_capability='unavailable', initial_card_attempts=1).action, 'blocked')

    def test_refresh_does_not_authorize_unknown_write_replay(self):
        self.assertFalse(policy.may_retry_business(credential_verified=True, safe_read=False, retries=0))
        self.assertTrue(policy.may_retry_business(credential_verified=True, safe_read=True, retries=0))
        self.assertFalse(policy.may_retry_business(credential_verified=True, safe_read=True, retries=1))


if __name__ == '__main__':
    unittest.main()
