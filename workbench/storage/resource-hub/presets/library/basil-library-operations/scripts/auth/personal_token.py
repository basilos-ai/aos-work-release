#!/usr/bin/env python3
"""Emit the fixed Workbench password form after OAuth2 is unavailable."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import BasilError, personal_token_action, print_json, read_json_stdin, run_script


def main():
    if read_json_stdin(helper=True):
        raise BasilError("personal_token accepts only {}; submit secrets through the Workbench password form")
    print_json({"next_action": personal_token_action()})


if __name__ == "__main__":
    raise SystemExit(run_script(main))
