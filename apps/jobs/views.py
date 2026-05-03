from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from .models import Job
from .serializers import JobSerializer
from apps.core.permissions import JobPermission
from apps.audit.utils import create_audit_log
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .serializers import JobSerializer, JobUpdateSerializer
from config.observability.logging import logger
from config.observability.metrics import JOB_CREATED_TOTAL, JOB_UPDATED_TOTAL
from opentelemetry import trace

class JobViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'put']  # DELETE 제외
    queryset = Job.objects.filter(
        server__is_deleted=False
    ).select_related("server", "created_by").order_by("-created_at")
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, JobPermission]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_fields = {
        "server__name": ["exact"],
        "server": ["exact"],            
        "action_type": ["exact"],     
        "status": ["exact"],         
        "created_by": ["exact"],    
        "performed_by": ["exact"],       
    }

    search_fields = ["description", "performed_by", "server__name"]  # 부분 검색
    ordering_fields = [
        "id",
        "created_at",
        "started_at",
        "ended_at",
        "status",
        "action_type",
    ]  
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return JobUpdateSerializer
        return JobSerializer

    # 작업 생성(신규/정정/추가)
    def perform_create(self, serializer):
        previous_job = serializer.validated_data.get("previous_job", None)

        with transaction.atomic():
            # 이전 Job이 있으면 root_job 그대로 가져오기
            if previous_job:
                job = serializer.save(
                    created_by=self.request.user,
                    previous_job=previous_job,
                    root_job=previous_job.root_job,
                    
                )
            else:
                # 신규 root_job인 경우, 일단 None으로 저장 후 update
                job = serializer.save(created_by=self.request.user)
                job.root_job = job
                job.save(update_fields=["root_job"])

            # Observability

            span = trace.get_current_span()
            if span and span.is_recording():
                span.set_attribute("server.environment", job.server.environment)

            JOB_CREATED_TOTAL.labels(action_type=job.action_type, environment=job.server.environment).inc()
            logger.info("job created", extra={
                "job_id": job.id,
                "server_id": job.server_id,
                "environment": job.server.environment,
                "action_type": job.action_type,
                "is_correction": previous_job is not None,
            })

            create_audit_log(
                user=self.request.user,
                action="create",
                target_type="jobs",
                target_id=job.id,
                description=f"Job created: {job.action_type} ({job.status})"
            )

    def perform_update(self, serializer):
        """
        작업 수정 + 감사 로그 기록
        30분 제한은 serializer에서 이미 방어
        """
        with transaction.atomic():
            instance = self.get_object()

            old_data = {
                field: getattr(instance, field)
                for field in serializer.validated_data.keys()
            }

            updated_instance = serializer.save()

            changes = []
            for field, old_value in old_data.items():
                new_value = getattr(updated_instance, field)

                if str(old_value) != str(new_value):
                    changes.append(
                        f"{field}: {old_value} -> {new_value}"
                    )

            description = "; ".join(changes) if changes else "No changes"

            JOB_UPDATED_TOTAL.labels(
                action_type=updated_instance.action_type,
                environment=updated_instance.server.environment
            ).inc()
            logger.info("job updated", extra={
                "job_id": updated_instance.id,
                "changes": description,
            })

            create_audit_log(
                user=self.request.user,
                action="update",
                target_type="jobs",
                target_id=updated_instance.id,
                description=description,
            )  
    
    # Chain Job 조회
    @action(detail=True, methods=["get"])
    def chain(self, request, pk=None):
        job = self.get_object()

        chain = Job.objects.filter(
            root_job=job.root_job,
            server__is_deleted=False
        ).select_related("server", "created_by").order_by("created_at")

        serializer = self.get_serializer(chain, many=True)
        return Response(serializer.data)
