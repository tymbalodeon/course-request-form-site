from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Course Request Form Administration"
admin.site.site_title = "ADMIN: Site Request"

urlpatterns = [
    path("admin/doc/", include("django.contrib.admindocs.urls")),
    path("admin/", admin.site.urls),
    path("", include("course.urls")),
]
