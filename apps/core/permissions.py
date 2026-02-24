from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.core.models import User

class ServerPermission(BasePermission):

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False
        
        # 조회는 모두 허용
        if request.method in SAFE_METHODS:
            return True
        
        # 생성
        if request.method == 'POST':
            return user.role != User.Role.VIEWER
        
        # 수정
        if request.method in ['PATCH', 'PUT']:
            return user.role != User.Role.VIEWER
        
        # 삭제
        if request.method == 'DELETE':
            return user.role != User.Role.VIEWER
        
        return False

class AuditLogPermission(BasePermission):

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False
        
        # 조회만 허용
        if request.method in SAFE_METHODS:
            return user.role in [User.Role.ADMIN, User.Role.OPERATOR]
        
        return False
    
