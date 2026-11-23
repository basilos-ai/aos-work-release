"""Whitelist-driven Basil OpenAPI operation execution."""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime import BasilError, DEFAULT_TIMEOUT, parse_success_response, request


@dataclass(frozen=True)
class Operation:
    method: str
    endpoint: str
    body_kind: str = "none"
    required_path: tuple[str, ...] = ()
    required_query: tuple[str, ...] = ()
    required_body: tuple[str, ...] = ()
    query_defaults: Mapping[str, Any] = field(default_factory=dict)
    response_kind: str = "json"
    mutating: bool = False
    destructive: bool = False


def _object(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise BasilError(f"{name} must be a JSON object")
    return dict(value)


def _required(container: Mapping[str, Any], fields: tuple[str, ...], location: str) -> None:
    missing = [name for name in fields if name not in container or container[name] is None]
    if missing:
        raise BasilError(f"missing required {location} field(s): {', '.join(missing)}")


def execute_operation(
    payload: dict[str, Any],
    catalog: Mapping[str, Operation],
) -> tuple[Any, str]:
    allowed = {"operation", "path", "query", "body", "_timeout", "_confirm", "_target"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise BasilError(f"unsupported input field(s): {', '.join(unknown)}")
    name = payload.get("operation")
    if not isinstance(name, str) or name not in catalog:
        raise BasilError("operation must name a supported module operation")
    operation = catalog[name]
    path = _object(payload.get("path"), "path")
    query = {**operation.query_defaults, **_object(payload.get("query"), "query")}
    _required(path, operation.required_path, "path")
    _required(query, operation.required_query, "query")

    if operation.body_kind == "none":
        if payload.get("body") is not None:
            raise BasilError(f"{name} does not accept a request body")
        body = None
    elif operation.body_kind == "object":
        body = _object(payload.get("body"), "body")
        _required(body, operation.required_body, "body")
    elif operation.body_kind == "list":
        body = payload.get("body")
        if not isinstance(body, list) or not body:
            raise BasilError("body must be a non-empty JSON array")
    else:
        raise BasilError(f"invalid operation catalog body kind: {operation.body_kind}")

    if operation.mutating and payload.get("_confirm") is not True:
        raise BasilError("write operation requires _confirm=true after user confirmation")
    if operation.destructive:
        target = payload.get("_target")
        if not isinstance(target, str) or not target.strip():
            raise BasilError("destructive operation requires a non-empty _target description")

    endpoint = operation.endpoint
    for key in operation.required_path:
        endpoint = endpoint.replace("{" + key + "}", urllib.parse.quote(str(path[key]), safe=""))
    timeout = payload.get("_timeout", DEFAULT_TIMEOUT)
    raw, content_type = request(
        operation.method,
        endpoint,
        query=query,
        body=body,
        timeout=timeout,
    )
    if operation.response_kind == "markdown":
        return raw, content_type
    return parse_success_response(raw), content_type
