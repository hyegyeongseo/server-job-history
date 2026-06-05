from .base import *
from config.observability.logging import LOGGING as BASE_LOGGING
import copy
import os
# 환경변수는 K8s Secret / ConfigMap에서 주입.

LOGGING = copy.deepcopy(BASE_LOGGING)
LOGGING["loggers"]["app"]["level"] = os.getenv("APP_LOG_LEVEL", "INFO")
LOGGING["root"]["level"] = os.getenv("LOG_LEVEL", "WARNING")

# 프록시(인그레스/게이트웨이)가 TLS 종단 → X-Forwarded-Proto로 원래 스킴 판단
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS
SECURE_HSTS_SECONDS = 31536000           # 1년
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False              # ★ preload list는 lab/미정 도메인에 위험 — 운영 확정 후에만 True

# 쿠키
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HTTP→HTTPS 리다이렉트는 env 토글
# ★ TLS 없이(NodePort/HTTP) 먼저 띄울 거면 false로 시작,
#    cert-manager(나중) 붙인 뒤 true로.
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "false").lower() == "true"