#!/usr/bin/env python3
"""Bounded stdin entry point; no credential values in inputs or output."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import BasilError, print_json, read_json_stdin, run_script
from dataclasses import asdict
from auth.policy import oauth_decision

def main():
    payload = read_json_stdin()
    if set(payload) - {"state", "refresh_capability", "refresh_attempts", "reauth_attempts", "initial_card_attempts"}:
        raise BasilError("Unsupported recovery controls; do not pass credentials")
    if "state" not in payload or "refresh_capability" not in payload:
        raise BasilError("Recovery requires normalized state and verified host refresh capability")
    try:
        result = asdict(oauth_decision(**payload))
    except (ValueError, TypeError) as exc:
        raise BasilError("Invalid normalized recovery state or budget") from None
    result["dispatched"] = False
    print_json(result)

if __name__ == "__main__":
    raise SystemExit(run_script(main))
