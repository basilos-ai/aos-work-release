#!/usr/bin/env python3
"""Bounded stdin entry point; no credential values in inputs or output."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import BasilError, print_json, read_json_stdin, run_script
from runtime import status

def main():
    if read_json_stdin():
        raise BasilError("status accepts only _runtimeDomain and _authMode controls")
    print_json(status())

if __name__ == "__main__":
    raise SystemExit(run_script(main))
