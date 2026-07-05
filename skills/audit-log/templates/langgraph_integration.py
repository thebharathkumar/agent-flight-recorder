"""Integration pattern: hash-chained audit log inside a LangGraph graph.

Copy the relevant pieces into your project. The pattern: create one ChainedLogger
per run before invoking the graph, log one entry per node with the node name as
actor, and verify the chain after the run (or any time later).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

# Adjust this path to wherever you copied chained_log.py in your project.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from chained_log import ChainedLogger  # noqa: E402


class State(TypedDict):
    question: str
    plan: str
    answer: str


def build_graph(audit: ChainedLogger):
    """Each node appends one audit entry describing what it did and why."""

    def planner(state: State) -> dict:
        plan = f"1. research {state['question']} 2. summarize"
        audit.append(
            actor="planner",
            action="plan_created",
            payload={"question": state["question"], "plan": plan},
        )
        return {"plan": plan}

    def worker(state: State) -> dict:
        answer = f"answer for: {state['question']}"
        audit.append(
            actor="worker",
            action="answer_produced",
            payload={"plan": state["plan"], "answer": answer},
        )
        return {"answer": answer}

    graph = StateGraph(State)
    graph.add_node("planner", planner)
    graph.add_node("worker", worker)
    graph.set_entry_point("planner")
    graph.add_edge("planner", "worker")
    graph.add_edge("worker", END)
    return graph.compile()


def main() -> None:
    run_id = uuid.uuid4().hex[:12]
    audit = ChainedLogger(Path("audit") / f"{run_id}.jsonl", run_id=run_id)
    audit.append(actor="system", action="run_started", payload={"run_id": run_id})

    app = build_graph(audit)
    result = app.invoke({"question": "what changed in the release?", "plan": "", "answer": ""})

    audit.append(actor="system", action="run_finished", payload={"answer": result["answer"]})
    print(f"run {run_id} complete, audit log at audit/{run_id}.jsonl")
    print(f"verify with: python verify_chain.py audit/{run_id}.jsonl")


if __name__ == "__main__":
    main()
