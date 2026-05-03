"""
Request 자동 계측 미들웨어.

1) RequestIDMiddleware: 모든 요청에 고유 ID 부여
2) RequestLogMiddleware: 요청 완료 시 메서드/경로/상태/지연 기록
"""
import logging
import uuid
import time
from .logging import request_id_var, logger


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        request_id_var.set(request_id)
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class RequestLogMiddleware:
    EXCLUDE_PATHS = frozenset([
        "/health/liveness/",
        "/health/readiness/",
        "/metrics",
    ])

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in self.EXCLUDE_PATHS:
            return self.get_response(request)

        start = time.monotonic()
        response = None
        try:
            response = self.get_response(request)
            return response
        finally:
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            status = getattr(response, "status_code", 500)

            log_level = logging.ERROR if status >= 500 else (
                logging.WARNING if status >= 400 else logging.INFO
            )

            logger.log(
                log_level,
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status_code": status,
                    "latency_ms": latency_ms,
                    "user_id": getattr(request.user, "id", None),
                },
            )