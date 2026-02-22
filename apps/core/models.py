from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):

    class Role(models.TextChoices):
        ADMIN = 'admin', '시스템 관리자'
        OPERATOR = 'operator', '운영자'
        VIEWER = 'viewer', '관찰자'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VIEWER,
    )

    class Meta:
        db_table = 'users'
