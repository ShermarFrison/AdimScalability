from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WorkspaceViewSet, OTPViewSet

router = DefaultRouter()
router.register(r'workspaces', WorkspaceViewSet, basename='workspace')
router.register(r'otps', OTPViewSet, basename='otp')

urlpatterns = [
    path('', include(router.urls)),
]
