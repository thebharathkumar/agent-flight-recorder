"""Convert OTLP JSON trace exports into agent-triage NDJSON events. Stdlib only.

Usage:
    python otlp_to_triage.py <otlp.json> [-o events.ndjson] [--map mapping.toml]

Input: real OTLP JSON as written by collector file exporters or the protobuf JSON
encoding (resourceSpans -> scopeSpans -> spans, attributes as key/value lists).
Accepts a single JSON document or one document per line (JSONL).

The DEFAULT mapping recognizes everything the otel-agent-tracing skill emits,
including MCP semantic conventions (mcp.method.name, span names shaped like
"{mcp.method.name} {target}"), so pack-emitted spans need no --map. For foreign
attribute layouts, pass --map mapping.toml (see references/attribute-mapping.md).
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ATTRIBUTES = {
    "agent_id": ["agent.id", "agent_id"],
    "run_id": ["run.id", "run_id"],
    "turn": ["turn"],
    "tool": ["action.tool", "tool_name"],
    "classification": ["failure.classification", "failure_classification"],
}

# exception.type -> triage failure_classification, applied to failed spans
# that carry no explicit classification attribute
DEFAULT_EXCEPTION_MAP = {
    "TimeoutError": "information_lag",
    "asyncio.TimeoutError": "information_lag",
    "ConnectionError": "environment_constraint",
    "OSError": "environment_constraint",
    "PermissionError": "environment_constraint",
    "ValueError": "agent_error",
    "TypeError": "agent_error",
    "KeyError": "agent_error",
}

ERROR_STATUS = {2, "2", "STATUS_CODE_ERROR", "ERROR"}


def _attr_value(value: dict):
    for key, cast in (("stringValue", str), ("boolValue", bool), ("doubleValue", float)):
        if key in value:
            return cast(value[key])
    if "intValue" in value:
        return int(value["intValue"])
    if "arrayValue" in value:
        return [_attr_value(v) for v in value["arrayValue"].get("values", [])]
    return None


def _flatten_attributes(kv_list: list | None) -> dict:
    return {kv["key"]: _attr_value(kv.get("value", {})) for kv in (kv_list or [])}


def _first(attrs: dict, names: list[str]):
    for name in names:
        if name in attrs and attrs[name] is not None:
            return attrs[name]
    return None


def _load_mapping(mapping_path: str | Path | None) -> tuple[dict, dict]:
    attributes = {k: list(v) for k, v in DEFAULT_ATTRIBUTES.items()}
    exceptions = dict(DEFAULT_EXCEPTION_MAP)
    if mapping_path:
        with open(mapping_path, "rb") as fh:
            overrides = tomllib.load(fh)
        for key, names in overrides.get("attributes", {}).items():
            attributes[key] = list(names) + attributes.get(key, [])
        exceptions.update(overrides.get("classification_from_exception", {}))
    return attributes, exceptions


def _iter_spans(doc: dict):
    for resource_spans in doc.get("resourceSpans", []):
        resource_attrs = _flatten_attributes(
            resource_spans.get("resource", {}).get("attributes")
        )
        for scope_spans in resource_spans.get("scopeSpans", []):
            for span in scope_spans.get("spans", []):
                yield resource_attrs, span


def _classify(span: dict, attrs: dict, attr_map: dict, exception_map: dict) -> str | None:
    explicit = _first(attrs, attr_map["classification"])
    if explicit:
        return explicit
    for event in span.get("events", []):
        if event.get("name") == "exception":
            exc_type = _flatten_attributes(event.get("attributes")).get("exception.type", "")
            for known, classification in exception_map.items():
                if exc_type == known or exc_type.endswith("." + known):
                    return classification
            return "agent_error"
    return None


def _tool_name(span: dict, attrs: dict, attr_map: dict) -> tuple[str, str | None]:
    """Returns (tool_name, mcp_method). MCP span names look like '{method} {target}'."""
    explicit = _first(attrs, attr_map["tool"])
    if explicit:
        return str(explicit), attrs.get("mcp.method.name")
    name = span.get("name", "unknown")
    mcp_method = attrs.get("mcp.method.name")
    if mcp_method and name.startswith(str(mcp_method) + " "):
        return name[len(str(mcp_method)) + 1 :], str(mcp_method)
    return name, str(mcp_method) if mcp_method else None


def convert(
    doc: dict, mapping_path: str | Path | None = None
) -> tuple[list[dict], int]:
    """Convert one OTLP JSON document. Returns (events, skipped_span_count)."""
    attr_map, exception_map = _load_mapping(mapping_path)
    raw = []
    skipped = 0
    for resource_attrs, span in _iter_spans(doc):
        if not span.get("spanId"):
            skipped += 1
            continue
        attrs = {**resource_attrs, **_flatten_attributes(span.get("attributes"))}
        start = int(span.get("startTimeUnixNano", 0))
        end = int(span.get("endTimeUnixNano", start))
        status_code = (span.get("status") or {}).get("code", 0)
        succeeded = status_code not in ERROR_STATUS
        tool, mcp_method = _tool_name(span, attrs, attr_map)
        event = {
            "event_id": span["spanId"],
            "run_id": str(
                _first(attrs, attr_map["run_id"]) or span.get("traceId") or "otlp-default"
            ),
            "agent_id": str(
                _first(attrs, attr_map["agent_id"]) or attrs.get("service.name") or "unknown"
            ),
            "timestamp": datetime.fromtimestamp(start / 1e9, tz=timezone.utc).isoformat(),
            "action_taken": {"tool_name": tool},
            "action_succeeded": succeeded,
            "failure_classification": (
                None if succeeded else _classify(span, attrs, attr_map, exception_map)
            ),
            # agent-triage's schema wants whole milliseconds
            "latency_ms": {"total": int(round((end - start) / 1e6))},
        }
        if mcp_method:
            event["mcp_method"] = mcp_method
        raw.append((start, _first(attrs, attr_map["turn"]), event))

    # synthesize turn from span start order per (run, agent) when absent
    raw.sort(key=lambda item: item[0])
    counters: dict[tuple[str, str], int] = {}
    events = []
    for _, explicit_turn, event in raw:
        key = (event["run_id"], event["agent_id"])
        ordinal = counters.get(key, 0)
        counters[key] = ordinal + 1
        event["turn"] = int(explicit_turn) if explicit_turn is not None else ordinal
        events.append(event)
    return events, skipped


def _load_docs(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    try:
        return [json.loads(text)]
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("otlp_file", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("events.ndjson"))
    parser.add_argument("--map", dest="mapping", type=Path, default=None)
    args = parser.parse_args()

    events: list[dict] = []
    skipped = 0
    for doc in _load_docs(args.otlp_file):
        converted, doc_skipped = convert(doc, mapping_path=args.mapping)
        events.extend(converted)
        skipped += doc_skipped

    with args.output.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")

    print(f"mapped {len(events)} spans, skipped {skipped}", file=sys.stderr)
    failed = [e for e in events if not e["action_succeeded"]]
    unclassified = [e for e in failed if not e["failure_classification"]]
    if failed and len(unclassified) > len(failed) / 2:
        print(
            f"warning: {len(unclassified)} of {len(failed)} failures are unclassified; "
            "triage scoring degrades without failure labels (see "
            "references/attribute-mapping.md for --map)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
