from rest_framework import generics
from .models import AuditLog
from .serializers import AuditLogSerializer
from rest_framework.permissions import IsAuthenticated

class AuditLogListView(generics.ListAPIView):

    """
    GET /api/audit-logs/
    
    - 관리자(is_staff=True) → 전체 조회
    - 일반 사용자 → 본인 기록만 조회
    """

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        user = self.request.user

        queryset = AuditLog.objects.select_related('user').order_by('-created_at')

        # 관리자면 전체 조회, 일반 사용자는 본인 기록만 조회
        if user.is_staff:
            return queryset
        
        return queryset.filter(user=user)

