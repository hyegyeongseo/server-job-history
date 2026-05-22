"""
테스트 전용 설정.

- DB를 in-memory SQLite로 교체 → Postgres 없이도 `manage.py test` 실행 가능.
- SECRET_KEY를 import 전에 주입 → base.py의 런타임 가드를 통과.
- 비밀번호 해셔를 빠른 것으로 교체 → 테스트 속도 개선.
- 로깅은 최소화 → 테스트 출력 깔끔하게.

실행:
    python manage.py test --settings=config.settings.test
"""
import os

# base.py는 import 시점에 DJANGO_SECRET_KEY가 없으면 RuntimeError를 던지므로,
# base를 import하기 전에 더미 키를 넣어준다. (setdefault라 실제 키가 있으면 유지)
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key")

from .base import *  # noqa: E402,F401,F403

DEBUG = False
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# 테스트 중 불필요한 로그 노이즈 제거 (기본 핸들러만 사용)
LOGGING = {"version": 1, "disable_existing_loggers": False}