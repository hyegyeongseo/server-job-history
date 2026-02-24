from django.urls import path
from .views import LogInView, RefreshView, LogOutView

urlpatterns = [
    path('login/', LogInView.as_view(), name='로그인'),
    path('refresh/', RefreshView.as_view(), name='토큰 갱신'),
    path('logout/', LogOutView.as_view(), name='로그아웃'),
]