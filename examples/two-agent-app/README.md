# two-agent-app

A deliberately small LangGraph app used by the pack's quickstart and tests: a
planner agent and a worker agent, a scripted stub LLM (no API keys, no
network), and seeded failure injection so the triage skill has real clusters
to find. Deterministic given `--seed`.

Tested against langgraph 1.2.7 (pinned `>=1.2,<2` in requirements.txt).

```bash
pip install -r requirements.txt
python app.py --runs 10 --seed 42            # plain run, printed summaries
python app.py --runs 10 --seed 42 --audit    # + hash-chained audit logs in audit/
python app.py --runs 10 --seed 42 --trace    # + OTLP JSON spans in captures/otlp.json
```

- `--audit` pairs with the audit-log skill:
  `python ../../skills/audit-log/scripts/verify_chain.py audit/run-000.jsonl`
- `--trace` pairs with the trace-triage skill:
  `python ../../skills/trace-triage/scripts/otlp_to_triage.py captures/otlp.json -o events.ndjson`
  then `triage report events.ndjson --top 5`
- With the docker stack from otel-agent-tracing running, add
  `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` to see the same runs in
  Jaeger.
