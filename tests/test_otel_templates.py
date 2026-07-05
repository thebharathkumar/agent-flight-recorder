"""OTel templates: the OTLP JSON file exporter feeds the converter; traced_node semantics."""

import json
import sys
from pathlib import Path

import pytest
import yaml
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "otel-agent-tracing" / "templates"))
sys.path.insert(0, str(ROOT / "skills" / "trace-triage" / "scripts"))

from langgraph_tracing import traced_node  # noqa: E402
from otel_setup import configure_otel  # noqa: E402
from otlp_to_triage import convert  # noqa: E402


@pytest.fixture(scope="module")
def otel(tmp_path_factory):
    path = tmp_path_factory.mktemp("otlp") / "otlp.json"
    provider = configure_otel("template-test", file_export_path=path)
    memory = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    return provider, memory, path


class ClassifiedError(RuntimeError):
    classification = "environment_constraint"


def test_traced_node_success_span(otel):
    provider, memory, _ = otel
    memory.clear()

    @traced_node(graph_name="demo", node_name="planner", agent_id="planner")
    def planner(state):
        return {"plan": "done"}

    assert planner({"run_id": "run-7", "turn": 3}) == {"plan": "done"}
    span = memory.get_finished_spans()[-1]
    assert span.name == "demo.planner"
    assert span.attributes["agent.id"] == "planner"
    assert span.attributes["run.id"] == "run-7"
    assert span.attributes["turn"] == 3
    assert span.attributes["gen_ai.operation.name"] == "invoke_agent"


def test_traced_node_failure_records_classification(otel):
    provider, memory, _ = otel
    memory.clear()

    @traced_node(graph_name="demo", node_name="worker", agent_id="worker")
    def worker(state):
        raise ClassifiedError("disk full")

    with pytest.raises(ClassifiedError):
        worker({"run_id": "run-7", "turn": 4})
    span = memory.get_finished_spans()[-1]
    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes["failure.classification"] == "environment_constraint"
    assert span.events[0].name == "exception"


def test_file_exporter_output_feeds_converter(otel):
    provider, memory, path = otel
    provider.force_flush()
    docs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert docs, "file exporter wrote nothing"
    events = []
    for doc in docs:
        converted, skipped = convert(doc)
        assert skipped == 0
        events.extend(converted)
    workers = [e for e in events if e["agent_id"] == "worker"]
    assert workers and workers[0]["action_succeeded"] is False
    assert workers[0]["failure_classification"] == "environment_constraint"
    assert all(len(e["event_id"]) == 16 for e in events), "span ids must be hex, not base64"
    assert all(int(e["event_id"], 16) for e in events)


def test_configure_otel_attaches_grpc_exporter_when_endpoint_set(tmp_path):
    provider = configure_otel("endpoint-test", otlp_endpoint="http://localhost:59999")
    processors = provider._active_span_processor._span_processors
    assert processors, "expected a batch processor for the grpc exporter"
    provider.shutdown()


def test_compose_and_collector_config_parse():
    assets = ROOT / "skills" / "otel-agent-tracing" / "assets"
    compose = yaml.safe_load((assets / "docker-compose.yml").read_text())
    services = compose["services"]
    assert {"otel-collector", "jaeger", "grafana"} <= set(services)
    collector = yaml.safe_load((assets / "otel-collector-config.yaml").read_text())
    assert "otlp" in collector["receivers"]
    assert "file" in collector["exporters"]
    datasource = yaml.safe_load(
        (assets / "grafana-provisioning" / "datasources" / "jaeger.yaml").read_text()
    )
    assert datasource["datasources"][0]["type"] == "jaeger"
