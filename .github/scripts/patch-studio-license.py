"""Apply the Studio license fix to the pinned quick installer (no network or execution).

The launcher verifies this file and its input before invoking it. The same
transformation is used on the repository installer; tests cover both variants.
"""
from pathlib import Path
import re
import sys

HELPERS = '''
LICENSE_HUB_DEFAULT = 'https://license-hub.aos.work'
LICENSE_CALLBACK_PATH = '/typekey/api/v1/system/license/webhook'


def studio_license_changes(current, public_url):
    public_url = public_url.rstrip('/')
    previous = current.get('ASSETS_SEARCH_SNAPSHOT_URL', '').removesuffix('/basilos/asset/search-embed').rstrip('/')
    callback = current.get('LICENSE_HUB_WEBHOOK_URL', '')
    changes = {}
    hub = current.get('LICENSE_HUB_API_URL', '')
    if not hub or hub.startswith('CHANGE_ME'):
        changes['LICENSE_HUB_API_URL'] = LICENSE_HUB_DEFAULT
    if public_url.startswith('https://') and (
            not callback or callback.startswith('CHANGE_ME') or
            (previous and callback == previous + LICENSE_CALLBACK_PATH)):
        changes['LICENSE_HUB_WEBHOOK_URL'] = public_url + LICENSE_CALLBACK_PATH
    return changes


def sync_studio_license(public_url):
    path = ops.env_path('studio')
    ops.edit_env(path, studio_license_changes(ops.read_env(path), public_url))


def verify_studio_license():
    current = ops.read_env(ops.env_path('studio'))
    for key in ('LICENSE_HUB_API_URL', 'LICENSE_HUB_WEBHOOK_URL'):
        expected = current.get(key, '')
        if expected and ops.capture(ops.compose('studio') + ['exec', '-T', 'studio', 'printenv', key]).strip() != expected:
            raise ValueError('Studio backend has stale ' + key + '; recreate the backend before activating a license.')

'''

ROUTE = '''    if target == 'studio':
        api_port = int(ops.read_env(ops.env_path('studio'))['STUDIO_API_HOST_PORT'])
        if not 1 <= api_port <= 65535:
            raise ValueError('Invalid Studio API port')
        proxy = f''' + "'''" + '''    location = /typekey/api/v1/system/license/webhook {{
        proxy_pass http://127.0.0.1:{api_port};
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
''' + "'''" + ''' + proxy
'''

def patch(text):
    if 'def studio_license_changes(' in text:
        raise ValueError('Installer already patched')
    # Only the embedded domain helper contains this signature.
    text = text.replace('def valid_domain(value):', HELPERS + '\ndef valid_domain(value):', 1)
    text = text.replace('def nginx_text(domain, port, tls):', 'def nginx_text(domain, port, tls, target=None):', 1)
    pos = text.index("    text = f'''# Managed by Basil deploy.sh", text.index('def nginx_text('))
    text = text[:pos] + ROUTE + text[pos:]
    text = text.replace("nginx_text(item['domain'], port, True)", "nginx_text(item['domain'], port, True, target)")
    text = text.replace('nginx_text(domain, port, False)', 'nginx_text(domain, port, False, target)')
    text = text.replace('nginx_text(domain, port, True)', 'nginx_text(domain, port, True, target)')
    text = text.replace("domain.nginx_text(settings['domain'], settings['port'], True)", "domain.nginx_text(settings['domain'], settings['port'], True, target)")
    start = text.index("    elif target == 'studio':", text.index('def apply_urls('))
    end = text.index("        groups = ['studio']", start)
    text = text[:start] + '''    elif target == 'studio':
        current = ops.read_env(ops.env_path('studio'))
        changes = studio_license_changes(current, url)
        changes.update(ASSETS_SEARCH_SNAPSHOT_URL=url + '/basilos/asset/search-embed',
                       VIEW_SNAPSHOT_URL=url + '/basilos/studio/engine/multi-dim-table-embed')
        ops.edit_env(ops.env_path('studio'), changes)
''' + text[end:]
    start = text.index('def main():', text.index('def apply_urls('))
    pos = text.index('\n', start) + 1
    text = text[:pos] + '''    if len(sys.argv) == 3 and sys.argv[1] == '--sync-studio-license':
        sync_studio_license(sys.argv[2])
        return
    if len(sys.argv) == 2 and sys.argv[1] == '--verify-studio-license':
        verify_studio_license()
        return
''' + text[pos:]
    text = text.replace('            ops.up(group, [group], recreate=True, no_deps=True, interactive=False)',
        "            ops.up(group, [group], recreate=True, no_deps=True, interactive=False)\n            if group == 'studio':\n                verify_studio_license()")
    start = text.index('ensure_studio_configuration() {')
    end = text.index('\ndeploy_studio() {', start)
    block = text[start:end]
    block = re.sub(r'  if \[\[ "\$studio_frontend_url" == https://\*.*?\n  fi\n', '', block, flags=re.S)
    anchor = '  studio_set_env ASSETS_SEARCH_SNAPSHOT_URL'
    block = block.replace(anchor, '  python3 "$SUPPORT_DIR/domain-ssl.py" --sync-studio-license "$studio_frontend_url"\n' + anchor, 1)
    text = text[:start] + block + text[end:]
    text = text.replace('  ops up studio\n', '  ops up studio\n  python3 "$SUPPORT_DIR/domain-ssl.py" --verify-studio-license\n')
    return text

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: patch-studio-license.py PATH_TO_VERIFIED_DEPLOY_SH')
    path = Path(sys.argv[1])
    path.write_text(patch(path.read_text()), encoding='utf-8', newline='\n')
