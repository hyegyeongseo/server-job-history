from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ServerViewSet

router = DefaultRouter()
router.register(r'servers', ServerViewSet, basename='servers')

urlpatterns = [
    path('', include(router.urls)),
]
