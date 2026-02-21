from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db import transaction
from .models import Server
from .serializers import ServerSerializer
from apps.audit.utils import create_audit_log
from rest_framework.permissions import IsAuthenticated

class ServerViewSet(viewsets.ModelViewSet):
    serializer_class = ServerSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """
        서버 생성 + 감사 로그 기록
        트랜잭션 처리: 서버와 로그가 둘 다 성공해야 commit
        """
        with transaction.atomic():
            server = serializer.save(created_by=self.request.user)
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
        queryset = Server.objects.filter(is_deleted=False)

        server_name = self.request.query_params.get('server_name')

        if server_name:
            queryset = queryset.filter(name__icontains=server_name)
        
        return queryset

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
    
    def perform_destroy(self, instance):
        """
        서버 삭제(soft delete) + 감사 로그 기록
        """
        with transaction.atomic():
            instance.is_deleted = True
            instance.save(update_fields=["is_deleted"])

            create_audit_log(
                user=self.request.user,
                action='delete',
                target_type='servers',
                target_id=instance.id,
                description=f'Soft deleted server {instance.name} with IP {instance.ip_address}'
            )