from rest_framework import generics

from apps.core.permissions import AuditLogPermission
from .models import AuditLog
from .serializers import AuditLogSerializer
from rest_framework.permissions import IsAuthenticated

class AuditLogListView(generics.ListAPIView):

    """
    GET /api/audit-logs/
    
    - Admin → 전체 조회
    - Operator → 본인 기록만 조회
    """

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, AuditLogPermission]

    def get_queryset(self):

        user = self.request.user

        queryset = AuditLog.objects.select_related('user').order_by('-created_at')

        if user.role == user.Role.ADMIN:
            return queryset
        
        if user.role == user.Role.OPERATOR:
            return queryset.filter(user=user)
        
        return AuditLog.objects.none()

