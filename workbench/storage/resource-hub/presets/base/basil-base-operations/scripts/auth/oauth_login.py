#!/usr/bin/env python3
"""Retired local credential entry point; authorization is managed by Workbench."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import BasilError, REAUTHORIZE, run_script


def oauth_login(_payload: dict) -> dict:
    raise BasilError("Local login and credential configuration are disabled for this App; personal tokens are collected only through the Workbench secure form. " + REAUTHORIZE)


def main() -> None:
    # Deliberately do not consume stdin: it may contain legacy secrets.
    oauth_login({})


if __name__ == "__main__":
    raise SystemExit(run_script(main))
