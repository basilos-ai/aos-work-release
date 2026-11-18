#!/usr/bin/env python3
"""Deployment operations. No third-party Python dependencies; never source .env as code."""
import argparse
import datetime
import json
import importlib.util
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
PORTS = {
    'middleware': {'postgresql': [('POSTGRES_HOST_PORT', 5432)], 'redis': [('REDIS_HOST_PORT', 6379)],
                   'rabbitmq': [('RABBITMQ_HOST_PORT', 5672), ('RABBITMQ_MANAGEMENT_HOST_PORT', 15672)],
                   'minio': [('MINIO_API_HOST_PORT', 9000), ('MINIO_CONSOLE_HOST_PORT', 9001)]},
    'studio': {'studio': [('STUDIO_API_HOST_PORT', 12001)], 'studio-frontend': [('STUDIO_FRONTEND_HOST_PORT', 80)],
               'node-sandbox': [('NODE_SANDBOX_HOST_PORT', 3000)]},
    'workbench': {'workbench': [('WORKBENCH_HOST_PORT', None)], 'workbench-frontend': [('WORKBENCH_FRONTEND_HOST_PORT', 80)],
                  'workbench-runtime': [('RUNTIME_GATEWAY_HOST_PORT', 3100)]},
}


def run(args, **kw):
    return subprocess.run(args, cwd=ROOT, check=True, **kw)


def capture(args):
    # Compose output can contain secrets. Keep both streams out of the terminal on failure.
    try:
        return run(args, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError:
        raise ValueError('命令检查失败：' + ' '.join(args[:3]) + '；请检查配置、Docker 权限或服务状态。') from None


def ask(label, default=''):
    value = input(f'{label}' + (f' [{default}]' if default else '') + ': ').strip() or default
    if not value:
        raise ValueError('输入为空，操作已取消。')
    return value


def env_path(group):
    return ROOT / ('.env.' + group)


def read_env(path):
    result = {}
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z_][A-Za-z_0-9]*)=(.*)', line)
        if not match or match[1] in result:
            raise ValueError(f'{path.name}:{n} 格式错误或变量重复（不输出变量值）。')
        value = match[2]
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'{path.name}:{n} 引号未闭合。')
            value = value[1:-1]
        result[match[1]] = value
    return result


def atomic_write(path, text):
    if path.is_symlink():
        raise ValueError(f'拒绝写入符号链接：{path}')
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.tmp.')
    with os.fdopen(fd, 'w') as f:
        f.write(text)
    os.replace(temp, path)


def backup(path):
    target = path.with_name(path.name + '.bak.' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    shutil.copy2(path, target)
    target.chmod(0o600)
    return target


def edit_env(path, changes):
    values = read_env(path)
    if all(values.get(k) == v for k, v in changes.items()):
        return
    backup(path)
    lines, seen = [], set()
    for line in path.read_text().splitlines():
        key = line.partition('=')[0]
        if key in changes:
            line = key + '=' + encode(changes[key])
            seen.add(key)
        lines.append(line)
    lines += [k + '=' + encode(v) for k, v in changes.items() if k not in seen]
    atomic_write(path, '\n'.join(lines) + '\n')


def encode(value):
    if any(c in value for c in "'\n\r"):
        raise ValueError('环境变量不能包含单引号或换行。')
    return value if re.fullmatch(r'[A-Za-z0-9_./,:@+-]*', value) else "'" + value + "'"


def compose(group):
    args = ['docker', 'compose', '--env-file', str(env_path('middleware'))]
    if group != 'middleware':
        args += ['--env-file', str(env_path(group)), '-f', str(ROOT / f'docker-compose.{group}.yaml')]
    else:
        files = read_env(env_path(group)).get('COMPOSE_FILE', 'docker-compose.middleware.yaml').split(',')
        for file in files:
            if file not in ['docker-compose.middleware.yaml', 'compose/db.yaml', 'compose/cache.yaml', 'compose/mq.yaml', 'compose/storage.yaml']:
                raise ValueError('COMPOSE_FILE 包含不支持的文件：' + file)
            args += ['-f', str(ROOT / file)]
    return args


def config(group):
    for name in ('middleware', group):
        read_env(env_path(name))
    return json.loads(capture(compose(group) + ['config', '--format', 'json']))


def check_files():
    files = ['deploy.sh', 'deploy-support.py', 'setup-domain-ssl.sh', 'domain-ssl.py', 'install-docker.sh',
             'check-workbench.sh', 'workbench/storage/templates/AGENTS.md', 'workbench/storage/nginx/runtime-nginx.conf']
    files += [f'docker-compose.{g}.yaml' for g in PORTS]
    files += [f'.env.{g}.example' for g in PORTS]
    files += [f'compose/{f}.yaml' for f in ('db', 'cache', 'mq', 'storage')]
    for name in files:
        p = ROOT / name
        if not p.is_file() or p.is_symlink():
            raise ValueError('部署包缺少普通文件：' + name)
    for group in PORTS:
        p, template = env_path(group), ROOT / f'.env.{group}.example'
        expected = read_env(template)
        if not p.exists():
            shutil.copyfile(template, p)
            p.chmod(0o600)
            print('已创建 ' + p.name)
        actual = read_env(p)
        missing = set(expected) - set(actual)
        if missing:
            print(p.name + ' 缺少变量，将从模板补齐：' + ', '.join(sorted(missing)))
            edit_env(p, {k: expected[k] for k in sorted(missing)})
        unresolved = [k for k, v in read_env(p).items() if 'CHANGE_ME' in v]
        if unresolved:
            print(p.name + ' 待配置：' + ', '.join(unresolved))
    print('部署文件结构和环境文件格式检查通过。')


def image_exists(image):
    return subprocess.run(['docker', 'image', 'inspect', image], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def pull_image(image, force=False):
    if not force and image_exists(image):
        print('使用本地镜像：' + image, flush=True)
        return
    while True:
        print('拉取镜像（单次最多 180 秒）：' + image, flush=True)
        try:
            result = subprocess.run(['docker', 'pull', image], timeout=180)
            if result.returncode == 0:
                return
        except subprocess.TimeoutExpired:
            print('镜像下载超时。')
        print('1) 重试  2) 导入离线 docker save 归档后继续  3) 从可信镜像仓库拉取并映射为原标签  0) 返回')
        choice = ask('请选择', '0')
        if choice == '0':
            raise ValueError('镜像未就绪，停止启动服务。已有配置与容器保留。')
        if choice == '2':
            archive = Path(ask('镜像归档绝对路径')).expanduser()
            if not archive.is_file():
                print('归档不存在。'); continue
            run(['docker', 'load', '-i', str(archive)])
            if image_exists(image):
                return
            print('归档没有所需标签：' + image)
        elif choice == '3':
            alternate = ask('输入你确认可信的完整镜像名:tag（或 @sha256）')
            if alternate.startswith('-') or any(c.isspace() for c in alternate):
                raise ValueError('镜像名称无效。')
            try:
                run(['docker', 'pull', alternate], timeout=180)
                run(['docker', 'tag', alternate, image])
                return
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                print('备用镜像拉取失败。')


def port_available(port):
    # Wildcard mappings must not overlap a listener on any local IPv4/IPv6 address.
    for family, host in [(socket.AF_INET, '0.0.0.0'), (socket.AF_INET6, '::')]:
        try:
            with socket.socket(family, socket.SOCK_STREAM) as s:
                if family == socket.AF_INET6:
                    s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                s.bind((host, port))
        except OSError as e:
            if e.errno in (47, 97, 99, 49):  # IPv6 unavailable
                continue
            return False
    return True


def port_owners():
    ids = capture(['docker', 'ps', '-q']).split()
    owners = {}
    if ids:
        for c in json.loads(capture(['docker', 'inspect'] + ids)):
            labels = c['Config'].get('Labels') or {}
            owner = (labels.get('com.docker.compose.project'), labels.get('com.docker.compose.service'))
            for bindings in (c['NetworkSettings'].get('Ports') or {}).values():
                for binding in bindings or []:
                    owners.setdefault(int(binding['HostPort']), set()).add(owner)
    return owners


def replace_http_port(value, old, new):
    p = urlsplit(value)
    if p.scheme == 'http' and p.port == old:
        host = p.hostname
        if ':' in host:
            host = '[' + host + ']'
        return urlunsplit((p.scheme, f'{host}:{new}', p.path, p.query, p.fragment))
    return value


def sync_port_urls(group, key, old, new):
    url_keys = {
        'STUDIO_FRONTEND_HOST_PORT': {'studio': ['ASSETS_SEARCH_SNAPSHOT_URL', 'VIEW_SNAPSHOT_URL']},
        'WORKBENCH_FRONTEND_HOST_PORT': {'workbench': ['APP_URL', 'FRONTEND_URL', 'FRONTEND_OAUTH_RESULT_URL']},
        'WORKBENCH_HOST_PORT': {'workbench': ['APP_URL']},
        'MINIO_API_HOST_PORT': {'middleware': ['MINIO_EXPOSE_URL'], 'workbench': ['MINIO_PUBLIC_BASE_URL']},
    }
    for target, keys in url_keys.get(key, {}).items():
        vals = read_env(env_path(target))
        changes = {k: replace_http_port(vals[k], old, new) for k in keys if vals.get(k)}
        if key == 'MINIO_API_HOST_PORT' and target == 'workbench' and vals.get('MINIO_PRESIGN_USE_SSL') == 'false' and vals.get('MINIO_PRESIGN_PORT') == str(old):
            changes['MINIO_PRESIGN_PORT'] = str(new)
        edit_env(env_path(target), changes)
    # Keep managed reverse proxies consistent; custom Nginx files are never edited.
    spec = importlib.util.spec_from_file_location('basil_domain', ROOT / 'domain-ssl.py')
    domain = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(domain)
    domain.refresh_port(ROOT, group, key, new)


def ensure_ports(group, selected, cfg):
    owners, reserved, changed = port_owners(), {}, False
    for service in selected:
        spec = cfg['services'][service]
        for mapping in spec.get('ports', []):
            old = int(mapping['published'])
            key = next((k for k, target in PORTS.get(group, {}).get(service, []) if target is None or target == int(mapping['target'])), None)
            current = old
            while True:
                owner = (cfg['name'], service)
                active = owners.get(current, set())
                free = active == {owner} or (not active and port_available(current))
                if current not in reserved and free:
                    break
                if key is None:
                    raise ValueError(f'{service} 端口 {current} 冲突，未找到对应 HOST_PORT 变量。')
                print(f'{service} 的宿主机端口 {current} 被占用。')
                val = ask('请输入新端口（1-65535），输入 0 取消')
                if val == '0':
                    raise ValueError('已取消端口调整。')
                if not val.isdecimal() or not 1 <= int(val) <= 65535:
                    print('端口无效。'); continue
                current = int(val)
            reserved[current] = service
            if current != old:
                snapshots = {env_path(g): env_path(g).read_text() for g in PORTS if env_path(g).exists()}
                try:
                    edit_env(env_path(group), {key: str(current)})
                    sync_port_urls(group, key, old, current)
                except BaseException:
                    for path, text in snapshots.items():
                        atomic_write(path, text)
                    raise
                print(f'已保存 {key}={current}，准备自动重试启动。')
                changed = True
    return changed


def select_services(cfg, requested, no_deps=False):
    selected = list(requested or cfg['services'])
    for name in selected:
        if name not in cfg['services']:
            raise ValueError('当前部署未配置服务：' + name)
        if not no_deps:
            for dep in cfg['services'][name].get('depends_on', {}):
                if dep not in selected:
                    selected.append(dep)
    return selected


def up(group, services=(), recreate=False, no_deps=False):
    before = {g: env_path(g).read_text() for g in PORTS if env_path(g).exists()}
    cfg = config(group)
    selected = select_services(cfg, services, no_deps)
    for service in selected:
        if 'CHANGE_ME' in json.dumps(cfg['services'][service]):
            raise ValueError(f'{service} 仍有未配置占位符，请先选择安装菜单完成配置。')
    for image in dict.fromkeys(cfg['services'][s]['image'] for s in selected):
        pull_image(image)
    while True:
        cfg = config(group)
        ensure_ports(group, selected, cfg)
        args = compose(group) + ['up', '-d', '--pull', 'never', '--wait', '--wait-timeout', '300']
        if recreate:
            args.append('--force-recreate')
        if no_deps:
            args.append('--no-deps')
        result = subprocess.run(args + list(services), capture_output=True, text=True, cwd=ROOT)
        # Compose startup logs do not include the full environment; show failures for diagnosis.
        print(result.stdout, end=''); print(result.stderr, end='', file=sys.stderr)
        if result.returncode == 0:
            # A changed direct MinIO URL must also reach already-running application containers.
            if group == 'middleware' and env_path(group).read_text() != before[group]:
                for dependent in ('studio', 'workbench'):
                    if capture(compose(dependent) + ['ps', '-q', dependent]).strip():
                        up(dependent, [dependent], recreate=True, no_deps=True)
            return
        if not re.search(r'port is already allocated|address already in use|ports are not available|failed to bind', result.stderr + result.stdout, re.I):
            raise ValueError('服务未就绪，请用菜单 5 查看健康度及 Compose logs 查看日志；不会重复索要密码。')
        if not ensure_ports(group, selected, config(group)):
            raise ValueError('启动报告端口冲突但无法定位占用，请检查 Docker 和宿主机监听状态。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('check-files')
    check = sub.add_parser('check-images'); check.add_argument('group', choices=PORTS)
    pull = sub.add_parser('pull'); pull.add_argument('image'); pull.add_argument('--force', action='store_true')
    start = sub.add_parser('up'); start.add_argument('group', choices=PORTS); start.add_argument('services', nargs='*')
    start.add_argument('--recreate', action='store_true'); start.add_argument('--no-deps', action='store_true')
    args = parser.parse_args()
    if args.action == 'check-files':
        check_files()
    elif args.action == 'pull':
        pull_image(args.image, args.force)
    elif args.action == 'check-images':
        for image in dict.fromkeys(s['image'] for s in config(args.group)['services'].values()):
            pull_image(image)
    else:
        up(args.group, args.services, args.recreate, args.no_deps)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, EOFError, KeyboardInterrupt, OSError, subprocess.SubprocessError) as error:
        print('[失败] ' + str(error), file=sys.stderr)
        sys.exit(1)
