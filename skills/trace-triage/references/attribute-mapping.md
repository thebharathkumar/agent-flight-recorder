# Attribute mapping

`otlp_to_triage.py` maps OTLP span data onto the agent-triage event schema.
The default mapping covers every span the otel-agent-tracing skill emits,
including MCP semantic conventions, so pack-emitted spans need no `--map`.

## Default mapping

| Triage field | Sources, in order |
| --- | --- |
| `event_id` | `spanId` (spans without one are skipped and counted) |
| `run_id` | `run.id`, `run_id` attribute, else `traceId` |
| `agent_id` | `agent.id`, `agent_id` attribute, else resource `service.name`, else `unknown` |
| `turn` | `turn` attribute, else synthesized: span start order per (run, agent) |
| `action_taken.tool_name` | `action.tool`, `tool_name` attribute, else the target extracted from MCP span names shaped `{mcp.method.name} {target}` (for example `tools/call echo` gives `echo`), else the span name |
| `action_succeeded` | span status code, `False` when ERROR (numeric `2` or `STATUS_CODE_ERROR`) |
| `failure_classification` | `failure.classification`, `failure_classification` attribute; else derived from the `exception` event type (table below); else `agent_error` when an exception event exists; else null |
| `latency_ms.total` | span duration from `startTimeUnixNano` and `endTimeUnixNano` |
| `timestamp` | `startTimeUnixNano` as UTC ISO 8601 |

Resource attributes are merged under span attributes (span wins on conflict).

## Exception type to classification

| `exception.type` | classification |
| --- | --- |
| `TimeoutError`, `asyncio.TimeoutError` | `information_lag` |
| `ConnectionError`, `OSError`, `PermissionError` | `environment_constraint` |
| `ValueError`, `TypeError`, `KeyError` | `agent_error` |
| anything else | `agent_error` |

Dotted suffixes match too: `somepkg.TimeoutError` maps like `TimeoutError`.

## Overriding with --map mapping.toml

Override attribute lookups or the exception table for foreign span layouts.
Your entries are tried before the defaults; the defaults stay as fallback.

```toml
[attributes]
agent_id = ["my.actor.name"]
run_id = ["session.id"]
tool = ["rpc.method"]
classification = ["error.category"]

[classification_from_exception]
"RateLimitError" = "environment_constraint"
"HallucinationError" = "agent_error"
```

Valid classification values, from the agent-triage schema:
`coordination_failure`, `agent_error`, `information_lag`,
`environment_constraint`. Anything else is passed through and agent-triage
will reject the event, so stick to these four.
