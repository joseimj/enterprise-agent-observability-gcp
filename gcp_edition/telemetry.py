"""OpenTelemetry service spans; export is opt-in until collector is configured."""
import logging
import os
from opentelemetry import trace

LOG = logging.getLogger(__name__)

def setup(app):
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
    if endpoint:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        provider=TracerProvider(resource=Resource.create({'service.name':'enterprise-agent-gcp'}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    LOG.info('Tracing configured; OTLP export active=%s',bool(endpoint))
