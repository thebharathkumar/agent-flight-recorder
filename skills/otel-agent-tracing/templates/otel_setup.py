"""OpenTelemetry SDK setup for agent processes. Copy into your project.

configure_otel() wires a TracerProvider with:
- an OTLP gRPC exporter when an endpoint is configured (OTEL_EXPORTER_OTLP_ENDPOINT
  env var or the otlp_endpoint argument), for the docker collector stack
- an OTLP JSON file exporter when file_export_path (or the OTEL_FILE_EXPORT env
  var) is set, writing one {"resourceSpans": [...]} JSON line per batch, the same
  shape a collector file exporter produces. The trace-triage skill consumes this
  directly, no collector or docker needed.

Call it once at startup. The provider is registered globally (first caller wins)
and flushed at interpreter exit.
"""

from __future__ import annotations

import atexit
import base64
import json
import os
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

_ID_FIELDS = ("traceId", "spanId", "parentSpanId")


def _b64_ids_to_hex(node) -> None:
    """OTLP/JSON mandates hex ids; protobuf JSON encoding emits base64. Fix in place."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _ID_FIELDS and isinstance(value, str):
                node[key] = base64.b64decode(value).hex()
            else:
                _b64_ids_to_hex(value)
    elif isinstance(node, list):
        for item in node:
            _b64_ids_to_hex(item)


class OTLPJsonFileExporter(SpanExporter):
    """Append finished spans to a file as OTLP JSON lines."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, spans) -> SpanExportResult:
        request = encode_spans(spans)
        doc = MessageToDict(request)
        _b64_ids_to_hex(doc)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(doc) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def configure_otel(
    service_name: str,
    file_export_path: str | Path | None = None,
    otlp_endpoint: str | None = None,
) -> TracerProvider:
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )

    endpoint = otlp_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )

    file_path = file_export_path or os.environ.get("OTEL_FILE_EXPORT")
    if file_path:
        provider.add_span_processor(SimpleSpanProcessor(OTLPJsonFileExporter(file_path)))

    trace.set_tracer_provider(provider)
    atexit.register(provider.shutdown)
    return provider
