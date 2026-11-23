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
SERVICE_PATH = Path(__file__).parent / "config" / "service.json"
DEFAULT_TIMEOUT = 30.0
REFRESH_MARGIN_SECONDS = 60
REAUTHORIZE = (
    "Use references/auth.md: managed silent refresh before expiry-driven consent; "
    "resume with fresh injection. Personal-token collection requires an explicit user request."
)


class BasilError(Exception):
    """An expected Basil request or configuration error."""

    def __init__(self, message, *, next_action=None, details=None):
        super().__init__(message)
        self.next_action = next_action
        self.details = details


def personal_token_action(*, explicit_request=False, replacement=False, replacement_attempts=0) -> dict[str, Any]:
    """Emit the fixed secure form only for a user-requested static-token workflow."""
    if explicit_request is not True:
        raise BasilError("An explicit user request is required before collecting a personal token")
    if type(replacement) is not bool or type(replacement_attempts) is not int or replacement_attempts < 0:
        raise BasilError("Invalid replacement recovery controls")
    if replacement_attempts >= 1:
        raise BasilError("Personal-token replacement budget exhausted; stop credential-dependent work")
    origin = runtime_origin(RUNTIME_DOMAIN)
    library_url = origin + "/library"
    return {
        "tool": "request_user_input",
        "arguments": {
            "title": "Configure BasilOS personal token",
            "description": (
                f"Open Library at {library_url} and sign in with your Library account. "
                "Open the bottom-left profile panel, select Personal token, and copy the token. "
                "Paste it only into this secure password field, never into chat."
            ),
            "credentialKey": PERSONAL_CREDENTIAL_KEY,
            "fields": [{"name": "personal_token", "label": "BasilOS Personal Token",
                        "type": "password", "secret": True, "required": True,
                        "environmentName": PERSONAL_TOKEN_ENV}],
        },
    }


def oauth_card_action() -> dict[str, Any]:
    return {"tool": "request_user_input", "arguments": {
        "title": "Connect Basil-admin-console",
        "description": "Authorize access to the users, roles and resources you may administer.",
        "authorization": {"type": "app_oauth", "appKey": "library"}, "fields": []}}


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
        raise BasilError("Cannot read packaged config/service.json") from None
    prefix = config.get("api_prefix") if isinstance(config, dict) else None
    if prefix != "/typekey/api/v1":
        raise BasilError("Packaged API prefix must be /typekey/api/v1")
    return origin + prefix


def _credential_state() -> tuple[str, str | None]:
    access_token = _environment_value("ACCESS_TOKEN")
    if access_token is None:
        if _environment_value("REFRESH_TOKEN") is not None:
            return "refresh_only", "Access token absent; managed refresh and fresh injection are required"
        return "missing_access_token", "No injected OAuth access token; check managed connection status before consent"
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in access_token):
        return "invalid_access_token", "Malformed injected OAuth access token; repair credential injection"
    if (_environment_value("TOKEN_TYPE") or "Bearer").lower() != "bearer":
        return "unsupported_token_type", "BasilOS requires Bearer OAuth tokens"
    expires_at = _environment_value("EXPIRES_AT")
    if expires_at is not None:
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                raise ValueError
        except ValueError:
            return "invalid_expiry", "OAuth EXPIRES_AT must be timezone-aware ISO 8601; repair host metadata"
        remaining = (expiry - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            return "expired", "OAuth access token expired; follow managed refresh recovery"
        if remaining <= REFRESH_MARGIN_SECONDS:
            return "expiring", "OAuth access token approaches expiry; refresh when a managed grant is available"
    return "available", None


def _personal_state() -> tuple[str, str | None]:
    token = os.environ.get(PERSONAL_TOKEN_ENV)
    if not token or not token.strip():
        return "missing_personal_token", "Personal token is absent; collection requires an explicit user request"
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in token):
        return "invalid_personal_token", "Malformed injected personal token; do not automatically collect a replacement"
    return "available", None


def _selected_credential() -> tuple[str, str, str | None]:
    if AUTH_MODE == "personal_token":
        return ("personal_token", *_personal_state())
    oauth_state, message = _credential_state()
    refresh_present = _environment_value("REFRESH_TOKEN") is not None
    # Refresh takes precedence over initial fallback. No request retries here.
    if oauth_state == "available" or (oauth_state == "expiring" and not refresh_present):
        return "oauth2", "available", None
    if AUTH_MODE == "auto" and oauth_state in {"missing_access_token", "expired"} and not refresh_present:
        state, static_message = _personal_state()
        if state == "available":
            return "personal_token", state, static_message
    return "oauth2", oauth_state, message


def status() -> dict[str, Any]:
    """Local presence only; no remote verification or token exchange."""
    base = service_api_base()
    mode, state, message = _selected_credential()
    oauth_state, _ = _credential_state()
    refresh_present = _environment_value("REFRESH_TOKEN") is not None
    result = {
        "source": "connector", "credential_source": "app", "provider_key": OAUTH_PROVIDER_KEY,
        "env_prefix": OAUTH_ENV_PREFIX, "auth_mode": mode,
        "personal_token_present": bool(os.environ.get(PERSONAL_TOKEN_ENV, "").strip()),
        "api_base": base, "state": state, "oauth_state": oauth_state,
        "access_token_present": _environment_value("ACCESS_TOKEN") is not None,
        "refresh_token_present": refresh_present,
        "configured": state == "available", "verified": False,
        "oauth2_usable": oauth_state == "available" or (oauth_state == "expiring" and not refresh_present),
        "managed_refresh_required": mode == "oauth2" and refresh_present and oauth_state in {"expiring", "expired", "refresh_only"},
        "managed_refresh_adapter_verified": False,
    }
    if message:
        result["message"] = message
    return result


authorization_status = status


def verify() -> dict[str, Any]:
    """Read the current authenticated user; return only bounded non-secret evidence."""
    mode, _, message = _selected_credential()
    if message:
        raise BasilError(message)
    raw, _ = request("GET", "/user/readAuthCurrentUser")
    response = parse_success_response(raw)
    user = response.get("data")
    if not isinstance(user, dict) or not user.get("id"):
        raise BasilError("Read-only verification returned no authenticated user identity")
    return {"configured": True, "verified": True, "auth_mode": mode,
            "user": {key: user[key] for key in ("id", "username", "nickname") if key in user}}


def auth_headers() -> dict[str, str]:
    mode, _, message = _selected_credential()
    if message:
        raise BasilError(message)
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
    from admin_console.contracts import endpoint_allowed
    if not endpoint_allowed(method, endpoint):
        raise BasilError("endpoint must be a packaged Basil-admin-console operation")
    url = service_api_base() + endpoint
    if query:
        values = {key: (str(value).lower() if isinstance(value, bool) else value)
                  for key, value in query.items() if value is not None}
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
        details = _http_error_details(exc) if exc.code >= 400 else None
        exc.close()
        if exc.code == 401:
            selected = "personal_token" if "auth-token" in headers else "oauth2"
            raise BasilError("HTTP 401: verify the credential failure before recovery; do not replay or switch methods",
                             details={**(details or {}), "httpStatus": 401, "auth_mode": selected,
                                      "recovery": "inspect_managed_oauth" if selected == "oauth2" else "explicit_static_recovery_only"}) from None
        if exc.code == 403:
            raise BasilError("HTTP 403: check permission/license codes; do not automatically reauthorize", details=details) from None
        if 300 <= exc.code < 400:
            raise BasilError(f"HTTP {exc.code}: credential-bearing redirect blocked") from None
        # Preserve the stable error string; never expose the raw body or headers.
        raise BasilError(f"Basil request failed with HTTP {exc.code}", details=details) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise BasilError("Basil network request failed; check routing/egress and reconcile unknown write outcomes") from None


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
        raise BasilError(f"Basil business error: {detail}", details={k: response[k] for k in ("code", "errorKey") if type(response.get(k)) in (str, int)})
    return response


def read_json_stdin(default: dict[str, Any] | None = None) -> dict[str, Any]:
    global AUTH_MODE, RUNTIME_DOMAIN
    AUTH_MODE = "auto"
    RUNTIME_DOMAIN = None
    raw = sys.stdin.read()
    if not raw.strip():
        if default is not None:
            return dict(default)
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
    if mode == "api_key":
        mode = "personal_token"
    if mode not in ("auto", "oauth2", "personal_token"):
        raise BasilError("_authMode must be auto, oauth2, api_key or personal_token")
    AUTH_MODE = mode
    return value


def print_json(value: Any) -> None:
    print(_redact(json.dumps(value, ensure_ascii=False, indent=2)))


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
