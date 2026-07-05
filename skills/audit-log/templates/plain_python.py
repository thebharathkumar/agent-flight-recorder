"""Integration pattern: hash-chained audit log around plain Python tool calls.

Copy the relevant pieces into your project. Log one entry per tool call or state
change: the actor is whoever acted, the action is what happened, the payload is
whatever you would need to reconstruct or dispute the event later.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

# Adjust this path to wherever you copied chained_log.py in your project.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from chained_log import ChainedLogger  # noqa: E402


def call_tool(audit: ChainedLogger, agent: str, tool: str, args: dict) -> dict:
    """Wrap every tool call so both attempt and outcome land in the chain."""
    audit.append(actor=agent, action="tool_call_started", payload={"tool": tool, "args": args})
    try:
        result = {"status": "ok", "data": f"{tool} result"}  # your real tool call here
    except Exception as exc:
        audit.append(
            actor=agent,
            action="tool_call_failed",
            payload={"tool": tool, "error": repr(exc)},
        )
        raise
    audit.append(actor=agent, action="tool_call_finished", payload={"tool": tool, "result": result})
    return result


def main() -> None:
    run_id = uuid.uuid4().hex[:12]
    audit = ChainedLogger(Path("audit") / f"{run_id}.jsonl", run_id=run_id)

    audit.append(actor="system", action="run_started", payload={})
    call_tool(audit, agent="researcher", tool="web_search", args={"query": "release notes"})
    call_tool(audit, agent="writer", tool="save_draft", args={"path": "draft.md"})
    audit.append(actor="system", action="run_finished", payload={})

    print(f"audit log at audit/{run_id}.jsonl")


if __name__ == "__main__":
    main()
