"""
Gunicorn 설정.

- worker 수, timeout 등은 환경변수로 외부 주입을 우선합니다.
- access log는 RequestLogMiddleware가 JSON으로 처리하므로 비활성.
- 에러 로그는 stderr로 출력해 K8s 로그 수집기가 가져가게 합니다.
- Prometheus 멀티프로세스 모드를 위해 child_exit hook을 등록합니다.
"""
import os


# 바인딩
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Worker
workers = int(os.getenv("GUNICORN_WORKERS", "3"))
worker_class = "sync"
threads = 1

# Timeout
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = 5

# 로그 — access log는 RequestLogMiddleware가 처리
accesslog = None
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")

# 프로세스 이름
proc_name = "server-job-manager"


def child_exit(server, worker):
    """Prometheus 멀티프로세스: worker 종료 시 stale 메트릭 정리."""
    from prometheus_client import multiprocess
    multiprocess.mark_process_dead(worker.pid)


def on_starting(server):
    server.log.info(
        "Gunicorn starting (workers=%d, timeout=%ds)", workers, timeout
    )


def on_exit(server):
    server.log.info("Gunicorn shutting down")
