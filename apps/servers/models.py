from django.db import models
from django.conf import settings

STATUS_CHOICES = [
    # 정상 상태
    ('online', '운영 중'),
    ('standby', '대기 중'),

    # 전환/작업 상태
    ('provisioning', '설치/배포 중'),
    ('maintenance', '점검 중'),
    ('rebooting', '재부팅 중'),

    # 장애/비정상 상태
    ('down', '다운/장애'),
    ('unreachable', '응답 없음'),

    # 종료/폐기 상태
    ('offline', '종료'),
    ('decommissioned', '폐기'),
]

class Server(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    ip_address = models.GenericIPAddressField(unique=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='online')
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.ip_address})"

