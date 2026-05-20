from .base import *  # noqa: F401,F403
from config.observability.logging import LOGGING as BASE_LOGGING
import copy

DEBUG = True
ALLOWED_HOSTS = ['*']

LOGGING = copy.deepcopy(BASE_LOGGING)
LOGGING["loggers"]["app"]["level"] = "DEBUG"
LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"
LOGGING["root"]["level"] = "DEBUG"