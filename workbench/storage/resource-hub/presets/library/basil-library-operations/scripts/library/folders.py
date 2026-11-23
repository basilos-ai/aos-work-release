#!/usr/bin/env python3
"""Basil Library folder-management capability."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from library.cli import run_capability
from runtime import run_script


OPERATIONS = {"folder_create", "folder_rename", "folder_move", "folder_delete"}


if __name__ == "__main__":
    raise SystemExit(run_script(lambda: run_capability(OPERATIONS)))
