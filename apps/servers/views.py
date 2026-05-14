from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db import transaction
from apps.core.models import User
from apps.core.permissions import ServerPermission
from .models import Server
from .serializers import ServerSerializer
from apps.audit.utils import create_audit_log
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import action
from config.observability.logging import logger
from config.observability.metrics import SERVER_COUNT_BY_STATUS
from django.db.transaction import on_commit
from opentelemetry import trace

class ServerViewSet(viewsets.ModelViewSet):
    serializer_class = ServerSerializer
    permission_classes = [IsAuthenticated, ServerPermission]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_fields = {
        'name': ['exact'],
        'ip_address': ['exact'],
        'status': ['exact'],
        'environment': ['exact', 'in'],
        'is_deleted': ['exact'],
    }

    search_fields = ['name', 'ip_address']
    ordering_fields = ['name', 'ip_address', 'id']

    ordering = ['-id']

    # Gauge 전체 리셋 후 재집계
    def _refresh_server_gauge(self):
        from django.db.models import Count
        SERVER_COUNT_BY_STATUS._metrics.clear()
        qs = Server.objects.filter(is_deleted=False) \
            .values("status", "environment") \
            .annotate(cnt=Count("id"))
        for row in qs:
            SERVER_COUNT_BY_STATUS.labels(
                status=row["status"],
                environment=row["environment"],
            ).set(row["cnt"])

    def perform_create(self, serializer):
        """
        서버 생성 + 감사 로그 기록
        트랜잭션 처리: 서버와 로그가 둘 다 성공해야 commit
        """
        with transaction.atomic():
            server = serializer.save()

            # trace 속성 추가
            span = trace.get_current_span()
            if span and span.is_recording():
                span.set_attribute("server.environment", server.environment)

            logger.info("server created", extra={
                "server_id": server.id,
                "server_name": server.name,
                "ip_address": server.ip_address,
                "environment": server.environment,
            })

            create_audit_log(
                user=self.request.user,
                action='create',
                target_type='servers',
                target_id=server.id,
                description=(
                    f'Created server {server.name} '
                    f'({server.environment}) with IP {server.ip_address}'
                ),
            )

            on_commit(lambda: self._refresh_server_gauge())

    
    def get_queryset(self):
        """
        기본: is_deleted=False 서버만 조회
        추가: ?server_name=xxx 필터 지원
        """

        # Swagger 대응
        if getattr(self, "swagger_fake_view", False):
            return Server.objects.none()
        
        # Admin은 삭제된 서버까지 포함해서 전체 리스트 조회 가능
        if self.request.user.role == User.Role.ADMIN:
            return Server.objects.all()
        
        # 그 외는 삭제 안 된 것만
        return Server.objects.filter(is_deleted=False)

    def perform_update(self, serializer):       
        with transaction.atomic():
            instance = serializer.instance # ← DB 조회 없이 기존 객체 사용
            old_data = {field: getattr(instance, field) for field in serializer.validated_data.keys()}
            updated_instance = serializer.save()

            # trace 속성 추가
            span = trace.get_current_span()
            if span and span.is_recording():
                span.set_attribute("server.environment", updated_instance.environment)

            logger.info("server updated", extra={
                "server_id": updated_instance.id,
                "changed_fields": list(serializer.validated_data.keys()),
            })

            # 변경 내용에 이전 값과 새로운 값을 기록
            changes = []
            for field, old_value in old_data.items():
                new_value = getattr(updated_instance, field)
                if old_value != new_value:
                    changes.append(f"{field}: {old_value} -> {new_value}")
            description = "; ".join(changes) if changes else "No changes"

            create_audit_log(
                user=self.request.user,
                action='update',
                target_type='servers',
                target_id=updated_instance.id,
                description=description,
            )

            on_commit(lambda: self._refresh_server_gauge())
    
    def destroy(self, request, *args, **kwargs):       
        """
        서버 삭제(soft delete) + 감사 로그 기록
        """
        instance = self.get_object()
        user_role = request.user.role

        if user_role not in [User.Role.ADMIN, User.Role.OPERATOR]:
            return Response(status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():

            # Admin / Operator → Soft delete
            instance.is_deleted = True
            instance.save(update_fields=["is_deleted"])

            logger.info("server soft-deleted", extra={"server_id": instance.id})

            create_audit_log(
                user=request.user,
                action='delete',
                target_type='servers',
                target_id=instance.id,
                description=f"Server '{instance.name}' deleted by {user_role} (Soft Delete)"
            )

            on_commit(lambda: self._refresh_server_gauge())

        return Response(status=status.HTTP_204_NO_CONTENT)

            
    # 서버 복구 (Soft Delete -> Restore) 
    @action(detail=True, methods=['patch'], url_path='restore')
    def restore(self, request, pk=None):
        server = self.get_object()

        if not server.is_deleted:
            return Response(
                {"message": "이미 활성 상태입니다."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.user.role != User.Role.ADMIN:
            return Response(
                {"message": "복구는 관리자만 가능합니다."},
                status=status.HTTP_403_FORBIDDEN
            )

        with transaction.atomic():
            server.is_deleted = False
            server.save(update_fields=["is_deleted"])

            logger.info("server restored", extra={"server_id": server.id})

            create_audit_log(
                user=request.user,
                action='restore',
                target_type='servers',
                target_id=server.id,
                description=f"Server '{server.name}' restored"
            )

            on_commit(lambda: self._refresh_server_gauge())

        return Response(
            {"message": "서버가 복구되었습니다."},
            status=status.HTTP_200_OK
        )