"""Verify the integrity of a hash-chained audit log produced by chained_log.py.

Usage:
    python verify_chain.py <log.jsonl> [--key-env AUDIT_CHAIN_KEY] [--require-anchor]
                           [--demo-tamper]

Exit codes:
    0  chain intact (a missing anchor still prints a loud warning, never silent)
    1  chain broken (line-numbered diagnosis printed)
    2  anchor mismatch, or --require-anchor with no anchor file

--demo-tamper flips one byte in the middle entry of the given file IN PLACE (run it
on a copy) and then verifies, demonstrating detection.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from chained_log import GENESIS, compute_hash, load_key

MISSING_ANCHOR_WARNING = (
    "=" * 68 + "\n"
    "WARNING: no head anchor file found ({anchor}).\n"
    "WARNING: the chain is internally consistent, but truncation from the\n"
    "WARNING: tail CANNOT be ruled out without an anchor. Rerun with\n"
    "WARNING: --require-anchor to make this a hard failure.\n" + "=" * 68
)


def verify(path: str | Path, key: bytes, require_anchor: bool = False) -> tuple[bool, str]:
    """Recompute every hash and check the head anchor. Returns (ok, report)."""
    path = Path(path)
    if not path.exists():
        return False, f"log file not found: {path}"

    prev = GENESIS
    count = 0
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        entry = json.loads(line)
        seq = entry.get("seq")
        if entry.get("prev_hash") != prev:
            return False, (
                f"BROKEN at line {lineno} (seq {seq}): prev_hash mismatch "
                f"(expected {prev[:8]}.., got {str(entry.get('prev_hash'))[:8]}..)"
            )
        body = {k: v for k, v in entry.items() if k != "entry_hash"}
        expected = compute_hash(prev, body, key)
        if expected != entry.get("entry_hash"):
            return False, (
                f"BROKEN at line {lineno} (seq {seq}): entry_hash mismatch "
                f"(recomputed {expected[:8]}.., stored {str(entry.get('entry_hash'))[:8]}..)"
            )
        prev = entry["entry_hash"]
        count += 1

    anchor_path = Path(str(path) + ".head.json")
    if not anchor_path.exists():
        if require_anchor:
            return False, "anchor required but no anchor file found"
        print(MISSING_ANCHOR_WARNING.format(anchor=anchor_path), file=sys.stderr)
        return True, f"chain ok: {count} entries verified (no anchor, see warning)"

    anchor = json.loads(anchor_path.read_text())
    if anchor.get("count") != count or anchor.get("head_hash") != prev:
        return False, (
            f"ANCHOR MISMATCH: anchor says {anchor.get('count')} entries ending "
            f"{str(anchor.get('head_hash'))[:8]}.., log has {count} entries ending "
            f"{prev[:8]}.. (possible truncation)"
        )
    return True, f"chain ok: {count} entries verified, anchor matches"


def demo_tamper(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    mid = len(lines) // 2
    entry = json.loads(lines[mid])
    entry["payload"] = {"tampered": True, "original": entry.get("payload")}
    lines[mid] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n")
    print(f"demo: flipped payload of seq {entry.get('seq')} in {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--key-env", default="AUDIT_CHAIN_KEY")
    parser.add_argument("--require-anchor", action="store_true")
    parser.add_argument("--demo-tamper", action="store_true",
                        help="tamper with the file in place, then verify (use a copy)")
    args = parser.parse_args()

    if args.demo_tamper:
        demo_tamper(args.log)

    key = load_key(args.key_env)
    ok, report = verify(args.log, key=key, require_anchor=args.require_anchor)
    print(report)
    if ok:
        return 0
    lowered = report.lower()
    return 2 if ("anchor" in lowered) else 1


if __name__ == "__main__":
    sys.exit(main())
