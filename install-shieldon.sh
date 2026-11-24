#!/bin/sh
# Ubuntu/Debian + systemd. Usage: sudo sh install-shieldon.sh shieldon.example.com
# Installs pinned ShieldON v0.6.2 with local middleware and Let's Encrypt HTTPS.
set -eu
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
download() { curl -fL --proto '=https' --proto-redir '=https' --retry 3 --connect-timeout 20 --max-time 600 "$1" -o "$2"; }

main() {
  [ "$#" -eq 1 ] || fail 'Usage: sudo sh install-shieldon.sh shieldon.example.com'
  domain=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
  [ "${#domain}" -le 253 ] || fail 'Domain is too long.'
  printf '%s\n' "$domain" | LC_ALL=C awk '
    /[^a-z0-9.-]/ || !/\./ || /^[0-9.]+$/ || /\.(local|localhost|test|invalid)$/ {exit 1}
    {n=split($0,a,"."); for(i=1;i<=n;i++) if(length(a[i])<1 || length(a[i])>63 || a[i]~/^-/ || a[i]~/-$/) exit 1}' || fail 'Provide a public domain without a URL scheme, path or port.'
  [ "$(id -u)" = 0 ] || fail 'Run as root or through sudo sh.'
  [ "$(uname -s)" = Linux ] && [ -d /run/systemd/system ] || fail 'Linux with systemd is required.'
  . /etc/os-release
  case "$ID" in ubuntu|debian) ;; *) fail 'Only Ubuntu and Debian are supported.' ;; esac
  case "$(uname -m)" in x86_64|aarch64) ;; *) fail 'Only x86_64 and ARM64 are supported.' ;; esac
  root=/opt/shieldon
  version=v0.6.2
  digest=355a39da4da1abb61babcff536bbe0728e0839c2abc9068d69949c4e0d33558e
  marker='# Managed by install-shieldon.sh: /opt/shieldon'
  site=/etc/nginx/conf.d/shieldon-oneclick.conf
  cert_name=shieldon-oneclick
  command -v flock >/dev/null || fail 'Install util-linux first.'
  exec 8>/run/shieldon-oneclick.lock
  flock -n 8 || fail 'Another ShieldON installation is running.'
  [ ! -L "$root" ] || fail 'Deployment directory must not be a symlink.'
  if [ -e "$root" ]; then
    [ -f "$root/.oneclick" ] && [ ! -L "$root/.oneclick" ] || fail 'Existing /opt/shieldon is not owned by this launcher.'
    [ "$(cat "$root/.oneclick")" = "$version $domain" ] || fail 'Use the same domain and version to resume.'
  fi
  timeout 15 getent ahosts "$domain" >/dev/null || fail 'Domain does not resolve. Set its public DNS records first.'
  [ "$(getconf _NPROCESSORS_ONLN)" -ge 4 ] || fail 'At least 4 CPUs are required.'
  awk '/MemTotal:/ {exit !($2>=7800000)}' /proc/meminfo || fail 'At least 8 GB RAM is required.'
  df -Pk /opt | awk 'NR==2 {exit !($2>=97656250 && $4>=5242880)}' || fail 'At least 100 GB total disk and 5 GiB free space are required.'

  printf '\n[1/5] Installing dependencies\n'
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl gnupg python3 nginx certbot iproute2
  if ! command -v docker >/dev/null 2>&1; then
    # Use Docker's signed official repository; never replace an existing engine.
    install -d -m 0755 /etc/apt/keyrings
    key=$(mktemp)
    download "https://download.docker.com/linux/$ID/gpg" "$key"
    gpg --show-keys --with-colons "$key" | grep -q '9DC858229FC7DD38854AE2D88D81803C0EBFCD88' || fail 'Docker signing-key fingerprint mismatch.'
    install -m 0644 "$key" /etc/apt/keyrings/shieldon-docker.asc
    rm -f "$key"
    printf 'deb [arch=%s signed-by=/etc/apt/keyrings/shieldon-docker.asc] https://download.docker.com/linux/%s %s stable\n' \
      "$(dpkg --print-architecture)" "$ID" "${UBUNTU_CODENAME:-$VERSION_CODENAME}" > /etc/apt/sources.list.d/shieldon-docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  fi
  if ! docker compose version >/dev/null 2>&1; then
    if apt-cache show docker-compose-plugin >/dev/null 2>&1; then
      apt-get install -y docker-compose-plugin
    elif apt-cache show docker-compose-v2 >/dev/null 2>&1; then
      apt-get install -y docker-compose-v2
    else
      fail 'Existing Docker requires Compose v2. Install its matching plugin and retry.'
    fi
  fi
  unset DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS_VERIFY DOCKER_CERT_PATH COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES COMPOSE_ENV_FILES
  export DOCKER_HOST=unix:///var/run/docker.sock
  systemctl enable --now docker
  docker info >/dev/null
  docker compose up --help | grep -q -- '--wait' || fail 'Upgrade Compose v2 to a version supporting --wait.'
  nginx -t
  # Reject any existing ShieldON stack at a different path.
  for owner in $(docker ps -a --filter label=com.docker.compose.project=shieldon --format '{{.Label "com.docker.compose.project.working_dir"}}'); do
    [ "$owner" = "$root" ] || fail "An existing ShieldON stack belongs to $owner."
  done
  if [ -e "$site" ] || [ -L "$site" ]; then
    [ ! -L "$site" ] && grep -Fxq "$marker" "$site" || fail "Existing unmanaged Nginx config: $site"
  fi
  # Catch duplicate virtual hosts before requesting a certificate.
  nginx -T > /run/shieldon-nginx-check.txt 2>&1
  python3 - "$domain" "$site" <<'PY'
import re, sys
from pathlib import Path
domain, own = sys.argv[1:]
source = ''
for line in Path('/run/shieldon-nginx-check.txt').read_text().splitlines():
    if line.startswith('# configuration file '):
        source = line[len('# configuration file '):].rstrip(':')
    clean = line.split('#', 1)[0]
    if source != own and re.search(r'\bserver_name\s+[^;]*\b' + re.escape(domain) + r'(?=\s|;)', clean):
        sys.exit('Domain already configured in Nginx: ' + source)
PY
  rm -f /run/shieldon-nginx-check.txt
  if [ ! -d "$root" ]; then
    install -d -m 0755 "$root"
    printf '%s %s\n' "$version" "$domain" > "$root/.oneclick"
  fi
  cd "$root"
  umask 077
  temp=$(mktemp -d "$root/.install.XXXXXXXX")
  trap 'rm -rf -- "$temp"' EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM

  printf '\n[2/5] Downloading and verifying ShieldON %s\n' "$version"
  if [ ! -f .bundle-ready ]; then
    [ ! -e .env ] && [ ! -e compose.yaml ] && [ ! -e runtime ] || fail 'Incomplete extraction or unmanaged files exist. Preserve them and inspect before retrying.'
    download "https://github.com/basilos-ai/shieldon-releases/releases/download/$version/shieldon.tar.gz" "$temp/shieldon.tar.gz"
    printf '%s  %s\n' "$digest" "$temp/shieldon.tar.gz" | sha256sum -c -
    mkdir "$temp/extract"
    python3 - "$temp" <<'PY'
import sys, tarfile
from pathlib import Path, PurePosixPath
root=Path(sys.argv[1])
with tarfile.open(root/'shieldon.tar.gz') as archive:
    for item in archive.getmembers():
        p=PurePosixPath(item.name)
        if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!='shieldon' or not (item.isfile() or item.isdir()):
            raise SystemExit('Unexpected archive entry: '+item.name)
    archive.extractall(root/'extract')
PY
    (cd "$temp/extract/shieldon" && sha256sum -c SHA256SUMS)
    cp -a "$temp/extract/shieldon/." "$root/"
    touch .bundle-ready
  fi
  # Keep generated passwords and keys on retries; modify only public entry settings.
  python3 - "$domain" <<'PY'
from pathlib import Path
import os, sys
p=Path('.env')
if p.is_symlink(): raise SystemExit('Refusing symlinked .env')
settings={'SHIELDON_PUBLIC_URL':'https://'+sys.argv[1], 'SHIELDON_COOKIE_SECURE':'true', 'PUBLIC_PORT':'127.0.0.1:13000'}
lines=p.read_text().splitlines()
for key,value in settings.items():
    lines=[line for line in lines if not line.startswith(key+'=')]
    lines.append(key+'='+value)
Path('.env.oneclick.tmp').write_text('\n'.join(lines)+'\n')
os.chmod('.env.oneclick.tmp',0o600)
os.replace('.env.oneclick.tmp',p)
PY
  # Prevent exported Compose variables from overriding the recorded configuration.
  for key in $(sed -n 's/^\([A-Z_][A-Z_0-9]*\)=.*/\1/p' .env); do unset "$key"; done

  printf '\n[3/5] Configuring HTTPS (DNS and inbound TCP 80/443 must be ready)\n'
  install -d -m 0755 /var/www/shieldon-acme/.well-known/acme-challenge
  # Keep an existing HTTPS endpoint during retry; create HTTP challenge site only on first run.
  if [ ! -f "$site" ]; then
    cat > "$site" <<NGINX
$marker
server {
    listen 80;
    server_name $domain;
    location /.well-known/acme-challenge/ { root /var/www/shieldon-acme; }
    location / { return 503; }
}
NGINX
    chmod 644 "$site"
  fi
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
  certbot certonly --non-interactive --agree-tos --register-unsafely-without-email \
    --webroot -w /var/www/shieldon-acme --cert-name "$cert_name" -d "$domain" --keep-until-expiring

  printf '\n[4/5] Deploying PostgreSQL, Redis, SeaweedFS and ShieldON\n'
  sh deploy.sh --with-middleware
  curl -fsS --retry 12 --retry-connrefused --retry-delay 5 --max-time 20 http://127.0.0.1:13000/health >/dev/null
  cat > "$temp/site.next" <<NGINX
$marker
server {
    listen 80;
    server_name $domain;
    location /.well-known/acme-challenge/ { root /var/www/shieldon-acme; }
    location / { return 301 https://\$host\$request_uri; }
}
server {
    listen 443 ssl;
    server_name $domain;
    ssl_certificate /etc/letsencrypt/live/$cert_name/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$cert_name/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 64m;
    location / {
        proxy_pass http://127.0.0.1:13000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
NGINX
  cp "$site" "$temp/site.challenge"
  install -m 0644 "$temp/site.next" "$site"
  if ! nginx -t; then
    install -m 0644 "$temp/site.challenge" "$site"
    fail 'New Nginx configuration failed validation; previous config restored.'
  fi
  systemctl reload nginx
  install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
  hook=/etc/letsencrypt/renewal-hooks/deploy/shieldon-oneclick.sh
  if [ -e "$hook" ] && ! grep -Fq "$marker" "$hook"; then fail "Unmanaged renewal hook exists: $hook"; fi
  printf '#!/bin/sh\n%s\nnginx -t && systemctl reload nginx\n' "$marker" > "$hook"
  chmod 755 "$hook"
  systemctl enable --now certbot.timer

  printf '\n[5/5] Verifying HTTPS and services\n'
  curl -fsS --resolve "$domain:443:127.0.0.1" --max-time 30 "https://$domain/health" >/dev/null
  docker compose --env-file .env -f compose.yaml ps -a
  docker compose --env-file .env -f compose.middleware.yaml ps
  printf '\nInstalled: https://%s\nDirectory: %s\n' "$domain" "$root"
  printf 'Create your administrator and Workspace in the browser. There is no default password.\n'
  printf 'Keep inbound access limited to your IP until first-admin setup is complete.\n'
}

main "$@"

