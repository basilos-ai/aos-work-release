#!/usr/bin/env python3
"""Execute a whitelisted Basil Base/Table OpenAPI operation."""

from __future__ import annotations

import mimetypes
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import (BasilError, DEFAULT_TIMEOUT, parse_success_response,
                     print_json, read_json_stdin, request, run_script)
from runtime.openapi import Operation, execute_operation, integer_id
# Re-export existing imports for callers of the original dispatcher module.
from base.operations import (OPERATIONS, RECORD_JSON_QUERY_FIELDS, FIELD_TYPES,
                             VIEW_TYPES, FIELD_KEY_TYPES, _validate_base,
                             _validate_batch_create, _validate_page)


ATTACHMENT_ID_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase
ATTACHMENT_PATH_PREFIX = "multi-dim-table/attachments/"
MAX_ATTACHMENT_CHUNKS = 10000
MAX_ATTACHMENT_CHUNK_SIZE = 64 * 1024 * 1024


def _multipart_chunk(file_name: str, mimetype: str, content: bytes) -> tuple[bytes, str]:
    boundary = "basil-base-" + secrets.token_hex(16)
    safe_name = file_name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
        f"Content-Type: {mimetype}\r\n\r\n"
    ).encode("utf-8")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    return prefix + content + suffix, f"multipart/form-data; boundary={boundary}"


def _response_data(result: dict, stage: str) -> dict:
    data = result.get("data")
    if not isinstance(data, dict):
        raise BasilError(f"attachment {stage} response requires an object data field")
    return data


def _upload_attachment(payload: dict) -> dict:
    allowed = {"operation", "baseId", "file_path", "_timeout", "_confirm"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise BasilError(f"unsupported record_attachment_upload input field(s): {', '.join(unknown)}")
    if payload.get("_confirm") is not True:
        raise BasilError("record_attachment_upload requires _confirm=true after user confirmation")
    base_id = integer_id(payload.get("baseId"), "baseId")
    file_path = payload.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        raise BasilError("record_attachment_upload requires file_path")
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise BasilError("file_path must identify an existing regular file")
    file_size = path.stat().st_size
    if file_size <= 0:
        raise BasilError("attachment file must not be empty")
    mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    timeout = payload.get("_timeout", DEFAULT_TIMEOUT)

    raw, _ = request(
        "POST",
        "/record/uploadAttachment/init",
        query={"baseId": base_id, "fileName": path.name, "mimetype": mimetype, "size": file_size},
        timeout=timeout,
    )
    session = _response_data(parse_success_response(raw), "init")
    token = session.get("token")
    object_path = session.get("path")
    upload_id = session.get("uploadId")
    chunk_size = session.get("chunkSize")
    total_chunks = session.get("totalChunks")
    if not isinstance(token, str) or not token.isdecimal():
        raise BasilError("attachment init response contains an invalid token")
    expected_prefix = f"{ATTACHMENT_PATH_PREFIX}{base_id}/"
    object_name = object_path.rsplit("/", 1)[-1] if isinstance(object_path, str) else ""
    if not isinstance(object_path, str) or not object_path.startswith(expected_prefix) or object_name.split(".", 1)[0] != token:
        raise BasilError("attachment init response contains an invalid path")
    if not isinstance(upload_id, str) or not upload_id:
        raise BasilError("attachment init response contains an invalid uploadId")
    complete_started = False
    try:
        if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or not 1 <= chunk_size <= MAX_ATTACHMENT_CHUNK_SIZE:
            raise BasilError("attachment init response contains an invalid chunkSize")
        expected_chunks = (file_size - 1) // chunk_size + 1
        if (
            not isinstance(total_chunks, int)
            or isinstance(total_chunks, bool)
            or not 1 <= total_chunks <= MAX_ATTACHMENT_CHUNKS
            or total_chunks != expected_chunks
        ):
            raise BasilError("attachment init response contains an invalid totalChunks")
        uploaded_size = 0
        with path.open("rb") as file:
            for part_number in range(1, total_chunks + 1):
                content = file.read(chunk_size)
                if not content:
                    raise BasilError("attachment file changed during upload")
                uploaded_size += len(content)
                body, content_type = _multipart_chunk(path.name, mimetype, content)
                chunk_raw, _ = request(
                    "POST",
                    f"/record/uploadAttachment/{token}/chunk/{part_number}",
                    query={"baseId": base_id, "path": object_path, "uploadId": upload_id},
                    raw_body=body,
                    content_type=content_type,
                    timeout=timeout,
                )
                parse_success_response(chunk_raw)
            if uploaded_size != file_size or file.read(1):
                raise BasilError("attachment file changed during upload")

        complete_started = True
        complete_raw, _ = request(
            "POST",
            f"/record/uploadAttachment/{token}/complete",
            query={
                "baseId": base_id,
                "path": object_path,
                "uploadId": upload_id,
                "mimetype": mimetype,
            },
            timeout=timeout,
        )
        result = parse_success_response(complete_raw)
        attachment = _response_data(result, "complete")
        response_size = attachment.get("size")
        if isinstance(response_size, str) and response_size.isascii() and response_size.isdecimal():
            response_size = int(response_size)
        if (
            attachment.get("token") != token
            or attachment.get("path") != object_path
            or isinstance(response_size, bool)
            or not isinstance(response_size, int)
            or response_size != file_size
            or not isinstance(attachment.get("mimetype"), str)
        ):
            raise BasilError("attachment complete response does not match the uploaded file")
        attachment["size"] = response_size
        for transient_key in ("url", "uploadId", "chunkSize", "totalChunks"):
            attachment.pop(transient_key, None)
        attachment["id"] = "act" + "".join(secrets.choice(ATTACHMENT_ID_ALPHABET) for _ in range(16))
        attachment["name"] = path.name
        result["data"] = attachment
        return result
    except (BasilError, OSError):
        if not complete_started:
            try:
                abort_raw, _ = request(
                    "DELETE",
                    f"/record/uploadAttachment/{token}",
                    query={"baseId": base_id, "path": object_path, "uploadId": upload_id},
                    timeout=timeout,
                )
                parse_success_response(abort_raw)
            except (BasilError, OSError):
                pass
        raise


def run_capability(allowed_operations: set[str] | None = None) -> None:
    if len(sys.argv) > 1:
        raise BasilError("pass one JSON object on standard input, not as a command-line argument")
    payload = read_json_stdin()
    operation = payload.get("operation")
    if not isinstance(operation, str):
        raise BasilError("operation must be a string")
    if allowed_operations is not None and operation not in allowed_operations:
        raise BasilError("operation is not supported by this Base capability")
    if operation in {"record_query", "view_create_query_result"}:
        from base.query_results import query, create
        print_json(query(payload) if operation == "record_query" else create(payload))
        return
    if operation == "record_attachment_upload":
        print_json(_upload_attachment(payload))
        return
    _validate_base(payload)
    result, _ = execute_operation(payload, OPERATIONS)
    print_json(result)


def main() -> None:
    run_capability(set(OPERATIONS) | {"view_create_query_result", "record_attachment_upload"})


if __name__ == "__main__":
    raise SystemExit(run_script(main))
