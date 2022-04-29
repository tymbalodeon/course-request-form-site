from django.contrib.admin import ModelAdmin, StackedInline, site
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

from .models import (
    AdditionalEnrollment,
    AutoAdd,
    Course,
    Notice,
    PageContent,
    Request,
    ScheduleType,
    School,
    Subject,
    User,
)


class CourseAdmin(ModelAdmin):
    list_display = [
        "course_code",
        "title",
        "get_instructors",
        "get_subjects",
        "get_schools",
        "term",
        "schedule_type",
        "requested",
    ]
    list_filter = ("schedule_type", "term", "school")
    search_fields = ("instructors__username", "course_code", "name")
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
                    "name",
                    (
                        "course_subject",
                        "course_number",
                        "course_section",
                        "year",
                        "term",
                    ),
                    "instructors",
                    "school",
                    "schedule_type",
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
                "fields": ("created_at", "updated_at", "owner"),
            },
        ),
    )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "course":
            kwargs["queryset"] = Course.objects.filter(
                school__abbreviation=request.user
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return [
                "created_at",
                "updated_at",
                "owner",
                "course_code",
                "course_section",
                "term",
                "year",
                "course_number",
                "course_subject",
                "requested",
                "request",
            ]
        else:
            return ["created_at", "updated_at", "owner", "course_code", "request"]

    def save_model(self, request, obj, form, change):
        obj.owner = request.user
        obj.save()


class AdditionalEnrollmentInline(StackedInline):
    model = AdditionalEnrollment
    extra = 2
    autocomplete_fields = ["user"]


class RequestAdmin(ModelAdmin):
    list_display = [
        "course_requested",
        "status",
        "requestors",
        "created_at",
        "updated_at",
    ]
    list_filter = (
        "status",
        "course_requested__term",
        "course_requested__school",
    )
    search_fields = (
        "requester__username",
        "masquerade",
        "course_requested__course_code",
    )
    readonly_fields = ["created_at", "updated_at", "masquerade", "additional_sections"]
    inlines = [AdditionalEnrollmentInline]
    autocomplete_fields = ["requester", "course_requested", "canvas_instance"]

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

        if obj.course_requested.school.abbreviation == "SAS":
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
                    "fields": ("created_at", "updated_at", "owner", "masquerade"),
                },
            ),
        )

    def additional_sections(self, instance):
        sections = list(Course.objects.filter(multisection_request=instance))
        sections = [section.course_code for section in sections]
        return ", ".join(sections) if sections else "-"

    def requestors(self, obj):
        if obj.masquerade != "":
            masquerade = f"{obj.owner.username} ({obj.masquerade})"
        else:
            masquerade = obj.owner.username

        return masquerade

    def save_model(self, request, obj, form, change):
        obj.save()


class AutoAddAdmin(ModelAdmin):
    autocomplete_fields = ["user"]
    list_display = [field.name for field in AutoAdd._meta.get_fields()]


site.register(User)
site.register(ScheduleType)
site.register(School)
site.register(Subject)
site.register(Course, CourseAdmin)
site.register(Request, RequestAdmin)
site.register(AdditionalEnrollment, AdditionalEnrollmentInline)
site.register(AutoAdd, AutoAddAdmin)
site.register(Notice)
site.register(PageContent)
