#!/usr/bin/env python3
"""Basil Library search and asset-detail capability."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from library.cli import run_capability
from runtime import run_script


OPERATIONS = {"metadata_catalog", "metadata_fields", "file_batch"}


if __name__ == "__main__":
    raise SystemExit(run_script(lambda: run_capability(OPERATIONS)))
