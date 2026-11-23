#!/usr/bin/env python3
"""Host function-call adapter: emit an intermediate plan, without API validation.

Script Agents may pass the same Plan directly to structured_search.py; the CLI
applies the same defaults and validation, so this adapter is optional outside a
host that binds it as a function call.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import BasilError, print_json, read_json_stdin, run_script


def build_structured_search(**arguments):
    # Host-side int64 precision guard. Full condition validation stays in
    # plan_to_body; this adapter must not duplicate API validation.
    conditions = arguments.get("metadataConditions", [])
    if isinstance(conditions, list):
        for condition in conditions:
            if isinstance(condition, dict) and "fieldId" in condition and not isinstance(
                condition["fieldId"], str
            ):
                raise BasilError("Search Plan fieldId must be a decimal string from /field/page")
    # Defaults keep a host-bound Plan complete. The CLI re-applies them in
    # plan_to_body, which remains the single API conversion/validation boundary;
    # original expressions stay intact for agent-directed repair.
    return {"keyword": "", "metadataLogic": "AND", "metadataConditions": [], **arguments}


def main():
    print_json(build_structured_search(**read_json_stdin(helper=True)))


if __name__ == "__main__":
    raise SystemExit(run_script(main))
