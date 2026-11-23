#!/usr/bin/env python3
"""Basil Base database capability."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from base.cli import run_capability
from runtime import run_script


OPERATIONS = {"base_create", "base_update", "base_list", "base_get", "base_delete"}


if __name__ == "__main__":
    raise SystemExit(run_script(lambda: run_capability(OPERATIONS)))
