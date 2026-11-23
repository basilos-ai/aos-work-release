"""Offline regression tests for Workbench-managed App OAuth2 credentials."""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request
import urllib.response
from email.message import Message

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import runtime
PREFIX = "APP_OAUTH_BASILOS"
ACCESS = "fixture-access-secret"
REFRESH = "fixture-refresh-secret"
ENV = {f"{PREFIX}_ACCESS_TOKEN": ACCESS, f"{PREFIX}_REFRESH_TOKEN": REFRESH}
ENDPOINT = "/openapi/assets/folder/tree"


class EnvironmentCredentialTests(unittest.TestCase):
    def test_personal_token_selection_and_oauth_priority(self):
        with patch.dict(os.environ, {runtime.PERSONAL_TOKEN_ENV: "fixture-personal"}, clear=True):
            self.assertEqual(runtime.auth_headers(), {"auth-token": "fixture-personal"})
            status = runtime.authorization_status()
            self.assertTrue(status["configured"])
            self.assertFalse(status["oauth2_usable"])
            self.assertEqual(status["auth_mode"], "personal_token")
            with patch.dict(os.environ, ENV):
                self.assertEqual(runtime.auth_headers(), {"Authorization": f"Bearer {ACCESS}"})
                with patch.object(runtime, "AUTH_MODE", "personal_token"):
                    self.assertEqual(runtime.auth_headers(), {"auth-token": "fixture-personal"})

    def test_personal_form_missing_and_401_use_same_contract(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(runtime, "AUTH_MODE", "personal_token"):
            form = runtime.authorization_status()["next_action"]
            args = form["arguments"]
            self.assertEqual(form["tool"], "request_user_input")
            self.assertEqual(args["credentialKey"], "app.basilos.personal-token")
            self.assertEqual(args["fields"], [{
                "name": "personal_token", "label": "BasilOS Personal Token",
                "type": "password", "secret": True, "required": True,
                "environmentName": "APP_BASILOS_PERSONAL_TOKEN",
            }])
            for phrase in ("Library platform", "Library account", "bottom-left", "Personal token", "secure field below"):
                self.assertIn(phrase, args["description"])
            with patch.dict(os.environ, {runtime.PERSONAL_TOKEN_ENV: "fixture-personal"}), patch.object(
                runtime, "_perform_request", side_effect=urllib.error.HTTPError(
                    "https://example.test", 401, "denied", {}, io.BytesIO(b""))
            ) as network:
                with self.assertRaises(runtime.BasilError) as caught:
                    runtime.request("GET", ENDPOINT)
                self.assertEqual(caught.exception.next_action, form)
                network.assert_called_once()

    def test_auto_missing_or_invalid_credentials_do_not_offer_personal_form(self):
        cases = [
            ({}, "missing_access_token"),
            ({runtime.PERSONAL_TOKEN_ENV: "bad token"}, "invalid_personal_token"),
            ({f"{PREFIX}_ACCESS_TOKEN": ACCESS, f"{PREFIX}_EXPIRES_AT": "2000-01-01T00:00:00Z"}, "expired"),
        ]
        with patch.object(runtime, "AUTH_MODE", "auto"):
            for env, state in cases:
                with self.subTest(state=state), patch.dict(os.environ, env, clear=True), patch.object(runtime, "_perform_request") as network:
                    status = runtime.authorization_status()
                    self.assertEqual(status["state"], state)
                    self.assertFalse(status["configured"])
                    self.assertNotIn("next_action", status)
                    with self.assertRaises(runtime.BasilError) as caught:
                        runtime.request("GET", ENDPOINT)
                    self.assertIsNone(caught.exception.next_action)
                    self.assertIn(runtime.REAUTHORIZE, str(caught.exception))
                    network.assert_not_called()

    def test_explicit_personal_mode_offers_form_for_invalid_token(self):
        with patch.dict(os.environ, {runtime.PERSONAL_TOKEN_ENV: "bad token"}, clear=True), patch.object(runtime, "AUTH_MODE", "personal_token"):
            form = runtime.personal_token_action()
            self.assertEqual(runtime.authorization_status()["next_action"], form)
            with patch.object(runtime, "_perform_request") as network:
                with self.assertRaises(runtime.BasilError) as caught:
                    runtime.request("GET", ENDPOINT)
                self.assertEqual(caught.exception.next_action, form)
                network.assert_not_called()

    def test_auto_401_never_collects_personal_token_or_replays_request(self):
        for oauth_present in (False, True):
            env = {runtime.PERSONAL_TOKEN_ENV: "fixture-personal"}
            if oauth_present:
                env.update(ENV)
            with self.subTest(oauth_present=oauth_present), patch.dict(os.environ, env, clear=True), patch.object(runtime, "AUTH_MODE", "auto"), patch.object(
                runtime, "_perform_request", side_effect=urllib.error.HTTPError(
                    "https://example.test", 401, "denied", {}, io.BytesIO(b""))
            ) as network:
                with self.assertRaises(runtime.BasilError) as caught:
                    runtime.request("PUT", ENDPOINT, body={"name": "test"})
                self.assertIsNone(caught.exception.next_action)
                self.assertIn(runtime.REAUTHORIZE, str(caught.exception))
                network.assert_called_once()
                headers = network.call_args.kwargs["headers"]
                if oauth_present:
                    self.assertEqual(headers["Authorization"], f"Bearer {ACCESS}")
                    self.assertNotIn("auth-token", headers)
                else:
                    self.assertEqual(headers["auth-token"], "fixture-personal")
                    self.assertNotIn("Authorization", headers)

    def test_personal_errors_do_not_request_unrelated_replacement(self):
        with patch.dict(os.environ, {runtime.PERSONAL_TOKEN_ENV: "fixture-personal"}, clear=True):
            for error in (urllib.error.URLError("offline"), *(
                urllib.error.HTTPError("https://example.test", code, "error", {}, io.BytesIO(b""))
                for code in (403, 429)
            )):
                with self.subTest(error=type(error)), patch.object(runtime, "_perform_request", side_effect=error):
                    with self.assertRaises(runtime.BasilError) as caught:
                        runtime.request("GET", ENDPOINT)
                    self.assertIsNone(caught.exception.next_action)
            self.assertNotIn("fixture-personal", runtime._redact("fixture-personal"))

    def test_auth_mode_is_consumed_without_reading_secrets_from_input(self):
        with patch.object(runtime.sys, "stdin", io.StringIO('{"_authMode":"personal_token","operation":"read"}')):
            try:
                self.assertEqual(runtime.read_json_stdin(), {"operation": "read"})
                self.assertEqual(runtime.AUTH_MODE, "personal_token")
            finally:
                runtime.AUTH_MODE = "auto"

    def setUp(self):
        domain = patch.object(runtime, "RUNTIME_DOMAIN", "https://current.test")
        domain.start()
        self.addCleanup(domain.stop)
        self.env = patch.dict(os.environ, ENV, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_access_token_without_optional_metadata_is_usable(self):
        with patch.dict(os.environ, {f"{PREFIX}_ACCESS_TOKEN": ACCESS}, clear=True):
            status = runtime.authorization_status()
            self.assertTrue(status["configured"])
            self.assertFalse(status["refresh_token_present"])
            self.assertFalse(status["verified"])
            self.assertEqual(runtime.auth_headers(), {"Authorization": f"Bearer {ACCESS}"})

    def test_status_does_not_expose_secrets_or_contact_provider(self):
        with patch.object(runtime.urllib.request, "build_opener") as network:
            result = runtime.authorization_status()
        network.assert_not_called()
        encoded = json.dumps(result)
        self.assertNotIn(ACCESS, encoded)
        self.assertNotIn(REFRESH, encoded)
        self.assertEqual(result["source"], "app")
        self.assertEqual(result["provider_key"], "basilos")
        self.assertEqual(result["env_prefix"], PREFIX)

    def test_missing_refresh_only_and_wrong_prefixes_fail_before_network(self):
        cases = [
            ({}, "missing_access_token"),
            ({f"{PREFIX}_REFRESH_TOKEN": REFRESH}, "refresh_only"),
            ({"CONNECTOR_OAUTH_BASILOS_ACCESS_TOKEN": ACCESS}, "missing_access_token"),
            ({"APP_OAUTH_LIBRARY_ACCESS_TOKEN": ACCESS}, "missing_access_token"),
            ({"APP_OAUTH_MULTIDIMENSIONAL_TABLE_ACCESS_TOKEN": ACCESS}, "missing_access_token"),
            ({"BASILOS_ACCESS_TOKEN": ACCESS}, "missing_access_token"),
            ({f"{PREFIX}_ACCESS_TOKEN": "  ", f"{PREFIX}_REFRESH_TOKEN": REFRESH}, "refresh_only"),
        ]
        for env, expected in cases:
            with self.subTest(expected=expected, keys=list(env)), patch.dict(os.environ, env, clear=True):
                self.assertEqual(runtime.authorization_status()["state"], expected)
                with patch.object(runtime, "_perform_request") as network:
                    with self.assertRaisesRegex(runtime.BasilError, "Workbench"):
                        runtime.request("GET", ENDPOINT)
                    network.assert_not_called()

    def test_invalid_type_expiry_and_header_injection_are_rejected(self):
        for suffix, value, state in [
            ("TOKEN_TYPE", "Basic", "unsupported_token_type"),
            ("EXPIRES_AT", "2000-01-01T00:00:00Z", "expired"),
            ("EXPIRES_AT", "invalid-date", "invalid_expiry"),
            ("EXPIRES_AT", "2099-01-01T00:00:00", "invalid_expiry"),
            ("ACCESS_TOKEN", "bad\r\nInjected: value", "invalid_access_token"),
        ]:
            with self.subTest(state=state), patch.dict(os.environ, {f"{PREFIX}_{suffix}": value}):
                self.assertEqual(runtime.authorization_status()["state"], state)
                with patch.object(runtime, "_perform_request") as network:
                    with self.assertRaises(runtime.BasilError):
                        runtime.request("GET", ENDPOINT)
                    network.assert_not_called()

    def test_future_expiry_and_case_insensitive_bearer(self):
        with patch.dict(os.environ, {
            f"{PREFIX}_EXPIRES_AT": "2099-01-01T08:00:00+08:00",
            f"{PREFIX}_TOKEN_TYPE": "bEaReR",
        }):
            self.assertTrue(runtime.authorization_status()["configured"])
            self.assertEqual(runtime.auth_headers()["Authorization"], f"Bearer {ACCESS}")

    def test_authenticated_json_request_uses_current_session_address_and_single_call(self):
        result = ('{"success":true,"code":0,"data":[]}', "application/json")
        with patch.object(runtime, "_perform_request", return_value=result) as network:
            self.assertEqual(runtime.request("POST", ENDPOINT, query={"q": "a b", "skip": None}, body={"page": 1}), result)
        network.assert_called_once()
        args, kwargs = network.call_args
        self.assertEqual(args, ("POST", runtime.service_api_base() + ENDPOINT + "?q=a+b"))
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {ACCESS}")
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")
        self.assertEqual(json.loads(kwargs["payload"]), {"page": 1})
        self.assertNotIn("auth-token", kwargs["headers"])
        self.assertNotIn(REFRESH, repr(network.call_args))

    def test_multipart_upload_retains_payload_and_bearer_header(self):
        with patch.object(runtime, "_perform_request", return_value=("{}", "application/json")) as network:
            runtime.request("POST", "/openapi/assets/file/upload", raw_body=b"file content", content_type="multipart/form-data; boundary=test")
        self.assertEqual(network.call_args.kwargs["payload"], b"file content")
        self.assertEqual(network.call_args.kwargs["headers"]["Authorization"], f"Bearer {ACCESS}")

    def test_only_attachment_internal_routes_bypass_openapi_prefix(self):
        allowed = (
            "/record/uploadAttachment/init",
            "/record/uploadAttachment/123/chunk/1",
            "/record/uploadAttachment/123/complete",
            "/record/uploadAttachment/123",
        )
        with patch.object(runtime, "_perform_request", return_value=("{}", "application/json")) as network:
            for endpoint in allowed:
                runtime.request("POST", endpoint)
        self.assertEqual(network.call_count, len(allowed))

        rejected = (
            "/record/readRecord",
            "/record/uploadAttachment",
            "/record/uploadAttachment/not-a-token/complete",
            "/record/uploadAttachment/123/chunk/0",
            "/record/uploadAttachment/123/chunk/1/extra",
        )
        for endpoint in rejected:
            with self.subTest(endpoint=endpoint), patch.object(runtime, "_perform_request") as network:
                with self.assertRaisesRegex(runtime.BasilError, "packaged Basil API path"):
                    runtime.request("POST", endpoint)
                network.assert_not_called()

    def test_http_errors_never_retry_refresh_fallback_or_echo_provider_body(self):
        for code, expected in [(401, "request_user_input"), (403, "Scope"), (302, "redirect"), (500, "HTTP 500")]:
            with self.subTest(code=code):
                body = io.BytesIO(f"{ACCESS} {REFRESH}".encode())
                error = urllib.error.HTTPError("http://configured.test", code, "error", {}, body)
                with patch.object(runtime, "_perform_request", side_effect=error) as network:
                    with self.assertRaisesRegex(runtime.BasilError, expected) as result:
                        runtime.request("PUT", ENDPOINT, body={"name": "test"})
                network.assert_called_once()
                self.assertTrue(body.closed)
                self.assertNotIn(ACCESS, str(result.exception))
                self.assertNotIn(REFRESH, str(result.exception))

    def test_network_errors_do_not_echo_provider_diagnostics(self):
        for error in [urllib.error.URLError(ACCESS), TimeoutError(REFRESH), OSError(ACCESS)]:
            with self.subTest(error=type(error)), patch.object(runtime, "_perform_request", side_effect=error):
                with self.assertRaises(runtime.BasilError) as result:
                    runtime.request("GET", ENDPOINT)
                self.assertNotIn(ACCESS, str(result.exception))
                self.assertNotIn(REFRESH, str(result.exception))

    def test_transport_refuses_redirects_without_second_request(self):
        for code in (301, 302, 303, 307, 308):
            calls = []
            class StubHTTP(urllib.request.HTTPHandler, urllib.request.HTTPSHandler):
                def http_open(self, request):
                    calls.append(request)
                    headers = Message()
                    headers["Location"] = "http://untrusted.test/collect"
                    response = urllib.response.addinfourl(io.BytesIO(b""), headers, request.full_url, code)
                    response.msg = "Redirect"
                    return response
                https_open = http_open
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), runtime.NoRedirect(), StubHTTP())
            with self.subTest(code=code), patch.object(runtime.urllib.request, "build_opener", return_value=opener):
                with self.assertRaisesRegex(runtime.BasilError, "redirect"):
                    runtime.request("GET", ENDPOINT)
            self.assertEqual(len(calls), 1)
            self.assertTrue(calls[0].full_url.startswith(runtime.service_api_base()))

    def test_successful_transport_redacts_echoed_credentials(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = f"{ACCESS} / {REFRESH}".encode()
        response.headers.get_content_charset.return_value = "utf-8"
        response.headers.get_content_type.return_value = "text/markdown"
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(runtime.urllib.request, "build_opener", return_value=opener) as builder:
            text, kind = runtime.request("GET", ENDPOINT)
        self.assertIsInstance(builder.call_args.args[0], runtime.NoRedirect)
        self.assertEqual(text, "[REDACTED] / [REDACTED]")
        self.assertEqual(kind, "text/markdown")
        self.assertEqual(opener.open.call_args.args[0].get_header("Authorization"), f"Bearer {ACCESS}")

    def test_json_and_business_error_output_redact_secrets(self):
        with patch.object(runtime.sys, "stdout", new_callable=io.StringIO) as output:
            runtime.print_json({"message": f"{ACCESS} {REFRESH}"})
            self.assertNotIn(ACCESS, output.getvalue())
            self.assertNotIn(REFRESH, output.getvalue())
        with self.assertRaises(runtime.BasilError) as result:
            runtime.parse_success_response(json.dumps({"success": False, "message": f"{ACCESS} {REFRESH}"}))
        self.assertNotIn(ACCESS, str(result.exception))
        self.assertNotIn(REFRESH, str(result.exception))

    def test_external_or_traversal_endpoints_rejected_before_network(self):
        for endpoint in ["https://untrusted.test", "//untrusted.test", "/oauth2/token", "/openapi/../oauth2/token", "/openapi/%2e%2e/oauth2/token", "/openapi/x?server=elsewhere"]:
            with self.subTest(endpoint=endpoint), patch.object(runtime, "_perform_request") as network:
                with self.assertRaises(runtime.BasilError):
                    runtime.request("GET", endpoint)
                network.assert_not_called()

    def test_legacy_environment_and_files_cannot_select_another_identity(self):
        real_read = Path.read_text
        reads = []
        def read(path, *args, **kwargs):
            reads.append(path)
            return real_read(path, *args, **kwargs)
        with patch.dict(os.environ, {"BASILOS_ACCESS_TOKEN": "old-identity", "BASIL_API_BASE": "https://other.test"}), \
             patch.object(Path, "read_text", read), \
             patch.object(Path, "write_text", side_effect=AssertionError("credentials must not be written")), \
             patch.object(runtime, "_perform_request", return_value=("{}", "application/json")) as network:
            runtime.request("GET", ENDPOINT)
        self.assertEqual(reads, [])
        self.assertEqual(network.call_args.kwargs["headers"]["Authorization"], f"Bearer {ACCESS}")
        self.assertFalse(hasattr(runtime, "refresh_oauth2"))
        self.assertFalse(hasattr(runtime, "save_authorization"))

    def test_cli_resolves_each_domain_before_authenticated_business_request(self):
        # Execute the real CLI in separate processes, replacing only HTTP I/O.
        harness = """
import json, sys
sys.path.insert(0, sys.argv[1])
sys.argv = sys.argv[:1]
import runtime
from base.cli import main

def transport(method, url, **kwargs):
    assert kwargs['headers']['Authorization'] == 'Bearer fixture-access-secret'
    assert '_runtimeDomain' not in url
    assert b'_runtimeDomain' not in (kwargs.get('payload') or b'')
    return json.dumps({'success': True, 'code': 0, 'data': {'url': url}}), 'application/json'

runtime._perform_request = transport
raise SystemExit(runtime.run_script(main))
"""
        for domain in ("https://first.test", "https://second.test:8443/"):
            payload = {"_runtimeDomain": domain, "operation": "base_list"}
            payload["query"] = {"page": 0, "size": 1}
            process = subprocess.run(
                [sys.executable, "-B", "-c", harness, str(SCRIPTS)],
                input=json.dumps(payload), text=True, capture_output=True, env=ENV,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            url = json.loads(process.stdout)["data"]["url"]
            self.assertTrue(url.startswith(domain.rstrip("/") + "/typekey/api/v1/openapi/"))
            self.assertEqual(url.count("/typekey/api/v1"), 1)
            self.assertNotIn(ACCESS, process.stdout + process.stderr)

    def test_cli_status_works_with_only_injected_access_token(self):
        process = subprocess.run([sys.executable, str(SCRIPTS / "auth/status.py")], input='{"_runtimeDomain":"https://current.test"}', text=True, capture_output=True, env={f"{PREFIX}_ACCESS_TOKEN": ACCESS})
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["state"], "available")
        self.assertNotIn(ACCESS, process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
