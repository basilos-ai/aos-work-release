---
id: RUNBOOK-BASILOS-COMPOSE-INSTALL
type: runbook
status: draft
owner: unassigned
updated: 2026-11-18
related:
  - RUNBOOK-BASILOS-SELF-HOSTED
  - RUNBOOK-BASILOS-OPERATIONS
---

# Docker Compose 部署

按下面顺序执行：**取得新版安装包 → 解压 → 启动脚本 → 选 1 安装 → 选 8 配置域名 → 选 5 检查状态**。已安装过的服务器在原目录运行同一脚本即可；检查通过的中间件会直接复用，不重复填写账号和密码。

本流程面向 Ubuntu 22.04/24.04、Debian 的 Linux amd64 主机，使用 root 或 sudo。准备服务器公网 IP、应用域名，以及 PostgreSQL、Redis、RabbitMQ、MinIO 的密码；已有中间件须保留原 `.env.middleware`。其他系统先安装 Docker Engine、Compose 插件、Python 3.9+ 和 curl。macOS 使用 Docker Desktop，不运行系统安装和证书配置；ARM 镜像兼容性见[验证记录](docs/%E6%9C%AC%E5%9C%B0%E9%83%A8%E7%BD%B2%E9%AA%8C%E8%AF%81-20261116.md)。

## 1. 取得安装包

从 [aos-work-release 的 Releases 页面](https://github.com/basilos-ai/aos-work-release/releases)选择明确的版本，下载同一 Release 的 `deploy.tar.gz` 和 `SHA256SUMS`。通用包不预填具体服务器地址，由安装脚本询问。发布方的打包方式见[部署文件说明](README.md)。

拿到交付包后，在自己电脑的下载目录执行，替换服务器地址和 SSH 用户：

```bash
scp deploy.tar.gz SHA256SUMS 用户名@服务器IP:/tmp/
ssh 用户名@服务器IP
```

也可以直接在服务器下载到 `/tmp`。把 `RELEASE_TAG` 替换为 Release 页面上选定的 tag，避免下载与校验期间版本变化：

```bash
cd /tmp
RELEASE_TAG='填写选定的发布 tag'
curl -fL --retry 3 --connect-timeout 10 -o deploy.tar.gz \
  "https://github.com/basilos-ai/aos-work-release/releases/download/${RELEASE_TAG}/deploy.tar.gz"
curl -fL --retry 3 --connect-timeout 10 -o SHA256SUMS \
  "https://github.com/basilos-ai/aos-work-release/releases/download/${RELEASE_TAG}/SHA256SUMS"
```

发布方须同时上传压缩包及校验文件。下载失败或校验文件缺失时先核对 Release 附件，不跳过校验。历史 OSS 包不作为当前安装入口。

## 2. 校验并解压（首次安装）

以下命令都在服务器执行：

```bash
cd /tmp
sha256sum --ignore-missing -c SHA256SUMS
sudo mkdir -p /data/basil
sudo tar -xzf deploy.tar.gz -C /data/basil
cd /data/basil
sha256sum -c FILES.sha256
test -f deploy-support.py && test -f domain-ssl.py
sudo bash deploy.sh
```

校验必须显示 `OK`。缺少 `deploy-support.py` 或 `domain-ssl.py` 说明是旧包，重新取得新版。不要向已有部署目录直接解压覆盖；已有环境先备份 `.env.*`、Compose、数据和定制用户模板，再按发布差异更新脚本/模板。

无需手工复制环境文件：脚本自动创建缺失的三份 `.env.*`，补齐缺失键，不覆盖已有值。端口和其他高级配置见[环境变量](docs/%E7%8E%AF%E5%A2%83%E5%8F%98%E9%87%8F.md)。

## 3. 选择菜单并安装

启动后看到：

```text
1) 配置并部署 Studio + Workbench
2) 配置并部署 Studio
3) 配置并部署 Workbench
4) 更新已部署服务的 Docker tag
5) 查看容器健康度
6) 停止服务
7) 重启服务（加载最新环境变量）
8) 配置域名与 HTTPS
9) 环境、部署文件与镜像检查
0) 退出
```

首次安装输入 **`1` 后回车**。只要 Studio 选 `2`，只要 Workbench 选 `3`。随后按顺序操作：

| 屏幕提示 | 全新同机部署如何选择 |
| --- | --- |
| 缺少 Docker / Compose / Python / curl，是否安装 | Ubuntu/Debian 输入 `y`；已安装则跳过 |
| PostgreSQL 部署方式 | 输入 `1`，用户名可回车使用默认值，输入并再次确认数据库密码 |
| Redis 部署方式 | 输入 `1`，输入并确认 Redis 密码 |
| RabbitMQ 部署方式 | 输入 `1`，输入用户名和密码 |
| 对象存储部署方式 | 输入 `1`，输入 MinIO 用户名和密码 |
| 部署服务器对外访问 IP | 输入服务器公网 IP，不带 `http://` 和端口 |
| MinIO 对外地址 | 暂时回车使用 IP 和端口；安装后菜单 `8` 配置 HTTPS 域名 |
| Studio 加密密码 | 输入并确认，保存好此值 |
| Studio 前端地址 | 回车使用默认 IP 和端口，已预填的地址会直接复用 |
| Workbench 地址 | 回车使用默认地址，或输入已有 HTTPS 入口 |
| Studio 平台网关 | 同机填写 `http://studio-frontend/`；已有正确值直接复用 |
| Workbench 新建/重置用户默认密码 | 输入并确认；不是内置 admin 的初始密码 |
| Sandbox Host 稳定标识 | 输入例如 `basil-server-01`，之后保持不变 |

外部中间件选择 `2`，按提示填写已有地址、端口和凭据。共享 PostgreSQL 须支持 vector 扩展；Studio、Workbench、Runtime 共库并按 schema 隔离。Workbench 当前使用 MinIO，整套部署不支持用 OSS/Azure 替换 Workbench 对象存储。

每项中间件都先检查原配置及连接：检查通过则跳过部署；未启动或连接异常时可选择用原配置恢复、重新检查、明确重配或返回。不会把连接失败直接当成必须重新设置密码。若已有数据的凭据丢失，应恢复原配置，不能靠重新输入密码修改数据库内的账号。

应用首次启动会执行数据库迁移。使用已有业务数据库前先备份；镜像回退不会撤销迁移。

Workbench 模板默认使用 GHCR `latest`；安装与重启复用本地已有镜像，菜单 `4` 才主动更新标签。正式交付可改为已验收的固定 tag，并记录镜像 digest 以便回退。

## 4. 遇到下载失败或端口占用

镜像已在本机时直接使用。下载失败或超时，菜单会提供：`1` 重试、`2` 导入离线镜像包、`3` 从你确认可信的镜像仓库获取、`0` 返回。私有仓库鉴权失败应先 `docker login 仓库域名`；脚本不自动更改 Docker daemon 的全局镜像源。

端口被其他进程或容器占用时，输入一个新的空闲端口，例如 `12010`。脚本会备份并更新对应 `.env.*`，同步引用该端口的 HTTP 地址，自动重试启动；不会停止占用端口的其他服务。已有自身容器占用的端口可以正常复用。通过本脚本配置的 Nginx 上游会同步更新，其他手工代理需自行调整。

模板统一使用 `宿主机端口:容器端口`，不再提供 BIND_HOST。Docker 会在宿主机所有接口发布这些端口，云安全组只放行需要的入口，数据库等端口限制来源。Studio 前端默认 `12000`，Workbench 前端默认 `11007`，80/443 留给宿主机 Nginx。

## 5. 配置域名和 HTTPS

安装完成返回主菜单，选择 **`8`**，然后选 `1` Studio、`2` Workbench 或 `3` MinIO。每个服务分别运行一次：

1. 输入完整域名，例如 `workbench.example.com`，不要包含协议、端口或路径。
2. 输入服务器公网 IP，以及用于证书通知的邮箱。
3. 按提示去 DNS 服务商添加 A 记录，指向公网 IPv4。有 AAAA 记录时必须正确指向本机 IPv6，否则删除错误记录；CDN 代理暂时关闭。
4. 在阿里云安全组放行 TCP 80 和 443；主机防火墙也允许这两个端口。
5. 回到终端确认继续。脚本检查 DNS、应用上游、端口与 HTTP 验证路径，再申请证书。

脚本不持有 DNS 平台凭据，因此不会自动创建 DNS 记录。NXDOMAIN 或错误解析会先报错，不反复调用证书申请。发现本部署容器占用 80/443 时会提示迁移应用端口；不接管其他程序或其他 Nginx 站点。

证书成功后自动配置 HTTPS、流式响应/WebSocket 代理与续期任务，更新对应应用 URL 并重新创建服务。Workbench 同步三个访问/回调 URL；MinIO 同步 Studio 外链和 Workbench 预签名地址。失败会恢复原 Nginx 站点配置，已签发的证书不删除。

## 6. 修改配置后重启

在部署目录执行 `sudo bash deploy.sh`，选 **`7`**，再选 Studio、Workbench 或具体容器。这个操作会重新创建容器以加载 `.env`，保留挂载数据并使用已有镜像。选 **`5`** 查看健康状态，选 **`6`** 停止服务，选 **`0`** 退出。

重复安装继续使用主菜单 `1/2/3`，健康的中间件会跳过。重新启动整套 Workbench 会中断正在执行的任务；仅修改访问 URL 时可选“Workbench API”。

## 7. 检查安装结果

```bash
cd /data/basil
sudo bash deploy.sh --health
```

确认长期服务 running、有健康检查的服务 healthy、初始化服务退出码 0。然后访问脚本显示的地址：Studio 的 `/basilos/asset/manage` 和 Workbench 的 `/chat`。Studio 当前镜像在非 80 端口根路径跳转可能丢端口，所以 HTTP 直连时使用上述业务路径；配置域名后再验证 HTTPS 入口。

进一步验收登录、上传/下载、对象文件、Sandbox 文件读写。真实模型对话与 AI 打标需要模型配置，未配置时标记待验收。日志与备份操作见[日常运维](docs/%E6%97%A5%E5%B8%B8%E8%BF%90%E7%BB%B4.md)。

### 首次管理员登录

Workbench Backend `v1.8.45` 的初始化迁移固定创建 `admin`，初始密码为 `Admin@12345`，并标记首次登录必须改密。`.env.workbench` 的 `DEFAULT_USER_PASSWORD` **不会覆盖该内置账号密码**，只用于后台新建/重置用户。首次启动后先从受控本地入口登录并修改管理员密码，再开放对外访问；其他镜像版本须以对应迁移和运行行为为准。

## 离线镜像准备

### 服务器下载较慢：从本机导入镜像

使用当前部署包的 `release.json` 作为镜像清单，不能只导出 Compose 的常驻服务：Runtime 动态启动的 Sandbox 镜像也必须包含在内。以下流程针对 Linux amd64 服务器，准备机需要 Python 3 和支持 `docker image save --platform` 的 Docker（本次实测 Engine 28.5.1）。Apple Silicon 准备机也必须下载并导出 `linux/amd64`，不要把本机 ARM 数据库替换镜像传到 x86 服务器。

在准备机解压后的部署包目录中，用 **Bash** 执行：

```bash
bash
set -euo pipefail
python3 - <<'PY' > images-linux-amd64.txt
import json
from pathlib import Path
release = json.loads(Path('release.json').read_text())
assert release['target_platform'] == 'linux/amd64'
print('\n'.join(dict.fromkeys(release['images'].values())))
PY

images=()
while IFS= read -r image; do
  docker pull --platform linux/amd64 "$image"
  images+=("$image")
done < images-linux-amd64.txt
docker image inspect --platform linux/amd64 \
  --format '{{.Id}} {{.Os}}/{{.Architecture}}' "${images[@]}" > images-linux-amd64.ids
docker image save --platform linux/amd64 "${images[@]}" | gzip -1 > basil-images-linux-amd64.tar.gz.partial
mv basil-images-linux-amd64.tar.gz.partial basil-images-linux-amd64.tar.gz
shasum -a 256 basil-images-linux-amd64.tar.gz images-linux-amd64.txt images-linux-amd64.ids > IMAGES.sha256
```

已有缓存时，先用 `docker image inspect --platform linux/amd64 <镜像:tag>` 核对架构与镜像 ID。服务器与本机 ID 一致的镜像可从导出列表中排除，减少上传量；仅 tag 相同不能证明内容相同。导出使用 `docker image save`，不能使用容器的 `docker export`。

把下面的用户和地址改为实际 SSH 连接信息。压缩包已压缩，传输时无需再加 `rsync -z`；连接中断后重新执行同一条 `rsync` 命令即可复用部分文件。

```bash
ssh deploy@192.0.2.10 'mkdir -p "$HOME/basil-offline-images"'
rsync --partial --progress \
  basil-images-linux-amd64.tar.gz images-linux-amd64.txt images-linux-amd64.ids IMAGES.sha256 \
  deploy@192.0.2.10:basil-offline-images/
```

在服务器用 Bash 执行：

```bash
bash
set -euo pipefail
cd "$HOME/basil-offline-images"
sha256sum -c IMAGES.sha256
docker image load -i basil-images-linux-amd64.tar.gz
images=()
while IFS= read -r image; do
  images+=("$image")
done < images-linux-amd64.txt
docker image inspect --format '{{.Id}} {{.Os}}/{{.Architecture}}' "${images[@]}" > images-server.ids
diff -u images-linux-amd64.ids images-server.ids
```

`docker load` 会自动解压 gzip 文件并恢复镜像标签，无需先用 `tar` 解开。确认镜像均存在、平台为 `linux/amd64`，并与准备机的镜像 ID 一致，再继续配置和部署。导入本身不会启动或重启容器。

安装和重启均优先使用本地镜像，不会为了核对已有 tag 再访问仓库。缺失镜像拉取失败或超过 180 秒时，按屏幕菜单选择重试、导入归档、指定可信备用镜像或返回。使用备用镜像前确认来源、平台与版本，脚本会映射为部署要求的原标签。软件包安装和申请证书仍需要网络；更新镜像 tag 的菜单仍会显式拉取版本。
