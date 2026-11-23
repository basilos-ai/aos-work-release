"""Documented operation registry; shared by validation and the transport allowlist."""
import json
import re
from pathlib import Path

CONTRACT = json.loads(Path(__file__).with_name("contracts.json").read_text(encoding="utf-8"))
OPERATIONS = CONTRACT["operations"]
MODELS = CONTRACT["models"]
SYSTEM_PERMISSIONS = set(CONTRACT["system_permission_ids"])


def endpoint_allowed(method, endpoint):
    if not isinstance(endpoint, str):
        return False
    for op in OPERATIONS.values():
        if op.get("unsupported") or method != op["method"]:
            continue
        pattern = re.escape(op["endpoint"])
        pattern = re.sub(r"\\\{\w+\\\}", r"[0-9]+", pattern)
        if re.fullmatch(pattern, endpoint):
            return True
    return False
