import json
import urllib.parse
from configparser import ConfigParser
from datetime import datetime
from logging import getLogger
from os import listdir, mkdir
from pathlib import Path

from canvas.api import CanvasException, create_canvas_user, get_canvas, get_user_by_sis
from data_warehouse.data_warehouse import inspect_course
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django_celery_beat.models import PeriodicTask
from django_filters import rest_framework as filters
from open_data import open_data
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.utils import html
from rest_framework.views import APIView, exception_handler

from course import email_processor
from course.forms import (
    CanvasSiteForm,
    ContactForm,
    EmailChangeForm,
    SubjectForm,
    UserForm,
)
from course.models import (
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
)
from course.serializers import (
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
from course.tasks import create_canvas_sites
from course.utils import datawarehouse_lookup, update_user_courses, validate_pennkey


def emergency_redirect():
    return redirect("/")


def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    # prsnt("helloooo","\n",exc,"\n",context)
    response = exception_handler(exc, context)
    # response = render({},'errors/403.html')

    # we need to be able to parse if they are doing a html request or not
    # Now add the HTTP status code to the response.
    if response is not None:
        response.data["status_code"] = response.status_code
        response.data["error"] = response.data["detail"]
        del response.data["detail"]

    # response.template_name = 'base_blank.html'#'errors/'+str(response.status_code)+'.html'
    # print("we r barely ali", response.data['status_code'])
    return response
    # return render(response, 'errors/'+str(response.status_code) +'.html')


class TestUserProfileCreated(UserPassesTestMixin):
    def test_func(self):
        user = User.objects.get(username=self.request.user.username)

        try:
            if user.profile:
                return True
        except Exception:
            userdata = datawarehouse_lookup(penn_key=user.username)

            if userdata:
                first_name = userdata["firstname"].title()
                last_name = userdata["lastname"].title()
                user.update(
                    first_name=first_name, last_name=last_name, email=userdata["email"]
                )
                Profile.objects.create(user=user, penn_id=userdata["penn_id"])

                return True
            else:
                return False

        return False


class MixedPermissionModelViewSet(viewsets.ModelViewSet):
    """
    Mixed permission base model allowing for action level
    permission control. Subclasses may define their permissions
    by creating a 'permission_classes_by_action' variable.

    Example:
    permission_classes_by_action = {'list': [AllowAny],
                                   'create': [IsAdminUser]}

    Since each viewset extends the modelviewset there are default actions that are included...
        for each action there should be a defined permission.
    see more here: http://www.cdrf.co/3.9/rest_framework.viewsets/ModelViewSet.html

    THIS MODEL IS INHERITED BY EVERY VIEWSET ( except homepage... ) !!
    """

    permission_classes_by_action = {}
    login_url = "/accounts/login/"

    def get_permissions(self):
        print(f"Action: {self.action}")

        try:
            return [
                permission()
                for permission in self.permission_classes_by_action[self.action]
            ]
        except KeyError:
            print(f"KeyError for permission: {self.action}")

            return [permission() for permission in self.permission_classes]

    def handle_no_permission(self):
        if self.raise_exception or self.request.user.is_authenticated:
            raise PermissionDenied(self.get_permission_denied_message())

        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name(),
        )


class CourseFilter(filters.FilterSet):
    # activity =
    # filter_fields = ('course_activity','instructors__username','course_schools__abbreviation','course_subjects__abbreviation',) #automatically create a FilterSet class
    # https://github.com/philipn/django-rest-framework-filters/issues/102
    # pls see: https://django-filter.readthedocs.io/en/master/ref/filters.html
    # https://django-filter.readthedocs.io/en/master/ref/filters.html#modelchoicefilter
    activity = filters.ModelChoiceFilter(
        queryset=Activity.objects.all(), field_name="course_activity", label="Activity"
    )
    instructor = filters.CharFilter(
        field_name="instructors__username", label="Instructor"
    )
    # school = filters.CharFilter(field_name='course_schools__abbreviation',label='School (abbreviation)')
    school = filters.ModelChoiceFilter(
        queryset=School.objects.all(),
        field_name="course_schools",
        to_field_name="abbreviation",
        label="School (abbreviation)",
    )

    subject = filters.CharFilter(
        field_name="course_subject__abbreviation", label="Subject (abbreviation)"
    )
    term = filters.ChoiceFilter(
        choices=Course.TERM_CHOICES, field_name="course_term", label="Term"
    )

    class Meta:
        model = Course
        # fields using custom autocomplete = ['instructor', 'subject']

        fields = [
            "term",
            "activity",
            "school",
            "instructor",
            "subject",
        ]  # ,'activity', school


class CourseViewSet(MixedPermissionModelViewSet, viewsets.ModelViewSet):
    current_date = datetime.now()
    month_terms = {
        1: "A",
        2: "A",
        3: "A",
        4: "A",
        5: "B",
        6: "B",
        7: "B",
        8: "B",
        9: "C",
        10: "C",
        11: "C",
        12: "C",
    }
    lookup_field = "course_code"
    queryset = Course.objects.filter(
        course_subject__visible=True,
        course_schools__visible=True,
        year__gte=current_date.year,
        course_term__gte=month_terms.get(current_date.month),
    )
    serializer_class = CourseSerializer
    search_fields = (
        "$course_name",
        "$course_code",
    )
    filterset_class = CourseFilter
    permission_classes_by_action = {
        "create": [IsAdminUser],
        "list": [IsAuthenticated],
        "retrieve": [IsAuthenticated],
        "update": [IsAdminUser],
        "partial_update": [IsAdminUser],
        "delete": [IsAdminUser],
    }

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True,
                fields=[
                    "course_subject",
                    "course_code",
                    "requested",
                    "instructors",
                    "course_activity",
                    "year",
                    "course_term",
                    "course_primary_subject",
                    "course_number",
                    "course_section",
                    "course_name",
                    "multisection_request",
                    "request",
                    "crosslisted",
                    "requested_override",
                    "associated_request",
                ],
            )
            response = self.get_paginated_response(serializer.data)

            if request.accepted_renderer.format == "html":
                response.template_name = "course_list.html"
                response.data = {
                    "results": response.data,
                    "paginator": self.paginator,
                    "filter": CourseFilter,
                    "request": request,
                    "is_staff": request.user.is_staff,
                    "autocompleteUser": UserForm(),
                    "autocompleteSubject": SubjectForm(),
                    "style": {"template_pack": "rest_framework/vertical/"},
                }

            return response

    def retrieve(self, request, *args, **kwargs):
        print("in CourseViewSet.retrieve()")
        response = super(CourseViewSet, self).retrieve(request, *args, **kwargs)
        print("response")

        if request.accepted_renderer.format == "html":
            course_instance = self.get_object()

            if course_instance.requested is True:

                if course_instance.multisection_request:
                    request_instance = ""
                else:
                    request_instance = course_instance.get_request()
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
                    "request_instance": request_instance,
                    "request_form": this_form,
                    "autocompleteCanvasSite": CanvasSiteForm(),
                    "is_staff": request.user.is_staff,
                    "style": {"template_pack": "rest_framework/vertical/"},
                },
                template_name="course_detail.html",
            )
        else:

            return response


class RequestFilter(filters.FilterSet):
    # activity =
    # filter_fields = ('course_activity','instructors__username','course_schools__abbreviation','course_subjects__abbreviation',) #automatically create a FilterSet class
    # https://github.com/philipn/django-rest-framework-filters/issues/102
    # pls see: https://django-filter.readthedocs.io/en/master/ref/filters.html
    status = filters.ChoiceFilter(
        choices=Request.REQUEST_PROCESS_CHOICES, field_name="status", label="Status"
    )
    requestor = filters.CharFilter(
        field_name="owner__username", label="Requestor"
    )  # does not include masquerade! and needs validator on input!
    date = filters.DateTimeFilter(field_name="created", label="Created")
    school = filters.ModelChoiceFilter(
        queryset=School.objects.all(),
        field_name="course_requested__course_schools",
        to_field_name="abbreviation",
        label="School (abbreviation)",
    )
    term = filters.ChoiceFilter(
        choices=Course.TERM_CHOICES,
        field_name="course_requested__course_term",
        label="Term",
    )

    class Meta:
        model = Request
        fields = ["status", "requestor", "date", "school", "term"]
        # fields = ['activity','instructor','school','subject','term']


class RequestViewSet(MixedPermissionModelViewSet, viewsets.ModelViewSet):
    queryset = Request.objects.all()
    serializer_class = RequestSerializer
    filterset_class = RequestFilter
    search_fields = [
        "$course_requested__course_name",
        "$course_requested__course_code",
    ]
    permission_classes = (permissions.IsAuthenticated,)
    permission_classes_by_action = {
        "create": [IsAuthenticated],
        "list": [IsAuthenticated],
        "retrieve": [IsAuthenticated],
        "update": [IsAuthenticated],
        "partial_update": [IsAuthenticated],
        "delete": [IsAdminUser],
    }

    def create(self, request, *args, **kwargs):
        def update_course(self, course):
            course.save()

            if course.crosslisted:
                for crosslisted in course.crosslisted.all():
                    crosslisted.request = course.request
                    crosslisted.save()

            crosslisted = course.crosslisted

        try:
            masquerade = request.session["on_behalf_of"]
        except KeyError:
            masquerade = ""

        course = Course.objects.get(course_code=request.data["course_requested"])
        instructors = course.get_instructors()

        if instructors == "STAFF":
            instructors = None

        self.custom_permissions(None, masquerade, instructors)
        additional_enrollments_partial = html.parse_html_list(
            request.data, prefix="additional_enrollments"
        )
        additional_sections_partial = html.parse_html_list(
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
            serializer = self.get_serializer(data=data_dict)
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

            if "view_type" in request.data:
                if request.data["view_type"] == "UI-course-list":
                    data["reserves"] = course.course_schools.abbreviation in [
                        "SAS",
                        "SEAS",
                        "FA",
                        "PSOM",
                        "SP2",
                    ]

            serializer = self.get_serializer(data=data)

        serializer.is_valid()

        if not serializer.is_valid():
            messages.add_message(request, messages.ERROR, serializer.errors)

            raise serializers.ValidationError(serializer.errors)

        serializer.validated_data["masquerade"] = masquerade
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        course = Course.objects.get(course_code=request.data["course_requested"])
        update_course(self, course)

        if "view_type" in request.data:
            if request.data["view_type"] == "UI-course-list":
                return redirect("UI-course-list")

            if request.data["view_type"] == "home":
                return redirect("home")

            if request.data["view_type"] == "UI-request-detail":
                return redirect(
                    "UI-request-detail-success",
                    pk=course.course_code,
                )

        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
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
                    "results": response.data,
                    "paginator": self.paginator,
                    "filter": RequestFilter,
                    "autocompleteUser": UserForm(),
                }

            return response

    def custom_permissions(self, request_obj, masquerade, instructors):
        if self.request.user.is_staff:
            return True

        if self.request.method == "GET":
            if not masquerade:
                if (
                    self.request.user.username == request_obj["owner"]
                    or self.request.user.username == request_obj["masquerade"]
                ):
                    return True
                else:
                    raise PermissionDenied(
                        {"message": "You don't have permission to access"}
                    )

                    return False

            elif (
                masquerade == request_obj["owner"]
                or masquerade == request_obj["masquerade"]
            ):
                return True
            else:
                raise PermissionDenied(
                    {"message": "You don't have permission to access"}
                )

                return False

        if self.request.method == "POST":
            if instructors:
                if self.request.user.username in instructors:
                    return True
                elif masquerade and masquerade in instructors:
                    return True
                else:
                    raise PermissionDenied(
                        {"message": "You don't have permission to access"}
                    )

                    return False
            else:
                return True
        else:
            return False

    def check_request_update_permissions(request, response_data):
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
        response = super(RequestViewSet, self).retrieve(request, *args, **kwargs)
        if request.resolver_match.url_name == "UI-request-detail-success":
            return Response(
                {"request_instance": response.data},
                template_name="request_success.html",
            )

        if request.accepted_renderer.format == "html":
            permissions = RequestViewSet.check_request_update_permissions(
                request, response.data
            )

            if request.resolver_match.url_name == "UI-request-detail-edit":
                here = RequestSerializer(
                    self.get_object(), context={"request": request}
                )

                return Response(
                    {
                        "request_instance": response.data,
                        "permissions": permissions,
                        "request_form": here,
                        "autocompleteCanvasSite": CanvasSiteForm(),
                        "style": {"template_pack": "rest_framework/vertical/"},
                    },
                    template_name="request_detail_edit.html",
                )

            return Response(
                {"request_instance": response.data, "permissions": permissions},
                template_name="request_detail.html",
            )
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
        additional_enrollments_partial = html.parse_html_list(
            request.data, prefix="additional_enrollments"
        )
        additional_sections_partial = html.parse_html_list(
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
            messages.add_message(request, messages.ERROR, serializer.errors)

            raise serializers.ValidationError(serializer.errors)
        else:
            serializer.save(owner=self.request.user)

        self.perform_update(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}

        if "status" in request.data:
            if request.data["status"] == "LOCKED":
                email_processor.admin_lock(
                    context={
                        "request_detail_url": request.build_absolute_uri(
                            reverse(
                                "UI-request-detail",
                                kwargs={"pk": request.data["course_requested"]},
                            )
                        ),
                        "course_code": request.data["course_requested"],
                    }
                )

        if "view_type" in request.data:
            if request.data["view_type"] == "UI-request-detail":
                permissions = RequestViewSet.check_request_update_permissions(
                    request,
                    {
                        "owner": instance.owner.username,
                        "masquerade": instance.masquerade,
                        "status": instance.status,
                    },
                )

                return Response(
                    {"request_instance": serializer.data, "permissions": permissions},
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


class UserViewSet(MixedPermissionModelViewSet, viewsets.ModelViewSet):
    """
    This viewset automatically provides `list` and `detail` actions. (READONLY)
    """

    # only admins ( user.is_staff ) can do anything with this data
    permission_classes = (permissions.IsAdminUser,)
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = "username"
    # filter_backends = (DjangoFilterBackend,)
    filterset_fields = ("profile__penn_id",)
    permission_classes_by_action = {
        "create": [],
        "list": [],
        "retrieve": [],
        "update": [],
        "partial_update": [],
        "delete": [],
    }

    """
    # this is just to havet the pk be username and not id
    def retrieve(self, request, pk=None):
        #print("IM DOING MY BEST")
        instance = User.objects.filter(username=pk)
        #print(instance)


        serializer = self.get_serializer(instance)
        return Response(serializer.data)

        return Response(serializer.data)
    """


class SchoolViewSet(MixedPermissionModelViewSet, viewsets.ModelViewSet):
    """
    This viewset only provides custom `list` actions
    """

    # # TODO:
    # [ ] ensure POST is only setting masquerade
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes_by_action = {
        "create": [],
        "list": [],
        "retrieve": [],
        "update": [],
        "partial_update": [],
        "delete": [],
    }

    #    def perform_create(self, serializer):
    #        serializer.save(owner=self.request.user)
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        # print("1")
        if page is not None:

            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(
                serializer.data
            )  # http://www.cdrf.co/3.9/rest_framework.viewsets/ModelViewSet.html#paginate_queryset
            # print("template_name",response.template_name)
            if request.accepted_renderer.format == "html":
                response.template_name = "schools_list.html"
                # print("template_name",response.template_name)
                response.data = {"results": response.data, "paginator": self.paginator}
            # print("request.accepted_renderer.format",request.accepted_renderer.format)
            return response
        """
        serializer = self.get_serializer(queryset, many=True)
        response = Response(serializer.data)
        if request.accepted_renderer.format == 'html':
            #print("template_name",response.template_name)
            response.template_name = 'schools_list.html'
            #print("template_name",response.template_name)
            response.data = {'results': response.data}
        return response
        """

    def post(self, request, *args, **kwargs):
        # print("posting")
        # if request.user.is_authenticated():

        """
        #need to check if the post is for masquerade
        #print(request.get_full_path())
        set_session(request)
        return(redirect(request.get_full_path()))
        """

    def update(self, request, *args, **kwargs):
        # print("update?")
        # print("args",args)
        # print("kwargs", kwargs)
        # print("request.data", request.data)
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}
        if request.data.get("view_type", None) == "UI":
            pass
            # print("its happening")

        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        # print("this is dumb",request.method)
        # print("self.lookup_field: ",self.lookup_field)
        # this response should probably be paginated but thats a lot of work ..
        response = super(SchoolViewSet, self).retrieve(request, *args, **kwargs)
        if request.accepted_renderer.format == "html":
            return Response({"data": response.data}, template_name="school_detail.html")
        return response


class SubjectViewSet(MixedPermissionModelViewSet, viewsets.ModelViewSet):
    """
    This viewset only provides custom `list` actions
    """

    # # TODO:
    # [ ] ensure POST is only setting masquerade

    # lookup_field = 'abbreviation'
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes_by_action = {
        "create": [],
        "list": [],
        "retrieve": [],
        "update": [],
        "partial_update": [],
        "delete": [],
    }
    #    def perform_create(self, serializer):
    #        serializer.save(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        # print("request.data", request.data)
        serializer = self.get_serializer(data=request.data)
        # print("serializer",serializer)
        serializer.is_valid(raise_exception=True)
        # print("ok")
        self.perform_create(serializer)
        # print("ok2")
        headers = self.get_success_headers(serializer.data)
        # print("serializer.data",serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def list(self, request, *args, **kwargs):
        # print("in list")
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        # print("1")
        if page is not None:

            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(
                serializer.data
            )  # http://www.cdrf.co/3.9/rest_framework.viewsets/ModelViewSet.html#paginate_queryset
            # print("template_name",response.template_name)

            if request.accepted_renderer.format == "html":
                response.template_name = "subjects_list.html"
                response.data = {"results": response.data, "paginator": self.paginator}
            return response
        """
        serializer = self.get_serializer(queryset, many=True)
        response = Response(serializer.data)
        if request.accepted_renderer.format == 'html':
            #print("template_name",response.template_name)
            response.template_name = 'subjects_list.html'
            #print("template_name",response.template_name)
            response.data = {'results': response.data}
        return response
        """

    def post(self, request, *args, **kwargs):
        # if request.user.is_authenticated():

        """
        #need to check if the post is for masquerade
        #print(request.get_full_path())
        set_session(request)
        return(redirect(request.get_full_path()))
        """

    def retrieve(self, request, *args, **kwargs):
        response = super(SubjectViewSet, self).retrieve(request, *args, **kwargs)

        if request.accepted_renderer.format == "html":
            return Response(
                {"data": response.data}, template_name="subject_detail.html"
            )

        return response


class NoticeViewSet(MixedPermissionModelViewSet, viewsets.ModelViewSet):
    """
    THIS IS A TEMPORARY COPY
    """

    queryset = Notice.objects.all()
    serializer_class = NoticeSerializer
    permission_classes_by_action = {
        "create": [],
        "list": [],
        "retrieve": [],
        "update": [],
        "partial_update": [],
        "delete": [],
    }

    def perform_create(self, serializer):
        # print("NoticeViewSet - perform_create trying to create Notice")
        serializer.save(owner=self.request.user)


class CanvasSiteViewSet(MixedPermissionModelViewSet, viewsets.ModelViewSet):
    queryset = CanvasSite.objects.all()
    serializer_class = CanvasSiteSerializer
    lookup_field = "canvas_id"
    permission_classes_by_action = {
        "create": [],
        "list": [],
        "retrieve": [],
        "update": [],
        "partial_update": [],
        "delete": [],
    }

    def get_queryset(self):
        user = self.request.user

        return CanvasSite.objects.filter(Q(owners=user) | Q(added_permissions=user))

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)

            if request.accepted_renderer.format == "html":
                response.template_name = "canvassite_list.html"
                response.data = {"results": response.data, "paginator": self.paginator}

            return response

    def retrieve(self, request, *args, **kwargs):
        response = super(CanvasSiteViewSet, self).retrieve(request, *args, **kwargs)
        if request.accepted_renderer.format == "html":
            return Response(
                {"data": response.data, "autocompleteUser": UserForm()},
                template_name="canvassite_detail.html",
            )
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = {"added_permissions": [request.data["username"]]}
        print("mydata", data)
        serializer = self.get_serializer(instance, data=data, partial=True)
        print("ok")
        serializer.is_valid(raise_exception=True)
        print("ok2")
        self.perform_update(serializer)
        return Response(
            {"data": serializer.data, "autocompleteUser": UserForm()},
            template_name="canvassite_detail.html",
        )

        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}
        if request.data.get('view_type',None) == 'UI':
            pass
            #print("its happening")

        return Response(serializer.data)
        """


class HomePage(APIView, UserPassesTestMixin):  # ,
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "home_content.html"
    login_url = "/accounts/login/"
    permission_classes_by_action = {
        "create": [],
        "list": [],
        "retrieve": [],
        "update": [],
        "partial_update": [],
        "delete": [],
    }

    permission_classes = (permissions.IsAuthenticated,)

    def test_func(self):
        user_name = self.request.user.username
        print(f'Checking Users for "{user_name}"...')
        user = User.objects.get(username=self.request.user.username)

        try:
            if user.profile:
                print(f'FOUND user "{user_name}".')

                return True
        except Exception:
            user_data = datawarehouse_lookup(penn_key=user.username)

            if user_data:
                user.first_name = user_data["firstname"].title()
                user.last_name = user_data["lastname"].title()
                user.email = user_data["email"]
                Profile.objects.create(user=user, penn_id=user_data["penn_id"])
                update_user_courses(user.username)

                print(f'CREATED user "{user_name}".')

                return True
            else:
                print(f'FAILED to create user "{user_name}".')

                return False

    def get(self, request, *args, **kwargs):
        # # TODO:
        # [x] Check that valid pennkey
        # [x] handles if there are no notice instances in the db
        # print("request.user",request.user)
        # print("in home")

        self.test_func()

        try:
            notice = Notice.objects.latest()
            # print(Notice.notice_text)
        except Notice.DoesNotExist:
            notice = None
            # print("no notices")

        # this should get the courses from this term !
        # currently we are just getting the courses that have not been requested
        masquerade = request.session["on_behalf_of"]
        if masquerade:
            user = User.objects.get(username=masquerade)
        else:
            user = request.user

        courses = Course.objects.filter(instructors=user, course_schools__visible=True)
        courses_count = courses.count()
        courses = courses[:15]  # requested=False
        # print(courses)
        # print("1",user,"2",user.username)
        site_requests = Request.objects.filter(Q(owner=user) | Q(masquerade=user))
        site_requests_count = site_requests.count()
        site_requests = site_requests[:15]

        canvas_sites = CanvasSite.objects.filter(Q(owners=user))
        canvas_sites_count = canvas_sites.count()
        canvas_sites = canvas_sites[:15]
        # for courses do instructors.courses since there is a manytomany relationship
        return Response(
            {
                "data": {
                    "notice": notice,
                    "site_requests": site_requests,
                    "site_requests_count": site_requests_count,
                    "srs_courses": courses,
                    "srs_courses_count": courses_count,
                    "canvas_sites": canvas_sites,
                    "canvas_sites_count": canvas_sites_count,
                    "username": request.user,
                }
            }
        )

    # get the user id and then do three queries to create these tables
    # you should get the user id of the auth.user or if they are masquerading get the id of that user
    # 1. Site Requests
    # 2. SRS Courses
    # 3. Canvas Sites

    #    def post(self, request,*args, **kwargs):
    #        return redirect(request.path)

    def set_session(request):
        print("set_session request.data", request.data)
        try:
            on_behalf_of = request.data["on_behalf_of"].lower()
            print("found on_behalf_of in request.data ", on_behalf_of)
            if on_behalf_of:  # if its not none -> if exists then see if pennkey works
                lookup_user = validate_pennkey(on_behalf_of)
                if lookup_user is None:  # if pennkey is good the user exists
                    print("not valid input")
                    messages.error(
                        request, "Invalid Pennkey -- Pennkey must be Upenn Employee"
                    )
                    on_behalf_of = None
                elif lookup_user.is_staff is True:
                    messages.error(
                        request,
                        "Invalid Pennkey -- Pennkey cannot be Courseware Team Member",
                    )
                    on_behalf_of = None

        except KeyError as error:
            print(f"HERE IS THE ERROR: {error}")
            pass
        # check if user is in the system
        request.session["on_behalf_of"] = on_behalf_of
        # print("masquerading as:", request.session['on_behalf_of'])

    def post(self, request, *args, **kwargs):
        # if request.user.is_authenticated():
        # need to check if the post is for masquerade
        # print("posting in home")
        # print("\trequest.get_full_path()",request.get_full_path())
        # print("\trequest.META[''HTTP_REFERER'']",request.META['HTTP_REFERER'])
        HomePage.set_session(request)
        print("HomePage.set_session!")
        return redirect(request.META["HTTP_REFERER"])


class AutoAddViewSet(MixedPermissionModelViewSet, viewsets.ModelViewSet):
    """
    provides list create and destroy actions only
    no update or detail actions.
    """

    queryset = AutoAdd.objects.all()
    serializer_class = AutoAddSerializer
    permission_classes_by_action = {
        "create": [IsAdminUser],
        "list": [IsAdminUser],
        "retrieve": [IsAdminUser],
        "update": [IsAdminUser],
        "partial_update": [IsAdminUser],
        "delete": [IsAdminUser],
    }

    def create(self, request, *args, **kwargs):
        # print(self.request.user)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        # print("headers",headers)
        # print("autoadd data",serializer.data) # {'url': 'http://127.0.0.1:8000/api/autoadds/1/', 'user': 'username_8', 'school': 'AN', 'subject': 'abbr_2', 'id': 1, 'role': 'ta'}
        response = Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

        email_processor.autoadd_contact(
            {
                "user": serializer.data["user"],
                "role": serializer.data["role"],
                "school": School.objects.get(
                    abbreviation=serializer.data["school"]
                ).name,
                "subject": Subject.objects.get(
                    abbreviation=serializer.data["subject"]
                ).name,
            }
        )
        # print("got here")
        if request.accepted_renderer.format == "html":
            response.template_name = "admin/autoadd_list.html"
            return redirect("UI-autoadd-list")
        return response

    def list(self, request, *args, **kwargs):
        # print(request.user.is_authenticated())
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        # print("1")

        if page is not None:

            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(
                serializer.data
            )  # http://www.cdrf.co/3.9/rest_framework.viewsets/ModelViewSet.html#paginate_queryset
            # print("template_name",response.template_name)
            if request.accepted_renderer.format == "html":
                response.template_name = "admin/autoadd_list.html"
                # print("template_name",response.template_name)
                # print("qqq",repr(AutoAddSerializer))
                # print("qqqq",AutoAddSerializer.fields)
                response.data = {
                    "results": response.data,
                    "paginator": self.paginator,
                    "serializer": AutoAddSerializer,
                    "autocompleteUser": UserForm(),
                }
            # print("request.accepted_renderer.format",request.accepted_renderer.format)
            # print("yeah ok1",response.items())
            return response

    def destroy(self, request, *args, **kwargs):
        # print("ss")
        instance = self.get_object()
        self.perform_destroy(instance)
        # print("ok", request.path)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        if "UI" in request.data:
            if request.data["UI"] == "true":

                response.template_name = "admin/autoadd_list.html"
                return redirect("UI-autoadd-list")
        return response


class UpdateLogViewSet(MixedPermissionModelViewSet, viewsets.ModelViewSet):
    """
    THIS IS A TEMPORARY COPY
    This viewset automatically provides `list` and `detail` actions.
    """

    # permission_classes = (IsAdminUser,)
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
        # print("yeah ok")
        # see more about the models here https://django-celery-beat.readthedocs.io/en/latest/index.html
        # https://medium.com/the-andela-way/crontabs-in-celery-d779a8eb4cf
        periodic_tasks = PeriodicTask.objects.all()
        return Response({"data": periodic_tasks}, template_name="admin/log_list.html")


# --------------- Redirect to Google Form -------------------
def googleform(request):
    return redirect(
        "https://docs.google.com/forms/d/e/1FAIpQLSeyF8mcCvvA4J4jQEmeNXCgjbHd4bG_2GfXEPgtezvljLV-pw/viewform"
    )


# --------------- USERINFO view -------------------

# @login_required(login_url='/accounts/login/')
def userinfo(request):

    form = EmailChangeForm(request.user)
    form2 = UserForm()
    # print(request.method)
    if request.method == "POST":
        form = EmailChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            return redirect("userinfo")  # this should redirect to success page
    return render(request, "user_info.html", {"form": form, "form2": form2})


# -------------- DWHSE Proxies ----------------
def DWHSE_Proxy(request):
    # if request.method == "GET":
    #     pennkey = request.GET.get("pennkey", "")
    #     firstName = request.GET.get("firstName", "")
    #     lastName = request.GET.get("lastName", "")
    #     email = request.GET.get("email", "")
    #     print(pennkey)
    #     staffResults = None
    #     studentResults = None

    return JsonResponse({})


# -------------- Canvas Proxies ----------------
def myproxy(request, username):

    print("user", username)
    login_id = username
    data = get_user_by_sis(login_id)
    print(data)
    print(data.get_courses())
    other = []
    courses = data.get_courses(enrollment_type="teacher")
    items = ["id", "name", "sis_course_id", "workflow_state"]
    for course in courses:

        other += [{k: course.attributes.get(k, "NONE") for k in items}]
    print(other)
    final = data.attributes
    final["courses"] = other
    return JsonResponse(final)


def autocompleteCanvasCourse(request, search):
    if True:  # request.is_ajax():
        q = urllib.parse.unquote(search)
        print("q", q)  #
        canvas = get_canvas()
        account = canvas.get_account(96678)
        search_qs = account.get_courses(
            search_term=q, search_by="course", sort="course_name", per_page=10
        )[:10]
        results = []
        for r in search_qs:
            print(r)
            print({"label": r.name, "value": r.id})
            # print(r['course']['name'])
            # results.append(r['course']['name'])
            results.append({"label": r.name, "value": r.id})
        # data = json.dumps(search_qs)
        data = json.dumps(results)
    else:
        data = "fail"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)


# ------------- TEMPORARY PROCESS REQUESTS --------


@staff_member_required
def process_requests(request):

    response = {"response": "response", "processed": []}
    approved_requests = Request.objects.filter(status="APPROVED")

    if approved_requests.exists():
        for approved_request in approved_requests:
            response["processed"] += [
                {
                    "course_code": approved_request.course_requested.course_code,
                    "status": "",
                    "notes": "",
                }
            ]

        try:
            create_canvas_sites()
        except Exception as error:
            error = str(error)
            response["error"] = error
            getLogger("error_logger").error(error)

        for processed_request in response["processed"]:
            request_object = Request.objects.get(
                course_requested=processed_request["course_code"]
            )
            processed_request["status"] = request_object.status
            processed_request["notes"] = request_object.process_notes

        response["response"] = datetime.now().strftime("%m/%d/%y %I:%M%p")

        log_path = Path("course/static/log")

        if not log_path.exists():
            mkdir(log_path)

        with open("course/static/log/result.json", "w+") as fp:
            json.dump(response, fp)
    else:
        response["processed"] = "No Approved Requests to Process"

    return JsonResponse(response)


@staff_member_required
def view_requests(request):
    try:
        with open("course/static/log/result.json") as json_file:
            data = json.load(json_file)

        return JsonResponse(data)
    except Exception:
        return JsonResponse({"response": "no data to display"})


@staff_member_required
def view_canceled_SRS(request):
    with open("course/static/log/deleted_courses_issues.log") as content:
        # data = json.load(json_file)
        return HttpResponse(content, content_type="text/plain; charset=utf8")
        # return django.http.JsonResponse(json_file)


@staff_member_required
def remove_canceled_requests(request):

    done = {"response": "", "processed": []}
    canceled_requests = Request.objects.filter(status="CANCELED")

    for request in canceled_requests:
        done["processed"] += [request.course_requested.course_code]

    done["response"] = datetime.now().strftime("%m/%d/%y %I:%M%p")

    return JsonResponse(done)


# --------- Quick Config of Canvas (enrollment/add tool) ----------
def quickconfig(request):
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
                    canvas_user.id,
                    roles[role],
                    enrollment={
                        "role_id": "1383",
                        "enrollment_state": "active",
                    },
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
                user = validate_pennkey(pennkey)

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


def side_sign_in(request):

    config = ConfigParser()
    config.read("config/config.ini")
    name = request.user.username + "_test"
    passwrd = config.get("users_test", "pass")
    user = authenticate(username=name, password=passwrd)
    login(request, user)
    return redirect("/")


# -------------- OpenData Proxy ----------------
def openDataProxy(request):
    """
    Access the parameters passed by POST, you need to access this way:
    request.data.get('role', None)
    """
    data = {"data": "none"}
    size = 0
    print("Course lookup failed.")

    if request.GET:
        try:
            course_id = request.GET.get("course_id", None)
            term = request.GET.get("term", None)
            instructor = request.GET.get("instructor", None)
            config = ConfigParser()
            config.read("config/config.ini")
            domain = config.get("opendata", "domain")
            id = config.get("opendata", "id2")
            key = config.get("opendata", "key2")
            OD = open_data.OpenData(domain, id, key)
            OD.set_uri("course_section_search")
            OD.add_param("course_id", course_id)

            if term:
                OD.add_param("term", term)

            OD.add_param("number_of_results_per_page", 5)

            if instructor:
                OD.add_param("instructor", instructor)

            data["data"] = OD.call_api()

            if isinstance(data["data"], list):
                size = len(data["data"])
            else:
                size = 1
        except Exception as error:
            print(f"ERROR (OpenData): {error}")

    return render(request, "admin/course_lookup.html", {"data": data, "size": size})


def check_data_warehouse_for_course(request):
    data = {"data": {}}
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
            course_code = request.GET.get("course_code", None)
            results = inspect_course(course_code, verbose=False)
            size = len(results)
            data["results"] = results

            if not data["results"]:
                data["data"] = "COURSE NOT FOUND"

            for course in data["results"]:
                course_code = course[0]
                data["data"][course_code] = dict()

                for index, item in enumerate(course[1:]):
                    data["data"][course_code][headers[index]] = item

            data.pop("results", None)
        except Exception as error:
            print(f"ERROR (Data Warehouse): {error}")

    return render(request, "admin/dw_lookup.html", {"data": data, "size": size})


# ---------------- AUTO COMPLETE -------------------


def autocompleteModel(request):
    if request.is_ajax():
        q = request.GET.get("term", "").capitalize()
        print("q", q)
        search_qs = User.objects.filter(username__startswith=q)
        results = []
        for r in search_qs:
            results.append(r.username)
        data = json.dumps(results)
    else:
        data = "fail"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)


def autocompleteSubjectModel(request):
    if request.is_ajax():
        q = request.GET.get("term", "").capitalize()
        print("q", q)
        search_qs = Subject.objects.filter(abbreviation__startswith=q)
        results = []
        for r in search_qs:
            results.append(r.abbreviation)
        data = json.dumps(results)
    else:
        data = "fail"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)


def autocompleteCanvasSiteModel(request):
    if request.is_ajax():
        q = request.GET.get("term", "").capitalize()
        search_qs = CanvasSite.objects.filter(Q(owners=q) | Q(added_permissions=q))
        results = []
        for r in search_qs:
            results.append(r.name)
        data = json.dumps(results)
    else:
        data = "fail"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)


# --------------- CONTACT view -------------------
# add to your views
def contact(request):
    form_class = ContactForm
    if request.method == "POST":
        form = form_class(data=request.POST)
        if form.is_valid():
            contact_name = request.POST.get("contact_name", "")
            contact_email = request.POST.get("contact_email", "")
            form_content = request.POST.get("content", "")

            # Email the profile with the
            # contact information
            context = {
                "contact_name": contact_name,
                "contact_email": contact_email,
                "form_content": form_content,
            }
            email_processor.feedback(context)
            return redirect("contact")
    return render(
        request,
        "contact.html",
        {
            "form": form_class,
        },
    )


# --------------- Temporary Email view -------------------
"""
This view is only for beta testing of the app
"""


def temporary_email_list(request):
    filelist = listdir("course/static/emails/")
    return render(request, "email/email_log.html", {"filelist": filelist})


def my_email(request, value):
    email = open("course/static/emails/" + value, "rb").read()
    return render(request, "email/email_detail.html", {"email": email.decode("utf-8")})


# SEE MORE: https://docs.djangoproject.com/en/2.1/topics/email/
