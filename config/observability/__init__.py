# Collector 자동 등록을 위해 import. 다른 곳에서 metrics.py 의 심볼을 직접
# import 하지 않더라도 이 파일을 통해 부팅 시 한 번은 로딩되도록 보장.
from . import metrics