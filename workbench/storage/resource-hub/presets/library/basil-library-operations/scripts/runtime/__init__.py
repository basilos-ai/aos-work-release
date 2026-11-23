"""Basil API transport using Workbench-managed OAuth2 or personal credentials."""

from __future__ import annotations

import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OAUTH_PROVIDER_KEY = "basilos"
OAUTH_ENV_PREFIX = "APP_OAUTH_BASILOS"
PERSONAL_TOKEN_ENV = "APP_BASILOS_PERSONAL_TOKEN"
PERSONAL_CREDENTIAL_KEY = "app.basilos.personal-token"
AUTH_MODE = "auto"
RUNTIME_DOMAIN = None
SERVICE_PATH = Path(__file__).with_name("service.json")
DEFAULT_TIMEOUT = 30.0
REAUTHORIZE = (
    "请按 SKILL.md 通过 Workbench request_user_input 原生 OAuth2 授权卡连接 Library 或 Base；"
    "授权成功后将在新 Attempt 自动恢复任务。仅当用户明确要求使用个人令牌时，才按 references/auth.md 收集令牌"
)


class BasilError(Exception):
    """An expected Basil request or configuration error."""

    def __init__(self, message, *, next_action=None, details=None):
        super().__init__(message)
        self.next_action = next_action
        self.details = details


def personal_token_action() -> dict[str, Any]:
    """Fixed local hint; the Agent must invoke the actual Workbench password tool."""
    return {
        "tool": "request_user_input",
        "arguments": {
            "title": "Configure BasilOS personal token",
            "description": (
                "You explicitly requested personal-token authorization. To find your token:\n"
                "1. Open the Library platform.\n"
                "2. Sign in with your Library account.\n"
                "3. Click your profile panel in the bottom-left corner.\n"
                "4. Select \"Personal token\".\n"
                "5. Copy the token from the pop-up and paste it into the secure field below."
            ),
            "credentialKey": PERSONAL_CREDENTIAL_KEY,
            "fields": [{
                "name": "personal_token", "label": "BasilOS Personal Token",
                "type": "password", "secret": True, "required": True,
                "environmentName": PERSONAL_TOKEN_ENV,
            }],
        },
    }


def _environment_value(suffix: str) -> str | None:
    value = os.environ.get(f"{OAUTH_ENV_PREFIX}_{suffix}")
    return value if value and value.strip() else None


def _redact(text: str) -> str:
    # Defense in depth for provider error messages and accidental token echoes.
    secrets = {
        os.environ.get(name, "")
        for name in (
            f"{OAUTH_ENV_PREFIX}_ACCESS_TOKEN",
            f"{OAUTH_ENV_PREFIX}_REFRESH_TOKEN",
            PERSONAL_TOKEN_ENV,
            "BASILOS_ACCESS_TOKEN",
        )
    }
    secrets |= {json.dumps(secret, ensure_ascii=False)[1:-1] for secret in secrets}
    for secret in sorted(secrets - {""}, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text


def _http_error_details(exc) -> dict:
    """Expose only bounded, sanitized scalar fields from a business error envelope."""
    details = {"httpStatus": exc.code}
    try:
        raw = exc.read(16385)
        if len(raw) > 16384:
            return details
        data = json.loads(raw)
    except (ValueError, UnicodeError, OSError):
        return details
    if not isinstance(data, dict) or data.get("success") is not False:
        return details
    for key in ("code", "message", "errorKey", "requestId", "traceId"):
        value = data.get(key)
        if type(value) not in (str, int):
            continue
        value = _redact(str(value))
        value = re.sub(r"https?://[^\s<>\"']+", "[URL REDACTED]", value)
        value = re.sub(r"(?i)(bearer\s+|(?:auth-token|authorization|token|cookie|secret|password)\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]", value)
        details[key] = " ".join(value.split())[:500]
    return details


def runtime_origin(domain: Any) -> str:
    """Validate the current session_status domain before using credentials.

    The Agent must pass the tool result unchanged. URL validation does not
    authenticate its provenance; Workbench supplies the trusted session domain.
    """
    if not isinstance(domain, str) or not domain:
        raise BasilError("Missing _runtimeDomain; call session_status with {} and pass its domain in every API script input")
    try:
        parsed = urllib.parse.urlsplit(domain)
        parsed.port
    except ValueError:
        raise BasilError("Invalid _runtimeDomain URL") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or "?" in domain or "#" in domain
        or "\\" in domain
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in domain)
    ):
        raise BasilError("_runtimeDomain must be the HTTPS origin returned by session_status, without an API path, credentials, query or fragment")
    return domain.rstrip("/")


def service_api_base() -> str:
    """Build the platform-guaranteed API entry from the current session domain."""
    origin = runtime_origin(RUNTIME_DOMAIN)
    try:
        config = json.loads(SERVICE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise BasilError("Cannot read packaged runtime/service.json") from None
    prefix = config.get("api_prefix") if isinstance(config, dict) else None
    if prefix != "/typekey/api/v1":
        raise BasilError("Packaged API prefix must be /typekey/api/v1")
    return origin + prefix


def _credential_state() -> tuple[str, str | None]:
    access_token = _environment_value("ACCESS_TOKEN")
    if access_token is None:
        if _environment_value("REFRESH_TOKEN") is not None:
            return "refresh_only", f"仅有 Refresh Token，不能用于访问 API。{REAUTHORIZE}"
        return "missing_access_token", (
            f"缺少 {OAUTH_ENV_PREFIX}_ACCESS_TOKEN；请检查页面授权、Runtime 凭证注入及部署版本。"
            f"{REAUTHORIZE}"
        )
    if any(char.isspace() for char in access_token):
        return "invalid_access_token", f"Access Token 格式无效。{REAUTHORIZE}"
    token_type = _environment_value("TOKEN_TYPE") or "Bearer"
    if token_type.lower() != "bearer":
        return "unsupported_token_type", "BasilOS API 仅支持 Bearer Token；请管理员检查授权协议"
    expires_at = _environment_value("EXPIRES_AT")
    if expires_at is not None:
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                raise ValueError
        except ValueError:
            return "invalid_expiry", "OAuth2 EXPIRES_AT 必须是带时区的 ISO 8601 时间；请检查 Runtime 凭证配置"
        if expiry <= datetime.now(timezone.utc):
            return "expired", f"Access Token 已过期。{REAUTHORIZE}"
    return "available", None


def _selected_credential() -> tuple[str, str, str | None]:
    oauth_state, oauth_message = _credential_state()
    token = os.environ.get(PERSONAL_TOKEN_ENV)
    if AUTH_MODE == "oauth2" or (AUTH_MODE == "auto" and oauth_state == "available"):
        return "oauth2", oauth_state, oauth_message
    if AUTH_MODE == "personal_token" or (token and token.strip()):
        if not token or not token.strip():
            return "personal_token", "missing_personal_token", "请通过 Workbench 安全表单配置个人令牌"
        if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in token):
            message = (
                "个人令牌格式无效，请通过 Workbench 安全表单更新"
                if AUTH_MODE == "personal_token" else f"个人令牌格式无效。{REAUTHORIZE}"
            )
            return "personal_token", "invalid_personal_token", message
        return "personal_token", "available", None
    return "oauth2", oauth_state, oauth_message


def authorization_status() -> dict[str, Any]:
    """Describe local availability; this does not verify remote account or scopes."""
    base = service_api_base()
    mode, state, message = _selected_credential()
    result: dict[str, Any] = {
        "source": "app",
        "provider_key": OAUTH_PROVIDER_KEY,
        "env_prefix": OAUTH_ENV_PREFIX,
        "auth_mode": mode,
        "personal_token_present": bool(os.environ.get(PERSONAL_TOKEN_ENV, "").strip()),
        "api_base": base,
        "state": state,
        "access_token_present": _environment_value("ACCESS_TOKEN") is not None,
        "refresh_token_present": _environment_value("REFRESH_TOKEN") is not None,
        "configured": state == "available",
        "oauth2_usable": _credential_state()[0] == "available",
        "verified": False,
    }
    if message is not None:
        result["message"] = message
        if AUTH_MODE == "personal_token":
            result["next_action"] = personal_token_action()
    return result


def auth_headers() -> dict[str, str]:
    mode, _, message = _selected_credential()
    if message is not None:
        raise BasilError(message, next_action=personal_token_action() if AUTH_MODE == "personal_token" else None)
    if mode == "personal_token":
        return {"auth-token": os.environ[PERSONAL_TOKEN_ENV]}
    return {"Authorization": f"Bearer {_environment_value('ACCESS_TOKEN')}"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward the Attempt's credentials to a redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _perform_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    payload: bytes | None,
    timeout: float,
) -> tuple[str, str]:
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(req, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return _redact(response.read().decode(charset)), response.headers.get_content_type()


def validate_timeout(timeout: Any) -> None:
    if (
        not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
        or not math.isfinite(timeout) or timeout <= 0
    ):
        raise BasilError("timeout must be a positive finite number")


def request(
    method: str,
    endpoint: str,
    *,
    query: dict[str, Any] | None = None,
    body: Any = None,
    raw_body: bytes | None = None,
    content_type: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[str, str]:
    validate_timeout(timeout)
    if (
        not isinstance(endpoint, str) or not (
            endpoint.startswith("/openapi/")
            or (method, endpoint) in {
                ("PUT", "/assets/metadata/field/save"),
                ("GET", "/assets/rule/group/page"),
                ("POST", "/assets/rule/group/save"),
                ("PUT", "/assets/rule/group/update"),
                ("DELETE", "/assets/rule/group/deleteBatch"),
            }
            or (method == "GET" and re.fullmatch(r"/assets/rule/group/[0-9]+", endpoint))
        )
        or any(char in endpoint for char in "?#\\")
        or any(part in {".", ".."} for part in urllib.parse.unquote(endpoint).split("/"))
    ):
        raise BasilError("endpoint must be a packaged Basil OpenAPI path")
    url = service_api_base() + endpoint
    if query:
        values = {key: value for key, value in query.items() if value is not None}
        url += "?" + urllib.parse.urlencode(values, doseq=True)
    headers = {"Accept": "*/*", **auth_headers()}
    if body is not None and raw_body is not None:
        raise BasilError("body and raw_body are mutually exclusive")
    payload = raw_body
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif raw_body is not None:
        if not isinstance(raw_body, bytes):
            raise BasilError("raw_body must be bytes")
        if not isinstance(content_type, str) or not content_type:
            raise BasilError("content_type is required with raw_body")
        headers["Content-Type"] = content_type
    try:
        return _perform_request(method, url, headers=headers, payload=payload, timeout=timeout)
    except urllib.error.HTTPError as exc:
        details = _http_error_details(exc) if exc.code not in (401, 403) and exc.code >= 400 else None
        exc.close()
        if exc.code == 401:
            if "auth-token" in headers:
                if AUTH_MODE != "personal_token":
                    raise BasilError(f"HTTP 401：个人令牌无效或已撤销。{REAUTHORIZE}") from None
                raise BasilError("HTTP 401：个人令牌无效或已撤销，请通过 Workbench 安全表单更新",
                                 next_action=personal_token_action()) from None
            raise BasilError(f"HTTP 401：授权可能已过期或被撤销。{REAUTHORIZE}") from None
        if exc.code == 403:
            raise BasilError("HTTP 403：请检查账号的 Scope 和业务权限；刷新 Token 不一定能解决权限不足") from None
        if 300 <= exc.code < 400:
            raise BasilError(f"HTTP {exc.code}：已阻止携带凭证的重定向；请管理员核对包内 API 地址") from None
        # Preserve the stable error string; never expose the raw body or headers.
        raise BasilError(f"Basil request failed with HTTP {exc.code}", details=details) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise BasilError("Basil 网络请求失败；请检查已配置的 API 地址和连接") from None


def parse_success_response(raw: str) -> dict[str, Any]:
    try:
        response = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BasilError(f"Basil returned invalid JSON: {exc.msg}") from None
    if not isinstance(response, dict):
        raise BasilError("Basil response must be a JSON object")
    if response.get("success") is not True or response.get("code") != 0:
        message = response.get("message")
        detail = _redact(message) if isinstance(message, str) else "unknown error"
        raise BasilError(f"Basil business error: {detail}")
    return response


def read_json_stdin(default: dict[str, Any] | None = None, *, helper: bool = False) -> dict[str, Any]:
    global AUTH_MODE, RUNTIME_DOMAIN
    AUTH_MODE = "auto"
    RUNTIME_DOMAIN = None
    raw = sys.stdin.read()
    if not raw.strip():
        if default is not None:
            return dict(default)
        if helper:
            raise BasilError(
                "INPUT_CHANNEL_ERROR: stdin is empty; no API request was made. "
                "Pass the function arguments as one JSON object on stdin, for example {}. "
                "This local helper makes no API call and needs no runtime domain or "
                "authorization check."
            )
        raise BasilError(
            "INPUT_CHANNEL_ERROR: stdin is empty; no API request was made. "
            "Call session_status({}) and scripts/auth/status.py with the current domain first, "
            "then read the selected capability reference and send its complete JSON on "
            "standard input (stdin). Use the shell here-document example in SKILL.md "
            "for argv-only exec. Correct this local invocation without asking the user "
            "for technical parameters or treating it as an authorization failure."
        )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BasilError(f"standard input must be valid JSON: {exc.msg}") from None
    if not isinstance(value, dict):
        raise BasilError("standard input must contain one JSON object")
    if "operation" in value and not isinstance(value["operation"], str):
        raise BasilError("operation must be a string")
    domain = value.pop("_runtimeDomain", None)
    if domain is not None:
        RUNTIME_DOMAIN = runtime_origin(domain)
    mode = value.pop("_authMode", "auto")
    if mode not in ("auto", "oauth2", "personal_token"):
        raise BasilError("_authMode must be auto, oauth2, or personal_token")
    AUTH_MODE = mode
    return value


def print_json(value: Any, *, compact: bool = False) -> None:
    """Print JSON without changing its data. Compact output only saves tokens."""
    if compact:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    print(_redact(text))


def run_script(action: Any) -> int:
    try:
        if len(sys.argv) > 1:
            raise BasilError(
                "INPUT_CHANNEL_ERROR: script arguments are not supported; pass one JSON object "
                "on standard input (stdin), not in argv/exec.arguments. Fix the invocation before checking "
                "domain or authorization; do not reauthorize for this error."
            )
        action()
        return 0
    except (BasilError, OSError) as exc:
        result = {"success": False, "error": str(exc)}
        if isinstance(exc, BasilError) and exc.next_action is not None:
            result["next_action"] = exc.next_action
        if isinstance(exc, BasilError) and exc.details is not None:
            result["details"] = exc.details
        print_json(result)
        return 1
