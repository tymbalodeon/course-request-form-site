from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import (
    Count,
    DateTimeField,
    Exists,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Q,
    Sum,
)
from django.db.models.functions import Trunc

from .models import (
    Activity,
    AdditionalEnrollment,
    AutoAdd,
    CanvasSite,
    Course,
    Notice,
    PageContent,
    Profile,
    Request,
    RequestSummary,
    School,
    Subject,
    UpdateLog,
)


class AdditionalEnrollmentInline(admin.StackedInline):
    model = AdditionalEnrollment
    extra = 2
    autocomplete_fields = ["user"]


class CourseAdmin(admin.ModelAdmin):
    list_display = [
        "course_code",
        "course_name",
        "get_instructors",
        "get_subjects",
        "get_schools",
        "course_term",
        "course_activity",
        "requested",
    ]

    list_filter = ("course_activity", "course_term", "course_schools")
    search_fields = ("instructors__username", "course_code", "course_name")
    autocomplete_fields = [
        "crosslisted",
        "instructors",
        "multisection_request",
        "crosslisted_request",
    ]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "course_code",
                    "course_name",
                    (
                        "course_subject",
                        "course_number",
                        "course_section",
                        "year",
                        "course_term",
                    ),
                    "instructors",
                    "course_schools",
                    "course_activity",
                )
            },
        ),
        (
            "Crosslist info",
            {
                "fields": (
                    "crosslisted",
                    "primary_crosslist",
                    "course_primary_subject",
                ),
            },
        ),
        (
            "Request Info",
            {
                "fields": (
                    "requested",
                    "request",
                    "requested_override",
                    "multisection_request",
                    "crosslisted_request",
                ),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created", "updated", "owner"),
            },
        ),
    )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "course":
            kwargs["queryset"] = Course.objects.filter(
                course_schools__abbreviation=request.user
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return [
                "created",
                "updated",
                "owner",
                "course_code",
                "course_section",
                "course_term",
                "year",
                "course_number",
                "course_subject",
                "requested",
                "request",
            ]
        else:
            return ["created", "updated", "owner", "course_code", "request"]

    def save_model(self, request, obj, form, change):
        obj.owner = request.user
        obj.save()


class RequestAdmin(admin.ModelAdmin):
    list_display = [
        "course_requested",
        "status",
        "requestors",
        "created",
        "updated",
    ]
    list_filter = (
        "status",
        "course_requested__course_term",
        "course_requested__course_schools",
    )
    search_fields = ("owner__username", "masquerade", "course_requested__course_code")
    readonly_fields = ["created", "updated", "masquerade", "additional_sections"]
    inlines = [AdditionalEnrollmentInline]
    autocomplete_fields = ["owner", "course_requested", "canvas_instance"]

    def get_fieldsets(self, request, obj):
        fields = [
            "course_requested",
            "copy_from_course",
            "title_override",
            "additional_sections",
            "reserves",
            "additional_instructions",
            "admin_additional_instructions",
            "status",
            "canvas_instance",
        ]

        if obj.course_requested.course_schools.abbreviation == "SAS":
            fields.insert(1, "lps_online")

        if obj.copy_from_course:
            fields.insert(2, "exclude_announcements")

        return (
            (
                None,
                {"fields": tuple(fields)},
            ),
            (
                "Metadata",
                {
                    "fields": ("created", "updated", "owner", "masquerade"),
                },
            ),
        )

    def additional_sections(self, instance):
        return instance.additional_sections.course_code

    def requestors(self, obj):
        if obj.masquerade != "":
            masquerade = f"{obj.owner.username} ({obj.masquerade})"
        else:
            masquerade = obj.owner.username

        return masquerade

    def save_model(self, request, obj, form, change):
        obj.save()


class CanvasSiteAdmin(admin.ModelAdmin):
    autocomplete_fields = ["owners", "added_permissions", "request_instance"]
    list_display = ["name", "get_owners", "get_added_permissions"]
    search_fields = ("owners__username", "added_permissions__username", "name")


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]


class AutoAddAdmin(admin.ModelAdmin):
    autocomplete_fields = ["user"]
    list_display = [field.name for field in AutoAdd._meta.get_fields()]


def get_next_in_date_hierarchy(request, date_hierarchy):
    if date_hierarchy + "__day" in request.GET:
        return "hour"
    elif date_hierarchy + "__month" in request.GET:
        return "day"
    elif date_hierarchy + "__year" in request.GET:
        return "week"
    else:
        return "month"


class RequestSummaryAdmin(admin.ModelAdmin):
    change_list_template = "admin/request_summary_change_list.html"
    date_hierarchy = "created"
    list_filter = ("course_requested__course_term",)

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(
            request,
            extra_context=extra_context,
        )

        try:
            query_set = response.context_data["cl"].queryset
        except (AttributeError, KeyError):
            return response

        multisectionExists = query_set.filter(
            course_requested=OuterRef("pk"), additional_sections__isnull=False
        )
        metrics = {
            "total": Count("course_requested", distinct=True),
            "ares": Count("reserves", filter=Q(reserves=True)),
            "multisection": Sum(
                Exists(multisectionExists), output_field=IntegerField()
            ),
            "content_copy": Count("copy_from_course", filter=~Q(copy_from_course="")),
            "not_completed": Count(
                "status",
                filter=Q(
                    status__in=[
                        "IN_PROCESS",
                        "CANCELED",
                        "APPROVED",
                        "SUBMITTED",
                        "LOCKED",
                    ]
                ),
            ),
        }

        response.context_data["summary"] = list(
            query_set.values("course_requested__course_schools__abbreviation")
            .annotate()
            .order_by("course_requested__course_schools__abbreviation")
        )
        response.context_data["summary_total"] = dict(query_set.aggregate(**metrics))
        period = get_next_in_date_hierarchy(
            request,
            self.date_hierarchy,
        )
        response.context_data["period"] = period
        summary_over_time = (
            query_set.annotate(
                period=Trunc(
                    "created",
                    period,
                    output_field=DateTimeField(),
                ),
            )
            .values("period")
            .annotate(total=Count("course_requested"))
            .order_by("period")
        )
        summary_range = summary_over_time.aggregate(
            low=Min("total"),
            high=Max("total"),
        )
        high = summary_range.get("high", 0)
        low = summary_range.get("low", 0)
        response.context_data["summary_over_time"] = [
            {
                "period": x["period"],
                "total": x["total"] or 0,
                "pct": ((x["total"] or 0) - low) / (high - low) * 100
                if high > low
                else 0,
            }
            for x in summary_over_time
        ]

        return response


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(Request, RequestAdmin)
admin.site.register(Notice)
admin.site.register(School)
admin.site.register(Activity)
admin.site.register(Subject)
admin.site.register(AutoAdd, AutoAddAdmin)
admin.site.register(UpdateLog)
admin.site.register(PageContent)
admin.site.register(CanvasSite, CanvasSiteAdmin)
admin.site.register(RequestSummary, RequestSummaryAdmin)
