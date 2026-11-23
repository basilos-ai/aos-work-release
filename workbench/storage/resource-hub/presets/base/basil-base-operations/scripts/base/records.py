#!/usr/bin/env python3
"""Basil Base table-record capability."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from base.cli import run_capability
from runtime import run_script


OPERATIONS = {
    "record_query", "record_get", "record_aggregate", "record_enum_values",
    "record_create", "record_batch_create", "record_update", "record_batch_update",
    "record_delete", "record_batch_delete", "record_attachment_upload",
}


if __name__ == "__main__":
    raise SystemExit(run_script(lambda: run_capability(OPERATIONS)))
