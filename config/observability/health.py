"""
Kubernetes Liveness / Readiness Probe용 엔드포인트.

- liveness: 프로세스 정상 여부만 확인 (DB 체크 안 함 — cascading failure 방지)
- readiness: 트래픽 수신 가능 여부 (DB 연결 확인, 실패 시 503)
"""
from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError


def liveness(request):
    return JsonResponse({"status": "ok"})


def readiness(request):
    try:
        conn = connections["default"]
        conn.ensure_connection()
        db_ok = True
    except OperationalError:
        db_ok = False

    status_code = 200 if db_ok else 503
    return JsonResponse(
        {"status": "ok" if db_ok else "unavailable", "db": db_ok},
        status=status_code,
    )