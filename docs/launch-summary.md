# Launch summary

agent-flight-recorder is an MIT-licensed pack of four Claude Code skills
that give any agent project observability and a tamper-evident audit trail
by default: audit-log drops in a hash-chained HMAC logger whose verifier
catches edits, deletions, reordering, and even truncation, otel-agent-tracing
instruments LangGraph or MCP agents with OpenTelemetry (local Jaeger and
Grafana via docker compose, first trace in 5 minutes, no-docker file export
supported), agent-eval-scaffold generates a deterministic golden-file eval
suite with a CI gate, and trace-triage pipes OTLP spans into the
agent-triage scorer to surface your top failure clusters. The skills
compose: the tracing skill's spans feed the triage skill with zero mapping
configuration, a property enforced by a round-trip test in CI, and the whole
pack ships with a 60 second quickstart on a bundled two-agent LangGraph
example, 97 percent test coverage, and both plugin marketplace and manual
install paths. Install with /plugin marketplace add
thebharathkumar/agent-flight-recorder.
