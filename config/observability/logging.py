"""
JSON Structured Logging + trace_id/request_id correlation.

사용법:
    from config.observability.logging import logger
    logger.info("server created", extra={"server_id": 1})
"""
import logging
import contextvars
from pythonjsonlogger import jsonlogger
from opentelemetry import trace

# Context Variable: 요청 단위 ID
request_id_var = contextvars.ContextVar("request_id", default=None)


class TraceFilter(logging.Filter):
    # 모든 로그 레코드에 trace_id, span_id, request_id를 주입.

    def filter(self, record):
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = None
            record.span_id = None
        record.request_id = request_id_var.get()
        return True


class HealthCheckFilter(logging.Filter):
    # Health check 경로의 로그를 제외 — 로그 볼륨 절감.
    def filter(self, record):
        msg = record.getMessage()
        if any(path in msg for path in ["/health/liveness", "/health/readiness"]):
            return False
        return True


# Logger 인스턴스 (다른 모듈에서 import)
logger = logging.getLogger("app")


# LOGGING dict — settings.py에서 import하여 적용
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "trace_filter": {"()": TraceFilter},
        "health_filter": {"()": HealthCheckFilter},
    },
    "formatters": {
        "json": {
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": (
                "%(asctime)s %(levelname)s %(name)s %(message)s "
                "%(trace_id)s %(span_id)s %(request_id)s"
            ),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["trace_filter", "health_filter"],
        },
    },
    "loggers": {
        "app": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}