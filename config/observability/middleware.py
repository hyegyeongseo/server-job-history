"""
Request 자동 계측 미들웨어.

1) RequestIDMiddleware: 모든 요청에 고유 ID 부여
2) RequestLogMiddleware: 요청 완료 시 메서드/경로/상태/지연 기록 + 403 카운트
"""
import logging
import uuid
import time
from .logging import request_id_var, logger
from .metrics import FORBIDDEN_REQUESTS_TOTAL


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

            # 403 → forbidden_requests_total{path, role}
            #   - DRF 권한 거부와 destroy/restore의 수동 Response(403)을 둘 다 포착(미들웨어라서).
            #   - path 라벨은 resolver_match.route(=URL 패턴, 예 'api/servers/<pk>/restore/')를 써서
            #     ID가 라벨에 박혀 카디널리티가 폭발하는 것을 방지. role 없으면 'anonymous'.
            if status == 403:
                route = getattr(getattr(request, "resolver_match", None), "route", None) or request.path
                role = getattr(request.user, "role", "anonymous")
                FORBIDDEN_REQUESTS_TOTAL.labels(path=route, role=role).inc()