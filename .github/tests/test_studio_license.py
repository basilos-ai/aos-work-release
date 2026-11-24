import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
CALLBACK = '/typekey/api/v1/system/license/webhook'

def extract(script, directory):
    text = Path(script).read_text(encoding='utf-8')
    for name, body in re.findall(r'cat > "\$SUPPORT_DIR/([^"\n]+)" <<\'AOS_EMBEDDED_FILE_END\'\n(.*?)\nAOS_EMBEDDED_FILE_END', text, re.S):
        if name.endswith('.py'):
            compile(body, name, 'exec')
            (directory / name).write_text(body, encoding='utf-8')
    os.environ['BASIL_DEPLOY_DIR'] = str(directory)
    spec=importlib.util.spec_from_file_location('studio_domain_test', directory/'domain-ssl.py')
    module=importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(directory))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module

class StudioLicenseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.domain=extract(os.environ.get('INSTALLER_UNDER_TEST', ROOT/'deploy.sh'), self.root)
        (self.root/'docker-compose.studio.yaml').write_text('services: {}\n')
        (self.root/'.env.studio').write_text('COMPOSE_PROJECT_NAME=basil-studio\nSTUDIO_API_HOST_PORT=12001\n')
        self.domain.ops.capture=Mock(return_value='')
        self.domain.ops.up=Mock()
        self.domain.ops.run=Mock()

    def tearDown(self):
        self.temp.cleanup()

    def env(self): return self.domain.ops.read_env(self.root/'.env.studio')

    def test_fresh_deployment_then_domain_change(self):
        self.domain.apply_urls('studio', 'studio.example.com')
        self.assertEqual(self.env()['LICENSE_HUB_API_URL'], 'https://license-hub.aos.work')
        self.assertEqual(self.env()['LICENSE_HUB_WEBHOOK_URL'], 'https://studio.example.com'+CALLBACK)
        self.domain.ops.up.assert_not_called()  # initial deployment starts later
        self.domain.ops.capture.side_effect=lambda args: self.env().get(args[-1],'') if 'printenv' in args else 'running-container'
        self.domain.apply_urls('studio', 'new.example.com')
        self.assertEqual(self.env()['LICENSE_HUB_WEBHOOK_URL'], 'https://new.example.com'+CALLBACK)
        self.domain.ops.up.assert_called_once_with('studio',['studio'],recreate=True,no_deps=True,interactive=False)

    def test_custom_callback_and_hub_survive(self):
        self.domain.ops.edit_env(self.root/'.env.studio',{
            'LICENSE_HUB_API_URL':'https://private.example.com',
            'LICENSE_HUB_WEBHOOK_URL':'https://callback.example.com/custom'})
        self.domain.apply_urls('studio','studio.example.com')
        self.domain.apply_urls('studio','new.example.com')
        self.assertEqual(self.env()['LICENSE_HUB_WEBHOOK_URL'],'https://callback.example.com/custom')
        self.assertEqual(self.env()['LICENSE_HUB_API_URL'],'https://private.example.com')

    def test_empty_legacy_and_placeholder_defaults(self):
        self.domain.ops.edit_env(self.root/'.env.studio',{'LICENSE_HUB_API_URL':'CHANGE_ME_HUB','LICENSE_HUB_WEBHOOK_URL':'CHANGE_ME_CALLBACK'})
        self.domain.sync_studio_license('https://studio.example.com/')
        self.assertEqual(self.env()['LICENSE_HUB_WEBHOOK_URL'],'https://studio.example.com'+CALLBACK)
        self.assertEqual(self.env()['LICENSE_HUB_API_URL'],'https://license-hub.aos.work')
        self.domain.sync_studio_license('https://studio.example.com/')
        self.assertEqual(self.env()['LICENSE_HUB_WEBHOOK_URL'],'https://studio.example.com'+CALLBACK)

    def test_http_does_not_invent_public_https(self):
        self.domain.sync_studio_license('http://192.0.2.1:12000')
        self.assertNotIn('LICENSE_HUB_WEBHOOK_URL',self.env())

    def test_https_route_is_exact_backend_route_and_preserves_uri(self):
        text=self.domain.nginx_text('studio.example.com',12000,True,'studio')
        self.assertIn('location = '+CALLBACK,text)
        self.assertIn('proxy_pass http://127.0.0.1:12001;',text)
        self.assertIn('proxy_set_header X-Forwarded-Proto $scheme;',text)
        self.assertIn('proxy_pass http://127.0.0.1:12000;',text)
        self.assertNotIn('location = '+CALLBACK,self.domain.nginx_text('work.example.com',11007,True,'workbench'))

    def test_backend_recreation_failure_is_not_reported_as_success(self):
        self.domain.ops.capture.return_value='running-container'
        self.domain.ops.up.side_effect=RuntimeError('recreation failed')
        with self.assertRaisesRegex(RuntimeError,'recreation failed'):
            self.domain.apply_urls('studio','studio.example.com')

    def test_stale_backend_environment_is_rejected(self):
        self.domain.sync_studio_license('https://studio.example.com')
        self.domain.ops.capture.return_value='stale'
        with self.assertRaisesRegex(ValueError,'stale LICENSE_HUB_API_URL'):
            self.domain.verify_studio_license()

if __name__=='__main__': unittest.main()
