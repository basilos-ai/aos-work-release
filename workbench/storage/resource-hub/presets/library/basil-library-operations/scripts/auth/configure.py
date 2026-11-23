#!/usr/bin/env python3
"""Retired local credential entry point; authorization is managed by Workbench."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import BasilError, REAUTHORIZE, run_script


def configure_authorization(_payload: dict) -> dict:
    raise BasilError("此 App 已停用本地登录和凭证配置；个人令牌仅通过 Workbench 安全表单收取。" + REAUTHORIZE)


def main() -> None:
    # Deliberately do not consume stdin: it may contain legacy secrets.
    configure_authorization({})


if __name__ == "__main__":
    raise SystemExit(run_script(main))
