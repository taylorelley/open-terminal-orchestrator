"""OpenTelemetry trace propagation setup.

Instruments FastAPI and httpx so that trace context (``traceparent`` /
``tracestate`` headers) is propagated from incoming Open WebUI requests
through the orchestrator to sandbox HTTP calls.

Enabled only when ``settings.otel_enabled`` is ``True``.
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def setup_telemetry() -> None:
    """Configure the OpenTelemetry SDK, exporter, and auto-instrumentation.

    Call once during application startup.  A no-op when ``otel_enabled`` is False.
    """
    if not settings.otel_enabled:
        logger.debug("OpenTelemetry disabled — skipping setup")
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI (picks up the app on first request).
    FastAPIInstrumentor.instrument()

    # Auto-instrument httpx so proxy calls to sandboxes propagate trace context.
    HTTPXClientInstrumentor().instrument()

    logger.info(
        "OpenTelemetry enabled — exporting to %s as '%s'",
        settings.otel_endpoint,
        settings.otel_service_name,
    )


def shutdown_telemetry() -> None:
    """Flush and shut down the tracer provider if OTel is active."""
    if not settings.otel_enabled:
        return

    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()
        logger.info("OpenTelemetry shut down")
