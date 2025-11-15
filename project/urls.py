from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include


def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("meta_auth.urls")),
    path("api/", include("workspaces.urls")),
    path("health/", health, name="health"),
    path("", health, name="home"),
]

