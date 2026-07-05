---
name: audit-log
description: Add a tamper-evident, hash-chained HMAC audit log to an agent
  project, or verify an existing chain. Use when the user asks for an audit
  trail, tamper-evident or compliance logging, run provenance, or wants to
  prove that an agent run log was not modified after the fact.
---

# Audit Log

Gives an agent project an append-only audit trail where every entry is
HMAC-chained to the previous one. Any modification, deletion, insertion, or
reordering of past entries breaks the chain. A head anchor, written on every
append by default, makes truncation from the tail detectable too.

## Record format

One JSONL file per run (default `audit/<run_id>.jsonl`). Entry fields:
`seq`, `ts`, `run_id`, `actor`, `action`, `payload`, `prev_hash`,
`entry_hash`. The hash covers every field except `entry_hash` itself:

    entry_hash = HMAC_SHA256(key, prev_hash + canonical_json(body))

Canonical JSON: sorted keys, compact separators, `default=str`. Genesis
`prev_hash` is 64 zeros. Each append also rewrites `<log>.head.json`
(`{"count": N, "head_hash": "..."}`), the anchor used to detect truncation.

## Procedure

1. Copy `scripts/chained_log.py` into the target project (for example
   `<project>/audit/chained_log.py`). It is stdlib-only, no dependencies.
2. Ensure `AUDIT_CHAIN_KEY` is set in the environment. Never hardcode it.
   The script falls back to a built-in dev key with a loud stderr warning;
   tell the user that key is for local experiments only.
3. Integrate at the points where the agent acts:
   - LangGraph: follow `templates/langgraph_integration.py`. Create one
     `ChainedLogger` per run before graph invocation, log one entry per
     node with `actor=<node name>`, `action=<what happened>`, and a
     payload containing the inputs and outputs worth auditing.
   - Plain Python: follow `templates/plain_python.py`. Log one entry per
     tool call or state change, including failures.
4. Smoke test: run the agent once, confirm the JSONL file and the
   `.head.json` anchor exist and that the anchor count matches the line
   count.
5. Prove integrity: `python scripts/verify_chain.py audit/<run_id>.jsonl`.
   It recomputes every hash and checks the anchor. Exit 0 means intact;
   exit 1 means a broken chain with a line-numbered diagnosis; exit 2
   means an anchor mismatch. To demonstrate detection, run
   `--demo-tamper` on a COPY of the log and show the failure output.
6. If no anchor file is present, verification still runs but prints a
   prominent warning that truncation cannot be ruled out; it never passes
   silently. Use `--require-anchor` to turn that into a hard failure.
7. Explain the trust model to the user (below). Do not overclaim.

## Trust model

Detected: any edit to a logged entry, deleted or inserted entries,
reordering, and truncation from the tail (via the head anchor). Not
detected: an attacker who has both write access to the log and the HMAC
key can rebuild the whole chain. Keep the key out of the repo, and for
strong truncation protection store the head anchor (or just its
`head_hash`) somewhere log writers cannot touch, such as a CI artifact or
a separate store.

## Files

- `scripts/chained_log.py`: `ChainedLogger` class, `append()`, head anchor.
- `scripts/verify_chain.py`: CLI verifier and importable `verify()`. Flags:
  `--key-env`, `--require-anchor`, `--demo-tamper`.
- `templates/langgraph_integration.py`: per-node logging in a LangGraph app.
- `templates/plain_python.py`: logging around plain tool calls.
