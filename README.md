# agent-flight-recorder

![demo](demo.gif)

> The demo: the example app runs with audit logging, the hash chain verifies,
> then a tampered copy gets caught. Re-record it with `brew install vhs` and
> `vhs demo.tape` from the repo root with the example requirements installed.

Claude Code skills that give any agent project observability and a
tamper-evident audit trail by default. Install the pack, point a skill at
your repo, and Claude wires it in.

| Skill | What it does |
| --- | --- |
| `audit-log` | Drop-in hash-chained HMAC audit logger for agent runs, plus a verifier that proves chain integrity and detects truncation |
| `otel-agent-tracing` | Instruments LangGraph or MCP agents with OpenTelemetry spans; local Jaeger and Grafana stack via docker compose; first trace in 5 minutes |
| `agent-eval-scaffold` | Generates an evals/ directory: deterministic pytest harness, fixed seeds, golden files, dataset format, GitHub Actions CI gate |
| `trace-triage` | Pipes OTLP spans into [agent-triage](https://github.com/thebharathkumar/agent-triage) and surfaces the top failure clusters |

## Install

Plugin flow (recommended):

```
/plugin marketplace add thebharathkumar/agent-flight-recorder
/plugin install flight-recorder@agent-flight-recorder
```

Skills then surface as `/flight-recorder:audit-log`,
`/flight-recorder:otel-agent-tracing`, `/flight-recorder:agent-eval-scaffold`,
and `/flight-recorder:trace-triage`.

Manual flow (no plugin system needed): each skill folder is self-contained.

```bash
git clone https://github.com/thebharathkumar/agent-flight-recorder
cp -r agent-flight-recorder/skills/* ~/.claude/skills/
```

## Quickstart: tamper-evident audit trail in under 60 seconds

```bash
git clone https://github.com/thebharathkumar/agent-flight-recorder
cd agent-flight-recorder
python3 -m venv .venv && source .venv/bin/activate
pip install -r examples/two-agent-app/requirements.txt
export AUDIT_CHAIN_KEY=demo-key

python examples/two-agent-app/app.py --runs 5 --seed 42 --audit
python skills/audit-log/scripts/verify_chain.py audit/run-000.jsonl
```

You get a two-agent LangGraph run with injected failures, a hash-chained
audit log per run, and a verifier proving nothing was modified. To see it
catch tampering:

```bash
cp audit/run-000.jsonl /tmp/t.jsonl && cp audit/run-000.jsonl.head.json /tmp/t.jsonl.head.json
python skills/audit-log/scripts/verify_chain.py /tmp/t.jsonl --demo-tamper
```

Next steps with the same example app:

```bash
# spans without any docker: OTLP JSON straight to a file
python examples/two-agent-app/app.py --runs 10 --seed 42 --trace

# cluster the failures
pip install agent-triage
python skills/trace-triage/scripts/otlp_to_triage.py captures/otlp.json -o events.ndjson
triage report events.ndjson --top 5
```

## The skills

### audit-log

Every entry is chained with
`entry_hash = HMAC_SHA256(key, prev_hash + canonical_json(body))`. Edits,
deletions, insertions, and reordering break the chain; a head anchor written
on every append catches truncation from the tail. The verifier never passes
silently when the anchor is missing. The trust model is documented in the
skill, including what an attacker with the key can still do.

### otel-agent-tracing

SDK setup template, a per-node span wrapper for LangGraph, and a docker
compose stack (OTel Collector, Jaeger, Grafana preprovisioned). Emits
OpenTelemetry semantic conventions, including the MCP attributes and the
four `mcp.*.duration` histograms that a 2026 audit of public MCP
instrumentations found nobody ships. Includes an OTLP JSON file exporter so
everything also works with no docker at all.

### agent-eval-scaffold

Generates `evals/` with a golden-file pytest harness, seed pinning, a JSONL
dataset format, and a PR-gating workflow. Two consecutive clean runs after
seeding goldens prove determinism before anything is committed.

### trace-triage

Converts real OTLP JSON (collector file exporter output or the tracing
skill's file exporter) into agent-triage events: attribute mapping, turn
synthesis from span order, and failure classification from exception types.
The default mapping covers everything otel-agent-tracing emits, so the two
skills compose with zero configuration; that composition is enforced by a
round-trip test in CI.

## Example app

`examples/two-agent-app/` is a planner and worker LangGraph graph with a
scripted stub LLM (no API keys, no network) and seeded failure injection.
Deterministic given `--seed`. Tested against langgraph 1.2.7, pinned
`>=1.2,<2`.

## Development

```bash
uv sync
make test        # pytest
make cov         # coverage gate, 90 percent on skills and examples
make lint        # ruff
make validate    # claude plugin validate . --strict
```

CI runs lint, the coverage-gated suite on Python 3.11 and 3.12, a repo-wide
em dash and hygiene gate, and plugin validation.

## License

MIT
