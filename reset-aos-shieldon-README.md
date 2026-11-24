# AOS / ShieldON 主机环境清理

适用于 Ubuntu/Debian + APT + systemd，系统级 Docker 使用默认数据目录 `/var/lib/docker`。
**不是重装系统。会永久删除全部本机 Docker 工作负载，不仅限于 AOS 和 ShieldON；全部 Nginx 站点和 Certbot 证书也会删除。无自动备份、无数据恢复。**

## 下载并预览

```sh
curl -fL --retry 3 https://raw.githubusercontent.com/basilos-ai/aos-work-release/main/reset-aos-shieldon.sh -o /tmp/reset-aos-shieldon.sh
sudo sh /tmp/reset-aos-shieldon.sh
```

不带参数只盘点，不停止服务、不删除数据。请先检查输出中的容器、镜像、卷、网络、软件包及目录，并做好一致性备份。

## 确认后执行

用预览中显示的实际 hostname 替换下面占位符：

```sh
sudo sh /tmp/reset-aos-shieldon.sh --execute --confirm-host 实际主机名
```

执行时重新盘点并检查归属、软件包依赖和挂载边界。中断可能留下部分清理状态；脚本不保证回滚。如果 Docker 仍已安装但不可用，需人工恢复它以完成盘点，不能跳过检查。

完成后建议手动 `sudo reboot`，重新连接后再安装。

## 删除范围

- 停止并删除全部系统级 Docker 容器；删除 `/var/lib/docker`、`/var/lib/containerd`，包括镜像、普通本地卷、网络元数据和构建缓存。
- 卸载匹配到的 APT Docker/Compose/containerd/runc、Nginx 模块和 Certbot 包（包括配置残留）；不运行无范围的 autoremove。
- 删除 `/etc/docker`、`/etc/containerd`、`/etc/nginx` 和相关 Nginx 日志、缓存、状态目录。
- 删除 `/etc/letsencrypt`、`/var/lib/letsencrypt`、`/var/log/letsencrypt`，包括账号、全部证书私钥和续期钩子。
- 删除 `/var/www/shieldon-acme`。
- 删除已知部署位置：`/home/aos-work`、`/opt/aos-work`、`/home/shieldon`、`/opt/shieldon`、`/data/shieldon`。其中数据库、对象存储、上传文件、密码、密钥和安装日志一并删除。
- 删除 AOS 安装器主机状态记录 `/var/lib/aos-work-deploy`。
- 删除上述服务的 systemd drop-in 目录，以及一键安装器添加的 `basil-docker` / `shieldon-docker` APT 源和签名密钥文件。

## 停止条件与范围限制

遇到非默认 Docker 根目录、外部卷、未纳入清单的容器 bind mount、符号链接、未卸载的数据盘/子挂载、Snap 或 `/usr/local` 手工安装、APT 将连带删除范围外软件包时停止，需单独审阅。
不会自动卸载挂载点，不会把 `/home`、`/data`、`/opt` 整个删除，不会清除 SSH、用户、云安全组或外部数据库。
不清理 rootless Docker、其他用户的 Docker 客户端认证、自定义路径、系统审计日志或不在清单中的旧备份。需要完全恢复出厂环境时，应备份后重装系统盘。

## 验证范围

基于目标机器的只读容器及目录盘点编写。Dev Buddy 拒绝了软件包查询和 Docker inspect，因此未验证全部安装来源和挂载关系；脚本由操作者运行时会本地完成这些检查。
已做 Shell/Python 语法检查及删除路径、边界和包名匹配逻辑测试。未在目标机器或真实系统上执行破坏性清理。

