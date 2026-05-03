"""
Prometheus 비즈니스 메트릭 정의.

django-prometheus가 HTTP 요청/응답의 기본 메트릭을 자동 수집하므로,
여기서는 비즈니스 도메인 메트릭만 정의합니다.
"""
from prometheus_client import Counter, Gauge

# 인증
LOGIN_TOTAL = Counter(
    "login_total",
    "Total login attempts",
    ["result"],  # success | failure
)

# 작업
JOB_CREATED_TOTAL = Counter(
    "job_created_total",
    "Total jobs created",
    ["action_type", "environment"],
)

JOB_UPDATED_TOTAL = Counter(
    "job_updated_total",
    "Total job modifications (within 30min)",
    ["action_type", "environment"],
)

# 서버 상태
SERVER_COUNT_BY_STATUS = Gauge(
    "server_count_by_status",
    "Number of active servers by status",
    ["status", "environment"],
)

# 권한 위반
FORBIDDEN_REQUESTS_TOTAL = Counter(
    "forbidden_requests_total",
    "403 Forbidden responses",
    ["path", "role"],
)