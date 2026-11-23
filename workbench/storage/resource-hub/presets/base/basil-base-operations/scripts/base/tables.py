#!/usr/bin/env python3
"""Basil Base data-table capability."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from base.cli import run_capability
from runtime import run_script


OPERATIONS = {"table_create", "table_update", "table_list", "table_get", "table_delete"}


if __name__ == "__main__":
    raise SystemExit(run_script(lambda: run_capability(OPERATIONS)))
