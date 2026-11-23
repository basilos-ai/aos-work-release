"""Base operation contracts and deterministic capability validation."""

from typing import Any

from runtime import BasilError
from runtime.openapi import Operation


RECORD_JSON_QUERY_FIELDS = ("filter", "orderBy", "groupBy", "collapsedGroupIds")


OPERATIONS = {
    "base_create": Operation("POST", "/openapi/base", "object", required_body=("name",), mutating=True),
    "base_update": Operation("PUT", "/openapi/base", "object", required_body=("id", "name"), mutating=True, integer_body_fields=('id',)),
    "base_list": Operation("GET", "/openapi/base/page", query_defaults={"page": 0, "size": 10}),
    "base_delete": Operation("DELETE", "/openapi/base/{id}", required_path=("id",), mutating=True, destructive=True),
    "base_get": Operation("GET", "/openapi/base/{id}", required_path=("id",)),
    "table_create": Operation("POST", "/openapi/tableMeta", "object", required_body=("baseId", "name"), mutating=True, integer_body_fields=('baseId',)),
    "table_update": Operation("PUT", "/openapi/tableMeta", "object", required_body=("id", "baseId", "name", "dbTableName"), mutating=True, integer_body_fields=('id', 'baseId')),
    "table_list": Operation("GET", "/openapi/tableMeta/page", required_query=("baseId",), query_defaults={"page": 0, "size": 10}),
    "table_delete": Operation("DELETE", "/openapi/tableMeta/{id}", required_path=("id",), mutating=True, destructive=True),
    "table_get": Operation("GET", "/openapi/tableMeta/{id}", required_path=("id",)),
    "field_create": Operation("POST", "/openapi/field", "object", required_body=("name", "type", "tableId"), mutating=True, integer_body_fields=('tableId',)),
    "field_update": Operation("PUT", "/openapi/field", "object", required_body=("id", "name", "type", "dbFieldName", "tableId"), mutating=True, integer_body_fields=('id', 'tableId')),
    "field_list": Operation("GET", "/openapi/field/page", required_query=("tableId",), query_defaults={"page": 0, "size": 10}),
    "field_delete": Operation("DELETE", "/openapi/field/{id}", required_path=("id",), mutating=True, destructive=True),
    "field_get": Operation("GET", "/openapi/field/{id}", required_path=("id",)),
    "view_create": Operation("POST", "/openapi/view", "object", required_body=("tableId", "type"), mutating=True, integer_body_fields=('tableId', 'shareId')),
    "view_update": Operation("PUT", "/openapi/view", "object", required_body=("id", "tableId"), mutating=True, integer_body_fields=('id', 'tableId', 'shareId')),
    "view_delete": Operation("DELETE", "/openapi/view/delete", required_query=("id", "tableId"), mutating=True, destructive=True),
    "view_list": Operation("GET", "/openapi/view/page", required_query=("tableId",), query_defaults={"page": 0, "size": 10}),
    "view_get": Operation("GET", "/openapi/view/read", required_query=("id", "tableId")),
    "record_aggregate": Operation("GET", "/openapi/record/aggregation", required_query=("tableId",), json_query_fields=RECORD_JSON_QUERY_FIELDS + ("aggregations",), integer_query_fields=("tableId", "viewId")),
    "record_batch_create": Operation("POST", "/openapi/record/batchSaveRecordList", "object", required_body=("tableId", "fieldKeyType", "records"), mutating=True, integer_body_fields=('tableId',)),
    "record_batch_update": Operation("PUT", "/openapi/record/batchUpdateRecordList", "object", required_body=("tableId", "records"), mutating=True, integer_body_fields=('tableId',)),
    "record_delete": Operation("DELETE", "/openapi/record/deleteRecord", required_query=("tableId", "recordId"), mutating=True, destructive=True),
    "record_batch_delete": Operation("DELETE", "/openapi/record/deleteRecordList", "object", required_body=("tableId", "recordIds"), mutating=True, destructive=True, integer_body_fields=('tableId',)),
    "record_enum_values": Operation("GET", "/openapi/record/fieldEnumValueList", required_query=("tableId", "fieldId"), query_defaults={"limit": 50}),
    "record_query": Operation("GET", "/openapi/record/queryRecord", required_query=("tableId",), query_defaults={"skip": 0, "take": 10}, json_query_fields=RECORD_JSON_QUERY_FIELDS, integer_query_fields=("tableId", "viewId")),
    "record_get": Operation("GET", "/openapi/record/readRecord", required_query=("tableId", "recordId")),
    "record_create": Operation("POST", "/openapi/record/saveRecord", "object", mutating=True, integer_body_fields=('tableId',)),
    "record_update": Operation("PUT", "/openapi/record/updateRecord", "object", required_body=("tableId", "recordId", "fields"), mutating=True, integer_body_fields=('tableId',)),
}


FIELD_TYPES = {
    "SINGLE_LINE_TEXT", "LONG_TEXT", "NUMBER", "CHECKBOX", "SINGLE_SELECT",
    "MULTIPLE_SELECT", "DATE", "RATING", "ATTACHMENT", "USER", "ASSETS_FILE",
}
VIEW_TYPES = {"GRID", "ASSETS_GRID", "KANBAN", "GALLERY", "CALENDAR", "FORM"}
FIELD_KEY_TYPES = {"ID", "NAME", "DB_FIELD_NAME"}


def _validate_batch_create(body: Any) -> None:
    if not isinstance(body, dict):
        raise BasilError("body must be a JSON object")
    records = body.get("records")
    if not isinstance(records, list) or not records:
        raise BasilError("body.records must be a non-empty array")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise BasilError(f"body.records[{index}] must be a JSON object")
    location_hint = (
        'Set body.fieldKeyType alongside body.tableId and body.records: '
        'ID (field IDs), NAME (field names), or DB_FIELD_NAME (database column names). '
        'The API defaults to NAME; field ID keys require explicit body.fieldKeyType="ID". '
        'The batch-level value overrides record-level fieldKeyType.'
    )
    if body.get("fieldKeyType") is None:
        nested = next((i for i, record in enumerate(records) if "fieldKeyType" in record), None)
        detail = (
            f"body.records[{nested}].fieldKeyType cannot select the batch key type. "
            if nested is not None else ""
        )
        raise BasilError(f"body.fieldKeyType is required for batch creation. {detail}{location_hint}")
    key_type = body["fieldKeyType"]
    if not isinstance(key_type, str) or key_type not in FIELD_KEY_TYPES:
        raise BasilError(f"Invalid body.fieldKeyType. {location_hint}")
    for index, record in enumerate(records):
        if "fieldKeyType" in record and record["fieldKeyType"] != key_type:
            raise BasilError(
                f"body.records[{index}].fieldKeyType conflicts with body.fieldKeyType. "
                f"Remove the record-level setting and use one key type for all records. {location_hint}"
            )


def _validate_page(query: dict[str, Any]) -> None:
    if "page" in query and (not isinstance(query["page"], int) or isinstance(query["page"], bool) or query["page"] < 0):
        raise BasilError("page must be an integer greater than or equal to 0")
    if "size" in query and (not isinstance(query["size"], int) or isinstance(query["size"], bool) or not 1 <= query["size"] <= 1000):
        raise BasilError("size must be an integer between 1 and 1000")


def _validate_base(payload: dict[str, Any]) -> None:
    operation = payload.get("operation")
    if not isinstance(operation, str):
        raise BasilError("operation must be a string")
    query = payload.get("query") or {}
    body = payload.get("body") or {}
    if not isinstance(query, dict):
        raise BasilError("query must be a JSON object")
    if operation in {"base_list", "table_list", "field_list", "view_list"}:
        _validate_page(query)
    if operation == "record_query":
        take = query.get("take", 10)
        skip = query.get("skip", 0)
        if not isinstance(skip, int) or isinstance(skip, bool) or skip < 0:
            raise BasilError("skip must be an integer greater than or equal to 0")
        if not isinstance(take, int) or isinstance(take, bool) or not 1 <= take <= 1000:
            raise BasilError("take must be an integer between 1 and 1000")
    if operation == "record_enum_values":
        limit = query.get("limit", 50)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise BasilError("limit must be an integer between 1 and 1000")
    if operation in {"field_create", "field_update"} and isinstance(body, dict):
        if not isinstance(body.get("type"), str) or body["type"] not in FIELD_TYPES:
            raise BasilError("field type is unsupported")
    if operation in {"view_create", "view_update"} and isinstance(body, dict) and body.get("type") is not None:
        if not isinstance(body["type"], str) or body["type"] not in VIEW_TYPES:
            raise BasilError("view type is unsupported")
    if operation == "record_batch_create":
        _validate_batch_create(body)
    if isinstance(body, dict) and body.get("fieldKeyType") is not None and (
        not isinstance(body["fieldKeyType"], str) or body["fieldKeyType"] not in FIELD_KEY_TYPES
    ):
        raise BasilError("fieldKeyType must be ID, NAME, or DB_FIELD_NAME")
    if operation == "record_batch_update" and isinstance(body, dict):
        records = body.get("records")
        if not isinstance(records, list) or not records:
            raise BasilError("records must be a non-empty array")
        for index, record in enumerate(records):
            if not isinstance(record, dict) or record.get("recordId") is None or not isinstance(record.get("fields"), dict):
                raise BasilError(f"records[{index}] requires recordId and a fields object")
    if operation == "record_batch_delete" and isinstance(body, dict):
        ids = body.get("recordIds")
        if not isinstance(ids, list) or not ids:
            raise BasilError("recordIds must be a non-empty array")
