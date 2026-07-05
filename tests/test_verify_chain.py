"""Verifier attack suite, ported from claimtrace and extended with anchor and key checks."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "audit-log" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from chained_log import ChainedLogger, compute_hash  # noqa: E402
from verify_chain import verify  # noqa: E402

KEY = b"test-key"


@pytest.fixture()
def chain(tmp_path):
    path = tmp_path / "run.jsonl"
    logger = ChainedLogger(path, run_id="run", key=KEY)
    for i in range(5):
        logger.append(actor=f"agent{i % 2}", action="step", payload={"i": i})
    return path


def entries_of(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_entries(path, entries):
    path.write_text("".join(json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n"
                            for e in entries))


def test_intact_chain_passes(chain):
    ok, report = verify(chain, key=KEY)
    assert ok
    assert "5 entries" in report


def test_flipped_byte_detected_at_that_seq(chain):
    entries = entries_of(chain)
    entries[3]["payload"]["i"] = 999
    write_entries(chain, entries)
    ok, report = verify(chain, key=KEY)
    assert not ok
    assert "seq 3" in report


def test_recomputed_hash_detected_at_next_link(chain):
    entries = entries_of(chain)
    entries[3]["payload"]["i"] = 999
    body = {k: v for k, v in entries[3].items() if k != "entry_hash"}
    entries[3]["entry_hash"] = compute_hash(entries[3]["prev_hash"], body, KEY)
    write_entries(chain, entries)
    ok, report = verify(chain, key=KEY)
    assert not ok
    assert "seq 4" in report


def test_deleted_entry_detected(chain):
    entries = entries_of(chain)
    del entries[2]
    write_entries(chain, entries)
    ok, _ = verify(chain, key=KEY)
    assert not ok


def test_reordering_detected(chain):
    entries = entries_of(chain)
    entries[1], entries[2] = entries[2], entries[1]
    write_entries(chain, entries)
    ok, _ = verify(chain, key=KEY)
    assert not ok


def test_truncation_detected_via_anchor(chain):
    entries = entries_of(chain)
    write_entries(chain, entries[:-2])
    ok, report = verify(chain, key=KEY)
    assert not ok
    assert "anchor" in report.lower()


def test_wrong_key_fails(chain):
    ok, _ = verify(chain, key=b"not-the-key")
    assert not ok


def run_cli(args, env_key="test-key"):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_chain.py"), *map(str, args)],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "AUDIT_CHAIN_KEY": env_key},
    )


def test_cli_intact_exit_0(chain):
    result = run_cli([chain])
    assert result.returncode == 0, result.stderr


def test_cli_missing_anchor_warns_loudly_but_exits_0(chain):
    Path(str(chain) + ".head.json").unlink()
    result = run_cli([chain])
    assert result.returncode == 0
    assert "WARNING" in result.stderr
    assert "truncation" in result.stderr.lower()


def test_cli_require_anchor_exits_2_when_missing(chain):
    Path(str(chain) + ".head.json").unlink()
    result = run_cli([chain, "--require-anchor"])
    assert result.returncode == 2


def test_cli_anchor_mismatch_exits_2(chain):
    entries = entries_of(chain)
    write_entries(chain, entries[:-1])
    result = run_cli([chain])
    assert result.returncode == 2


def test_cli_broken_chain_exits_1(chain):
    entries = entries_of(chain)
    entries[0]["actor"] = "evil"
    write_entries(chain, entries)
    result = run_cli([chain])
    assert result.returncode == 1
    assert "seq 0" in result.stdout + result.stderr


def test_cli_demo_tamper_roundtrip(chain, tmp_path):
    copy = tmp_path / "copy.jsonl"
    shutil.copy(chain, copy)
    shutil.copy(str(chain) + ".head.json", str(copy) + ".head.json")
    result = run_cli([copy, "--demo-tamper"])
    assert result.returncode != 0
    assert "tamper" in (result.stdout + result.stderr).lower()
    # the original is untouched
    assert run_cli([chain]).returncode == 0
