"""Eval harness: the one file you edit.

run_case() must call your agent and return something JSON-serializable.
normalize() strips nondeterminism before golden comparison.
"""

from __future__ import annotations

import os

# EDIT ME: import your agent's entrypoint here. The default targets a project
# with app.py exposing run_query(question, seed=...) at the repo root.
from app import run_query as agent_entrypoint


def run_case(case: dict) -> dict:
    """Run one dataset case through the agent, deterministically."""
    seed = int(os.environ.get("EVAL_SEED", "0"))
    return agent_entrypoint(case["input"], seed=seed)


def normalize(result: dict) -> dict:
    """Strip fields that legitimately vary between runs (timestamps, ids,
    float noise). With a fully deterministic agent this is the identity."""
    return result
