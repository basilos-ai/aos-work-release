#!/usr/bin/env python3
"""Search Library assets and return the query-level snapshot link for hits."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import (
    BasilError,
    DEFAULT_TIMEOUT,
    parse_success_response,
    print_json,
    read_json_stdin,
    request,
    run_script,
)

from library.metadata_catalog import fetch_metadata_catalog, metadata_id
from library.search_validation import normalize_search, validate_search, plan_to_body, validate_metadata

ALLOWED_FIELDS = {"operation", "plan", "body", "_timeout", "inspectResults", "inspectPages"}
MAX_INSPECT_PAGES = 20


def search_assets_structured(body: dict, timeout: float = DEFAULT_TIMEOUT, *, inspect_pages=None) -> dict:
    if inspect_pages is not None and (type(inspect_pages) is not int or not 1 <= inspect_pages <= MAX_INSPECT_PAGES):
        raise BasilError(f"inspectPages must be an integer from 1 through {MAX_INSPECT_PAGES}")
    body = normalize_search(body)
    validate_search(body)
    catalog = fetch_metadata_catalog(timeout=timeout)
    validate_metadata(body, catalog)
    body["enableAI"] = False
    body.setdefault("page", 1)
    body.setdefault("size", 50)
    if body.get("tagConditionList"):
        body.setdefault("tagLogicType", "AND")
    validate_search(body)
    if inspect_pages is not None:
        return _inspect_pages(body, timeout, inspect_pages)
    return _request_page(body, timeout)


def _request_page(body, timeout):
    raw, _ = request(
        "POST",
        "/openapi/assets/search/structured",
        query={"planType": "LITE"},
        body=body,
        timeout=timeout,
    )
    return parse_success_response(raw)


def _inspect_pages(body, timeout, limit):
    """Read a bounded batch with one live catalog validation; no relevance inference."""
    pages, seen = [], set()
    start = body["page"]
    for page in range(start, start + limit):
        response = _request_page({**body, "page": page}, timeout)
        data = response.get("data")
        info = data.get("pageInfo") if isinstance(data, dict) else None
        if not isinstance(info, dict) or type(info.get("hasMore")) is not bool:
            raise BasilError("Candidate inspection requires pageInfo.hasMore; completeness is unknown")
        if not any(key in data for key in ("fileList", "folderList")):
            raise BasilError("Candidate inspection requires fileList or folderList")
        current = set()
        for key in ("fileList", "folderList"):
            rows = data.get(key, [])
            if not isinstance(rows, list):
                raise BasilError(f"Candidate inspection requires an array for {key}")
            for row in rows:
                if not isinstance(row, dict) or "id" not in row:
                    raise BasilError(f"Candidate inspection requires real IDs in {key}")
                current.add((key, metadata_id(row["id"])))
        if (current and not current - seen) or (info["hasMore"] and not current):
            raise BasilError("Candidate pagination made no progress; do not finalize partial results")
        seen.update(current)
        # Keep each server response, including its own link and pagination.
        pages.append({"page": page, "response": response})
        if not info["hasMore"]:
            break
    return {
        "success": True,
        "code": 0,
        "data": {
            "pages": pages,
            "nextPage": page + 1 if info["hasMore"] else None,
            # Reaching the end from page > 1 alone does not prove full coverage.
            "complete": start == 1 and not info["hasMore"],
        },
    }


def _snapshot_result(response: dict) -> dict:
    data = response.get("data")
    if not isinstance(data, dict):
        return response
    file_list = data.get("fileList")
    if not isinstance(file_list, list) or not file_list:
        return response
    link = data.get("snapshotLink")
    if not isinstance(link, str) or not link.strip():
        return response
    return {
        "success": True,
        "code": 0,
        "message": "success",
        "data": {"snapshotLink": link.strip()},
        "addition": None,
    }


def execute(payload: dict) -> dict:
    unknown = sorted(set(payload) - ALLOWED_FIELDS)
    if unknown:
        raise BasilError(f"unsupported input field(s): {', '.join(unknown)}")
    if payload.get("operation") != "structured_search":
        raise BasilError("operation must be structured_search")
    if ("plan" in payload) == ("body" in payload):
        raise BasilError("provide exactly one of plan (Agent) or body (legacy API caller)")
    inspect = payload.get("inspectResults", False)
    if type(inspect) is not bool:
        raise BasilError("inspectResults must be boolean")
    if "inspectPages" in payload:
        count = payload["inspectPages"]
        if not inspect or type(count) is not int or not 1 <= count <= MAX_INSPECT_PAGES:
            raise BasilError(f"inspectPages requires inspectResults=true and an integer from 1 through {MAX_INSPECT_PAGES}")
    body = plan_to_body(payload["plan"]) if "plan" in payload else payload["body"]
    if not isinstance(body, dict):
        raise BasilError("body must be a JSON object")
    timeout = payload.get("_timeout", DEFAULT_TIMEOUT)
    if "inspectPages" in payload:
        return search_assets_structured(body, timeout=timeout, inspect_pages=payload["inspectPages"])
    response = search_assets_structured(body, timeout=timeout)
    # The agent can inspect hits before deciding whether to repair a mapping;
    # default callers retain the existing snapshot-link-only output contract.
    return response if inspect else _snapshot_result(response)


def main() -> None:
    print_json(execute(read_json_stdin()))


if __name__ == "__main__":
    raise SystemExit(run_script(main))
