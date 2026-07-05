# First trace in 5 minutes

From zero to a rendered trace in Jaeger, using the pack's example app. Swap
in your own agent at step 4 once the pipeline works.

## 1. Start the local stack (about 1 minute, mostly image pulls)

```bash
cd skills/otel-agent-tracing/assets
docker compose up -d
```

Wait for `docker compose ps` to show all three services running.

## 2. Install the SDK in your agent's environment

```bash
pip install "opentelemetry-sdk>=1.30,<2" "opentelemetry-exporter-otlp-proto-grpc>=1.30,<2"
```

## 3. Wire the SDK

Copy `templates/otel_setup.py` next to your agent code and call it once at
startup:

```python
from otel_setup import configure_otel

configure_otel("my-agent", otlp_endpoint="http://localhost:4317")
```

## 4. Emit spans

Fastest path, the example app from this pack:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
  python examples/two-agent-app/app.py --runs 5 --trace
```

Or wrap your own LangGraph nodes with `traced_node` from
`templates/langgraph_tracing.py`:

```python
from langgraph_tracing import traced_node

@traced_node(graph_name="support", node_name="planner", agent_id="planner")
def planner(state):
    ...
```

## 5. Look at the trace

Open http://localhost:16686, pick your service name, click Find Traces.
You should see one trace per run with a span per node. Grafana is at
http://localhost:3000 with the Jaeger datasource preloaded (Explore, then
pick Jaeger).

## No docker?

Skip the stack and export to a file instead:

```python
configure_otel("my-agent", file_export_path="captures/otlp.json")
```

The file holds real OTLP JSON that the trace-triage skill consumes directly.
