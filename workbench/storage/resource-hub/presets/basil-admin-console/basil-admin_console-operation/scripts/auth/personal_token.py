#!/usr/bin/env python3
"""Bounded stdin entry point; no credential values in inputs or output."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import BasilError, print_json, read_json_stdin, run_script
from runtime import personal_token_action

def main():
    payload = read_json_stdin()
    if set(payload) - {"explicit_request", "replacement", "replacement_attempts"}:
        raise BasilError("Only non-secret form controls are accepted")
    print_json({"next_action": personal_token_action(**payload)})

if __name__ == "__main__":
    raise SystemExit(run_script(main))
