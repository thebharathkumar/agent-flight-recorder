"""Example app: determinism, verifiable audit chain, classified failure variety."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "examples" / "two-agent-app" / "app.py"

sys.path.insert(0, str(ROOT / "skills" / "audit-log" / "scripts"))

from verify_chain import verify  # noqa: E402


def run_app(tmp_path, *args):
    # inherit the environment so pytest-cov's subprocess hook stays active
    env = {**os.environ, "AUDIT_CHAIN_KEY": "example-key"}
    return subprocess.run(
        [sys.executable, str(APP), *args],
        capture_output=True, text=True, cwd=tmp_path, env=env,
    )


def test_same_seed_is_deterministic(tmp_path):
    first = run_app(tmp_path, "--runs", "6", "--seed", "42")
    second = run_app(tmp_path, "--runs", "6", "--seed", "42")
    assert first.returncode == 0, first.stderr
    assert first.stdout == second.stdout
    assert "run-000" in first.stdout


def test_different_seed_differs(tmp_path):
    a = run_app(tmp_path, "--runs", "6", "--seed", "42")
    b = run_app(tmp_path, "--runs", "6", "--seed", "43")
    assert a.stdout != b.stdout


def test_audit_chains_verify(tmp_path):
    result = run_app(tmp_path, "--runs", "3", "--seed", "42", "--audit")
    assert result.returncode == 0, result.stderr
    logs = sorted((tmp_path / "audit").glob("*.jsonl"))
    assert len(logs) == 3
    for log in logs:
        ok, report = verify(log, key=b"example-key")
        assert ok, report


def test_failures_span_multiple_classifications(tmp_path):
    result = run_app(tmp_path, "--runs", "10", "--seed", "42")
    failures = [part for part in result.stdout.split() if "FAIL(" in part]
    classes = {part.split("FAIL(")[1].rstrip(")") for part in failures}
    assert len(classes) >= 2, f"only saw {classes}"


def test_run_query_entrypoint_is_deterministic(tmp_path):
    sys.path.insert(0, str(APP.parent))
    try:
        from app import run_query
    finally:
        sys.path.pop(0)
    a = run_query("what changed?", seed=7)
    b = run_query("what changed?", seed=7)
    assert a == b
    assert set(a) == {"plan", "answer"}


def test_main_inprocess_with_audit(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(APP.parent))
    try:
        import app
    finally:
        sys.path.pop(0)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUDIT_CHAIN_KEY", "example-key")
    monkeypatch.setattr(sys, "argv", ["app.py", "--runs", "4", "--seed", "1", "--audit"])
    assert app.main() == 0
    out = capsys.readouterr().out
    assert out.count("run-") == 4
    assert (tmp_path / "audit").exists()
    # the trace wrapper factory is importable without turning tracing on
    assert callable(app.make_wrapper(True)("planner"))


def test_trace_flag_writes_otlp_json(tmp_path):
    result = run_app(tmp_path, "--runs", "4", "--seed", "42", "--trace")
    assert result.returncode == 0, result.stderr
    capture = tmp_path / "captures" / "otlp.json"
    assert capture.exists()
    docs = [json.loads(line) for line in capture.read_text().splitlines() if line.strip()]
    assert docs and "resourceSpans" in docs[0]


def test_dev_key_warning_when_env_missing(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "AUDIT_CHAIN_KEY"}
    result = subprocess.run(
        [sys.executable, str(APP), "--runs", "1", "--audit"],
        capture_output=True, text=True, cwd=tmp_path, env=env,
    )
    assert result.returncode == 0
    assert "WARNING" in result.stderr
