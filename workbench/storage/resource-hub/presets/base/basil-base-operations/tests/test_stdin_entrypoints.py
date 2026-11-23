"""Real subprocess coverage for Runtime argv/stdin handoff; no live credentials."""
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]


class StdinEntrypointTests(TestCase):
    def run_entry(self, script, args=(), payload=""):
        return subprocess.run(
            [sys.executable, "-B", str(ROOT / script), *args],
            input=payload, text=True, capture_output=True,
            env={"PATH": os.defpath}, timeout=10,
        )

    def test_argv_payload_is_rejected_without_echo_or_auth_action(self):
        for script in ("scripts/auth/status.py", "scripts/auth/personal_token.py"):
            with self.subTest(script=script):
                result = self.run_entry(script, ['{"_runtimeDomain":"https://example.test","secret":"sentinel-do-not-echo"}'])
                self.assertEqual(result.returncode, 1)
                data = json.loads(result.stdout)
                self.assertIn("INPUT_CHANNEL_ERROR", data["error"])
                self.assertNotIn("next_action", data)
                self.assertNotIn("sentinel-do-not-echo", result.stdout + result.stderr)

    def test_business_argv_fails_before_operation_or_domain_validation(self):
        result = self.run_entry("scripts/base/records.py", ["folder_create", '{"space":"MY","path":"example"}'])
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertIn("INPUT_CHANNEL_ERROR", data["error"])
        self.assertNotIn("next_action", data)

    def test_empty_stdin_reports_transport_problem_before_business_validation(self):
        for script in ("scripts/auth/status.py", "scripts/base/records.py"):
            with self.subTest(script=script):
                result = self.run_entry(script)
                self.assertEqual(result.returncode, 1)
                data = json.loads(result.stdout)
                self.assertIn("INPUT_CHANNEL_ERROR", data["error"])
                self.assertIn("stdin is empty", data["error"])
                self.assertNotIn("next_action", data)

    def test_existing_personal_token_is_reused_without_a_form(self):
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/auth/status.py")],
            input=json.dumps({"_runtimeDomain": "https://example.test"}),
            text=True, capture_output=True, timeout=10,
            env={"PATH": os.defpath, "APP_BASILOS_PERSONAL_TOKEN": "fixture-token"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["auth_mode"], "personal_token")
        self.assertTrue(data["configured"])
        self.assertNotIn("next_action", data)
        self.assertNotIn("fixture-token", result.stdout)

    def test_stdin_domain_reaches_missing_credential_detection(self):
        result = self.run_entry("scripts/auth/status.py", payload=json.dumps({"_runtimeDomain": "https://example.test"}))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["state"], "missing_access_token")
        self.assertFalse(data["configured"])
        self.assertEqual(data["api_base"], "https://example.test/typekey/api/v1")

    def test_shell_stdin_transport_matches_direct_transport(self):
        payload = json.dumps({"_runtimeDomain": "https://example.test", "_authMode": "personal_token"})
        direct = self.run_entry("scripts/auth/status.py", payload=payload)
        import shlex
        command = "exec " + shlex.quote(sys.executable) + " -B scripts/auth/status.py <<'BASIL_INPUT'\n" + payload + "\nBASIL_INPUT"
        shell = subprocess.run(["/bin/sh", "-c", command], cwd=ROOT, env={"PATH": os.defpath}, capture_output=True, text=True, timeout=10)
        self.assertEqual(shell.returncode, direct.returncode)
        self.assertEqual(json.loads(shell.stdout), json.loads(direct.stdout))
        self.assertEqual(json.loads(shell.stdout)["next_action"]["tool"], "request_user_input")

    def test_empty_helper_input_still_emits_original_secure_form(self):
        result = self.run_entry("scripts/auth/personal_token.py", payload="{}")
        self.assertEqual(result.returncode, 0)
        args = json.loads(result.stdout)["next_action"]["arguments"]
        self.assertEqual(args["credentialKey"], "app.basilos.personal-token")
        self.assertIn("bottom-left", args["description"])
        self.assertTrue(args["fields"][0]["secret"])
