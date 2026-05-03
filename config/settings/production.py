from .base import *
from config.observability.logging import LOGGING as BASE_LOGGING
import copy
import os
# 환경변수는 K8s Secret / ConfigMap에서 주입.

LOGGING = copy.deepcopy(BASE_LOGGING)
LOGGING["loggers"]["app"]["level"] = os.getenv("APP_LOG_LEVEL", "INFO")
LOGGING["root"]["level"] = os.getenv("LOG_LEVEL", "WARNING")