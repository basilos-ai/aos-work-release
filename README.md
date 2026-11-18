---
id: RUNBOOK-BASILOS-DEPLOYMENT-FILES
type: index
status: draft
owner: unassigned
updated: 2026-11-18
related:
  - RUNBOOK-BASILOS-SELF-HOSTED
---

# aos-work 部署文件

本目录保存 Docker Compose、环境变量模板和部署脚本。部署步骤统一见 [Docker Compose 部署](INSTALL.md)。

## 公网下载

部署文件与安装包统一通过 [basilos-ai/aos-work-release](https://github.com/basilos-ai/aos-work-release) 维护，下载入口为 [GitHub Releases](https://github.com/basilos-ai/aos-work-release/releases)。每次部署选择明确的 Release tag，并从同一 Release 下载：

- `deploy.tar` 或 `deploy.tar.gz`：同一份部署文件的两种归档格式，不包含 Docker 镜像。
- `SHA256SUMS`：两种归档的 SHA-256 校验文件。

发布仓库只同步本目录明确列出的部署文件与打包后改写链接的安装文档，不上传知识库其他内容。仓库内容变更不会自动更新 Release 附件；发布时必须从同一份待发布文件生成两种归档与校验文件。解压后执行 `sha256sum -c FILES.sha256` 和 `./deploy.sh --self-test`，确认包内文件、脚本 LF 换行和本次发布清单一致。

历史 OSS 下载包不作为当前安装入口。2026-11-16 实测其仍使用旧镜像仓库与路径，缺少当前要求的用户模板与 Runtime Nginx 配置；不能用历史包代替本次 Release 附件。

## 从当前仓库生成部署包

全新安装 Studio + Workbench 时，使用 [package.py](package.py) 生成 Linux amd64 包。打包机和服务器辅助检查均需要 Python 3.9+；Ubuntu/Debian 可由部署脚本安装。

在部署文件目录（发布仓库根目录）生成通用公开包，不预填具体服务器地址；安装时由交互脚本询问：

```bash
DEPLOY_OUTPUT="$(mktemp -d)"
python3 package.py "$DEPLOY_OUTPUT"
```

从本知识库调用时，将命令中的 `package.py` 换为 `02-研发/BasilOS 私有化部署/05-部署文件/package.py`。生成服务器专用包时追加 `--host 192.0.2.10`（示例 IP，替换为实际地址）；此类专用包不作为通用公开 Release 附件。

输出 `deploy.tar`、`deploy.tar.gz` 和使用相对文件名的 `SHA256SUMS`，可连同压缩包上传服务器校验。输出目录已有同名包时拒绝覆盖。

包内包含脚本、Compose、三份 `.env.*.example`、新用户模板、Nginx 配置，以及：

- `SERVER.md`：仅在指定 `--host` 时生成，记录该服务器的首次安装入口、预填地址和端口。
- `INSTALL.md` 与 `docs/`：来自本库的完整安装、配置、运维及验证说明，内部链接已转换为包内路径。
- `release.json`：目标平台、部署目录和应用/中间件镜像清单。
- `FILES.sha256`：解压文件的完整性校验。
- `package.py`、`tests/` 与 `.gitignore`：支持从独立发布仓库或解压目录重新打包、执行回归检查，并排除运行文件。

采用显式文件清单，排除运行 `.env.*`、SSH 凭据、备份、数据库和用户数据。目标服务器地址只写入生成包，不写入通用模板。`release.json` 的 `mutable_image_tags` 列出 `latest` 镜像；需要可重复交付时先把模板改为已验收固定 tag，并保存实际镜像 digest。包保留 Linux PostgreSQL 镜像及 `/data/basil`，不携带本机 ARM 替换配置。

指定 `--host` 打包时将 Studio 和 Workbench 的地址预填为服务器 HTTP 入口；Workbench `APP_URL` 与 `FRONTEND_URL` 共用前端端口，通过同源代理访问 API，平台网关使用同一 Docker 网络的 `http://studio-frontend/`。通用包保留地址占位符，由首次部署交互配置。所有服务使用宿主机端口映射，访问来源由云安全组控制；中间件密码、应用密钥和对象存储访问地址继续由首次部署交互配置。

在新目录解压，执行 `sha256sum -c FILES.sha256` 和 `bash deploy.sh --self-test` 后，按安装文档部署；专用包也可从 `SERVER.md` 开始。Workbench 模板沿用 GHCR `latest`，其他固定版本及历史验证组合见验证记录；打包不代表当前 `latest` 或目标服务器已通过验收。部署包 tag 仅标识脚本与模板批次，不等同于应用镜像版本。

## 目录结构

```text
/data/basil/
├── deploy.sh
├── deploy-support.py
├── domain-ssl.py
├── setup-domain-ssl.sh
├── install-docker.sh
├── docker-compose.middleware.yaml
├── .env.middleware
├── compose/
│   ├── db.yaml
│   ├── cache.yaml
│   ├── mq.yaml
│   └── storage.yaml
├── docker-compose.studio.yaml
├── .env.studio
├── docker-compose.workbench.yaml
├── .env.workbench
├── check-workbench.sh
└── workbench/
    └── storage/
        ├── templates/AGENTS.md
        └── nginx/runtime-nginx.conf
```

## 文件归属

| 分类 | Compose | 环境变量模板 |
| --- | --- | --- |
| 共享中间件 | `docker-compose.middleware.yaml`、`compose/*.yaml` | [`.env.middleware.example`](.env.middleware.example) |
| Studio | `docker-compose.studio.yaml` | [`.env.studio.example`](.env.studio.example) |
| Workbench | `docker-compose.workbench.yaml` | [`.env.workbench.example`](.env.workbench.example) |

中间件只部署一套，由 Studio 和 Workbench 共用。`deploy.sh` 负责交互式配置、中间件复用、单服务版本更新、重启/停止、域名 HTTPS 和环境检查；`deploy-support.py` 负责环境文件校验、镜像下载恢复与端口冲突处理；`domain-ssl.py` / `setup-domain-ssl.sh` 负责 DNS 检查、Nginx、证书及域名配置同步；`check-workbench.sh` 负责 Workbench 主机目录和 Docker Socket 检查。

首次配置时，脚本会为 `CHANGE_ME_VERSION` 逐项询问 Docker tag，并使用各 `*_HOST_PORT` 生成 Studio、Workbench 和本地 MinIO 的默认直连地址。

```bash
./deploy.sh --self-test  # 不连接 Docker，验证脚本关键更新流程
./deploy.sh --update  # 更新已部署服务的镜像版本
./deploy.sh --health  # 查看容器状态、健康度和重启次数
sudo bash deploy.sh --check  # 检查/补齐部署文件并检查基础环境
```

`--update` 会先以临时版本覆盖执行 Compose 配置检查和镜像拉取，拉取成功后才备份并修改对应 `.env.*`。随后仅重建目标服务，不联动重建依赖服务。更新失败时脚本会恢复环境文件并尝试按旧版本重建容器；数据库迁移和外部副作用不会随镜像回滚。

备份文件名格式为 `.env.*.bak.update-<service>-<old-version>-<UTC timestamp>`。备份包含密码和密钥，应与 `.env.*` 使用相同的访问控制，不得提交到 Git 或放入公开部署包。确认新版本稳定后再按内部保留策略清理。

同时更新 Workbench API 与 Frontend 时，先更新并验证 API，再更新 Frontend。前端代理配置属于镜像内容；仅重启旧 Frontend 镜像不会获得新的 Nginx 配置。

仓库内的 [`.gitattributes`](.gitattributes) 强制 Shell 脚本使用 LF 换行，避免在 Linux 上出现 `bad interpreter` 或 `$'\r'` 语法错误。

Studio 的 `ENABLE_HTTPS_COOKIES` 在私有化部署中固定为 `false`，不提供交互修改入口；即使现有 `.env.studio` 中保留其他值，`deploy.sh` 在部署 Studio 前也会强制改回 `false`。

## Workbench 初始化

`workbench-storage-init` 负责目录权限、新用户模板校验及 MinIO Bucket 就绪检查。API 镜像不会自动创建 Bucket，初始化服务使用同一应用镜像内的 MinIO SDK，在 Bucket 不存在时创建 `MINIO_BUCKET`（默认 `bascilclaw`），失败则阻止 Runtime/API 启动。外部对象存储应预先建桶或授予初始化账号建桶权限；已有 Bucket 不清空、不改公开读策略。

部署包不再包含内置 Library、多维表 App，不要求配置它们的 OAuth 变量。`workbench/storage/templates/AGENTS.md` 为新用户指令模板，直接挂载到容器 `/app/storage/templates/AGENTS.md`；初始化服务只校验文件并设置权限，不复制或覆盖内容。升级保留已有 Resource Hub 文件和数据库安装记录。`ASSETS_BASE_URL` 默认留空，仅按需启用任务输出保存到 Library。

## 共库与升级边界

新部署 Studio、Workbench、Runtime 均连接 `basilos` 数据库。Workbench 使用 `DB_SCHEMA=workbench`，Runtime 使用 `RUNTIME_DB_SCHEMA=runtime`。Studio 固定表沿用默认 schema（需按目标数据库 search_path 确认），动态表继续使用 `base{id}`，不要把 Studio 的全部数据归为一个 schema。

必须使用支持 DB_SCHEMA 的 Workbench/Runtime 镜像。旧环境须停写、备份，迁移业务对象及迁移记录并核对序列、类型、函数、扩展和所有权后才能切换；修改环境变量不会搬迁历史数据。备份须覆盖 Studio 的全部动态 schema。共库还需验证扩展对象在各应用 search_path 下可见。Workbench 迁移命令显式将业务 schema 放在首位、`public` 放在其后，解决 Studio 已在 public 安装 `pg_trgm` 时 Workbench 创建 `gin_trgm_ops` 索引失败的问题；迁移记录仍保存在 `DB_SCHEMA`，不移动扩展。现有环境文件不会自动改成共库配置。

Sandbox 镜像更新会重建 Runtime，等待健康并读取容器环境确认新镜像配置。它可能中断在途任务，不会重建已有 Sandbox，也不代表已实际创建新 Sandbox 验证。失败保留环境备份并报错，不自动回退可能已执行启动迁移的 Runtime。

### 存储路径迁移

Workbench 的宿主机存储统一为部署目录下的 `workbench/storage`，容器内仍为 `/app/storage`。Runtime 创建 Sandbox 使用的宿主机绝对路径也指向此目录。`WORKBENCH_DEPLOYMENT_ROOT` 必须是实际部署根目录，不能指向其 `workbench` 子目录。

已有部署切换前应停写并备份，将旧 `storage/` 的完整数据保留属主和权限迁移到 `workbench/storage/`，先处理目标目录中的同名文件，尤其不要用随包模板覆盖已有定制内容；原 `data/workbench/frontend-logs/` 同步迁移至 `workbench/frontend-logs/`。核对后再启动；仅修改挂载不会自动迁移历史数据。

Runtime Nginx 配置位于 `workbench/storage/nginx/runtime-nginx.conf`，作为只读文件挂载，缺失时拒绝自动创建目录。Runtime 镜像须包含 `/ready` 健康检查（当前源码 Dockerfile 已提供）。`PORT` 若修改，还须同步调整 `.env.workbench` 的 `WORKBENCH_INTERNAL_BASE_URL` 端口。

## 脚本验证与来源

开发环境执行 `bash deploy.sh --self-test` 和 `python3 tests/test_deployment.py`。回归测试包含通用包、服务器预填地址、归档校验及脱离知识库重新打包。设置 `BASIL_DOCKER_TEST=1` 会额外创建独立 Docker 项目，实测端口冲突恢复、重建加载环境变量，结束后清理测试容器；测试不操作正式项目。

Docker 安装和容器重建分别参考 [Docker Ubuntu 安装说明](https://docs.docker.com/engine/install/ubuntu/)与 [Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)；证书使用 [Let's Encrypt HTTP-01 验证](https://letsencrypt.org/docs/challenge-types/)，要求公网 80 端口可达。
