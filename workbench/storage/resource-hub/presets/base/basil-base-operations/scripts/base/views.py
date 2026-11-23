#!/usr/bin/env python3
"""Basil Base table-view capability."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from base.cli import run_capability
from runtime import run_script


OPERATIONS = {"view_create_query_result", "view_create", "view_update", "view_list", "view_get", "view_delete"}


if __name__ == "__main__":
    raise SystemExit(run_script(lambda: run_capability(OPERATIONS)))
