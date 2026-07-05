---
name: trace-triage
description: Cluster and rank agent failures from OpenTelemetry trace exports
  using the agent-triage scorer. Use when the user has OTel spans or OTLP
  exports from agent runs and asks what is failing, wants failure clusters or
  a triage report, or wants to compare agent behavior before and after a
  change.
---

# Trace Triage

Pipes OTLP span exports into `agent-triage` (PyPI) and surfaces the top
failure clusters, ranked by frequency and severity, with recovery rates and
suggested next actions.

## Procedure

1. Install the scorer in the target environment:
   `pip install agent-triage`.
2. Locate the span source, in order of preference:
   - `captures/otlp.json` written by the otel-agent-tracing skill (either
     its docker collector or its OTLP JSON file exporter),
   - any OTLP JSON export the user points at,
   - native triage NDJSON, which skips step 3.
3. Convert OTLP to triage events:
   `python scripts/otlp_to_triage.py <otlp.json> -o events.ndjson`.
   The DEFAULT mapping understands everything the otel-agent-tracing skill
   emits, including MCP semconv (`mcp.method.name`, span names shaped
   `{method} {target}`), so no `--map` is needed for pack-emitted spans.
   For foreign span layouts pass `--map mapping.toml`; the format and the
   full default mapping live in `references/attribute-mapping.md`.
   The converter prints mapped and skipped counts to stderr. If it warns
   that most failures are unclassified, relay that to the user: triage
   scoring degrades without failure labels.
4. Score and report: `triage report events.ndjson --top 5`.
5. Present the clusters to the user: rank, agent, tool, classification,
   final score, recovery rate, and the suggested action line. Offer to
   drill into the spans behind the top cluster.
6. Optional follow-ups:
   - Before and after: `triage compare before.ndjson after.ndjson` to
     verify a fix actually moved the numbers.
   - Live dashboard: `pip install "agent-triage[server]"`, run
     `triage-serve`, point agents or a collector at
     `POST /otlp/v1/traces`.

## Files

- `scripts/otlp_to_triage.py`: stdlib-only OTLP JSON to NDJSON converter
  with attribute mapping, turn synthesis, and classification derivation.
- `references/attribute-mapping.md`: default mapping and `--map` format.
