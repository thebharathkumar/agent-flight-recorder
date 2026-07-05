"""Tamper-evident, hash-chained HMAC audit logger. Stdlib only, drop into any project.

Chain spec:
    entry_hash = HMAC_SHA256(key, prev_hash + canonical_json(body))
where body is the full entry minus entry_hash, canonical JSON uses sorted keys and
compact separators, and the genesis prev_hash is 64 zeros. Every append rewrites a
<log>.head.json anchor ({"count": N, "head_hash": ...}) so truncation from the tail
is detectable by verify_chain.py. Store that anchor (or just its head_hash) somewhere
writers of the log cannot touch to get full truncation protection.

Key comes from the AUDIT_CHAIN_KEY environment variable. The built-in dev key is for
local experiments only and triggers a loud warning.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64
DEV_KEY = b"flight-recorder-dev-key"
DEV_KEY_WARNING = (
    "WARNING: AUDIT_CHAIN_KEY is not set; using the built-in dev key.\n"
    "WARNING: anyone can forge a chain signed with the dev key. Set a real secret."
)


def canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str, body: dict, key: bytes) -> str:
    message = (prev_hash + canonical(body)).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def load_key(env_var: str = "AUDIT_CHAIN_KEY") -> bytes:
    value = os.environ.get(env_var)
    if value:
        return value.encode("utf-8")
    print(DEV_KEY_WARNING, file=sys.stderr)
    return DEV_KEY


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class ChainedLogger:
    """Append-only JSONL audit log, one chain per file, head anchor on by default."""

    def __init__(self, path: str | Path, run_id: str, key: bytes | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.key = key if key is not None else load_key()
        self._seq, self._prev_hash = self._resume()

    def _resume(self) -> tuple[int, str]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return 0, GENESIS
        last = None
        count = 0
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = line
                    count += 1
        if last is None:
            return 0, GENESIS
        return count, json.loads(last)["entry_hash"]

    @property
    def anchor_path(self) -> Path:
        return Path(str(self.path) + ".head.json")

    def append(self, actor: str, action: str, payload: dict) -> dict:
        body = {
            "seq": self._seq,
            "ts": _now_iso(),
            "run_id": self.run_id,
            "actor": actor,
            "action": action,
            "payload": payload,
            "prev_hash": self._prev_hash,
        }
        entry = dict(body, entry_hash=compute_hash(self._prev_hash, body, self.key))
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(canonical(entry) + "\n")
        self._seq += 1
        self._prev_hash = entry["entry_hash"]
        self.anchor_path.write_text(
            json.dumps({"count": self._seq, "head_hash": self._prev_hash}) + "\n"
        )
        return entry
