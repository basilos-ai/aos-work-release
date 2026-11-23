"""Query normalization and exact result-view construction, without CLI dispatch."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from base.operations import OPERATIONS, RECORD_JSON_QUERY_FIELDS, _validate_base
from base.field_refs import normalize_field_refs
from runtime import BasilError
from runtime.openapi import execute_operation, integer_id, json_value

ALLOWED_FIELDS = {"operation", "query", "viewName", "_confirm", "_timeout"}
QUERY_FIELDS = {"tableId", "viewId", "ignoreViewQuery", "fieldKeyType", "cellFormat",
                "projection", "filter", "orderBy", "groupBy", "collapsedGroupIds",
                "search", "selectedRecordIds", "skip", "take"}


def _filter(value: Any, location: str = "query.filter") -> dict:
    """Validate ViewFilterVO structure without inventing an operator enum."""
    if not isinstance(value, dict):
        raise BasilError(f"{location}: must be an object")
    if set(value) - {"conjunction", "filterSet", "isSymbol", "fieldId", "operator", "value"}:
        raise BasilError(f"{location}: unsupported ViewFilterVO field")
    result = dict(value)
    if value.get("conjunction") is not None:
        conjunction = value["conjunction"]
        if not isinstance(conjunction, str) or conjunction.lower() not in {"and", "or"}:
            raise BasilError(f"{location}.conjunction: use and or or")
        result["conjunction"] = conjunction.lower()
    if value.get("filterSet") is not None:
        if not isinstance(value["filterSet"], list):
            raise BasilError(f"{location}.filterSet: must be an array")
        result["filterSet"] = [_filter(child, f"{location}.filterSet[{i}]")
                               for i, child in enumerate(value["filterSet"])]
    for key in ("fieldId", "operator"):
        if value.get(key) is not None and (not isinstance(value[key], str) or not value[key].strip()):
            raise BasilError(f"{location}.{key}: must be a non-empty string")
    if value.get("isSymbol") is not None and not isinstance(value["isSymbol"], bool):
        raise BasilError(f"{location}.isSymbol: must be boolean")
    return result


def _order(value: Any, location: str) -> list:
    if not isinstance(value, list):
        raise BasilError(f"{location}: must be an array of fieldId/order objects")
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) - {"fieldId", "order"}:
            raise BasilError(f"{location}: each item accepts fieldId and order")
        normalized = dict(item)
        if item.get("fieldId") is not None and (not isinstance(item["fieldId"], str) or not item["fieldId"].strip()):
            raise BasilError(f"{location}.fieldId: must be a resolved string ID")
        if item.get("order") is not None:
            if not isinstance(item["order"], str) or item["order"].lower() not in {"asc", "desc"}:
                raise BasilError(f"{location}.order: use asc or desc")
            normalized["order"] = item["order"].lower()
        result.append(normalized)
    return result


def _result_link(link: Any) -> tuple[str, str]:
    if not isinstance(link, str) or not link.strip():
        raise BasilError("view_create returned no snapshotLink")
    try:
        parsed = urlsplit(link)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None or "\\" in link or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in link):
            raise ValueError()
        # Accessing port validates malformed or out-of-range port values.
        parsed.port
    except ValueError:
        raise BasilError("view_create returned an invalid snapshotLink") from None
    # The provider's frontend is independent of the Workbench API entry point.
    # Preserve its complete URL without rewriting the origin or frontend route.
    return link, "returned_unverified"


def query_records(payload: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(payload) - ALLOWED_FIELDS)
    if unknown:
        raise BasilError(f"unsupported input field(s): {', '.join(unknown)}")
    if payload.get("operation") != "record_query_snapshot":
        raise BasilError("operation must be record_query_snapshot")
    if "_confirm" in payload and not isinstance(payload["_confirm"], bool):
        raise BasilError("_confirm must be boolean when provided")
    query = payload.get("query")
    if not isinstance(query, dict):
        raise BasilError("query must be a JSON object")
    unsupported = sorted(set(query) - QUERY_FIELDS)
    if unsupported:
        raise BasilError("unsupported query field(s): " + ", ".join(unsupported))
    query = {"skip": 0, "take": 100, **{key: val for key, val in query.items() if val is not None}}
    query["tableId"] = integer_id(query.get("tableId"), "query.tableId")
    if "viewId" in query:
        query["viewId"] = integer_id(query["viewId"], "query.viewId")
    for key in RECORD_JSON_QUERY_FIELDS:
        if key in query:
            query[key] = json_value(query[key], f"query.{key}")
    if "filter" in query:
        try:
            query["filter"] = _filter(query["filter"])
        except RecursionError:
            raise BasilError("query.filter nesting exceeds the supported recursion limit") from None
    for key in ("orderBy", "groupBy"):
        if key in query:
            query[key] = _order(query[key], f"query.{key}")
    for key in ("projection", "selectedRecordIds", "collapsedGroupIds"):
        if key in query and (not isinstance(query[key], list) or any(not isinstance(v, str) for v in query[key])):
            raise BasilError(f"query.{key}: must be an array of strings")
    if "search" in query and not isinstance(query["search"], str):
        raise BasilError("query.search must be a string")
    if "ignoreViewQuery" in query and not isinstance(query["ignoreViewQuery"], bool):
        raise BasilError("query.ignoreViewQuery must be boolean")
    for key, choices in (("fieldKeyType", {"ID", "NAME", "DB_FIELD_NAME"}), ("cellFormat", {"TEXT", "JSON"})):
        if key in query and (not isinstance(query[key], str) or query[key] not in choices):
            raise BasilError(f"query.{key}: unsupported value")
    name = payload.get("viewName", "Query results " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    if not isinstance(name, str) or not name.strip():
        raise BasilError("viewName must be a non-empty string")
    query_payload = {"operation": "record_query", "query": query}
    if "_timeout" in payload:
        query_payload["_timeout"] = payload["_timeout"]
    _validate_base(query_payload)
    normalize_field_refs(query, payload.get("_timeout"))
    response, _ = execute_operation(query_payload, OPERATIONS)
    data = response.get("data")
    if (not isinstance(data, dict) or not isinstance(data.get("recordList"), list)
            or any(not isinstance(row, dict) for row in data["recordList"])):
        raise BasilError("queryRecord returned an invalid recordList; no view was created")
    result = {**response, "data": dict(data), "workflow": {
        "queryStatus": "succeeded", "viewStatus": "not_created_empty_page",
        "effectiveQuery": query, "viewScope": "all_matching_records",
        "recordScope": {"skip": query["skip"], "take": query["take"]},
    }}
    # Never inherit an unrelated query-level link.
    result["data"].pop("snapshotLink", None)
    if not data["recordList"]:
        return result
    # Query-only scope has no documented ViewSaveVO mapping. Return its rows,
    # not a view with silently broadened conditions. Never fabricate snapshotQuery.
    unmapped = [key for key in ("projection", "search", "selectedRecordIds", "collapsedGroupIds") if query.get(key)]
    if "viewId" in query and not query.get("ignoreViewQuery", False):
        unmapped.append("viewId")
    if unmapped:
        result["workflow"].update(viewStatus="not_created_unsupported_scope", viewScope=None,
                                  unsupportedViewFields=unmapped, retryAllowed=False)
        return result
    result["workflow"]["viewStatus"] = "pending"
    return result


def result_view_name(result: dict[str, Any], name: str) -> str:
    """Assign once; readable labels need not be unique across user queries."""
    workflow = result["workflow"]
    if "viewName" not in workflow:
        workflow["viewName"] = name.strip()[:80] + " - " + uuid4().hex
    return workflow["viewName"]


def create_result_view(result: dict[str, Any], name: str, timeout=None) -> dict[str, Any]:
    """Create from the exact successful query; never query records here."""
    if result["workflow"]["viewStatus"] != "pending":
        return result
    query = result["workflow"]["effectiveQuery"]
    body = {"tableId": query["tableId"], "name": result_view_name(result, name), "type": "GRID", "display": False}
    if "filter" in query:
        body["filter"] = query["filter"]
    if "orderBy" in query:
        body["sort"] = {"sortObjs": query["orderBy"], "manualSort": False}
    if "groupBy" in query:
        body["groupMeta"] = query["groupBy"]
    create = {"operation": "view_create", "body": body, "_confirm": True}
    if timeout is not None:
        create["_timeout"] = timeout
    try:
        _validate_base(create)
        view, _ = execute_operation(create, OPERATIONS)
    except BasilError as exc:
        result["workflow"].update(viewStatus="failed_or_unknown", failedStage="view_create", error=str(exc), retryAllowed=False)
        return result
    result["workflow"]["viewStatus"] = "created"
    view_data = view.get("data")
    if isinstance(view_data, dict) and view_data.get("id") is not None:
        result["workflow"]["viewId"] = view_data["id"]
    link = view_data.get("snapshotLink") if isinstance(view_data, dict) else None
    try:
        corrected, status = _result_link(link)
    except BasilError as exc:
        result["workflow"].update(linkStatus="unavailable", failedStage="result_link", error=str(exc), retryAllowed=False)
        return result
    result["data"]["snapshotLink"] = corrected
    result["workflow"].update(linkStatus=status, originalSnapshotLink=link, browserVerified=False, retryAllowed=False)
    return result
