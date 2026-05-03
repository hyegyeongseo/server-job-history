# syntax=docker/dockerfile:1.7
# =========================
# Stage 1: builder
# =========================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 빌드에 필요한 시스템 패키지
# (psycopg2-binary는 wheel이라 불필요하지만 grpcio가 환경에 따라 빌드를 시도할 수 있음)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# venv 생성
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 의존성만 먼저 설치 (레이어 캐시 활용)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt


# =========================
# Stage 2: runtime
# =========================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prom_metrics \
    PORT=8000

# 런타임 OS 패키지 (시간대 + healthcheck용 curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tzdata \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 비루트 사용자 (uid 1000 고정 — K8s securityContext와 매칭)
RUN groupadd --system --gid 1000 app && \
    useradd  --system --uid 1000 --gid app --home-dir /app --shell /sbin/nologin app

# 빌더에서 venv만 복사
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Prometheus multiproc 디렉토리
# K8s에서는 emptyDir로 덮어씌우지만 docker run 단독 실행 시에도 동작하도록 미리 생성
RUN mkdir -p /tmp/prom_metrics && chown app:app /tmp/prom_metrics

# 앱 코드 복사 (가장 자주 바뀌므로 마지막 레이어)
COPY --chown=app:app . /app

USER app

EXPOSE 8000

# K8s에서는 liveness/readiness probe로 대체. docker run 단독 디버깅용.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/liveness/ || exit 1

# exec form → PID 1 = gunicorn
# K8s rolling update 시 SIGTERM이 gunicorn에 직접 전달되어야 graceful shutdown이 동작
CMD ["gunicorn", "-c", "gunicorn.conf.py", "config.wsgi:application"]
