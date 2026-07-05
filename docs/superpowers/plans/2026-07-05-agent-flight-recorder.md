# agent-flight-recorder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the agent-flight-recorder Claude Code skill pack: four skills, plugin plus marketplace packaging, a deterministic two-agent LangGraph example, a pytest suite with a 90 percent coverage gate including a no-docker round-trip test, GitHub Actions CI, and launch docs.

**Architecture:** A single repo that is both a Claude Code plugin (skills/ at root, .claude-plugin/plugin.json) and its own one-entry marketplace (.claude-plugin/marketplace.json). Bundled skill scripts are stdlib-only (plus the OTel SDK already required by tracing targets); heavy deps live in the target project. The example app closes the loop: it emits OTLP JSON through the tracing template's file exporter, the trace-triage converter maps it with its DEFAULT mapping, and agent-triage scores it.

**Tech Stack:** Python 3.11+, pytest + pytest-cov, ruff, uv, langgraph (example only), opentelemetry-sdk + otlp exporters (tracing template), agent-triage from PyPI (round-trip test), GitHub Actions.

Spec: docs/superpowers/specs/2026-07-05-agent-flight-recorder-design.md. All naming, chain spec, mapping rules, and amendments come from there.

---

### Task 1: Repo scaffolding and packaging manifests

**Files:**
- Create: `pyproject.toml` (dev tooling: pytest, pytest-cov, ruff; project metadata, not published)
- Create: `LICENSE` (MIT, 2026, Bharath Kumar)
- Create: `.gitignore` (venv, __pycache__, .coverage, captures/, audit/, .pytest_cache)
- Create: `.claude-plugin/plugin.json` (name flight-recorder, version 0.1.0, MIT, repository URL, keywords)
- Create: `.claude-plugin/marketplace.json` (name agent-flight-recorder, owner Bharath Kumar, one plugin entry, source "./")
- Create: `Makefile` (test, lint, coverage, validate targets)
- Test: `tests/test_packaging.py`

- [ ] Step 1: Write failing test `tests/test_packaging.py`: plugin.json parses, has name "flight-recorder", version, license MIT; marketplace.json parses, has name "agent-flight-recorder", owner.name, plugins[0].source == "./" and plugins[0].name == "flight-recorder".
- [ ] Step 2: Run `uv run pytest tests/test_packaging.py -v`, expect FAIL (files missing).
- [ ] Step 3: Create all files listed above.
- [ ] Step 4: Run test, expect PASS.
- [ ] Step 5: Commit "feat: repo scaffolding, plugin and marketplace manifests".

### Task 2: audit-log core logger (TDD)

**Files:**
- Create: `skills/audit-log/scripts/chained_log.py`
- Test: `tests/test_audit_chain.py`

Public API locked here:

```python
GENESIS = "0" * 64
DEV_KEY_WARNING: str  # printed to stderr when the dev default key is used

def canonical(obj: dict) -> str  # json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
def compute_hash(prev_hash: str, body: dict, key: bytes) -> str  # HMAC-SHA256 hex over prev_hash + canonical(body)
def load_key(env_var: str = "AUDIT_CHAIN_KEY") -> bytes  # env var, else dev default + stderr warning

class ChainedLogger:
    def __init__(self, path, run_id: str, key: bytes | None = None): ...
    def append(self, actor: str, action: str, payload: dict) -> dict  # returns full entry
    # entry fields: seq, ts, run_id, actor, action, payload, prev_hash, entry_hash
    # every append rewrites <path>.head.json with {"count": N, "head_hash": "..."} (anchor ON by default)
    # resumes chain from last line when the file exists
```

- [ ] Step 1: Write failing tests: entries chained from GENESIS; hash covers seq/ts/run_id (mutating any of them breaks verification); resume after reopen; head anchor file written and matches; dev-key warning emitted when env missing.
- [ ] Step 2: Run `uv run pytest tests/test_audit_chain.py -v`, expect FAIL.
- [ ] Step 3: Implement chained_log.py (stdlib only: json, hmac, hashlib, os, time, pathlib).
- [ ] Step 4: Run tests, expect PASS.
- [ ] Step 5: Commit "feat: hash-chained HMAC audit logger with truncation anchor".

### Task 3: audit-log verifier (TDD, attack tests)

**Files:**
- Create: `skills/audit-log/scripts/verify_chain.py`
- Test: `tests/test_verify_chain.py`

CLI: `python verify_chain.py <log.jsonl> [--key-env AUDIT_CHAIN_KEY] [--require-anchor] [--demo-tamper]`
Exit codes: 0 intact, 1 chain broken (line-numbered diagnosis), 2 anchor mismatch or --require-anchor without anchor. Missing anchor without the flag: still verifies the chain but prints a prominent multi-line WARNING (never silent). Also exposes `verify(path, key) -> (ok: bool, report: str)` for import.

- [ ] Step 1: Write failing tests porting the claimtrace attack suite: intact pass; one-byte payload flip detected at that seq; recomputed-hash attack detected at next link; deleted entry detected; reordering detected; truncation detected via anchor; missing anchor warns loudly on stderr but exits 0; --require-anchor exits 2; wrong key fails; --demo-tamper on a copy breaks then restore verifies.
- [ ] Step 2: Run, expect FAIL.
- [ ] Step 3: Implement verify_chain.py (imports compute_hash/canonical/GENESIS from chained_log.py via sibling import with fallback path insert, so the folder works when copied standalone).
- [ ] Step 4: Run tests, expect PASS.
- [ ] Step 5: Commit "feat: chain verifier with anchor enforcement and tamper demo".

### Task 4: audit-log templates and SKILL.md

**Files:**
- Create: `skills/audit-log/templates/langgraph_integration.py` (ChainedLogger in graph state, one append per node, complete runnable pattern)
- Create: `skills/audit-log/templates/plain_python.py` (logger around tool calls)
- Create: `skills/audit-log/SKILL.md` (approved draft, renamed env var AUDIT_CHAIN_KEY, anchor described as default-on, verify warning behavior documented)

- [ ] Step 1: Write files. SKILL.md body matches the approved draft with the amendments.
- [ ] Step 2: `uv run ruff check skills/`, expect clean.
- [ ] Step 3: Commit "feat: audit-log skill doc and integration templates".

### Task 5: trace-triage converter (TDD)

**Files:**
- Create: `skills/trace-triage/scripts/otlp_to_triage.py`
- Create: `tests/fixtures/otlp_sample.json` (real OTLP JSON: resourceSpans, KV-list attributes, resource attrs, one ERROR span with exception event, one MCP-shaped span named "tools/call echo" with mcp.method.name)
- Test: `tests/test_otlp_converter.py`

CLI: `python otlp_to_triage.py <otlp.json> [-o events.ndjson] [--map mapping.toml]`. Stdlib only (tomllib for --map). DEFAULT mapping per spec: agent.id|agent_id -> agent_id else service.name; run.id|run_id else trace_id; turn attr else synthesized from span start order per (trace, agent); tool from action.tool|tool_name, else MCP span name "{method} {target}" (target as tool_name), else span name; succeeded from status code (2/ERROR -> False); failure.classification|failure_classification, else derived from exception event type (TimeoutError -> information_lag, ConnectionError|OSError -> environment_constraint, ValueError|TypeError|KeyError -> agent_error, default agent_error), else None; latency_ms.total from span duration. Emits triage TraceEvent NDJSON (event_id, run_id, turn, agent_id, timestamp, action_taken.tool_name, action_succeeded, failure_classification, latency_ms). Prints mapped/skipped counts and an unclassified-majority warning to stderr.

- [ ] Step 1: Write failing tests: fixture converts; MCP span name split works with mcp.method.name recognized; turn synthesis ordering; classification derivation table; resource attr merge; skipped-span counting; --map override.
- [ ] Step 2: Run, expect FAIL.
- [ ] Step 3: Implement.
- [ ] Step 4: Run, expect PASS.
- [ ] Step 5: Commit "feat: OTLP to triage converter with pack-native default mapping".

### Task 6: trace-triage references and SKILL.md

**Files:**
- Create: `skills/trace-triage/references/attribute-mapping.md` (default mapping table, mapping.toml format)
- Create: `skills/trace-triage/SKILL.md` (approved draft; step 3 states pack-emitted spans need no --map)

- [ ] Step 1: Write files.
- [ ] Step 2: Commit "feat: trace-triage skill doc and mapping reference".

### Task 7: otel-agent-tracing templates (TDD on the file exporter)

**Files:**
- Create: `skills/otel-agent-tracing/templates/otel_setup.py`
- Create: `skills/otel-agent-tracing/templates/langgraph_tracing.py`
- Test: `tests/test_otel_templates.py`

`configure_otel(service_name: str, file_export_path: str | None = None, otlp_endpoint: str | None = None) -> TracerProvider`. File exporter class `OTLPJsonFileExporter(SpanExporter)` encodes finished spans with `opentelemetry.exporter.otlp.proto.common.trace_encoder.encode_spans` then `google.protobuf.json_format.MessageToDict`, appending one `{"resourceSpans": [...]}` JSON line per batch. OTLP gRPC exporter attached only when endpoint reachable or explicitly set (env OTEL_EXPORTER_OTLP_ENDPOINT), so the no-docker path works offline. `traced_node(graph_name, node_name, agent_id)` decorator: span `{graph}.{node}`, attrs gen_ai.operation.name, agent.id, run.id, turn (from state), status from exception, failure.classification attr when the exception carries `.classification`.

- [ ] Step 1: Write failing tests: configure_otel with file_export_path writes valid OTLP JSON lines the Task 5 converter can parse; traced_node sets span name, attrs, ERROR status and failure.classification on a classified exception.
- [ ] Step 2: Run, expect FAIL (deps: add otel packages to dev extras first).
- [ ] Step 3: Implement both templates.
- [ ] Step 4: Run, expect PASS.
- [ ] Step 5: Commit "feat: otel setup template with OTLP JSON file exporter and langgraph node tracing".

### Task 8: otel-agent-tracing assets, references, SKILL.md

**Files:**
- Create: `skills/otel-agent-tracing/assets/docker-compose.yml` (otel-collector-contrib 0.115.1 with 4317/4318 plus file exporter to captures/otlp.json; jaegertracing/all-in-one with 16686; grafana with provisioned Jaeger datasource)
- Create: `skills/otel-agent-tracing/assets/otel-collector-config.yaml`
- Create: `skills/otel-agent-tracing/assets/grafana-provisioning/datasources/jaeger.yaml`
- Create: `skills/otel-agent-tracing/references/first-trace.md`, `references/semconv.md`, `references/conformance.md`
- Create: `skills/otel-agent-tracing/SKILL.md` (approved draft)
- Test: extend `tests/test_otel_templates.py` with a YAML parse check of compose and collector config

- [ ] Step 1: Write the YAML parse test (pyyaml in dev deps), expect FAIL.
- [ ] Step 2: Write all assets, references, SKILL.md. semconv.md carries the exact vocabulary from the audit findings (mcp.method.name, span name format, recommended attrs, four duration histograms). conformance.md documents the Weaver v0.23.0 live-check loop.
- [ ] Step 3: Run tests, expect PASS. If docker available locally run `docker compose -f skills/otel-agent-tracing/assets/docker-compose.yml config -q` once as a sanity check (not in CI).
- [ ] Step 4: Commit "feat: local observability stack assets and tracing skill doc".

### Task 9: example two-agent app (TDD on determinism)

**Files:**
- Create: `examples/two-agent-app/app.py` (planner node + worker node LangGraph graph, scripted stub LLM, seeded failure injection with triage classifications; flags --runs, --seed, --audit, --trace; --trace calls configure_otel with file_export_path captures/otlp.json)
- Create: `examples/two-agent-app/stub_llm.py`
- Create: `examples/two-agent-app/requirements.txt` (pinned langgraph range per spec, exact range chosen from the version installed at build time)
- Create: `examples/two-agent-app/README.md` (tested langgraph version stated)
- Test: `tests/test_example_app.py`

- [ ] Step 1: `uv pip install langgraph` in the dev venv, record version, write requirements.txt range around it.
- [ ] Step 2: Write failing tests: same seed twice gives identical run summaries; --audit produces a verifiable chain (import verify from Task 3); failure injection yields at least two distinct classifications across 10 runs.
- [ ] Step 3: Run, expect FAIL.
- [ ] Step 4: Implement app.py and stub_llm.py. Audit integration follows skills/audit-log/templates/langgraph_integration.py; tracing follows templates/langgraph_tracing.py (import via path, no packaging tricks: the example vendors nothing, it inserts the skills paths).
- [ ] Step 5: Run, expect PASS.
- [ ] Step 6: Commit "feat: deterministic two-agent example app".

### Task 10: agent-eval-scaffold templates, SKILL.md, generation test

**Files:**
- Create: `skills/agent-eval-scaffold/templates/{harness.py, conftest.py, test_golden.py, smoke.jsonl, evals-README.md, evals-ci.yml}`
- Create: `skills/agent-eval-scaffold/SKILL.md` (approved draft)
- Test: `tests/test_eval_scaffold.py`

- [ ] Step 1: Write failing test: copy toy app to tmp, materialize evals/ from the templates (string substitution of the entrypoint import), run `pytest evals/ --update-golden` then `pytest evals/` twice via subprocess, both exit 0; goldens exist; corrupt one golden byte, rerun, exit != 0.
- [ ] Step 2: Run, expect FAIL.
- [ ] Step 3: Write templates. test_golden.py implements --update-golden via a conftest pytest_addoption. harness.py template contains a working default for the toy app shape plus clear EDIT ME markers.
- [ ] Step 4: Run, expect PASS.
- [ ] Step 5: Commit "feat: eval scaffold templates proven against the example app".

### Task 11: round-trip integration test (no docker)

**Files:**
- Test: `tests/test_round_trip.py`
- Create: `tests/golden/round_trip_report.md`

- [ ] Step 1: `uv pip install agent-triage` into dev deps. Write the test: run `python examples/two-agent-app/app.py --runs 10 --seed 42 --trace` in a tmp cwd; assert captures/otlp.json exists; run otlp_to_triage.py with NO --map; run `triage report events.ndjson --top 5`; normalize timestamps and floating scores to fixed precision; compare to golden. First run with an UPDATE_GOLDEN=1 escape hatch to seed the golden, then a second clean run must pass.
- [ ] Step 2: Run twice, second run green against committed golden.
- [ ] Step 3: Commit "test: no-docker round trip from traced example app to triage report".

### Task 12: skill format and hygiene tests

**Files:**
- Test: `tests/test_skill_format.py` (every skills/*/SKILL.md: frontmatter parses as YAML, has name matching folder and description under 1024 chars containing "Use when"; every relative file referenced in the body exists)
- Test: `tests/test_hygiene.py` (no U+2014 em dash in any tracked file; no "agent-ops" residue)

- [ ] Step 1: Write both tests, run, fix any violations they surface.
- [ ] Step 2: Commit "test: skill format and hygiene gates".

### Task 13: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

Jobs: lint (ruff + hygiene tests) and test (matrix 3.11/3.12, uv sync, pytest with `--cov=skills --cov=examples --cov-fail-under=90`), plus a best-effort plugin-validate step (`claude plugin validate . --marketplace` if the CLI installs, `continue-on-error: true`).

- [ ] Step 1: Write ci.yml.
- [ ] Step 2: Validate with `uv run --with pyyaml python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"` and run the exact pytest command locally, expect >= 90 percent coverage and all green.
- [ ] Step 3: Commit "ci: lint, coverage-gated tests, best-effort plugin validation".

### Task 14: README, CHANGELOG, launch summary

**Files:**
- Create: `README.md` (demo GIF placeholder at top plus exact vhs tape and commands; both install paths; 60 second quickstart; per-skill sections; tested langgraph version; trust model link)
- Create: `demo.tape` (vhs script the README references)
- Create: `CHANGELOG.md` (Keep a Changelog, 0.1.0)
- Create: `docs/launch-summary.md` (one paragraph for the post generator)

- [ ] Step 1: Write all four files. README quickstart commands must be copy-paste runnable against the repo as committed.
- [ ] Step 2: Manually execute the quickstart commands from a clean tmp clone, confirm under 60 seconds and working.
- [ ] Step 3: Run the full suite one final time plus ruff plus hygiene, all green.
- [ ] Step 4: Commit "docs: README with vhs demo script, changelog, launch summary".

### Task 15: final verification sweep

- [ ] Step 1: `uv run pytest --cov=skills --cov=examples --cov-report=term-missing --cov-fail-under=90` green.
- [ ] Step 2: `claude plugin validate . --marketplace` if available locally; otherwise note for CI.
- [ ] Step 3: Fresh-clone manual install path check: copy skills/* into a tmp dir shaped like ~/.claude/skills and confirm self-containment (verify_chain.py runs standalone).
- [ ] Step 4: Update plan checkboxes, commit "chore: final verification pass".

## Self-review

Spec coverage: naming/packaging (Task 1), chain spec and anchor default plus loud warning (Tasks 2-4), converter default mapping incl. MCP semconv (Task 5), tracing templates with file exporter enabling amendment 3 (Task 7), stack assets (Task 8), pinned langgraph example (Task 9), eval scaffold with determinism proof (Task 10), round-trip golden test (Task 11), format and em dash gates (Task 12), CI (Task 13), README/vhs/CHANGELOG/launch summary (Task 14). Types checked: compute_hash(prev_hash, body, key) is used identically in Tasks 2 and 3; converter output fields match the triage TraceEvent schema consumed in Task 11; traced_node attribute names match the converter default mapping in Task 5.
