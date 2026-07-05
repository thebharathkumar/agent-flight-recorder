"""Chained audit logger: chaining, coverage of metadata, resume, anchor, key handling."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "audit-log" / "scripts"))

import chained_log  # noqa: E402
from chained_log import GENESIS, ChainedLogger, canonical, compute_hash  # noqa: E402

KEY = b"test-key"


@pytest.fixture()
def log(tmp_path):
    path = tmp_path / "run1.jsonl"
    return ChainedLogger(path, run_id="run1", key=KEY), path


def read_entries(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_entries_chain_from_genesis(log):
    logger, path = log
    logger.append(actor="planner", action="plan_created", payload={"steps": 2})
    logger.append(actor="worker", action="tool_called", payload={"tool": "search"})
    entries = read_entries(path)
    assert entries[0]["prev_hash"] == GENESIS
    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]
    assert entries[0]["seq"] == 0 and entries[1]["seq"] == 1


def test_hash_covers_all_metadata(log):
    """Mutating seq, ts, run_id, actor, or action invalidates the entry hash."""
    logger, path = log
    entry = logger.append(actor="a", action="act", payload={"x": 1})
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    assert compute_hash(entry["prev_hash"], body, KEY) == entry["entry_hash"]
    for field, bogus in [("seq", 99), ("ts", "1999-01-01T00:00:00Z"), ("run_id", "other"),
                         ("actor", "evil"), ("action", "changed")]:
        tampered = dict(body, **{field: bogus})
        assert compute_hash(entry["prev_hash"], tampered, KEY) != entry["entry_hash"]


def test_resume_continues_chain(tmp_path):
    path = tmp_path / "r.jsonl"
    ChainedLogger(path, run_id="r", key=KEY).append(actor="a", action="one", payload={})
    ChainedLogger(path, run_id="r", key=KEY).append(actor="a", action="two", payload={})
    entries = read_entries(path)
    assert len(entries) == 2
    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]
    assert entries[1]["seq"] == 1


def test_head_anchor_written_by_default(log):
    logger, path = log
    logger.append(actor="a", action="one", payload={})
    last = logger.append(actor="a", action="two", payload={})
    anchor = json.loads(Path(str(path) + ".head.json").read_text())
    assert anchor == {"count": 2, "head_hash": last["entry_hash"]}


def test_dev_key_warns(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("AUDIT_CHAIN_KEY", raising=False)
    key = chained_log.load_key()
    assert key == chained_log.DEV_KEY
    assert "WARNING" in capsys.readouterr().err


def test_env_key_no_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AUDIT_CHAIN_KEY", "real-secret")
    assert chained_log.load_key() == b"real-secret"
    assert capsys.readouterr().err == ""


def test_canonical_is_deterministic():
    assert canonical({"b": 1, "a": {"y": 2, "x": None}}) == canonical({"a": {"x": None, "y": 2}, "b": 1})
