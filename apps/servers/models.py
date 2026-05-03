from django.db import models
from django.conf import settings

STATUS_CHOICES = [
    # 정상 상태
    ('online', '운영 중'),
    ('standby', '대기 중'),

    # 전환/작업 상태
    ('provisioning', '구성 중'),
    ('maintenance', '유지보수 중'),
    ('rebooting', '재부팅 중'),

    # 장애/비정상 상태
    ('down', '서비스 중단'),
    ('unreachable', '통신 불가'),

    # 종료/폐기 상태
    ('offline', '전원 꺼짐'),
    ('decommissioned', '폐기됨'),
]

ENVIRONMENT_CHOICES = [
    ('prod', '운영 환경'),
    ('stg', '스테이징 환경'),
    ('dev', '개발 환경'),
]

class Server(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    ip_address = models.GenericIPAddressField(unique=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='online')
    environment = models.CharField(
        max_length=10,
        choices=ENVIRONMENT_CHOICES,
        db_index=True,               
    )
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.ip_address})"

