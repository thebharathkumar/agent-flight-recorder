# agent-flight-recorder design

Date: 2026-07-05
Status: approved (user approved the four SKILL.md drafts and repo structure with four amendments, all folded in below)

## Purpose

An open source pack of Claude Code skills that give any agent project observability and a tamper-evident audit trail by default. Repackages three existing bodies of work: the agent-triage OTLP triage scorer, the mcp-otel-audit semantic convention findings, and the hash-chained HMAC audit log pattern from claimtrace and obindoc. MIT license, public GitHub repo.

## Naming

Original working name agent-ops collided with AgentOps (agentops.ai and the agentops PyPI SDK), a well known company in this niche. The user's replacement pick was agent-receipts with fallback agent-flight-recorder. Collision check results (2026-07-05):

- agent-receipts: REJECTED. Active same-niche project, not a squatter. PyPI package agent-receipts v0.12.0, "Python SDK for the Agent Receipts protocol" by Otto Jongerius, backed by the GitHub org agent-receipts with an SDK repo (agent-receipts/ar) and a separate protocol spec repo (agent-receipts/spec). The org's flagship repo has 20 stars and is described as "cryptographically signed audit trails for AI agent actions", which is exactly this pack's audit-log story. Shipping under this name would read as an implementation of their protocol. GitHub search shows 38 repos matching the name.
- agent-flight-recorder: SELECTED. PyPI package agent-flight-recorder v0.2.0 exists ("Debug AI Agents without burning money", individual developer 0xdivin3), and GitHub search shows 40 small matching repos, with top hits at 0 to 3 stars. No org, no protocol, no company. This pack does not publish to PyPI, so the package name overlap is cosmetic. thebharathkumar/agent-flight-recorder is free.

Names used throughout:

- GitHub repo and marketplace name: agent-flight-recorder
- Plugin name: flight-recorder
- Skill invocations: /flight-recorder:audit-log, /flight-recorder:otel-agent-tracing, /flight-recorder:agent-eval-scaffold, /flight-recorder:trace-triage
- Audit key env var: AUDIT_CHAIN_KEY

## Packaging

One repo that is simultaneously the plugin and its own single-entry marketplace.

- .claude-plugin/plugin.json: name flight-recorder, MIT, repo metadata, keywords.
- .claude-plugin/marketplace.json: marketplace name agent-flight-recorder, one plugin entry with source "./".
- skills/ at repo root per the plugin layout rules (components never live inside .claude-plugin/).

Both install paths documented in the README:

1. Plugin flow: /plugin marketplace add thebharathkumar/agent-flight-recorder then /plugin install flight-recorder@agent-flight-recorder
2. Manual flow: cp -r skills/* ~/.claude/skills/ (each skill folder is self-contained)

## Repo structure

    agent-flight-recorder/
    ├── .claude-plugin/
    │   ├── plugin.json
    │   └── marketplace.json
    ├── skills/
    │   ├── audit-log/
    │   │   ├── SKILL.md
    │   │   ├── scripts/chained_log.py
    │   │   ├── scripts/verify_chain.py
    │   │   └── templates/{langgraph_integration.py, plain_python.py}
    │   ├── otel-agent-tracing/
    │   │   ├── SKILL.md
    │   │   ├── templates/{otel_setup.py, langgraph_tracing.py}
    │   │   ├── assets/{docker-compose.yml, otel-collector-config.yaml, grafana-provisioning/}
    │   │   └── references/{first-trace.md, semconv.md, conformance.md}
    │   ├── agent-eval-scaffold/
    │   │   ├── SKILL.md
    │   │   └── templates/{harness.py, conftest.py, test_golden.py, smoke.jsonl, evals-README.md, evals-ci.yml}
    │   └── trace-triage/
    │       ├── SKILL.md
    │       ├── scripts/otlp_to_triage.py
    │       └── references/attribute-mapping.md
    ├── examples/two-agent-app/
    ├── tests/
    ├── .github/workflows/ci.yml
    ├── docs/superpowers/specs/  (this doc)
    ├── README.md, CHANGELOG.md, LICENSE, pyproject.toml
    └── Makefile (dev shortcuts)

Design principle: bundled scripts are stdlib-only so target repos need no install step. Heavier dependencies (agent-triage, OTel SDK, langgraph) are installed by skill procedures inside the target project, or already exist there.

## Skill 1: audit-log

Tamper-evident hash-chained HMAC audit logger, merged from claimtrace (keyed HMAC-SHA256, structured verify, tamper demo) and obindoc (portable JSONL-per-run format, human-readable diagnostics).

Chain spec:

- One JSONL file per run, default audit/<run_id>.jsonl.
- Entry fields: seq, ts, run_id, actor, action, payload, prev_hash, entry_hash.
- entry_hash = HMAC_SHA256(key, prev_hash + canonical_json(body)) where body is every field except entry_hash. Canonical JSON: sorted keys, compact separators, default=str.
- Genesis prev_hash is 64 zeros.
- Key from AUDIT_CHAIN_KEY env var. Dev default ships in the script with a loud warning; docs say never use it in production.

Three deliberate improvements over the source repos:

1. The hash covers ts, seq, and run_id (claimtrace left them outside the hash).
2. The chain is keyed (obindoc used unkeyed SHA-256).
3. Truncation anchor, ON BY DEFAULT (user amendment 4): every append rewrites <log>.head.json containing {count, head_hash}. verify_chain.py always checks the anchor when present. When no anchor file exists, verification of the chain still runs but the script prints a prominent WARNING that truncation from the tail cannot be ruled out; it never passes silently. A --require-anchor flag turns the missing anchor into a hard failure (exit 2).

Trust model documented honestly in SKILL.md: an attacker with both file write access and the HMAC key can rebuild the chain; the anchor only protects truncation to the extent it is stored where the attacker cannot write.

verify_chain.py: exit 0 intact, exit 1 with line-numbered diagnosis on chain failure, exit 2 on anchor failure or --require-anchor with no anchor. --demo-tamper flips one byte on a copy to demonstrate detection.

## Skill 2: otel-agent-tracing

Instruments a LangGraph or MCP agent with OpenTelemetry and stands up a local stack.

- templates/otel_setup.py: configure_otel(service_name, file_export_path=None). TracerProvider + BatchSpanProcessor + OTLP gRPC exporter (endpoint from OTEL_EXPORTER_OTLP_ENDPOINT, default localhost:4317) plus MeterProvider. When file_export_path is set (or OTEL_FILE_EXPORT env), an additional file span exporter serializes finished spans to real OTLP JSON (resourceSpans shape, via the otlp proto common encoder and protobuf json_format). This file exporter is what makes the no-docker round trip possible (user amendment 3).
- templates/langgraph_tracing.py: traced_node wrapper. Span per node named <graph>.<node>, records gen_ai.operation.name, agent.id, run.id, turn; sets span status from exceptions and records failure.classification when the raised error carries one.
- MCP guidance encoded from the mcp-otel-audit findings: fastmcp native telemetry already emits semconv-shaped spans (span name "{mcp.method.name} {target}", SpanKind.SERVER, mcp.method.name attribute), so only SDK setup is needed; official mcp SDK servers should emit that same shape manually; Traceloop McpInstrumentor and logfire.instrument_mcp() get a warning because measured captures show neither emits mcp.method.name.
- assets/docker-compose.yml: otel-collector (4317/4318, also file-exports to captures/otlp.json), Jaeger UI (16686), Grafana (3000) with Jaeger datasource provisioned.
- references/first-trace.md: the 5 minute walkthrough. references/semconv.md: exact vocabulary including the four mcp.*.{operation,session}.duration histograms that the audit showed nobody emits. references/conformance.md: OTel Weaver live-check loop against semconv v1.40.0.

## Skill 3: agent-eval-scaffold

Generates evals/ in the target repo from bundled templates: datasets/smoke.jsonl (cases: id, input, optional expected), harness.py (run_case and normalize, the one file users edit), conftest.py (PYTHONHASHSEED, random and numpy seeding, EVAL_SEED env), test_golden.py (parametrized golden comparison, --update-golden flag), evals/README.md, and a GitHub Actions workflow gating PRs. Procedure requires two consecutive passing runs after seeding goldens as the determinism proof.

## Skill 4: trace-triage

Pipes OTLP span exports into the agent-triage PyPI package.

- scripts/otlp_to_triage.py: stdlib-only converter from real OTLP JSON (resourceSpans, KV-list attributes, resource attrs merged into span attrs) to triage NDJSON.
- DEFAULT mapping closes the loop with otel-agent-tracing (user amendment 3), no --map needed for pack-emitted spans. It recognizes:
  - agent.id / agent_id, falling back to service.name
  - run.id / run_id, falling back to trace_id
  - turn, falling back to span start order per trace per agent
  - tool/action name from action.tool / tool_name, from MCP semconv span names of the form "{mcp.method.name} {target}" (target extracted as tool name, mcp.method.name kept), and from plain span names
  - success from span status code (ERROR means failed)
  - failure.classification / failure_classification attribute; when absent on failed spans, derived from exception event type via a small default table, else unclassified
  - latency from span duration into latency_ms.total
- --map mapping.toml overrides for foreign attribute layouts, documented in references/attribute-mapping.md.
- Converter reports mapped/skipped counts and warns when most failed events land unclassified.
- Then: triage report events.ndjson --top 5, optional triage compare and triage-serve dashboard.

## Example app

examples/two-agent-app: a real LangGraph graph (planner node, worker node) driven by a scripted stub LLM. Zero API keys, zero network, deterministic per seed. Seeded failure injection produces classified failures across runs so triage has clusters to find. Flags: --audit wires the audit logger, --trace wires configure_otel with the OTLP JSON file exporter, --runs N, --seed S.

Version pinning (user amendment 2): examples/two-agent-app/requirements.txt pins a langgraph version range; the README states the exact version the quickstart was tested against.

Quickstart (under 60 seconds, no docker): install pack, run the app with --audit, verify the chain with the audit-log skill. The tracing demo with Jaeger is the separate 5 minute walkthrough.

## Tests and CI

pytest, coverage gate 90 percent on skill scripts and templates.

1. Format tests: every SKILL.md frontmatter parses, description present and within limits, every file referenced by a SKILL.md exists; plugin.json and marketplace.json parse and carry required fields. claude plugin validate runs in CI when the CLI is available (best effort, skipped otherwise).
2. Audit tests: the six claimtrace attack tests ported (intact chain, linkage, one-byte flip, recomputed-hash attack detected at next link, deletion, tamper demo roundtrip) plus truncation-with-anchor detection, missing-anchor loud warning, --require-anchor failure, and wrong-key detection.
3. Converter tests: golden OTLP JSON fixture to NDJSON snapshot; attribute fallbacks; turn synthesis; classification derivation.
4. Round-trip test, no docker (user amendment 3): run the toy app with --trace (SDK file exporter), convert captures/otlp.json with otlp_to_triage.py using the DEFAULT mapping, run triage report --top 5, assert against a golden report file (timestamps normalized).
5. Eval scaffold test: generate evals/ into a tmp copy of the toy app, seed goldens, run the generated suite twice, both green.
6. Hygiene: em dash grep gate over the whole repo (the character U+2014 must appear nowhere), ruff lint.

CI: GitHub Actions, Python 3.11 and 3.12, uv for env setup, jobs: lint+hygiene, tests+coverage, plugin validate (best effort).

## Deliverables checklist

- README topped by demo GIF placeholder plus exact vhs commands to record it; install paths; tested langgraph version; per-skill summaries.
- CHANGELOG.md (Keep a Changelog format, 0.1.0).
- One-paragraph launch summary for the user's post generator.
- No em dashes anywhere in docs or generated text, enforced by CI.

## Open items to batch at the end

- Confirm the agent-flight-recorder name choice given the collision findings above.
- Whether to publish the repo via gh (creation is an outward-facing action reserved for the user unless they say go).
