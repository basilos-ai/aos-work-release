#!/usr/bin/env python3
"""Interactive DNS verification, Nginx and ACME setup (Ubuntu/Debian)."""
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent
NGINX_DIR = Path('/etc/nginx/conf.d')
ACME_DIR = Path('/var/www/basil-acme')
spec = importlib.util.spec_from_file_location('basil_ops', ROOT / 'deploy-support.py')
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)
TARGETS = {
    'studio': ('studio', 'STUDIO_FRONTEND_HOST_PORT'),
    'workbench': ('workbench', 'WORKBENCH_FRONTEND_HOST_PORT'),
    'storage': ('middleware', 'MINIO_API_HOST_PORT'),
}


def valid_domain(value):
    try:
        ipaddress.ip_address(value)
        return False
    except ValueError:
        return len(value) <= 253 and '.' in value and all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', x) for x in value.split('.')) and not value.endswith(('.local', '.localhost', '.test', '.invalid'))


def nginx_text(domain, port, tls):
    challenge = '''    location ^~ /.well-known/acme-challenge/ {
        root /var/www/basil-acme;
        try_files $uri =404;
    }
'''
    proxy = f'''    client_max_body_size 500M;
    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $basil_{domain.replace('.', '_').replace('-', '_')}_upgrade;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_redirect off;
    }}
'''
    text = f'''# Managed by Basil deploy.sh
map $http_upgrade $basil_{domain.replace('.', '_').replace('-', '_')}_upgrade {{
    default upgrade;
    '' close;
}}
server {{
    listen 80;
    listen [::]:80;
    server_name {domain};
{challenge}'''
    if not tls:
        return text + proxy + '}\n'
    return text + f'''    location / {{ return 301 https://$host$request_uri; }}
}}
server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {domain};
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
{proxy}}}
'''


def reload_nginx():
    ops.run(['nginx', '-t'])
    ops.run(['systemctl', 'enable', '--now', 'nginx'])
    ops.run(['systemctl', 'reload', 'nginx'])


def refresh_port(root, group, key, port):
    state = root / '.domains.json'
    if not state.exists():
        return
    settings = json.loads(state.read_text())
    for target, item in settings.items():
        if TARGETS.get(target) != (group, key):
            continue
        conf = NGINX_DIR / ('basil-' + target + '.conf')
        old = conf.read_text()
        if os.geteuid() != 0:
            raise ValueError('已有域名代理，修改上游端口请使用 sudo bash deploy.sh。')
        ops.backup(conf)
        ops.atomic_write(conf, nginx_text(item['domain'], port, True))
        conf.chmod(0o644)
        try:
            reload_nginx()
        except subprocess.SubprocessError:
            ops.atomic_write(conf, old); reload_nginx(); raise
        item['port'] = port
    ops.atomic_write(state, json.dumps(settings, indent=2) + '\n')


def setup(target, domain, email, port, expected):
    if not valid_domain(domain):
        raise ValueError('请填写完整公网域名，例如 workbench.example.com，不含协议、路径或端口。')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('证书通知邮箱格式无效。')
    if not 1 <= port <= 65535 or port in (80, 443):
        raise ValueError('应用上游请使用 80/443 以外的端口，80/443 留给宿主机 Nginx。在环境文件修改应用 HOST_PORT 后用菜单 7 重启。')
    expected = {str(ipaddress.ip_address(x.strip())) for x in expected.split(',')}
    addresses = {x[4][0] for x in socket.getaddrinfo(domain, 80, type=socket.SOCK_STREAM)}
    if not addresses or not addresses.issubset(expected):
        raise ValueError('DNS 尚未正确指向本机：' + ', '.join(sorted(addresses)) + '。检查 A/AAAA；暂时关闭 CDN 代理后重试。')
    health_path = '/minio/health/ready' if target == 'storage' else '/'
    ops.run(['curl', '--noproxy', '*', '-fsS', '--max-time', '10', '-o', '/dev/null', f'http://127.0.0.1:{port}{health_path}'])
    if not shutil.which('nginx') or not shutil.which('certbot'):
        if not shutil.which('apt-get'):
            raise ValueError('此系统请先安装 nginx、certbot 和 systemd，再运行菜单。')
        ops.run(['apt-get', 'update'])
        ops.run(['apt-get', 'install', '-y', 'nginx', 'certbot'])
    # Existing non-nginx listeners must be handled before changing any site configuration.
    for number in (80, 443):
        listeners = ops.capture(['ss', '-H', '-ltnp', f'sport = :{number}']).strip()
        if listeners and any('nginx' not in line for line in listeners.splitlines()):
            raise ValueError(f'端口 {number} 已被其他服务占用，请通过重启菜单调整容器 HOST_PORT 后重试。')
    conf = NGINX_DIR / ('basil-' + target + '.conf')
    conf.parent.mkdir(parents=True, exist_ok=True)
    if conf.exists() and not conf.read_text().startswith('# Managed by Basil deploy.sh'):
        raise ValueError('目标配置不是脚本管理的文件，拒绝覆盖：' + str(conf))
    nginx_all = subprocess.run(['nginx', '-T'], capture_output=True, text=True)
    current_file = ''
    for line in nginx_all.stdout.splitlines():
        if line.startswith('# configuration file '):
            current_file = line.removeprefix('# configuration file ').rstrip(':')
        if re.search(r'\bserver_name\s', line) and domain in line.replace(';', '').split() and current_file != str(conf):
            raise ValueError('该域名已在另一份 Nginx 配置中使用：' + current_file)
    previous = conf.read_text() if conf.exists() else None
    if conf.exists():
        ops.backup(conf)
    token = uuid.uuid4().hex
    challenge = ACME_DIR / '.well-known/acme-challenge' / token
    challenge.parent.mkdir(parents=True, exist_ok=True)
    challenge.write_text(token); challenge.chmod(0o644)
    try:
        ops.atomic_write(conf, nginx_text(domain, port, False)); conf.chmod(0o644)
        reload_nginx()
        for address in addresses:
            ip = '[' + address + ']' if ':' in address else address
            body = ops.capture(['curl', '--noproxy', '*', '-fsS', '--max-time', '15', '--resolve', f'{domain}:80:{ip}', f'http://{domain}/.well-known/acme-challenge/{token}'])
            if body != token:
                raise ValueError('HTTP 验证路径未返回测试文件，请检查安全组 80 入站和 DNS。')
        ops.run(['certbot', 'certonly', '--webroot', '-w', '/var/www/basil-acme', '-d', domain,
                 '--cert-name', domain, '--email', email, '--agree-tos', '--non-interactive', '--keep-until-expiring'])
        ops.atomic_write(conf, nginx_text(domain, port, True)); conf.chmod(0o644)
        reload_nginx()
        ops.run(['curl', '--noproxy', '*', '-fsS', '--max-time', '20', '-o', '/dev/null', f'https://{domain}{health_path}'])
    except BaseException:
        if previous is None:
            conf.unlink(missing_ok=True)
        else:
            ops.atomic_write(conf, previous); conf.chmod(0o644)
        reload_nginx()
        raise
    finally:
        challenge.unlink(missing_ok=True)
    hook = Path('/etc/letsencrypt/renewal-hooks/deploy/basil-nginx.sh')
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text('#!/bin/sh\nset -eu\nnginx -t\nsystemctl reload nginx\n'); hook.chmod(0o755)
    ops.run(['systemctl', 'enable', '--now', 'certbot.timer'])
    state = ROOT / '.domains.json'
    settings = json.loads(state.read_text()) if state.exists() else {}
    settings[target] = {'domain': domain, 'port': port}
    ops.atomic_write(state, json.dumps(settings, indent=2) + '\n')


def apply_urls(target, domain):
    url = 'https://' + domain
    if target == 'workbench':
        ops.edit_env(ops.env_path('workbench'), {k: url for k in ('APP_URL', 'FRONTEND_URL', 'FRONTEND_OAUTH_RESULT_URL')})
        ops.up('workbench', ['workbench'], recreate=True, no_deps=True)
    elif target == 'studio':
        ops.edit_env(ops.env_path('studio'), {'ASSETS_SEARCH_SNAPSHOT_URL': url + '/basilos/asset/search-embed',
                    'VIEW_SNAPSHOT_URL': url + '/basilos/studio/engine/multi-dim-table-embed'})
        ops.up('studio', ['studio'], recreate=True, no_deps=True)
    else:
        ops.edit_env(ops.env_path('middleware'), {'MINIO_EXPOSE_URL': url})
        ops.edit_env(ops.env_path('workbench'), {'MINIO_PUBLIC_BASE_URL': url, 'MINIO_PRESIGN_ENDPOINT': domain,
                    'MINIO_PRESIGN_PORT': '443', 'MINIO_PRESIGN_USE_SSL': 'true'})
        for group, service in [('studio', 'studio'), ('workbench', 'workbench')]:
            if ops.capture(ops.compose(group) + ['ps', '-a', '-q', service]).strip():
                ops.up(group, [service], recreate=True, no_deps=True)
    for group, frontend in [('studio', 'studio-frontend'), ('workbench', 'workbench-frontend')]:
        if ops.capture(ops.compose(group) + ['ps', '-q', frontend]).strip():
            ops.run(ops.compose(group) + ['exec', '-T', frontend, 'nginx', '-s', 'reload'])


def release_web_ports():
    owners = ops.port_owners()
    for group in ops.PORTS:
        cfg = ops.config(group)
        for service, mappings in ops.PORTS[group].items():
            for key, _ in mappings:
                value = ops.read_env(ops.env_path(group)).get(key)
                if value not in ('80', '443') or (cfg['name'], service) not in owners.get(int(value), set()):
                    continue
                print(f'{service} 正占用 {value}，需要移到其他端口，供 Nginx 使用 80/443。')
                while True:
                    proposed = ops.ask('请输入新的应用端口（0 取消）', '12000' if service == 'studio-frontend' else '')
                    if proposed == '0':
                        raise ValueError('已取消域名配置。')
                    if proposed.isdecimal() and 1 <= int(proposed) <= 65535 and int(proposed) not in (80, 443) and not owners.get(int(proposed)) and ops.port_available(int(proposed)):
                        break
                    print('端口不可用，请重新输入。')
                ops.edit_env(ops.env_path(group), {key: proposed})
                ops.sync_port_urls(group, key, int(value), int(proposed))
                ops.up(group, [service], recreate=True, no_deps=True)


def main():
    if os.geteuid() != 0:
        raise ValueError('域名配置需要宿主机管理权限，请使用 sudo bash deploy.sh 后选择菜单 8。')
    print('配置域名与 HTTPS：1) Studio  2) Workbench  3) MinIO 文件服务  0) 返回')
    target = {'1': 'studio', '2': 'workbench', '3': 'storage'}.get(ops.ask('选择', '0'))
    if not target:
        return
    release_web_ports()
    group, key = TARGETS[target]
    port = int(ops.read_env(ops.env_path(group))[key])
    domain = ops.ask('完整公网域名（例如 workbench.example.com）').lower()
    expected = ops.ask('服务器公网 IP（有 IPv6 时逗号分隔全部 A/AAAA 地址）')
    email = ops.ask('证书通知邮箱')
    print(f'请在域名的 DNS 服务商添加 A/AAAA：{domain} → {expected}。\n暂时关闭 CDN 代理；安全组放行 TCP 80/443。此脚本负责检查 DNS，不会修改 DNS 账户。')
    ops.ask('完成后输入任意字符开始检查，Ctrl-C 返回')
    setup(target, domain, email, port, expected)
    apply_urls(target, domain)
    print('域名、证书和应用环境变量已更新：https://' + domain)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, EOFError, KeyboardInterrupt, subprocess.SubprocessError) as error:
        print('[失败] ' + str(error), file=sys.stderr)
        sys.exit(1)
