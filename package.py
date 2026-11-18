#!/usr/bin/env python3
"""Build an uploadable new-install bundle from an explicit, credential-free file list."""

import argparse
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import tarfile
from urllib.parse import quote, unquote


SOURCE = Path(__file__).resolve().parent
FILES = (
    "deploy.sh", "check-workbench.sh", ".gitattributes", ".gitignore",
    "package.py", "tests/test_deployment.py",
    "deploy-support.py", "domain-ssl.py", "setup-domain-ssl.sh", "install-docker.sh",
    "docker-compose.middleware.yaml", "docker-compose.studio.yaml",
    "docker-compose.workbench.yaml", ".env.middleware.example",
    ".env.studio.example", ".env.workbench.example",
    "compose/db.yaml", "compose/cache.yaml", "compose/mq.yaml", "compose/storage.yaml",
    "workbench/storage/templates/AGENTS.md", "workbench/storage/nginx/runtime-nginx.conf",
)
DOCS = {
    SOURCE / "README.md": "README.md",
    SOURCE.parent / "01-快速开始/Docker Compose 部署.md": "INSTALL.md",
    SOURCE.parent / "02-配置/环境变量.md": "docs/环境变量.md",
    SOURCE.parent / "03-维护/日常运维.md": "docs/日常运维.md",
    SOURCE.parent / "04-参考/参考信息.md": "docs/参考信息.md",
    SOURCE.parent / "04-参考/本地部署验证-20261116.md": "docs/本地部署验证-20261116.md",
}
if (SOURCE / "INSTALL.md").is_file():
    # The release repository keeps the rewritten documentation beside the scripts.
    DOCS = {SOURCE / name: name for name in DOCS.values()}


def server_host(value):
    value = value.strip()
    try:
        address = ipaddress.ip_address(value.strip("[]"))
        return f"[{address}]" if address.version == 6 else str(address)
    except ValueError:
        if len(value) <= 253 and all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in value.split(".")
        ):
            return value
    raise argparse.ArgumentTypeError("host 必须为 IP 或域名，不包含协议、端口和路径")


def read_file(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"缺少普通文件或不允许符号链接：{path}")
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def env_values(content):
    return dict(line.split("=", 1) for line in content.splitlines()
                if "=" in line and not line.lstrip().startswith("#"))


def set_env(content, key, value):
    pattern = rf"^{re.escape(key)}=.*$"
    if not re.search(pattern, content, re.MULTILINE):
        raise ValueError(f"模板缺少变量：{key}")
    return re.sub(pattern, lambda _: f"{key}={value}", content, flags=re.MULTILINE)


def build_contents(host=None):
    contents = {name: read_file(SOURCE / name) for name in FILES}
    mapping = {(SOURCE / name).resolve(): name for name in FILES}
    mapping.update({path.resolve(): name for path, name in DOCS.items()})
    for path, name in DOCS.items():
        def rewrite(match):
            target = match[1]
            if "://" in target or target.startswith("#"):
                return match[0]
            target_path, separator, fragment = target.partition("#")
            resolved = (path.parent / unquote(target_path)).resolve()
            if resolved not in mapping:
                raise ValueError(f"未打包的文档链接：{path.name} -> {target}")
            relative = os.path.relpath(mapping[resolved], Path(name).parent).replace(os.sep, "/")
            return "](" + quote(relative, safe="/.-_") + separator + fragment + ")"
        contents[name] = re.sub(r"\]\(([^)]+)\)", rewrite, read_file(path))

    configs = {kind: env_values(contents[f".env.{kind}.example"])
               for kind in ("middleware", "studio", "workbench")}
    studio_url = f"http://{host}:{configs['studio']['STUDIO_FRONTEND_HOST_PORT']}"
    workbench_url = f"http://{host}:{configs['workbench']['WORKBENCH_FRONTEND_HOST_PORT']}"
    overrides = {
        "studio": {
            "ASSETS_SEARCH_SNAPSHOT_URL": studio_url + "/basilos/asset/search-embed",
            "VIEW_SNAPSHOT_URL": studio_url + "/basilos/studio/engine/multi-dim-table-embed",
        },
        "workbench": {
            "APP_URL": workbench_url,
            "FRONTEND_URL": workbench_url,
            "FRONTEND_OAUTH_RESULT_URL": workbench_url,
            "BASILOS_GATEWAY_HOST": "http://studio-frontend/",
        },
    }
    for kind, values in (overrides.items() if host else ()):
        name = f".env.{kind}.example"
        for key, value in values.items():
            contents[name] = set_env(contents[name], key, value)

    images = {}
    for config in configs.values():
        for key, value in config.items():
            if key.endswith("_IMAGE"):
                version = config[key.removesuffix("_IMAGE") + "_VERSION"]
                if not version or "CHANGE_ME" in version:
                    raise ValueError(f"打包前必须填写镜像标签：{key}")
                images[key] = f"{value}:{version}"
    contents["release.json"] = json.dumps({
        "deployment": "new-studio-and-workbench",
        "target_platform": "linux/amd64",
        "target_host": host,
        "deployment_root": "/data/basil",
        "images": images,
        "mutable_image_tags": [image for image in images.values() if image.endswith(":latest")],
        "validation": "Local tests only; target Linux host acceptance is still required.",
    }, ensure_ascii=False, indent=2) + "\n"
    contents["SERVER.md"] = f"""# 服务器首次部署

本包用于全新安装 Studio + Workbench，目标地址 `{host}`，目标平台 `linux/amd64`，部署目录 `/data/basil`。
目标服务器架构、资源和端口仍需现场确认；本包不包含 Docker 镜像，服务器需要访问镜像仓库。
完整流程见 [INSTALL.md](INSTALL.md)，镜像清单见 [release.json](release.json)。

## 上传与解压

将 `deploy.tar.gz` 和 `SHA256SUMS` 上传到服务器同一个目录。在该目录执行：

```bash
uname -m  # 目标为 x86_64；其他架构先确认兼容镜像，不直接启动
sha256sum --ignore-missing -c SHA256SUMS
sudo install -d -m 0750 -o "$(id -u)" -g "$(id -g)" /data/basil
tar -xzf deploy.tar.gz -C /data/basil
cd /data/basil
sha256sum -c FILES.sha256
bash deploy.sh --self-test
```

仅在确认全新、没有已有数据和定制模板的部署目录中解压。

## 配置并启动

```bash
[ -e .env.middleware ] || cp .env.middleware.example .env.middleware
[ -e .env.studio ] || cp .env.studio.example .env.studio
[ -e .env.workbench ] || cp .env.workbench.example .env.workbench
chmod 600 .env.middleware .env.studio .env.workbench
docker ps --format 'table {{{{.Names}}}}\\t{{{{.Ports}}}}'
sudo bash deploy.sh
```

主菜单选 `1`，四项中间件选择本地部署（`1`）。按提示输入独立的数据库、Redis、RabbitMQ、MinIO、Studio 加密密码和 Workbench 新建/重置用户默认密码。对外访问 IP 输入 `{host}`；Sandbox Host 使用本机稳定且唯一的标识。

MinIO 文件地址由交互填写；其默认直连端口为 `{configs['middleware']['MINIO_API_HOST_PORT']}`。正式对外文件访问按 INSTALL.md 配置受控入口/域名，不能把仅本机可达的地址用于外部用户或模型。

本包预填的应用地址：

- Studio：{studio_url}/basilos/asset/manage
- Workbench：{workbench_url}/chat
- Workbench `APP_URL` 使用前端同源代理入口；API 的宿主机端口 `{configs['workbench']['WORKBENCH_HOST_PORT']}` 与 Runtime Gateway 端口 `{configs['workbench']['RUNTIME_GATEWAY_HOST_PORT']}` 均使用宿主机端口映射，请在云安全组控制访问。
- Workbench 到 Studio 的平台网关为 Docker 内部 `http://studio-frontend/`，无需使用宿主机公网地址绕行。

端口冲突时按脚本提示输入新端口，脚本保存并重试。部署后选择菜单 `8` 配置域名和 HTTPS，自动同步应用 URL；修改环境文件后选择菜单 `7` 重新创建服务。内置管理员首次登录方式和改密要求见 INSTALL.md，`DEFAULT_USER_PASSWORD` 不会修改内置管理员初始密码。

## 验收

```bash
./deploy.sh --health
```

继续完成 INSTALL.md 中的 HTTP、登录、文件上传下载和 Sandbox 验收。真实模型对话与 AI 打标尚未验收。SSH 登录密码、应用密码、私钥和本机测试数据均未写入本包。
"""
    if not host:
        # Public releases retain the templates' interactive address placeholders.
        del contents["SERVER.md"]
    encoded = {name: text.encode("utf-8") for name, text in contents.items()}
    encoded["FILES.sha256"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in sorted(encoded.items())
    ).encode("utf-8")
    return encoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="输出目录；不覆盖已有同名部署包")
    parser.add_argument("--host", type=server_host, help="可选：预填服务器 IP 或域名；省略则生成通用交互部署包")
    args = parser.parse_args()
    names = ("deploy.tar", "deploy.tar.gz", "SHA256SUMS")
    if any((args.output / name).exists() for name in names):
        parser.error("输出目录已有部署包，请使用新的空目录")
    try:
        contents = build_contents(args.host)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    args.output.mkdir(parents=True, exist_ok=True)
    for name, mode in (("deploy.tar", "w"), ("deploy.tar.gz", "w:gz")):
        with tarfile.open(args.output / name, mode, format=tarfile.PAX_FORMAT) as archive:
            for path, data in sorted(contents.items()):
                info = tarfile.TarInfo(path)
                info.size = len(data)
                info.mode = 0o755 if path.endswith(".sh") else 0o644
                archive.addfile(info, io.BytesIO(data))
    (args.output / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256((args.output / name).read_bytes()).hexdigest()}  {name}\n"
        for name in names[:2]
    ), encoding="utf-8")
    print(f"已生成 {len(contents)} 个文件的 Linux 首次部署包：{args.output.resolve()}")


if __name__ == "__main__":
    main()
