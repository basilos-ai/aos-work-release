#!/usr/bin/env python3
"""Compatibility entrypoint; new Agents use records.py followed by views.py."""
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import print_json, read_json_stdin, run_script
from base.query_workflow import (
    ALLOWED_FIELDS, QUERY_FIELDS, _filter, _order, _result_link,
    query_records, result_view_name, create_result_view,
)


def execute(payload: dict[str, Any]) -> dict[str, Any]:
    """Legacy adapter; new callers use records.py then views.py."""
    result = query_records(payload)
    name = payload.get("viewName", "Query results " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    return create_result_view(result, name, payload.get("_timeout"))


def main() -> None:
    # Preserve old entrypoints without exposing unbounded record output.
    from base.query_results import save_result, summary
    result = execute(read_json_stdin())
    print_json(summary(result, save_result(result), delivery=True))


if __name__ == "__main__":
    raise SystemExit(run_script(main))
