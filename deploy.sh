#!/usr/bin/env bash
# aos-work deployment release: v2026.11.19

set -Eeuo pipefail
export LC_ALL=C
IFS=$'\n\t'

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export BASIL_DEPLOY_DIR="$DEPLOY_DIR"
SUPPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aos-work.XXXXXXXX")"
trap 'rm -rf -- "$SUPPORT_DIR"' EXIT
cat > "$SUPPORT_DIR/deployment_state.py" <<'AOS_EMBEDDED_FILE_END'
"""Deployment-local baseline for package files, configuration and Docker resources."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ENV_FILES = tuple('.env.' + group for group in ('studio', 'workbench', 'middleware'))
PACKAGE_FILES = (
    'docker-compose.studio.yaml', 'docker-compose.workbench.yaml',
    *(f'compose/{name}.yaml' for name in ('middleware', 'db', 'cache', 'mq', 'storage')),
    'workbench/storage/templates/AGENTS.md', 'workbench/storage/nginx/runtime-nginx.conf',
)
DIRECTORIES = ('data', 'compose', 'workbench', 'workbench/storage', 'workbench/storage/nginx',
               'workbench/storage/templates')
STATE = '.aos-install/baseline.json'


def save(path, obj):
    if path.resolve() != path:
        raise ValueError(f'Refusing state path through symlink: {path}')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode='w', delete=False) as f:
        json.dump(obj, f, indent=2)
    os.replace(f.name, path)


def begin(root):
    path = root / STATE
    if path.resolve() != path:
        raise ValueError('Unexpected link in the deployment state directory.')
    if path.is_file():
        return
    legacy = any((root / n).exists() for n in ('.aos-selected.sh', '.domains.json', 'data/postgresql',
                                               'workbench/storage/user'))
    files = {}
    for name in (*ENV_FILES, *PACKAGE_FILES):
        p = root / name
        if p.resolve() != p:
            raise ValueError(f'Unexpected symlink: {p}')
        if p.is_file() and not (legacy and name in ENV_FILES):
            files[name] = [p.read_text(), p.stat().st_mode & 0o777]
    def docker(*args):
        return subprocess.check_output(['docker', *args], text=True).splitlines()
    images = [] if legacy else docker('image', 'ls', '-a', '--no-trunc', '--format', '{{.Repository}}:{{.Tag}} {{.ID}}')
    save(path, dict(files=files, directories=[n for n in DIRECTORIES if (root/n).is_dir()],
                    initial_images=images, legacy=legacy, original_backups=[
                        p.name for n in ENV_FILES for p in root.glob(n+'.bak*') if not legacy]))


def read(root):
    p = root / STATE
    return json.loads(p.read_text()) if p.is_file() else {}


def record_image(root, ref):
    state = read(root)
    if state:
        image_id = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', ref], text=True).strip()
        acquired = state.setdefault('acquired_images', [])
        row = ref + ' ' + image_id
        if row not in acquired:
            acquired.append(row)
            save(root / STATE, state)


def restore(root, state):
    for name in (*PACKAGE_FILES, *ENV_FILES):
        p = root / name
        if p.resolve() != p:
            raise ValueError(f'Refusing symlink: {p}')
        if name in state['files']:
            data, mode = state['files'][name]
            p.parent.mkdir(exist_ok=True, parents=True)
            with tempfile.NamedTemporaryFile(dir=p.parent, mode='w', delete=False) as f:
                f.write(data)
                os.fchmod(f.fileno(), mode)
            os.replace(f.name, p)
        else:
            p.unlink(missing_ok=True)
    for name in sorted(DIRECTORIES, key=lambda n: -len(Path(n).parts)):
        p = root / name
        if name not in state['directories'] and p.is_dir() and not any(p.iterdir()):
            p.rmdir()
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/host-state.sh" <<'AOS_EMBEDDED_FILE_END'
#!/usr/bin/env bash
# Root-owned records of host changes made on behalf of one deployment.
set -Eeuo pipefail
export LC_ALL=C
: "${BASIL_DEPLOY_DIR:?Missing deployment directory}"
key="$(printf '%s' "$(cd "$BASIL_DEPLOY_DIR" && pwd -P)" | sha256sum | cut -d' ' -f1)"
base=/var/lib/aos-work-deploy
ledger="$base/$key"
units=(docker.service docker.socket containerd.service nginx.service certbot.timer)
hostfiles=(/etc/apt/keyrings/basil-docker.asc /etc/apt/sources.list.d/basil-docker.list /etc/letsencrypt/renewal-hooks/deploy/basil-nginx.sh)
if [[ "$EUID" != 0 && ! -e "$base" && ( "${1:-}" == preview || "${1:-}" == cleanup ) ]]; then exit 0; fi
[[ "$EUID" == 0 ]] || { echo 'Host changes require root.' >&2; exit 1; }

init() {
  install -d -m 0700 "$base" "$ledger"
  [[ ! -f "$ledger/ready" ]] || return 0
  local unit file
  for unit in "${units[@]}"; do
    systemctl is-active --quiet "$unit" && touch "$ledger/$unit.active"
    systemctl is-enabled --quiet "$unit" 2>/dev/null && touch "$ledger/$unit.enabled"
  done
  for file in "${hostfiles[@]}"; do
    [[ ! -L "$file" ]] || { echo "Unexpected symlink: $file"; return 1; }
    [[ ! -f "$file" ]] || cp -p "$file" "$ledger/${file##*/}.before"
  done
  for file in /var/lib/docker /var/lib/containerd; do
    [[ ! -e "$file" ]] || touch "$ledger/${file##*/}.existed"
  done
  getent group docker >/dev/null && touch "$ledger/docker.group-existed"
  [[ ! -e /var/www/basil-acme ]] || touch "$ledger/acme.existed"
  touch "$ledger/ready"
}

install_packages() {
  init
  local plan list pkg
  plan="$(apt-get -s --no-install-recommends --no-upgrade install "$@")" || return 1
  if grep -Eq '^(Remv |Inst [^ ]+ \[)' <<<"$plan"; then
    echo 'Installation would remove or upgrade existing system packages. Configure these dependencies with your system administrator.'
    return 1
  fi
  list="$(awk '/^Inst / {print $2}' <<<"$plan")"
  if [[ -n "$list" ]]; then
    { cat "$ledger/packages" 2>/dev/null || true; printf '%s\n' "$list"; } | sort -u > "$ledger/packages.next"
    mv "$ledger/packages.next" "$ledger/packages"
    DEBIAN_FRONTEND=noninteractive apt-get --no-install-recommends --no-upgrade -y install "$@"
  fi
}

installed_owned() {
  [[ -f "$ledger/packages" ]] || return 0
  local pkg status
  while read -r pkg; do
    status="$(dpkg-query -W -f='${db:Status-Status}' "$pkg" 2>/dev/null || true)"
    [[ -z "$status" || "$status" == not-installed ]] || printf '%s\n' "$pkg"
  done < "$ledger/packages"
}

accounts() {
  if [[ -d /etc/letsencrypt/accounts ]]; then
    find /etc/letsencrypt/accounts -mindepth 1 -type f -name regr.json | sort
  fi
}

cleanup() {
  [[ -f "$ledger/ready" ]] || return 0
  local file cert unit name actual
  local -a packages=()
  mapfile -t packages < <(installed_owned)
  if (( ${#packages[@]} )); then
    local plan
    plan="$(apt-get -s purge "${packages[@]}")" || return 1
    while read -r name; do
      grep -Fxq "$name" "$ledger/packages" || { echo "Retaining host packages: $name is outside this installation."; return 1; }
    done < <(awk '/^(Remv|Purg) /{print $2}' <<<"$plan")
    if grep -Eq '^(docker-ce|docker.io|containerd.io|containerd)$' "$ledger/packages"; then
      if command -v docker >/dev/null; then
        docker info >/dev/null 2>&1 || { echo 'Start Docker to verify remaining resources before cleanup.'; return 1; }
        for query in 'ps -aq' 'image ls -aq' 'volume ls -q' 'network ls -q --filter type=custom'; do
          actual="$(docker $query)" || return 1
          [[ -z "$actual" ]] || { echo 'Docker still has resources outside this deployment. Host cleanup deferred.'; return 1; }
        done
        if [[ "$(docker info --format '{{.DockerRootDir}}')" == /var/lib/docker ]]; then touch "$ledger/docker.default-root"; fi
      fi
      if command -v ctr >/dev/null && systemctl is-active --quiet containerd; then
        local ns
        while read -r ns; do
          [[ -z "$ns" || "$ns" == moby ]] && continue
          [[ -z "$(ctr -n "$ns" containers ls -q)$(ctr -n "$ns" images ls -q)" ]] || {
            echo "containerd namespace $ns is shared. Host cleanup deferred."; return 1; }
        done < <(ctr namespaces ls -q)
      fi
    fi
  fi
  if [[ -s "$ledger/packages" ]] && grep -Eq '^(nginx|nginx-core|nginx-full)$' "$ledger/packages"; then
    for file in /etc/nginx/conf.d/*.conf /etc/nginx/sites-enabled/*; do
      [[ ! -e "$file" ]] && continue
      [[ "$file" == /etc/nginx/sites-enabled/default && "$(readlink -f "$file")" == /etc/nginx/sites-available/default ]] && continue
      echo "Nginx still has a site at $file. Host cleanup deferred."; return 1
    done
  fi
  if [[ -s "$ledger/packages" ]] && grep -Fxq certbot "$ledger/packages"; then
    for file in /etc/letsencrypt/renewal/*.conf; do
      [[ -f "$file" ]] || continue
      name="${file##*/}"; name="${name%.conf}"
      if ! grep -Fxq "$name" "$ledger/certs" 2>/dev/null; then
        echo "Another certificate uses Certbot: $name. Host cleanup deferred."; return 1
      fi
    done
  fi
  if [[ -s "$ledger/certs" ]]; then
    local config=""
    if command -v nginx >/dev/null; then config="$(nginx -T 2>/dev/null)" || return 1; fi
    while read -r cert; do
      [[ -f "/etc/letsencrypt/renewal/$cert.conf" ]] || continue
      if grep -Fq "/live/$cert/" <<<"$config"; then
        echo "Certificate $cert is still in use. Host cleanup deferred."; return 1
      fi
      certbot delete --non-interactive --cert-name "$cert"
    done < "$ledger/certs"
  fi
  if [[ -f "$ledger/accounts.added" ]]; then
    while read -r file; do
      [[ -f "$file" && "$(realpath "$file")" == "$file" && "$file" == /etc/letsencrypt/accounts/*/regr.json ]] || continue
      local account_dir="${file%/*}"
      if grep -Fqs "${account_dir##*/}" /etc/letsencrypt/renewal/*.conf; then continue; fi
      rm -f -- "$file" "$account_dir/meta.json" "$account_dir/private_key.json"
      while [[ "$account_dir" == /etc/letsencrypt/accounts/* ]] && rmdir "$account_dir" 2>/dev/null; do
        account_dir="${account_dir%/*}"
      done
    done < "$ledger/accounts.added"
  fi
  if [[ -e "$ledger/nginx.used" ]] &&
     [[ ! -f "$ledger/nginx.service.active" || ( -f "$ledger/basil-nginx.sh.after" && ! -f "$ledger/basil-nginx.sh.before" ) ]] &&
     compgen -G '/etc/nginx/conf.d/basil-*.conf' >/dev/null; then
    echo 'Another AosWork site uses this Nginx instance. Host cleanup deferred.'
    return 1
  fi
  for file in "${hostfiles[@]}"; do
    name="${file##*/}"
    [[ -f "$ledger/$name.after" && -e "$file" ]] || continue
    actual="$(sha256sum "$file" | cut -d' ' -f1)"
    [[ "$actual" == "$(cat "$ledger/$name.after")" ]] || { echo "Host file changed: $file"; return 1; }
    if [[ -f "$ledger/$name.before" ]]; then cp -p "$ledger/$name.before" "$file"; else rm -- "$file"; fi
    rm "$ledger/$name.after"
  done
  for unit in "${units[@]}"; do
    case "$unit" in
      docker*|containerd*) [[ -e "$ledger/docker.used" ]] || continue ;;
      *) [[ -e "$ledger/nginx.used" ]] || continue ;;
    esac
    if [[ ! -f "$ledger/$unit.active" ]] && systemctl is-active --quiet "$unit"; then systemctl stop "$unit"; fi
    if [[ ! -f "$ledger/$unit.enabled" ]] && systemctl is-enabled --quiet "$unit" 2>/dev/null; then systemctl disable "$unit"; fi
  done
  if (( ${#packages[@]} )); then
    touch "$ledger/purge-started"
    DEBIAN_FRONTEND=noninteractive apt-get -y purge "${packages[@]}"
  fi
  if [[ -e "$ledger/purge-started" ]] && grep -Eq '^(docker-ce|docker.io)$' "$ledger/packages"; then
      for file in /var/lib/docker /var/lib/containerd; do
        if [[ "$file" == /var/lib/docker && ! -f "$ledger/docker.default-root" ]]; then continue; fi
        if [[ "$file" == /var/lib/containerd ]] && ! grep -Eq '^(containerd.io|containerd)$' "$ledger/packages"; then continue; fi
        command -v findmnt >/dev/null || { echo 'Install findmnt to verify mount boundaries.'; return 1; }
        [[ ! -e "$ledger/${file##*/}.existed" && ! -L "$file" && -d "$file" ]] || continue
        if findmnt -rn -o TARGET | awk -v p="$file" '$0==p || index($0,p"/")==1 {found=1} END {exit !found}'; then
          echo "Unmount $file before cleanup."; return 1
        fi
        rm -rf --one-file-system -- "$file"
      done
  fi
  if [[ -e "$ledger/purge-started" && ! -e "$ledger/docker.group-existed" ]] &&
     grep -Eq '^(docker-ce|docker.io)$' "$ledger/packages"; then
    local entry gid
    entry="$(getent group docker || true)"
    if [[ -n "$entry" && -z "${entry##*:}" ]]; then
      gid="$(cut -d: -f3 <<<"$entry")"
      if ! getent passwd | awk -F: -v g="$gid" '$4==g {used=1} END {exit !used}'; then groupdel docker; fi
    fi
  fi
  if [[ -e "$ledger/nginx.used" ]]; then
    for file in /var/www/basil-acme/.well-known/acme-challenge /var/www/basil-acme/.well-known /var/www/basil-acme; do
      if [[ ! -f "$ledger/acme.existed" && -d "$file" ]]; then rmdir "$file" 2>/dev/null || true; fi
    done
  fi
  rm -r -- "$ledger"
  rmdir "$base" 2>/dev/null || true
}

case "${1:-}" in
  setup) init ;;
  packages) shift; install_packages "$@" ;;
  mark) init; case "$2" in docker|nginx) touch "$ledger/$2.used" ;; *) exit 2 ;; esac ;;
  file) init; for file in "${hostfiles[@]}"; do
          if [[ "$file" == "$2" ]]; then sha256sum "$file" | cut -d' ' -f1 > "$ledger/${file##*/}.after"; exit 0; fi
        done; exit 2 ;;
  cert) init; accounts > "$ledger/accounts.before-request"; [[ "$2" =~ ^[a-zA-Z0-9.-]+$ ]] || exit 2
        if [[ ! -e "/etc/letsencrypt/renewal/$2.conf" ]] && ! grep -Fqx "$2" "$ledger/certs" 2>/dev/null; then
          printf '%s\n' "$2" >> "$ledger/certs"
        fi ;;
  cert-done) if [[ -f "$ledger/accounts.before-request" ]]; then
               accounts > "$ledger/accounts.after-request"
               comm -13 "$ledger/accounts.before-request" "$ledger/accounts.after-request" >> "$ledger/accounts.added"
             fi ;;
  preview) if [[ -d "$ledger" ]]; then
             printf 'Host packages installed by this deployment:\n'; installed_owned
             if [[ -s "$ledger/certs" ]]; then printf 'Certificates created by this deployment:\n'; cat "$ledger/certs"; fi
           else echo 'No host installation record. Existing host software will be retained.'; fi ;;
  recover) if [[ -f "$ledger/ready" && ! -f "$BASIL_DEPLOY_DIR/.aos-install/baseline.json" ]]; then
             bash "$0" preview
             read -r -p "To undo host setup, type DELETE $BASIL_DEPLOY_DIR: " answer || exit 0
             if [[ "$answer" == "DELETE $BASIL_DEPLOY_DIR" ]]; then cleanup; fi
           fi ;;
  cleanup) cleanup ;;
  *) exit 2 ;;
esac
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/release-install.py" <<'AOS_EMBEDDED_FILE_END'
"""Install public deployment files while preserving the operator's local configuration."""
import argparse
import deployment_state
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
VERSIONS = {'v2026.11.19': None}
# Keep verification for pending installs that resume from a manually uploaded archive.
ARCHIVED_VERSIONS = {
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
    print('Select a server package')
    for i, tag in enumerate(tags, 1):
        print(f'  {i}) {tag}  {RELEASES}/download/{tag}/deploy.tar.gz')
    if not tags:
        print('No published releases are listed.')
    print(f'GitHub Releases: {RELEASES}\nOr paste a trusted HTTPS link to deploy.tar.gz or deploy.tar.')
    value = input('Version number or package URL (0 to return): ').strip()
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
        raise ValueError('Enter a trusted HTTPS package URL.')
    name = PurePosixPath(parsed.path).name
    if name not in ('deploy.tar.gz', 'deploy.tar'):
        raise ValueError('Paste the release asset URL for deploy.tar.gz or deploy.tar.')
    return name


def check_path(root, path):
    # A live deployment may contain user-created symlinks.
    if path.resolve() != path or root not in path.parents:
        raise ValueError(f'Refusing symlink or path outside the deployment directory: {path}')


def unpack(archive, staging):
    if archive.stat().st_size > MAX_BYTES:
        raise ValueError('Archive is too large. Select deploy.tar.gz or deploy.tar.')
    if archive.name.endswith('.gz'):
        with gzip.open(archive, 'rb') as stream:
            if len(stream.read(MAX_BYTES + 1)) > MAX_BYTES:
                raise ValueError('Uncompressed archive exceeds the size limit.')
    total = 0
    seen = set()
    with tarfile.open(archive, 'r:*') as bundle:
        for entry in bundle:
            path = PurePosixPath(entry.name)
            if (path.is_absolute() or '..' in path.parts or path in seen or
                    not (entry.isfile() or entry.isdir()) or len(seen) >= 256):
                raise ValueError('Unsupported or duplicate archive entry.')
            seen.add(path)
            total += entry.size
            if total > MAX_BYTES:
                raise ValueError('Extracted data exceeds the size limit.')
            if entry.isfile() and str(path) in MODERN | LEGACY:
                dest = staging / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(entry) as src, dest.open('xb') as out:
                    shutil.copyfileobj(src, out)
                dest.chmod(0o755 if dest.suffix == '.sh' else 0o600 if dest.name.startswith('.env.') else 0o644)
    for layout in (MODERN, LEGACY):
        if all((staging / n).is_file() for n in layout):
            return layout
    raise ValueError('Package is missing deployment scripts, environment files or Compose definitions.')


def env_defaults(lines):
    return dict(line.split('=', 1) for line in lines if line and not line.lstrip().startswith('#') and '=' in line)


def install(root, folder, url):
    name = check_url(url)
    archive = folder / name
    check_path(root, archive)
    digest = None
    known_versions = {**ARCHIVED_VERSIONS, **VERSIONS}
    for tag, known in known_versions.items():
        if url == f'{RELEASES}/download/{tag}/deploy.tar.gz':
            digest = known
    sums = folder / 'SHA256SUMS'
    check_path(root, sums)
    if sums.is_file():
        lines = sums.read_text().splitlines()
        matches = [m[1] for line in lines if (m := re.fullmatch(r'([0-9a-f]{64})  '+re.escape(name), line))]
        if len(matches) != 1 or (digest and digest != matches[0]):
            raise ValueError('SHA256SUMS does not match the selected asset.')
        digest = matches[0]
    if archive.stat().st_size > MAX_BYTES:
        raise ValueError('Select a deployment package within the size limit.')
    if digest and hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError('SHA-256 mismatch. Upload the selected release again.')
    with tempfile.TemporaryDirectory(dir=folder) as tmp:
        stage = Path(tmp)
        layout = unpack(archive, stage)
        subprocess.run(['bash', '-n', str(stage / 'deploy.sh')], check=True)
        tag = re.fullmatch(re.escape(RELEASES) + r'/download/([^/]+)/deploy\.tar(?:\.gz)?', url)
        if tag and tag[1] in known_versions and known_versions[tag[1]] is None:
            marker = '# aos-work deployment release: ' + tag[1]
            if marker not in (stage / 'deploy.sh').read_text().splitlines():
                raise ValueError('Package version does not match the selected release.')
        selection = root / '.aos-install/selected.json'
        check_path(root, selection)
        previous = json.loads(selection.read_text()).get('defaults', {}) if selection.exists() else {}
        new_defaults = {}
        # Install the selected Compose definitions and version defaults. Keep the V1 launcher
        # for all versions, including older releases with different menu numbers.
        inputs = {name: stage / name for name in MODERN if name != 'deploy.sh'}
        if layout == LEGACY:
            inputs['compose/middleware.yaml'] = stage / 'docker-compose.middleware.yaml'
            for name in ENV:
                inputs[name] = stage / (name + '.example')
        staged = []
        for name, src in sorted(inputs.items()):
            dest = root / name
            check_path(root, dest)
            if dest.exists() and not dest.is_file():
                raise ValueError(f'Destination is not a regular file: {dest}')
            if name in ENV:
                lines = src.read_text().splitlines()
                new_defaults[name] = env_defaults(lines)
                if dest.exists():
                    template = Path(__file__).parent / (name + '.example')
                    defaults = previous.get(name, env_defaults(template.read_text().splitlines()))
                    # Carry local overrides (including custom keys) across package versions.
                    live = env_defaults(dest.read_text().splitlines())
                    edited = {k: f'{k}={v}' for k, v in live.items() if defaults.get(k) != v}
                    lines = [edited.pop(line.partition('=')[0], line) for line in lines]
                    src.write_text('\n'.join([*lines, *edited.values()]) + '\n')
            if name in WORKBENCH and dest.exists():
                continue
            staged.append((src, dest))
        applied = []
        try:
            for index, (src, dest) in enumerate(staged):
                backup = None
                if dest.exists():
                    backup = stage / f'backup-{index}'
                    shutil.copy2(dest, backup)
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.replace(src, dest)
                applied.append((dest, backup))
            deployment_state.save(selection, {'url': url, 'defaults': new_defaults})
        except BaseException:
            for dest, backup in reversed(applied):
                if backup:
                    os.replace(backup, dest)
                else:
                    dest.unlink(missing_ok=True)
            raise


def offline(folder, name):
    print(f'Download the selected version from {RELEASES}.\nUpload it to {folder / name}.\n'
          f'Optionally upload its SHA256SUMS to {folder}. Run sudo bash deploy.sh again to resume.')


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
            print('Downloading: ' + url, flush=True)
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
            print(f'Package validation failed: {error}')
            offline(folder, name)
            return False
        print('Server package ready. Select Deploy AosWork to start services.', flush=True)
        pending.unlink()
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('choose', 'resume'))
    try:
        ready = run(Path(os.environ['BASIL_DEPLOY_DIR']).resolve(), parser.parse_args().action == 'resume')
    except (ValueError, KeyError, OSError, EOFError) as error:
        parser.exit(1, f'Package installation failed: {error}\n')
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
import deployment_state

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
        raise ValueError('Cleanup requires a local Docker Unix socket.')


def local_path(value):
    # Docker Desktop exposes Mac bind sources with a /host_mnt prefix.
    if sys.platform == 'darwin' and value.startswith('/host_mnt/'):
        value = value.removeprefix('/host_mnt')
    return Path(value)


def paths_to_reset(root, env):
    if len(root.parts) < 3 or root == Path.home() or not ((root / 'docker-compose.workbench.yaml').is_file() or (root / deployment_state.STATE).is_file()):
        raise ValueError('Unrecognized deployment directory.')
    baseline = deployment_state.read(root)
    files = [root / n for n in ('data/postgresql', 'data/redis', 'data/rabbitmq', 'data/minio',
                                 'data/studio-logs', 'workbench/frontend-logs', '.domains.json', '.aos-install/pending.json')]
    minio = Path(env['middleware'].get('MINIO_DATA_HOST_PATH', './data/minio'))
    custom = (root / minio).resolve()
    if custom.is_relative_to(root / 'data') and custom != root / 'data':
        files.append(custom)
    storage = root / 'workbench/storage'
    if storage.resolve() != storage:
        raise ValueError('Workbench storage path contains a symlink.')
    if storage.is_dir():
        for child in storage.iterdir():
            if child.name not in ('templates', 'nginx'):
                files.append(child)
            elif child.is_symlink():
                raise ValueError(f'Review the symlink before cleanup: {child}')
            elif child.is_dir():
                keep = 'AGENTS.md' if child.name == 'templates' else 'runtime-nginx.conf'
                files.extend(p for p in child.iterdir() if p.name != keep)
    for g in GROUPS:
        files.append(root / ('.env.' + g))
        files.extend(p for p in root.glob('.env.' + g + '.bak*') if p.name not in baseline.get('original_backups', []))
    paths = sorted({p for p in files if p.exists() or p.is_symlink()})
    mounts = set()
    if Path('/proc/self/mountinfo').is_file():
        for row in Path('/proc/self/mountinfo').read_text().splitlines():
            mounts.add(Path(re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), row.split()[4])))
    for p in paths:
        if p.resolve() != p or p.is_mount() or any(m == p or p in m.parents for m in mounts):
            raise ValueError(f'Cleanup path contains a symlink or mount: {p}')
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
                    raise ValueError(f'Another container {c["Name"]} also mounts {p}. Resolve shared storage before cleanup.')
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
            kept.append('Shared or external network: ' + net['Name'])
    private_volumes = []
    for volume in objects('volume', sorted(volumes)):
        name = volume['Name']
        if name not in held_vols and ((volume.get('Labels') or {}).get(PROJECT) in projects or re.fullmatch('[0-9a-f]{64}', name)):
            private_volumes.append(name)
        else:
            kept.append('Shared or external volume: ' + name)
    images.update(c['Config']['Image'] for c in own)
    used_by_own = {c['Image'] for c in own}
    remove_images = []
    tags_by_id = {}
    for line in docker('image', 'ls', '-a', '--no-trunc', '--format', '{{.ID}} {{.Repository}}:{{.Tag}}').splitlines():
        image_id, tag = line.split(' ', 1)
        tags = tags_by_id.setdefault(image_id, set())
        if not tag.endswith(':<none>'):
            tags.add(tag)
    baseline = deployment_state.read(root)
    initial_images = set(baseline.get('initial_images', []))
    acquired = set(baseline.get('acquired_images', []))
    original_tags = dict(row.rsplit(' ', 1) for row in initial_images)
    restore_tags = []
    for image_id, tags in tags_by_id.items():
        eligible = not baseline or baseline.get('legacy') or image_id in used_by_own
        refs = {tag for tag in tags & images if eligible and f'{tag} {image_id}' not in initial_images}
        refs.update(tag for tag in tags if f'{tag} {image_id}' in acquired - initial_images)
        owned_id = image_id in used_by_own or any(row.endswith(' ' + image_id) for row in acquired)
        if not tags and owned_id and not any(row.endswith(' ' + image_id) for row in initial_images):
            refs.add(image_id)
        if image_id in used_images:
            kept.extend('Image used by another container: ' + ref for ref in refs)
        else:
            for ref in refs:
                original = original_tags.get(ref)
                if original and original != image_id:
                    if original in tags_by_id:
                        restore_tags.append((ref, original))
                    else:
                        kept.append('Original image unavailable; retaining current tag: ' + ref)
                        continue
                remove_images.append((ref, image_id))
    custom = (root / env['middleware'].get('MINIO_DATA_HOST_PATH', './data/minio')).resolve()
    if not custom.is_relative_to(root / 'data'):
        kept.append('Custom storage path: ' + str(custom))
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
                # Previous launchers emitted the same HTTPS proxy without the TLS challenge location.
                legacy = expected[:expected.index('    listen 443 ssl;')] + expected[expected.index('    listen 443 ssl;'):].replace(
                    expected[expected.index('    location ^~'):expected.index('    location /')], '', 1)
                if not site.is_symlink() and site.read_text() in (expected, legacy):
                    proxies.append(site)
                else:
                    kept.append('Modified Nginx site: ' + str(site))
    return dict(containers=containers, proxies=sorted(proxies), networks=sorted(networks), volumes=sorted(private_volumes),
                images=sorted(remove_images), restore_tags=sorted(restore_tags), paths=paths, kept=sorted(kept))


def host_action(root, action):
    if sys.platform.startswith('linux'):
        subprocess.run(['bash', str(support / 'host-state.sh'), action], check=True,
                       env=dict(os.environ, BASIL_DEPLOY_DIR=str(root)))


def finish_reset(root):
    state = deployment_state.read(root)
    if state:
        deployment_state.restore(root, state)
    (root / '.aos-selected.sh').unlink(missing_ok=True)
    cache = root / '.aos-install'
    if cache.is_dir():
        for p in cache.iterdir():
            if p.is_symlink():
                raise ValueError(f'Unexpected link in package cache: {p}')
            if p.is_dir() and re.fullmatch('[0-9a-f]{12}', p.name):
                for name in ('deploy.tar.gz', 'deploy.tar', 'SHA256SUMS'):
                    (p / name).unlink(missing_ok=True)
                if not any(p.iterdir()):
                    p.rmdir()
        for name in ('lock', 'pending.json', 'selected.json', 'baseline.json'):
            (cache / name).unlink(missing_ok=True)
        deployment_state.save(cache / 'cleanup-pending', 'local-restored')
    host_action(root, 'cleanup')
    if cache.is_dir():
        (cache / 'cleanup-pending').unlink(missing_ok=True)
        if not any(cache.iterdir()):
            cache.rmdir()
    print('Deployment removed. Run the launcher again to start a new installation.')


def reset(root):
    marker = root / '.aos-install/cleanup-pending'
    if marker.is_file():
        if input(f'Resume cleanup? Type DELETE {root}: ') == f'DELETE {root}':
            finish_reset(root)
        return
    local_docker()
    plan = inventory(root)
    print(f'Delete deployment in {root}. Local databases, uploads and secrets will be permanently removed.')
    for title, entries in [('Containers', [v for _, v in plan['containers']]), ('Image', [v for v, _ in plan['images']]),
                           ('Restore image tags', [v for v, _ in plan['restore_tags']]), ('Volumes', plan['volumes']), ('Networks', [v for _, v in plan['networks']]),
                           ('Managed Nginx sites', plan['proxies']), ('Local configuration and data', plan['paths']), ('Retained', plan['kept'])]:
        print(title + ': ' + (', '.join(map(str, entries)) or 'none'))
    host_action(root, 'preview')
    print('The launcher and externally managed resources will be retained.')
    if input(f'Type DELETE {root} to confirm: ') != f'DELETE {root}':
        print('Cancelled.')
        return
    if inventory(root) != plan:
        raise ValueError('Deployment resources changed. Review the inventory again.')
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
        print('Stopping ' + name, flush=True)
        docker('stop', cid)
    for cid, _ in plan['containers']:
        docker('rm', cid)
    for vol in plan['volumes']:
        docker('volume', 'rm', vol)
    for nid, _ in plan['networks']:
        docker('network', 'rm', nid)
    for ref, image_id in plan['images']:
        if docker('image', 'inspect', '--format', '{{.Id}}', ref) != image_id:
            raise ValueError(f'Image tag changed. Review the inventory again: {ref}')
        original = dict(plan['restore_tags']).get(ref)
        if original:
            docker('tag', original, ref)
        else:
            docker('image', 'rm', ref)
    # Recheck consumers before unlinking data; a concurrently created sandbox must be stopped first.
    remaining = inventory(root)
    if remaining['containers'] or remaining['paths'] != plan['paths']:
        raise ValueError('Data or containers changed. Review the inventory before continuing.')
    for path in plan['paths']:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    deployment_state.save(marker, True)
    finish_reset(root)


if __name__ == '__main__':
    try:
        reset(Path(os.environ['BASIL_DEPLOY_DIR']).resolve())
    except (OSError, ValueError, EOFError, subprocess.CalledProcessError) as error:
        sys.exit(f'Cleanup incomplete: {error}')
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/deploy-support.py" <<'AOS_EMBEDDED_FILE_END'
#!/usr/bin/env python3
"""Deployment operations. No third-party Python dependencies; never source .env as code."""
import argparse
import deployment_state
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
        raise ValueError('Command failed: ' + ' '.join(args[:3]) + '. Check configuration, Docker permissions and service status.') from None


def ask(label, default=''):
    value = input(f'{label}' + (f' [{default}]' if default else '') + ': ').strip() or default
    if not value:
        raise ValueError('Empty input. Cancelled.')
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
            raise ValueError(f'{path.name}:{n}: invalid or duplicate variable.')
        value = match[2]
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'{path.name}:{n}: unmatched quote.')
            value = value[1:-1]
        result[match[1]] = value
    return result


def atomic_write(path, text):
    if path.is_symlink():
        raise ValueError(f'Refusing to write to symlink: {path}')
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
        raise ValueError('Environment values cannot contain single quotes or newlines.')
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
                raise ValueError('Unsupported COMPOSE_FILE entry: ' + file)
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
            raise ValueError('Missing regular file: ' + name)
    prepare_envs()
    print('Deployment files and environment syntax are valid.')


def prepare_envs():
    for group in PORTS:
        p, template = env_path(group), SUPPORT / f'.env.{group}.example'
        if p.is_symlink() or (p.exists() and not p.is_file()):
            raise ValueError('Expected a regular environment file: ' + p.name)
        expected = read_env(template)
        if not p.exists():
            shutil.copyfile(template, p)
            p.chmod(0o600)
            print('Created ' + p.name)
        p.chmod(0o600)
        actual = read_env(p)
        missing = set(expected) - set(actual)
        if missing:
            print(p.name + ': adding missing template keys: ' + ', '.join(sorted(missing)))
            edit_env(p, {k: expected[k] for k in sorted(missing)})


def image_exists(image):
    return subprocess.run(['docker', 'image', 'inspect', image], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def pull_image(image, force=False, *, interactive=True):
    if not force and image_exists(image):
        print('Using local image: ' + image, flush=True)
        return
    while True:
        print('Pulling image (180s timeout): ' + image, flush=True)
        try:
            result = subprocess.run(['docker', 'pull', image], timeout=180)
            if result.returncode == 0:
                deployment_state.record_image(ROOT, image)
                return
        except subprocess.TimeoutExpired:
            print('Image download timed out.')
        if not interactive:
            raise ValueError(f'Could not obtain {image}. Prepare the image and retry.')
        print('1) Retry  2) Load offline image archive  3) Pull from a trusted registry  0) Back')
        choice = ask('Select', '0')
        if choice == '0':
            raise ValueError('Image unavailable. Service startup stopped.')
        if choice == '2':
            archive = Path(ask('Absolute path to image archive')).expanduser()
            if not archive.is_file():
                print('Archive not found.'); continue
            run(['docker', 'load', '-i', str(archive)])
            if image_exists(image):
                deployment_state.record_image(ROOT, image)
                return
            print('Archive does not contain the required tag: ' + image)
        elif choice == '3':
            alternate = ask('Trusted image reference with tag or digest')
            if alternate.startswith('-') or any(c.isspace() for c in alternate):
                raise ValueError('Invalid image name.')
            try:
                run(['docker', 'pull', alternate], timeout=180)
                run(['docker', 'tag', alternate, image])
                for ref in (alternate, image):
                    deployment_state.record_image(ROOT, ref)
                return
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                print('Failed to pull the alternate image.')


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
            wd = labels.get('com.docker.compose.project.working_dir', '').removeprefix('/host_mnt/')
            if wd and Path('/' + wd.lstrip('/')) not in (ROOT, ROOT / 'compose'):
                owner = (wd, owner[1])
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


def ensure_ports(group, selected, cfg, *, interactive=True, owners=None, reserved=None):
    owners = port_owners() if owners is None else owners
    reserved = {} if reserved is None else reserved
    changed = False
    for service in selected:
        spec = cfg['services'][service]
        for mapping in spec.get('ports', []):
            published = str(mapping['published'])
            old = int(published) if published.isdecimal() else 0
            key = next((k for k, target in PORTS.get(group, {}).get(service, []) if target is None or target == int(mapping['target'])), None)
            current = old
            while True:
                owner = (cfg['name'], service)
                active = owners.get(current, set())
                free = 1 <= current <= 65535 and (active == {owner} or (not active and port_available(current)))
                if 1 <= current <= 65535 and current not in reserved and free:
                    break
                if key is None:
                    raise ValueError(f'Port {current} for {service} is in use and has no configurable host port.')
                if not interactive:
                    raise ValueError(f'Port {current} for {service} is in use. Resolve the conflict and retry.')
                print(f'{group}/{service}: {key}={published if current == old else current} is invalid, reserved or in use.')
                val = ask('New port (1-65535, 0 to cancel)')
                if val == '0':
                    raise ValueError('Port change cancelled.')
                if not val.isdecimal() or not 1 <= int(val) <= 65535:
                    print('Invalid port.'); continue
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
                print(f'Saved {key}={current}.')
                changed = True
    return changed


def preflight():
    deployment_state.begin(ROOT)
    prepare_envs()
    owners = port_owners()
    reserved = {80: 'HTTP', 443: 'HTTPS'}
    external = {'postgresql': ('POSTGRESQL_HOST', 'db'), 'redis': ('REDIS_HOST', 'cache'),
                'rabbitmq': ('RABBITMQ_HOST', 'mq'), 'minio': ('MINIO_HOST', 'storage')}
    for group, services in PORTS.items():
        env = read_env(env_path(group))
        cfg = {'name': env['COMPOSE_PROJECT_NAME'], 'services': {}}
        for service, mappings in services.items():
            if group == 'middleware':
                host, fragment = external[service]
                if not env.get(host, '').startswith('CHANGE_ME') and f'compose/{fragment}.yaml' not in env['COMPOSE_FILE']:
                    continue
            cfg['services'][service] = {'ports': [
                {'published': env[key], 'target': target or 0} for key, target in mappings]}
        ensure_ports(group, cfg['services'], cfg, owners=owners, reserved=reserved)
    if sys.platform.startswith('linux'):
        for port in (80, 443):
            listeners = capture(['ss', '-H', '-ltnp', f'sport = :{port}'])
            if any('nginx' not in line for line in listeners.splitlines()):
                print(f'[WARN] TCP {port} is occupied. Move the existing listener before configuring public HTTPS.')
    print('Application ports checked.')


def select_services(cfg, requested, no_deps=False):
    selected = list(requested or cfg['services'])
    for name in selected:
        if name not in cfg['services']:
            raise ValueError('Unknown service: ' + name)
        if not no_deps:
            for dep in cfg['services'][name].get('depends_on', {}):
                if dep not in selected:
                    selected.append(dep)
    return selected


def up(group, services=(), recreate=False, no_deps=False, *, interactive=True):
    before = {g: env_path(g).read_text() for g in PORTS if env_path(g).exists()}
    cfg = config(group)
    selected = select_services(cfg, services, no_deps)
    for service in selected:
        if 'CHANGE_ME' in json.dumps(cfg['services'][service]):
            raise ValueError(f'Configure placeholders for {service} before deployment.')
    for image in dict.fromkeys(cfg['services'][s]['image'] for s in selected):
        pull_image(image, interactive=interactive)
    while True:
        cfg = config(group)
        ensure_ports(group, selected, cfg, interactive=interactive)
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
                        up(dependent, [dependent], recreate=True, no_deps=True, interactive=interactive)
            return
        if not re.search(r'port is already allocated|address already in use|ports are not available|failed to bind', result.stderr + result.stdout, re.I):
            raise ValueError('Service is not ready. Use View server health and check the Compose logs.')
        if not ensure_ports(group, selected, config(group), interactive=interactive):
            raise ValueError('Docker reported a port conflict. Check host listeners and Docker mappings.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('preflight')
    sub.add_parser('check-files')
    check = sub.add_parser('check-images'); check.add_argument('group', choices=PORTS)
    pull = sub.add_parser('pull'); pull.add_argument('image'); pull.add_argument('--force', action='store_true')
    start = sub.add_parser('up'); start.add_argument('group', choices=PORTS); start.add_argument('services', nargs='*')
    start.add_argument('--recreate', action='store_true'); start.add_argument('--no-deps', action='store_true')
    args = parser.parse_args()
    if args.action == 'preflight':
        preflight()
    elif args.action == 'check-files':
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
        print('[ERROR] ' + str(error), file=sys.stderr)
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
import time
import uuid

SUPPORT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("BASIL_DEPLOY_DIR", SUPPORT))
NGINX_DIR = Path('/etc/nginx/conf.d')
ACME_DIR = Path('/var/www/basil-acme')
RENEWAL_HOOK = Path('/etc/letsencrypt/renewal-hooks/deploy/basil-nginx.sh')
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
{challenge}{proxy}}}
'''


def reload_nginx():
    ops.run(['nginx', '-t'])
    ops.run(['systemctl', 'enable', '--now', 'nginx'])
    ops.run(['systemctl', 'reload', 'nginx'])


def wait_for_site(domain, health_path, expected_body=None, *, tls=True):
    scheme, port = ('https', 443) if tls else ('http', 80)
    print(f'Waiting up to 30 seconds for Nginx to serve {scheme.upper()} for {domain}.', flush=True)
    deadline = time.monotonic() + 30
    remaining = 30
    while remaining >= 0.01:
        result = subprocess.run(
            ['curl', '-q', '--noproxy', '*', '-fsS', '--max-time', f'{min(remaining, 20):.3f}',
             '--resolve', f'{domain}:{port}:127.0.0.1', f'{scheme}://{domain}{health_path}'],
            capture_output=True, text=True)
        if result.returncode == 0 and (expected_body is None or result.stdout == expected_body):
            return
        time.sleep(max(0, min(2, deadline - time.monotonic())))
        remaining = deadline - time.monotonic()
    detail = (result.stderr.strip() or ('Unexpected site response' if result.returncode == 0 else f'curl exit {result.returncode}')).splitlines()[0]
    raise ValueError(f'{scheme.upper()} for {domain} did not become ready within 30 seconds. Last error: {detail}')


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
            raise ValueError('Run sudo bash deploy.sh to update a managed proxy.')
        if not valid_domain(item['domain']) or not old.startswith('# Managed by Basil deploy.sh'):
            raise ValueError(f'Unexpected managed site configuration: {conf}')
        ops.atomic_write(conf, nginx_text(item['domain'], port, True))
        conf.chmod(0o644)
        try:
            reload_nginx()
        except subprocess.SubprocessError:
            ops.atomic_write(conf, old); reload_nginx(); raise
        item['port'] = port
    ops.atomic_write(state, json.dumps(settings, indent=2) + '\n')


def setup(target, domain, port):
    if not valid_domain(domain):
        raise ValueError(f'Enter a fully qualified domain without protocol, path or port, e.g. {target}.example.com.')
    if not 1 <= port <= 65535 or port in (80, 443):
        raise ValueError('Reserve ports 80 and 443 for Nginx. Choose a different application host port.')
    try:
        addresses = {x[4][0] for x in socket.getaddrinfo(domain, 80, type=socket.SOCK_STREAM)}
    except socket.gaierror as error:
        raise ValueError(f'Cannot resolve {domain}. Check its A/AAAA records.') from error
    if not addresses:
        raise ValueError(f'No A/AAAA records for {domain}.')
    print(f'{domain} resolves to {", ".join(sorted(addresses))}. Configuring HTTPS.', flush=True)
    # Existing non-nginx listeners must be handled before changing any site configuration.
    for number in (80, 443):
        listeners = ops.capture(['ss', '-H', '-ltnp', f'sport = :{number}']).strip()
        if listeners and any('nginx' not in line for line in listeners.splitlines()):
            raise ValueError(f'Another service occupies port {number}. Move its listener and retry.')
    if not shutil.which('nginx') or not shutil.which('certbot'):
        raise ValueError('Configure Nginx and Certbot during the startup environment check.')
    ops.run(['bash', str(SUPPORT / 'host-state.sh'), 'mark', 'nginx'])
    conf = NGINX_DIR / ('basil-' + target + '.conf')
    conf.parent.mkdir(parents=True, exist_ok=True)
    if conf.exists() and not conf.read_text().startswith('# Managed by Basil deploy.sh'):
        raise ValueError('Refusing to overwrite unmanaged configuration: ' + str(conf))
    nginx_all = subprocess.run(['nginx', '-T'], capture_output=True, text=True)
    current_file = ''
    for line in nginx_all.stdout.splitlines():
        if line.startswith('# configuration file '):
            current_file = line.removeprefix('# configuration file ').rstrip(':')
        if re.search(r'\bserver_name\s', line) and domain in line.replace(';', '').split() and current_file != str(conf):
            raise ValueError('Domain already configured in another Nginx site: ' + current_file)
    previous = conf.read_text() if conf.exists() else None
    if previous is not None:
        state = ROOT / '.domains.json'
        if not state.is_file() or target not in json.loads(state.read_text()):
            raise ValueError(f'This deployment has no ownership record for {conf}.')
    token = uuid.uuid4().hex
    challenge = ACME_DIR / '.well-known/acme-challenge' / token
    challenge.parent.mkdir(parents=True, exist_ok=True)
    challenge.write_text(token); challenge.chmod(0o644)
    try:
        ops.atomic_write(conf, nginx_text(domain, port, False)); conf.chmod(0o644)
        reload_nginx()
        challenge_path = f'/.well-known/acme-challenge/{token}'
        wait_for_site(domain, challenge_path, token, tls=False)
        try:
            ops.run(['bash', str(SUPPORT / 'host-state.sh'), 'cert', domain])
            ops.run(['certbot', 'certonly', '--webroot', '-w', str(ACME_DIR), '-d', domain,
                     '--cert-name', domain, '--register-unsafely-without-email', '--agree-tos',
                     '--non-interactive', '--keep-until-expiring'])
            ops.run(['bash', str(SUPPORT / 'host-state.sh'), 'cert-done'])
        except subprocess.CalledProcessError as error:
            raise ValueError(f'Certificate request failed for {domain}. See the Certbot error above. For HTTP-01 failures, '
                             'check that public DNS and TCP port 80 route the challenge path to this Nginx instance.') from error
        ops.atomic_write(conf, nginx_text(domain, port, True)); conf.chmod(0o644)
        reload_nginx()
        wait_for_site(domain, challenge_path, token)
    except BaseException:
        if previous is None:
            conf.unlink(missing_ok=True)
        else:
            ops.atomic_write(conf, previous); conf.chmod(0o644)
        reload_nginx()
        raise
    finally:
        challenge.unlink(missing_ok=True)
    hook = RENEWAL_HOOK
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text('#!/bin/sh\nset -eu\nnginx -t\nsystemctl reload nginx\n'); hook.chmod(0o755)
    ops.run(['bash', str(SUPPORT / 'host-state.sh'), 'file', str(hook)])
    ops.run(['systemctl', 'enable', '--now', 'certbot.timer'])
    state = ROOT / '.domains.json'
    settings = json.loads(state.read_text()) if state.exists() else {}
    settings[target] = {'domain': domain, 'port': port}
    ops.atomic_write(state, json.dumps(settings, indent=2) + '\n')


def apply_urls(target, domain):
    url = 'https://' + domain
    if target == 'workbench':
        ops.edit_env(ops.env_path('workbench'), dict(APP_URL=url, FRONTEND_URL=url,
                    FRONTEND_OAUTH_RESULT_URL=url, BASILCRAW_API_HOST=domain))
        groups = ['workbench']
    elif target == 'studio':
        ops.edit_env(ops.env_path('studio'), {'ASSETS_SEARCH_SNAPSHOT_URL': url + '/basilos/asset/search-embed',
                    'VIEW_SNAPSHOT_URL': url + '/basilos/studio/engine/multi-dim-table-embed'})
        groups = ['studio']
    else:
        ops.edit_env(ops.env_path('middleware'), {'MINIO_EXPOSE_URL': url})
        ops.edit_env(ops.env_path('workbench'), {'MINIO_PUBLIC_BASE_URL': url, 'MINIO_PRESIGN_ENDPOINT': domain,
                    'MINIO_PRESIGN_PORT': '443', 'MINIO_PRESIGN_USE_SSL': 'true'})
        groups = ['studio', 'workbench']
    def running(group, service):
        if not (ROOT / f'docker-compose.{group}.yaml').is_file():
            return False
        project = ops.read_env(ops.env_path(group))['COMPOSE_PROJECT_NAME']
        return bool(ops.capture(['docker', 'ps', '-q', '--filter', f'label=com.docker.compose.project={project}',
                                 '--filter', f'label=com.docker.compose.service={service}',
                                 '--filter', f'label=com.docker.compose.project.working_dir={ROOT}']).strip())

    for group in groups:
        if running(group, group):
            ops.up(group, [group], recreate=True, no_deps=True, interactive=False)
    for group, frontend in [('studio', 'studio-frontend'), ('workbench', 'workbench-frontend')]:
        if running(group, frontend):
            ops.run(ops.compose(group) + ['exec', '-T', frontend, 'nginx', '-s', 'reload'])


def main():
    if os.geteuid() != 0:
        raise ValueError('Domain setup requires root. Run sudo bash deploy.sh.')
    services = {'1': 'workbench', '2': 'studio', '3': 'storage'}
    while True:
        print('Set up domain and HTTPS\n  1) Workbench\n  2) Studio\n  3) Storage\n  0) Back')
        choice = ops.ask('Select', '0')
        if choice == '0':
            return
        if choice not in services:
            print('Select a number from 0 to 3.')
            continue
        target = services[choice]
        group, key = TARGETS[target]
        try:
            port = int(ops.read_env(ops.env_path(group))[key])
            domain = ops.ask(f'{target.capitalize()} domain name (e.g. {target}.example.com)').lower().rstrip('.')
            setup(target, domain, port)
            apply_urls(target, domain)
            print('Domain, certificate and application settings saved: https://' + domain)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            print('[ERROR] ' + str(error), file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, EOFError, KeyboardInterrupt, subprocess.SubprocessError) as error:
        print('[ERROR] ' + str(error), file=sys.stderr)
        sys.exit(1)
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/install-docker.sh" <<'AOS_EMBEDDED_FILE_END'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Run sudo bash deploy.sh to configure the server.' >&2; exit 1; }
[[ -f /etc/os-release ]] || { echo 'Install Docker Engine and its Compose plugin.'; exit 1; }
. /etc/os-release
[[ "$ID" == ubuntu || "$ID" == debian ]] || { echo 'Automatic setup supports Ubuntu and Debian. Install Docker and Compose manually on other systems.'; exit 1; }
journal="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/host-state.sh"
record() { bash "$journal" "$@"; }
record setup
if [[ "${1:-}" == start ]]; then record mark docker; systemctl start docker; exit; fi
apt-get update
basic=()
for entry in curl:curl python3:python3 ss:iproute2 nginx:nginx certbot:certbot; do
  command -v "${entry%:*}" >/dev/null || basic+=("${entry#*:}")
done
if (( ${#basic[@]} )); then
  if ! command -v nginx >/dev/null || ! command -v certbot >/dev/null; then record mark nginx; fi
  record packages "${basic[@]}"
fi
help="$(docker compose up --help 2>/dev/null)" || help=""
[[ "$help" != *--wait* ]] || exit 0
if command -v docker >/dev/null; then
  if apt-cache show docker-compose-plugin >/dev/null 2>&1; then record packages docker-compose-plugin; exit; fi
  if dpkg-query -W -f='${Status}' docker.io 2>/dev/null | grep -q 'install ok installed'; then
    record packages docker-compose-v2; exit
  fi
else
  record mark docker
fi
record packages ca-certificates gnupg
install -m 0755 -d /etc/apt/keyrings
key_file="$(mktemp)"
trap 'rm -f "$key_file"' EXIT
repo="https://download.docker.com/linux/$ID"
if ! curl -fSL --retry 2 --connect-timeout 10 --max-time 40 "$repo/gpg" -o "$key_file"; then
  repo="https://mirrors.aliyun.com/docker-ce/linux/$ID"
  echo 'Docker download failed. Trying the Alibaba Cloud Docker CE mirror.'
  curl -fSL --retry 2 --connect-timeout 10 --max-time 40 "$repo/gpg" -o "$key_file"
fi
# Pin Docker's signing key, including when obtained from the mirror.
gpg --show-keys --with-colons "$key_file" | grep -q '9DC858229FC7DD38854AE2D88D81803C0EBFCD88' || { echo 'Docker signing key fingerprint mismatch.'; exit 1; }
install -m 0644 "$key_file" /etc/apt/keyrings/basil-docker.asc
record file /etc/apt/keyrings/basil-docker.asc
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/basil-docker.asc] %s %s stable\n' "$(dpkg --print-architecture)" "$repo" "${UBUNTU_CODENAME:-$VERSION_CODENAME}" > /etc/apt/sources.list.d/basil-docker.list
record file /etc/apt/sources.list.d/basil-docker.list
apt-get update
if command -v docker >/dev/null; then
  record packages docker-compose-plugin
else
  record packages docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
record mark docker
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
    fail "Could not update ${key} in ${ENV_FILE}"
  fi

  chmod 600 "${temp_file}"
  mv "${temp_file}" "${ENV_FILE}"
  UPDATED_COUNT=$((UPDATED_COUNT + 1))
  info "Corrected ${key}: ${current_value:-<unset>} -> ${value}"
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
  # Docker Desktop presents the Engine socket as root:root inside Linux containers.
  # The macOS socket group does not determine the Linux container group.
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

  [[ -e "${ENV_FILE}" ]] || fail "Create ${ENV_FILE} from .env.workbench.example first"
  [[ -f "${ENV_FILE}" ]] || fail "Expected a regular file: ${ENV_FILE}"
  [[ ! -L "${ENV_FILE}" ]] || fail "Refusing to edit symlink: ${ENV_FILE}"
  command -v docker >/dev/null 2>&1 || fail 'Missing docker command'
  command -v stat >/dev/null 2>&1 || fail 'Missing stat command'

  docker_socket="$(resolve_docker_socket)" || \
    fail 'No accessible local Docker Engine socket'
  docker_gid="$(read_socket_gid "${docker_socket}")" || \
    fail "Cannot read the Docker socket GID: ${docker_socket}"
  [[ "${docker_gid}" =~ ^[0-9]+$ ]] || fail "Invalid Docker socket GID: ${docker_gid}"

  # Workbench manages storage as root; the sandbox runs as 1000:10001.
  write_env USER_STORAGE_OWNER_UID 0
  write_env USER_STORAGE_GID 10001
  write_env SANDBOX_WORKSPACE_OWNER_UID 0
  write_env SANDBOX_WORKSPACE_UID 1000
  write_env SANDBOX_WORKSPACE_GID 10001
  write_env RUNTIME_DOCKER_SOCKET_PATH "${docker_socket}"
  write_env RUNTIME_DOCKER_GID "${docker_gid}"

  if ((UPDATED_COUNT > 0)); then
    pass "Updated ${ENV_FILE}: ${UPDATED_COUNT} corrections"
  else
    pass "UID/GID and Docker socket settings are valid in ${ENV_FILE}"
  fi
  info 'Host filesystem and socket checks complete'
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

# Middleware images
POSTGRES_IMAGE=registry.cn-hangzhou.aliyuncs.com/tyrion-image/pgvector
POSTGRES_VERSION=pg16
REDIS_IMAGE=registry.cn-hangzhou.aliyuncs.com/tyrion-image/redis
REDIS_VERSION=7.2.4
RABBITMQ_IMAGE=registry.cn-hangzhou.aliyuncs.com/tyrion-image/rabbitmq
RABBITMQ_VERSION=3-management
MINIO_IMAGE=registry.cn-hangzhou.aliyuncs.com/tyrion-image/minio
MINIO_VERSION=2024.8.3

# Published host ports
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

# MinIO object storage
FILE_SERVICE_SELECTOR=minio
MINIO_EXPOSE_URL=https://CHANGE_ME_STORAGE_DOMAIN
MINIO_HOST=CHANGE_ME_MINIO_HOST
MINIO_PORT=9000
MINIO_USERNAME=CHANGE_ME_MINIO_USERNAME
MINIO_PASSWORD=CHANGE_ME_MINIO_PASSWORD
MINIO_DATA_HOST_PATH=./data/minio
MINIO_DATA_CONTAINER_PATH=/bitnami/minio/data

# Alibaba Cloud OSS
ALI_OSS_ACCESS_ID=
ALI_OSS_ACCESS_KEY=
ALI_OSS_ENDPOINT=

# Azure Blob storage
AZURE_BLOB_ACCOUNT_NAME=
AZURE_BLOB_ACCOUNT_KEY=
AZURE_BLOB_ENDPOINT=
AOS_EMBEDDED_FILE_END
cat > "$SUPPORT_DIR/.env.studio.example" <<'AOS_EMBEDDED_FILE_END'
# Compose
COMPOSE_PROJECT_NAME=basil-studio
COMPOSE_PATH_SEPARATOR=,
COMPOSE_FILE=docker-compose.studio.yaml

# Studio images tested together on 2026-11-16. Validate on the target server.
STUDIO_IMAGE=ghcr.io/basilos-ai/studio-backend
STUDIO_VERSION=v1.8.10
STUDIO_FRONTEND_IMAGE=ghcr.io/basilos-ai/studio-frontend
STUDIO_FRONTEND_VERSION=v1.8.12
NODE_SANDBOX_IMAGE=ghcr.io/basilos-ai/studio-node-sandbox
NODE_SANDBOX_VERSION=v1.0.0

# Studio published host ports
STUDIO_API_HOST_PORT=12001
STUDIO_FRONTEND_HOST_PORT=12000
NODE_SANDBOX_HOST_PORT=12002

# Studio runtime
JAVA_OPTS=-Xms1g -Xmx2g
SPRING_PROFILES_ACTIVE=docker
ENCRYPTOR_PASSWORD=CHANGE_ME_ENCRYPTOR_PASSWORD
# Private deployment requires false; deploy.sh enforces this setting.
ENABLE_HTTPS_COOKIES=false
FLOW_NODE_CALL_DEPTH=100
SANDBOX_READ_TIMEOUT_SECOND=600

# Studio frontend URLs returned by the API
ASSETS_SEARCH_SNAPSHOT_URL=https://CHANGE_ME_STUDIO_FRONTEND_DOMAIN/basilos/asset/search-embed
VIEW_SNAPSHOT_URL=https://CHANGE_ME_STUDIO_FRONTEND_DOMAIN/basilos/studio/engine/multi-dim-table-embed

# Studio database
POSTGRESQL_DATABASE=basilos

# Studio Redis database
REDIS_DATABASE=0

# Studio object storage
FILE_SERVICE_PRIVATE_BUCKET_NAME=studio-private
FILE_SERVICE_PUBLIC_BUCKET_NAME=studio-public
ALI_OSS_BUCKET_NAME=
AZURE_BLOB_CONTAINER=

# Vector database (PostgreSQL by default)
VECTOR_DATABASE_SELECTOR=postgresql
WEAVIATE_HOST=http://weaviate
WEAVIATE_PORT=8080
WEAVIATE_API_KEY=

# Optional OAuth2
PUB_KEY=
OAUTH2_DISCOVERY_URL=
OAUTH2_CLIENT_ID=
OAUTH2_CLIENT_SECRET=
OAUTH2_REDIRECT_URI=
OAUTH2_SCOPE=openid,profile,email
OAUTH2_HOME_URI=
OAUTH2_AUTHORIZED_URI=
OAUTH2_TOKEN_URI=

# Optional SAML
SAML_SP_ENTITY_ID=
SAML_IDP_SSO_URL=
SAML_ACS_URI=
SAML_HOME_URI=
SAML_PUBLIC_KEY=

# Optional content and data integrations
TEXT_IN_APP_ID=
TEXT_IN_SECRET_CODE=
MINERU_HOST=
DATA_QUERY_BASE_URL=
HANDLE_CONTENT_PARSE_CONCURRENCY=2
HANDLE_PRO_KNOWLEDGE_BASE_PARSE_QUEUE_CONCURRENCY=2

# Optional WeCom integration
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

# Deploy/restart reuse cached images; Update pulls explicitly.
WORKBENCH_IMAGE=ghcr.io/basilos-ai/workbench-backend
WORKBENCH_VERSION=v1.8.48
WORKBENCH_FRONTEND_IMAGE=ghcr.io/basilos-ai/workbench-frontend
WORKBENCH_FRONTEND_VERSION=v1.8.43
RUNTIME_IMAGE=ghcr.io/basilos-ai/workbench-runtime
RUNTIME_VERSION=v1.8.25
RUNTIME_SANDBOX_IMAGE=ghcr.io/basilos-ai/workbench-runtime-sandbox
RUNTIME_SANDBOX_VERSION=latest
RUNTIME_NGINX_IMAGE=nginx
RUNTIME_NGINX_VERSION=1.29-alpine
WORKBENCH_FRONTEND_PLATFORM=linux/amd64

SERVER_HOST=http://workbench:3000

# Public endpoints and published host ports
APP_URL=CHANGE_ME_WORKBENCH_API_URL
FRONTEND_URL=CHANGE_ME_WORKBENCH_FRONTEND_URL
FRONTEND_OAUTH_RESULT_URL=CHANGE_ME_WORKBENCH_FRONTEND_URL
WORKBENCH_HOST_PORT=11001
WORKBENCH_FRONTEND_HOST_PORT=11007
RUNTIME_GATEWAY_HOST_PORT=11002

# Workbench frontend gateway to Studio
BASILOS_GATEWAY_HOST=http://studio-frontend/
# Optional Library endpoint for task outputs
ASSETS_BASE_URL=
DESKTOP_DOWNLOAD_BASE_URL=https://tyrion-team.oss-cn-shanghai.aliyuncs.com/Workbench

# Workbench and Runtime databases
POSTGRESQL_DATABASE=basilos
RUNTIME_DB_DATABASE=basilos
DB_SCHEMA=workbench
RUNTIME_DB_SCHEMA=runtime
JWT_SECRET=CHANGE_ME_RANDOM_JWT_SECRET
ENCRYPTION_KEY=CHANGE_ME_RANDOM_ENCRYPTION_KEY
# Used for new or reset users. Migrations set the initial built-in admin password.
DEFAULT_USER_PASSWORD=CHANGE_ME_DEFAULT_USER_PASSWORD

# Runtime and Workbench resolve this URL to the shared /basilos vhost.
RABBITMQ_VIRTUAL_HOST=//basilos
REDIS_DATABASE=1
RUNTIME_HTTP_SERVICE_TOKEN=CHANGE_ME_RUNTIME_HTTP_SERVICE_TOKEN
RUNTIME_TO_WORKBENCH_SERVICE_TOKEN=CHANGE_ME_RUNTIME_TO_WORKBENCH_SERVICE_TOKEN
WORKBENCH_INTERNAL_BASE_URL=http://workbench:3000

# Conversation output and URL attachments
RUNTIME_MODEL_MAX_TOKENS=65536
INTEGRATION_ATTACHMENT_URL_MODE=public-https

# Storage and sandbox. deploy.sh verifies the UID/GID and Docker socket.
# The init container sets top-level directory ownership without recursive changes.
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

# Workbench object storage
MINIO_BUCKET=bascilclaw
MINIO_REGION=us-east-1
STORAGE_PRESIGNED_URL_EXPIRES_SECONDS=3600

# Optional registration email, alerts and APM
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
  printf '[OK] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*" >&2
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
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
      warn "Single quotes are not supported."
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
    warn "Enter a port from 1 to 65535."
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
    warn "Invalid Docker image tag."
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
    warn "Enter a URL starting with http:// or https://."
    value=""
  done
}

ensure_deployment_access_host() {
  local value=""

  [[ -n "$DEPLOYMENT_ACCESS_HOST" ]] && return
  while true; do
    prompt_required value "Server hostname or IP (bracket IPv6; omit protocol and port)"
    if [[ "$value" != *://* && "$value" != */* && "$value" != *[[:space:]]* &&
      ( "$value" != *:* || "$value" == \[*\] ) ]]; then
      DEPLOYMENT_ACCESS_HOST="$value"
      return
    fi
    warn "Enter a hostname or IP without a protocol, port or path. Enclose IPv6 in brackets."
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
    read -r -s -p "Confirm $label: " second
    printf '\n'
    if [[ -z "$first" ]]; then
      warn "Enter a nonempty password or key."
    elif [[ "$first" == *"'"* ]]; then
      warn "Passwords and keys cannot contain a single quote."
    elif [[ "$first" != "$second" ]]; then
      warn "The entries do not match. Try again."
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

  while true; do
    read -r -p "$label [y/n] (default: $default_answer): " answer || return 1
    answer="${answer:-$default_answer}"
    case "$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')" in
      y | yes) return 0 ;;
      n | no) return 1 ;;
      *) warn "Enter y or n." ;;
    esac
  done
}

choose_mode() {
  local service_name="$1"
  local choice=""

  while true; do
    printf '\n%s deployment mode\n' "$service_name"
    printf '  1) Local Docker Compose service\n'
    printf '  2) External service\n'
    read -r -p 'Select [1-2]: ' choice
    case "$choice" in
      1) SELECTED_MODE=local; return ;;
      2) SELECTED_MODE=external; return ;;
      *) warn "Enter 1 or 2." ;;
    esac
  done
}

choose_storage_provider() {
  local choice=""

  while true; do
    printf '\nExternal storage provider\n'
    printf '  1) MinIO\n'
    printf '  2) Alibaba Cloud OSS\n'
    printf '  3) Azure Blob\n'
    read -r -p 'Select [1-3]: ' choice
    case "$choice" in
      1) SELECTED_PROVIDER=minio; return ;;
      2) SELECTED_PROVIDER=aliyun-oss; return ;;
      3) SELECTED_PROVIDER=azure-blob; return ;;
      *) warn "Enter 1, 2 or 3." ;;
    esac
  done
}

dotenv_encode() {
  local value="$1"
  if [[ "$value" =~ ^[A-Za-z0-9_./,:@+-]*$ ]]; then
    printf '%s' "$value"
    return
  fi
  [[ "$value" != *"'"* ]] || die "Environment values cannot contain a single quote."
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
    # Set Linux ownership inside Docker Desktop.
    # Reuse the verified local PostgreSQL image and its platform.
    ownership_image="$(docker image inspect --format '{{.Id}}' \
      "$(dotenv_get POSTGRES_IMAGE):$(dotenv_get POSTGRES_VERSION)")"
    ownership_platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$ownership_image")"
    docker run --rm --pull never --platform "$ownership_platform" --user 0 --entrypoint chown \
      --volume "$path:/data" \
      "$ownership_image" -R 1001:1001 /data
  elif command -v sudo >/dev/null 2>&1; then
    sudo chown -R 1001:1001 "$path"
  else
    die "$path must be owned by 1001:1001. Correct its ownership as root and retry."
  fi
}

retry_configuration() {
  confirm "Check failed. Reconfigure this service?" y || die "Deployment stopped."
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

check_minio_public_url() {
  local saved_url candidate kind status
  saved_url="$(dotenv_get MINIO_EXPOSE_URL)"
  candidate="$saved_url"
  while true; do
    kind="$(python3 - "$candidate" <<'PYTHON'
import ipaddress
import sys
from urllib.parse import urlsplit

try:
    url = urlsplit(sys.argv[1])
    if (url.scheme not in ('http', 'https') or not url.hostname or url.username is not None
            or url.query or url.fragment or any(c.isspace() or c == "'" for c in sys.argv[1])
            or url.port == 0):
        raise ValueError()
    host = url.hostname.rstrip('.').lower()
    try:
        ip = ipaddress.ip_address(host)
        ip = getattr(ip, 'ipv4_mapped', None) or ip
        local = ip.is_loopback or ip.is_unspecified
    except ValueError:
        local = host == 'localhost' or host.endswith('.localhost')
    print('local' if local else 'probe')
except ValueError:
    print('invalid')
PYTHON
)" || die "Unable to check the public MinIO URL."
    case "$kind" in
      local) warn "The MinIO URL $candidate uses loopback. External AI models cannot use it to reach this server." ;;
      probe)
        status="$(curl --silent --output /dev/null --write-out '%{http_code}' --connect-timeout 10 --max-time 20 \
          -- "${candidate%/}/minio/health/ready")" || status=000
        if [[ "$status" == 2[0-9][0-9] ]]; then
          success "The MinIO public endpoint passed its health check from this server."
          break
        fi
        if [[ "$status" == 000 ]]; then
          warn "This server could not connect to ${candidate}. External AI models may be unable to read files."
        else
          warn "The MinIO endpoint returned HTTP ${status}. External model access is unverified."
        fi ;;
      invalid) warn "Enter a full HTTP or HTTPS URL, for example http://files.example.com:9000." ;;
    esac
    if [[ "$kind" != invalid ]]; then
      warn "AI Tagging may fail."
      if confirm "Use this URL and continue deployment?" n; then
        info "Confirmed. Continuing with the current MinIO URL."
        break
      fi
    fi
    IFS= read -r -p 'New MinIO public URL (Enter to return): ' candidate || die "Cancelled. Returning to the main menu."
    [[ -n "$candidate" ]] || die "Cancelled. Returning to the main menu."
    candidate="${candidate%/}"
  done
  if [[ "$candidate" != "$saved_url" ]]; then
    set_env MINIO_EXPOSE_URL "$candidate" || die "Could not save the MinIO URL."
  fi
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

  info "1/4 Configure PostgreSQL"
  while true; do
    choose_mode PostgreSQL
    if [[ "$SELECTED_MODE" == local ]]; then
      ensure_image_version dotenv_get set_env POSTGRES_VERSION PostgreSQL
      prompt_required username "Database username" basilos
      prompt_secret_confirm password "Database password"
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
        success "Local PostgreSQL is ready with the vector extension."
        return
      fi
    else
      prompt_required host "PostgreSQL host"
      prompt_port port "PostgreSQL port" 5432
      prompt_required database "Database name" basilos
      prompt_required username "Database username" basilos
      prompt_secret_confirm password "Database password"

      POSTGRES_MODE=external
      set_env POSTGRESQL_HOST "$host"
      set_env POSTGRESQL_PORT "$port"
      set_env POSTGRESQL_USERNAME "$username"
      set_env POSTGRESQL_PASSWORD "$password"
      set_env POSTGRESQL_BOOTSTRAP_DATABASE "$database"
      studio_set_env POSTGRESQL_DATABASE "$database"
      rebuild_compose_files

      if test_postgresql_external "$host" "$port" "$username" "$password" "$database"; then
        success "External PostgreSQL is reachable with the vector extension."
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

  info "2/4 Configure Redis"
  while true; do
    choose_mode Redis
    if [[ "$SELECTED_MODE" == local ]]; then
      ensure_image_version dotenv_get set_env REDIS_VERSION Redis
      prompt_secret_confirm password "Redis password"

      REDIS_MODE=local
      set_env REDIS_HOST redis
      set_env REDIS_PORT 6379
      set_env REDIS_PASSWORD "$password"
      studio_set_env REDIS_DATABASE 0
      set_env REDIS_SSL false
      rebuild_compose_files

      prepare_owned_directory "$DEPLOY_DIR/data/redis"
      if ops up middleware redis && test_redis_local "$password"; then
        success "Local Redis is ready."
        return
      fi
    else
      prompt_required host "Redis host"
      prompt_port port "Redis port" 6379
      prompt_secret_confirm password "Redis password"
      prompt_required database "Redis database number" 0
      if confirm "Use TLS for Redis?" n; then use_tls=true; else use_tls=false; fi

      REDIS_MODE=external
      set_env REDIS_HOST "$host"
      set_env REDIS_PORT "$port"
      set_env REDIS_PASSWORD "$password"
      studio_set_env REDIS_DATABASE "$database"
      set_env REDIS_SSL "$use_tls"
      rebuild_compose_files

      if test_redis_external "$host" "$port" "$password" "$use_tls"; then
        success "External Redis is reachable."
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

  info "3/4 Configure RabbitMQ"
  while true; do
    choose_mode RabbitMQ
    if [[ "$SELECTED_MODE" == local ]]; then
      ensure_image_version dotenv_get set_env RABBITMQ_VERSION RabbitMQ
      prompt_required username "RabbitMQ username" basilos
      prompt_secret_confirm password "RabbitMQ password"

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
        success "Local RabbitMQ is ready."
        return
      fi
    else
      prompt_required host "RabbitMQ host"
      prompt_port port "RabbitMQ port" 5672
      prompt_port management_port "RabbitMQ management port" 15672
      prompt_required username "RabbitMQ username" basilos
      prompt_secret_confirm password "RabbitMQ password"
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
        success "External RabbitMQ management API is reachable."
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
  prompt_required username "MinIO username" basilos
  prompt_secret_confirm password "MinIO password"
  expose_url="$(dotenv_get MINIO_EXPOSE_URL)"
  if [[ -z "$expose_url" || "$expose_url" == *CHANGE_ME* ]]; then
    ensure_deployment_access_host
    expose_port="$(dotenv_get MINIO_API_HOST_PORT)"
    prompt_url expose_url "MinIO URL accessible to the AI model" "$(deployment_access_url "$expose_port")"
  fi

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
    middleware_compose exec -T minio curl --fail --silent http://127.0.0.1:9000/minio/health/ready >/dev/null </dev/null &&
    check_minio_public_url
}

configure_external_minio() {
  local host=""
  local port=""
  local username=""
  local password=""
  local expose_url=""

  prompt_required host "MinIO hostname or IP"
  prompt_port port "MinIO API port" 9000
  prompt_required username "MinIO username"
  prompt_secret_confirm password "MinIO password"
  expose_url="$(dotenv_get MINIO_EXPOSE_URL)"
  [[ -n "$expose_url" && "$expose_url" != *CHANGE_ME* ]] || expose_url="http://$host:$port"
  prompt_url expose_url "MinIO URL accessible to the AI model" "$expose_url"

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

  check_minio_public_url
}

configure_aliyun_oss() {
  local access_id=""
  local access_key=""
  local endpoint=""
  local bucket=""

  prompt_required access_id "OSS AccessKey ID"
  prompt_secret_confirm access_key "OSS AccessKey Secret"
  prompt_url endpoint "OSS Endpoint"
  prompt_required bucket "OSS bucket name" studio

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

  prompt_required account_name "Azure Storage account name"
  prompt_secret_confirm account_key "Azure Storage account key"
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
  info "4/4 Configure object storage"
  while true; do
    choose_mode "Object storage"
    if [[ "$SELECTED_MODE" == local ]]; then
      if configure_local_minio; then
        success "Local MinIO is ready."
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

  if [[ "$(dotenv_get FILE_SERVICE_SELECTOR)" != minio ]]; then
    success "This server can reach the storage endpoint."
  fi
  warn "Check file access from the AI model network for AI Tagging."
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
    prompt_secret_confirm encryptor_password "Studio data encryption password"
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
    info "Studio frontend host port: ${studio_frontend_port}. Use the external URL for HTTPS or a reverse proxy."
    prompt_url studio_frontend_url "Studio frontend URL" "$(deployment_access_url "$studio_frontend_port")"
  fi
  studio_set_env ASSETS_SEARCH_SNAPSHOT_URL "${studio_frontend_url%/}$assets_path"
  studio_set_env VIEW_SNAPSHOT_URL "${studio_frontend_url%/}/basilos/studio/engine/multi-dim-table-embed"
}

deploy_studio() {
  local studio_frontend_url=""

  info "Deploy Studio"
  enforce_studio_cookie_mode
  ensure_studio_configuration
  mkdir -p "$DEPLOY_DIR/data/studio-logs"
  studio_compose config --quiet
  ops up studio
  studio_compose ps
  studio_frontend_url="$(studio_get_env ASSETS_SEARCH_SNAPSHOT_URL)"
  studio_frontend_url="${studio_frontend_url%/basilos/asset/search-embed}"
  success "Studio is running at $studio_frontend_url"
  info "Verify migrations, HTTP redirects, login and application workflows."
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
    warn "Invalid $label value: $configured_url"
    ensure_deployment_access_host
    default_url="$(deployment_access_url "$port")"
  fi

  if [[ -n "$default_url" ]]; then
    info "$label uses host port ${port}. Enter the external URL for HTTPS or a reverse proxy."
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
    info "Generated Workbench secret: $key"
  fi
}

prepare_workbench_env() {
  [[ -f "$WORKBENCH_COMPOSE_FILE" ]] || die "Missing docker-compose.workbench.yaml"
  [[ -f "$WORKBENCH_ENV_TEMPLATE" ]] || die "Missing .env.workbench.example"
  [[ -f "$WORKBENCH_CHECK_SCRIPT" ]] || die "Missing check-workbench.sh"
  [[ -f "$DEPLOY_DIR/workbench/storage/nginx/runtime-nginx.conf" ]] || die "Missing workbench/storage/nginx/runtime-nginx.conf"
  [[ -f "$DEPLOY_DIR/workbench/storage/templates/AGENTS.md" && -r "$DEPLOY_DIR/workbench/storage/templates/AGENTS.md" && ! -L "$DEPLOY_DIR/workbench/storage/templates/AGENTS.md" ]] || die "Expected a readable regular file at workbench/storage/templates/AGENTS.md."

  [[ ! -L "$WORKBENCH_ENV_FILE" ]] || die "Refusing to edit a symlink: $WORKBENCH_ENV_FILE"
  if [[ ! -f "$WORKBENCH_ENV_FILE" ]]; then
    cp "$WORKBENCH_ENV_TEMPLATE" "$WORKBENCH_ENV_FILE"
    info "Created $WORKBENCH_ENV_FILE"
  fi
  chmod 600 "$WORKBENCH_ENV_FILE"
}

sync_workbench_shared_configuration() {
  local studio_vhost=""
  local storage_url=""

  studio_vhost="$(dotenv_get RABBITMQ_VIRTUAL_HOST)"
  storage_url="$(dotenv_get MINIO_EXPOSE_URL)"
  parse_url "$storage_url" || die "Invalid HTTP(S) URL in MINIO_EXPOSE_URL: $storage_url"

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
  # The frontend gateway proxies Studio, independently of the Workbench API URL.
  gateway_url="$(workbench_get_env BASILOS_GATEWAY_HOST)"
  if workbench_value_needs_configuration "$gateway_url"; then
    gateway_url="http://studio-frontend/"
  fi
  parse_url "$gateway_url" || die "Invalid Studio gateway URL: $gateway_url"
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

  ensure_workbench_url APP_URL "Workbench API browser URL" "$frontend_port"
  api_url="$WORKBENCH_VALUE"
  parse_url "$api_url" || die "Invalid Workbench API URL: $api_url"
  workbench_set_env BASILCRAW_API_HOST "$URL_AUTHORITY"

  ensure_workbench_gateway

  ensure_workbench_url FRONTEND_URL "Workbench frontend URL" "$frontend_port"
  frontend_url="$WORKBENCH_VALUE"
  workbench_set_env FRONTEND_OAUTH_RESULT_URL "$frontend_url"

  ensure_workbench_generated_secret JWT_SECRET
  ensure_workbench_generated_secret ENCRYPTION_KEY
  ensure_workbench_generated_secret RUNTIME_HTTP_SERVICE_TOKEN
  ensure_workbench_generated_secret RUNTIME_TO_WORKBENCH_SERVICE_TOKEN

  admin_password="$(workbench_get_env DEFAULT_USER_PASSWORD)"
  if workbench_value_needs_configuration "$admin_password"; then
    prompt_secret_confirm admin_password "Default password for newly created or reset Workbench users"
    workbench_set_env DEFAULT_USER_PASSWORD "$admin_password"
  fi
  ensure_workbench_text RUNTIME_SANDBOX_HOST_ID "Stable sandbox host ID"
}

check_workbench_placeholders() {
  local keys=""

  keys="$(awk -F= '
    /^[[:space:]]*#/ || !index($0, "=") { next }
    index(substr($0, index($0, "=") + 1), "CHANGE_ME") { print $1 }
  ' "$WORKBENCH_ENV_FILE")"
  if [[ -n "$keys" ]]; then
    warn "Unconfigured Workbench variables: $(printf '%s\n' "$keys" | tr '\n' ' ')"
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

  info "Deploy Workbench"
  if ! workbench_storage_supported; then
    warn "Workbench requires MinIO object storage."
    return 1
  fi

  require_command od
  prepare_workbench_env
  configure_workbench
  ENV_FILE="$WORKBENCH_ENV_FILE" bash "$WORKBENCH_CHECK_SCRIPT"
  check_workbench_placeholders || return 1

  middleware_network="$(dotenv_get BASIL_NETWORK_NAME)"
  docker network inspect "$middleware_network" >/dev/null ||
    die "Missing Workbench Docker network: $middleware_network"
  workbench_compose config --quiet

  sandbox_image="$(workbench_get_env RUNTIME_SANDBOX_IMAGE):$(workbench_get_env RUNTIME_SANDBOX_VERSION)"
  if ! docker image inspect "$sandbox_image" >/dev/null 2>&1; then
    ops pull "$sandbox_image"
  fi
  ops up workbench
  if ! test_workbench_http; then
    workbench_compose ps
    die "Workbench HTTP health checks failed. Check container status and logs."
  fi
  workbench_compose ps
  success "Workbench passed its HTTP health checks."
  info "Workbench frontend URL: $(workbench_get_env FRONTEND_URL)"
  info "Workbench API URL: $(workbench_get_env APP_URL)"
}

deploy_all() {
  if ! workbench_storage_supported; then
    warn "Deploying Studio and Workbench together requires MinIO."
    return 1
  fi
  deploy_studio
  deploy_workbench
}

prepare_deployment() {
  prepare
  info "Configure middleware"
  initialize_postgresql
  initialize_redis
  initialize_rabbitmq
  initialize_storage
}

ensure_shared_network() {
  local network_name=""

  network_name="$(dotenv_get BASIL_NETWORK_NAME)"
  [[ -n "$network_name" ]] || die "BASIL_NETWORK_NAME is required."
  if ! docker network inspect "$network_name" >/dev/null 2>&1; then
    docker network create --label "ai.basilos.deploy.directory=$DEPLOY_DIR" "$network_name" >/dev/null
    info "Created shared network: $network_name"
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
    warn "This Compose project does not manage $label."
    return
  fi

  image="$("$getter" "$image_key")"
  current_version="$("$getter" "$version_key")"
  prompt_image_version new_version "$label Docker tag" "$current_version"
  printf '%s: %s:%s -> %s:%s\n' "$label" "$image" "$current_version" "$image" "$new_version"
  confirm "Update ${label}?" "$confirm_default" || return

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
    warn "Image pull failed for $label. The current configuration is intact."
    return 1
  fi

  safe_current_version="${current_version//[^A-Za-z0-9_.-]/_}"
  backup_file="${env_file}.bak.update-${service}-${safe_current_version}-$(date -u +%Y%m%dT%H%M%SZ)"
  [[ ! -e "$backup_file" ]] || die "Backup already exists: $backup_file"
  cp -a -- "$env_file" "$backup_file"
  info "Environment backup: $backup_file"

  "$setter" "$version_key" "$new_version"
  if "$compose_command" config --quiet &&
    compose_recreate "$compose_command" "$service"; then
    "$compose_command" ps "$service"
    success "Updated $label to ${new_version}."
    return
  fi

  cp -a -- "$backup_file" "$env_file"
  warn "Update failed for $label. Restoring ${current_version}."
  if "$compose_command" config --quiet &&
    compose_recreate "$compose_command" "$service"; then
    "$compose_command" ps "$service"
    warn "Restored $label to ${current_version}. Review database migrations and external changes separately."
  else
    warn "Restored the environment file. Automatic recovery of $label failed. Check its container and logs."
  fi
  return 1
}

update_runtime_sandbox_image() {
  local image="" current_version="" new_version="" backup_file=""
  local safe_current_version="" container_id="" configured_image=""

  container_id="$(workbench_compose ps -a -q workbench-runtime-node)" || return 1
  [[ -n "$container_id" ]] || { warn "Deploy Runtime before configuring the sandbox."; return 1; }
  # Shell variables take precedence over env files.
  [[ -z "${RUNTIME_SANDBOX_VERSION+x}" ]] || {
    warn "Unset RUNTIME_SANDBOX_VERSION before updating."
    return 1
  }
  image="$(workbench_get_env RUNTIME_SANDBOX_IMAGE)"
  current_version="$(workbench_get_env RUNTIME_SANDBOX_VERSION)"
  prompt_image_version new_version "Runtime Sandbox Docker tag" "$current_version"
  printf 'Runtime Sandbox: %s:%s -> %s:%s\n' "$image" "$current_version" "$image" "$new_version"
  confirm "Recreating Runtime may interrupt running tasks. Continue?" y || return

  if ! workbench_compose config --quiet || ! ops pull "$image:$new_version" --force; then
    warn "Configuration check or image pull failed. Runtime was not updated."
    return 1
  fi
  safe_current_version="${current_version//[^A-Za-z0-9_.-]/_}"
  backup_file="${WORKBENCH_ENV_FILE}.bak.update-runtime-sandbox-${safe_current_version}-$(date -u +%Y%m%dT%H%M%SZ)"
  [[ ! -e "$backup_file" ]] || die "Backup already exists: $backup_file"
  cp -a -- "$WORKBENCH_ENV_FILE" "$backup_file" || return 1
  workbench_set_env RUNTIME_SANDBOX_VERSION "$new_version" || return 1

  if workbench_compose config --quiet &&
    compose_recreate workbench_compose workbench-runtime-node; then
    container_id="$(workbench_compose ps -q workbench-runtime-node)" || return 1
    configured_image="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$container_id" |
      sed -n 's/^RUNTIME_SANDBOX_IMAGE=//p')" || return 1
    if [[ "$configured_image" == "$image:$new_version" ]]; then
      success "Runtime now uses ${image}:${new_version} for new sandboxes."
      return
    fi
  fi
  warn "Runtime update failed. Check the logs and the backup at ${backup_file} before reverting migrations."
  return 1
}

workbench_env_exists() {
  if [[ ! -f "$WORKBENCH_ENV_FILE" ]]; then
    warn "Deploy Workbench first to create .env.workbench."
    return 1
  fi
}

service_update_menu() {
  local choice=""

  while true; do
    printf '\nUpdate server version\n'
    printf '  1) Studio API\n'
    printf '  2) Studio Frontend\n'
    printf '  3) Studio Node Sandbox\n'
    printf '  4) Workbench API\n'
    printf '  5) Workbench Frontend\n'
    printf '  6) Workbench Runtime\n'
    printf '  7) Workbench Runtime Gateway\n'
    printf '  8) Runtime Sandbox image\n'
    printf '  9) PostgreSQL\n'
    printf ' 10) Redis\n'
    printf ' 11) RabbitMQ\n'
    printf ' 12) MinIO\n'
    printf '  0) Back\n'
    read -r -p 'Select [0-12]: ' choice
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
          warn "Workbench may run database migrations at startup. Reverting the image does not revert migrations."
          update_service_version "Workbench API" workbench_get_env workbench_set_env workbench_compose WORKBENCH_IMAGE WORKBENCH_VERSION workbench 300 y "$WORKBENCH_ENV_FILE"
        fi
        ;;
      5) if workbench_env_exists; then update_service_version "Workbench Frontend" workbench_get_env workbench_set_env workbench_compose WORKBENCH_FRONTEND_IMAGE WORKBENCH_FRONTEND_VERSION workbench-frontend 300 y "$WORKBENCH_ENV_FILE"; fi ;;
      6) if workbench_env_exists; then update_service_version "Workbench Runtime" workbench_get_env workbench_set_env workbench_compose RUNTIME_IMAGE RUNTIME_VERSION workbench-runtime-node 300 y "$WORKBENCH_ENV_FILE"; fi ;;
      7) if workbench_env_exists; then update_service_version "Workbench Runtime Gateway" workbench_get_env workbench_set_env workbench_compose RUNTIME_NGINX_IMAGE RUNTIME_NGINX_VERSION workbench-runtime 300 y "$WORKBENCH_ENV_FILE"; fi ;;
      8) if workbench_env_exists; then update_runtime_sandbox_image; fi ;;
      9)
        warn "Back up PostgreSQL and check version compatibility before updating."
        update_service_version PostgreSQL dotenv_get set_env middleware_compose POSTGRES_IMAGE POSTGRES_VERSION postgresql 240 n "$ENV_FILE"
        ;;
      10)
        warn "Back up Redis and check version compatibility before updating."
        update_service_version Redis dotenv_get set_env middleware_compose REDIS_IMAGE REDIS_VERSION redis 240 n "$ENV_FILE"
        ;;
      11)
        warn "Back up RabbitMQ and check version compatibility before updating."
        update_service_version RabbitMQ dotenv_get set_env middleware_compose RABBITMQ_IMAGE RABBITMQ_VERSION rabbitmq 240 n "$ENV_FILE"
        ;;
      12)
        warn "Back up MinIO and check version compatibility before updating."
        update_service_version MinIO dotenv_get set_env middleware_compose MINIO_IMAGE MINIO_VERSION minio 240 n "$ENV_FILE"
        ;;
      0) return ;;
      *) warn "Enter a number from 0 to 12." ;;
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
    "Project" "Service" "State" "Health" "Restarts" "Image"
  while read -r id; do
    [[ -n "$id" ]] || continue
    details="$(docker inspect --format \
      '{{index .Config.Labels "com.docker.compose.project"}}{{"\t"}}{{index .Config.Labels "com.docker.compose.service"}}{{"\t"}}{{.Config.Image}}{{"\t"}}{{.State.Status}}{{"\t"}}{{if .State.Health}}{{.State.Health.Status}}{{else}}unconfigured{{end}}{{"\t"}}{{.State.ExitCode}}{{"\t"}}{{.RestartCount}}' \
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
    warn "No AosWork Compose containers found."
  elif ((issues == 0)); then
    success "Checked $count containers. All healthy."
  else
    warn "Checked $count containers. See logs for the $issues unhealthy containers."
  fi
}

# Operations shared by first installation and subsequent maintenance.
compose_recreate() { ops up "${1%_compose}" "$2" --recreate --no-deps; }

ops() { python3 "$SUPPORT_DIR/deploy-support.py" "$@"; }

environment_check() {
  local missing=() cmd help
  if command -v python3 >/dev/null && ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
    warn "Python 3.9 or later is required."; return 1
  fi
  for cmd in python3 curl docker; do
    command -v "$cmd" >/dev/null || missing+=("$cmd")
  done
  if [[ "$(uname -s)" == Linux ]]; then
    for cmd in ss nginx certbot systemctl; do
      command -v "$cmd" >/dev/null || missing+=("$cmd")
    done
  fi
  help="$(docker compose up --help 2>/dev/null)" || help=""
  [[ "$help" == *--wait* ]] || missing+=("Docker Compose v2 with --wait")
  if (( ${#missing[@]} )); then
    printf 'Missing requirement: %s\n' "${missing[@]}"
    confirm 'Configure the server environment now?' n || return 1
    bash "$SUPPORT_DIR/install-docker.sh" || return 1
    help="$(docker compose up --help)" && [[ "$help" == *--wait* ]] || {
      warn 'A Docker Compose plugin supporting --wait is required.'; return 1;
    }
  fi
  if ! docker info >/dev/null 2>&1; then
    if [[ "$(uname -s)" == Linux && "$EUID" == 0 ]] && ! systemctl is-active --quiet docker &&
       confirm 'Start the Docker service?' n; then
      bash "$SUPPORT_DIR/install-docker.sh" start || return 1
    fi
    docker info >/dev/null 2>&1 || { warn 'Docker daemon unavailable. Check its service and socket permissions.'; return 1; }
  fi
  ops preflight || return 1
  success "Environment ready: $(uname -s)/$(uname -m)"
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
        middleware_compose exec -T minio curl --fail --silent http://127.0.0.1:9000/minio/health/ready >/dev/null </dev/null || return 1
      fi
      check_minio_public_url ;;
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
        die "$service has existing containers with incomplete configuration. Restore the original .env.middleware credentials."
      fi
      return 1
    fi
  done < <(printf '%s\n' "$keys" | tr ' ' '\n')
  while true; do
    info "Checking existing ${service} with its configured credentials"
    if existing_middleware_test "$service"; then
      success "Reusing $service."
      return 0
    fi
    printf '  1) Recover local service  2) Check again  3) Reconfigure  0) Back\n'
    read -r -p 'Select [0-3]: ' choice
    case "$choice" in
      1)
        if [[ "$mode" == local ]]; then
          ops up middleware "$service" || die "Recovery failed for $service. Existing configuration retained."
          if [[ "$service" == postgresql ]]; then middleware_compose run --rm postgresql-init || die 'Database initialization failed.'; fi
        else warn 'Recover this external service on its own host.'; fi ;;
      2) ;;
      3) confirm "Reconfigure ${service}? Existing database passwords will not be reset." n && return 1 ;;
      0) die 'Configuration retained. Stopping deployment.' ;;
    esac
  done
}

restart_services() {
  local group="$1" service="${2-}" frontend id
  if [[ -n "$service" ]]; then
    id="$("${group}_compose" ps -a -q "$service")"
    [[ -n "$id" ]] || die 'Deploy the service first.'
    ops up "$group" "$service" --recreate --no-deps
  else
    [[ -n "$("${group}_compose" ps -a -q)" ]] || die 'Deploy this project first.'
    ops up "$group" --recreate
  fi
  # Refresh static backend DNS after recreation.
  for group in studio workbench; do
    frontend="${group}-frontend"
    if [[ -n "$("${group}_compose" ps -q "$frontend" 2>/dev/null)" ]]; then
      "${group}_compose" exec -T "$frontend" nginx -s reload
    fi
  done
  success 'Services recreated with the current environment.'
}

service_restart_menu() {
  local choice group service
  printf '\nRestart server\n  1) All Studio services\n  2) All Workbench services\n  3) Studio API\n  4) Studio Frontend\n  5) Node Sandbox\n  6) Workbench API\n  7) Workbench Frontend\n  8) Runtime Node\n  9) Runtime Gateway\n  10) PostgreSQL\n  11) Redis\n  12) RabbitMQ\n  13) MinIO\n  0) Back\n'
  read -r -p 'Select [0-13]: ' choice
  case "$choice" in
    0) return ;; 1) restart_services studio ;; 2) restart_services workbench ;;
    3) restart_services studio studio ;; 4) restart_services studio studio-frontend ;;
    5) restart_services studio node-sandbox ;; 6) restart_services workbench workbench ;;
    7) restart_services workbench workbench-frontend ;; 8) restart_services workbench workbench-runtime-node ;;
    9) restart_services workbench workbench-runtime ;; 10) restart_services middleware postgresql ;;
    11) restart_services middleware redis ;; 12) restart_services middleware rabbitmq ;; 13) restart_services middleware minio ;;
    *) warn 'Invalid selection.' ;;
  esac
}

run_menu_action() {
  local status
  set +e
  ( set -Eeuo pipefail; "$@" )
  status=$?
  set -e
  [[ "$status" -eq 0 ]] || warn "Action failed (exit ${status}). Review the error above and retry."
}

install_selected() {
  prepare_deployment
  "$1"
}

maintenance_selected() {
  prepare_health_check
  "$@"
}

deploy_menu() {
  local choice
  printf '\nDeploy AosWork\n  1) Deploy Studio\n  2) Deploy Workbench\n  3) Deploy Studio and Workbench\n  0) Back\n'
  read -r -p 'Select [3]: ' choice || return 0
  case "${choice:-3}" in
    1) install_selected deploy_studio ;;
    2) install_selected deploy_workbench ;;
    3) install_selected deploy_all ;;
    0) return 0 ;;
    *) warn 'Invalid selection.' ;;
  esac
}

package_install() {
  local status=0
  python3 "$SUPPORT_DIR/release-install.py" "$1" || status=$?
  case "$status" in
    0) ops preflight ;;
    2) return 0 ;;
    *) return "$status" ;;
  esac
}

show_banner() {
  cat <<'BANNER'

    ___              _       __           __
   /   | ____  _____| |     / /___  _____/ /__
  / /| |/ __ \/ ___/| | /| / / __ \/ ___/ //_/
 / ___ / /_/ (__  ) | |/ |/ / /_/ / /  / ,<
/_/  |_\____/____/  |__/|__/\____/_/  /_/|_|

             AosWork Deploy V1.0.0

BANNER
}

deployment_menu() {
  local choice
  while true; do
    cat <<'MENU'

  1) Set up domain and HTTPS
  2) Select server packages
  3) Deploy AosWork
  4) Update server version
  5) Restart server
  6) View server health
  7) Delete deployment settings
  0) Exit
MENU
    read -r -p 'Select [0-7]: ' choice || return 0
    case "$choice" in
      1) run_menu_action bash "$SUPPORT_DIR/setup-domain-ssl.sh" ;;
      2) run_menu_action package_install choose ;;
      3) run_menu_action deploy_menu ;;
      4) run_menu_action maintenance_selected service_update_menu ;;
      5) run_menu_action maintenance_selected service_restart_menu ;;
      6) run_menu_action show_container_health ;;
      7) run_menu_action python3 "$SUPPORT_DIR/reset-deployment.py"
         [[ -f "$DEPLOY_DIR/.aos-install/baseline.json" && ! -f "$DEPLOY_DIR/.aos-install/cleanup-pending" ]] || return 0 ;;
      0) return 0 ;;
      *) warn 'Select a number from 0 to 7.' ;;
    esac
  done
}

prepare() {
  [[ -t 0 ]] || die "Run this action in an interactive terminal."
  [[ -f "$STUDIO_COMPOSE_FILE" ]] || die "Select a server package in menu 2 first."
  ops check-files
  require_command docker
  require_command curl
  docker compose version >/dev/null
  docker info >/dev/null 2>&1 || die "Check Docker daemon status and access permissions."
  [[ -f "$MIDDLEWARE_COMPOSE_FILE" ]] || die "Missing compose/middleware.yaml"
  [[ -f "$STUDIO_COMPOSE_FILE" ]] || die "Missing docker-compose.studio.yaml"
  [[ -f "$ENV_TEMPLATE" ]] || die "Missing .env.middleware.example"
  [[ -f "$STUDIO_ENV_TEMPLATE" ]] || die "Missing .env.studio.example"

  cd "$DEPLOY_DIR"
  [[ ! -L "$ENV_FILE" ]] || die "Refusing to edit symlink: $ENV_FILE"
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    info "Created $ENV_FILE"
  fi
  chmod 600 "$ENV_FILE"

  [[ ! -L "$STUDIO_ENV_FILE" ]] || die "Refusing to edit symlink: $STUDIO_ENV_FILE"
  if [[ ! -f "$STUDIO_ENV_FILE" ]]; then
    cp "$STUDIO_ENV_TEMPLATE" "$STUDIO_ENV_FILE"
    info "Created $STUDIO_ENV_FILE"
  fi
  chmod 600 "$STUDIO_ENV_FILE"

  restore_middleware_modes
  prepare_workbench_env
  ensure_shared_network
}

prepare_health_check() {
  require_command docker
  docker compose version >/dev/null
  docker info >/dev/null 2>&1 || die "Check Docker daemon status and access permissions."
  [[ -f "$MIDDLEWARE_COMPOSE_FILE" ]] || die "Missing compose/middleware.yaml"
  [[ -f "$STUDIO_COMPOSE_FILE" ]] || die "Missing docker-compose.studio.yaml"
  [[ -f "$ENV_FILE" ]] || die "Missing .env.middleware. Select a package first."
  [[ -f "$STUDIO_ENV_FILE" ]] || die "Missing .env.studio. Select a package first."
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
    prompt_url() { die "Previously configured gateway should not prompt"; }
    workbench_set_env BASILOS_GATEWAY_HOST https://studio.example.com
    ensure_workbench_gateway
    [[ "$(workbench_get_env BASILOS_GATEWAY_HOST)" == https://studio.example.com/ ]]
    workbench_set_env BASILOS_GATEWAY_HOST CHANGE_ME_GATEWAY_URL
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
  ! container_state_is_abnormal exited unconfigured 0
  container_state_is_abnormal exited unconfigured 1

  (
    ensure_image_version workbench_get_env workbench_set_env TEST_VERSION Test <<< 'v1.2.3'
    [[ "$(workbench_get_env TEST_VERSION)" == v1.2.3 ]]

    DEPLOYMENT_ACCESS_HOST=deploy.example.com
    prompt_url() {
      [[ "$3" == 'http://deploy.example.com:38080' ]]
      printf -v "$1" '%s' "$3"
    }
    ensure_workbench_url APP_URL 'Test API' 38080 >/dev/null 2>&1
    # Public frontend and internal API endpoints can use separate ports.
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
    # The initial ps runs in a subshell.
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
    prepare_health_check() {
      calls+="prepare "
    }
    run_menu_action() { "$@"; }
    environment_check() { :; }
    package_install() { :; }
    service_update_menu() {
      calls+="update"
    }

    main <<< '0' >/dev/null
    [[ -z "$calls" ]]
    deployment_menu <<< $'4\n0\n' >/dev/null
    [[ "$calls" == 'prepare update' ]]
  )

  unlink "$test_file"
  unlink "$studio_test_file"
  unlink "$workbench_test_file"
  ENV_FILE="$original_env_file"
  STUDIO_ENV_FILE="$original_studio_env_file"
  WORKBENCH_ENV_FILE="$original_workbench_env_file"
  success "deploy.sh self-test passed."
}

main() {
  case "${1-}" in
    --self-test)
      self_test
      return
      ;;
    --update)
      [[ $# -eq 1 ]] || die "Usage: ./deploy.sh [--self-test|--update|--health|--check]"
      environment_check
      prepare
      service_update_menu
      return
      ;;
    --check)
      environment_check
      return
      ;;
    --health)
      [[ $# -eq 1 ]] || die "Usage: ./deploy.sh [--self-test|--update|--health|--check]"
      prepare_health_check
      show_container_health
      return
      ;;
    '') ;;
    *) die "Usage: ./deploy.sh [--self-test|--update|--health|--check]" ;;
  esac

  show_banner
  if command -v flock >/dev/null; then
    exec 9<"$DEPLOY_DIR"
    flock -n 9 || die 'Another deployment session is open in this directory.'
  fi
  if [[ -f "$DEPLOY_DIR/.aos-install/cleanup-pending" ]]; then
    if command -v python3 >/dev/null; then
      python3 "$SUPPORT_DIR/reset-deployment.py"
    elif [[ "$(cat "$DEPLOY_DIR/.aos-install/cleanup-pending")" == '"local-restored"' ]]; then
      local answer
      read -r -p "Resume host cleanup? Type DELETE $DEPLOY_DIR: " answer || return 0
      if [[ "$answer" == "DELETE $DEPLOY_DIR" ]]; then
        bash "$SUPPORT_DIR/host-state.sh" cleanup
        rm -- "$DEPLOY_DIR/.aos-install/cleanup-pending"
        rmdir "$DEPLOY_DIR/.aos-install" 2>/dev/null || true
      fi
    else
      die 'Python 3 is required to finish restoring local deployment files.'
    fi
    return
  fi
  if ! environment_check; then
    warn 'Server setup incomplete.'
    if [[ -f "$DEPLOY_DIR/.aos-install/baseline.json" ]] && confirm 'Open deployment cleanup?' n; then
      python3 "$SUPPORT_DIR/reset-deployment.py"
    elif [[ "$(uname -s)" == Linux && "$EUID" == 0 ]]; then
      bash "$SUPPORT_DIR/host-state.sh" recover
    fi
    return 1
  fi
  if [[ -f "$DEPLOY_DIR/.aos-install/pending.json" ]]; then
    run_menu_action package_install resume
  fi
  deployment_menu
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
