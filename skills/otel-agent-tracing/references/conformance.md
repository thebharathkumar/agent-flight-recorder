# Checking your spans against the official conventions

OTel Weaver can score a live OTLP stream against the semantic conventions
registry. This is the loop the mcp-otel-audit project used; it works for any
agent spans, not just MCP.

## One-time setup

Download Weaver v0.23.0 for your platform from
https://github.com/open-telemetry/weaver/releases and put it on PATH.

## The loop

1. Start Weaver as an OTLP listener scoring against semconv v1.40.0:

```bash
weaver registry live-check \
  --registry 'https://github.com/open-telemetry/semantic-conventions.git@v1.40.0[model]' \
  --input-source otlp --otlp-grpc-port 14317 --admin-port 14320 \
  --inactivity-timeout 300 --format json --no-stream true > weaver-findings.json
```

2. Point your agent at it and run once:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:14317 python your_agent.py
```

3. Stop the listener and read the findings:

```bash
curl -X POST http://127.0.0.1:14320/stop
```

Findings carry an `all_advice` list per span with `id`, `level`
(`violation`, `improvement`, `information`), and `message`. Start with the
violations: `missing_attribute` and `deprecated` are the ones that mean
your spans will not interoperate.
