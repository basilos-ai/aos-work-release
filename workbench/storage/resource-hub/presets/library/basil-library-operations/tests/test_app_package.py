"""Source App integration checks; member-only installations have no App files."""
import importlib.util
from pathlib import Path
import re
import unittest

SKILL_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('app_package_runtime', SKILL_ROOT / 'scripts/runtime/__init__.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


@unittest.skipUnless(all((SKILL_ROOT.parent / name).is_file() for name in ('manifest.yaml', 'oauth-clients.yaml')),
                     'App source integration requires parent manifest and client configuration')
class AppPackageIntegrationTests(unittest.TestCase):
    def test_manifest_provider_matches_member(self):
        manifest = (SKILL_ROOT.parent / "manifest.yaml").read_text()
        provider = re.search(r"authProviderKey:\s*(\S+)", manifest).group(1)
        token_url = re.search(r"(?m)^ +tokenUrl: '([^'\n]+)'$", manifest).group(1)
        self.assertEqual(provider, runtime.OAUTH_PROVIDER_KEY)
        self.assertTrue(token_url.endswith("/typekey/api/v1/oauth2/token"))
        self.assertIn("auth:\n  type: oauth2", manifest)
        self.assertIn("/basilcraw/api/apps/oauth2/callback", manifest)
        self.assertTrue((SKILL_ROOT / "SKILL.md").is_file())
        # Inspect provider metadata only; never print client credentials.
        clients = (SKILL_ROOT.parent / "oauth-clients.yaml").read_text()
        self.assertIn(f"key: {provider}", clients)
        self.assertIn("authType: oauth2", clients)


if __name__ == '__main__':
    unittest.main()
