"""LITE request validation and intermediate-plan conversion (no semantic inference)."""

from copy import deepcopy

from library.metadata_catalog import metadata_id
from runtime import BasilError

FILE_TYPES = {"ALL", "IMAGE", "VIDEO", "DOC", "FOLDER"}
API_FIELDS = {
    "enableAI", "keyword", "spaceType", "folderIdList",
    "folderPath", "includeSubfolders", "tagLogicType", "tagConditionList",
    "filterConditionList", "fileTypeFilter", "sortRule", "page", "size",
}


def file_id_string(value):
    """Validate a lossless FILE_ID filter value and canonicalize its digits."""
    if not isinstance(value, str):
        raise BasilError("FILE_ID values must be decimal strings")
    try:
        return str(metadata_id(value))
    except BasilError:
        raise BasilError("FILE_ID must be a non-negative signed int64 decimal string") from None


def normalize_search(body):
    """Omit empty optional fields without hiding unknown fields or bad conditions."""
    if not isinstance(body, dict):
        raise BasilError("body must be a JSON object")
    body = deepcopy(body)
    for key in API_FIELDS - {"enableAI"}:
        if key in body and body[key] is None:
            del body[key]
    for key in ("keyword", "folderPath"):
        if isinstance(body.get(key), str) and not body[key].strip():
            del body[key]
    if "spaceType" in body and body["spaceType"] not in ("MY", "TEAM", "SHARED"):
        del body["spaceType"]
    for key in ("folderIdList", "tagConditionList", "filterConditionList", "fileTypeFilter"):
        if body.get(key) == []:
            del body[key]
    if body.get("sortRule") in ({}, {"previewableTypeOrder": []}):
        del body["sortRule"]
    if "tagConditionList" not in body and body.get("tagLogicType") in ("AND", "OR"):
        del body["tagLogicType"]
    filters = body.get("filterConditionList")
    if isinstance(filters, list):
        for condition in filters:
            if isinstance(condition, dict) and condition.get("fieldType") == "FILE_ID" and isinstance(condition.get("value"), list):
                # Preserve input order and never mutate the caller's plan/body.
                condition["value"] = list(dict.fromkeys(file_id_string(v) for v in condition["value"]))
    return body


def strings(value, name, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value) or any(
        not isinstance(v, str) or not v.strip() for v in value
    ):
        raise BasilError(f"{name} must be an array of non-empty strings")
    return value


def validate_space_path(space_type, folder_path, field="folderPath"):
    if folder_path is None:
        return
    if not isinstance(folder_path, str) or not folder_path.startswith("/") or folder_path == "/":
        raise BasilError(f"{field} must be an absolute Library path")
    parts = folder_path.strip("/").split("/")
    if any(p in {"", ".", ".."} for p in parts):
        raise BasilError(f"{field} contains an invalid path segment")
    if parts[0] in {"Shared", "User"} and len(parts) < 2:
        raise BasilError(f"{field} requires a grantId or current username")
    if space_type == "TEAM" and parts[0] != "Root":
        raise BasilError(f"TEAM {field} must start with /Root")
    if space_type == "SHARED" and parts[0] != "Shared":
        raise BasilError(f"SHARED {field} must start with /Shared/{{grantId}}")
    if space_type == "MY" and parts[0] in {"Root", "Shared"}:
        raise BasilError(f"MY {field} must identify the current user's personal path")


def validate_search(body):
    if not isinstance(body, dict):
        raise BasilError("body must be a JSON object")
    unknown = sorted(set(body) - API_FIELDS)
    if unknown:
        raise BasilError(f"unsupported LITE structured-search field(s): {', '.join(unknown)}")
    for key in ("enableAI", "includeSubfolders"):
        if key in body and type(body[key]) is not bool:
            raise BasilError(f"{key} must be boolean")
    if body.get("enableAI", False):
        raise BasilError("LITE structured search requires enableAI=false")
    if "keyword" in body and not isinstance(body["keyword"], str):
        raise BasilError("keyword must be a string")
    if "spaceType" in body and body["spaceType"] not in ("MY", "TEAM", "SHARED"):
        raise BasilError("spaceType must be MY, TEAM, or SHARED")
    validate_space_path(body.get("spaceType"), body.get("folderPath"))
    if "folderPath" in body and "folderIdList" in body:
        raise BasilError("folderPath and folderIdList are mutually exclusive")
    if "folderPath" in body and body["folderPath"] is None:
        raise BasilError("folderPath must be a path")
    if body.get("includeSubfolders") and not body.get("folderPath"):
        raise BasilError("includeSubfolders=true requires folderPath")
    if "folderIdList" in body:
        ids = body["folderIdList"]
        if not isinstance(ids, list) or any(type(i) is not int or i < 0 for i in ids):
            raise BasilError("folderIdList must be an integer array")
    for key, default, maximum in (("page", 1, None), ("size", 50, 1000)):
        value = body.get(key, default)
        if type(value) is not int or value < 1 or (maximum and value > maximum):
            raise BasilError(f"{key} must be a positive integer" + (" <= 1000" if maximum else ""))
    types = strings(body.get("fileTypeFilter", []), "fileTypeFilter", False)
    if any(t not in FILE_TYPES for t in types) or ("FOLDER" in types and len(types) > 1):
        raise BasilError("unsupported fileTypeFilter combination")
    if "sortRule" in body:
        rule = body["sortRule"]
        if not isinstance(rule, dict) or set(rule) - {"previewableTypeOrder"}:
            raise BasilError("unsupported sortRule")
        order = strings(rule.get("previewableTypeOrder", []), "previewableTypeOrder", False)
        if any(t not in {"IMAGE", "VIDEO", "DOC"} for t in order):
            raise BasilError("unsupported previewableTypeOrder")
    conditions = body.get("tagConditionList", [])
    if not isinstance(conditions, list):
        raise BasilError("tagConditionList must be an array")
    if body.get("tagLogicType", "AND") not in ("AND", "OR"):
        raise BasilError("tagLogicType must be AND or OR")
    if "tagLogicType" in body and not conditions:
        raise BasilError("tagLogicType requires tagConditionList")
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) != {"fieldId", "value"}:
            raise BasilError("each tag condition requires only fieldId and value")
        metadata_id(condition["fieldId"])
        values = condition["value"]
        if not isinstance(values, list) or not values:
            raise BasilError("tag condition value must be a non-empty array")
        for value in values:
            if isinstance(value, str):
                strings([value], "tag condition value")
            else:
                metadata_id(value)
    filters = body.get("filterConditionList", [])
    if not isinstance(filters, list):
        raise BasilError("filterConditionList must be an array")
    for condition in filters:
        if not isinstance(condition, dict) or set(condition) != {"fieldType", "operator", "value"}:
            raise BasilError("each filter requires fieldType, operator, value")
        field_type = condition["fieldType"]
        op = condition["operator"]
        values = strings(condition["value"], "filter value")
        if field_type in ("CREATED_AT", "UPDATED_AT", "FILE_SIZE"):
            if op not in ("GT", "LT", "BETWEEN"):
                raise BasilError("LITE range filter operator must be GT, LT, BETWEEN")
            if len(values) != (2 if op == "BETWEEN" else 1):
                raise BasilError("filter value count does not match operator")
        elif field_type in ("MIME_SUB_TYPE", "DOC_SUB_TYPE"):
            if op not in ("EQUALS", "NOT_EQUALS", "IN", "NOT_IN"):
                raise BasilError("LITE subtype filter operator must be EQUALS, NOT_EQUALS, IN, NOT_IN")
            if op in ("EQUALS", "NOT_EQUALS") and len(values) != 1:
                raise BasilError("subtype equality requires exactly one value")
        elif field_type == "FILE_ID":
            if op != "IN":
                raise BasilError("FILE_ID supports only IN with a non-empty ID list")
            for value in values:
                file_id_string(value)
            if types == ["FOLDER"]:
                raise BasilError("FILE_ID cannot be combined with FOLDER-only search")
        else:
            raise BasilError("LITE filters support CREATED_AT, UPDATED_AT, FILE_SIZE, MIME_SUB_TYPE, DOC_SUB_TYPE, FILE_ID; use metadataConditions for Metadata")


def plan_to_body(plan):
    if not isinstance(plan, dict):
        raise BasilError("plan must be the build_structured_search JSON object")
    allowed = {"keyword", "metadataLogic", "metadataConditions", "spaceType", "folderPath",
               "includeSubfolders", "fileTypeFilter", "filterConditions", "page", "size", "sortRule"}
    if set(plan) - allowed:
        raise BasilError("unsupported intermediate plan field(s): " + ", ".join(sorted(set(plan) - allowed)))
    logic = plan.get("metadataLogic", "AND")
    if logic not in ("AND", "OR"):
        raise BasilError("metadataLogic must be AND or OR")
    body = {"enableAI": False}
    for key in allowed - {"metadataLogic", "metadataConditions", "filterConditions"}:
        if key in plan:
            body[key] = plan[key]
    conditions = plan.get("metadataConditions", [])
    if not isinstance(conditions, list):
        raise BasilError("metadataConditions must be an array")
    tags = []
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) != {"fieldId", "value", "sourceText"}:
            raise BasilError("each metadata condition requires fieldId, value, sourceText")
        if not isinstance(condition["sourceText"], str) or not condition["sourceText"].strip():
            raise BasilError("sourceText must contain the original user expression")
        if not isinstance(condition["fieldId"], str):
            raise BasilError("Search Plan fieldId must be a decimal string from /field/page")
        strings(condition["value"], "Search Plan metadata value")
        tags.append({"fieldId": condition["fieldId"], "value": condition["value"]})
    if tags:
        body.update(tagLogicType=logic, tagConditionList=tags)
    if "filterConditions" in plan:
        body["filterConditionList"] = plan["filterConditions"]
    body = normalize_search(body)
    validate_search(body)
    return body


def validate_metadata(body, catalog):
    """Resolve enum labels to option IDs; validate direct integer IDs in body too."""
    fields = {metadata_id(f["id"]): f for f in catalog}
    for condition in body.get("tagConditionList", []):
        key = metadata_id(condition["fieldId"])
        if key not in fields:
            raise BasilError(f"Metadata fieldId {key} not in current catalog; review mapping and restore sourceText to keyword")
        field = fields[key]
        kind = field.get("type")
        if kind in ("SINGLE_SELECT", "MULTI_SELECT"):
            options = field.get("enumOptionList")
            if not isinstance(options, list) or any(
                not isinstance(o, dict) or "id" not in o or not isinstance(o.get("value"), str)
                for o in options
            ):
                raise BasilError(f"Metadata field {key} has invalid enumOptionList")
            by_value, ids = {}, set()
            for option in options:
                option_id = metadata_id(option["id"])
                if option_id in ids or ("fieldId" in option and metadata_id(option["fieldId"]) != key):
                    raise BasilError(f"Metadata field {key} has inconsistent enumOptionList IDs")
                ids.add(option_id)
                by_value.setdefault(option["value"], []).append(option_id)
            resolved = []
            for value in condition["value"]:
                # Numeric-looking strings are still labels, never guessed IDs.
                matches = by_value.get(value, []) if isinstance(value, str) else [metadata_id(value)]
                if len(matches) != 1 or matches[0] not in ids:
                    raise BasilError(f"Metadata field {key} value must identify one current enum option; review sourceText")
                resolved.append(matches[0])
            condition["value"] = resolved
        elif kind in ("NOT_ENUM", "NUMBER", "STRING", "TIME"):
            strings(condition["value"], "non-enum Metadata value")
            if kind != "NOT_ENUM" and len(condition["value"]) != 1:
                raise BasilError(f"Scalar Metadata field {key} requires exactly one value")
        else:
            raise BasilError(f"Metadata field {key} has an unsupported type")
        # Python integers and json.dumps preserve int64 digits on the API wire.
        # The source plan remains a string and is never mutated.
        condition["fieldId"] = key
