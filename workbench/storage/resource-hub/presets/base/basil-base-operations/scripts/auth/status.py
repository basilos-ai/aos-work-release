#!/usr/bin/env python3
"""Report non-secret availability of Workbench-managed credentials."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import BasilError, authorization_status, print_json, read_json_stdin, run_script


def main() -> None:
    if read_json_stdin():
        raise BasilError("status accepts only _runtimeDomain and optional _authMode controls")
    print_json(authorization_status())


if __name__ == "__main__":
    raise SystemExit(run_script(main))
