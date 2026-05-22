"""
역할 기반 접근 제어(RBAC).

역할 위계
---------
    ADMIN    : 모든 자원에 대한 전체 권한 (남이 만든 작업도 수정 가능)
    OPERATOR : 서버/작업 생성·수정 가능. 단, 작업 수정은 '본인이 만든 것'만.
    VIEWER   : 조회 전용

검사 단계
---------
    1) has_permission        — 메서드/역할 수준 게이트 (목록·생성 포함)
    2) has_object_permission — 개별 객체 소유권 검사 (상세·수정·삭제)

DRF는 detail 액션에서 get_object()를 호출할 때 has_object_permission을
자동으로 부른다. 목록(list)·생성(create)에는 호출되지 않으므로, 생성 시
소유자(created_by) 지정은 view의 perform_create에서 처리한다.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.core.models import User


def _role(user):
    return getattr(user, "role", None)


def _authenticated(user):
    return bool(user and user.is_authenticated)


class ServerPermission(BasePermission):
    """
    조회         : 인증된 모든 역할
    생성/수정/삭제 : OPERATOR, ADMIN (VIEWER 불가)

    삭제는 soft-delete이며, 복구(restore)와 삭제 서버 조회는
    ServerViewSet 안에서 ADMIN 전용으로 추가 제한된다.
    """

    def has_permission(self, request, view):
        user = request.user
        if not _authenticated(user):
            return False
        if request.method in SAFE_METHODS:
            return True
        return _role(user) in (User.Role.ADMIN, User.Role.OPERATOR)


class AuditLogPermission(BasePermission):
    """
    감사 로그는 읽기 전용 자원.
    조회 : OPERATOR, ADMIN (VIEWER는 감사 로그 열람 불가)
    쓰기 : 누구도 불가 (시스템이 자동 생성)
    """

    def has_permission(self, request, view):
        user = request.user
        if not _authenticated(user):
            return False
        if request.method in SAFE_METHODS:
            return _role(user) in (User.Role.ADMIN, User.Role.OPERATOR)
        return False


class JobPermission(BasePermission):
    """
    조회 : 인증된 모든 역할
    생성 : OPERATOR, ADMIN
    수정 : OPERATOR(본인 작업만), ADMIN(전체)
    삭제 : ADMIN  (단, JobViewSet은 DELETE 자체를 비활성화)

    OPERATOR의 '본인 작업만' 제약은 has_object_permission에서 확정된다.
    """

    def has_permission(self, request, view):
        user = request.user
        if not _authenticated(user):
            return False

        if request.method in SAFE_METHODS:
            return True

        if request.method == "POST":
            return _role(user) in (User.Role.ADMIN, User.Role.OPERATOR)

        if request.method in ("PUT", "PATCH"):
            # 1차 게이트: 역할만 통과시키고, 소유권은 객체 단위에서 검사.
            return _role(user) in (User.Role.ADMIN, User.Role.OPERATOR)

        if request.method == "DELETE":
            return _role(user) == User.Role.ADMIN

        return False

    def has_object_permission(self, request, view, obj):
        user = request.user

        if request.method in SAFE_METHODS:
            return True

        role = _role(user)

        if role == User.Role.ADMIN:
            return True

        if role == User.Role.OPERATOR:
            # 본인이 생성한 작업만 수정 가능 (created_by가 None이면 ADMIN만)
            return obj.created_by_id == user.id

        return False