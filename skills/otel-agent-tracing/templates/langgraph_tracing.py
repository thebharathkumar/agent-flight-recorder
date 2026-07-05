"""Per-node OpenTelemetry spans for LangGraph graphs. Copy into your project.

Wrap each node function with traced_node. Every node invocation becomes a span
named {graph}.{node} carrying agent identity, run id, and turn, with span status
set from exceptions. Exceptions that carry a `classification` attribute (one of
the agent-triage classes) are recorded as failure.classification so the
trace-triage skill can cluster them without extra mapping.
"""

from __future__ import annotations

import functools

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


def traced_node(graph_name: str, node_name: str, agent_id: str):
    """Decorator for a LangGraph node function (state) -> dict."""

    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(state, *args, **kwargs):
            tracer = trace.get_tracer("flight-recorder")
            with tracer.start_as_current_span(f"{graph_name}.{node_name}") as span:
                span.set_attribute("gen_ai.operation.name", "invoke_agent")
                span.set_attribute("agent.id", agent_id)
                if isinstance(state, dict):
                    if state.get("run_id") is not None:
                        span.set_attribute("run.id", str(state["run_id"]))
                    if state.get("turn") is not None:
                        span.set_attribute("turn", int(state["turn"]))
                try:
                    return fn(state, *args, **kwargs)
                except Exception as exc:
                    classification = getattr(exc, "classification", None)
                    if classification:
                        span.set_attribute("failure.classification", str(classification))
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise

        return wrapper

    return decorate
