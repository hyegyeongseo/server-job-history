"""
Prometheus 비즈니스 메트릭 정의.

django-prometheus가 HTTP 요청/응답의 기본 메트릭을 자동 수집하므로,
여기서는 비즈니스 도메인 메트릭만 정의합니다.
"""
from prometheus_client import Counter
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector, REGISTRY

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

# 권한 위반
FORBIDDEN_REQUESTS_TOTAL = Counter(
    "forbidden_requests_total",
    "403 Forbidden responses",
    ["path", "role"],
)

# 서버 상태 — Custom Collector (multiprocess-safe)
class ServerCountCollector(Collector):
    """매 scrape 시 DB 에서 직접 집계.

    Multiprocess 모드에서도 안전: 각 worker 가 독립적으로 DB 쿼리.
    Gauge + _metrics.clear() 방식의 stale-label 문제 없음.
    """

    def describe(self):
        """등록 시점의 name-discovery 용. DB 안 건드림.

        prometheus_client 는 REGISTRY.register() 시 describe() 가 있으면
        그걸로 메트릭 이름을 알아냅니다. 없으면 collect() 를 부르는데,
        collect() 는 Django app registry 가 준비된 후에만 안전하므로
        describe() 를 명시 제공해서 등록 시점의 DB import 트리거를 회피.
        """
        yield GaugeMetricFamily(
            "server_count_by_status",
            "Number of active servers by status and environment",
            labels=["status", "environment"],
        )

    def collect(self):
        # 지연 import — Django 앱 로딩 전 import 회피 (Counter 들과 다른 점)
        from apps.servers.models import Server
        from django.db.models import Count

        gauge = GaugeMetricFamily(
            "server_count_by_status",
            "Number of active servers by status and environment",
            labels=["status", "environment"],
        )

        try:
            results = (
                Server.objects.filter(is_deleted=False)
                .values("status", "environment")
                .annotate(count=Count("id"))
            )
            for row in results:
                gauge.add_metric(
                    [row["status"], row["environment"] or "unknown"],
                    row["count"],
                )
        except Exception:
            # DB 미준비 / 마이그레이션 직전에 /metrics 가 죽으면 안 됨
            pass

        yield gauge


REGISTRY.register(ServerCountCollector())