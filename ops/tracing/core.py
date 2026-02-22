"""
WATCHTOWER: OpenTelemetry core setup.
MongoDB exporter, tracer provider, and get_tracer.
"""
from datetime import datetime

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult, BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from pymongo import MongoClient


class MongoDBSpanExporter(SpanExporter):
    """
    Exports OpenTelemetry spans to MongoDB.
    Each span is stored as a document in watchtower.spans.
    """

    def __init__(self, mongodb_uri: str, database: str = "watchtower", collection: str = "spans"):
        self.client = MongoClient(mongodb_uri)
        self.collection = self.client[database][collection]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create indexes for trace_id, run_id, and time-range queries."""
        self.collection.create_index("trace_id")
        self.collection.create_index("attributes.run_id")
        self.collection.create_index([("start_time", -1)])

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        """Convert OTel spans to MongoDB documents and insert."""
        docs = []
        for span in spans:
            docs.append({
                "trace_id": format(span.context.trace_id, "032x"),
                "span_id": format(span.context.span_id, "016x"),
                "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
                "name": span.name,
                "start_time": datetime.fromtimestamp(span.start_time / 1e9),
                "end_time": datetime.fromtimestamp(span.end_time / 1e9),
                "duration_ms": (span.end_time - span.start_time) / 1e6,
                "attributes": {k: str(v) for k, v in span.attributes.items()},
                "status": "error" if span.status.is_ok is False else "ok",
            })
        if docs:
            self.collection.insert_many(docs)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def init_tracing(mongodb_uri: str, jaeger_endpoint: str | None = None, service_name: str = "arcturus"):
    """
    Initialize OpenTelemetry: set up TracerProvider and exporters.
    Call once at app startup (e.g. in api.py lifespan).
    service_name: Shown in Jaeger as the service/project name (default: arcturus).
    """
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(MongoDBSpanExporter(mongodb_uri)))
    if jaeger_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=jaeger_endpoint)))
    trace.set_tracer_provider(provider)


def get_tracer(name: str):
    """Return a tracer for the given module/component. Use this when creating spans."""
    return trace.get_tracer(name, "1.0.0")
