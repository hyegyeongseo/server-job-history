from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.core.models import User

class ServerPermission(BasePermission):

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False
        
        role = getattr(user, 'role', None)
        
        # 조회는 모두 허용
        if request.method in SAFE_METHODS:
            return True
        
        # 생성, 수정, 삭제 모두 Viewer만 아니면 허용
        return role != User.Role.VIEWER
        

class AuditLogPermission(BasePermission):

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False
        
        role = getattr(user, 'role', None)
        
        # 조회만 허용
        if request.method in SAFE_METHODS:
            return role != User.Role.VIEWER
        
        return False
    
class JobPermission(BasePermission):
    """
    Admin: 전체 가능
    Operator: 서버/작업 관리 가능
    Viewer: 조회만 가능
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False
        
        role = getattr(user, 'role', None)

        # 조회
        if request.method in SAFE_METHODS:
            return True

        # 생성
        if request.method == 'POST':
            return role != User.Role.VIEWER

        # 수정
        if request.method in ['PATCH', 'PUT']:
            return role != User.Role.VIEWER
        
        # 삭제
        if request.method == 'DELETE':
            return False