from .base import *
from dotenv import load_dotenv
from config.observability.logging import LOGGING as BASE_LOGGING
import copy

LOGGING = copy.deepcopy(BASE_LOGGING)
LOGGING["loggers"]["app"]["level"] = "DEBUG"
LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"
LOGGING["root"]["level"] = "DEBUG"