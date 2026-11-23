#!/usr/bin/env python3
"""Basil Base table-field capability."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from base.cli import run_capability
from runtime import run_script


OPERATIONS = {"field_create", "field_update", "field_list", "field_get", "field_delete"}


if __name__ == "__main__":
    raise SystemExit(run_script(lambda: run_capability(OPERATIONS)))
