#!/usr/bin/env bash
# aos-work deployment release: v2026.11.18.2

set -Eeuo pipefail
IFS=$'\n\t'

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export BASIL_DEPLOY_DIR="$DEPLOY_DIR"
SUPPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aos-work.XXXXXXXX")"
trap 'rm -rf -- "$SUPPORT_DIR"' EXIT
cat > "$SUPPORT_DIR/release-install.py" <<'AOS_EMBEDDED_FILE_END'
"""Install public deployment files while preserving the operator's local configuration."""
import argparse
import gzip
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.parse import urlsplit

RELEASES = 'https://github.com/basilos-ai/aos-work-release/releases'
# Newest first. Add the new tag here when preparing a release.
VERSIONS = {
    'v2026.11.18.2': None,
    'v2026.11.18.1': 'e328e235b52651e9e43c857767e4b844944dd1efba61624f7525767c0c705f76',
    'v2026.11.18': 'b7f19f50f985f9fe93ba963cc7cdbbf6310fdc678faa5d1d76970e3b712d3429',
}
ENV = {'.env.' + g for g in ('middleware', 'studio', 'workbench')}
WORKBENCH = {'workbench/storage/templates/AGENTS.md', 'workbench/storage/nginx/runtime-nginx.conf'}
COMMON = WORKBENCH | {'deploy.sh', 'docker-compose.studio.yaml', 'docker-compose.workbench.yaml'}
COMMON.update('compose/' + n + '.yaml' for n in ('db', 'cache', 'mq', 'storage'))
MODERN = COMMON | ENV | {'compose/middleware.yaml'}
LEGACY = COMMON | {n + '.example' for n in ENV} | {
    'docker-compose.middleware.yaml', 'deploy-support.py', 'domain-ssl.py',
    'setup-domain-ssl.sh', 'check-workbench.sh', 'install-docker.sh',
}
MAX_BYTES = 16 * 1024 * 1024


def choose():
    tags = list(VERSIONS)[:5]
    print('选择安装包版本：')
    for i, tag in enumerate(tags, 1):
        print(f'  {i}) {tag}  {RELEASES}/download/{tag}/deploy.tar.gz')
    print(f'更多历史版本：{RELEASES}\n也可粘贴可信来源的 HTTPS 安装包直链（deploy.tar.gz 或 deploy.tar）。')
    value = input('版本序号 / 安装包直链（0 返回）：').strip()
    if value == '0':
        return None
    if value.isdecimal() and 1 <= int(value) <= len(tags):
        return f'{RELEASES}/download/{tags[int(value)-1]}/deploy.tar.gz'
    tag_page = re.fullmatch(re.escape(RELEASES) + r'/tag/([A-Za-z0-9._-]+)', value)
    if tag_page:
        return f'{RELEASES}/download/{tag_page[1]}/deploy.tar.gz'
    check_url(value)
    return value


def check_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('请输入可信的 HTTPS 安装包直链。')
    name = PurePosixPath(parsed.path).name
    if name not in ('deploy.tar.gz', 'deploy.tar'):
        raise ValueError('请粘贴 Release 附件 deploy.tar.gz 或 deploy.tar 的直链。')
    return name


def check_path(root, path):
    # A live deployment may contain user-created symlinks.
    if path.resolve() != path or root not in path.parents:
        raise ValueError(f'拒绝写入符号链接或部署目录之外的路径：{path}')


def unpack(archive, staging):
    if archive.stat().st_size > MAX_BYTES:
        raise ValueError('部署文件包超过大小上限。请选择 deploy.tar.gz 或 deploy.tar。')
    if archive.name.endswith('.gz'):
        with gzip.open(archive, 'rb') as stream:
            if len(stream.read(MAX_BYTES + 1)) > MAX_BYTES:
                raise ValueError('压缩包展开后过大。')
    total = 0
    seen = set()
    with tarfile.open(archive, 'r:*') as bundle:
        for entry in bundle:
            path = PurePosixPath(entry.name)
            if (path.is_absolute() or '..' in path.parts or path in seen or
                    not (entry.isfile() or entry.isdir()) or len(seen) >= 256):
                raise ValueError('压缩包含有不支持或重复的条目。')
            seen.add(path)
            total += entry.size
            if total > MAX_BYTES:
                raise ValueError('解压内容超过大小上限。')
            if entry.isfile() and str(path) in MODERN | LEGACY:
                dest = staging / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(entry) as src, dest.open('xb') as out:
                    shutil.copyfileobj(src, out)
                dest.chmod(0o755 if dest.suffix == '.sh' else 0o600 if dest.name.startswith('.env.') else 0o644)
    for layout in (MODERN, LEGACY):
        if all((staging / n).is_file() for n in layout):
            return layout
    raise ValueError('安装包缺少部署脚本、环境文件或 Compose 配置。')


def install(root, folder, url):
    name = check_url(url)
    archive = folder / name
    check_path(root, archive)
    digest = None
    for tag, known in VERSIONS.items():
        if url == f'{RELEASES}/download/{tag}/deploy.tar.gz':
            digest = known
    sums = folder / 'SHA256SUMS'
    check_path(root, sums)
    if sums.is_file():
        lines = sums.read_text().splitlines()
        matches = [m[1] for line in lines if (m := re.fullmatch(r'([0-9a-f]{64})  '+re.escape(name), line))]
        if len(matches) != 1 or (digest and digest != matches[0]):
            raise ValueError('SHA256SUMS 与所选附件不匹配。')
        digest = matches[0]
    if archive.stat().st_size > MAX_BYTES:
        raise ValueError('请选择部署文件包，当前文件过大。')
    if digest and hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError('SHA-256 不匹配，请重新上传所选版本。')
    with tempfile.TemporaryDirectory(dir=folder) as tmp:
        stage = Path(tmp)
        layout = unpack(archive, stage)
        subprocess.run(['bash', '-n', str(stage / 'deploy.sh')], check=True)
        tag = re.fullmatch(re.escape(RELEASES) + r'/download/([^/]+)/deploy\.tar(?:\.gz)?', url)
        if tag and tag[1] in VERSIONS and VERSIONS[tag[1]] is None:
            marker = '# aos-work deployment release: ' + tag[1]
            if marker not in (stage / 'deploy.sh').read_text().splitlines():
                raise ValueError('包内版本与选择的 Release 不符。')
        # Validate every destination before changing any installed file. Move the entry point last.
        targets = {n: root / ('.aos-selected.sh' if n == 'deploy.sh' else n) for n in layout}
        for dest in targets.values():
            check_path(root, dest)
            if dest.exists() and not dest.is_file():
                raise ValueError(f'文件位置被占用：{dest}')
        for n in sorted(layout, key=lambda n: n == 'deploy.sh'):
            dest = targets[n]
            if n in ENV | WORKBENCH and dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage / n, dest)
        if layout == LEGACY:
            # Keep configured credentials and local service choices across layout changes.
            p = root / '.env.middleware'
            check_path(root, p)
            if p.exists():
                text = p.read_text()
                updated = re.sub(r'^(COMPOSE_FILE=[\x27"]?)compose/middleware\.yaml', r'\1docker-compose.middleware.yaml', text, flags=re.M)
                if updated != text:
                    new = stage / 'middleware.env'
                    new.write_text(updated)
                    new.chmod(0o600)
                    os.replace(new, p)


def offline(folder, name):
    print(f'请访问 {RELEASES} 手动下载同一版本。\n上传到：{folder / name}\n'
          f'可将同一 Release 的 SHA256SUMS 一起上传到 {folder}。上传完成后再次运行 sudo bash deploy.sh。')


def run(root, resume):
    state = root / '.aos-install'
    check_path(root, state)
    state.mkdir(mode=0o700, exist_ok=True)
    lock = state / 'lock'
    check_path(root, lock)
    with lock.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pending = state / 'pending.json'
        check_path(root, pending)
        if resume:
            url = json.loads(pending.read_text())['url']
        else:
            url = choose()
            if url is None:
                return False
        name = check_url(url)
        # Isolate different versions, including different mirrors with the same asset name.
        folder = state / hashlib.sha256(url.encode()).hexdigest()[:12]
        check_path(root, folder)
        folder.mkdir(mode=0o700, exist_ok=True)
        if not resume:
            with tempfile.NamedTemporaryFile(mode='w', dir=state, delete=False) as f:
                json.dump({'url': url}, f)
            os.replace(f.name, pending)
        archive = folder / name
        check_path(root, archive)
        if not archive.is_file():
            if resume:
                offline(folder, name)
                return False
            print('正在下载：' + url, flush=True)
            try:
                with tempfile.NamedTemporaryFile(dir=folder, delete=False) as f:
                    partial = Path(f.name)
                try:
                    subprocess.run(['curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
                                    '--connect-timeout', '10', '--max-time', '120', '--max-filesize', str(MAX_BYTES),
                                    '-o', str(partial), '--', url], check=True)
                    os.replace(partial, archive)
                finally:
                    partial.unlink(missing_ok=True)
            except (OSError, subprocess.CalledProcessError):
                offline(folder, name)
                return False
        try:
            install(root, folder, url)
        except (OSError, ValueError, EOFError, tarfile.TarError, subprocess.CalledProcessError) as error:
            print(f'安装包未通过检查：{error}')
            offline(folder, name)
            return False
        print('已解压所选部署包，开始配置并安装 Studio + Workbench。', flush=True)
        pending.unlink()
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('choose', 'resume'))
    try:
        ready = run(Path(os.environ['BASIL_DEPLOY_DIR']).resolve(), parser.parse_args().action == 'resume')
    except (ValueError, KeyError, OSError, EOFError) as error:
        parser.exit(1, f'安装包处理失败：{error}\n')
    # 2 means cancelled or waiting for upload.
    raise SystemExit(0 if ready else 2)
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/reset-deployment.py" <<'AOS_EMBEDDED_FILE_END'
"""Inventory and remove resources owned by one deployment, after operator confirmation."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

support = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ops', support / 'deploy-support.py')
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)
PROJECT = 'com.docker.compose.project'
OWNER = 'ai.basilos.deploy.directory'
GROUPS = ('workbench', 'studio', 'middleware')


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def objects(kind, ids):
    return json.loads(docker(kind, 'inspect', *ids)) if ids else []


def local_docker():
    endpoint = os.environ.get('DOCKER_HOST', '')
    if os.environ.get('DOCKER_CONTEXT') or not endpoint:
        endpoint = docker('context', 'inspect', '--format', '{{.Endpoints.docker.Host}}')
    if not endpoint.startswith('unix://'):
        raise ValueError('清理需要当前服务器的本地 Docker Unix Socket。')


def local_path(value):
    # Docker Desktop exposes Mac bind sources with a /host_mnt prefix.
    if sys.platform == 'darwin' and value.startswith('/host_mnt/'):
        value = value.removeprefix('/host_mnt')
    return Path(value)


def paths_to_reset(root, env):
    if len(root.parts) < 3 or root == Path.home() or not (root / 'docker-compose.workbench.yaml').is_file():
        raise ValueError('当前目录不是可识别的独立部署目录。')
    files = [root / n for n in ('data/postgresql', 'data/redis', 'data/rabbitmq', 'data/minio',
                                 'data/studio-logs', 'workbench/frontend-logs', '.domains.json', '.aos-install/pending.json')]
    minio = Path(env['middleware'].get('MINIO_DATA_HOST_PATH', './data/minio'))
    custom = (root / minio).resolve()
    if custom.is_relative_to(root / 'data') and custom != root / 'data':
        files.append(custom)
    storage = root / 'workbench/storage'
    if storage.resolve() != storage:
        raise ValueError('Workbench 存储路径包含符号链接，请先核对。')
    if storage.is_dir():
        for child in storage.iterdir():
            if child.name not in ('templates', 'nginx'):
                files.append(child)
            elif child.is_symlink():
                raise ValueError(f'请先核对符号链接：{child}')
            elif child.is_dir():
                keep = 'AGENTS.md' if child.name == 'templates' else 'runtime-nginx.conf'
                files.extend(p for p in child.iterdir() if p.name != keep)
    for g in GROUPS:
        files.append(root / ('.env.' + g))
        files.extend(root.glob('.env.' + g + '.bak*'))
    paths = sorted({p for p in files if p.exists() or p.is_symlink()})
    mounts = set()
    if Path('/proc/self/mountinfo').is_file():
        for row in Path('/proc/self/mountinfo').read_text().splitlines():
            mounts.add(Path(re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), row.split()[4])))
    for p in paths:
        if p.resolve() != p or p.is_mount() or any(m == p or p in m.parents for m in mounts):
            raise ValueError(f'清理范围包含链接或挂载点，请先核对并卸载：{p}')
    return [p for p in paths if not any(parent in paths for parent in p.parents)]


def inventory(root):
    env = {}
    for group in GROUPS:
        path = root / ('.env.' + group)
        env[group] = ops.read_env(path) if path.is_file() else {}
    projects = {values.get('COMPOSE_PROJECT_NAME', 'basil-' + group) for group, values in env.items()}
    images = set()
    for cfg in env.values():
        for k, v in cfg.items():
            tag = cfg.get(k[:-6] + '_VERSION') if k.endswith('_IMAGE') else None
            if tag and v:
                images.add(v + ':' + tag)
    sandbox = env['workbench'].get('RUNTIME_SANDBOX_IMAGE')
    paths = paths_to_reset(root, env)
    own, others = [], []
    for c in objects('container', docker('ps', '-aq', '--no-trunc').splitlines()):
        labels = c['Config'].get('Labels') or {}
        wd = local_path(labels.get(PROJECT + '.working_dir', ''))
        inputs = [local_path(f) for f in labels.get(PROJECT + '.config_files', '').split(',')]
        composed = labels.get(PROJECT) in projects and (wd == root or wd == root / 'compose') and any(
            f in {root / 'docker-compose.studio.yaml', root / 'docker-compose.workbench.yaml',
                  root / 'compose/middleware.yaml', root / 'docker-compose.middleware.yaml'} for f in inputs)
        mounts = [local_path(m['Source']) for m in c['Mounts'] if m['Type'] == 'bind']
        dynamic = (not labels.get(PROJECT) and sandbox and c['Config']['Image'].startswith(sandbox + ':')
                   and any(root / 'workbench/storage/sandbox/workspaces' in p.parents for p in mounts))
        if composed or dynamic:
            own.append(c)
        else:
            others.append(c)
            for p in paths:
                if any(src == p or p in src.parents or src in p.parents for src in mounts):
                    raise ValueError(f'其他容器 {c["Name"]} 也挂载了 {p}，请先处理共享数据。')
    used_images = {c['Image'] for c in others}
    held_vols = {m['Name'] for c in others for m in c['Mounts'] if m['Type'] == 'volume'}
    volumes = {m['Name'] for c in own for m in c['Mounts'] if m['Type'] == 'volume'}
    containers = sorted((c['Id'], c['Name'].lstrip('/')) for c in own)
    nets = {n['NetworkID'] for c in own for n in c['NetworkSettings']['Networks'].values() if n.get('NetworkID')}
    nets.update(docker('network', 'ls', '--no-trunc', '-q', '--filter', 'label='+OWNER+'='+str(root)).splitlines())
    networks = []
    ids = {c['Id'] for c in own}
    kept = []
    for net in objects('network', sorted(nets)):
        label = net.get('Labels') or {}
        if (label.get(OWNER) == str(root) or label.get(PROJECT) in projects) and not set(net.get('Containers') or {}) - ids:
            networks.append((net['Id'], net['Name']))
        else:
            kept.append('共享或外部网络 ' + net['Name'])
    private_volumes = []
    for volume in objects('volume', sorted(volumes)):
        name = volume['Name']
        if name not in held_vols and ((volume.get('Labels') or {}).get(PROJECT) in projects or re.fullmatch('[0-9a-f]{64}', name)):
            private_volumes.append(name)
        else:
            kept.append('共享或外部卷 ' + name)
    images.update(c['Config']['Image'] for c in own)
    used_by_own = {c['Image'] for c in own}
    remove_images = []
    tags_by_id = {}
    for line in docker('image', 'ls', '-a', '--no-trunc', '--format', '{{.ID}} {{.Repository}}:{{.Tag}}').splitlines():
        image_id, tag = line.split(' ', 1)
        tags = tags_by_id.setdefault(image_id, set())
        if not tag.endswith(':<none>'):
            tags.add(tag)
    for image_id, tags in tags_by_id.items():
        refs = (tags & images)
        if not tags and image_id in used_by_own:
            refs.add(image_id)
        if image_id in used_images:
            kept.extend('其他容器使用镜像 ' + ref for ref in refs)
        else:
            remove_images.extend((ref, image_id) for ref in refs)
    custom = (root / env['middleware'].get('MINIO_DATA_HOST_PATH', './data/minio')).resolve()
    if not custom.is_relative_to(root / 'data'):
        kept.append('自定义对象存储路径 ' + str(custom))
    proxies = []
    state = root / '.domains.json'
    if state.is_file():
        spec = importlib.util.spec_from_file_location('domain', support / 'domain-ssl.py')
        domain = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(domain)
        for target, settings in json.loads(state.read_text()).items():
            if target not in domain.TARGETS:
                continue
            site = domain.NGINX_DIR / ('basil-' + target + '.conf')
            if site.is_file():
                expected = domain.nginx_text(settings['domain'], settings['port'], True)
                if not site.is_symlink() and site.read_text() == expected:
                    proxies.append(site)
                else:
                    kept.append('已另行修改的 Nginx 配置 ' + str(site))
    return dict(containers=containers, proxies=sorted(proxies), networks=sorted(networks), volumes=sorted(private_volumes),
                images=sorted(remove_images), paths=paths, kept=sorted(kept))


def reset(root):
    local_docker()
    plan = inventory(root)
    print(f'完全清理当前部署 {root}。本地数据库、上传文件及密钥将永久删除。')
    for title, entries in [('容器', [v for _, v in plan['containers']]), ('镜像', [v for v, _ in plan['images']]),
                           ('卷', plan['volumes']), ('网络', [v for _, v in plan['networks']]),
                           ('部署创建的 Nginx 站点', plan['proxies']), ('本地配置和数据', plan['paths']), ('保留', plan['kept'])]:
        print(title + '：' + ('、'.join(map(str, entries)) or '无'))
    print('保留安装脚本、部署模板、已下载安装包、外部服务及宿主机证书。')
    if input(f'输入 DELETE {root} 确认，其他输入取消：') != f'DELETE {root}':
        print('已取消。')
        return
    if inventory(root) != plan:
        raise ValueError('部署资源发生变化，请重新预览。')
    if plan['proxies']:
        saved = {p: p.read_bytes() for p in plan['proxies']}
        try:
            for site in saved:
                site.unlink()
            subprocess.run(['nginx', '-t'], check=True)
            subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
        except (OSError, subprocess.CalledProcessError):
            for site, data in saved.items():
                site.write_bytes(data)
            raise
    for cid, name in plan['containers']:
        print('停止 ' + name, flush=True)
        docker('stop', cid)
    for cid, _ in plan['containers']:
        docker('rm', cid)
    for vol in plan['volumes']:
        docker('volume', 'rm', vol)
    for nid, _ in plan['networks']:
        docker('network', 'rm', nid)
    for ref, image_id in plan['images']:
        if docker('image', 'inspect', '--format', '{{.Id}}', ref) != image_id:
            raise ValueError(f'镜像标签已变化，请重新预览：{ref}')
        docker('image', 'rm', ref)
    # Recheck consumers before unlinking data; a concurrently created sandbox must be stopped first.
    remaining = inventory(root)
    if remaining['containers'] or remaining['paths'] != plan['paths']:
        raise ValueError('数据或容器状态已变化，请重新预览后继续清理。')
    for path in plan['paths']:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    print('当前部署已清理。重新选择菜单 1 可从头配置并安装。')


if __name__ == '__main__':
    try:
        reset(Path(os.environ['BASIL_DEPLOY_DIR']).resolve())
    except (OSError, ValueError, EOFError, subprocess.CalledProcessError) as error:
        sys.exit(f'清理未完成：{error}')
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/deploy-support.py" <<'AOS_EMBEDDED_FILE_END'
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

SUPPORT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("BASIL_DEPLOY_DIR", SUPPORT))
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
    args = ['docker', 'compose', '--project-directory', str(ROOT), '--env-file', str(env_path('middleware'))]
    if group != 'middleware':
        args += ['--env-file', str(env_path(group)), '-f', str(ROOT / f'docker-compose.{group}.yaml')]
    else:
        files = read_env(env_path(group)).get('COMPOSE_FILE', 'compose/middleware.yaml').split(',')
        for file in files:
            if file == 'docker-compose.middleware.yaml':  # previously shipped layout
                file = 'compose/middleware.yaml'
            if file not in ['compose/middleware.yaml', 'compose/db.yaml', 'compose/cache.yaml', 'compose/mq.yaml', 'compose/storage.yaml']:
                raise ValueError('COMPOSE_FILE 包含不支持的文件：' + file)
            args += ['-f', str(ROOT / file)]
    return args


def config(group):
    for name in ('middleware', group):
        read_env(env_path(name))
    return json.loads(capture(compose(group) + ['config', '--format', 'json']))


def check_files():
    files = ['deploy.sh', 'docker-compose.studio.yaml', 'docker-compose.workbench.yaml',
             'workbench/storage/templates/AGENTS.md', 'workbench/storage/nginx/runtime-nginx.conf']
    files += [f'compose/{name}.yaml' for name in ('middleware', 'db', 'cache', 'mq', 'storage')]
    for name in files:
        p = ROOT / name
        if not p.is_file() or p.is_symlink():
            raise ValueError('部署包缺少普通文件：' + name)
    for group in PORTS:
        p, template = env_path(group), SUPPORT / f'.env.{group}.example'
        if p.is_symlink() or (p.exists() and not p.is_file()):
            raise ValueError('环境文件必须是普通文件：' + p.name)
        expected = read_env(template)
        if not p.exists():
            shutil.copyfile(template, p)
            p.chmod(0o600)
            print('已创建 ' + p.name)
        p.chmod(0o600)
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
    spec = importlib.util.spec_from_file_location('basil_domain', SUPPORT / 'domain-ssl.py')
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
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/domain-ssl.py" <<'AOS_EMBEDDED_FILE_END'
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

SUPPORT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("BASIL_DEPLOY_DIR", SUPPORT))
NGINX_DIR = Path('/etc/nginx/conf.d')
ACME_DIR = Path('/var/www/basil-acme')
spec = importlib.util.spec_from_file_location('basil_ops', SUPPORT / 'deploy-support.py')
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
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/install-docker.sh" <<'AOS_EMBEDDED_FILE_END'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo '请使用 sudo bash deploy.sh，再选择环境检查。' >&2; exit 1; }
[[ -f /etc/os-release ]] || { echo '请手动安装 Docker Engine 与 Compose 插件。'; exit 1; }
. /etc/os-release
[[ "$ID" == ubuntu || "$ID" == debian ]] || { echo '自动安装支持 Ubuntu/Debian；其他系统请先安装 Docker 与 Compose 插件。'; exit 1; }
apt-get update
apt-get install -y ca-certificates curl python3 iproute2 gnupg
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  exit
fi
if command -v docker >/dev/null && ! docker compose version >/dev/null 2>&1; then
  if apt-cache show docker-compose-plugin >/dev/null 2>&1; then
    apt-get install -y docker-compose-plugin
    exit
  fi
  # Preserve existing distribution packages instead of replacing a live engine.
  if dpkg-query -W -f='${Status}' docker.io 2>/dev/null | grep -q 'install ok installed'; then
    apt-get install -y docker-compose-v2
    exit
  fi
fi
install -m 0755 -d /etc/apt/keyrings
key_file="$(mktemp)"
trap 'rm -f "$key_file"' EXIT
repo="https://download.docker.com/linux/$ID"
if ! curl -fSL --retry 2 --connect-timeout 10 --max-time 40 "$repo/gpg" -o "$key_file"; then
  repo="https://mirrors.aliyun.com/docker-ce/linux/$ID"
  echo 'Docker 官方下载连接失败，尝试阿里云 Docker CE 软件包镜像。'
  curl -fSL --retry 2 --connect-timeout 10 --max-time 40 "$repo/gpg" -o "$key_file"
fi
# Pin Docker's signing key, including when obtained from the mirror.
gpg --show-keys --with-colons "$key_file" | grep -q '9DC858229FC7DD38854AE2D88D81803C0EBFCD88' || { echo 'Docker 签名密钥指纹不匹配。'; exit 1; }
install -m 0644 "$key_file" /etc/apt/keyrings/basil-docker.asc
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/basil-docker.asc] %s %s stable\n' "$(dpkg --print-architecture)" "$repo" "${UBUNTU_CODENAME:-$VERSION_CODENAME}" > /etc/apt/sources.list.d/basil-docker.list
apt-get update
if command -v docker >/dev/null; then
  apt-get install -y docker-compose-plugin
else
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
docker compose version
docker info >/dev/null
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/setup-domain-ssl.sh" <<'AOS_EMBEDDED_FILE_END'
#!/usr/bin/env bash
set -Eeuo pipefail
DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$DEPLOY_DIR/domain-ssl.py" "$@"
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/check-workbench.sh" <<'AOS_EMBEDDED_FILE_END'
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.workbench}"
UPDATED_COUNT=0

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

pass() {
  printf '[PASS] %s\n' "$*"
}

info() {
  printf '[INFO] %s\n' "$*"
}

read_env() {
  local key="$1"
  awk -F= -v key="${key}" '
    $1 == key {
      value = substr($0, index($0, "=") + 1)
      sub(/\r$/, "", value)
      print value
      exit
    }
  ' "${ENV_FILE}"
}

write_env() {
  local key="$1"
  local value="$2"
  local current_value temp_file

  current_value="$(read_env "${key}")"
  if [[ "${current_value}" == "${value}" ]]; then
    pass "${key}=${value}"
    return
  fi

  temp_file="$(mktemp "${ENV_FILE}.tmp.XXXXXX")"
  if ! awk -F= -v key="${key}" -v value="${value}" '
    BEGIN { written = 0 }
    $1 == key {
      if (!written) {
        print key "=" value
        written = 1
      }
      next
    }
    { print }
    END {
      if (!written) print key "=" value
    }
  ' "${ENV_FILE}" >"${temp_file}"; then
    rm -f "${temp_file}"
    fail "无法更新 ${ENV_FILE} 中的 ${key}"
  fi

  chmod 600 "${temp_file}"
  mv "${temp_file}" "${ENV_FILE}"
  UPDATED_COUNT=$((UPDATED_COUNT + 1))
  info "已修正 ${key}: ${current_value:-<未配置>} -> ${value}"
}

append_candidate() {
  local candidate="$1"
  local existing
  [[ -n "${candidate}" ]] || return
  for existing in "${SOCKET_CANDIDATES[@]:-}"; do
    [[ "${existing}" == "${candidate}" ]] && return
  done
  SOCKET_CANDIDATES+=("${candidate}")
}

socket_responds() {
  local socket_path="$1"
  [[ -S "${socket_path}" ]] || return 1
  docker --host "unix://${socket_path}" version --format '{{.Server.Version}}' >/dev/null 2>&1
}

resolve_docker_socket() {
  local configured_socket context_host candidate
  configured_socket="$(read_env RUNTIME_DOCKER_SOCKET_PATH)"
  append_candidate "${configured_socket}"

  if [[ "${DOCKER_HOST:-}" == unix://* ]]; then
    append_candidate "${DOCKER_HOST#unix://}"
  fi

  context_host="$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)"
  if [[ "${context_host}" == unix://* ]]; then
    append_candidate "${context_host#unix://}"
  fi

  append_candidate '/var/run/docker.sock'
  append_candidate "/run/user/$(id -u)/docker.sock"
  if [[ -n "${HOME:-}" ]]; then
    append_candidate "${HOME}/.docker/run/docker.sock"
  fi

  for candidate in "${SOCKET_CANDIDATES[@]}"; do
    if socket_responds "${candidate}"; then
      printf '%s' "${candidate}"
      return
    fi
  done

  return 1
}

read_socket_gid() {
  local socket_path="$1"
  local gid
  # Docker Desktop 将挂载到 Linux 容器内的 Engine Socket 表现为 root:root；
  # macOS 宿主机 Socket 文件自身的组 ID 不能直接用于容器 group_add。
  if [[ "$(uname -s)" == 'Darwin' ]]; then
    printf '0'
    return
  fi
  if gid="$(stat -c '%g' "${socket_path}" 2>/dev/null)"; then
    printf '%s' "${gid}"
    return
  fi
  if gid="$(stat -f '%g' "${socket_path}" 2>/dev/null)"; then
    printf '%s' "${gid}"
    return
  fi
  return 1
}

main() {
  local docker_socket docker_gid
  SOCKET_CANDIDATES=()

  [[ -e "${ENV_FILE}" ]] || fail "未找到 ${ENV_FILE}；请先从 .env.workbench.example 创建该文件"
  [[ -f "${ENV_FILE}" ]] || fail "${ENV_FILE} 不是普通文件"
  [[ ! -L "${ENV_FILE}" ]] || fail "拒绝修改符号链接环境文件：${ENV_FILE}"
  command -v docker >/dev/null 2>&1 || fail '缺少 docker 命令'
  command -v stat >/dev/null 2>&1 || fail '缺少 stat 命令'

  docker_socket="$(resolve_docker_socket)" || \
    fail '未找到当前用户可访问且 Docker Engine 能响应的 Unix Socket'
  docker_gid="$(read_socket_gid "${docker_socket}")" || \
    fail "无法读取 Docker Socket GID：${docker_socket}"
  [[ "${docker_gid}" =~ ^[0-9]+$ ]] || fail "Docker Socket GID 非法：${docker_gid}"

  # 当前发布镜像合同：Workbench 以 root 管理目录，Sandbox 以 1000:10001 运行。
  write_env USER_STORAGE_OWNER_UID 0
  write_env USER_STORAGE_GID 10001
  write_env SANDBOX_WORKSPACE_OWNER_UID 0
  write_env SANDBOX_WORKSPACE_UID 1000
  write_env SANDBOX_WORKSPACE_GID 10001
  write_env RUNTIME_DOCKER_SOCKET_PATH "${docker_socket}"
  write_env RUNTIME_DOCKER_GID "${docker_gid}"

  if ((UPDATED_COUNT > 0)); then
    pass "已更新 ${ENV_FILE}，共修正 ${UPDATED_COUNT} 项"
  else
    pass "${ENV_FILE} 中的 UID/GID 与 Docker Socket 配置均正确"
  fi
  info '脚本未检查或修改镜像、密钥、域名、容器状态、HTTP 服务和业务功能'
}

main "$@"
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/.env.middleware.example" <<'AOS_EMBEDDED_FILE_END'
# Compose
COMPOSE_PROJECT_NAME=basil-middleware
COMPOSE_PATH_SEPARATOR=,
COMPOSE_FILE=compose/middleware.yaml
BASIL_NETWORK_NAME=basilos
TZ=Asia/Shanghai

# 中间件镜像
POSTGRES_IMAGE=registry.cn-hangzhou.aliyuncs.com/tyrion-image/pgvector
POSTGRES_VERSION=pg16
REDIS_IMAGE=registry.cn-hangzhou.aliyuncs.com/tyrion-image/redis
REDIS_VERSION=7.2.4
RABBITMQ_IMAGE=registry.cn-hangzhou.aliyuncs.com/tyrion-image/rabbitmq
RABBITMQ_VERSION=3-management
MINIO_IMAGE=registry.cn-hangzhou.aliyuncs.com/tyrion-image/minio
MINIO_VERSION=2024.8.3

# 宿主机映射端口
POSTGRES_HOST_PORT=5432
REDIS_HOST_PORT=6379
RABBITMQ_HOST_PORT=5672
RABBITMQ_MANAGEMENT_HOST_PORT=15672
MINIO_API_HOST_PORT=9000
MINIO_CONSOLE_HOST_PORT=9001

# PostgreSQL
POSTGRESQL_HOST=CHANGE_ME_POSTGRESQL_HOST
POSTGRESQL_PORT=5432
POSTGRESQL_USERNAME=basilos
POSTGRESQL_PASSWORD=CHANGE_ME_POSTGRESQL_PASSWORD
POSTGRESQL_BOOTSTRAP_DATABASE=basilos

# Redis
REDIS_HOST=CHANGE_ME_REDIS_HOST
REDIS_PORT=6379
REDIS_PASSWORD=CHANGE_ME_REDIS_PASSWORD
REDIS_SSL=false

# RabbitMQ
RABBITMQ_HOST=CHANGE_ME_RABBITMQ_HOST
RABBITMQ_PORT=5672
RABBITMQ_MANAGEMENT_PORT=15672
RABBITMQ_USERNAME=basilos
RABBITMQ_PASSWORD=CHANGE_ME_RABBITMQ_PASSWORD
RABBITMQ_VIRTUAL_HOST=/basilos

# 对象存储：MinIO
FILE_SERVICE_SELECTOR=minio
MINIO_EXPOSE_URL=https://CHANGE_ME_STORAGE_DOMAIN
MINIO_HOST=CHANGE_ME_MINIO_HOST
MINIO_PORT=9000
MINIO_USERNAME=CHANGE_ME_MINIO_USERNAME
MINIO_PASSWORD=CHANGE_ME_MINIO_PASSWORD
MINIO_DATA_HOST_PATH=./data/minio
MINIO_DATA_CONTAINER_PATH=/bitnami/minio/data

# 对象存储：阿里云 OSS
ALI_OSS_ACCESS_ID=
ALI_OSS_ACCESS_KEY=
ALI_OSS_ENDPOINT=

# 对象存储：Azure Blob
AZURE_BLOB_ACCOUNT_NAME=
AZURE_BLOB_ACCOUNT_KEY=
AZURE_BLOB_ENDPOINT=
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/.env.studio.example" <<'AOS_EMBEDDED_FILE_END'
# Compose
COMPOSE_PROJECT_NAME=basil-studio
COMPOSE_PATH_SEPARATOR=,
COMPOSE_FILE=docker-compose.studio.yaml

# Studio 镜像：2026-11-16 本地验证组合；正式服务器仍须按部署流程验收。
STUDIO_IMAGE=ghcr.io/basilos-ai/studio-backend
STUDIO_VERSION=v1.8.10
STUDIO_FRONTEND_IMAGE=ghcr.io/basilos-ai/studio-frontend
STUDIO_FRONTEND_VERSION=v1.8.11
NODE_SANDBOX_IMAGE=ghcr.io/basilos-ai/studio-node-sandbox
NODE_SANDBOX_VERSION=v1.0.0

# Studio 宿主机映射端口
STUDIO_API_HOST_PORT=12001
STUDIO_FRONTEND_HOST_PORT=12000
NODE_SANDBOX_HOST_PORT=12002

# Studio 运行配置
JAVA_OPTS=-Xms1g -Xmx2g
SPRING_PROFILES_ACTIVE=docker
ENCRYPTOR_PASSWORD=CHANGE_ME_ENCRYPTOR_PASSWORD
# 私有化部署固定为 false，deploy.sh 在部署 Studio 时会强制校正。
ENABLE_HTTPS_COOKIES=false
FLOW_NODE_CALL_DEPTH=100
SANDBOX_READ_TIMEOUT_SECOND=600

# Studio 接口返回的前端页面地址
ASSETS_SEARCH_SNAPSHOT_URL=https://CHANGE_ME_STUDIO_FRONTEND_DOMAIN/basilos/asset/search-embed
VIEW_SNAPSHOT_URL=https://CHANGE_ME_STUDIO_FRONTEND_DOMAIN/basilos/studio/engine/multi-dim-table-embed

# Studio 数据库
POSTGRESQL_DATABASE=basilos

# Studio Redis 逻辑库
REDIS_DATABASE=0

# Studio 对象存储空间
FILE_SERVICE_PRIVATE_BUCKET_NAME=studio-private
FILE_SERVICE_PUBLIC_BUCKET_NAME=studio-public
ALI_OSS_BUCKET_NAME=
AZURE_BLOB_CONTAINER=

# 向量数据库：默认使用 PostgreSQL
VECTOR_DATABASE_SELECTOR=postgresql
WEAVIATE_HOST=http://weaviate
WEAVIATE_PORT=8080
WEAVIATE_API_KEY=

# 可选：OAuth2
PUB_KEY=
OAUTH2_DISCOVERY_URL=
OAUTH2_CLIENT_ID=
OAUTH2_CLIENT_SECRET=
OAUTH2_REDIRECT_URI=
OAUTH2_SCOPE=openid,profile,email
OAUTH2_HOME_URI=
OAUTH2_AUTHORIZED_URI=
OAUTH2_TOKEN_URI=

# 可选：SAML
SAML_SP_ENTITY_ID=
SAML_IDP_SSO_URL=
SAML_ACS_URI=
SAML_HOME_URI=
SAML_PUBLIC_KEY=

# 可选：内容与数据集成
TEXT_IN_APP_ID=
TEXT_IN_SECRET_CODE=
MINERU_HOST=
DATA_QUERY_BASE_URL=
HANDLE_CONTENT_PARSE_CONCURRENCY=2
HANDLE_PRO_KNOWLEDGE_BASE_PARSE_QUEUE_CONCURRENCY=2

# 可选：企业微信
WX_CP_CORP_ID=
WX_CP_AGENT_ID=
WX_CP_SECRET=
WX_CP_REDIRECT_URI=
WX_CP_HOME_BASE_URL=
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/.env.workbench.example" <<'AOS_EMBEDDED_FILE_END'
# Compose
COMPOSE_PROJECT_NAME=basil-workbench
COMPOSE_PATH_SEPARATOR=
COMPOSE_FILE=docker-compose.workbench.yaml
WORKBENCH_DEPLOYMENT_ROOT=/data/basil

# GitHub GHCR 镜像；各组件默认使用 latest 标签，安装/重启优先使用缓存，菜单 4 显式更新
WORKBENCH_IMAGE=ghcr.io/basilos-ai/workbench-backend
WORKBENCH_VERSION=latest
WORKBENCH_FRONTEND_IMAGE=ghcr.io/basilos-ai/workbench-frontend
WORKBENCH_FRONTEND_VERSION=latest
RUNTIME_IMAGE=ghcr.io/basilos-ai/workbench-runtime
RUNTIME_VERSION=latest
RUNTIME_SANDBOX_IMAGE=ghcr.io/basilos-ai/workbench-runtime-sandbox
RUNTIME_SANDBOX_VERSION=latest
RUNTIME_NGINX_IMAGE=nginx
RUNTIME_NGINX_VERSION=1.29-alpine
WORKBENCH_FRONTEND_PLATFORM=linux/amd64

SERVER_HOST=http://workbench:3000

# 对外访问和宿主机端口
APP_URL=CHANGE_ME_WORKBENCH_API_URL
FRONTEND_URL=CHANGE_ME_WORKBENCH_FRONTEND_URL
FRONTEND_OAUTH_RESULT_URL=CHANGE_ME_WORKBENCH_FRONTEND_URL
WORKBENCH_HOST_PORT=11001
WORKBENCH_FRONTEND_HOST_PORT=11007
RUNTIME_GATEWAY_HOST_PORT=11002

# Workbench 前端访问 Studio 平台网关
BASILOS_GATEWAY_HOST=CHANGE_ME_GATEWAY_URL
# 可选：任务产出保存到 Library 时使用；不使用该能力则留空
ASSETS_BASE_URL=
DESKTOP_DOWNLOAD_BASE_URL=https://tyrion-team.oss-cn-shanghai.aliyuncs.com/Workbench

# Workbench 与 Runtime 数据库
POSTGRESQL_DATABASE=basilos
RUNTIME_DB_DATABASE=basilos
DB_SCHEMA=workbench
RUNTIME_DB_SCHEMA=runtime
JWT_SECRET=CHANGE_ME_RANDOM_JWT_SECRET
ENCRYPTION_KEY=CHANGE_ME_RANDOM_ENCRYPTION_KEY
# 仅用于后台新建/重置用户；内置 admin 的初始密码由镜像迁移脚本决定，首次登录必须修改。
DEFAULT_USER_PASSWORD=CHANGE_ME_DEFAULT_USER_PASSWORD

# Workbench/Runtime 当前客户端的 URL 输入写法；解析后连接共享的 /basilos VHost。
RABBITMQ_VIRTUAL_HOST=//basilos
REDIS_DATABASE=1
RUNTIME_HTTP_SERVICE_TOKEN=CHANGE_ME_RUNTIME_HTTP_SERVICE_TOKEN
RUNTIME_TO_WORKBENCH_SERVICE_TOKEN=CHANGE_ME_RUNTIME_TO_WORKBENCH_SERVICE_TOKEN
WORKBENCH_INTERNAL_BASE_URL=http://workbench:3000

# 对话输出与 URL 附件
RUNTIME_MODEL_MAX_TOKENS=65536
INTEGRATION_ATTACHMENT_URL_MODE=public-https

# Storage 初始化与 Runtime Sandbox；部署脚本自动校正以下 UID/GID 与 Docker Socket 配置。
# workbench-storage-init 使用以下 UID/GID 创建共享目录，只处理顶层权限，不递归改写已有数据。
AGENT_RUNTIME_ENABLED=true
RUNTIME_SANDBOX_ENABLED=true
RUNTIME_SANDBOX_HOST_ID=CHANGE_ME_SANDBOX_HOST_ID
RUNTIME_SANDBOX_NETWORK=bridge
RUNTIME_DOCKER_SOCKET_PATH=/var/run/docker.sock
RUNTIME_DOCKER_GID=CHANGE_ME_DOCKER_SOCKET_GID
USER_STORAGE_OWNER_UID=0
USER_STORAGE_GID=10001
SANDBOX_WORKSPACE_OWNER_UID=0
SANDBOX_WORKSPACE_UID=1000
SANDBOX_WORKSPACE_GID=10001
RUNTIME_SANDBOX_CPU_LIMIT=2
RUNTIME_SANDBOX_MEMORY_LIMIT_MB=2048
RUNTIME_SANDBOX_PIDS_LIMIT=256

# Workbench 对象存储空间
MINIO_BUCKET=bascilclaw
MINIO_REGION=us-east-1
STORAGE_PRESIGNED_URL_EXPIRES_SECONDS=3600

# 可选：注册邮件、故障告警和 APM；未启用时保持关闭或留空
MAIL_TRANSPORT=disabled
INCIDENT_ALERT_ENABLED=false
INCIDENT_ALERT_WEBHOOK_URL=
ARMS_MONITORING_ENABLED=false
ARMS_APP_NAME=
ARMS_REGION_ID=
ARMS_LICENSE_KEY=
ARMS_WORKSPACE=
AOS_EMBEDDED_FILE_END
ENV_FILE="$DEPLOY_DIR/.env.middleware"
ENV_TEMPLATE="$SUPPORT_DIR/.env.middleware.example"
STUDIO_ENV_FILE="$DEPLOY_DIR/.env.studio"
STUDIO_ENV_TEMPLATE="$SUPPORT_DIR/.env.studio.example"
MIDDLEWARE_COMPOSE_FILE="$DEPLOY_DIR/compose/middleware.yaml"
STUDIO_COMPOSE_FILE="$DEPLOY_DIR/docker-compose.studio.yaml"
WORKBENCH_ENV_FILE="$DEPLOY_DIR/.env.workbench"
WORKBENCH_ENV_TEMPLATE="$SUPPORT_DIR/.env.workbench.example"
WORKBENCH_COMPOSE_FILE="$DEPLOY_DIR/docker-compose.workbench.yaml"
WORKBENCH_CHECK_SCRIPT="$SUPPORT_DIR/check-workbench.sh"
COMPOSE_FILES="compose/middleware.yaml"
POSTGRES_MODE=external
REDIS_MODE=external
RABBITMQ_MODE=external
STORAGE_MODE=external
SELECTED_MODE=
SELECTED_PROVIDER=
DEPLOYMENT_ACCESS_HOST=

info() {
  printf '\n==> %s\n' "$*"
}

success() {
  printf '[通过] %s\n' "$*"
}

warn() {
  printf '[注意] %s\n' "$*" >&2
}

die() {
  printf '[失败] %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"
}

prompt_required() {
  local variable_name="$1"
  local label="$2"
  local default_value="${3-}"
  local input_value=""

  while [[ -z "$input_value" ]]; do
    if [[ -n "$default_value" ]]; then
      read -r -p "$label [$default_value]: " input_value
      input_value="${input_value:-$default_value}"
    else
      read -r -p "$label: " input_value
    fi
    if [[ "$input_value" == *"'"* ]]; then
      warn "输入不能包含英文单引号。"
      input_value=""
    fi
  done

  printf -v "$variable_name" '%s' "$input_value"
}

prompt_port() {
  local variable_name="$1"
  local label="$2"
  local default_value="$3"
  local value=""

  while true; do
    prompt_required value "$label" "$default_value"
    if [[ "$value" =~ ^[0-9]+$ ]] && ((value >= 1 && value <= 65535)); then
      printf -v "$variable_name" '%s' "$value"
      return
    fi
    warn "端口必须是 1 到 65535 之间的整数。"
    value=""
  done
}

image_version_valid() {
  [[ "$1" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]
}

prompt_image_version() {
  local variable_name="$1"
  local label="$2"
  local default_value="$3"
  local value=""

  while true; do
    prompt_required value "$label" "$default_value"
    if image_version_valid "$value" && [[ "$value" != CHANGE_ME* ]]; then
      printf -v "$variable_name" '%s' "$value"
      return
    fi
    warn "镜像版本不是有效的 Docker tag。"
    value=""
  done
}

prompt_url() {
  local variable_name="$1"
  local label="$2"
  local default_value="${3-}"
  local value=""

  while true; do
    prompt_required value "$label" "$default_value"
    if [[ "$value" == http://* || "$value" == https://* ]]; then
      printf -v "$variable_name" '%s' "${value%/}"
      return
    fi
    warn "地址必须以 http:// 或 https:// 开头。"
    value=""
  done
}

ensure_deployment_access_host() {
  local value=""

  [[ -n "$DEPLOYMENT_ACCESS_HOST" ]] && return
  while true; do
    prompt_required value "部署服务器对外访问 IP 或域名（IPv6 使用 []，不含协议和端口）"
    if [[ "$value" != *://* && "$value" != */* && "$value" != *[[:space:]]* &&
      ( "$value" != *:* || "$value" == \[*\] ) ]]; then
      DEPLOYMENT_ACCESS_HOST="$value"
      return
    fi
    warn "请只输入 IP 或域名（IPv6 使用 []），不要包含协议、端口或路径。"
    value=""
  done
}

deployment_access_url() {
  local port="$1"
  local host="$DEPLOYMENT_ACCESS_HOST"

  printf 'http://%s:%s' "$host" "$port"
}

prompt_secret_confirm() {
  local variable_name="$1"
  local label="$2"
  local first=""
  local second=""

  while true; do
    read -r -s -p "$label: " first
    printf '\n'
    read -r -s -p "再次确认$label: " second
    printf '\n'
    if [[ -z "$first" ]]; then
      warn "密码或密钥不能为空。"
    elif [[ "$first" == *"'"* ]]; then
      warn "密码或密钥不能包含英文单引号。"
    elif [[ "$first" != "$second" ]]; then
      warn "两次输入不一致，请重新输入。"
    else
      printf -v "$variable_name" '%s' "$first"
      return
    fi
  done
}

confirm() {
  local label="$1"
  local default_answer="${2:-y}"
  local answer=""
  local hint='[Y/n]'

  [[ "$default_answer" == n ]] && hint='[y/N]'
  while true; do
    read -r -p "$label $hint: " answer
    answer="${answer:-$default_answer}"
    case "$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')" in
      y | yes) return 0 ;;
      n | no) return 1 ;;
      *) warn "请输入 y 或 n。" ;;
    esac
  done
}

choose_mode() {
  local service_name="$1"
  local choice=""

  while true; do
    printf '\n%s 部署方式：\n' "$service_name"
    printf '  1) 本地：由 Docker Compose 部署\n'
    printf '  2) 线上：连接外部服务\n'
    read -r -p '请选择 [1-2]: ' choice
    case "$choice" in
      1) SELECTED_MODE=local; return ;;
      2) SELECTED_MODE=external; return ;;
      *) warn "请输入 1 或 2。" ;;
    esac
  done
}

choose_storage_provider() {
  local choice=""

  while true; do
    printf '\n外部存储类型：\n'
    printf '  1) MinIO\n'
    printf '  2) 阿里云 OSS\n'
    printf '  3) Azure Blob\n'
    read -r -p '请选择 [1-3]: ' choice
    case "$choice" in
      1) SELECTED_PROVIDER=minio; return ;;
      2) SELECTED_PROVIDER=aliyun-oss; return ;;
      3) SELECTED_PROVIDER=azure-blob; return ;;
      *) warn "请输入 1、2 或 3。" ;;
    esac
  done
}

dotenv_encode() {
  local value="$1"
  if [[ "$value" =~ ^[A-Za-z0-9_./,:@+-]*$ ]]; then
    printf '%s' "$value"
    return
  fi
  [[ "$value" != *"'"* ]] || die "环境变量值不能包含英文单引号，请更换输入。"
  printf "'%s'" "$value"
}

set_env_in_file() {
  local target_file="$1"
  local key="$2"
  local value="$3"
  local encoded=""
  local temporary_file=""

  encoded="$(dotenv_encode "$value")"
  temporary_file="$(mktemp "${target_file}.tmp.XXXXXX")"
  BASIL_DEPLOY_ENV_KEY="$key" BASIL_DEPLOY_ENV_VALUE="$encoded" \
    awk '
      BEGIN {
        key = ENVIRON["BASIL_DEPLOY_ENV_KEY"]
        replacement = key "=" ENVIRON["BASIL_DEPLOY_ENV_VALUE"]
      }
      index($0, key "=") == 1 {
        print replacement
        found = 1
        next
      }
      { print }
      END {
        if (!found) print replacement
      }
    ' "$target_file" > "$temporary_file"
  mv "$temporary_file" "$target_file"
  chmod 600 "$target_file"
}

set_env() {
  set_env_in_file "$ENV_FILE" "$@"
}

workbench_set_env() {
  set_env_in_file "$WORKBENCH_ENV_FILE" "$@"
}

studio_set_env() {
  set_env_in_file "$STUDIO_ENV_FILE" "$@"
}

dotenv_get_from_file() {
  local target_file="$1"
  local key="$2"
  local value=""

  value="$(BASIL_DEPLOY_ENV_KEY="$key" awk '
    index($0, ENVIRON["BASIL_DEPLOY_ENV_KEY"] "=") == 1 {
      sub(/^[^=]*=/, "")
      print
      exit
    }
  ' "$target_file")"

  if [[ "$value" == \'*\' && ${#value} -ge 2 ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "$value" == \"*\" && ${#value} -ge 2 ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

dotenv_get() {
  dotenv_get_from_file "$ENV_FILE" "$1"
}

workbench_get_env() {
  dotenv_get_from_file "$WORKBENCH_ENV_FILE" "$1"
}

studio_get_env() {
  dotenv_get_from_file "$STUDIO_ENV_FILE" "$1"
}

ensure_image_version() {
  local getter="$1"
  local setter="$2"
  local key="$3"
  local label="$4"
  local resolved_version=""

  resolved_version="$("$getter" "$key")"
  if [[ -z "$resolved_version" || "$resolved_version" == CHANGE_ME* ]]; then
    prompt_image_version resolved_version "$label Docker tag" ""
    "$setter" "$key" "$resolved_version"
  fi
}

enforce_studio_cookie_mode() {
  studio_set_env ENABLE_HTTPS_COOKIES false
}

rebuild_compose_files() {
  COMPOSE_FILES="compose/middleware.yaml"
  [[ "$POSTGRES_MODE" == local ]] && COMPOSE_FILES+=",compose/db.yaml"
  [[ "$REDIS_MODE" == local ]] && COMPOSE_FILES+=",compose/cache.yaml"
  [[ "$RABBITMQ_MODE" == local ]] && COMPOSE_FILES+=",compose/mq.yaml"
  [[ "$STORAGE_MODE" == local ]] && COMPOSE_FILES+=",compose/storage.yaml"
  set_env COMPOSE_FILE "$COMPOSE_FILES"
}

middleware_compose() (
  cd "$DEPLOY_DIR" || return 1
  local files
  files="$(dotenv_get COMPOSE_FILE)"
  # v2026.11.18 used the repository root for the base file.
  case "$files" in
    docker-compose.middleware.yaml|docker-compose.middleware.yaml,*)
      files="compose/middleware.yaml${files#docker-compose.middleware.yaml}" ;;
  esac
  COMPOSE_FILE="$files" docker compose --project-directory "$DEPLOY_DIR" --env-file "$ENV_FILE" "$@"
)

studio_compose() {
  docker compose --env-file "$ENV_FILE" --env-file "$STUDIO_ENV_FILE" \
    -f "$STUDIO_COMPOSE_FILE" "$@"
}

prepare_owned_directory() {
  local path="$1"
  local ownership_image=""
  local ownership_platform=""
  mkdir -p "$path"

  if [[ "$(id -u)" -eq 0 ]]; then
    chown -R 1001:1001 "$path"
  elif [[ "$(uname -s)" == Darwin ]]; then
    # Docker Desktop 的目录权限在 Linux 容器中设置，避免要求 macOS sudo 密码。
    # 使用前一步已验证的本地 PostgreSQL 镜像，不因全局 amd64 模拟设置另拉一个平台。
    ownership_image="$(docker image inspect --format '{{.Id}}' \
      "$(dotenv_get POSTGRES_IMAGE):$(dotenv_get POSTGRES_VERSION)")"
    ownership_platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$ownership_image")"
    docker run --rm --pull never --platform "$ownership_platform" --user 0 --entrypoint chown \
      --volume "$path:/data" \
      "$ownership_image" -R 1001:1001 /data
  elif command -v sudo >/dev/null 2>&1; then
    sudo chown -R 1001:1001 "$path"
  else
    die "$path 需要归属 1001:1001；请使用 root 权限处理后重试。"
  fi
}

retry_configuration() {
  confirm "测试失败，是否重新配置当前服务？" y || die "部署已停止。"
}

test_postgresql_local() {
  local username="$1"
  local password="$2"
  local database="$3"
  local extension=""

  extension="$(middleware_compose exec -T -e "PGPASSWORD=$password" postgresql \
    psql --username "$username" --dbname "$database" --tuples-only --no-align \
    --command "SELECT extname FROM pg_extension WHERE extname = 'vector';")"
  [[ "$extension" == vector ]]
}

test_postgresql_external() {
  local host="$1"
  local port="$2"
  local username="$3"
  local password="$4"
  local database="$5"
  local image=""
  local extension=""

  image="$(dotenv_get POSTGRES_IMAGE):$(dotenv_get POSTGRES_VERSION)"
  ops pull "$image" || return 1
  extension="$(PGPASSWORD="$password" docker run --rm \
    --env PGPASSWORD "$image" psql \
    --host "$host" --port "$port" --username "$username" --dbname "$database" \
    --tuples-only --no-align \
    --command "SELECT extname FROM pg_extension WHERE extname = 'vector';")"
  [[ "$extension" == vector ]]
}

test_redis_local() {
  local password="$1"
  [[ "$(middleware_compose exec -T -e "REDISCLI_AUTH=$password" redis redis-cli ping)" == PONG ]]
}

test_redis_external() {
  local host="$1"
  local port="$2"
  local password="$3"
  local use_tls="$4"
  local image=""
  local output=""

  image="$(dotenv_get REDIS_IMAGE):$(dotenv_get REDIS_VERSION)"
  ops pull "$image" || return 1
  if [[ "$use_tls" == true ]]; then
    output="$(REDISCLI_AUTH="$password" docker run --rm \
      --env REDISCLI_AUTH "$image" redis-cli -h "$host" -p "$port" --tls ping)"
  else
    output="$(REDISCLI_AUTH="$password" docker run --rm \
      --env REDISCLI_AUTH "$image" redis-cli -h "$host" -p "$port" ping)"
  fi
  [[ "$output" == PONG ]]
}

test_rabbitmq_endpoint() {
  local host="$1"
  local port="$2"
  local username="$3"
  local password="$4"

  curl --fail --silent --show-error --connect-timeout 10 --max-time 20 \
    --user "$username:$password" "http://$host:$port/api/overview" >/dev/null 2>&1 ||
    curl --fail --silent --show-error --connect-timeout 10 --max-time 20 \
      --user "$username:$password" "https://$host:$port/api/overview" >/dev/null 2>&1
}

test_url_reachable() {
  local url="$1"
  local status=""

  status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --connect-timeout 10 --max-time 20 "$url")" || return 1
  [[ "$status" != 000 ]]
}

clear_minio_config() {
  set_env MINIO_EXPOSE_URL ""
  set_env MINIO_HOST ""
  set_env MINIO_USERNAME ""
  set_env MINIO_PASSWORD ""
}

clear_aliyun_oss_config() {
  set_env ALI_OSS_ACCESS_ID ""
  set_env ALI_OSS_ACCESS_KEY ""
  set_env ALI_OSS_ENDPOINT ""
  studio_set_env ALI_OSS_BUCKET_NAME ""
}

clear_azure_blob_config() {
  set_env AZURE_BLOB_ACCOUNT_NAME ""
  set_env AZURE_BLOB_ACCOUNT_KEY ""
  set_env AZURE_BLOB_ENDPOINT ""
  studio_set_env AZURE_BLOB_CONTAINER ""
}

initialize_postgresql() {
  reuse_middleware postgresql && return 0
  local host=""
  local port=""
  local username=""
  local password=""
  local database=""

  info "1/4 初始化 PostgreSQL"
  while true; do
    choose_mode PostgreSQL
    if [[ "$SELECTED_MODE" == local ]]; then
      ensure_image_version dotenv_get set_env POSTGRES_VERSION PostgreSQL
      prompt_required username "数据库用户名" basilos
      prompt_secret_confirm password "数据库密码"
      database=basilos

      POSTGRES_MODE=local
      set_env POSTGRESQL_HOST postgresql
      set_env POSTGRESQL_PORT 5432
      set_env POSTGRESQL_USERNAME "$username"
      set_env POSTGRESQL_PASSWORD "$password"
      set_env POSTGRESQL_BOOTSTRAP_DATABASE "$database"
      studio_set_env POSTGRESQL_DATABASE "$database"
      rebuild_compose_files

      mkdir -p "$DEPLOY_DIR/data/postgresql"
      if ops up middleware postgresql &&
        middleware_compose run --rm postgresql-init &&
        test_postgresql_local "$username" "$password" "$database"; then
        success "本地 PostgreSQL 已部署，连接正常，vector 扩展可用。"
        return
      fi
    else
      prompt_required host "PostgreSQL 地址"
      prompt_port port "PostgreSQL 端口" 5432
      prompt_required database "数据库名称" basilos
      prompt_required username "数据库用户名" basilos
      prompt_secret_confirm password "数据库密码"

      POSTGRES_MODE=external
      set_env POSTGRESQL_HOST "$host"
      set_env POSTGRESQL_PORT "$port"
      set_env POSTGRESQL_USERNAME "$username"
      set_env POSTGRESQL_PASSWORD "$password"
      set_env POSTGRESQL_BOOTSTRAP_DATABASE "$database"
      studio_set_env POSTGRESQL_DATABASE "$database"
      rebuild_compose_files

      if test_postgresql_external "$host" "$port" "$username" "$password" "$database"; then
        success "外部 PostgreSQL 连接正常，vector 扩展可用。"
        return
      fi
    fi
    retry_configuration
  done
}

initialize_redis() {
  reuse_middleware redis && return 0
  local host=""
  local port=""
  local password=""
  local database=""
  local use_tls=false

  info "2/4 初始化 Redis"
  while true; do
    choose_mode Redis
    if [[ "$SELECTED_MODE" == local ]]; then
      ensure_image_version dotenv_get set_env REDIS_VERSION Redis
      prompt_secret_confirm password "Redis 密码"

      REDIS_MODE=local
      set_env REDIS_HOST redis
      set_env REDIS_PORT 6379
      set_env REDIS_PASSWORD "$password"
      studio_set_env REDIS_DATABASE 0
      set_env REDIS_SSL false
      rebuild_compose_files

      prepare_owned_directory "$DEPLOY_DIR/data/redis"
      if ops up middleware redis && test_redis_local "$password"; then
        success "本地 Redis 已部署并通过连接测试。"
        return
      fi
    else
      prompt_required host "Redis 地址"
      prompt_port port "Redis 端口" 6379
      prompt_secret_confirm password "Redis 密码"
      prompt_required database "Redis 数据库编号" 0
      if confirm "Redis 是否启用 TLS？" n; then use_tls=true; else use_tls=false; fi

      REDIS_MODE=external
      set_env REDIS_HOST "$host"
      set_env REDIS_PORT "$port"
      set_env REDIS_PASSWORD "$password"
      studio_set_env REDIS_DATABASE "$database"
      set_env REDIS_SSL "$use_tls"
      rebuild_compose_files

      if test_redis_external "$host" "$port" "$password" "$use_tls"; then
        success "外部 Redis 连接正常。"
        return
      fi
    fi
    retry_configuration
  done
}

initialize_rabbitmq() {
  reuse_middleware rabbitmq && return 0
  local host=""
  local port=""
  local management_port=""
  local username=""
  local password=""
  local virtual_host=""
  local local_management_port=""

  info "3/4 初始化 RabbitMQ"
  while true; do
    choose_mode RabbitMQ
    if [[ "$SELECTED_MODE" == local ]]; then
      ensure_image_version dotenv_get set_env RABBITMQ_VERSION RabbitMQ
      prompt_required username "RabbitMQ 用户名" basilos
      prompt_secret_confirm password "RabbitMQ 密码"

      RABBITMQ_MODE=local
      set_env RABBITMQ_HOST rabbitmq
      set_env RABBITMQ_PORT 5672
      set_env RABBITMQ_MANAGEMENT_PORT 15672
      set_env RABBITMQ_USERNAME "$username"
      set_env RABBITMQ_PASSWORD "$password"
      set_env RABBITMQ_VIRTUAL_HOST /basilos
      rebuild_compose_files

      mkdir -p "$DEPLOY_DIR/data/rabbitmq"
      local_management_port="$(dotenv_get RABBITMQ_MANAGEMENT_HOST_PORT)"
      if ops up middleware rabbitmq &&
        test_rabbitmq_endpoint 127.0.0.1 "$(dotenv_get RABBITMQ_MANAGEMENT_HOST_PORT)" "$username" "$password"; then
        success "本地 RabbitMQ 已部署并通过连接测试。"
        return
      fi
    else
      prompt_required host "RabbitMQ 地址"
      prompt_port port "RabbitMQ 端口" 5672
      prompt_port management_port "RabbitMQ 管理端口" 15672
      prompt_required username "RabbitMQ 用户名" basilos
      prompt_secret_confirm password "RabbitMQ 密码"
      prompt_required virtual_host "RabbitMQ Virtual Host" /basilos

      RABBITMQ_MODE=external
      set_env RABBITMQ_HOST "$host"
      set_env RABBITMQ_PORT "$port"
      set_env RABBITMQ_MANAGEMENT_PORT "$management_port"
      set_env RABBITMQ_USERNAME "$username"
      set_env RABBITMQ_PASSWORD "$password"
      set_env RABBITMQ_VIRTUAL_HOST "$virtual_host"
      rebuild_compose_files

      if test_rabbitmq_endpoint "$host" "$management_port" "$username" "$password"; then
        success "外部 RabbitMQ 管理接口连接正常。"
        return
      fi
    fi
    retry_configuration
  done
}

configure_local_minio() {
  local username=""
  local password=""
  local expose_url=""
  local expose_port=""

  ensure_image_version dotenv_get set_env MINIO_VERSION MinIO
  prompt_required username "MinIO 用户名" basilos
  prompt_secret_confirm password "MinIO 密码"
  ensure_deployment_access_host
  expose_port="$(dotenv_get MINIO_API_HOST_PORT)"
  info "MinIO API 当前 Compose 对外端口：${expose_port}；使用 HTTPS 或反向代理时请覆盖默认值。"
  prompt_url expose_url "AI 模型可访问的 MinIO 地址" "$(deployment_access_url "$expose_port")"

  STORAGE_MODE=local
  set_env FILE_SERVICE_SELECTOR minio
  studio_set_env FILE_SERVICE_PRIVATE_BUCKET_NAME studio-private
  studio_set_env FILE_SERVICE_PUBLIC_BUCKET_NAME studio-public
  set_env MINIO_EXPOSE_URL "$expose_url"
  set_env MINIO_HOST minio
  set_env MINIO_PORT 9000
  set_env MINIO_USERNAME "$username"
  set_env MINIO_PASSWORD "$password"
  clear_aliyun_oss_config
  clear_azure_blob_config
  rebuild_compose_files

  prepare_owned_directory "$DEPLOY_DIR/data/minio"
  ops up middleware minio &&
    middleware_compose exec -T minio curl --fail --silent http://127.0.0.1:9000/minio/health/ready >/dev/null &&
    test_url_reachable "$(dotenv_get MINIO_EXPOSE_URL)/minio/health/ready"
}

configure_external_minio() {
  local host=""
  local port=""
  local username=""
  local password=""
  local expose_url=""

  prompt_required host "MinIO 地址（不含协议）"
  prompt_port port "MinIO API 端口" 9000
  prompt_required username "MinIO 用户名"
  prompt_secret_confirm password "MinIO 密码"
  prompt_url expose_url "AI 模型可访问的 MinIO 地址" "http://$host:$port"

  STORAGE_MODE=external
  set_env FILE_SERVICE_SELECTOR minio
  studio_set_env FILE_SERVICE_PRIVATE_BUCKET_NAME studio-private
  studio_set_env FILE_SERVICE_PUBLIC_BUCKET_NAME studio-public
  set_env MINIO_EXPOSE_URL "$expose_url"
  set_env MINIO_HOST "$host"
  set_env MINIO_PORT "$port"
  set_env MINIO_USERNAME "$username"
  set_env MINIO_PASSWORD "$password"
  clear_aliyun_oss_config
  clear_azure_blob_config
  rebuild_compose_files

  test_url_reachable "$expose_url/minio/health/ready"
}

configure_aliyun_oss() {
  local access_id=""
  local access_key=""
  local endpoint=""
  local bucket=""

  prompt_required access_id "OSS AccessKey ID"
  prompt_secret_confirm access_key "OSS AccessKey Secret"
  prompt_url endpoint "OSS Endpoint"
  prompt_required bucket "OSS Bucket 名称" studio

  STORAGE_MODE=external
  set_env FILE_SERVICE_SELECTOR aliyun-oss
  studio_set_env FILE_SERVICE_PRIVATE_BUCKET_NAME studio-private
  studio_set_env FILE_SERVICE_PUBLIC_BUCKET_NAME studio-public
  set_env ALI_OSS_ACCESS_ID "$access_id"
  set_env ALI_OSS_ACCESS_KEY "$access_key"
  set_env ALI_OSS_ENDPOINT "$endpoint"
  studio_set_env ALI_OSS_BUCKET_NAME "$bucket"
  clear_minio_config
  clear_azure_blob_config
  rebuild_compose_files

  test_url_reachable "$endpoint/$bucket"
}

configure_azure_blob() {
  local account_name=""
  local account_key=""
  local endpoint=""
  local container=""

  prompt_required account_name "Azure Storage 账户名称"
  prompt_secret_confirm account_key "Azure Storage 账户密钥"
  prompt_url endpoint "Azure Blob Endpoint"
  prompt_required container "Azure Blob Container" studio

  STORAGE_MODE=external
  set_env FILE_SERVICE_SELECTOR azure-blob
  studio_set_env FILE_SERVICE_PRIVATE_BUCKET_NAME studio-private
  studio_set_env FILE_SERVICE_PUBLIC_BUCKET_NAME studio-public
  set_env AZURE_BLOB_ACCOUNT_NAME "$account_name"
  set_env AZURE_BLOB_ACCOUNT_KEY "$account_key"
  set_env AZURE_BLOB_ENDPOINT "$endpoint"
  studio_set_env AZURE_BLOB_CONTAINER "$container"
  clear_minio_config
  clear_aliyun_oss_config
  rebuild_compose_files

  test_url_reachable "$endpoint/$container"
}

initialize_storage() {
  reuse_middleware storage && return 0
  info "4/4 初始化对象存储"
  while true; do
    choose_mode "对象存储"
    if [[ "$SELECTED_MODE" == local ]]; then
      if configure_local_minio; then
        success "本地 MinIO 已部署，内部和公开地址均可访问。"
        break
      fi
    else
      choose_storage_provider
      case "$SELECTED_PROVIDER" in
        minio) configure_external_minio && break ;;
        aliyun-oss) configure_aliyun_oss && break ;;
        azure-blob) configure_azure_blob && break ;;
      esac
    fi
    retry_configuration
  done

  success "对象存储地址可从当前服务器访问。"
  warn "AI 打标还要求实际使用的 AI 模型能够访问对象存储生成的文件地址，请从模型所在网络完成验证。"
}

ensure_studio_configuration() {
  local encryptor_password=""
  local assets_search_url=""
  local studio_frontend_url=""
  local studio_frontend_port=""
  local assets_path='/basilos/asset/search-embed'

  ensure_image_version studio_get_env studio_set_env STUDIO_VERSION "Studio API"
  ensure_image_version studio_get_env studio_set_env STUDIO_FRONTEND_VERSION "Studio Frontend"
  ensure_image_version studio_get_env studio_set_env NODE_SANDBOX_VERSION "Studio Node Sandbox"

  encryptor_password="$(studio_get_env ENCRYPTOR_PASSWORD)"
  if [[ -z "$encryptor_password" || "$encryptor_password" == CHANGE_ME_* ]]; then
    prompt_secret_confirm encryptor_password "Studio 数据加密密码"
    studio_set_env ENCRYPTOR_PASSWORD "$encryptor_password"
  fi

  assets_search_url="$(studio_get_env ASSETS_SEARCH_SNAPSHOT_URL)"
  if [[ -n "$assets_search_url" &&
    "$assets_search_url" != *CHANGE_ME* &&
    "$assets_search_url" == *"$assets_path" ]]; then
    studio_frontend_url="${assets_search_url%$assets_path}"
  else
    ensure_deployment_access_host
    studio_frontend_port="$(studio_get_env STUDIO_FRONTEND_HOST_PORT)"
    info "Studio Frontend 当前 Compose 对外端口：${studio_frontend_port}；使用 HTTPS 或反向代理时请覆盖默认值。"
    prompt_url studio_frontend_url "Studio 前端访问地址" "$(deployment_access_url "$studio_frontend_port")"
  fi
  studio_set_env ASSETS_SEARCH_SNAPSHOT_URL "${studio_frontend_url%/}$assets_path"
  studio_set_env VIEW_SNAPSHOT_URL "${studio_frontend_url%/}/basilos/studio/engine/multi-dim-table-embed"
}

deploy_studio() {
  local studio_frontend_url=""

  info "部署 Basil Studio"
  enforce_studio_cookie_mode
  ensure_studio_configuration
  mkdir -p "$DEPLOY_DIR/data/studio-logs"
  studio_compose config --quiet
  ops up studio
  studio_compose ps
  studio_frontend_url="$(studio_get_env ASSETS_SEARCH_SNAPSHOT_URL)"
  studio_frontend_url="${studio_frontend_url%/basilos/asset/search-embed}"
  success "Basil Studio 容器已启动，访问地址：$studio_frontend_url"
  info "仍需按部署文档检查后端迁移、HTTP 重定向、登录和业务功能；running 不代表应用已就绪。"
}

workbench_compose() {
  docker compose --env-file "$ENV_FILE" --env-file "$WORKBENCH_ENV_FILE" \
    -f "$WORKBENCH_COMPOSE_FILE" "$@"
}

workbench_value_needs_configuration() {
  local value="$1"
  [[ -z "$value" || "$value" == *CHANGE_ME* ]]
}

generate_secret() {
  od -An -N32 -tx1 /dev/urandom | tr -d '[:space:]'
}

parse_url() {
  local url="$1"
  local remainder=""

  URL_SCHEME="${url%%://*}"
  remainder="${url#*://}"
  URL_AUTHORITY="${remainder%%/*}"
  URL_HOST="$URL_AUTHORITY"
  URL_PORT=""

  [[ "$URL_SCHEME" == http || "$URL_SCHEME" == https ]] || return 1
  [[ -n "$URL_AUTHORITY" ]] || return 1

  if [[ "$URL_AUTHORITY" == \[*\]:* ]]; then
    URL_HOST="${URL_AUTHORITY%%]:*}]"
    URL_PORT="${URL_AUTHORITY##*:}"
  elif [[ "$URL_AUTHORITY" == *:* ]]; then
    URL_HOST="${URL_AUTHORITY%%:*}"
    URL_PORT="${URL_AUTHORITY##*:}"
  fi

  if [[ -z "$URL_PORT" ]]; then
    [[ "$URL_SCHEME" == https ]] && URL_PORT=443 || URL_PORT=80
  fi
  [[ "$URL_PORT" =~ ^[0-9]+$ ]] && ((URL_PORT >= 1 && URL_PORT <= 65535))
}

ensure_workbench_url() {
  local key="$1"
  local label="$2"
  local port="$3"
  local configured_url=""
  local default_url=""

  configured_url="$(workbench_get_env "$key")"
  if workbench_value_needs_configuration "$configured_url"; then
    ensure_deployment_access_host
    default_url="$(deployment_access_url "$port")"
  elif ! parse_url "$configured_url"; then
    warn "$label 当前值无效：$configured_url"
    ensure_deployment_access_host
    default_url="$(deployment_access_url "$port")"
  fi

  if [[ -n "$default_url" ]]; then
    info "$label 当前 Compose 对外端口：${port}；使用 HTTPS 或反向代理时请覆盖默认值。"
    prompt_url configured_url "$label" "$default_url"
    workbench_set_env "$key" "$configured_url"
  fi
  WORKBENCH_VALUE="$configured_url"
}

ensure_workbench_text() {
  local key="$1"
  local label="$2"
  local default_value="${3-}"
  local value=""

  value="$(workbench_get_env "$key")"
  if workbench_value_needs_configuration "$value"; then
    prompt_required value "$label" "$default_value"
    workbench_set_env "$key" "$value"
  fi
}

ensure_workbench_generated_secret() {
  local key="$1"
  local value=""

  value="$(workbench_get_env "$key")"
  if workbench_value_needs_configuration "$value"; then
    workbench_set_env "$key" "$(generate_secret)"
    info "已生成 Workbench 密钥：$key"
  fi
}

prepare_workbench_env() {
  [[ -f "$WORKBENCH_COMPOSE_FILE" ]] || die "缺少 docker-compose.workbench.yaml"
  [[ -f "$WORKBENCH_ENV_TEMPLATE" ]] || die "缺少 .env.workbench.example"
  [[ -f "$WORKBENCH_CHECK_SCRIPT" ]] || die "缺少 check-workbench.sh"
  [[ -f "$DEPLOY_DIR/workbench/storage/nginx/runtime-nginx.conf" ]] || die "缺少 workbench/storage/nginx/runtime-nginx.conf"
  [[ -f "$DEPLOY_DIR/workbench/storage/templates/AGENTS.md" && -r "$DEPLOY_DIR/workbench/storage/templates/AGENTS.md" && ! -L "$DEPLOY_DIR/workbench/storage/templates/AGENTS.md" ]] || die "缺少可读的普通文件 workbench/storage/templates/AGENTS.md（不允许符号链接）"

  [[ ! -L "$WORKBENCH_ENV_FILE" ]] || die "拒绝修改符号链接环境文件：$WORKBENCH_ENV_FILE"
  if [[ ! -f "$WORKBENCH_ENV_FILE" ]]; then
    cp "$WORKBENCH_ENV_TEMPLATE" "$WORKBENCH_ENV_FILE"
    info "已创建 $WORKBENCH_ENV_FILE"
  fi
  chmod 600 "$WORKBENCH_ENV_FILE"
}

sync_workbench_shared_configuration() {
  local studio_vhost=""
  local storage_url=""

  studio_vhost="$(dotenv_get RABBITMQ_VIRTUAL_HOST)"
  storage_url="$(dotenv_get MINIO_EXPOSE_URL)"
  parse_url "$storage_url" || die "MINIO_EXPOSE_URL 不是有效的 HTTP(S) 地址：$storage_url"

  workbench_set_env WORKBENCH_DEPLOYMENT_ROOT "$DEPLOY_DIR"
  workbench_set_env REDIS_DATABASE 1
  workbench_set_env RABBITMQ_VIRTUAL_HOST "/${studio_vhost}"
  workbench_set_env MINIO_PUBLIC_BASE_URL "$storage_url"
  workbench_set_env MINIO_PRESIGN_ENDPOINT "$URL_HOST"
  workbench_set_env MINIO_PRESIGN_PORT "$URL_PORT"
  [[ "$URL_SCHEME" == https ]] &&
    workbench_set_env MINIO_PRESIGN_USE_SSL true ||
    workbench_set_env MINIO_PRESIGN_USE_SSL false
}

ensure_workbench_gateway() {
  local gateway_url=""
  # 平台网关代理 Studio 页面/API，不能从 Workbench 自身 API 地址推导。
  gateway_url="$(workbench_get_env BASILOS_GATEWAY_HOST)"
  if workbench_value_needs_configuration "$gateway_url"; then
    prompt_url gateway_url "Studio 平台网关地址（须从 Workbench Frontend 容器可达）"
  fi
  parse_url "$gateway_url" || die "Studio 平台网关地址无效：$gateway_url"
  workbench_set_env BASILOS_GATEWAY_HOST "${gateway_url%/}/"
}

configure_workbench() {
  local api_url=""
  local frontend_url=""
  local admin_password=""
  local api_port=""
  local frontend_port=""

  sync_workbench_shared_configuration
  ensure_image_version workbench_get_env workbench_set_env WORKBENCH_VERSION "Workbench API"
  ensure_image_version workbench_get_env workbench_set_env WORKBENCH_FRONTEND_VERSION "Workbench Frontend"
  ensure_image_version workbench_get_env workbench_set_env RUNTIME_VERSION "Workbench Runtime"
  ensure_image_version workbench_get_env workbench_set_env RUNTIME_SANDBOX_VERSION "Runtime Sandbox"
  ensure_image_version workbench_get_env workbench_set_env RUNTIME_NGINX_VERSION "Runtime Gateway"

  api_port="$(workbench_get_env WORKBENCH_HOST_PORT)"
  frontend_port="$(workbench_get_env WORKBENCH_FRONTEND_HOST_PORT)"

  ensure_workbench_url APP_URL "Workbench API 的浏览器入口（通常与前端同源）" "$frontend_port"
  api_url="$WORKBENCH_VALUE"
  parse_url "$api_url" || die "Workbench API 访问地址无效：$api_url"
  workbench_set_env BASILCRAW_API_HOST "$URL_AUTHORITY"

  ensure_workbench_gateway

  ensure_workbench_url FRONTEND_URL "Workbench 前端访问地址" "$frontend_port"
  frontend_url="$WORKBENCH_VALUE"
  workbench_set_env FRONTEND_OAUTH_RESULT_URL "$frontend_url"

  ensure_workbench_generated_secret JWT_SECRET
  ensure_workbench_generated_secret ENCRYPTION_KEY
  ensure_workbench_generated_secret RUNTIME_HTTP_SERVICE_TOKEN
  ensure_workbench_generated_secret RUNTIME_TO_WORKBENCH_SERVICE_TOKEN

  admin_password="$(workbench_get_env DEFAULT_USER_PASSWORD)"
  if workbench_value_needs_configuration "$admin_password"; then
    prompt_secret_confirm admin_password "Workbench 新建/重置用户默认密码"
    workbench_set_env DEFAULT_USER_PASSWORD "$admin_password"
  fi
  ensure_workbench_text RUNTIME_SANDBOX_HOST_ID "Sandbox Host 稳定标识"
}

check_workbench_placeholders() {
  local keys=""

  keys="$(awk -F= '
    /^[[:space:]]*#/ || !index($0, "=") { next }
    index(substr($0, index($0, "=") + 1), "CHANGE_ME") { print $1 }
  ' "$WORKBENCH_ENV_FILE")"
  if [[ -n "$keys" ]]; then
    warn "Workbench 仍有未配置变量：$(printf '%s\n' "$keys" | tr '\n' ' ')"
    return 1
  fi
}

wait_for_url() {
  local url="$1"
  local attempt=0

  for ((attempt = 1; attempt <= 30; attempt++)); do
    if curl --fail --silent --connect-timeout 5 --max-time 10 "$url" >/dev/null; then
      return
    fi
    sleep 2
  done
  curl --fail --silent --show-error --connect-timeout 5 --max-time 10 "$url" >/dev/null
}

test_workbench_http() {
  local runtime_port=""
  local api_port=""
  local frontend_port=""

  runtime_port="$(workbench_get_env RUNTIME_GATEWAY_HOST_PORT)"
  api_port="$(workbench_get_env WORKBENCH_HOST_PORT)"
  frontend_port="$(workbench_get_env WORKBENCH_FRONTEND_HOST_PORT)"
  wait_for_url "http://127.0.0.1:$runtime_port/health" || return 1
  wait_for_url "http://127.0.0.1:$runtime_port/ready" || return 1
  wait_for_url "http://127.0.0.1:$api_port/" || return 1
  wait_for_url "http://127.0.0.1:$frontend_port/" || return 1
}

workbench_storage_supported() {
  [[ "$(dotenv_get FILE_SERVICE_SELECTOR)" == minio ]]
}

deploy_workbench() {
  local middleware_network=""
  local sandbox_image=""

  info "部署 Basil Workbench"
  if ! workbench_storage_supported; then
    warn "当前 Workbench 部署模板仅支持 MinIO 对象存储。"
    return 1
  fi

  require_command od
  prepare_workbench_env
  configure_workbench
  ENV_FILE="$WORKBENCH_ENV_FILE" bash "$WORKBENCH_CHECK_SCRIPT"
  check_workbench_placeholders || return 1

  middleware_network="$(dotenv_get BASIL_NETWORK_NAME)"
  docker network inspect "$middleware_network" >/dev/null ||
    die "Workbench 依赖的 Docker 网络不存在：$middleware_network"
  workbench_compose config --quiet

  sandbox_image="$(workbench_get_env RUNTIME_SANDBOX_IMAGE):$(workbench_get_env RUNTIME_SANDBOX_VERSION)"
  if ! docker image inspect "$sandbox_image" >/dev/null 2>&1; then
    ops pull "$sandbox_image"
  fi
  ops up workbench
  if ! test_workbench_http; then
    workbench_compose ps
    die "Workbench 基础 HTTP 检查失败，请查看容器状态和日志。"
  fi
  workbench_compose ps
  success "Basil Workbench 部署完成并通过基础 HTTP 检查。"
  info "Workbench 前端访问地址：$(workbench_get_env FRONTEND_URL)"
  info "Workbench API 访问地址：$(workbench_get_env APP_URL)"
}

deploy_all() {
  if ! workbench_storage_supported; then
    warn "一键部署需要使用 MinIO；当前未执行 Studio 或 Workbench 部署。"
    return 1
  fi
  deploy_studio
  deploy_workbench
}

prepare_deployment() {
  prepare
  info "初始化中间件"
  initialize_postgresql
  initialize_redis
  initialize_rabbitmq
  initialize_storage
}

ensure_shared_network() {
  local network_name=""

  network_name="$(dotenv_get BASIL_NETWORK_NAME)"
  [[ -n "$network_name" ]] || die "BASIL_NETWORK_NAME 不能为空。"
  if ! docker network inspect "$network_name" >/dev/null 2>&1; then
    docker network create --label "ai.basilos.deploy.directory=$DEPLOY_DIR" "$network_name" >/dev/null
    info "已创建共享网络：$network_name"
  fi
}

update_service_version() {
  local label="$1"
  local getter="$2"
  local setter="$3"
  local compose_command="$4"
  local image_key="$5"
  local version_key="$6"
  local service="$7"
  local wait_timeout="$8"
  local confirm_default="$9"
  local env_file="${10}"
  local current_version=""
  local new_version=""
  local image=""
  local container_ids=""
  local previous_override=""
  local previous_override_was_set=false
  local pull_succeeded=false
  local backup_file=""
  local safe_current_version=""

  container_ids="$("$compose_command" ps -a -q "$service" 2>/dev/null || true)"
  if [[ -z "$container_ids" ]]; then
    warn "$label 未由当前 Docker Compose 部署，无法通过此脚本更新。"
    return
  fi

  image="$("$getter" "$image_key")"
  current_version="$("$getter" "$version_key")"
  prompt_image_version new_version "$label Docker tag" "$current_version"
  printf '%s: %s:%s -> %s:%s\n' "$label" "$image" "$current_version" "$image" "$new_version"
  confirm "确认更新 ${label}？" "$confirm_default" || return

  if [[ "${!version_key+x}" == x ]]; then
    previous_override_was_set=true
    previous_override="${!version_key}"
  fi
  printf -v "$version_key" '%s' "$new_version"
  export "$version_key"
  if "$compose_command" config --quiet && ops pull "$image:$new_version" --force; then
    pull_succeeded=true
  fi
  if [[ "$previous_override_was_set" == true ]]; then
    printf -v "$version_key" '%s' "$previous_override"
    export "$version_key"
  else
    unset "$version_key"
  fi
  if [[ "$pull_succeeded" != true ]]; then
    warn "$label 镜像拉取失败；环境变量和现有容器均未修改。"
    return 1
  fi

  safe_current_version="${current_version//[^A-Za-z0-9_.-]/_}"
  backup_file="${env_file}.bak.update-${service}-${safe_current_version}-$(date -u +%Y%m%dT%H%M%SZ)"
  [[ ! -e "$backup_file" ]] || die "备份文件已存在：$backup_file"
  cp -a -- "$env_file" "$backup_file"
  info "已备份环境文件：$backup_file"

  "$setter" "$version_key" "$new_version"
  if "$compose_command" config --quiet &&
    compose_recreate "$compose_command" "$service"; then
    "$compose_command" ps "$service"
    success "$label 已更新到 ${new_version}。"
    return
  fi

  cp -a -- "$backup_file" "$env_file"
  warn "$label 更新失败，正在使用备份恢复 ${current_version}。"
  if "$compose_command" config --quiet &&
    compose_recreate "$compose_command" "$service"; then
    "$compose_command" ps "$service"
    warn "$label 已恢复到 ${current_version}；数据库迁移和外部副作用不会随镜像自动回滚。"
  else
    warn "$label 自动恢复失败；环境文件已恢复，请立即检查容器和日志。"
  fi
  return 1
}

update_runtime_sandbox_image() {
  local image="" current_version="" new_version="" backup_file=""
  local safe_current_version="" container_id="" configured_image=""

  container_id="$(workbench_compose ps -a -q workbench-runtime-node)" || return 1
  [[ -n "$container_id" ]] || { warn "Runtime 尚未部署，无法更新 Sandbox 配置。"; return 1; }
  # Shell 环境变量优先于 env 文件，避免文件更新后仍使用外部旧值。
  [[ -z "${RUNTIME_SANDBOX_VERSION+x}" ]] || {
    warn "请先 unset RUNTIME_SANDBOX_VERSION，再运行更新。"
    return 1
  }
  image="$(workbench_get_env RUNTIME_SANDBOX_IMAGE)"
  current_version="$(workbench_get_env RUNTIME_SANDBOX_VERSION)"
  prompt_image_version new_version "Runtime Sandbox Docker tag" "$current_version"
  printf 'Runtime Sandbox: %s:%s -> %s:%s\n' "$image" "$current_version" "$image" "$new_version"
  confirm "更新将重建 Runtime，可能中断执行中的任务；确认继续？" y || return

  if ! workbench_compose config --quiet || ! ops pull "$image:$new_version" --force; then
    warn "配置检查或镜像拉取失败；环境文件和 Runtime 未修改。"
    return 1
  fi
  safe_current_version="${current_version//[^A-Za-z0-9_.-]/_}"
  backup_file="${WORKBENCH_ENV_FILE}.bak.update-runtime-sandbox-${safe_current_version}-$(date -u +%Y%m%dT%H%M%SZ)"
  [[ ! -e "$backup_file" ]] || die "备份文件已存在：$backup_file"
  cp -a -- "$WORKBENCH_ENV_FILE" "$backup_file" || return 1
  workbench_set_env RUNTIME_SANDBOX_VERSION "$new_version" || return 1

  if workbench_compose config --quiet &&
    compose_recreate workbench_compose workbench-runtime-node; then
    container_id="$(workbench_compose ps -q workbench-runtime-node)" || return 1
    configured_image="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$container_id" |
      sed -n 's/^RUNTIME_SANDBOX_IMAGE=//p')" || return 1
    if [[ "$configured_image" == "$image:$new_version" ]]; then
      success "Runtime 已重建并加载 Sandbox 镜像 ${image}:${new_version}；已有 Sandbox 不会被此脚本重建。"
      return
    fi
  fi
  warn "Runtime 更新或配置验证失败。备份位于 ${backup_file}；请检查容器日志。未自动回退，避免掩盖已执行的启动迁移。"
  return 1
}

workbench_env_exists() {
  if [[ ! -f "$WORKBENCH_ENV_FILE" ]]; then
    warn "尚未生成 .env.workbench，请先部署 Workbench。"
    return 1
  fi
}

service_update_menu() {
  local choice=""

  while true; do
    printf '\n服务更新菜单：\n'
    printf '  1) Studio API\n'
    printf '  2) Studio Frontend\n'
    printf '  3) Studio Node Sandbox\n'
    printf '  4) Workbench API\n'
    printf '  5) Workbench Frontend\n'
    printf '  6) Workbench Runtime\n'
    printf '  7) Workbench Runtime Gateway\n'
    printf '  8) Runtime Sandbox 镜像\n'
    printf '  9) PostgreSQL\n'
    printf ' 10) Redis\n'
    printf ' 11) RabbitMQ\n'
    printf ' 12) MinIO\n'
    printf '  0) 返回\n'
    read -r -p '请选择 [0-12]: ' choice
    case "$choice" in
      1)
        enforce_studio_cookie_mode
        update_service_version "Studio API" studio_get_env studio_set_env studio_compose STUDIO_IMAGE STUDIO_VERSION studio 240 y "$STUDIO_ENV_FILE"
        ;;
      2)
        enforce_studio_cookie_mode
        update_service_version "Studio Frontend" studio_get_env studio_set_env studio_compose STUDIO_FRONTEND_IMAGE STUDIO_FRONTEND_VERSION studio-frontend 240 y "$STUDIO_ENV_FILE"
        ;;
      3)
        enforce_studio_cookie_mode
        update_service_version "Studio Node Sandbox" studio_get_env studio_set_env studio_compose NODE_SANDBOX_IMAGE NODE_SANDBOX_VERSION node-sandbox 240 y "$STUDIO_ENV_FILE"
        ;;
      4)
        if workbench_env_exists; then
          warn "Workbench API 启动时可能执行数据库迁移，镜像恢复不会自动撤销迁移。"
          update_service_version "Workbench API" workbench_get_env workbench_set_env workbench_compose WORKBENCH_IMAGE WORKBENCH_VERSION workbench 300 y "$WORKBENCH_ENV_FILE"
        fi
        ;;
      5) if workbench_env_exists; then update_service_version "Workbench Frontend" workbench_get_env workbench_set_env workbench_compose WORKBENCH_FRONTEND_IMAGE WORKBENCH_FRONTEND_VERSION workbench-frontend 300 y "$WORKBENCH_ENV_FILE"; fi ;;
      6) if workbench_env_exists; then update_service_version "Workbench Runtime" workbench_get_env workbench_set_env workbench_compose RUNTIME_IMAGE RUNTIME_VERSION workbench-runtime-node 300 y "$WORKBENCH_ENV_FILE"; fi ;;
      7) if workbench_env_exists; then update_service_version "Workbench Runtime Gateway" workbench_get_env workbench_set_env workbench_compose RUNTIME_NGINX_IMAGE RUNTIME_NGINX_VERSION workbench-runtime 300 y "$WORKBENCH_ENV_FILE"; fi ;;
      8) if workbench_env_exists; then update_runtime_sandbox_image; fi ;;
      9)
        warn "更新 PostgreSQL 前必须完成数据库备份并确认版本升级兼容性。"
        update_service_version PostgreSQL dotenv_get set_env middleware_compose POSTGRES_IMAGE POSTGRES_VERSION postgresql 240 n "$ENV_FILE"
        ;;
      10)
        warn "更新 Redis 前必须完成备份并确认版本升级兼容性。"
        update_service_version Redis dotenv_get set_env middleware_compose REDIS_IMAGE REDIS_VERSION redis 240 n "$ENV_FILE"
        ;;
      11)
        warn "更新 RabbitMQ 前必须完成备份并确认版本升级兼容性。"
        update_service_version RabbitMQ dotenv_get set_env middleware_compose RABBITMQ_IMAGE RABBITMQ_VERSION rabbitmq 240 n "$ENV_FILE"
        ;;
      12)
        warn "更新 MinIO 前必须完成对象存储备份并确认版本升级兼容性。"
        update_service_version MinIO dotenv_get set_env middleware_compose MINIO_IMAGE MINIO_VERSION minio 240 n "$ENV_FILE"
        ;;
      0) return ;;
      *) warn "请输入 0 到 12 之间的数字。" ;;
    esac
  done
}

stop_studio_services() {
  studio_compose stop
  success "Studio 服务已停止。"
}

stop_workbench_services() {
  if ! workbench_env_exists; then
    return
  fi
  workbench_compose stop
  success "Workbench 服务已停止。"
}

stop_application_services() {
  stop_workbench_services
  stop_studio_services
}

stop_all_services() {
  stop_application_services
  middleware_compose stop
  success "共享中间件已停止。"
}

service_stop_menu() {
  local choice=""

  while true; do
    printf '\n服务停止菜单：\n'
    printf '  1) 停止 Studio\n'
    printf '  2) 停止 Workbench\n'
    printf '  3) 停止 Studio + Workbench\n'
    printf '  4) 停止全部（含共享中间件）\n'
    printf '  0) 返回\n'
    read -r -p '请选择 [0-4]: ' choice
    case "$choice" in
      1) if confirm "确认停止 Studio？" n; then stop_studio_services; fi ;;
      2) if confirm "确认停止 Workbench？" n; then stop_workbench_services; fi ;;
      3) if confirm "确认停止 Studio 和 Workbench？" n; then stop_application_services; fi ;;
      4) if confirm "确认停止全部服务（含共享中间件）？" n; then stop_all_services; fi ;;
      0) return ;;
      *) warn "请输入 0 到 4 之间的数字。" ;;
    esac
  done
}

container_state_is_abnormal() {
  local state="$1"
  local health="$2"
  local exit_code="$3"

  [[ "$health" == unhealthy ]] && return 0
  [[ "$state" == running ]] && return 1
  [[ "$state" == exited && "$exit_code" == 0 ]] && return 1
  return 0
}

show_container_health() {
  local ids_file=""
  local id=""
  local details=""
  local project=""
  local service=""
  local image=""
  local state=""
  local health=""
  local exit_code=""
  local restarts=""
  local count=0
  local issues=0

  ids_file="$(mktemp)"
  middleware_compose ps -a -q >> "$ids_file" 2>/dev/null || true
  studio_compose ps -a -q >> "$ids_file" 2>/dev/null || true
  if [[ -f "$WORKBENCH_ENV_FILE" ]]; then
    workbench_compose ps -a -q >> "$ids_file" 2>/dev/null || true
  fi

  printf '\n%-20s %-28s %-12s %-10s %-8s %s\n' \
    "项目" "服务" "状态" "健康度" "重启次数" "镜像"
  while read -r id; do
    [[ -n "$id" ]] || continue
    details="$(docker inspect --format \
      '{{index .Config.Labels "com.docker.compose.project"}}{{"\t"}}{{index .Config.Labels "com.docker.compose.service"}}{{"\t"}}{{.Config.Image}}{{"\t"}}{{.State.Status}}{{"\t"}}{{if .State.Health}}{{.State.Health.Status}}{{else}}未配置{{end}}{{"\t"}}{{.State.ExitCode}}{{"\t"}}{{.RestartCount}}' \
      "$id" 2>/dev/null || true)"
    [[ -n "$details" ]] || continue
    IFS=$'\t' read -r project service image state health exit_code restarts <<< "$details"
    printf '%-20s %-28s %-12s %-10s %-8s %s\n' \
      "$project" "$service" "$state" "$health" "$restarts" "$image"
    count=$((count + 1))
    if container_state_is_abnormal "$state" "$health" "$exit_code"; then
      issues=$((issues + 1))
    fi
  done < <(sort -u "$ids_file")
  unlink "$ids_file"

  if ((count == 0)); then
    warn "未找到 BasilOS Compose 容器。"
  elif ((issues == 0)); then
    success "共检查 $count 个容器，未发现异常状态。"
  else
    warn "共检查 $count 个容器，其中 $issues 个状态异常；请查看对应容器日志。"
  fi
}

# Operations shared by first installation and subsequent maintenance.
compose_recreate() { ops up "${1%_compose}" "$2" --recreate --no-deps; }

ops() { python3 "$SUPPORT_DIR/deploy-support.py" "$@"; }

environment_check() {
  if ! command -v python3 >/dev/null || ! command -v curl >/dev/null ||
    ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
    confirm '缺少 Python 3、curl、Docker 或 Compose，是否安装缺少的组件？' y || return 1
    bash "$SUPPORT_DIR/install-docker.sh" || return 1
  fi
  docker info >/dev/null 2>&1 || { warn 'Docker 未启动或无访问权限；Linux 可用 sudo bash deploy.sh。'; return 1; }
  docker compose up --help | grep -q -- '--wait' || { warn 'Compose 版本过旧，请升级 Compose 插件。'; return 1; }
  require_command python3
  require_command curl
  ops check-files || return 1
  success "环境检查通过：$(uname -s)/$(uname -m)"
}

restore_middleware_modes() {
  local files
  files="$(dotenv_get COMPOSE_FILE)"
  POSTGRES_MODE=external; REDIS_MODE=external; RABBITMQ_MODE=external; STORAGE_MODE=external
  [[ "$files" != *compose/db.yaml* ]] || POSTGRES_MODE=local
  [[ "$files" != *compose/cache.yaml* ]] || REDIS_MODE=local
  [[ "$files" != *compose/mq.yaml* ]] || RABBITMQ_MODE=local
  [[ "$files" != *compose/storage.yaml* ]] || STORAGE_MODE=local
  COMPOSE_FILES="$files"
}

existing_middleware_test() {
  case "$1" in
    postgresql)
      if [[ "$POSTGRES_MODE" == local ]]; then
        test_postgresql_local "$(dotenv_get POSTGRESQL_USERNAME)" "$(dotenv_get POSTGRESQL_PASSWORD)" "$(dotenv_get POSTGRESQL_BOOTSTRAP_DATABASE)"
      else
        ops pull "$(dotenv_get POSTGRES_IMAGE):$(dotenv_get POSTGRES_VERSION)" || return 1
        test_postgresql_external "$(dotenv_get POSTGRESQL_HOST)" "$(dotenv_get POSTGRESQL_PORT)" "$(dotenv_get POSTGRESQL_USERNAME)" "$(dotenv_get POSTGRESQL_PASSWORD)" "$(dotenv_get POSTGRESQL_BOOTSTRAP_DATABASE)"
      fi ;;
    redis)
      if [[ "$REDIS_MODE" == local ]]; then
        test_redis_local "$(dotenv_get REDIS_PASSWORD)"
      else
        ops pull "$(dotenv_get REDIS_IMAGE):$(dotenv_get REDIS_VERSION)" || return 1
        test_redis_external "$(dotenv_get REDIS_HOST)" "$(dotenv_get REDIS_PORT)" "$(dotenv_get REDIS_PASSWORD)" "$(dotenv_get REDIS_SSL)"
      fi ;;
    rabbitmq)
      local host port
      host="$(dotenv_get RABBITMQ_HOST)"; port="$(dotenv_get RABBITMQ_MANAGEMENT_PORT)"
      if [[ "$RABBITMQ_MODE" == local ]]; then host=127.0.0.1; port="$(dotenv_get RABBITMQ_MANAGEMENT_HOST_PORT)"; fi
      test_rabbitmq_endpoint "$host" "$port" "$(dotenv_get RABBITMQ_USERNAME)" "$(dotenv_get RABBITMQ_PASSWORD)" ;;
    minio)
      if [[ "$STORAGE_MODE" == local ]]; then
        middleware_compose exec -T minio curl --fail --silent http://127.0.0.1:9000/minio/health/ready >/dev/null
      else
        curl --fail --silent --show-error --connect-timeout 10 --max-time 20 "$(dotenv_get MINIO_EXPOSE_URL)/minio/health/ready" >/dev/null
      fi ;;
    aliyun-oss) test_url_reachable "$(dotenv_get ALI_OSS_ENDPOINT)" ;;
    azure-blob) test_url_reachable "$(dotenv_get AZURE_BLOB_ENDPOINT)" ;;
  esac
}

reuse_middleware() {
  local service="$1" keys='' key value mode=external choice id
  case "$service" in
    postgresql) keys='POSTGRESQL_HOST POSTGRESQL_PORT POSTGRESQL_USERNAME POSTGRESQL_PASSWORD POSTGRESQL_BOOTSTRAP_DATABASE'; mode="$POSTGRES_MODE" ;;
    redis) keys='REDIS_HOST REDIS_PORT REDIS_PASSWORD'; mode="$REDIS_MODE" ;;
    rabbitmq) keys='RABBITMQ_HOST RABBITMQ_PORT RABBITMQ_USERNAME RABBITMQ_PASSWORD RABBITMQ_VIRTUAL_HOST'; mode="$RABBITMQ_MODE" ;;
    storage)
      service="$(dotenv_get FILE_SERVICE_SELECTOR)"; mode="$STORAGE_MODE"
      case "$service" in
        minio) keys='MINIO_HOST MINIO_PORT MINIO_USERNAME MINIO_PASSWORD MINIO_EXPOSE_URL' ;;
        aliyun-oss) keys='ALI_OSS_ACCESS_ID ALI_OSS_ACCESS_KEY ALI_OSS_ENDPOINT' ;;
        azure-blob) keys='AZURE_BLOB_ACCOUNT_NAME AZURE_BLOB_ACCOUNT_KEY AZURE_BLOB_ENDPOINT' ;;
        *) return 1 ;;
      esac ;;
  esac
  while read -r key; do
    value="$(dotenv_get "$key")"
    if [[ -z "$value" || "$value" == *CHANGE_ME* ]]; then
      if [[ "$mode" == local ]] && [[ -n "$(middleware_compose ps -a -q "$service" 2>/dev/null)" ]]; then
        die "$service 已有容器但配置不完整；请恢复原 .env.middleware，不能用新密码覆盖已有数据。"
      fi
      return 1
    fi
  done < <(printf '%s\n' "$keys" | tr ' ' '\n')
  while true; do
    info "检查已有 ${service}（复用环境文件中的连接信息）"
    if existing_middleware_test "$service"; then
      success "$service 检查通过，跳过配置和重新部署。"
      return 0
    fi
    printf '  1) 用原配置启动/恢复本地服务  2) 重新检查  3) 重新配置  0) 返回主菜单\n'
    read -r -p '请选择 [0-3]: ' choice
    case "$choice" in
      1)
        if [[ "$mode" == local ]]; then
          ops up middleware "$service" || die "$service 恢复失败；配置已保留。"
          if [[ "$service" == postgresql ]]; then middleware_compose run --rm postgresql-init || die '数据库初始化失败。'; fi
        else warn '此服务是外部中间件，请在服务所在主机恢复。'; fi ;;
      2) ;;
      3) confirm "确认重新配置 ${service}？已有数据的密码不会被自动重置。" n && return 1 ;;
      0) die '已保留配置，结束本次部署。' ;;
    esac
  done
}

restart_services() {
  local group="$1" service="${2-}" frontend id
  if [[ -n "$service" ]]; then
    id="$("${group}_compose" ps -a -q "$service")"
    [[ -n "$id" ]] || die '该服务尚未部署，请先用安装菜单。'
    ops up "$group" "$service" --recreate --no-deps
  else
    [[ -n "$("${group}_compose" ps -a -q)" ]] || die '该项目尚未部署，请先用安装菜单。'
    ops up "$group" --recreate
  fi
  # Refresh static backend DNS after recreation.
  for group in studio workbench; do
    frontend="${group}-frontend"
    if [[ -n "$("${group}_compose" ps -q "$frontend" 2>/dev/null)" ]]; then
      "${group}_compose" exec -T "$frontend" nginx -s reload
    fi
  done
  success '服务已重新创建，环境文件中的修改已生效。'
}

service_restart_menu() {
  local choice group service
  printf '\n重启并加载环境变量：\n  1) Studio 全部\n  2) Workbench 全部\n  3) Studio API\n  4) Studio Frontend\n  5) Node Sandbox\n  6) Workbench API\n  7) Workbench Frontend\n  8) Runtime Node\n  9) Runtime Gateway\n  10) PostgreSQL\n  11) Redis\n  12) RabbitMQ\n  13) MinIO\n  0) 返回\n'
  read -r -p '请选择 [0-13]: ' choice
  case "$choice" in
    0) return ;; 1) restart_services studio ;; 2) restart_services workbench ;;
    3) restart_services studio studio ;; 4) restart_services studio studio-frontend ;;
    5) restart_services studio node-sandbox ;; 6) restart_services workbench workbench ;;
    7) restart_services workbench workbench-frontend ;; 8) restart_services workbench workbench-runtime-node ;;
    9) restart_services workbench workbench-runtime ;; 10) restart_services middleware postgresql ;;
    11) restart_services middleware redis ;; 12) restart_services middleware rabbitmq ;; 13) restart_services middleware minio ;;
    *) warn '选项无效。' ;;
  esac
}

run_menu_action() {
  local status
  set +e
  ( set -Eeuo pipefail; "$@" )
  status=$?
  set -e
  [[ "$status" -eq 0 ]] || warn "操作未完成（退出码 ${status}），已返回菜单；请根据上方原因处理后重试。"
}

install_selected() {
  prepare_deployment
  "$1"
}

maintenance_selected() {
  prepare
  "$@"
}

diagnose_environment() {
  prepare
  local group
  for group in middleware studio workbench; do
    ops check-images "$group"
  done
  ops pull "$(workbench_get_env RUNTIME_SANDBOX_IMAGE):$(workbench_get_env RUNTIME_SANDBOX_VERSION)"
}

perform_action() {
  case "$1" in
    1) install_selected deploy_all ;;
    2) install_selected deploy_studio ;;
    3) install_selected deploy_workbench ;;
    4) maintenance_selected service_update_menu ;;
    5) prepare_health_check; show_container_health ;;
    6) prepare_health_check; service_stop_menu ;;
    7) maintenance_selected service_restart_menu ;;
    8) maintenance_selected bash "${SUPPORT_DIR:-$DEPLOY_DIR}/setup-domain-ssl.sh" ;;
    9) diagnose_environment ;;
  esac
}

installed_action() {
  if [[ -f "$DEPLOY_DIR/.aos-selected.sh" ]]; then
    # Start a fresh Bash so historical scripts use their own functions and helper paths.
    bash -c "$(declare -f perform_action)"$'\nsource "$1"\nperform_action "$2"' bash "$DEPLOY_DIR/.aos-selected.sh" "$1"
  else
    perform_action "$1"
  fi
}

package_install() {
  require_command python3
  local status=0
  python3 "$SUPPORT_DIR/release-install.py" "$1" || status=$?
  case "$status" in
    0) installed_action 1 ;;
    2) return 0 ;;
    *) return "$status" ;;
  esac
}

deployment_menu() {
  local choice=""

  while true; do
    printf '\nBasilOS 部署与运维菜单：\n'
    printf '  1) 配置并部署 Studio + Workbench\n'
    printf '  2) 配置并部署 Studio\n'
    printf '  3) 配置并部署 Workbench\n'
    printf '  4) 更新已部署服务的 Docker tag\n'
    printf '  5) 查看容器健康度\n'
    printf '  6) 停止服务\n'
    printf '  7) 重启服务（加载最新环境变量）\n'
    printf '  8) 配置域名与 HTTPS\n'
    printf '  9) 环境、部署文件与镜像检查\n'
    printf '  10) 选择版本、下载并安装部署包\n'
    printf '  11) 完全删除当前部署（容器、镜像及本地数据）\n'
    printf '  0) 退出\n'
    read -r -p '请选择 [0-11]: ' choice || return 0
    case "$choice" in
      [1-9]) run_menu_action installed_action "$choice" ;;
      10) run_menu_action package_install choose ;;
      11) run_menu_action python3 "$SUPPORT_DIR/reset-deployment.py" ;;
      0) return ;;
      *) warn "请输入 0 到 11 之间的数字。" ;;
    esac
  done
}

prepare() {
  [[ -t 0 ]] || die "该脚本需要在交互式终端中运行。"
  environment_check || die "环境检查未通过。"
  require_command docker
  require_command curl
  docker compose version >/dev/null
  docker info >/dev/null 2>&1 || die "Docker 服务不可用或当前用户无权访问。"
  [[ -f "$MIDDLEWARE_COMPOSE_FILE" ]] || die "缺少 compose/middleware.yaml"
  [[ -f "$STUDIO_COMPOSE_FILE" ]] || die "缺少 docker-compose.studio.yaml"
  [[ -f "$ENV_TEMPLATE" ]] || die "缺少 .env.middleware.example"
  [[ -f "$STUDIO_ENV_TEMPLATE" ]] || die "缺少 .env.studio.example"

  cd "$DEPLOY_DIR"
  [[ ! -L "$ENV_FILE" ]] || die "拒绝修改符号链接环境文件：$ENV_FILE"
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    info "已创建 $ENV_FILE"
  fi
  chmod 600 "$ENV_FILE"

  [[ ! -L "$STUDIO_ENV_FILE" ]] || die "拒绝修改符号链接环境文件：$STUDIO_ENV_FILE"
  if [[ ! -f "$STUDIO_ENV_FILE" ]]; then
    cp "$STUDIO_ENV_TEMPLATE" "$STUDIO_ENV_FILE"
    info "已创建 $STUDIO_ENV_FILE"
  fi
  chmod 600 "$STUDIO_ENV_FILE"

  restore_middleware_modes
  prepare_workbench_env
  ensure_shared_network
}

prepare_health_check() {
  require_command docker
  docker compose version >/dev/null
  docker info >/dev/null 2>&1 || die "Docker 服务不可用或当前用户无权访问。"
  [[ -f "$MIDDLEWARE_COMPOSE_FILE" ]] || die "缺少 compose/middleware.yaml"
  [[ -f "$STUDIO_COMPOSE_FILE" ]] || die "缺少 docker-compose.studio.yaml"
  [[ -f "$ENV_FILE" ]] || die "缺少 .env.middleware，请先完成部署。"
  [[ -f "$STUDIO_ENV_FILE" ]] || die "缺少 .env.studio，请先完成部署。"
  cd "$DEPLOY_DIR"
}

self_test() {
  local original_env_file="$ENV_FILE"
  local original_studio_env_file="$STUDIO_ENV_FILE"
  local original_workbench_env_file="$WORKBENCH_ENV_FILE"
  local test_file=""
  local studio_test_file=""
  local workbench_test_file=""
  local prompted_version=""
  local expected="pass#\$word\\tail"

  test_file="$(mktemp)"
  printf 'COMPOSE_FILE=compose/middleware.yaml\nTEST_VALUE=old\n' > "$test_file"
  ENV_FILE="$test_file"
  set_env TEST_VALUE "$expected"
  [[ "$(dotenv_get TEST_VALUE)" == "$expected" ]]

  studio_test_file="$(mktemp)"
  printf 'ENABLE_HTTPS_COOKIES=true\n' > "$studio_test_file"
  STUDIO_ENV_FILE="$studio_test_file"
  enforce_studio_cookie_mode
  [[ "$(studio_get_env ENABLE_HTTPS_COOKIES)" == false ]]

  POSTGRES_MODE=local
  REDIS_MODE=external
  RABBITMQ_MODE=local
  STORAGE_MODE=external
  rebuild_compose_files
  [[ "$(dotenv_get COMPOSE_FILE)" == \
    'compose/middleware.yaml,compose/db.yaml,compose/mq.yaml' ]]

  workbench_test_file="$(mktemp)"
  printf 'TEST_VALUE=old\nTEST_VERSION=CHANGE_ME_VERSION\nAPP_URL=http://deploy.example.com:31001\n' > "$workbench_test_file"
  WORKBENCH_ENV_FILE="$workbench_test_file"
  workbench_set_env TEST_VALUE "$expected"
  [[ "$(workbench_get_env TEST_VALUE)" == "$expected" ]]

  (
    prompt_url() { die "已有平台网关不应重复询问"; }
    workbench_set_env BASILOS_GATEWAY_HOST https://studio.example.com
    ensure_workbench_gateway
    [[ "$(workbench_get_env BASILOS_GATEWAY_HOST)" == https://studio.example.com/ ]]
    workbench_set_env BASILOS_GATEWAY_HOST CHANGE_ME_GATEWAY_URL
    prompt_url() { printf -v "$1" '%s' http://studio-frontend; }
    ensure_workbench_gateway
    [[ "$(workbench_get_env BASILOS_GATEWAY_HOST)" == http://studio-frontend/ ]]
  )

  parse_url 'https://files.example.com:9443/path'
  [[ "$URL_SCHEME" == https ]]
  [[ "$URL_AUTHORITY" == 'files.example.com:9443' ]]
  [[ "$URL_HOST" == files.example.com ]]
  [[ "$URL_PORT" == 9443 ]]

  image_version_valid 'v1.2.3-alpine'
  ! image_version_valid 'repo/image:tag'
  prompt_image_version prompted_version 'Test Docker tag' current <<< ''
  [[ "$prompted_version" == current ]]
  DEPLOYMENT_ACCESS_HOST=deploy.example.com
  [[ "$(deployment_access_url 38080)" == 'http://deploy.example.com:38080' ]]
  DEPLOYMENT_ACCESS_HOST='[2001:db8::1]'
  [[ "$(deployment_access_url 80)" == 'http://[2001:db8::1]:80' ]]
  DEPLOYMENT_ACCESS_HOST=
  ! container_state_is_abnormal running healthy 0
  ! container_state_is_abnormal exited 未配置 0
  container_state_is_abnormal exited 未配置 1

  (
    ensure_image_version workbench_get_env workbench_set_env TEST_VERSION Test <<< 'v1.2.3'
    [[ "$(workbench_get_env TEST_VERSION)" == v1.2.3 ]]

    DEPLOYMENT_ACCESS_HOST=deploy.example.com
    prompt_url() {
      [[ "$3" == 'http://deploy.example.com:38080' ]]
      printf -v "$1" '%s' "$3"
    }
    ensure_workbench_url APP_URL 'Test API' 38080 >/dev/null 2>&1
    # HTTP 同源代理可以与内部 API 映射使用不同端口，不能覆盖已有公网地址。
    [[ "$WORKBENCH_VALUE" == 'http://deploy.example.com:31001' ]]
    workbench_set_env APP_URL CHANGE_ME_WORKBENCH_API_URL
    ensure_workbench_url APP_URL 'Test API' 38080 >/dev/null 2>&1
    [[ "$WORKBENCH_VALUE" == 'http://deploy.example.com:38080' ]]
  )

  (
    local calls=""
    local up_arguments=""
    local updated_key=""
    local updated_value=""
    unset TEST_VERSION
    ops() { test_compose pull; }
    compose_recreate() { test_compose up --no-deps --pull never --force-recreate; }
    test_getter() {
      if [[ "$1" == TEST_IMAGE ]]; then printf 'repo/service'; else printf 'old'; fi
    }
    test_setter() {
      updated_key="$1"
      updated_value="$2"
    }
    test_compose() {
      calls+="$1 "
      case "$1" in
        ps) printf 'container-id\n' ;;
        config) return 0 ;;
        pull) [[ "${TEST_VERSION-}" == new ]] ;;
        up) up_arguments="$*" ;;
      esac
    }
    prompt_image_version() {
      printf -v "$1" '%s' new
    }
    confirm() {
      return 0
    }

    update_service_version Test test_getter test_setter test_compose \
      TEST_IMAGE TEST_VERSION service 10 y "$workbench_test_file" >/dev/null
    [[ "$updated_key" == TEST_VERSION ]]
    [[ "$updated_value" == new ]]
    # 初始 ps 运行在命令替换的子 Shell 中，不会修改父 Shell 的 calls。
    [[ "$calls" == 'config pull config up ps ' ]]
    [[ "$up_arguments" == *'--no-deps'* ]]
    [[ "$up_arguments" == *'--pull'* ]]
    [[ "$up_arguments" == *'never'* ]]
    [[ "$up_arguments" == *'--force-recreate'* ]]
    [[ "${TEST_VERSION+x}" != x ]]
    rm -f -- "${workbench_test_file}.bak.update-service-old-"*
  )

  (
    local setter_called=false
    unset TEST_VERSION
    ops() { test_compose pull; }
    compose_recreate() { test_compose up --no-deps --pull never --force-recreate; }
    test_getter() {
      if [[ "$1" == TEST_IMAGE ]]; then printf 'repo/service'; else printf 'old'; fi
    }
    test_setter() {
      setter_called=true
    }
    test_compose() {
      case "$1" in
        ps) printf 'container-id\n' ;;
        config) return 0 ;;
        pull) return 1 ;;
      esac
    }
    prompt_image_version() {
      printf -v "$1" '%s' new
    }
    confirm() {
      return 0
    }

    ! update_service_version Test test_getter test_setter test_compose \
      TEST_IMAGE TEST_VERSION service 10 y "$workbench_test_file" >/dev/null 2>&1
    [[ "$setter_called" == false ]]
    [[ "${TEST_VERSION+x}" != x ]]
  )

  (
    local calls=""
    prepare() {
      calls+="prepare "
    }
    run_menu_action() { "$@"; }
    installed_action() { perform_action "$1"; }
    package_install() { :; }
    service_update_menu() {
      calls+="update"
    }

    main <<< '0' >/dev/null
    [[ -z "$calls" ]]
    deployment_menu <<< $'4\n0\n' >/dev/null
    [[ "$calls" == 'prepare update' ]]
  )

  (
    local calls=""
    workbench_env_exists() { return 0; }
    workbench_compose() { calls+="workbench "; }
    studio_compose() { calls+="studio "; }
    middleware_compose() { calls+="middleware"; }
    confirm() { return 0; }

    service_stop_menu <<< $'4\n0\n' >/dev/null
    [[ "$calls" == 'workbench studio middleware' ]]
  )

  unlink "$test_file"
  unlink "$studio_test_file"
  unlink "$workbench_test_file"
  ENV_FILE="$original_env_file"
  STUDIO_ENV_FILE="$original_studio_env_file"
  WORKBENCH_ENV_FILE="$original_workbench_env_file"
  success "deploy.sh 自检通过。"
}

main() {
  if [[ -f "$DEPLOY_DIR/.aos-selected.sh" && "${1-}" =~ ^--(health|check|update)$ && "${BASH_SOURCE[0]##*/}" != .aos-selected.sh ]]; then
    bash "$DEPLOY_DIR/.aos-selected.sh" "$@"
    return
  fi
  case "${1-}" in
    --self-test)
      self_test
      return
      ;;
    --update)
      [[ $# -eq 1 ]] || die "用法：./deploy.sh [--self-test|--update|--health|--check]"
      prepare
      service_update_menu
      return
      ;;
    --check)
      environment_check
      return
      ;;
    --health)
      [[ $# -eq 1 ]] || die "用法：./deploy.sh [--self-test|--update|--health|--check]"
      prepare_health_check
      show_container_health
      return
      ;;
    '') ;;
    *) die "用法：./deploy.sh [--self-test|--update|--health|--check]" ;;
  esac

  if [[ -f "$DEPLOY_DIR/.aos-install/pending.json" ]]; then
    run_menu_action package_install resume
  fi
  deployment_menu
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
