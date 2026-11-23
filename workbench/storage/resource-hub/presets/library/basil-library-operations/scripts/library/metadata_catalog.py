"""Fetch a complete, current-user LITE catalog; never cache across identities."""

from runtime import BasilError, DEFAULT_TIMEOUT, parse_success_response, request


def metadata_id(value):
    if isinstance(value, bool) or not (
        isinstance(value, int) and value >= 0
        or isinstance(value, str) and value.isascii() and value.isdigit()
    ):
        raise BasilError("Metadata ID must be a non-negative integer ID")
    # Bound before parsing, including arbitrarily long or zero-padded input.
    digits = str(value).lstrip("0") or "0"
    if len(digits) > 19 or (len(digits) == 19 and digits > "9223372036854775807"):
        raise BasilError("Metadata ID must fit a non-negative signed 64-bit integer")
    return int(digits)


def _page_rows(raw, page, size, expected_total):
    """Validate one field-page response without trusting its declared totals."""
    response = parse_success_response(raw)
    rows, addition = response.get("data"), response.get("addition")
    if not isinstance(rows, list) or not isinstance(addition, dict):
        raise BasilError("Metadata catalog requires data array and addition pagination")
    total, actual_page, actual_size = (addition.get(k) for k in ("total", "page", "size"))
    if any(type(v) is not int for v in (total, actual_page, actual_size)) or (
        total < 0 or actual_page != page or not 1 <= actual_size <= 1000
    ):
        raise BasilError("Invalid Metadata pagination; reload the catalog")
    if expected_total is not None and (total != expected_total or actual_size != size):
        raise BasilError("Metadata pagination changed; reload the catalog")
    if len(rows) > actual_size:
        raise BasilError("Metadata page exceeds its declared size")
    return rows, total, actual_size


def fetch_metadata_catalog(timeout=DEFAULT_TIMEOUT):
    fields, seen = [], set()
    page, size, expected_total = 1, 1000, None
    while True:
        raw, _ = request(
            "GET", "/openapi/assets/metadata/field/page",
            query={"page": page, "size": size}, timeout=timeout,
        )
        rows, total, actual_size = _page_rows(raw, page, size, expected_total)
        expected_total, size = total, actual_size
        for row in rows:
            if not isinstance(row, dict) or "id" not in row:
                raise BasilError("Invalid Metadata field in catalog")
            key = metadata_id(row["id"])
            if key in seen:
                raise BasilError("Duplicate Metadata ID across pages; reload the catalog")
            seen.add(key)
            fields.append(row)
        if len(fields) == total:
            return fields
        if len(fields) > total or len(rows) != size:
            raise BasilError("Incomplete Metadata pagination; reload the catalog")
        page += 1


def _compact_option(option):
    item = {}
    if option.get("id") is not None:
        item["id"] = str(option["id"])
    if isinstance(option.get("value"), str):
        item["value"] = option["value"]
    if isinstance(option.get("description"), str) and option["description"].strip():
        item["description"] = option["description"]
    return item


def compact_catalog(fields):
    """Project a catalog to the fields needed to map and write Metadata.

    Audit, ordering and duplicated foreign keys are omitted; field IDs, group
    information, option IDs, exact labels and descriptions are preserved so
    the result is information-complete for search mapping and Metadata writes.
    """
    compact = []
    for field in fields:
        if not isinstance(field, dict):
            raise BasilError("Invalid Metadata field in catalog")
        item = {}
        for key in ("id", "name", "type"):
            if key in field:
                value = field[key]
                if key == "id" and isinstance(value, int) and not isinstance(value, bool):
                    value = str(value)
                item[key] = value
        for key in ("description", "groupName"):
            value = field.get(key)
            if isinstance(value, str) and value.strip():
                item[key] = value
        if field.get("groupId") is not None:
            item["groupId"] = field["groupId"]
        options = field.get("enumOptionList")
        if isinstance(options, list):
            projected = []
            for option in options:
                if not isinstance(option, dict):
                    raise BasilError("Invalid Metadata field in catalog")
                projected.append(_compact_option(option))
            item["enumOptionList"] = projected
        compact.append(item)
    return compact


def name_collisions(fields):
    """Return case-insensitive duplicate names so ambiguity is visible in data."""
    groups = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = field.get("name")
        if isinstance(name, str) and name.strip():
            groups.setdefault(name.strip().casefold(), []).append(name)
    return [names for names in groups.values() if len(names) > 1]
