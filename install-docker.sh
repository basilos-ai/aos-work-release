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
