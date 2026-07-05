---
name: agent-eval-scaffold
description: Generate an evals directory for an agent repo with a
  deterministic pytest harness, fixed seeds, golden files, a JSONL dataset
  format, and a GitHub Actions CI gate. Use when the user asks to add evals,
  regression tests for agent behavior, golden or snapshot testing for an
  agent, or a CI quality gate on agent output.
---

# Agent Eval Scaffold

Generates a self-contained `evals/` directory in the target repo. The
harness runs dataset cases through the user's agent deterministically and
compares normalized output against committed golden files. CI fails the PR
when goldens drift.

## Procedure

1. Locate the agent entrypoint: the function or graph invocation that takes
   an input and returns a result. If ambiguous, ask the user which callable
   the evals should exercise.
2. Materialize `evals/` in the target repo from the bundled templates:
   - `templates/harness.py` to `evals/harness.py`, then rewrite the line
     marked `EDIT ME` to import the real entrypoint. `run_case(case)` must
     call the agent with the case input and return a JSON-serializable
     result; adapt the call signature here.
   - `templates/conftest.py` to `evals/conftest.py` (seed pinning plus the
     `--update-golden` flag; it also puts the repo root on sys.path).
   - `templates/test_golden.py` to `evals/test_golden.py` unchanged.
   - `templates/smoke.jsonl` to `evals/datasets/smoke.jsonl`, then replace
     the sample cases with 3 to 5 real ones based on the project's README
     or existing tests. Fields: `id`, `input`, optional `expected`
     substring.
   - `templates/evals-README.md` to `evals/README.md`.
   - Create an empty `evals/golden/` directory.
3. Copy `templates/evals-ci.yml` to `.github/workflows/evals.yml` and
   adjust the dependency install step to match the project (requirements
   file, uv, poetry, whatever it uses).
4. Determinism check: LLM-backed agents must run with temperature 0 and a
   pinned model, or better, a recorded or stubbed model for CI. If some
   output fields still vary, strip them in `normalize()` in
   `evals/harness.py` and note it in `evals/README.md`. Do not loosen the
   golden comparison itself.
5. Seed goldens: `pytest evals/ --update-golden`, then immediately run
   `pytest evals/` twice. Two consecutive clean passes prove determinism;
   if the second pass fails, fix `normalize()` before continuing. Commit
   `evals/` including `golden/`.
6. Show the user the failure mode: change one byte in a golden file, run
   `pytest evals/`, show the drift failure, restore the file.

## Files

- `templates/harness.py`: run_case and normalize, the one file users edit.
- `templates/conftest.py`: seeds and the `--update-golden` option.
- `templates/test_golden.py`: parametrized golden comparison.
- `templates/smoke.jsonl`: dataset format example.
- `templates/evals-README.md`: docs dropped into the generated directory.
- `templates/evals-ci.yml`: PR gate workflow.
