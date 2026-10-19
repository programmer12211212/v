from django.contrib import admin
from django.urls import include, path, re_path

from core.views import serve_media

urlpatterns = [
    path("admin/", admin.site.urls),
    re_path(r"^media/(?P<path>.+)$", serve_media, name="media"),
    path("", include("core.urls")),
]
