"""
OpenTelemetry 설정.
Django 요청 → OTLP(gRPC) → Alloy → Tempo.
"""
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor


def setup_tracing():
    if os.getenv("OTEL_TRACING_ENABLED", "true").lower() == "false":
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", "server-job-manager")
    env = os.getenv("OTEL_ENV", "production")
    endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "alloy.monitoring.svc.cluster.local:4317",
    )

    resource = Resource.create({
        "service.name": service_name,
        "deployment.environment": env,
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    DjangoInstrumentor().instrument()