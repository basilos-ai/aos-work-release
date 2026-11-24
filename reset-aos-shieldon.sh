#!/bin/sh
# Default is a read-only plan. No remote credentials are needed.
set -eu
main() {
  command -v python3 >/dev/null || { echo 'python3 is required.' >&2; exit 1; }
  python3 - "$@" <<'PY'
import argparse, json, os, re, shutil, socket, subprocess, sys
from pathlib import Path

APP_DIRS = ['/home/aos-work', '/opt/aos-work', '/home/shieldon', '/opt/shieldon', '/data/shieldon']
DIRS = APP_DIRS + [
    '/var/lib/docker', '/var/lib/containerd', '/var/lib/aos-work-deploy', '/etc/docker', '/etc/containerd',
    '/etc/nginx', '/var/log/nginx', '/var/cache/nginx', '/var/lib/nginx',
    '/etc/letsencrypt', '/var/lib/letsencrypt', '/var/log/letsencrypt',
    '/var/www/shieldon-acme',
    '/etc/systemd/system/docker.service.d', '/etc/systemd/system/docker.socket.d',
    '/etc/systemd/system/containerd.service.d', '/etc/systemd/system/nginx.service.d',
    '/etc/systemd/system/certbot.service.d', '/etc/systemd/system/certbot.timer.d',
]
FILES = [
    '/etc/apt/sources.list.d/basil-docker.list', '/etc/apt/keyrings/basil-docker.asc',
    '/etc/apt/sources.list.d/shieldon-docker.list', '/etc/apt/keyrings/shieldon-docker.asc',
]
UNITS = ['certbot.timer', 'certbot.service', 'nginx.service', 'docker.socket', 'docker.service', 'containerd.service']
PKG = re.compile(r'^(docker-ce(?:-cli|-rootless-extras)?|docker-buildx-plugin|docker-compose(?:-plugin|-v2)?|docker\.io|containerd(?:\.io)?|runc|nginx(?:-[a-z0-9-]+)?|libnginx-mod-[a-z0-9-]+|certbot|python3-certbot(?:-[a-z0-9-]+)?)$')

def run(args, check=True):
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(args) + '\n' + p.stderr[-3000:])
    return p

def inside(path, root):
    return path == root or path.startswith(root + '/')

def validate_path(value):
    if value not in DIRS + FILES:
        raise RuntimeError('Path is not on the deletion allowlist: ' + value)
    p = Path(value)
    if str(p.resolve()) != value or p.is_symlink():
        raise RuntimeError('Refusing symlinked or redirected deletion path: ' + value)

def mounts():
    # mountinfo encodes whitespace and backslashes with octal escapes.
    def decode(s): return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), s)
    return [decode(line.split()[4]) for line in Path('/proc/self/mountinfo').read_text().splitlines()]

def check_mounts(allow_docker=False):
    for target in DIRS:
        for mounted in mounts():
            if inside(mounted, target):
                if allow_docker and any(inside(mounted, base) and mounted != base for base in ['/var/lib/docker', '/var/lib/containerd']):
                    continue
                raise RuntimeError('Mounted path must be unmounted by the operator before cleanup: ' + mounted)

def packages():
    p=run(['dpkg-query','-W','-f=${binary:Package} ${db:Status-Status}\n'])
    return sorted(line.split()[0] for line in p.stdout.splitlines()
                  if len(line.split()) == 2 and line.split()[1] in ('installed','config-files')
                  and PKG.fullmatch(line.split()[0].split(':')[0]))

def purge_plan(names):
    if not names: return
    p=run(['apt-get','-s','purge',*names])
    affected=re.findall(r'^(?:Remv|Purg)\s+(\S+)',p.stdout,re.M)
    unexpected=[n for n in affected if n.split(':')[0] not in {s.split(':')[0] for s in names}]
    if unexpected:
        raise RuntimeError('APT would remove other packages; refusing: '+', '.join(unexpected))

def docker_inventory():
    result={'available':False,'containers':[],'images':[],'volumes':[],'networks':[]}
    if not shutil.which('docker'): return result
    p=run(['docker','info','--format','{{.DockerRootDir}}'],check=False)
    if p.returncode:
        raise RuntimeError('Docker is installed but unavailable. Start it manually to inventory bind mounts before deletion.')
    if p.stdout.strip()!='/var/lib/docker':
        raise RuntimeError('Non-default Docker data root requires a separately reviewed plan: '+p.stdout.strip())
    result['available']=True
    ids=run(['docker','ps','-aq']).stdout.split()
    if ids:
        # Only mount metadata is read. Environment variables and credentials are not displayed.
        p=run(['docker','inspect','--format','{{.Id}} {{.Name}} {{json .Mounts}}',*ids])
        for line in p.stdout.splitlines():
            cid,name,data=line.split(' ',2)
            for mount in json.loads(data):
                source=mount.get('Source','')
                if mount.get('Type')=='bind' and source!='/var/run/docker.sock' and not any(inside(source,d) for d in APP_DIRS):
                    raise RuntimeError('Unreviewed bind mount: '+name+' -> '+source+'. No deletion was performed.')
            result['containers'].append({'id':cid,'name':name})
    result['images']=run(['docker','image','ls','--format','{{.Repository}}:{{.Tag}} {{.ID}}']).stdout.splitlines()
    result['volumes']=run(['docker','volume','ls','--format','{{.Driver}} {{.Name}}']).stdout.splitlines()
    for entry in result['volumes']:
        driver,name=entry.split(' ',1)
        if driver!='local': raise RuntimeError('External volume driver requires manual review: '+entry)
        opts=run(['docker','volume','inspect','--format','{{json .Options}}',name]).stdout.strip()
        if opts not in ('null','{}',''): raise RuntimeError('Volume with external mount options requires review: '+name)
    result['networks']=run(['docker','network','ls','--format','{{.Driver}} {{.Name}}']).stdout.splitlines()
    if any(line.split()[0] not in ('bridge','host','null') for line in result['networks']):
        raise RuntimeError('Nonstandard Docker networks require manual review.')
    return result

def main():
    ap=argparse.ArgumentParser(description='Remove all system Docker data, Nginx, Certbot and the allowlisted AOS/ShieldON deployments. Default: preview only.')
    ap.add_argument('--execute',action='store_true')
    ap.add_argument('--confirm-host',default='',help='Must equal the hostname shown by the preview.')
    args=ap.parse_args()
    if os.geteuid()!=0: raise RuntimeError('Run with sudo for a complete inventory.')
    if args.execute and args.confirm_host!=socket.gethostname():
        raise RuntimeError('Explicit --confirm-host must match this machine: '+socket.gethostname())
    distro=Path('/etc/os-release').read_text()
    if not re.search(r'^ID="?(ubuntu|debian)"?$',distro,re.M): raise RuntimeError('Only Ubuntu/Debian are supported.')
    for cmd in ['systemctl','dpkg-query','apt-get','rm']:
        if not shutil.which(cmd): raise RuntimeError('Required command missing: '+cmd)
    # Ignore remote Docker contexts; this script operates only on the local host.
    for key in ['DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH']: os.environ.pop(key,None)
    os.environ['DOCKER_HOST']='unix:///var/run/docker.sock'
    for name in ['docker','nginx','certbot']:
        binary=shutil.which(name)
        if binary and (binary.startswith('/snap/') or binary.startswith('/usr/local/')):
            raise RuntimeError('Non-APT installation requires manual review: '+binary)
    if shutil.which('snap'):
        installed=run(['snap','list'],check=False)
        if installed.returncode==0 and re.search(r'^(docker|certbot|nginx)\s',installed.stdout,re.M):
            raise RuntimeError('Snap-managed components detected. This script only removes APT installations.')
    for path in DIRS+FILES: validate_path(path)
    check_mounts(allow_docker=True)
    names=packages()
    purge_plan(names)
    inv=docker_inventory()
    print(json.dumps({'hostname':socket.gethostname(),'mode':'EXECUTE' if args.execute else 'PREVIEW',
          'packages_to_purge':names,'docker':inv,'directories_to_delete':DIRS,'files_to_delete':FILES,
          'warning':'PERMANENT data loss. ALL local Docker workloads and all Nginx/Certbot sites are affected. No automatic backup.'},indent=2),flush=True)
    if not args.execute:
        print('\nPREVIEW ONLY. Nothing changed. Review this inventory before using --execute --confirm-host <hostname>.')
        return
    # Lock the deletion operation; concurrent manual changes are unsupported.
    import fcntl
    with open('/run/aos-shieldon-reset.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if packages()!=names or docker_inventory()!=inv:
            raise RuntimeError('Inventory changed. Run the preview again.')
        for row in inv['containers']:
            run(['docker','stop','--time','30',row['id']])
        for row in inv['containers']:
            run(['docker','rm',row['id']])
        for unit in UNITS:
            exists=run(['systemctl','show',unit,'--property=LoadState','--value'],check=False).stdout.strip()
            if exists and exists!='not-found':
                run(['systemctl','stop',unit])
                run(['systemctl','disable',unit])
        for unit in UNITS:
            if run(['systemctl','is-active','--quiet',unit],check=False).returncode==0:
                raise RuntimeError('Service is still active: '+unit)
        check_mounts()
        purge_plan(names)
        if names:
            os.environ['DEBIAN_FRONTEND']='noninteractive'
            run(['apt-get','-y','purge',*names])
        for path in DIRS+FILES:
            validate_path(path)
            # Recheck mount boundaries after package maintainer scripts.
            if any(inside(m,path) for m in mounts()): raise RuntimeError('Mount appeared: '+path)
            run(['rm','-rf','--one-file-system','--',path])
        run(['systemctl','daemon-reload'])
        leftovers=[p for p in DIRS+FILES if os.path.lexists(p)]
        if leftovers or packages(): raise RuntimeError('Cleanup incomplete; inspect remaining paths/packages: '+str(leftovers))
        print('\nCleanup complete. Reboot before reinstalling to clear any remaining runtime network state.')
        print('OS, SSH, user accounts, unrelated paths and external databases were not reset.')

try:
    main()
except (RuntimeError,OSError,ValueError) as exc:
    print('STOPPED: '+str(exc),file=sys.stderr)
    print('If execution had started, cleanup may be partial. Do not assume rollback.',file=sys.stderr)
    sys.exit(1)
PY
}
main "$@"

