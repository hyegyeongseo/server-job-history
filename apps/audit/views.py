from rest_framework import generics
from apps.core.permissions import AuditLogPermission
from .models import AuditLog
from .serializers import AuditLogSerializer
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

class AuditLogListView(generics.ListAPIView):

    """
    GET /api/audit-logs/
    
    - Admin → 전체 조회
    - Operator → 본인 기록만 조회
    """

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, AuditLogPermission]

    # 필터링과 검색을 위한 설정
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = {
        'action': ['exact'],
        'created_at': ['date__gte', 'date__lte'], # 시작일~종료일 범위를 위해 gte, lte 추가
    }
    search_fields = ['user__username', 'ip_address']

    def get_queryset(self):

        # Swagger 문서 생성 시 예외 방지
        if getattr(self, "swagger_fake_view", False):
            return AuditLog.objects.none()

        user = self.request.user

        queryset = AuditLog.objects.select_related('user').order_by('-created_at')

        if user.role == user.Role.ADMIN:
            return queryset
        
        if user.role == user.Role.OPERATOR:
            return queryset.filter(user=user)
        
        return AuditLog.objects.none()

