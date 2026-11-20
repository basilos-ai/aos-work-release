#!/usr/bin/env python3
"""Validate Workbench administrator upload packages and their auth contracts."""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - the declared Runtime baseline includes PyYAML.
    yaml = None


TEXT_SUFFIXES = {
    ".css", ".html", ".ini", ".js", ".json", ".jsx", ".md", ".mjs",
    ".py", ".sh", ".svg", ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml",
}
FORBIDDEN_FILE_NAMES = {
    ".ds_store", "authors.md", "generated-by.md", "generated_by.md",
    "provenance.md", "upstream-provenance.md",
}
AUTHORING_SOURCE = re.compile(
    r"(?im)^\s*(?:[-*]>?\s*)?(?:generated|written|authored|created|produced)\s+by\s+"
    r"(?:codex|claude|chatgpt|copilot)\b|"
    r"^\s*(?:author|writer|generator|source|作者|编写来源|生成来源)\s*[:=：]\s*"
    r"(?:codex|claude|chatgpt|copilot)\b|"
    r"^\s*(?:codex|claude|chatgpt|copilot)\s+(?:generated|wrote|authored|created|produced)\b"
)
PLACEHOLDER = re.compile(
    r"^(?:<[^>]+>|\$\{[^}]+\}|YOUR_|your_|placeholder|platform|managed|"
    r"redacted|REDACTED|TBD|TODO|\.\.\.)"
)
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
AUTH_TYPES = {"none", "token", "oauth", "api_key", "oauth2"}
LEGACY_OAUTH_FILE_NAMES = {
    "token.json", "tokens.json", "oauth-token.json", "oauth_token.json",
    "oauth_tokens.json", "token-store.json", "token_store.json",
    "callback.py", "oauth-callback.py", "oauth_callback.py", "callback_server.py",
}


def load_yaml(path: Path, errors: list[str]) -> Any:
    """读取 YAML；解析失败时只报告路径和错误类型，不回显敏感值。"""
    if yaml is None:
        errors.append(f"{path.name}: PyYAML is unavailable in the validator runtime")
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        errors.append(f"{path.name}: invalid YAML ({type(exc).__name__})")
        return None


def member_directories(root: Path, resource_type: str, errors: list[str]) -> list[Path]:
    if resource_type == "skill":
        if not (root / "SKILL.md").is_file():
            errors.append("Skill requires root SKILL.md")
        return [root]

    if (root / "SKILL.md").exists():
        errors.append(f"{resource_type.title()} root must not contain SKILL.md")
    members = sorted(
        path for path in root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    )
    if not members:
        errors.append(f"{resource_type.title()} requires a first-level member SKILL.md")
    return members


def validate_member(member: Path, root: Path, errors: list[str]) -> None:
    actual_names = {path.name for path in member.iterdir() if path.is_file()}
    relative = member.relative_to(root).as_posix() or "."
    for required in ("SKILL.md", "readme.md", "user_preferences.md"):
        if required not in actual_names:
            errors.append(f"{relative}: missing exact lowercase required file {required}")
            continue
        path = member / required
        if not path.read_text(encoding="utf-8").strip():
            errors.append(f"{relative}/{required}: file must be non-empty")
        elif required == "SKILL.md":
            validate_frontmatter(path, relative, errors)


def validate_frontmatter(path: Path, relative: str, errors: list[str]) -> None:
    """校验 Skill 入口的 YAML frontmatter，避免只检查文件名而漏掉入口契约。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        errors.append(f"{relative}/SKILL.md: missing YAML frontmatter opening delimiter")
        return
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        errors.append(f"{relative}/SKILL.md: missing YAML frontmatter closing delimiter")
        return
    if yaml is None:
        errors.append(f"{relative}/SKILL.md: PyYAML is unavailable for frontmatter validation")
        return
    try:
        frontmatter = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        errors.append(f"{relative}/SKILL.md: invalid YAML frontmatter ({type(exc).__name__})")
        return
    mapping = require_mapping(frontmatter, f"{relative}/SKILL.md frontmatter", errors)
    if mapping is not None:
        require_non_empty(mapping.get("name"), f"{relative}/SKILL.md frontmatter.name", errors)
        require_non_empty(mapping.get("description"), f"{relative}/SKILL.md frontmatter.description", errors)


def validate_tree(root: Path, errors: list[str]) -> None:
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        lowered = path.name.casefold()
        if lowered == "readme.md" and path.name != "readme.md":
            errors.append(f"{relative}: use exact lowercase readme.md")
        if lowered in FORBIDDEN_FILE_NAMES or "provenance" in lowered:
            errors.append(f"{relative}: provenance/authoring-source files are forbidden")
        if path.suffix.casefold() not in TEXT_SUFFIXES or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if AUTHORING_SOURCE.search(text):
            errors.append(f"{relative}: packaged authoring-source attribution is forbidden")


def require_mapping(value: Any, label: str, errors: list[str]) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append(f"{label}: expected a YAML mapping")
        return None
    return value


def require_non_empty(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: must be a non-empty string")


def validate_action(action: Any, index: int, errors: list[str]) -> None:
    mapping = require_mapping(action, f"manifest.actions[{index}]", errors)
    if mapping is None:
        return
    require_non_empty(mapping.get("key"), f"manifest.actions[{index}].key", errors)
    url = mapping.get("url")
    if not isinstance(url, str) or not re.match(r"^https?://", url):
        errors.append(f"manifest.actions[{index}].url: must be an HTTP(S) URL")
    method = str(mapping.get("method", "GET")).upper()
    if method not in HTTP_METHODS:
        errors.append(f"manifest.actions[{index}].method: unsupported HTTP method {method}")
    response_path = mapping.get("responseDataPath", "$")
    if not isinstance(response_path, str) or not response_path.startswith("$"):
        errors.append(f"manifest.actions[{index}].responseDataPath: must use a supported $ path")
    # Workbench 当前只支持点路径，不把它误当成完整 JSONPath。
    if isinstance(response_path, str) and ("[" in response_path or "*" in response_path):
        errors.append(f"manifest.actions[{index}].responseDataPath: array/wildcard JSONPath is unsupported")
    if "auth" in mapping and not isinstance(mapping["auth"], bool):
        errors.append(f"manifest.actions[{index}].auth: must be boolean")


def validate_manifest(root: Path, resource_type: str, errors: list[str]) -> Mapping[str, Any] | None:
    """校验管理员原包的 Connector Manifest。Skill/Work 不强制使用 Manifest。"""
    if resource_type != "connector":
        return None
    manifest_path = root / "manifest.yaml"
    if not manifest_path.is_file():
        errors.append("Connector administrator package requires root manifest.yaml")
        return None
    manifest = require_mapping(load_yaml(manifest_path, errors), "manifest", errors)
    if manifest is None:
        return None
    if manifest.get("schemaVersion") != 1:
        errors.append("manifest.schemaVersion: must be 1")
    plugin = require_mapping(manifest.get("plugin"), "manifest.plugin", errors)
    if plugin is not None:
        require_non_empty(plugin.get("name"), "manifest.plugin.name", errors)
    connector = require_mapping(manifest.get("connector"), "manifest.connector", errors)
    if connector is None:
        return manifest
    key = connector.get("key")
    require_non_empty(key, "manifest.connector.key", errors)
    # 交付目录经常使用 source/ 作为本地包装名；真正的 Connector 包目录仍需与 key 一致。
    if isinstance(key, str) and key != root.name and root.name not in {"source"}:
        errors.append("manifest.connector.key: must match the Connector package directory name")
    provider_key = connector.get("authProviderKey", key)
    require_non_empty(provider_key, "manifest.connector.authProviderKey", errors)

    auth = require_mapping(manifest.get("auth"), "manifest.auth", errors)
    if auth is not None:
        auth_type = auth.get("type")
        if auth_type not in AUTH_TYPES:
            errors.append(f"manifest.auth.type: unsupported value {auth_type!r}")
        if auth_type in {"oauth", "oauth2"}:
            oauth = require_mapping(auth.get("oauth"), "manifest.auth.oauth", errors)
            if oauth is not None:
                for field in ("authorizeUrl", "tokenUrl"):
                    value = oauth.get(field)
                    if not isinstance(value, str) or not re.match(r"^https://", value):
                        errors.append(f"manifest.auth.oauth.{field}: must be a verified HTTPS URL")
                if "redirectUri" in oauth or "resultBaseUrl" in oauth:
                    errors.append("manifest.auth.oauth: remove backend-derived redirectUri/resultBaseUrl")
                scopes = oauth.get("scopes", [])
                if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
                    errors.append("manifest.auth.oauth.scopes: must be a list of strings")
        elif auth_type == "token":
            token = require_mapping(auth.get("token"), "manifest.auth.token", errors)
            if token is not None:
                if token.get("placement", "header") not in {"header", "query"}:
                    errors.append("manifest.auth.token.placement: must be header or query")
                require_non_empty(token.get("name"), "manifest.auth.token.name", errors)
        elif auth_type == "api_key":
            api_key = auth.get("apiKey", auth.get("token"))
            require_mapping(api_key, "manifest.auth.apiKey", errors)

    actions = manifest.get("actions", [])
    if not isinstance(actions, list):
        errors.append("manifest.actions: must be a list")
    else:
        keys: set[str] = set()
        for index, action in enumerate(actions):
            validate_action(action, index, errors)
            if isinstance(action, Mapping) and isinstance(action.get("key"), str):
                if action["key"] in keys:
                    errors.append(f"manifest.actions[{index}].key: duplicate Action key")
                keys.add(action["key"])
    return manifest


def validate_icon(root: Path, errors: list[str]) -> None:
    icon = root / "icon.svg"
    if not icon.is_file():
        errors.append("Connector administrator package requires root icon.svg for the publishing profile")
        return
    text = icon.read_text(encoding="utf-8", errors="replace").lstrip()
    if not text.startswith("<svg"):
        errors.append("icon.svg: expected an SVG document")


def validate_oauth_clients(root: Path, manifest: Mapping[str, Any], errors: list[str], warnings: list[str]) -> None:
    path = root / "oauth-clients.yaml"
    if not path.is_file():
        errors.append("OAuth2 administrator package requires root oauth-clients.yaml")
        return
    document = require_mapping(load_yaml(path, errors), "oauth-clients", errors)
    if document is None:
        return
    clients = document.get("oauthClients")
    if not isinstance(clients, list) or not clients:
        errors.append("oauth-clients.oauthClients: must be a non-empty list")
        return
    connector = manifest.get("connector")
    provider_key = connector.get("authProviderKey", connector.get("key")) if isinstance(connector, Mapping) else None
    matching = [client for client in clients if isinstance(client, Mapping) and client.get("key") == provider_key]
    if not matching:
        errors.append("oauth-clients.oauthClients[].key: no entry matches manifest.connector.authProviderKey")
        return
    client = matching[0]
    if client.get("authType") not in {"oauth", "oauth2"}:
        errors.append("oauth-clients matching entry: authType must be oauth or oauth2")
    for field in ("clientId", "clientSecret"):
        value = client.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"oauth-clients matching entry: missing {field}")
        elif PLACEHOLDER.match(value.strip()):
            warnings.append(f"oauth-clients matching entry: {field} is a placeholder; administrator configuration is still required")


def validate_api_key(root: Path, members: list[Path], errors: list[str]) -> None:
    """Limited static Python Runtime profile; not a secret-flow or live audit."""
    # Connector 也可以只通过 Manifest + Actions 声明接口；只有包内确实带 Python Runtime 时，
    # 才进入脚本级的 status/verify 和环境变量注入检查。
    runtime_members = [member for member in members if (member / "scripts" / "runtime.py").is_file()]
    if not runtime_members:
        return
    for member in runtime_members:
        relative = member.relative_to(root).as_posix()
        runtime = member / "scripts" / "runtime.py"
        source = runtime.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            errors.append(f"{relative}: invalid Python runtime syntax")
            continue
        functions = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in ("status", "verify"):
            if name not in functions:
                errors.append(f"{relative}: missing separate {name} function")
        strings = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        for marker in ("request_user_input", "credentialKey", "environmentName", "password", "secret", "next_action"):
            if marker not in strings:
                errors.append(f"{relative}: missing secure form marker {marker}")
        identities = [value for value in strings if re.fullmatch(r"connector\.[a-z0-9-]+\.[a-z0-9-]+", value)]
        if not identities:
            errors.append(f"{relative}: missing stable connector credential identity")
        environment_reads = any(
            isinstance(node, ast.Attribute) and node.attr == "environ"
            and isinstance(node.value, ast.Name) and node.value.id == "os"
            or isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr == "getenv"
            for node in ast.walk(tree)
        )
        if not environment_reads:
            errors.append(f"{relative}: missing process environment access")
        if "_read_secret_stdin" in functions or any(
            isinstance(node, ast.Name) and node.id == "CREDENTIAL_PATH" for node in ast.walk(tree)
        ):
            errors.append(f"{relative}: legacy secret stdin/file runtime pattern requires removal")
        instructions = (member / "SKILL.md").read_text(encoding="utf-8")
        if any(identity not in instructions for identity in identities):
            errors.append(f"{relative}: runtime credential identity absent from Skill instructions")
        if re.search(r"may provide their own .*current direct/private conversation", instructions, re.I):
            errors.append(f"{relative}: legacy chat credential onboarding")


def validate_oauth_legacy_artifacts(root: Path, errors: list[str]) -> None:
    """拦截本地 OAuth 生命周期文件，但保留原包根目录的控制面配置入口。"""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        name = path.name.casefold()
        if name == "oauth-clients.yaml":
            if path != root / "oauth-clients.yaml":
                errors.append(f"{relative}: oauth-clients.yaml is allowed only at the administrator package root")
            continue
        if name in LEGACY_OAUTH_FILE_NAMES:
            errors.append(f"{relative}: local OAuth token/callback artifact is forbidden")
            continue
        if path.suffix.casefold() in {".py", ".js", ".mjs", ".ts"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"\brefresh[_ -]?token\b", text, re.I):
                errors.append(f"{relative}: script-owned OAuth refresh logic is forbidden")


def validate_oauth2(root: Path, members: list[Path], errors: list[str], manifest: Mapping[str, Any] | None) -> None:
    """Run static checks for the managed OAuth2 branch and admin source package."""
    validate_oauth_legacy_artifacts(root, errors)
    setup = root / "OAUTH_SETUP.md"
    if not setup.is_file() or not setup.read_text(encoding="utf-8").strip():
        errors.append("OAuth2 Connector requires a non-empty root OAUTH_SETUP.md")
        setup_text = ""
    else:
        setup_text = setup.read_text(encoding="utf-8")

    required_setup_terms = {
        "application owner": "application owner/ownership",
        "tenant model": "tenant model",
        "redirect uri": "redirect URI",
        "minimum scopes": "minimum scopes",
        "authorization": "authorization start/resume",
        "managed runtime": "managed Runtime",
        "callback": "callback handling",
        "pkce": "PKCE",
        "token exchange": "token exchange",
        "refresh": "refresh",
        "revocation": "revocation",
        "rotation": "rotation",
        "read-only": "safe read-only verification",
        "connection identity": "connection identity",
        "provider-call channel": "provider-call channel",
        "oauth-clients": "control-plane OAuth client configuration",
        "authproviderkey": "authProviderKey mapping",
    }
    setup_lower = setup_text.casefold()
    for marker, label in required_setup_terms.items():
        if marker not in setup_lower:
            errors.append(f"OAUTH_SETUP.md: missing OAuth2 setup requirement {label}")

    for member in members:
        relative = member.relative_to(root).as_posix()
        instructions_path = member / "SKILL.md"
        if not instructions_path.is_file():
            continue
        instructions = instructions_path.read_text(encoding="utf-8")
        combined_lower = f"{instructions}\n{setup_text}".casefold()
        if not re.search(r"authorization[\s_-]*code", combined_lower):
            errors.append(f"{relative}: missing OAuth2 authorization-code flow")
        for marker, label in (
            ("oauth2", "OAuth2 mode"),
            ("managed", "managed Runtime authorization"),
            ("status", "connection status"),
            ("verify", "separate verification"),
        ):
            if marker.casefold() not in combined_lower:
                errors.append(f"{relative}: missing OAuth2 contract marker {label}")
        if "oauth_setup.md" not in instructions.casefold():
            errors.append(f"{relative}: must reference root OAUTH_SETUP.md")
        if "connector." not in instructions or ".oauth2" not in instructions:
            errors.append(f"{relative}: missing non-secret connector.<connector-key>.oauth2 identity")
        for line in instructions.splitlines():
            if "request_user_input" not in line.casefold():
                continue
            if re.search(r"\b(?:do not|never|must not|without)\b", line, re.I):
                continue
            if re.search(
                r"(?:call|invoke|use|open|submit|collect)[^\n]{0,120}request_user_input|"
                r"request_user_input[^\n]{0,120}(?:password|client secret|access token|refresh token)",
                line,
                re.I,
            ):
                errors.append(f"{relative}: OAuth2 member must not use an API-Key password form")
                break

    secret_assignment = re.compile(
        r"(?im)^\s*(?:[-*]\s*)?(?:client[_-]?secret|access[_-]?token|refresh[_-]?token|"
        r"authorization[_-]?code|connection[_-]?id)\s*[:=]\s*"
        r"(?!<|YOUR_|your_|placeholder|platform|managed|redacted|REDACTED|TBD|TODO|\.\.\.|`)[^\s#]+"
    )
    json_secret_assignment = re.compile(
        r"(?i)[\"'](?:client[_-]?secret|access[_-]?token|refresh[_-]?token|"
        r"authorization[_-]?code|connection[_-]?id)[\"']\s*:\s*[\"']"
        r"(?!<|YOUR_|your_|placeholder|platform|managed|redacted|REDACTED|TBD|TODO|\.\.\.|`)[^\"']+[\"']"
    )
    # 控制面文件允许管理员填入受保护值；验证器不回显也不扫描它的值。
    paths_to_scan = [setup, *[member / "SKILL.md" for member in members], root / "manifest.yaml"]
    for path in paths_to_scan:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if secret_assignment.search(text) or json_secret_assignment.search(text):
            errors.append(f"{path.relative_to(root).as_posix()}: possible OAuth secret/token value")

    if manifest:
        auth = manifest.get("auth")
        if isinstance(auth, Mapping) and auth.get("type") in {"oauth", "oauth2"}:
            oauth = auth.get("oauth")
            if isinstance(oauth, Mapping) and ("redirectUri" in oauth or "resultBaseUrl" in oauth):
                errors.append("manifest.auth.oauth: backend-derived redirectUri/resultBaseUrl must not be packaged")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package")
    parser.add_argument("--resource-type", required=True, choices=("skill", "work", "connector"))
    parser.add_argument("--auth-mode", choices=("api_key", "oauth2"), help="Connector authentication branch")
    parser.add_argument(
        "--package-profile",
        choices=("admin_upload", "resource_only"),
        default="admin_upload",
        help="Validate the administrator source package by default; resource_only is a compatibility profile",
    )
    parser.add_argument(
        "--require-icon",
        action="store_true",
        help="Require the root icon.svg used by the target publishing surface",
    )
    args = parser.parse_args()

    root = Path(args.package).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if args.auth_mode and args.resource_type != "connector":
        errors.append("--auth-mode applies only to connector resources")
    if not root.is_dir():
        errors.append("package must be a directory")
    else:
        members = member_directories(root, args.resource_type, errors)
        for member in members:
            validate_member(member, root, errors)
        validate_tree(root, errors)
        manifest = None
        if args.resource_type == "connector" and args.package_profile == "admin_upload":
            manifest = validate_manifest(root, args.resource_type, errors)
            if args.require_icon:
                validate_icon(root, errors)
            if args.auth_mode == "oauth2" and manifest is not None:
                validate_oauth_clients(root, manifest, errors, warnings)
        if args.auth_mode == "api_key" and args.resource_type == "connector":
            validate_api_key(root, members, errors)
        if args.auth_mode == "oauth2" and args.resource_type == "connector":
            validate_oauth2(root, members, errors, manifest)

    print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
