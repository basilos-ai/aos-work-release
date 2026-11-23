#!/usr/bin/env python3
"""Basil Library recursive folder-tree capability."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from library.cli import OPERATIONS, _validate_library
from runtime import BasilError, print_json, read_json_stdin, run_script
from runtime.openapi import execute_operation


OPERATIONS_ALLOWED = {"folder_tree"}


def main() -> None:
    payload = read_json_stdin()
    # Preserve the earlier wrapper shape while preferring the standard module
    # envelope for all new calls.
    if "operation" not in payload:
        query = {key: value for key, value in payload.items() if key != "_timeout"}
        payload = {"operation": "folder_tree", "query": query, **(
            {"_timeout": payload["_timeout"]} if "_timeout" in payload else {}
        )}
    if payload.get("operation") not in OPERATIONS_ALLOWED:
        raise BasilError("operation must be folder_tree")
    _validate_library(payload)
    result, _ = execute_operation(payload, OPERATIONS)
    if isinstance(result, str):
        print(result, end="" if result.endswith("\n") else "\n")
    else:
        print_json(result)


if __name__ == "__main__":
    raise SystemExit(run_script(main))
