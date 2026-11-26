"""
URL configuration for filevault project.

Uploaded files are deliberately NOT served from /media/: every download goes
through GET /api/files/<id>/download/, which checks that the file belongs to the
caller.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('files.urls')),
]
