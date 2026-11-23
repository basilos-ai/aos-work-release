"""Package configuration and retired local-authorization entry point tests."""
import json
from pathlib import Path
import re
import shutil
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import runtime


class AppOAuthConfigurationTests(unittest.TestCase):
    def test_service_configuration_is_packaged_with_member(self):
        self.assertTrue((SCRIPTS / "runtime/service.py").is_file())
        self.assertEqual(runtime.service.API_PREFIX, "/typekey/api/v1")
        self.assertFalse((SCRIPTS / "runtime/service.json").exists())
        self.assertFalse((SCRIPTS / "base/result_links.json").exists())
        self.assertFalse(list(SKILL_ROOT.rglob("oauth-clients.y*ml")))

    def test_missing_or_invalid_domain_fails_before_credentials_or_network(self):
        for domain in [None, 42, {}, "", "https://user:password@example.test",
                       "https://example.test?token=foo", "https://example.test#",
                       "https://example.test/typekey/api/v1", "http://example.test",
                       "https://example.test:invalid", "https://[broken", "https://example.test\n",
                       "https://example.test/\\evil"]:
            with self.subTest(domain=domain), patch.object(runtime, "RUNTIME_DOMAIN", domain), \
                 patch.object(runtime, "_perform_request") as network, \
                 patch.object(runtime, "auth_headers") as credentials:
                with self.assertRaises(runtime.BasilError):
                    runtime.request("GET", "/openapi/base")
                credentials.assert_not_called()
                network.assert_not_called()

    def test_status_requires_domain_even_with_injected_credentials(self):
        process = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / "auth/status.py")],
            input="{}", text=True, capture_output=True,
            env={"APP_OAUTH_BASILOS_ACCESS_TOKEN": "fixture-injected-access"},
        )
        self.assertEqual(process.returncode, 1)
        self.assertIn("_runtimeDomain", json.loads(process.stdout)["error"])
        self.assertNotIn("fixture-injected-access", process.stdout + process.stderr)

    def test_domain_preserves_origin_and_appends_prefix_once(self):
        for domain in ["https://one.test", "https://two.test:8443/", "https://[::1]:8443"]:
            with self.subTest(domain=domain), patch.object(runtime, "RUNTIME_DOMAIN", domain):
                self.assertEqual(runtime.service_api_base(), domain.rstrip("/") + "/typekey/api/v1")

    def test_domain_control_is_consumed_and_does_not_leak_between_inputs(self):
        import io
        with patch.object(runtime, "RUNTIME_DOMAIN", None):
            with patch.object(runtime.sys, "stdin", io.StringIO(json.dumps({
                "_runtimeDomain": "https://current.test/", "operation": "base_list"
            }))):
                self.assertEqual(runtime.read_json_stdin(), {"operation": "base_list"})
                self.assertEqual(runtime.service_api_base(), "https://current.test/typekey/api/v1")
            for raw in ["{}", "", '{"_runtimeDomain":null}', "not json"]:
                with patch.object(runtime.sys, "stdin", io.StringIO(raw)):
                    try:
                        runtime.read_json_stdin()
                    except runtime.BasilError:
                        pass
                    with self.assertRaises(runtime.BasilError):
                        runtime.service_api_base()

    def test_retired_scripts_fail_without_consuming_or_echoing_credentials(self):
        for script in ["oauth_login.py", "configure.py"]:
            with self.subTest(script=script):
                process = subprocess.run([sys.executable, str(SCRIPTS / "auth" / script)], input='{"token":"fixture-private-token","server":"https://example.test"}', text=True, capture_output=True, env={})
                self.assertEqual(process.returncode, 1)
                self.assertIn("Workbench", json.loads(process.stdout)["error"])
                self.assertNotIn("fixture-private-token", process.stdout + process.stderr)
                self.assertEqual(process.stderr, "")

    def test_isolated_member_uses_service_without_parent_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            member = Path(directory) / "resources/apps/basil-base-operations"
            shutil.copytree(SKILL_ROOT, member, ignore=shutil.ignore_patterns("__pycache__"))
            for domain in ["https://first.test", "https://second.test:8443/"]:
                process = subprocess.run(
                    [sys.executable, "-B", str(member / "scripts/auth/status.py")],
                    input=json.dumps({"_runtimeDomain": domain}), text=True, capture_output=True,
                    env={"APP_OAUTH_BASILOS_ACCESS_TOKEN": "fixture-injected-access"},
                    cwd=directory, timeout=10,
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(process.stderr, "")
                self.assertEqual(json.loads(process.stdout)["state"], "available")
                self.assertEqual(json.loads(process.stdout)["api_base"], domain.rstrip("/") + "/typekey/api/v1")
                self.assertNotIn("fixture-injected-access", process.stdout + process.stderr)
                self.assertFalse((member.parent / "manifest.yaml").exists())

    def test_agent_documentation_references_exist(self):
        documents = [SKILL_ROOT / "SKILL.md", SKILL_ROOT / "README.md",
                     *sorted((SKILL_ROOT / "references").glob("*.md"))]
        reference_count = 0
        for document in documents:
            for reference in re.findall(r"`((?:scripts|references)/[^`\s]+)`", document.read_text()):
                with self.subTest(document=document.name, reference=reference):
                    self.assertTrue((SKILL_ROOT / reference).is_file(), reference)
                reference_count += 1
        self.assertGreater(reference_count, 0)

    def test_all_cli_entrypoints_run_from_an_isolated_member(self):
        with tempfile.TemporaryDirectory() as directory:
            member = Path(directory) / SKILL_ROOT.name
            shutil.copytree(SKILL_ROOT, member)
            entrypoints = [path for path in sorted((member / "scripts").rglob("*.py"))
                           if 'if __name__ == "__main__":' in path.read_text()]
            self.assertTrue(entrypoints)
            for script in entrypoints:
                with self.subTest(script=str(script.relative_to(member))):
                    # No credentials or PYTHONPATH; invalid business input must
                    # produce a controlled JSON error without reaching the API.
                    process = subprocess.run(
                        [sys.executable, "-B", str(script)], input='{"_runtimeDomain":"https://current.test"}',
                        text=True, capture_output=True, env={}, cwd=directory,
                        timeout=10,
                    )
                    self.assertEqual(process.stderr, "")
                    result = json.loads(process.stdout)
                    self.assertIsInstance(result, dict)
                    if script.name in {"status.py", "personal_token.py"}:
                        self.assertEqual(process.returncode, 0)
                    else:
                        self.assertEqual(process.returncode, 1)
                        self.assertTrue(result.get("error"))

    def test_status_rejects_server_and_token_overrides(self):
        process = subprocess.run([sys.executable, str(SCRIPTS / "auth/status.py")], input='{"server":"https://other.test","token":"fixture-private-token"}', text=True, capture_output=True, env={})
        self.assertEqual(process.returncode, 1)
        self.assertNotIn("fixture-private-token", process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
