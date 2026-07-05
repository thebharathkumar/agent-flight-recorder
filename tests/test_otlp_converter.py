"""OTLP JSON to triage NDJSON converter: default mapping, fallbacks, overrides."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "trace-triage" / "scripts" / "otlp_to_triage.py"
FIXTURE = ROOT / "tests" / "fixtures" / "otlp_sample.json"

sys.path.insert(0, str(SCRIPT.parent))

from otlp_to_triage import convert  # noqa: E402


@pytest.fixture()
def events():
    converted, skipped = convert(json.loads(FIXTURE.read_text()))
    return converted


def by_id(events, event_id):
    return next(e for e in events if e["event_id"] == event_id)


def test_fixture_converts_four_spans_and_skips_one(events):
    _, skipped = convert(json.loads(FIXTURE.read_text()))
    assert len(events) == 4
    assert skipped == 1


def test_success_and_failure_from_status(events):
    assert by_id(events, "0000000000000001")["action_succeeded"] is True
    assert by_id(events, "0000000000000002")["action_succeeded"] is False


def test_agent_run_turn_from_attributes(events):
    planner = by_id(events, "0000000000000001")
    assert planner["agent_id"] == "planner"
    assert planner["run_id"] == "run-1"
    assert planner["turn"] == 0


def test_agent_falls_back_to_service_name_run_to_trace_id(events):
    mcp = by_id(events, "0000000000000003")
    assert mcp["agent_id"] == "mcp-server"
    assert mcp["run_id"] == "bbbb0000000000000000000000000002"


def test_turn_synthesized_from_start_order(events):
    first = by_id(events, "0000000000000003")
    second = by_id(events, "0000000000000004")
    assert (first["turn"], second["turn"]) == (0, 1)


def test_mcp_span_name_yields_tool_and_method(events):
    mcp = by_id(events, "0000000000000003")
    assert mcp["action_taken"]["tool_name"] == "echo"
    assert mcp["mcp_method"] == "tools/call"


def test_explicit_tool_attribute_wins(events):
    assert by_id(events, "0000000000000002")["action_taken"]["tool_name"] == "fetch_data"


def test_classification_derived_from_exception(events):
    assert by_id(events, "0000000000000002")["failure_classification"] == "information_lag"
    assert by_id(events, "0000000000000004")["failure_classification"] == "agent_error"


def test_explicit_classification_attribute_wins():
    doc = json.loads(FIXTURE.read_text())
    span = doc["resourceSpans"][0]["scopeSpans"][0]["spans"][1]
    span["attributes"].append(
        {"key": "failure.classification", "value": {"stringValue": "coordination_failure"}}
    )
    events, _ = convert(doc)
    assert by_id(events, "0000000000000002")["failure_classification"] == "coordination_failure"


def test_latency_from_span_duration(events):
    assert by_id(events, "0000000000000002")["latency_ms"]["total"] == 1500.0


def test_map_override(tmp_path):
    doc = json.loads(FIXTURE.read_text())
    doc["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"].append(
        {"key": "custom.actor", "value": {"stringValue": "overridden"}}
    )
    mapping = tmp_path / "mapping.toml"
    mapping.write_text('[attributes]\nagent_id = ["custom.actor"]\n')
    events, _ = convert(doc, mapping_path=mapping)
    assert by_id(events, "0000000000000001")["agent_id"] == "overridden"


def test_cli_writes_ndjson_and_reports_counts(tmp_path):
    out = tmp_path / "events.ndjson"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(FIXTURE), "-o", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    lines = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(lines) == 4
    assert "mapped 4 spans" in result.stderr
    assert "skipped 1" in result.stderr


def test_events_load_into_triage(tmp_path, events):
    """The converter output is accepted by the real agent-triage loader."""
    out = tmp_path / "events.ndjson"
    out.write_text("".join(json.dumps(e) + "\n" for e in events))
    from triage.loader import load_files

    result = load_files([out], None)
    assert not result.parse_errors
    assert len(result.events) == 4
