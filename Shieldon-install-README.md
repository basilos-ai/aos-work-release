# ShieldON 一键安装

依据：https://app.shieldon.ai/docs/guides/deployment/

## 运行

将 `install-shieldon.sh` 上传到服务器后执行：

```sh
sudo sh install-shieldon.sh shieldon.example.com
```

域名直接传参，无交互输入。替换为你自己的域名。

也可直接从本仓库下载运行：

```sh
curl -fsSL https://raw.githubusercontent.com/basilos-ai/aos-work-release/main/install-shieldon.sh | sudo sh -s -- shieldon.example.com
```

脚本位于本仓库根目录 `install-shieldon.sh`。

## 前提

- Ubuntu/Debian，systemd，x86_64 或 ARM64。
- 最少 4 核、8 GB RAM、100 GB 总磁盘；脚本额外要求至少 5 GiB 可用空间。实际运行、日志和备份需要更多可用空间。
- 能访问 GitHub、GHCR、Docker Hub、操作系统软件源和 Docker 官方软件源。
- 域名 A/AAAA 记录必须指向此服务器且可从公网访问 TCP 80、443。删除指向其他机器的陈旧 AAAA 记录。
- 不能有其他程序独占 80、443；允许复用现有 Nginx，但同一域名不能已有其他站点配置。
- 首次管理员创建前，请通过安全组等限制 443 仅供部署人员访问；TCP 80 需供 Let's Encrypt HTTP-01 校验访问。完成初始化后再放开业务访问。

## 自动执行内容

1. 检查系统、域名解析及硬件条件，安装依赖和缺失的 Docker/Compose。
2. 下载固定 `v0.6.2` 发布包，校验固定 SHA-256 和包内 `SHA256SUMS`。
3. 设置公开 HTTPS URL、安全 Cookie，将前端绑定到 `127.0.0.1:13000`。
4. 创建独立 Nginx 站点，通过 Certbot 申请 Let's Encrypt 证书。运行脚本即使用其 `--agree-tos` 参数；未提供联系邮箱。
5. 调用官方 `sh deploy.sh --with-middleware`，安装 PostgreSQL、Redis、SeaweedFS 和 ShieldON 服务。
6. 配置流式响应代理、证书自动续期，检查本机应用及带 TLS 的 HTTPS 健康端点。

## 文件位置

- 部署：`/opt/shieldon`
- 配置：`/opt/shieldon/.env`，权限 600
- 数据：`/opt/shieldon/runtime/data/`
- 密钥：`/opt/shieldon/runtime/secrets/`
- Nginx：`/etc/nginx/conf.d/shieldon-oneclick.conf`
- 证书：`/etc/letsencrypt/live/shieldon-oneclick/`
- 续期钩子：`/etc/letsencrypt/renewal-hooks/deploy/shieldon-oneclick.sh`

## 安装后

打开 `https://你的域名` 创建管理员和 Workspace；没有默认管理员密码。
随后按产品流程配置 Provider、模型、Gateway API key，并发布配置。
脚本不会自动创建管理员、配置模型或发布 Gateway Release。

## 失败和重试

保留目录、配置、密码和密钥，修复报错后重新运行同一条命令、使用同一域名。
不会主动清空 AOS 或其他 Docker 项目，也不自动删除冲突的 Nginx 站点。
网络失败、端口冲突、证书签发失败或官方安装器失败时停止，保留已有状态。
应用部署重试可能停止并重新创建当前 ShieldON 应用容器；不要当作无停机操作。
中间件版本与官方包一致，其中 PostgreSQL 和 Redis 使用 latest；生产升级需要另行备份与兼容性规划。
归属标记不匹配、未完成的文件解压或已有非本脚本管理的目录会被拒绝覆盖，需人工检查。

升级请遵循官方 `update.sh` 流程；本脚本只用于固定版本新装和同版本重试。

## 验证范围

已验证 Shell 语法、非法域名拒绝、发布包完整性及 Compose 回环端口解析。
未在真实 Linux 主机上执行系统软件安装、镜像启动或证书申请。

