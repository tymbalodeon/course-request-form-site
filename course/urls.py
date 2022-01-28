from django.conf import settings
from django.conf.urls import include
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from django.views.generic.base import TemplateView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.routers import DefaultRouter
from rest_framework_swagger.views import get_swagger_view

from .autocomplete import CanvasSiteAutocomplete, SubjectAutocomplete, UserAutocomplete
from .views import (
    AutoAddViewSet,
    CanvasSiteViewSet,
    CourseViewSet,
    HomePage,
    NoticeViewSet,
    RequestViewSet,
    SchoolViewSet,
    SubjectViewSet,
    UpdateLogViewSet,
    UserViewSet,
    autocomplete_canvas_course,
    check_data_warehouse_for_course,
    check_open_data_for_course,
    contact,
    delete_canceled_requests,
    emergency_redirect,
    process_requests,
    quick_config,
    search_banner_courses,
    user_courses,
    user_info,
    view_canceled_SIS,
    view_deleted_requests,
    view_requests,
)

schema_view = get_swagger_view(title="Pastebin API")

router = DefaultRouter()
router.register(r"courses", CourseViewSet)
router.register(r"users", UserViewSet)
router.register(r"notices", NoticeViewSet)
router.register(r"requests", RequestViewSet)
router.register(r"schools", SchoolViewSet)
router.register(r"subjects", SubjectViewSet)
router.register(r"autoadds", AutoAddViewSet)
router.register(r"canvassites", CanvasSiteViewSet)
urlpatterns = [
    path("siterequest/", emergency_redirect),
    path("admin/process_requests/", process_requests),
    path("admin/view_requests/", view_requests),
    path("admin/view_canceled_SIS/", view_canceled_SIS),
    path("admin/delete_canceled_requests/", delete_canceled_requests),
    path("admin/view_deleted_requests/", view_deleted_requests),
    path("quickconfig/", quick_config),
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
    path("courselookup/", check_open_data_for_course),
    path("dwlookup/", check_data_warehouse_for_course),
    path("bannerlookup/", search_banner_courses),
    path("api/", include(router.urls)),
    path("api_doc/", schema_view),
    path(
        "courses/",
        CourseViewSet.as_view({"get": "list"}, renderer_classes=[TemplateHTMLRenderer]),
        name="UI-course-list",
    ),
    path(
        "courses/<course_code>/",
        CourseViewSet.as_view(
            {"get": "retrieve"}, renderer_classes=[TemplateHTMLRenderer]
        ),
        name="UI-course-detail",
    ),
    path(
        "canvassites/",
        CanvasSiteViewSet.as_view(
            {"get": "list"}, renderer_classes=[TemplateHTMLRenderer]
        ),
        name="UI-canvas_site-list",
    ),
    path(
        "canvassites/<canvas_id>/",
        CanvasSiteViewSet.as_view(
            {"get": "retrieve", "put": "update"},
            renderer_classes=[TemplateHTMLRenderer],
        ),
        name="UI-canvas_site-detail",
    ),
    path(
        "requests/",
        RequestViewSet.as_view(
            {"get": "list", "post": "create"},
            renderer_classes=[TemplateHTMLRenderer],
        ),
        name="UI-request-list",
    ),
    path(
        "requests/<str:pk>/",
        RequestViewSet.as_view(
            {"get": "retrieve", "put": "update"},
            renderer_classes=[TemplateHTMLRenderer],
        ),
        name="UI-request-detail",
    ),
    path(
        "requests/<str:pk>/edit/",
        RequestViewSet.as_view(
            {"get": "retrieve"}, renderer_classes=[TemplateHTMLRenderer]
        ),
        name="UI-request-detail-edit",
    ),
    path(
        "requests/<str:pk>/success/",
        RequestViewSet.as_view(
            {"get": "retrieve"}, renderer_classes=[TemplateHTMLRenderer]
        ),
        name="UI-request-detail-success",
    ),
    path(
        "schools/",
        SchoolViewSet.as_view(
            {
                "get": "list",
            },
            renderer_classes=[TemplateHTMLRenderer],
        ),
        name="UI-school-list",
    ),
    path(
        "schools/<str:pk>/",
        SchoolViewSet.as_view(
            {"get": "retrieve", "put": "update"},
            renderer_classes=[TemplateHTMLRenderer],
        ),
        name="UI-school-detail",
    ),
    path(
        "subjects/",
        SubjectViewSet.as_view(
            {"get": "list"}, renderer_classes=[TemplateHTMLRenderer]
        ),
        name="UI-subject-list",
    ),
    path(
        "subjects/<str:pk>/",
        SubjectViewSet.as_view(
            {"get": "retrieve", "put": "update"},
            renderer_classes=[TemplateHTMLRenderer],
        ),
        name="UI-subject-detail",
    ),
    path(
        "autoadds/",
        AutoAddViewSet.as_view(
            {"get": "list", "post": "create", "delete": "list"},
            renderer_classes=[TemplateHTMLRenderer],
        ),
        name="UI-autoadd-list",
    ),
    path(
        "",
        HomePage.as_view(
            {"get": "get", "post": "post"}, renderer_classes=[TemplateHTMLRenderer]
        ),
        name="home",
    ),
    path("contact/", contact, name="contact"),
    path("accounts/userinfo/", user_info, name="userinfo"),
    path(
        "logs/",
        UpdateLogViewSet.as_view(
            {"get": "list"}, renderer_classes=[TemplateHTMLRenderer]
        ),
        name="UI-updatelog-list",
    ),
    path(
        "accounts/login/",
        LoginView.as_view(
            template_name="login.html",
            extra_context={
                "next": "/",
            },
        ),
        name="login",
    ),
    path(
        "accounts/logout/",
        LogoutView.as_view(
            next_page=settings.LOGOUT_REDIRECT_URL,
            template_name="logout.html",
        ),
        name="logout",
    ),
    path("canvasuser/<username>/", user_courses),
    path("searchcanvas/<search>/", autocomplete_canvas_course),
    path("user-autocomplete/", UserAutocomplete.as_view(), name="user-autocomplete"),
    path(
        "subject-autocomplete/",
        SubjectAutocomplete.as_view(),
        name="subject-autocomplete",
    ),
    path(
        "canvas_site-autocomplete/",
        CanvasSiteAutocomplete.as_view(),
        name="canvas_site-autocomplete",
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns.extend(
        [
            path("__debug__/", include(debug_toolbar.urls)),
        ]
    )
