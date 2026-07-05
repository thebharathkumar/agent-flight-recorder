"""A scripted stand-in for a model client. Deterministic given its rng.

Real projects would call an LLM here; the example keeps the quickstart free of
API keys and network access while exercising the same control flow.
"""

from __future__ import annotations

import random

PLAN_SHAPES = [
    "1. gather sources on {q} 2. draft summary",
    "1. check cache for {q} 2. fetch fresh data 3. summarize",
    "1. split {q} into subtasks 2. delegate 3. merge",
]

ANSWER_SHAPES = [
    "summary: {q} resolved with 2 sources",
    "summary: {q} resolved from cache",
    "summary: {q} needs follow-up, partial answer drafted",
]


class ScriptedLLM:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def plan(self, question: str) -> str:
        return self.rng.choice(PLAN_SHAPES).format(q=question)

    def answer(self, question: str) -> str:
        return self.rng.choice(ANSWER_SHAPES).format(q=question)
