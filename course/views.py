from datetime import datetime
from json import dump, dumps, load
from logging import getLogger
from os import mkdir
from re import search
from typing import Dict
from urllib.parse import unquote

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import AccessMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.contrib.messages import ERROR, add_message
from django.contrib.messages import error as messages_error
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django_celery_beat.models import PeriodicTask
from django_filters import CharFilter, ChoiceFilter, DateTimeFilter, ModelChoiceFilter
from django_filters.rest_framework import FilterSet
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.utils.html import parse_html_list
from rest_framework.viewsets import ModelViewSet

from canvas.api import (
    MAIN_ACCOUNT_ID,
    CanvasException,
    create_canvas_user,
    get_canvas,
    get_user_by_sis,
)
from config.config import OPEN_DATA_DOMAIN, OPEN_DATA_ID, OPEN_DATA_KEY
from data_warehouse.data_warehouse import (
    get_course,
    get_staff_account,
    get_user_by_pennkey,
)
from open_data.open_data import OpenData

from .forms import CanvasSiteForm, EmailChangeForm, SubjectForm, UserForm
from .models import (
    Activity,
    AutoAdd,
    CanvasSite,
    Course,
    Notice,
    Profile,
    Request,
    School,
    Subject,
    UpdateLog,
    User,
)
from .serializers import (
    AutoAddSerializer,
    CanvasSiteSerializer,
    CourseSerializer,
    NoticeSerializer,
    RequestSerializer,
    SchoolSerializer,
    SubjectSerializer,
    UpdateLogSerializer,
    UserSerializer,
)
from .tasks import create_canvas_sites
from .terms import (
    CURRENT_TERM,
    CURRENT_YEAR,
    CURRENT_YEAR_AND_TERM,
    NEXT_TERM,
    NEXT_YEAR,
    NEXT_YEAR_AND_TERM,
    get_term_letters,
)
from .utils import DATA_DIRECTORY_NAME, get_data_directory, update_user_courses

FIVE_OR_MORE_ALPHABETIC_CHARACTERS = r"[a-z]{5,}"
SPRING, SUMMER, FALL = get_term_letters()
TASKS_LOG_PATH = get_data_directory(DATA_DIRECTORY_NAME) / "tasks"
PROCESS_REQUESTS_LOG = TASKS_LOG_PATH / "processed-requests.json"
DELETE_REQUESTS_LOG = TASKS_LOG_PATH / "deleted-courses.json"
CHECK_CANCELED_LOG = TASKS_LOG_PATH / "canceled-courses.json"

logger = getLogger(__name__)


def get_search_term(request):
    search_term = request.GET.get("search", None)

    if search_term and not search(FIVE_OR_MORE_ALPHABETIC_CHARACTERS, search_term):
        search_term = search_term.replace(" ", "").replace("-", "").replace("_", "")

    return search_term


def emergency_redirect(request):
    return redirect("/")


def print_log_message(request, object_type, action_type):
    search_term = request.GET.get("search", None)

    if not search_term:
        search_term = request.GET.get("subject", None)

    search_term_display = f'using search term "{search_term}" ' if search_term else ""

    logger.info(
        f"Retrieving {object_type} {action_type.upper()} {search_term_display}for"
        f' "{request.user}"...'
    )


class MixedPermissionModelViewSet(AccessMixin, ModelViewSet):
    permission_classes_by_action: Dict[str, list] = {}
    login_url = "/accounts/login/"

    def get_permissions(self):
        return (
            [
                permission()
                for permission in self.permission_classes_by_action[self.action]
            ]
            if self.permission_classes_by_action
            else [permission() for permission in self.permission_classes]
        )

    def handle_no_permission(self):
        if self.raise_exception or self.request.user.is_authenticated:
            raise PermissionDenied(self.get_permission_denied_message())

        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )


class CourseFilter(FilterSet):
    activity = ModelChoiceFilter(
        queryset=Activity.objects.all(), field_name="course_activity", label="Activity"
    )
    instructor = CharFilter(field_name="instructors__username", label="Instructor")
    school = ModelChoiceFilter(
        queryset=School.objects.all(),
        field_name="course_schools",
        to_field_name="abbreviation",
        label="School (abbreviation)",
    )
    subject = CharFilter(
        field_name="course_subject__abbreviation", label="Subject (abbreviation)"
    )
    term = ChoiceFilter(
        choices=Course.TERM_CHOICES, field_name="course_term", label="Term"
    )

    class Meta:
        model = Course
        fields = [
            "term",
            "activity",
            "school",
            "instructor",
            "subject",
        ]


class CourseViewSet(MixedPermissionModelViewSet, ModelViewSet):
    lookup_field = "course_code"
    queryset = (
        Course.objects.filter(
            course_term__in=[CURRENT_TERM, NEXT_TERM],
            year=CURRENT_YEAR,
            course_subject__visible=True,
            course_schools__visible=True,
        )
        if CURRENT_TERM != FALL
        else Course.objects.filter(
            Q(course_term=NEXT_TERM, year=NEXT_YEAR)
            | Q(course_term=CURRENT_TERM, year=CURRENT_YEAR),
            course_subject__visible=True,
            course_schools__visible=True,
        )
    )
    serializer_class = CourseSerializer
    filterset_class = CourseFilter
    search_fields = ("$course_name", "$course_code")
    permission_classes_by_action: Dict[str, list] = {
        "create": [IsAdminUser],
        "list": [IsAuthenticated],
        "retrieve": [IsAuthenticated],
        "update": [IsAdminUser],
        "partial_update": [IsAdminUser],
        "delete": [IsAdminUser],
    }

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def list(self, request):
        print_log_message(request, "course", "list")

        search_term = get_search_term(request)
        queryset = (
            self.get_queryset().filter(
                Q(course_code__contains=search_term)
                | Q(course_name__contains=search_term)
            )
            if search_term
            else self.filter_queryset(self.get_queryset())
        )
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)

            if request.accepted_renderer.format == "html":
                response.template_name = "course_list.html"
                response.data = {
                    "results": response.data,
                    "paginator": self.paginator,
                    "filter": CourseFilter,
                    "request": request,
                    "is_staff": request.user.is_staff,
                    "autocomplete_user": UserForm(),
                    "autocomplete_subject": SubjectForm(),
                    "autocomplete_canvas_site": CanvasSiteForm(),
                    "style": {"template_pack": "rest_framework/vertical/"},
                    "current_term": CURRENT_YEAR_AND_TERM,
                    "next_term": NEXT_YEAR_AND_TERM,
                }

            logger.info(response.data["paginator"].page)

            return response

    def retrieve(self, request, *args, **kwargs):
        print_log_message(request, "course", "detail")
        response = super(CourseViewSet, self).retrieve(request, *args, **kwargs)
        if request.accepted_renderer.format == "html":
            course_instance = self.get_object()
            logger.info(f"- COURSE: {course_instance}")
            if course_instance.requested:
                request_instance = (
                    ""
                    if course_instance.multisection_request
                    else course_instance.get_request()
                )
                this_form = ""
            else:
                reserves = (
                    True
                    if course_instance.course_schools.abbreviation
                    in [
                        "SAS",
                        "SEAS",
                        "FA",
                        "PSOM",
                        "SP2",
                    ]
                    else False
                )
                this_form = RequestSerializer(
                    data={"course_requested": self.get_object(), "reserves": reserves}
                )
                this_form.is_valid()
                request_instance = ""
            return Response(
                {
                    "course": response.data,
                    "request": request_instance,
                    "request_form": this_form,
                    "autocomplete_canvas_site": CanvasSiteForm(),
                    "is_staff": request.user.is_staff,
                    "style": {"template_pack": "rest_framework/vertical/"},
                },
                template_name="course_detail.html",
            )
        else:
            return response


class RequestFilter(FilterSet):
    status = ChoiceFilter(
        choices=Request.REQUEST_PROCESS_CHOICES, field_name="status", label="Status"
    )
    requestor = CharFilter(field_name="owner__username", label="Requestor")
    date = DateTimeFilter(field_name="created", label="Created")
    school = ModelChoiceFilter(
        queryset=School.objects.all(),
        field_name="course_requested__course_schools",
        to_field_name="abbreviation",
        label="School (abbreviation)",
    )
    term = ChoiceFilter(
        choices=Course.TERM_CHOICES,
        field_name="course_requested__course_term",
        label="Term",
    )

    class Meta:
        model = Request
        fields = ["status", "requestor", "date", "school", "term"]


class RequestViewSet(MixedPermissionModelViewSet, ModelViewSet):
    queryset = Request.objects.all()
    serializer_class = RequestSerializer
    filterset_class = RequestFilter
    permission_classes = (permissions.IsAuthenticated,)
    permission_classes_by_action: Dict[str, list] = {
        "create": [IsAuthenticated],
        "list": [IsAuthenticated],
        "retrieve": [IsAuthenticated],
        "update": [IsAuthenticated],
        "partial_update": [IsAuthenticated],
        "delete": [IsAdminUser],
    }

    def create(self, request):
        def update_course(course):
            course.save()

            if course.crosslisted:
                for crosslisted in course.crosslisted.all():
                    crosslisted.request = course.request
                    crosslisted.save()

        masquerade = (
            request.session["on_behalf_of"] if "on_behalf_of" in request.session else ""
        )
        course = Course.objects.get(course_code=request.data["course_requested"])
        instructors = course.get_instructors()

        if instructors == "STAFF":
            instructors = None

        if (instructors and self.request.user.get_username() not in instructors) and (
            masquerade and masquerade not in instructors
        ):
            raise PermissionDenied({"message": "You don't have permission to access"})

        additional_enrollments_partial = parse_html_list(
            request.data, prefix="additional_enrollments"
        )
        additional_sections_partial = parse_html_list(
            request.data, prefix="additional_sections"
        )
        request_data = request.data.dict()
        request_data["additional_enrollments"] = (
            clean_custom_input(additional_enrollments_partial)
            if additional_enrollments_partial
            else []
        )
        request_data["additional_sections"] = (
            [
                data_dict["course_code"]
                for data_dict in clean_custom_input(additional_sections_partial)
            ]
            if additional_sections_partial
            else []
        )
        request_data["reserves"] = (
            course.course_schools.abbreviation
            in [
                "SAS",
                "SEAS",
                "FA",
                "PSOM",
                "SP2",
            ]
            if "view_type" in request.data
            and request.data["view_type"] == "UI-course-list"
            else None
        )

        request_data["copy_from_course"] = (
            request.data["name"] if "name" in request.data else None
        )
        request_data["exclude_announcements"] = (
            (
                request.data["exclude_announcements"] == "on"
                or request.data["exclude_announcements"] == "true"
                or False
            )
            if "exclude_announcements" in request.data
            else False
        )
        serializer = self.get_serializer(data=request_data)
        is_valid = serializer.is_valid()

        if not is_valid:
            for error in serializer.errors:
                add_message(request, ERROR, error)

            raise serializers.ValidationError()

        serializer.validated_data["masquerade"] = masquerade
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        course = Course.objects.get(course_code=request.data["course_requested"])
        update_course(course)

        if "view_type" in request.data:
            if request.data["view_type"] == "UI-course-list":
                return redirect("UI-course-list")
            elif request.data["view_type"] == "home":
                return redirect("home")
            elif request.data["view_type"] == "UI-request-detail":
                return redirect(
                    "UI-request-detail-success",
                    pk=course.course_code,
                )
        else:
            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def list(self, request):
        print_log_message(request, "request", "list")
        search_term = get_search_term(request)
        queryset = (
            self.get_queryset().filter(
                Q(course_requested__course_code__contains=search_term)
                | Q(course_requested__course_name__contains=search_term)
            )
            if search_term
            else self.get_queryset()
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True,
                fields=[
                    "course_info",
                    "owner",
                    "masquerade",
                    "created",
                    "status",
                    "course_requested",
                ],
            )
            response = self.get_paginated_response(serializer.data)
            if request.accepted_renderer.format == "html":
                response.template_name = "request_list.html"
                response.data = {
                    "requests": response.data,
                    "paginator": self.paginator,
                    "filter": RequestFilter,
                    "autocomplete_user": UserForm(),
                }
            logger.info(response.data["paginator"].page)
            return response

    def check_request_update_permissions(self, request, response_data):
        request_status = response_data["status"]
        request_owner = response_data["owner"]
        request_masquerade = response_data["masquerade"]
        if request_status == "SUBMITTED":
            permissions = {
                "staff": ["lock", "cancel", "edit", "create"],
                "owner": ["cancel", "edit"],
            }
        elif request_status == "APPROVED":
            permissions = {"staff": ["cancel", "edit", "lock"], "owner": ["cancel"]}
        elif request_status == "LOCKED":
            permissions = {"staff": ["cancel", "edit", "unlock"], "owner": [""]}
        elif request_status == "CANCELED":
            permissions = {"staff": ["lock"], "owner": [""]}
        elif request_status == "IN_PROCESS":
            permissions = {"staff": ["lock"], "owner": [""]}
        elif request_status == "COMPLETED":
            permissions = {"staff": [""], "owner": [""]}
        else:
            permissions = {"staff": [""], "owner": [""]}
        if request.session["on_behalf_of"]:
            current_masquerade = request.session["on_behalf_of"]
            if current_masquerade == request_owner:
                return permissions["owner"]
        if request.user.is_staff:
            return permissions["staff"]
        if request.user.username == request_owner or (
            request.user.username == request_masquerade and request_masquerade != ""
        ):
            return permissions["owner"]
        return ""

    def retrieve(self, request, *args, **kwargs):
        print_log_message(request, "request", "detail")
        response = super(RequestViewSet, self).retrieve(request, *args, **kwargs)
        logger.info(f"- REQUEST: {response.data['course_requested']}")
        if request.resolver_match.url_name == "UI-request-detail-success":
            return Response(
                {"request": response.data},
                template_name="request_success.html",
            )
        elif request.accepted_renderer.format == "html":
            permissions = self.check_request_update_permissions(request, response.data)
            if request.resolver_match.url_name == "UI-request-detail-edit":
                here = RequestSerializer(
                    self.get_object(), context={"request": request}
                )
                return Response(
                    {
                        "request": response.data,
                        "permissions": permissions,
                        "request_form": here,
                        "autocomplete_canvas_site": CanvasSiteForm(),
                        "style": {"template_pack": "rest_framework/vertical/"},
                    },
                    template_name="request_detail_edit.html",
                )
            else:
                return Response(
                    {"request": response.data, "permissions": permissions},
                    template_name="request_detail.html",
                )
        else:
            return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        course = Course.objects.get(course_code=instance.course_requested)
        course.save()
        self.perform_destroy(instance)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def post(self, request, *args, **kwargs):
        pass

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        additional_enrollments_partial = parse_html_list(
            request.data, prefix="additional_enrollments"
        )
        additional_sections_partial = parse_html_list(
            request.data, prefix="additional_sections"
        )
        data_dict = request.data.dict()
        if additional_enrollments_partial or additional_sections_partial:
            if additional_enrollments_partial:
                final_add_enroll = clean_custom_input(additional_enrollments_partial)
                data_dict["additional_enrollments"] = final_add_enroll
            else:
                data_dict["additional_enrollments"] = []
            if additional_sections_partial:
                final_add_sects = clean_custom_input(additional_sections_partial)
                data_dict["additional_sections"] = [
                    data_dict["course_code"] for data_dict in final_add_sects
                ]
            else:
                data_dict["additional_sections"] = []
            serializer = self.get_serializer(instance, data=data_dict, partial=True)
        else:
            data = dict(
                [
                    (x, y)
                    for x, y in data_dict.items()
                    if not x.startswith("additional_enrollments")
                    or x.startswith("additional_sections")
                ]
            )
            data["additional_enrollments"] = []
            data["additional_sections"] = []
            serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid()
        if not serializer.is_valid():
            add_message(request, ERROR, serializer.errors)
            raise serializers.ValidationError(serializer.errors)
        else:
            serializer.save(owner=self.request.user)
        self.perform_update(serializer)
        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}
        if (
            "view_type" in request.data
            and request.data["view_type"] == "UI-request-detail"
        ):
            permissions = self.check_request_update_permissions(
                request,
                {
                    "owner": instance.owner.username,
                    "masquerade": instance.masquerade,
                    "status": instance.status,
                },
            )
            return Response(
                {"request": serializer.data, "permissions": permissions},
                template_name="request_detail.html",
            )
        return Response(serializer.data)


def clean_custom_input(adds):
    adds_dict = adds[0].dict()
    adds_dict = {
        key.replace("[", "").replace("]", ""): value for key, value in adds_dict.items()
    }
    final_add = []

    for add in adds:
        add = add.dict()
        new_add = {
            key.replace("[", "").replace("]", ""): value for key, value in add.items()
        }

        if "" not in new_add.values():
            if "user" in new_add.keys():
                new_add["user"] = new_add["user"].lower()

            final_add += [new_add]

    return final_add


class UserViewSet(MixedPermissionModelViewSet, ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = "username"
    filterset_fields = ("profile__penn_id",)


class SchoolViewSet(MixedPermissionModelViewSet, ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer

    def list(self, request):
        print_log_message(request, "school", "list")
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            if request.accepted_renderer.format == "html":
                response.template_name = "schools_list.html"
                response.data = {"schools": response.data, "paginator": self.paginator}
            logger.info(response.data["paginator"].page)
            return response

    def update(self, request, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        print_log_message(request, "school", "detail")
        response = super(SchoolViewSet, self).retrieve(request, *args, **kwargs)
        logger.info(f"- SCHOOL: {response.data['name']}")
        return (
            Response({"school": response.data}, template_name="school_detail.html")
            if request.accepted_renderer.format == "html"
            else response
        )


class SubjectViewSet(MixedPermissionModelViewSet, ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def list(self, request):
        print_log_message(request, "subject", "list")
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if not page:
            return
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        if request.accepted_renderer.format == "html":
            response.template_name = "subjects_list.html"
            response.data = {"subjects": response.data, "paginator": self.paginator}
        logger.info(response.data["paginator"].page)
        return response

    def retrieve(self, request, *args, **kwargs):
        print_log_message(request, "subject", "detail")
        response = super(SubjectViewSet, self).retrieve(request, *args, **kwargs)
        logger.info(f"- SUBJECT: {response.data['name']}")
        return (
            Response({"subjects": response.data}, template_name="subject_detail.html")
            if request.accepted_renderer.format == "html"
            else response
        )


class NoticeViewSet(MixedPermissionModelViewSet, ModelViewSet):
    queryset = Notice.objects.all()
    serializer_class = NoticeSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class CanvasSiteViewSet(MixedPermissionModelViewSet, ModelViewSet):
    queryset = CanvasSite.objects.all()
    serializer_class = CanvasSiteSerializer
    lookup_field = "canvas_id"

    def get_queryset(self):
        user = self.request.user

        return CanvasSite.objects.filter(Q(owners=user) | Q(added_permissions=user))

    def list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)

            if request.accepted_renderer.format == "html":
                response.template_name = "canvas_site_list.html"
                response.data = {"results": response.data, "paginator": self.paginator}

            return response

    def retrieve(self, request, *args, **kwargs):
        response = super(CanvasSiteViewSet, self).retrieve(request, *args, **kwargs)

        return (
            Response(
                {"data": response.data, "autocomplete_user": UserForm()},
                template_name="canvas_site_detail.html",
            )
            if request.accepted_renderer.format == "html"
            else response
        )

    def update(self, request):
        instance = self.get_object()
        data = {"added_permissions": [request.data["username"]]}
        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(
            {"data": serializer.data, "autocomplete_user": UserForm()},
            template_name="canvas_site_detail.html",
        )


class HomePage(UserPassesTestMixin, ModelViewSet):
    lookup_field = "course_code"
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "home_content.html"
    login_url = "/accounts/login/"
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = CourseSerializer
    queryset = Course.objects.filter(course_schools__visible=True)

    def test_func(self):
        user_name = self.request.user.get_username()
        logger.info(f'Checking Users for "{user_name}"...')
        user = User.objects.get(username=self.request.user.get_username())
        try:
            if user.profile:
                logger.info(f'FOUND user "{user_name}".')
                return True
        except Exception:
            user_data = get_staff_account(penn_key=user.username)
            if user_data:
                user.first_name = user_data["first_name"].title()
                user.last_name = user_data["last_name"].title()
                user.email = user_data["email"]
                Profile.objects.create(user=user, penn_id=user_data["penn_id"])
                update_user_courses(user.username)
                logger.info(f'CREATED user "{user_name}".')
                return True
            else:
                logger.error(f'FAILED to create user "{user_name}".')
                return False

    def get(self, request):
        self.test_func()
        try:
            notice = Notice.objects.latest()
        except Notice.DoesNotExist:
            notice = None
        masquerade = request.session["on_behalf_of"]
        user_account = (
            User.objects.get(username=masquerade) if masquerade else request.user
        )
        courses = self.get_queryset().filter(instructors=user_account)
        courses_count = courses.count()
        courses = courses[:15]
        requests = Request.objects.filter(
            Q(owner=user_account) | Q(masquerade=user_account)
        )
        requests_count = requests.count()
        requests = requests[:15]
        canvas_sites = CanvasSite.objects.filter(Q(owners=user_account))
        canvas_sites_count = canvas_sites.count()
        canvas_sites = canvas_sites[:15]
        page = self.paginate_queryset(courses)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        response.data = {
            "notice": notice,
            "requests": requests,
            "requests_count": requests_count,
            "courses": response.data,
            "courses_count": courses_count,
            "canvas_sites": canvas_sites,
            "canvas_sites_count": canvas_sites_count,
            "username": request.user,
            "user_account": user_account,
            "autocomplete_canvas_site": CanvasSiteForm(),
            "style": {"template_pack": "rest_framework/vertical/"},
        }
        return response

    def set_session(self, request):
        on_behalf_of = None
        try:
            on_behalf_of = request.data["on_behalf_of"].lower()
            if on_behalf_of:
                lookup_user = get_user_by_pennkey(on_behalf_of)
                if lookup_user is None:
                    messages_error(
                        request, "Invalid Pennkey -- Pennkey must be Upenn Employee"
                    )
                elif lookup_user.is_staff is True:
                    messages_error(
                        request,
                        "Invalid Pennkey -- Pennkey cannot be Courseware Team Member",
                    )
        except KeyError as error:
            logger.error(f"ERROR: There was a problem setting the session ({error})")
        request.session["on_behalf_of"] = on_behalf_of

    def post(self, request):
        self.set_session(request)
        return redirect(request.META["HTTP_REFERER"])


class AutoAddViewSet(MixedPermissionModelViewSet, ModelViewSet):
    queryset = AutoAdd.objects.all()
    serializer_class = AutoAddSerializer
    permission_classes_by_action = {
        "create": [IsAdminUser],
        "list": [IsAdminUser],
        "retrieve": [IsAdminUser],
        "update": [IsAdminUser],
        "partial_update": [IsAdminUser],
        "destroy": [IsAdminUser],
    }

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        response = Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

        if request.accepted_renderer.format == "html":
            response.template_name = "admin/autoadd_list.html"

            return redirect("UI-autoadd-list")
        else:
            return response

    def list(self, request):
        print_log_message(request, "auto-added user", "list")

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)

            if request.accepted_renderer.format == "html":
                response.template_name = "admin/autoadd_list.html"
                response.data = {
                    "auto_adds": response.data,
                    "paginator": self.paginator,
                    "serializer": AutoAddSerializer,
                    "user_form": UserForm(),
                }

            logger.info(response.data["paginator"].page)

            return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        response = Response(status=status.HTTP_204_NO_CONTENT)

        if "UI" in request.data and request.data["UI"] == "true":
            response.template_name = "admin/autoadd_list.html"

            return redirect("UI-autoadd-list")
        else:
            return response


class UpdateLogViewSet(MixedPermissionModelViewSet, ModelViewSet):
    queryset = UpdateLog.objects.all()
    serializer_class = UpdateLogSerializer
    permission_classes_by_action = {
        "create": [IsAdminUser],
        "list": [IsAdminUser],
        "retrieve": [IsAdminUser],
        "update": [IsAdminUser],
        "partial_update": [IsAdminUser],
        "delete": [IsAdminUser],
    }

    def list(self, request, *args, **kwargs):
        periodic_tasks = PeriodicTask.objects.all()

        return Response({"data": periodic_tasks}, template_name="admin/log_list.html")


def user_info(request):
    masquerade = request.session["on_behalf_of"]
    user_account = User.objects.get(username=masquerade) if masquerade else request.user
    email_change_form = EmailChangeForm(request.user)
    if request.method == "POST":
        email_change_form = EmailChangeForm(request.user, request.POST)
        if email_change_form.is_valid():
            email_change_form.save()
            return redirect("userinfo")
    return render(
        request,
        "user_info.html",
        {"email_change_form": email_change_form, "user_account": user_account},
    )


def DWHSE_Proxy(request):
    return JsonResponse({})


def user_courses(request, username):
    logger.info(f"Username: {username}")

    user = get_user_by_sis(username)
    courses = user.get_courses(enrollment_type="teacher") if user else None
    properties = ["id", "name", "sis_course_id", "workflow_state"]
    courses = (
        [
            [{key: course.attributes.get(key, "NONE") for key in properties}]
            for course in courses
        ]
        if courses
        else None
    )
    courses = (
        [
            course_attributes
            for attributes in courses
            for course_attributes in attributes
        ]
        if courses
        else None
    )
    response = user.attributes if user else {}

    if courses:
        response["courses"] = courses

    return JsonResponse(response)


def autocomplete_canvas_course(request, search_results):
    if request.is_ajax():
        query = unquote(search_results)
        canvas = get_canvas()
        account = canvas.get_account(MAIN_ACCOUNT_ID)
        search_results = account.get_courses(
            search_term=query, search_by="course", sort="course_name", per_page=10
        )[:10]
        results = [
            {"label": result.name, "value": result.id} for result in search_results
        ]
        data = dumps(results)
    else:
        data = "fail"
    mimetype = "application/json"

    return HttpResponse(data, mimetype)


@staff_member_required
def process_requests(request):
    response = {}
    approved_requests = Request.objects.filter(status="APPROVED")

    if approved_requests:
        requests = [
            (
                Request.objects.get(
                    course_requested=request.course_requested.course_code
                ),
                request.course_requested.course_code,
            )
            for request in approved_requests
        ]
        response["processed"] = [
            {
                "course_code": course_code,
                "status": request.status,
                "notes": request.process_notes,
            }
            for request, course_code in requests
        ]

        try:
            create_canvas_sites()
        except Exception as error:
            error = str(error)
            response["error"] = error
            logger.error(error)

        response["time"] = datetime.now().strftime("%m/%d/%y %I:%M%p")

        if not TASKS_LOG_PATH.exists():
            mkdir(TASKS_LOG_PATH)

        with open(PROCESS_REQUESTS_LOG, "w+") as writer:
            dump(response, writer)
    else:
        response["processed"] = "No approved requests to process"

    return JsonResponse(response)


@staff_member_required
def view_requests(request):
    try:
        with open(PROCESS_REQUESTS_LOG) as json_file:
            content = load(json_file)

        return JsonResponse(content)
    except Exception:
        return JsonResponse({"processed": "No processed requests"})


@staff_member_required
def view_canceled_SRS(request):
    try:
        with open(CHECK_CANCELED_LOG) as json_file:
            content = load(json_file)

        return JsonResponse(content)
    except Exception:
        return JsonResponse({"canceled": "No canceled courses"})


@staff_member_required
def delete_canceled_requests(request):
    canceled_requests = Request.objects.filter(status="CANCELED")
    response = {}
    response["deleted"] = [
        request.course_requested.course_code for request in canceled_requests
    ]
    response["time"] = datetime.now().strftime("%m/%d/%y %I:%M%p")

    if not TASKS_LOG_PATH.exists():
        mkdir(TASKS_LOG_PATH)

    with open(DELETE_REQUESTS_LOG, "w+") as writer:
        dump(response, writer)

    return JsonResponse(response)


@staff_member_required
def view_deleted_requests(request):
    try:
        with open(DELETE_REQUESTS_LOG) as json_file:
            content = load(json_file)

        return JsonResponse(content)
    except Exception:
        return JsonResponse({"response": "No canceled courses"})


def quick_config(request):
    def handle_error(
        error, canvas_course, canvas_user, roles, enrollment_term_id, lib=False
    ):
        if (
            error.message
            == '{"message":"Can\'t add an enrollment to a concluded course."}'
        ):
            try:
                enrollment = (
                    {
                        "role_id": "1383",
                        "enrollment_state": "active",
                    }
                    if lib
                    else {"enrollment_state": "active"}
                )
                canvas_course.update(course={"term_id": 4373})
                canvas_course.enroll_user(
                    canvas_user.id, roles[role], enrollment=enrollment
                )
                canvas_course.update(course={"term_id": enrollment_term_id})
            except CanvasException as error:
                data["Info"]["Errors"] = f"CanvasException: {error}"
        else:
            data["Info"]["Errors"] = f"CanvasException: {error}"

    data = {"Job": "", "Info": {"Errors": ""}}

    if not request.method == "POST":
        return render(request, "admin/quickconfig.html")
    else:
        canvas = get_canvas()
        config = request.POST.get("config")
        pennkey = request.POST.get("pennkey")
        role = request.POST.get("role")
        course_id = request.POST.get("course_id")

        if config != "user":
            data["Info"]["Errors"] = "something went wrong"
        else:
            roles = {
                "inst": "TeacherEnrollment",
                "stud": "StudentEnrollment",
                "ta": "TaEnrollment",
                "lib": "DesignerEnrollment",
                "obs": "ObserverEnrollment",
                "des": "DesignerEnrollment",
            }

            if not pennkey:
                data["Info"]["Errors"] = "please set pennkey"
            else:
                user = get_user_by_pennkey(pennkey)

                if not user:
                    data["Info"]["Errors"] = f"failed to find user {pennkey} in DW"

                    return render(request, "admin/quickconfig.html", {"data": data})

                canvas_user = get_user_by_sis(pennkey)

                if not canvas_user:
                    data["Job"] = "AccountCreation"

                    try:
                        canvas_user = create_canvas_user(
                            pennkey,
                            user.profile.penn_id,
                            user.email,
                            user.first_name + user.last_name,
                        )
                    except Exception:
                        data["Info"]["Errors"] = "failed create user in Canvas"

                        return render(request, "admin/quickconfig.html", {"data": data})

                    data["Info"]["Notes"] = f"created canvas account for user {pennkey}"

                if role and course_id:
                    data["Job"] += "EnrollmentCreation"
                    data["Info"]["Role"] = roles[role]
                    canvas_course = canvas.get_course(course_id)
                    enrollment_term_id = canvas_course.enrollment_term_id

                    if role == "lib":
                        try:
                            canvas_course.enroll_user(
                                canvas_user.id,
                                roles[role],
                                enrollment={
                                    "role_id": "1383",
                                    "enrollment_state": "active",
                                },
                            )
                            data["Role"] = "LibrarianEnrollment"
                        except CanvasException as error:
                            handle_error(
                                error,
                                canvas_course,
                                canvas_user,
                                roles,
                                enrollment_term_id,
                                lib=True,
                            )
                    else:
                        try:
                            canvas_course.enroll_user(
                                canvas_user.id,
                                roles[role],
                                enrollment={"enrollment_state": "active"},
                            )
                        except CanvasException as error:
                            handle_error(
                                error,
                                canvas_course,
                                canvas_user,
                                roles,
                                enrollment_term_id,
                            )

                    data["Info"]["Course"] = {
                        "title": canvas_course.name,
                        "link": f"https://canvas.upenn.edu/courses/{course_id}",
                    }
                    data["Info"]["User"] = {"pennkey": pennkey}

        return render(request, "admin/quickconfig.html", {"data": data})


def check_open_data_for_course(request):
    data = {}
    size = 0
    logger.warning(f"Course lookup failed: {request}")

    if request.GET:
        try:
            course_id = request.GET.get("course_id", None)
            term = request.GET.get("term", None)
            instructor = request.GET.get("instructor", None)
            open_data = OpenData(OPEN_DATA_DOMAIN, OPEN_DATA_ID, OPEN_DATA_KEY)
            open_data.set_uri("course_section_search")
            open_data.add_param("course_id", course_id)

            if term:
                open_data.add_param("term", term)

            open_data.add_param("number_of_results_per_page", 5)

            if instructor:
                open_data.add_param("instructor", instructor)

            data["data"] = open_data.call_api()

            if isinstance(data["data"], list):
                size = len(data["data"])
            else:
                size = 1
        except Exception as error:
            logger.error(f"ERROR (OpenData): {error}")

    return render(request, "admin/course_lookup.html", {"data": data, "size": size})


def check_data_warehouse_for_course(request):
    data = {}
    size = 0

    if request.GET:
        try:
            headers = [
                "section id",
                "term",
                "subject",
                "school",
                "crosslisting",
                "crosslist code",
                "activity",
                "section department",
                "section division",
                "title",
                "status",
                "revision",
                "instructors",
            ]
            course_code = request.GET.get("course_code")
            results = get_course(course_code, verbose=False)

            if results:
                size = len(results)

                for course in results:
                    course_code = course[0]
                    data["data"][course_code] = dict()

                    for index, item in enumerate(course[1:]):
                        data["data"][course_code][headers[index]] = item
            else:
                data["data"] = "COURSE NOT FOUND"
        except Exception as error:
            logger.error(f"ERROR (Data Warehouse): {error}")

    return render(request, "admin/dw_lookup.html", {"data": data, "size": size})


def autocomplete(request):
    if request.is_ajax():
        query = request.GET.get("term", "").capitalize()
        search_results = User.objects.filter(username__startswith=query)
        results = [user.username for user in search_results]
        data = dumps(results)
    else:
        data = "fail"
    mimetype = "application/json"

    return HttpResponse(data, mimetype)


def autocomplete_subject(request):
    if request.is_ajax():
        query = request.GET.get("term", "").capitalize()
        search_results = Subject.objects.filter(abbreviation__startswith=query)
        results = [abbreviation for abbreviation in search_results]
        data = dumps(results)
    else:
        data = "fail"
    mimetype = "application/json"

    return HttpResponse(data, mimetype)


def autocomplete_canvas_site(request):
    if request.is_ajax():
        query = request.GET.get("term", "").capitalize()
        search_results = CanvasSite.objects.filter(
            Q(owners=query) | Q(added_permissions=query)
        )
        results = [site.name for site in search_results]
        data = dumps(results)
    else:
        data = "fail"
    mimetype = "application/json"

    return HttpResponse(data, mimetype)


def contact(request):
    return render(request, "contact.html")
