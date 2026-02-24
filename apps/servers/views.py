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

class ServerViewSet(viewsets.ModelViewSet):
    serializer_class = ServerSerializer
    permission_classes = [IsAuthenticated, ServerPermission]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_fields = {
        'name': ['exact'],
        'ip_address': ['exact'],
        'status': ['exact'],
        'is_deleted': ['exact'],
    }

    search_fields = ['name', 'ip_address']
    ordering_fields = ['name', 'ip_address', 'id']

    ordering = ['-id']

    def perform_create(self, serializer):
        """
        서버 생성 + 감사 로그 기록
        트랜잭션 처리: 서버와 로그가 둘 다 성공해야 commit
        """
        with transaction.atomic():
            server = serializer.save()
            create_audit_log(
                user=self.request.user,
                action='create',
                target_type='servers',
                target_id=server.id,
                description=f'Created server {server.name} with IP {server.ip_address}'
            )
    
    def get_queryset(self):
        """
        기본: is_deleted=False 서버만 조회
        추가: ?server_name=xxx 필터 지원
        """
        # Admin은 삭제된 서버까지 포함해서 전체 리스트 조회 가능
        if self.request.user.role == User.Role.ADMIN:
            return Server.objects.all()
        
        # 그 외는 삭제 안 된 것만
        return Server.objects.filter(is_deleted=False)

    def perform_update(self, serializer):
        """
        서버 수정 + 감사 로그 기록
        변경 내용(description)에 이전 값과 새로운 값을 기록
        """
        with transaction.atomic():
            instance = self.get_object()
            
            old_data = {field: getattr(instance, field) for field in serializer.validated_data.keys()}

            updated_instance = serializer.save()

            # 변경 내용 기록
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
                description=description
            )
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        """
        서버 삭제(soft delete) + 감사 로그 기록
        """
        user_role = request.user.role

        with transaction.atomic():

            # Admin / Operator → Soft delete
            if user_role in [User.Role.ADMIN, User.Role.OPERATOR]:
                instance.is_deleted = True
                instance.save(update_fields=["is_deleted"])

                create_audit_log(
                    user=request.user,
                    action='delete',
                    target_type='servers',
                    target_id=instance.id,
                    description=f"Server '{instance.name}' deleted by {user_role} (Soft Delete)"
                )

                return Response(status=status.HTTP_204_NO_CONTENT)

            return Response(status=status.HTTP_403_FORBIDDEN)

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

            create_audit_log(
                user=request.user,
                action='restore',
                target_type='servers',
                target_id=server.id,
                description=f"Server '{server.name}' restored"
            )

        return Response(
            {"message": "서버가 복구되었습니다."},
            status=status.HTTP_200_OK
        )