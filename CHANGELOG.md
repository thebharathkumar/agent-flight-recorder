# Changelog

All notable changes to this project are documented in this file. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-05

### Added

- `audit-log` skill: stdlib-only hash-chained HMAC audit logger
  (`chained_log.py`), verifier with truncation anchor enforcement and tamper
  demo (`verify_chain.py`), LangGraph and plain Python integration templates.
- `otel-agent-tracing` skill: SDK setup template with an OTLP JSON file
  exporter, LangGraph per-node span wrapper, docker compose stack with OTel
  Collector, Jaeger, and preprovisioned Grafana, plus references covering a
  5 minute first-trace walkthrough, the semantic convention vocabulary, and
  a Weaver conformance loop.
- `agent-eval-scaffold` skill: golden-file pytest harness templates with
  seed pinning, JSONL dataset format, and a PR-gating GitHub Actions
  workflow.
- `trace-triage` skill: stdlib-only OTLP JSON to agent-triage NDJSON
  converter with default mapping for pack-emitted and MCP semconv spans,
  turn synthesis, and exception-based failure classification.
- `examples/two-agent-app`: deterministic two-agent LangGraph app with a
  scripted stub LLM and seeded failure injection, used by the quickstart
  and the round-trip CI test.
- Plugin and marketplace manifests: install via
  `/plugin marketplace add thebharathkumar/agent-flight-recorder` or copy
  skill folders manually.
- Test suite at 97 percent coverage over skill scripts and the example app,
  including a no-docker round-trip test (traced app to converter to triage
  report golden) and repo-wide hygiene gates.
