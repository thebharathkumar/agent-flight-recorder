"""Repo-wide hygiene: no em dashes anywhere, no stale project names."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=ROOT, check=True
    ).stdout
    paths = [ROOT / line for line in out.splitlines() if (ROOT / line).is_file()]
    # text files only: binary blobs (the demo gif) can alias any byte sequence
    return [p for p in paths if b"\x00" not in p.read_bytes()[:1024]]


EM_DASH = "\u2014"
# built dynamically so this file does not flag itself
STALE_NAMES = ["agent" + "-ops", "agent" + "-receipts"]
# design history legitimately discusses the naming decision
HISTORY = Path("docs/superpowers")


def test_no_em_dashes_anywhere():
    offenders = []
    for path in tracked_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if EM_DASH in text:
            line = next(
                i for i, ln in enumerate(text.splitlines(), 1) if EM_DASH in ln
            )
            offenders.append(f"{path.relative_to(ROOT)}:{line}")
    assert not offenders, f"em dashes found in: {offenders}"


def test_no_stale_project_names():
    offenders = []
    for path in tracked_files():
        if HISTORY in path.relative_to(ROOT).parents:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(name in text for name in STALE_NAMES):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"stale project names in: {offenders}"
