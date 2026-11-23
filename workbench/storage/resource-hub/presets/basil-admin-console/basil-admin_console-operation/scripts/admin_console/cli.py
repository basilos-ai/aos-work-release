#!/usr/bin/env python3
"""Strict stdin dispatcher for Basil-admin-console; standard library only, no retries."""
from __future__ import annotations

import json
import mimetypes
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from admin_console.contracts import MODELS, OPERATIONS, SYSTEM_PERMISSIONS
from runtime import BasilError, DEFAULT_TIMEOUT, parse_success_response, print_json, read_json_stdin, request, run_script


def require(condition, message):
    if not condition:
        raise BasilError(message)


def validate_value(value, spec, location):
    typ = spec["type"]
    if value is None:
        require(not spec["required"], f"{location} is required")
        return
    if typ.endswith("[]"):
        require(isinstance(value, list), f"{location} must be an array")
        for i, item in enumerate(value):
            validate_value(item, {**spec, "type": typ[:-2], "required": True}, f"{location}[{i}]")
    elif typ in MODELS:
        model = MODELS[typ]
        if "enum" in model:
            require(isinstance(value, str) and value in model["enum"], f"{location} has an unsupported enum value")
        else:
            validate_object(value, model, location)
    elif typ in ("integer", "int32"):
        require(type(value) is int, f"{location} must be an integer")
    elif typ == "boolean":
        require(type(value) is bool, f"{location} must be boolean")
    elif typ.startswith("string(") or typ.startswith("BigInteger"):
        require(isinstance(value, str) and re.fullmatch(r"[0-9]+", value) is not None,
                f"{location} must be a decimal ID string (including 0 where allowed)")
    elif typ == "string":
        require(isinstance(value, str), f"{location} must be a string")
    else:
        raise BasilError(f"unhandled packaged type {typ}; do not send an unvalidated request")
    if spec.get("not_blank"):
        require(isinstance(value, str) and bool(value.strip()), f"{location} must not be blank")


def validate_object(value, fields, location):
    require(isinstance(value, dict), f"{location} must be an object")
    require(not set(value) - set(fields), f"{location} contains unsupported fields")
    for key, spec in fields.items():
        if spec["required"]:
            require(key in value and value[key] is not None, f"{location}.{key} is required")
        if key in value:
            validate_value(value[key], spec, f"{location}.{key}")


def bounded(value, minimum, maximum, location):
    if value is not None:
        require(type(value) is int and minimum <= value <= maximum,
                f"{location} must be an integer in {minimum}..{maximum}")


def validate_business(name, body, query, path):
    bounded(query.get("page"), 1, 2**31-1, "query.page")
    bounded(query.get("size"), 1, 100 if name == "shares_received" else 1000, "query.size")
    bounded(query.get("folderSize"), 1, 100, "query.folderSize")
    bounded(query.get("fileSize"), 1, 100 if name.startswith("directory_") else 1000, "query.fileSize")
    if name.startswith("directory_"):
        require(query.get("spaceType") != "SHARED" or query.get("entryRootId") is not None,
                "SHARED requires a real received directory entryRootId")
    if name in ("directory_search", "shares_received"):
        require(len(query.get("keyword") or "") <= 100, "query.keyword exceeds 100 characters")
    if name == "shares_received":
        require(len(query.get("cursor") or "") <= 2048, "query.cursor exceeds 2048 characters")
    if name in ("effective_permissions", "resource_files", "folder_navigate"):
        require(bool(query.get("path")) or query.get("targetId") is None or query.get("targetType") is not None,
                "targetId requires targetType when path is absent")
    if name == "department_delete":
        require(path["id"] != "0", "cannot delete the root department")
    if name == "system_role_delete":
        require(path["id"] != "0", "cannot delete the default system role")
    if name == "department_update" and body.get("parentId") is not None:
        require(body["id"] != "0" and body["parentId"] != body["id"], "cannot move root or move a department under itself")
        # Descendant and existence checks require the current tree; see departments.md.
    if name in ("user_create", "user_batch_create", "user_update"):
        users = body if isinstance(body, list) else [body]
        for user in users:
            username = user.get("username")
            if username is not None:
                require(bool(username.strip()) and len(username) <= 100 and re.search(r'[\\/:*?"<>|]', username) is None,
                        "username must be nonblank, at most 100 characters, without path-reserved characters")
            email = user.get("email")
            if email:
                require(len(email) <= 320 and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) is not None, "email must be a valid address of at most 320 characters")
            permissions = user.get("userPermissionIdList")
            if permissions is not None:
                require(set(permissions) <= {"114001", "114002"}, "userPermissionIdList supports only 114001/114002")
            for key in ("personalAssets", "personalBase"):
                if user.get(key) is not None:
                    require(user[key]["enabled"] is True, f"{key} only supports enabled=true")
            if name == "user_batch_create":
                require(not user.get("departmentIdList") or set(user["departmentIdList"]) == {"0"},
                        "batch create ignores departments and assigns root; use user_create for non-root departments")
        if name == "user_batch_create":
            require(len({x["username"] for x in users}) == len(users), "batch usernames must be unique")
    if name in ("system_role_create", "system_role_update"):
        require(set(body.get("permissionList") or []) <= SYSTEM_PERMISSIONS,
                "permissionList must contain documented system permission IDs, not user-level or ACL action IDs")
    if name == "organization_join":
        require(bool(body["tenantIdList"]), "tenantIdList must not be empty")
    if name == "organization_role_assign":
        require(bool(body["roleIdList"]), "roleIdList must not be empty")
    if name == "organization_role_create":
        require(len(body["name"].encode("utf-16-le")) // 2 <= 20, "organization role name exceeds 20 UTF-16 code units")
    if name in ("acl_create", "acl_update"):
        require(bool(body.get("systemRoleIdList") or body.get("departmentIdList")), "ACL requires at least one system role or department")
        rules = body.get("ruleList") or []
        require(len({rule["folderId"] for rule in rules}) == len(rules), "duplicate ACL folder rules are ambiguous")
        for rule in rules:
            actions = rule.get("permissionIdList")
            if actions is not None:
                require(set(actions) <= {str(i) for i in range(1,12)}, "ACL actions must be IDs 1..11")
                require(rule["presetType"] == "CUSTOM" or not actions, "permissionIdList is effective only for CUSTOM")
    if name in ("share_create", "share_update"):
        require((body.get("userId") is not None) != (body.get("departmentId") is not None), "direct share requires exactly one userId or departmentId")
        require(body["presetType"] in {"VIEW", "DOWNLOAD", "UPLOAD", "EDIT"}, "direct sharing supports VIEW/DOWNLOAD/UPLOAD/EDIT only")
    if name in ("share_update", "share_delete"):
        require(body["version"] >= 0, "version must be the current nonnegative grant version")


def validate_payload(payload):
    require(isinstance(payload, dict), "input must be an object")
    name = payload.get("operation")
    require(isinstance(name, str) and name in OPERATIONS, "operation must name a supported Basil-admin-console operation")
    op = OPERATIONS[name]
    require(not op.get("unsupported"), op.get("unsupported", "unsupported operation"))
    allowed = {"operation", "path", "query", "body", "_timeout", "_confirm", "_target"}
    if op["body_kind"] == "multipart":
        allowed |= {"file_path", "filename"}
    require(not set(payload) - allowed, "unsupported top-level input fields")
    path = payload.get("path", {})
    query = payload.get("query", {})
    validate_object(path, op["fields"].get("path", {}), "path")
    validate_object(query, op["fields"].get("query", {}), "query")
    body = payload.get("body")
    kind = op["body_kind"]
    if kind == "array":
        require(isinstance(body, list) and bool(body), "body must be a nonempty top-level JSON array")
        for i, item in enumerate(body):
            validate_object(item, op["fields"]["body"], f"body[{i}]")
    elif kind == "object":
        if name == "folder_page_post" and body is None:
            pass  # Its metadata filter is an optional raw object, never a wrapper.
        else:
            validate_object(body, op["fields"]["body"], "body")
        for field in op.get("require_explicit", []):
            require(field in body, f"body.{field} must be explicitly preserved or intentionally replaced")
    else:
        require(body is None, "this operation does not accept a JSON body")
    if op["mutating"]:
        require(payload.get("_confirm") is True, "write requires _confirm=true after a concrete user instruction or confirmation")
    if op["destructive"]:
        require(isinstance(payload.get("_target"), str) and bool(payload["_target"].strip()), "sensitive/destructive operation requires a nonempty _target description")
    validate_business(name, body, query, path)
    return name, op, path, query, body


def multipart(payload):
    file_path = payload.get("file_path")
    require(isinstance(file_path, str) and bool(file_path), "icon_upload requires file_path")
    file = Path(file_path).expanduser()
    require(file.is_file(), "file_path must identify a regular file")
    filename = payload.get("filename")
    require(filename is None or isinstance(filename, str), "filename must be a string")
    for value in (file.name, filename or ""):
        require(not any(c in value for c in ('\r', '\n', '"')), "multipart filename contains invalid characters")
    boundary = "basil-admin-" + secrets.token_hex(16)
    mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    prefix = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file.name}"\r\nContent-Type: {mime}\r\n\r\n').encode()
    data = prefix + file.read_bytes() + b"\r\n"
    if filename is not None:
        data += (f'--{boundary}\r\nContent-Disposition: form-data; name="filename"\r\n\r\n{filename}\r\n').encode()
    return data + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def sanitize_response(value):
    # UserVO.leader may expose the underlying entity; do not echo authentication internals.
    private = {"password", "salt", "tokenVersion", "accessToken", "refreshToken", "access_token", "refresh_token"}
    if isinstance(value, list):
        return [sanitize_response(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_response(item) for key, item in value.items() if key not in private}
    return value


def execute(payload):
    name, op, path, query, body = validate_payload(payload)
    endpoint = op["endpoint"]
    for key, value in path.items():
        endpoint = endpoint.replace("{" + key + "}", value)
    kwargs = {"query": query, "timeout": payload.get("_timeout", DEFAULT_TIMEOUT)}
    if op["body_kind"] == "multipart":
        kwargs["raw_body"], kwargs["content_type"] = multipart(payload)
    else:
        kwargs["body"] = body
    raw, _ = request(op["method"], endpoint, **kwargs)
    if name == "icon_upload":
        require(isinstance(raw, str) and raw.strip().startswith(("https://", "http://")), "upload did not return a URL string; inspect the operation outcome before retrying")
        return {"success": True, "code": 0, "data": raw.strip()}
    return sanitize_response(parse_success_response(raw))


def main():
    print_json(execute(read_json_stdin()))


if __name__ == "__main__":
    raise SystemExit(run_script(main))
