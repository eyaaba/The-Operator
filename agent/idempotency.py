"""
Idempotency key = SHA-256 of (tool name + canonical JSON of its arguments).

Before a write runs, the tool looks this key up in the `idempotency_keys` table.
If it is there, the stored result is returned with idempotent_replay=True and
nothing is written again. That is what "running the same call twice does not do
the thing twice" means in the brief.
"""

import hashlib
import json
from typing import Any


def idempotency_key(tool_name: str, args: dict[str, Any]) -> str:
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{tool_name}|{canonical}".encode("utf-8")).hexdigest()
