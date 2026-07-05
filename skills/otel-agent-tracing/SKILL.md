---
name: otel-agent-tracing
description: Instrument a LangGraph or MCP agent with OpenTelemetry spans and
  view them locally in Jaeger and Grafana. Use when the user asks to add
  tracing or observability to an agent, see spans or traces from agent runs,
  set up Jaeger or Grafana locally, or debug agent latency and failures with
  traces.
---

# OTel Agent Tracing

Adds OpenTelemetry instrumentation to an agent and stands up a local
observability stack (OTel Collector, Jaeger, Grafana) with docker compose.
Target: first trace visible in Jaeger within 5 minutes;
`references/first-trace.md` is the walkthrough version of this procedure.

## Procedure

1. Detect the stack. Look for `langgraph`, `fastmcp`, or `mcp` in the
   project dependencies. This decides step 3.
2. Install SDK deps in the target project:
   `pip install "opentelemetry-sdk>=1.30,<2"
   "opentelemetry-exporter-otlp-proto-grpc>=1.30,<2"`.
   Copy `templates/otel_setup.py` into the project and call
   `configure_otel(service_name=...)` once at startup. It attaches an OTLP
   gRPC exporter when `OTEL_EXPORTER_OTLP_ENDPOINT` (or the
   `otlp_endpoint` argument) is set, and an OTLP JSON file exporter when
   `file_export_path` (or `OTEL_FILE_EXPORT`) is set. The file path works
   with no docker at all and feeds the trace-triage skill directly.
3. Instrument by stack:
   - LangGraph: copy `templates/langgraph_tracing.py` and wrap each node
     with `traced_node(graph_name, node_name, agent_id)`. Nodes become
     spans named `{graph}.{node}` carrying `gen_ai.operation.name`,
     `agent.id`, `run.id`, and `turn` from state; exceptions set ERROR
     status and, when the exception has a `classification` attribute,
     a `failure.classification` span attribute.
   - fastmcp (jlowin): native telemetry already emits semconv-shaped
     spans. Only step 2 is needed.
   - Official `mcp` SDK server: emit spans named
     `{mcp.method.name} {target}` with `SpanKind.SERVER` and the
     attributes in `references/semconv.md`. Prefer SDK-native OTel if the
     installed version ships it.
   - Warn if the project uses Traceloop's `McpInstrumentor` or
     `logfire.instrument_mcp()`: measured against OTel semconv v1.40.0,
     neither emits the required `mcp.method.name` attribute.
4. Start the local stack:
   `docker compose -f <skill>/assets/docker-compose.yml up -d`.
   Services: otel-collector (4317 grpc, 4318 http), Jaeger UI (16686),
   Grafana (3000, Jaeger datasource provisioned). The collector also
   mirrors spans to `captures/otlp.json` for the trace-triage skill. If
   docker is unavailable, skip this step and use the file exporter from
   step 2 instead.
5. Run the agent once with `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`,
   then open http://localhost:16686, select the service name, and confirm
   the trace renders. Show the user what to look for: one root span per
   run, child spans per node or tool call.
6. Optional conformance check: `references/conformance.md` describes the
   OTel Weaver live-check loop that scores spans against the official
   semantic conventions.

## Files

- `templates/otel_setup.py`: SDK boilerplate plus the OTLP JSON file
  exporter.
- `templates/langgraph_tracing.py`: per-node span wrapper.
- `assets/docker-compose.yml`, `assets/otel-collector-config.yaml`,
  `assets/grafana-provisioning/`: the local stack.
- `references/first-trace.md`: 5 minute walkthrough.
- `references/semconv.md`: exact span names, attributes, and the four
  `mcp.*.duration` histograms worth emitting.
- `references/conformance.md`: Weaver-based semconv self-audit.
