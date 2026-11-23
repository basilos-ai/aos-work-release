#!/usr/bin/env python3
"""Execute a whitelisted Basil Library OpenAPI operation."""

from __future__ import annotations

import json
import mimetypes
import secrets
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from library.search_validation import validate_space_path
from library.metadata_catalog import (
    compact_catalog,
    fetch_metadata_catalog,
    name_collisions,
)
from runtime import BasilError, DEFAULT_TIMEOUT, parse_success_response, print_json, read_json_stdin, request, run_script
from runtime.openapi import Operation, execute_operation


OPERATIONS = {
    "metadata_field_create": Operation("PUT", "/assets/metadata/field/save", "object", required_body=("name", "description", "type", "planType"), mutating=True),
    "delete_batch": Operation("PUT", "/openapi/assets/deleteBatch", "object", mutating=True, destructive=True),
    "file_delete": Operation("DELETE", "/openapi/assets/file", "object", required_body=("folderId", "fileId"), mutating=True, destructive=True),
    "file_batch": Operation("POST", "/openapi/assets/file/batch", "object", required_body=("idList",), query_defaults={"planType": "LITE"}),
    "file_metadata_operate": Operation("POST", "/openapi/assets/file/metadata/operate", "object", required_body=("operationType", "fileId"), mutating=True),
    "file_move": Operation("PUT", "/openapi/assets/file/move", "object", required_body=("fileId", "version"), mutating=True),
    "file_rename": Operation("PUT", "/openapi/assets/file/rename", "object", required_body=("fileId", "newName", "version"), mutating=True),
    "file_url_batch": Operation("POST", "/openapi/assets/file/url/batch", "list"),
    "folder_delete": Operation("DELETE", "/openapi/assets/folder", "object", required_body=("folderId", "version", "parentVersion"), mutating=True, destructive=True),
    "folder_move": Operation("PUT", "/openapi/assets/folder/move", "object", required_body=("folderId", "version", "parentVersion", "targetParentVersion"), mutating=True),
    "folder_rename": Operation("PUT", "/openapi/assets/folder/rename", "object", required_body=("folderId", "newName", "version", "parentVersion"), mutating=True),
    "folder_create": Operation("PUT", "/openapi/assets/folder/save", "object", required_body=("parentId", "name", "parentVersion"), mutating=True),
    "folder_tags": Operation("GET", "/openapi/assets/folder/tag/list"),
    "folder_tree": Operation("GET", "/openapi/assets/folder/tree", response_kind="markdown"),
    "metadata_fields": Operation(
        "GET",
        "/openapi/assets/metadata/field/page",
        required_query=("page", "size"),
    ),
}


def _validate_library(payload: dict[str, Any]) -> None:
    operation = payload.get("operation")
    if not isinstance(operation, str):
        raise BasilError("operation must be a string")
    body = payload.get("body")
    query = payload.get("query") or {}
    if not isinstance(query, dict):
        raise BasilError("query must be a JSON object")
    space_type = query.get("spaceType")
    if space_type is not None and space_type not in ("MY", "TEAM", "SHARED"):
        raise BasilError("query.spaceType must be MY, TEAM, or SHARED")
    if operation in {"file_upload", "folder_tags", "folder_tree"}:
        validate_space_path(space_type, query.get("folderPath"), "query.folderPath")
    if operation == "folder_tree":
        folder_path = query.get("folderPath")
        if folder_path is not None and (not isinstance(folder_path, str) or not folder_path):
            raise BasilError("query.folderPath must be a non-empty string")
        if space_type == "SHARED" and (
            not isinstance(folder_path, str)
            or not folder_path.startswith("/Shared/")
            or len(folder_path.split("/")) < 3
            or not folder_path.split("/")[2]
        ):
            raise BasilError("SHARED requires folderPath /Shared/{grantId}[/relativePath]")
    if operation == "file_batch" and query.get("planType", "LITE") != "LITE":
        raise BasilError("file_batch supports only planType=LITE")
    if operation == "metadata_field_create":
        if query or payload.get("path"):
            raise BasilError("metadata_field_create accepts body parameters only")
        if not isinstance(body, dict):
            raise BasilError("body must be a JSON object")
        body = dict(body)
        unknown = sorted(set(body) - {"name", "description", "type", "planType", "groupId", "enumOptionList"})
        if unknown:
            raise BasilError(f"unsupported metadata_field_create body field(s): {', '.join(unknown)}")
        for key in ("name", "description"):
            if not isinstance(body.get(key), str) or not body[key].strip():
                raise BasilError(f"body.{key} must be a non-blank string")
        if body.get("type") not in ("SINGLE_SELECT", "MULTI_SELECT", "NOT_ENUM", "STRING", "TIME", "NUMBER"):
            raise BasilError("body.type must be SINGLE_SELECT, MULTI_SELECT, NOT_ENUM, STRING, TIME, or NUMBER")
        body.setdefault("planType", "PRO")
        if body["planType"] not in ("LITE", "PRO"):
            raise BasilError("body.planType must be LITE or PRO")
        if body["planType"] == "LITE" and body["type"] in ("STRING", "TIME", "NUMBER"):
            raise BasilError("LITE fields support only SINGLE_SELECT, MULTI_SELECT, or NOT_ENUM")
        body.setdefault("groupId", None)
        group_id = body["groupId"]
        if group_id is not None and not (
            isinstance(group_id, str) and group_id.isascii() and group_id.isdigit()
        ):
            raise BasilError("body.groupId must be a decimal ID string or null")
        if "enumOptionList" in body:
            options = body["enumOptionList"]
            if not isinstance(options, list):
                raise BasilError("body.enumOptionList must be an array")
            if body["type"] not in ("SINGLE_SELECT", "MULTI_SELECT") and options:
                raise BasilError("only selection fields save enum options; omit enumOptionList")
            seen = set()
            for option in options:
                if not isinstance(option, dict) or set(option) - {"value", "description"}:
                    raise BasilError("new enum options accept only value and description; do not supply IDs")
                value = option.get("value")
                if not isinstance(value, str) or not value.strip():
                    raise BasilError("enum option value must be a non-blank string")
                if value in seen:
                    raise BasilError("duplicate enum option value")
                seen.add(value)
                if "description" in option and not isinstance(option["description"], str):
                    raise BasilError("enum option description must be a string")
        payload["body"] = body
    if operation == "metadata_fields":
        allowed_query = {
            "name", "fieldType", "groupName", "ungrouped",
            "sortField", "sortDirection", "page", "size",
        }
        unknown_query = sorted(set(query) - allowed_query)
        if unknown_query:
            raise BasilError(f"unsupported metadata_fields query field(s): {', '.join(unknown_query)}")
        page = query.get("page")
        size = query.get("size")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            raise BasilError("query.page must be an integer greater than or equal to 1")
        if not isinstance(size, int) or isinstance(size, bool) or not 1 <= size <= 1000:
            raise BasilError("query.size must be an integer between 1 and 1000")
        if query.get("fieldType") is not None and query["fieldType"] not in (
            "SINGLE_SELECT", "MULTI_SELECT", "NOT_ENUM", "STRING", "TIME", "NUMBER"
        ):
            raise BasilError("query.fieldType is unsupported")
        if query.get("name") is not None and not isinstance(query["name"], str):
            raise BasilError("query.name must be a string")
        group_name = query.get("groupName")
        if group_name is not None:
            if not isinstance(group_name, str):
                raise BasilError("query.groupName must be a string")
            if len(group_name) > 100:
                raise BasilError("query.groupName must be at most 100 characters")
            if group_name.strip() and query.get("ungrouped") is True:
                raise BasilError("non-empty query.groupName and query.ungrouped=true are mutually exclusive")
        if query.get("ungrouped") is not None and not isinstance(query["ungrouped"], bool):
            raise BasilError("query.ungrouped must be boolean")
        if query.get("sortField") is not None and query["sortField"] not in (
            "name", "type", "createdAt", "updatedAt"
        ):
            raise BasilError("query.sortField is unsupported")
        if query.get("sortDirection") is not None and query["sortDirection"] not in ("ASC", "DESC"):
            raise BasilError("query.sortDirection must be ASC or DESC")
    if operation == "delete_batch" and isinstance(body, dict):
        if not body.get("fileItemList") and not body.get("folderItemList"):
            raise BasilError("delete_batch requires fileItemList or folderItemList")
    if operation == "file_metadata_operate" and isinstance(body, dict):
        if body.get("operationType") not in ("ADD", "UPDATE", "DELETE"):
            raise BasilError("operationType must be ADD, UPDATE, or DELETE")
        if body.get("fieldId") is None and not body.get("fieldName"):
            raise BasilError("file metadata operation requires fieldId or fieldName")
        if body.get("operationType") in {"ADD", "UPDATE"}:
            value = body.get("value")
            message = "body.value must be a string containing a JSON array; encode values with json.dumps(values)"
            if not isinstance(value, str):
                raise BasilError(message)
            try:
                decoded_value = json.loads(value)
            except ValueError:
                raise BasilError(message) from None
            if not isinstance(decoded_value, list):
                raise BasilError(message)
    if operation == "file_url_batch" and isinstance(body, list):
        if any(not isinstance(item, dict) or (item.get("id") is None and not item.get("path")) for item in body):
            raise BasilError("each file URL item requires id or path")
    if operation == "file_upload" and query.get("folderId") is None and not query.get("folderPath"):
        raise BasilError("file_upload requires query.folderId or query.folderPath")


def _multipart_file(path: Path) -> tuple[bytes, str]:
    if not path.is_file():
        raise BasilError("file_path must identify an existing regular file")
    boundary = "basil-cli-" + secrets.token_hex(16)
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    safe_name = path.name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    return prefix + path.read_bytes() + suffix, f"multipart/form-data; boundary={boundary}"


def _upload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"operation", "query", "file_path", "_timeout", "_confirm"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise BasilError(f"unsupported file_upload input field(s): {', '.join(unknown)}")
    if payload.get("_confirm") is not True:
        raise BasilError("file_upload requires _confirm=true after user confirmation")
    query = payload.get("query") or {}
    if not isinstance(query, dict):
        raise BasilError("query must be a JSON object")
    _validate_library(payload)
    file_path = payload.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        raise BasilError("file_upload requires file_path")
    body, content_type = _multipart_file(Path(file_path).expanduser())
    raw, _ = request(
        "POST",
        "/openapi/assets/file/upload",
        query=query,
        raw_body=body,
        content_type=content_type,
        timeout=payload.get("_timeout", DEFAULT_TIMEOUT),
    )
    return parse_success_response(raw)


def run_capability(allowed_operations: set[str] | None = None) -> None:
    payload = read_json_stdin()
    operation = payload.get("operation")
    if not isinstance(operation, str):
        raise BasilError("operation must be a string")
    if allowed_operations is not None and operation not in allowed_operations:
        raise BasilError("operation is not supported by this Library capability")
    if operation == "metadata_catalog":
        allowed = {"operation", "_timeout", "view"}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise BasilError(
                "metadata_catalog accepts only operation, _timeout and view; filters are forbidden"
            )
        view = payload.get("view", "full")
        if view not in ("full", "compact"):
            raise BasilError("metadata_catalog.view must be full or compact")
        fields = fetch_metadata_catalog(payload.get("_timeout", DEFAULT_TIMEOUT))
        addition = {"total": len(fields)}
        if view == "compact":
            addition["view"] = "compact"
            collisions = name_collisions(fields)
            if collisions:
                addition["nameCollisions"] = collisions
            print_json(
                {"success": True, "code": 0, "message": "success",
                 "data": compact_catalog(fields), "addition": addition},
                compact=True,
            )
        else:
            print_json({"success": True, "code": 0, "message": "success",
                        "data": fields, "addition": addition})
        return
    if payload.get("operation") == "file_upload":
        print_json(_upload(payload))
        return
    _validate_library(payload)
    view = "full"
    if operation == "metadata_fields" and "view" in payload:
        view = payload.pop("view")
        if view not in ("full", "compact"):
            raise BasilError("metadata_fields.view must be full or compact")
    if operation == "file_metadata_operate" and isinstance(payload.get("body"), dict):
        body = payload["body"]
        if body.get("fieldId") is None and body.get("fieldName"):
            # Resolve legacy name inputs through the same complete LITE catalog.
            # Never guess aliases or use a fuzzy match as a write target.
            if payload.get("_confirm") is not True:
                raise BasilError("write operation requires _confirm=true after user confirmation")
            if not body.get("fileId"):
                raise BasilError("missing required body field(s): fileId")
            fields = fetch_metadata_catalog(payload.get("_timeout", DEFAULT_TIMEOUT))
            matches = [item for item in fields if item.get("name") == body["fieldName"]]
            if len(matches) != 1:
                raise BasilError("Metadata field name must match exactly one visible LITE definition; inspect metadata_fields and resolve the intended field before writing")
            payload = {**payload, "body": {**body, "fieldId": str(matches[0]["id"])}}
            del payload["body"]["fieldName"]
    result, _ = execute_operation(payload, OPERATIONS)
    if operation == "metadata_field_create" and (
            not isinstance(result, dict) or result.get("data") is not True):
        # The save route returns a boolean, not an ID. success/code alone do not
        # prove the write; treat every other data value as an unverified outcome.
        raise BasilError(
            "metadata_field_create returned data!=true; outcome unverified, do not replay",
            next_action={"action": "verify field state through an applicable authoritative read before any retry; the OpenAPI field page is LITE-only"})
    if isinstance(result, str):
        print(result, end="" if result.endswith("\n") else "\n")
    elif view == "compact" and isinstance(result, dict) and isinstance(result.get("data"), list):
        addition = result.get("addition")
        projected = {**result, "data": compact_catalog(result["data"])}
        projected["addition"] = {
            **(addition if isinstance(addition, dict) else {}), "view": "compact",
        }
        print_json(projected, compact=True)
    else:
        print_json(result)


def main() -> None:
    # Search is deliberately absent from the generic operation catalog: only
    # structured_search.py applies the live Metadata validation boundary.
    run_capability(set(OPERATIONS) | {"metadata_catalog"})


if __name__ == "__main__":
    raise SystemExit(run_script(main))
