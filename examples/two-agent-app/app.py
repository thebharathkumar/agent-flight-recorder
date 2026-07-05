"""Two-agent LangGraph example: a planner and a worker with injected failures.

Deterministic given --seed: the scripted LLM and the failure injection both draw
from one seeded rng, so two runs with the same arguments print identical
summaries. No API keys, no network.

Usage:
    python app.py [--runs N] [--seed S] [--audit] [--trace]

--audit writes a hash-chained audit log per run to audit/<run_id>.jsonl
        (verify with the audit-log skill's verify_chain.py)
--trace writes OTLP JSON spans to captures/otlp.json via the otel-agent-tracing
        skill's file exporter (feed it to the trace-triage skill), and honors
        OTEL_EXPORTER_OTLP_ENDPOINT for the docker Jaeger stack
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "audit-log" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "otel-agent-tracing" / "templates"))

from stub_llm import ScriptedLLM  # noqa: E402

TURNS_PER_RUN = 3
QUESTIONS = ["release notes", "error budget", "user churn"]


class InjectedFailure(Exception):
    """Base for injected failures; classification drives triage clustering."""

    classification = "agent_error"


class CoordinationFailure(InjectedFailure):
    classification = "coordination_failure"


class State(TypedDict):
    run_id: str
    turn: int
    question: str
    plan: str
    answer: str


def maybe_fail(rng: random.Random, actor: str) -> None:
    roll = rng.random()
    if actor == "worker":
        if roll < 0.12:
            raise TimeoutError("tool fetch timed out")
        if roll < 0.22:
            raise ValueError("malformed tool arguments")
    elif actor == "planner" and roll < 0.08:
        raise CoordinationFailure("planner and worker disagree on task ownership")


def build_graph(llm: ScriptedLLM, rng: random.Random, audit, wrap):
    def log(actor: str, action: str, payload: dict) -> None:
        if audit is not None:
            audit.append(actor=actor, action=action, payload=payload)

    @wrap("planner")
    def planner(state: State) -> dict:
        maybe_fail(rng, "planner")
        plan = llm.plan(state["question"])
        log("planner", "plan_created", {"turn": state["turn"], "plan": plan})
        return {"plan": plan}

    @wrap("worker")
    def worker(state: State) -> dict:
        maybe_fail(rng, "worker")
        answer = llm.answer(state["question"])
        log("worker", "answer_produced", {"turn": state["turn"], "answer": answer})
        return {"answer": answer}

    graph = StateGraph(State)
    graph.add_node("planner", planner)
    graph.add_node("worker", worker)
    graph.set_entry_point("planner")
    graph.add_edge("planner", "worker")
    graph.add_edge("worker", END)
    return graph.compile()


def run_query(question: str, seed: int = 0) -> dict:
    """Deterministic single-question entrypoint, used by the eval scaffold."""
    rng = random.Random(seed)
    llm = ScriptedLLM(rng)
    return {"plan": llm.plan(question), "answer": llm.answer(question)}


def make_wrapper(tracing: bool):
    if not tracing:
        return lambda node_name: (lambda fn: fn)
    from langgraph_tracing import traced_node

    def wrap(node_name: str):
        return traced_node(graph_name="twoagent", node_name=node_name, agent_id=node_name)

    return wrap


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()

    if args.trace:
        from otel_setup import configure_otel

        configure_otel("two-agent-app", file_export_path=Path("captures") / "otlp.json")
    wrap = make_wrapper(args.trace)

    rng = random.Random(args.seed)
    llm = ScriptedLLM(rng)

    for i in range(args.runs):
        run_id = f"run-{i:03d}"
        audit = None
        if args.audit:
            from chained_log import ChainedLogger

            audit = ChainedLogger(Path("audit") / f"{run_id}.jsonl", run_id=run_id)
            audit.append(actor="system", action="run_started", payload={"seed": args.seed})

        app = build_graph(llm, rng, audit, wrap)
        outcomes = []
        for turn in range(TURNS_PER_RUN):
            question = QUESTIONS[turn % len(QUESTIONS)]
            state = {"run_id": run_id, "turn": turn, "question": question,
                     "plan": "", "answer": ""}
            try:
                app.invoke(state)
                outcomes.append(f"turn{turn}=ok")
            except Exception as exc:
                classification = getattr(exc, "classification", None) or {
                    TimeoutError: "information_lag",
                    ValueError: "agent_error",
                }.get(type(exc), "agent_error")
                if audit is not None:
                    audit.append(
                        actor="system",
                        action="node_failed",
                        payload={"turn": turn, "error": repr(exc),
                                 "classification": classification},
                    )
                outcomes.append(f"turn{turn}=FAIL({classification})")
        if audit is not None:
            audit.append(actor="system", action="run_finished", payload={})
        print(f"{run_id} " + " ".join(outcomes))

    if args.audit:
        print("audit logs in audit/, verify with verify_chain.py", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
