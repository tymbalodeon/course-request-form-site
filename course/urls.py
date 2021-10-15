from django.conf import settings
from django.conf.urls import include, url
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic.base import TemplateView
from rest_framework import renderers
from rest_framework.routers import DefaultRouter
from rest_framework_swagger.views import get_swagger_view

from course import views
from course.auto_complete import (
    CanvasSiteAutocomplete,
    SubjectAutocomplete,
    UserAutocomplete,
)

schema_view = get_swagger_view(title="Pastebin API")

router = DefaultRouter()
router.register(r"courses", views.CourseViewSet)
router.register(r"users", views.UserViewSet)
router.register(r"notices", views.NoticeViewSet)
router.register(r"requests", views.RequestViewSet)
router.register(r"schools", views.SchoolViewSet)
router.register(r"subjects", views.SubjectViewSet)
router.register(r"autoadds", views.AutoAddViewSet)
router.register(r"canvassites", views.CanvasSiteViewSet)
urlpatterns = [
    path("siterequest/", views.emergency_redirect),
    path("contact/googleform/", views.google_form),
    url("admin/process_requests/", views.process_requests, name="process_requests"),
    url("admin/view_requests/", views.view_requests, name="view_requests"),
    url("admin/view_canceled_SRS/", views.view_canceled_SRS),
    url("admin/delete_canceled_requests/", views.remove_canceled_requests),
    url("quickconfig/", views.quick_config),
    path(
        "documentation/",
        TemplateView.as_view(template_name="documentation.html"),
        name="documentation",
    ),
    path(
        "userlookup/",
        TemplateView.as_view(template_name="admin/user_lookup.html"),
        name="user_lookup",
    ),
    url("courselookup/", views.open_data_proxy),
    url("dwlookup/", views.check_data_warehouse_for_course),
    url(r"^api/", include(router.urls)),
    url(r"^api_doc/", schema_view),
    path(
        "courses/",
        views.CourseViewSet.as_view(
            {"get": "list"}, renderer_classes=[renderers.TemplateHTMLRenderer]
        ),
        name="UI-course-list",
    ),
    path(
        "courses/<course_code>/",
        views.CourseViewSet.as_view(
            {"get": "retrieve"}, renderer_classes=[renderers.TemplateHTMLRenderer]
        ),
        name="UI-course-detail",
    ),
    path(
        "canvassites/",
        views.CanvasSiteViewSet.as_view(
            {"get": "list"}, renderer_classes=[renderers.TemplateHTMLRenderer]
        ),
        name="UI-canvas_site-list",
    ),
    path(
        "canvassites/<canvas_id>/",
        views.CanvasSiteViewSet.as_view(
            {"get": "retrieve", "put": "update"},
            renderer_classes=[renderers.TemplateHTMLRenderer],
        ),
        name="UI-canvas_site-detail",
    ),
    path(
        "requests/",
        views.RequestViewSet.as_view(
            {"get": "list", "post": "create"},
            renderer_classes=[renderers.TemplateHTMLRenderer],
        ),
        name="UI-request-list",
    ),
    path(
        "requests/<str:pk>/",
        views.RequestViewSet.as_view(
            {"get": "retrieve", "put": "update"},
            renderer_classes=[renderers.TemplateHTMLRenderer],
        ),
        name="UI-request-detail",
    ),
    path(
        "requests/<str:pk>/edit/",
        views.RequestViewSet.as_view(
            {"get": "retrieve"}, renderer_classes=[renderers.TemplateHTMLRenderer]
        ),
        name="UI-request-detail-edit",
    ),
    path(
        "requests/<str:pk>/success/",
        views.RequestViewSet.as_view(
            {"get": "retrieve"}, renderer_classes=[renderers.TemplateHTMLRenderer]
        ),
        name="UI-request-detail-success",
    ),
    path(
        "schools/",
        views.SchoolViewSet.as_view(
            {
                "get": "list",
            },
            renderer_classes=[renderers.TemplateHTMLRenderer],
        ),
        name="UI-school-list",
    ),
    path(
        "schools/<str:pk>/",
        views.SchoolViewSet.as_view(
            {"get": "retrieve", "put": "update"},
            renderer_classes=[renderers.TemplateHTMLRenderer],
        ),
        name="UI-school-detail",
    ),
    path(
        "subjects/",
        views.SubjectViewSet.as_view(
            {"get": "list"}, renderer_classes=[renderers.TemplateHTMLRenderer]
        ),
        name="UI-subject-list",
    ),
    path(
        "subjects/<str:pk>/",
        views.SubjectViewSet.as_view(
            {"get": "retrieve", "put": "update"},
            renderer_classes=[renderers.TemplateHTMLRenderer],
        ),
        name="UI-subject-detail",
    ),
    path(
        "autoadds/",
        views.AutoAddViewSet.as_view(
            {"get": "list", "post": "create", "delete": "list"},
            renderer_classes=[renderers.TemplateHTMLRenderer],
        ),
        name="UI-autoadd-list",
    ),
    path("", views.HomePage.as_view(), name="home"),
    path("contact/", views.contact, name="contact"),
    path("accounts/userinfo/", views.user_info, name="userinfo"),
    path(
        "logs/",
        views.UpdateLogViewSet.as_view(
            {"get": "list"}, renderer_classes=[renderers.TemplateHTMLRenderer]
        ),
        name="UI-updatelog-list",
    ),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="login.html",
            extra_context={
                "next": "/",
            },
        ),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(
            next_page=settings.LOGOUT_REDIRECT_URL,
            template_name="logout.html",
        ),
        name="logout",
    ),
    url(r"^canvasuser/(?P<username>\w+)/$", views.my_proxy),
    path("searchcanvas/<search>/", views.auto_complete_canvas_course),
    url(
        r"^user-autocomplete/$",
        UserAutocomplete.as_view(),
        name="user-autocomplete",
    ),
    url(
        r"^subject-autocomplete/$",
        SubjectAutocomplete.as_view(),
        name="subject-autocomplete",
    ),
    url(
        r"^canvas_site-autocomplete/$",
        CanvasSiteAutocomplete.as_view(),
        name="canvas_site-autocomplete",
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
