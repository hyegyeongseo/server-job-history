import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# OTEL 은 Phase 2 부터. 지금은 호출만 해두고 내부는 false-noop.
from config.observability.tracing import setup_tracing
setup_tracing()

from django.core.wsgi import get_wsgi_application  # asgi 면 asgi
application = get_wsgi_application()