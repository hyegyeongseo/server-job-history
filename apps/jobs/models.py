from django.db import models
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
from apps.servers.models import Server

class Job(models.Model):
    STATUS_CHOICES = [
        ("pending", "대기 중"),      # 작업 등록 후 시작 전
        ("running", "진행 중"),      # 실제 작업 수행 중
        ("completed", "완료"),       # 정상 종료
        ("failed", "실패"),          # 오류 발생
        ("canceled", "취소됨"),      # 작업 취소
    ]

    server = models.ForeignKey(Server, on_delete=models.PROTECT, related_name="jobs")

    action_type = models.CharField(max_length=50)  # 예: "backup", "update", "restart"
    description = models.TextField()  # 작업에 대한 상세 설명

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    previous_job = models.ForeignKey(    
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="next_jobs"
    )

    root_job = models.ForeignKey(
        "self",
        null=True,   
        blank=False,
        related_name="descendants",
        on_delete=models.PROTECT,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    performed_by = models.CharField(max_length=150, blank=True, null=True)

    started_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def can_edit(self):
        return timezone.now() <= self.created_at + timedelta(minutes=30)
    
    def __str__(self):
        return f"{self.action_type} - {self.status}"