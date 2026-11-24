# Studio 公网域名与生产 License 激活

首次安装时，在安装器的域名和 HTTPS 菜单中选择 Studio 并填写公网域名；一键安装则使用第三方入口 `install-aos.sh` 的第二个域名参数。域名需解析到本机，公网 TCP 80/443 可达。

安装器会自动：

- 为 Studio 配置 HTTPS，并把精确路径 `/typekey/api/v1/system/license/webhook` 转发至本机 Studio API 端口，保留 URI、请求体及转发协议头。
- 当 `LICENSE_HUB_API_URL` 缺失、为空或为 `CHANGE_ME` 占位符时，设置为 `https://license-hub.aos.work`。
- 当 `LICENSE_HUB_WEBHOOK_URL` 缺失、为空、为占位符，或等于旧 Studio 公网 URL 加上标准回调路径时，设置为 `https://<Studio域名>/typekey/api/v1/system/license/webhook`。
- 保留其他非空的自定义 Hub 地址和回调。原来手工填写的标准旧域名回调也会随域名迁移；无法从其值区分它和自动生成的回调。
- 域名更换时重建正在运行的 Studio 后端，随后核对容器内两个 License 环境变量；不只是重启容器。首次部署也会在启动后核对。

管理员不需要编辑 `.env.studio`。域名更换使用当前部署目录内已更新的 `deploy.sh`：菜单 1 → Studio → 新域名。不要把一键入口当作跨域名迁移命令，其原配置校验仍然有效。

## 两种安装器

仓库 `deploy.sh` 与 `install-aos.sh` 下载的预览版是不同的代码。此变更同时修复两条路径。
一键入口仍校验原始预览版 SHA-256，再下载固定提交、固定 SHA-256 的兼容修补脚本，只修改 Studio License 相关逻辑。配套部署包版本不变。修补后的启动脚本保留在部署目录，交互式域名更换也使用修复后的逻辑。
发布到旧 Release 的附件不会因仓库提交而自动更新；直接从旧 Release 下载的安装器不包含修复。

## 已执行的验证

- 两种安装器分别通过 7 项回归测试：首次配置、域名变更、后端重建、自定义配置保留、占位符迁移、HTTP 模式不伪造 HTTPS、后端失败/陈旧配置检测。
- 两种安装器分别通过 Docker 集成验证：使用实际仓库 Compose 渲染配置并注入测试后端容器；真实 Nginx 配合测试证书完成 TLS POST 转发；检查精确路径、查询参数、请求体和 `X-Forwarded-Proto`；变更域名后实际重建容器并核对环境；保留自定义回调。
- 仓库安装器原有 `--self-test` 和两种脚本的 Shell 语法检查通过。
- 一键入口的固定修补脚本下载摘要已核对。

集成测试后端是记录请求的测试替身，不是 Studio 生产后端。尚未验证真实 Studio 的生产 License Key 激活、License Hub 实际回调及授权状态；没有生产 Key，不把路由测试当作激活成功。测试未修改部署服务器。

## 生产验收

部署后在 Studio 登录并填写有效、适用于此实例的生产 License Key；确认界面授权状态和 License Hub 的实际回调结果。若失败，检查 Hub 连通性、证书链、License 适用范围及后端日志。不要将 License Key 或完整环境文件提交到仓库。
