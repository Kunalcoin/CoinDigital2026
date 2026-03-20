"""RoyaltyWebsite URL Configuration"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.contrib import admin
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Translate API",
        default_version="v1",
        description="API for translation tasks",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)
urlpatterns = (
    [
        path("admin/", admin.site.urls),
        path("", include("main.urls")),
        path("", include("releases.urls")),
        # path("api/", include("app_models.urls")),
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
        re_path(
            r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}
        ),
        path(
            "swagger/",
            schema_view.with_ui("swagger", cache_timeout=0),
            name="schema-swagger-ui",
        ),
    ]
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
)
