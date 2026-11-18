#!/usr/bin/env python3
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import tarfile
import unittest
from unittest.mock import patch
import uuid

SOURCE = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ops = load('ops_test', SOURCE / 'deploy-support.py')
domain = load('domain_test', SOURCE / 'domain-ssl.py')
package = load('package_test', SOURCE / 'package.py')


class Packaging(unittest.TestCase):
    def test_public_bundle_preserves_interactive_addresses(self):
        contents = package.build_contents()
        self.assertNotIn('SERVER.md', contents)
        self.assertIsNone(json.loads(contents['release.json'])['target_host'])
        for group in ('middleware', 'studio', 'workbench'):
            self.assertEqual(contents[f'.env.{group}.example'].decode(),
                             package.read_file(SOURCE / f'.env.{group}.example'))
        for name in ('package.py', 'tests/test_deployment.py', '.gitignore'):
            self.assertIn(name, contents)

    def test_server_bundle_keeps_host_prefill(self):
        host = package.server_host('2001:db8::10')
        contents = package.build_contents(host)
        self.assertIn('SERVER.md', contents)
        self.assertEqual(json.loads(contents['release.json'])['target_host'], host)
        self.assertIn('APP_URL=http://[2001:db8::10]:11007', contents['.env.workbench.example'].decode())

    def test_archives_verify_and_rebuild_without_knowledge_base(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / 'dist'
            command = ['python3', str(SOURCE / 'package.py'), str(output)]
            subprocess.run(command, check=True, capture_output=True)
            for line in (output / 'SHA256SUMS').read_text().splitlines():
                digest, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            checkout = root / 'checkout'
            checkout.mkdir()
            with tarfile.open(output / 'deploy.tar.gz') as archive:
                archive.extractall(checkout)
            for line in (checkout / 'FILES.sha256').read_text().splitlines():
                digest, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((checkout / name).read_bytes()).hexdigest(), digest)
            rebuilt = root / 'rebuilt'
            subprocess.run(['python3', str(checkout / 'package.py'), str(rebuilt)], check=True, capture_output=True)
            with tarfile.open(output / 'deploy.tar') as original, tarfile.open(rebuilt / 'deploy.tar') as copy:
                self.assertEqual(original.getnames(), copy.getnames())
                for name in original.getnames():
                    self.assertEqual(original.extractfile(name).read(), copy.extractfile(name).read(), name)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)


class Operations(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.oldroot = ops.ROOT
        ops.ROOT = self.root
        for g in ops.PORTS:
            shutil.copy(SOURCE / f'.env.{g}.example', self.root / f'.env.{g}')
        shutil.copy(SOURCE / 'domain-ssl.py', self.root)
        shutil.copy(SOURCE / 'deploy-support.py', self.root)

    def tearDown(self):
        ops.ROOT = self.oldroot
        self.temp.cleanup()

    def test_env_is_data_and_duplicates_are_rejected(self):
        p = self.root / '.env.workbench'
        secret = 'password$with#literal\\characters'
        ops.edit_env(p, {'JWT_SECRET': secret})
        self.assertEqual(ops.read_env(p)['JWT_SECRET'], secret)
        self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        p.write_text('A=one\nA=two\n')
        with self.assertRaises(ValueError): ops.read_env(p)

    def test_direct_urls_follow_port_but_https_stays(self):
        self.assertEqual(ops.replace_http_port('http://example.com:80/a?q=1', 80, 12000), 'http://example.com:12000/a?q=1')
        self.assertEqual(ops.replace_http_port('https://example.com/a', 80, 12000), 'https://example.com/a')
        self.assertEqual(ops.replace_http_port('http://[::1]:80/a', 80, 12000), 'http://[::1]:12000/a')

    def test_cached_image_never_contacts_registry(self):
        with patch.object(ops, 'image_exists', return_value=True), patch.object(ops.subprocess, 'run') as run:
            ops.pull_image('nginx:1.29-alpine')
            run.assert_not_called()

    def test_pull_timeout_offline_recovery(self):
        with patch.object(ops, 'image_exists', side_effect=[False, True]), patch.object(ops.subprocess, 'run', side_effect=[subprocess.TimeoutExpired('docker', 180), subprocess.CompletedProcess([], 0)]), patch.object(ops, 'ask', side_effect=['2', str(self.root / '.env.studio')]):
            ops.pull_image('test:image')

    def test_port_conflict_and_own_container_reuse(self):
        cfg = {'name': 'test', 'services': {'studio-frontend': {'ports': [{'published': '12000', 'target': 80}]}}}
        with patch.object(ops, 'port_owners', return_value={12000: {('other', 'web')}}), patch.object(ops, 'port_available', return_value=True), patch.object(ops, 'ask', side_effect=['0', '12009']):
            with self.assertRaises(ValueError): ops.ensure_ports('studio', ['studio-frontend'], cfg)
            self.assertTrue(ops.ensure_ports('studio', ['studio-frontend'], cfg))
        self.assertEqual(ops.read_env(self.root / '.env.studio')['STUDIO_FRONTEND_HOST_PORT'], '12009')
        with patch.object(ops, 'port_owners', return_value={12000: {('test', 'studio-frontend')}}), patch.object(ops, 'ask') as ask:
            self.assertFalse(ops.ensure_ports('studio', ['studio-frontend'], cfg))
            ask.assert_not_called()

    def test_failed_proxy_update_restores_env(self):
        p = self.root / '.env.studio'; before = p.read_text()
        cfg = {'name': 'test', 'services': {'studio-frontend': {'ports': [{'published': '12000', 'target': 80}]}}}
        with patch.object(ops, 'port_owners', return_value={12000: {('other', 'web')}}), patch.object(ops, 'port_available', return_value=True), patch.object(ops, 'ask', return_value='12009'), patch.object(ops, 'sync_port_urls', side_effect=ValueError('nginx failure')):
            with self.assertRaises(ValueError): ops.ensure_ports('studio', ['studio-frontend'], cfg)
        self.assertEqual(p.read_text(), before)

    def test_start_rejects_unconfigured_secrets_before_pull(self):
        cfg = {'services': {'api': {'image': 'test:image', 'environment': {'SECRET': 'CHANGE_ME_SECRET'}}}}
        with patch.object(ops, 'config', return_value=cfg), patch.object(ops, 'pull_image') as pull:
            with self.assertRaises(ValueError): ops.up('workbench', ['api'])
            pull.assert_not_called()

    def test_dependencies_are_included_only_when_requested(self):
        cfg = {'services': {'api': {'depends_on': {'db': {}}}, 'db': {}}}
        self.assertEqual(ops.select_services(cfg, ['api']), ['api', 'db'])
        self.assertEqual(ops.select_services(cfg, ['api'], True), ['api'])

    def test_invalid_domains_and_nxdomain_fail_before_nginx(self):
        for value in ['http://test.com', 'test', 'test.local', 'a..com', '1.2.3.4', 'test.com;bad']:
            self.assertFalse(domain.valid_domain(value))
        self.assertTrue(domain.valid_domain('workbench.example.com'))
        with patch.object(domain.socket, 'getaddrinfo', side_effect=socket.gaierror()), patch.object(domain.ops, 'run') as run:
            with self.assertRaises(socket.gaierror): domain.setup('workbench', 'wb.example.com', 'me@example.com', 11007, '192.0.2.1')
            run.assert_not_called()

    def test_cert_failure_restores_existing_site(self):
        confdir = self.root / 'nginx'; confdir.mkdir()
        acme = self.root / 'acme'
        conf = confdir / 'basil-workbench.conf'
        previous = '# Managed by Basil deploy.sh\n# existing working site\n'
        conf.write_text(previous)
        def checked_run(args, **kwargs):
            if args[0] == 'certbot': raise subprocess.CalledProcessError(1, ['certbot'])
            return subprocess.CompletedProcess(args, 0)
        def capture(args):
            if args[0] == 'ss': return ''
            return next((acme / '.well-known/acme-challenge').iterdir()).read_text()
        with patch.object(domain, 'NGINX_DIR', confdir), patch.object(domain, 'ACME_DIR', acme), patch.object(domain.socket, 'getaddrinfo', return_value=[(None, None, None, None, ('192.0.2.1', 80))]), patch.object(domain.shutil, 'which', return_value='/bin/mock'), patch.object(domain.ops, 'run', side_effect=checked_run), patch.object(domain.ops, 'capture', side_effect=capture), patch.object(domain.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')), patch.object(domain, 'reload_nginx'):
            with self.assertRaises(subprocess.CalledProcessError): domain.setup('workbench', 'wb.example.com', 'me@example.com', 11007, '192.0.2.1')
        self.assertEqual(conf.read_text(), previous)
        self.assertEqual(list((acme / '.well-known/acme-challenge').iterdir()), [])

    def test_existing_middleware_keeps_credentials_and_modes(self):
        script = '''source "$1/deploy.sh"
ENV_FILE="$2/.env.middleware"
set_env COMPOSE_FILE 'docker-compose.middleware.yaml,compose/db.yaml,compose/cache.yaml'
set_env POSTGRESQL_HOST postgresql
set_env POSTGRESQL_PASSWORD 'test-secret'
restore_middleware_modes
[[ "$POSTGRES_MODE" == local && "$REDIS_MODE" == local && "$RABBITMQ_MODE" == external ]]
existing_middleware_test() { return 0; }
choose_mode() { exit 91; }
prompt_secret_confirm() { exit 92; }
initialize_postgresql
[[ "$(dotenv_get POSTGRESQL_PASSWORD)" == test-secret ]]
'''
        subprocess.run(['bash', '-c', script, 'test', str(SOURCE), str(self.root)], check=True)

    @unittest.skipUnless(os.environ.get('BASIL_DOCKER_TEST') == '1', 'opt-in isolated Docker integration')
    def test_real_docker_conflict_restart_and_env_reload(self):
        project = 'basil-ops-test-' + uuid.uuid4().hex[:8]
        with socket.socket() as occupied:
            occupied.bind(('0.0.0.0', 0)); occupied.listen()
            old = occupied.getsockname()[1]
            with socket.socket() as probe:
                probe.bind(('0.0.0.0', 0)); new = probe.getsockname()[1]
            ops.edit_env(self.root / '.env.studio', {'COMPOSE_PROJECT_NAME': project, 'STUDIO_FRONTEND_HOST_PORT': str(old), 'ENCRYPTOR_PASSWORD': 'before'})
            (self.root / 'docker-compose.studio.yaml').write_text('''services:
  studio-frontend:
    image: nginx:1.29-alpine
    platform: linux/amd64
    environment:
      TEST_CONFIG: ${ENCRYPTOR_PASSWORD}
    ports:
      - "${STUDIO_FRONTEND_HOST_PORT}:80"
''')
            try:
                with patch.object(ops, 'ask', return_value=str(new)):
                    ops.up('studio', ['studio-frontend'])
                subprocess.run(['curl', '-fsS', '--max-time', '10', '-o', '/dev/null', f'http://127.0.0.1:{new}'], check=True)
                ops.edit_env(self.root / '.env.studio', {'ENCRYPTOR_PASSWORD': 'after'})
                with patch.object(ops, 'ask', side_effect=AssertionError('own port must be reusable')):
                    ops.up('studio', ['studio-frontend'], recreate=True, no_deps=True)
                cid = ops.capture(ops.compose('studio') + ['ps', '-q', 'studio-frontend']).strip()
                env = json.loads(ops.capture(['docker', 'inspect', cid]))[0]['Config']['Env']
                self.assertIn('TEST_CONFIG=after', env)
            finally:
                subprocess.run(ops.compose('studio') + ['down'], cwd=self.root, check=True)

if __name__ == '__main__': unittest.main()
