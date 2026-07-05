# Semantic conventions worth emitting

Vocabulary from OpenTelemetry semantic conventions v1.40.0 (MCP groups in
development status), plus what a 2026 conformance audit of four public MCP
instrumentations found actually matters.

## MCP servers and clients

- Span name: `{mcp.method.name} {target}`, for example `tools/call echo`.
- Span kind: `SERVER` on the server side, `CLIENT` on the client side.
- Required attribute: `mcp.method.name` (the only required one).
- Recommended attributes: `mcp.session.id`, `server.address`, `server.port`,
  `client.address`, `client.port`, `network.transport`,
  `network.protocol.name`, `network.protocol.version`,
  `jsonrpc.protocol.version`, `gen_ai.operation.name`.
- Also defined: `mcp.resource.uri`, `mcp.protocol.version`.

## The metrics gap

Four histograms are defined that, per the audit, no public instrumentation
emitted at the time of measurement. Emitting them puts you ahead of every
off-the-shelf option:

- `mcp.client.operation.duration`
- `mcp.server.operation.duration`
- `mcp.client.session.duration`
- `mcp.server.session.duration`

## Agent graphs (LangGraph and similar)

No MCP-specific conventions apply; use the gen_ai namespace plus this pack's
conventions, which the trace-triage skill maps by default:

- Span name: `{graph}.{node}`.
- `gen_ai.operation.name`: `invoke_agent` for node execution.
- `agent.id`: which agent acted.
- `run.id`: one id per end-to-end run (falls back to trace id downstream).
- `turn`: integer position in the run, used for recovery scoring.
- `failure.classification`: one of `coordination_failure`, `agent_error`,
  `information_lag`, `environment_constraint` on failed spans.

## Instrumentation choices, measured

- fastmcp (jlowin) native telemetry: emits the correct span name, kind, and
  `mcp.method.name` out of the box. Just configure the SDK.
- Official `mcp` SDK: no native spans at audit time; emit manually per the
  shapes above (native OTel is expected in v2, prefer it once shipped).
- Traceloop `McpInstrumentor` and `logfire.instrument_mcp()`: measured zero
  MCP semconv attributes (INTERNAL spans, no `mcp.method.name`). Avoid when
  conformance matters.
