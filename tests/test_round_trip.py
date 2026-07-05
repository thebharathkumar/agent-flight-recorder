"""Amendment 3 gate: the pack's skills compose with no docker.

Traced example app (SDK file exporter) -> otlp_to_triage.py with the DEFAULT
mapping -> triage report --top 5 -> golden comparison.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "examples" / "two-agent-app" / "app.py"
CONVERTER = ROOT / "skills" / "trace-triage" / "scripts" / "otlp_to_triage.py"
GOLDEN = ROOT / "tests" / "golden" / "round_trip_report.md"
ENV = {"PATH": "/usr/bin:/bin", "AUDIT_CHAIN_KEY": "round-trip-key"}


def normalize(report: str) -> str:
    """Drop the wall-clock header line; normalize punctuation that agent-triage
    puts in its canned prose so the committed golden stays free of em dashes."""
    lines = [line for line in report.splitlines() if not line.startswith("Generated:")]
    return "\n".join(lines).replace("\u2014", "-") + "\n"


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("roundtrip")
    run = subprocess.run(
        [sys.executable, str(APP), "--runs", "10", "--seed", "42", "--trace"],
        capture_output=True, text=True, cwd=workdir, env=ENV,
    )
    assert run.returncode == 0, run.stderr
    capture = workdir / "captures" / "otlp.json"
    assert capture.exists(), "file exporter produced no OTLP JSON"

    convert = subprocess.run(
        [sys.executable, str(CONVERTER), "captures/otlp.json", "-o", "events.ndjson"],
        capture_output=True, text=True, cwd=workdir, env=ENV,
    )
    assert convert.returncode == 0, convert.stderr
    assert "skipped 0" in convert.stderr, "default mapping must cover every pack span"

    # relative path: the report embeds it in its Sources line
    triage = subprocess.run(
        [str(Path(sys.executable).parent / "triage"), "report", "events.ndjson", "--top", "5"],
        capture_output=True, text=True, cwd=workdir, env=ENV,
    )
    assert triage.returncode == 0, triage.stderr
    assert "[parse error]" not in triage.stderr, triage.stderr
    return normalize(triage.stdout)


def test_report_finds_multiple_clusters(report):
    assert "## #1" in report
    assert "## #2" in report
    assert "coordination_failure" in report
    assert "information_lag" in report


def test_report_matches_golden(report):
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(report)
    assert GOLDEN.exists(), "seed the golden with UPDATE_GOLDEN=1 pytest tests/test_round_trip.py"
    assert report == GOLDEN.read_text()
