from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):

    # 목록 화면에 보일 컬럼
    list_display = ('username', 'email', 'role')

    # 검색 기능
    search_fields = ('username', 'role')

    # 상세 페이지에 role 추가
    fieldsets = BaseUserAdmin.fieldsets + (
        ('권한 정보', {
            'fields': ('role',),
        }),
    )