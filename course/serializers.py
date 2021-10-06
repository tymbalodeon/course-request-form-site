import collections

from django.contrib.auth.models import User
from rest_framework import serializers

from course.models import (
    Activity,
    AdditionalEnrollment,
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
from course.utils import validate_pennkey


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop("fields", None)
        super(DynamicFieldsModelSerializer, self).__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields)

            for field_name in existing - allowed:
                self.fields.pop(field_name)


class CourseSerializer(DynamicFieldsModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")
    course_code = serializers.CharField()
    crosslisted = serializers.SlugRelatedField(
        many=True,
        queryset=Course.objects.all(),
        slug_field="course_code",
        required=False,
    )
    requested = serializers.BooleanField(default=False)
    sections = serializers.SerializerMethodField()  #
    instructors = serializers.SlugRelatedField(
        many=True, queryset=User.objects.all(), slug_field="username"
    )
    course_schools = serializers.SlugRelatedField(
        many=False, queryset=School.objects.all(), slug_field="abbreviation"
    )
    course_subject = serializers.SlugRelatedField(
        many=False, queryset=Subject.objects.all(), slug_field="abbreviation"
    )
    course_activity = serializers.SlugRelatedField(
        many=False, queryset=Activity.objects.all(), slug_field="abbr"
    )
    id = serializers.ReadOnlyField()
    requested_override = serializers.ReadOnlyField()
    associated_request = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = "__all__"
        read_only_fields = ("sections",)

    def get_associated_request(self, obj):
        request = obj.get_request()

        return request.course_requested.course_code if request else None

    def get_sections(self, obj):
        return [
            (course.course_code, course.course_activity.abbr, course.requested)
            for course in obj.sections.all()
        ]

    def create(self, validated_data):
        instructors_data = validated_data.pop("instructors")
        course = Course.objects.create(**validated_data)

        for instructor_data in instructors_data:
            course.instructors.add(instructor_data)

        if "crosslisted" in validated_data:
            for cross_course in validated_data.pop("crosslisted"):
                course.crosslisted.add(cross_course)

        return course

    def update(self, instance, validated_data):
        if len(validated_data) == 1 and "crosslisted" in validated_data.keys():
            instance.crosslisted.set(
                validated_data.get("crosslisted", instance.crosslisted)
            )
            instance.save()
            crosslistings = validated_data.get("crosslisted", instance.crosslisted)

            for ccourse in crosslistings:
                crosslistings.remove(ccourse)
                current = ccourse.crosslisted.all()
                new = list(current) + list(crosslistings)
                ccourse.crosslisted.set(new)
                ccourse.requested = validated_data.get("requested", instance.requested)

            return instance
        else:
            instance.course_code = validated_data.get(
                "course_code", instance.course_code
            )
            instance.requested = validated_data.get("requested", instance.requested)
            instance.course_schools.set(
                validated_data.get("course_schools", instance.course_schools)
            )
            instance.instructors.set(
                validated_data.get("instructors", instance.instructors)
            )
            instance.crosslisted.set(
                validated_data.get("crosslisted", instance.crosslisted)
            )
            instance.save()
            crosslistings = validated_data.get("crosslisted", instance.crosslisted)

            for ccourse in crosslistings:
                crosslistings.remove(ccourse)
                current = ccourse.crosslisted.all()
                new = list(current) + list(crosslistings)
                ccourse.crosslisted.set(new)
                ccourse.requested = validated_data.get("requested", instance.requested)

            return instance


class UserSerializer(serializers.ModelSerializer):
    requests = serializers.HyperlinkedRelatedField(
        many=True, view_name="request-detail", read_only=True
    )
    penn_id = serializers.CharField(source="profile.penn_id")

    class Meta:
        model = User
        fields = (
            "id",
            "penn_id",
            "username",
            "courses",
            "requests",
            "email",
        )
        read_only_fields = ("courses",)

    def create(self, validated_data):
        pennid_data = validated_data.pop("profile")["penn_id"]
        user = User.objects.create(**validated_data)
        Profile.objects.create(user=user, penn_id=pennid_data)

        return user

    def update(self, instance, validated_data):
        instance.name = validated_data.get("username", instance.username)
        instance.save()

        return instance


class AdditionalEnrollmentSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(
        queryset=User.objects.all(),
        slug_field="username",
        style={"base_template": "input.html"},
    )

    class Meta:
        model = AdditionalEnrollment
        exclude = ("id", "course_request")


class CanvasSiteSerializer(serializers.ModelSerializer):
    owners = serializers.SlugRelatedField(
        many=True, queryset=User.objects.all(), slug_field="username"
    )
    added_permissions = serializers.SlugRelatedField(
        many=True, queryset=User.objects.all(), slug_field="username"
    )

    class Meta:
        model = CanvasSite
        fields = "__all__"

    def validate(self, data):
        return data

    def update(self, instance, validated_data):
        names = validated_data.pop("added_permissions")

        for name in names:
            instance.added_permissions.add(name)
        instance.save()

        return instance


class RequestSerializer(DynamicFieldsModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username", required=False)
    course_info = CourseSerializer(source="course_requested", read_only=True)
    canvas_instance = CanvasSiteSerializer(read_only=True)
    masquerade = serializers.ReadOnlyField()
    course_requested = serializers.SlugRelatedField(
        many=False,
        queryset=Course.objects.all(),
        slug_field="course_code",
        style={"base_template": "input.html"},
    )
    title_override = serializers.CharField(
        allow_null=True,
        required=False,
        max_length=45,
        style={"base_template": "input.html"},
    )
    lps_online = serializers.BooleanField(default=False)
    exclude_announcements = serializers.BooleanField(default=False)
    additional_enrollments = AdditionalEnrollmentSerializer(
        many=True,
        default=[],
        style={"base_template": "list_fieldset.html"},
        required=False,
    )
    created = serializers.DateTimeField(format="%I:%M%p %b,%d %Y", required=False)
    updated = serializers.DateTimeField(format="%I:%M%p %b,%d %Y", required=False)
    additional_sections = serializers.SlugRelatedField(
        many=True,
        default=[],
        queryset=Course.objects.all(),
        slug_field="course_code",
        required=False,
    )

    class Meta:
        model = Request
        fields = "__all__"

    def to_internal_value(self, data):
        def check_for_crf_account(enrollments):
            for enrollment in enrollments:
                print(f"Checking Users for {enrollment['user']}...")
                user = validate_pennkey(enrollment["user"])

                if user is None:
                    print(f"FAILED to find User {enrollment['user']}.")

        data = dict(data)

        if data.get("title_override", None) == "":
            data["title_override"] = None

        if data.get("course_requested", None) == "":
            data["course_requested"] = None

        if data.get("reserves", None) is None:
            data["reserves"] = False

        if data.get("additional_enrollments", None) is not None:
            check_for_crf_account(data["additional_enrollments"])

        return super(RequestSerializer, self).to_internal_value(data)

    def validate(self, data):
        if "additional_enrollments" in data.keys():
            if data["additional_enrollments"]:
                for enrollment in data["additional_enrollments"]:
                    print(f"Checking Users for {enrollment['user']}...")
                    user = validate_pennkey(enrollment["user"])

                    if user is None:
                        print(f"FAILED to find User {enrollment['user']}.")

                        raise serializers.ValidationError(
                            {
                                "error": (
                                    "An error occurred. Please check that the pennkeys"
                                    " you entered are correct and add the course"
                                    " information to the additional instructions field."
                                )
                            }
                        )

        return data

    def create(self, validated_data):
        add_enrolls_data = validated_data.pop("additional_enrollments")
        add_sections_data = validated_data.pop("additional_sections")
        autoadds = AutoAdd.objects.filter(
            school=validated_data["course_requested"].course_schools
        ).filter(subject=validated_data["course_requested"].course_subject)
        request_object = Request.objects.create(**validated_data)

        if add_enrolls_data:
            for enroll_data in add_enrolls_data:
                AdditionalEnrollment.objects.create(
                    course_request=request_object, **enroll_data
                )
        if autoadds:
            for autoadd in autoadds:
                enroll_data = collections.OrderedDict(
                    [("user", autoadd.user), ("role", autoadd.role)]
                )
                AdditionalEnrollment.objects.create(
                    course_request=request_object, **enroll_data
                )

        if add_sections_data:
            for section_data in add_sections_data:
                section = Course.objects.get(course_code=section_data.course_code)
                section.multisection_request = request_object
                section.save()

        course = validated_data["course_requested"]

        if course.crosslisted.all():
            for crosslisted_course in course.crosslisted.all():
                if course != crosslisted_course:
                    crosslisted_course.crosslisted_request = request_object
                    crosslisted_course.save()

        return request_object

    def update(self, instance, validated_data):
        new_status = validated_data.get("status", None)

        if new_status:
            instance.status = new_status
            instance.save()

            return instance

        instance.status = validated_data.get("status", instance.status)
        instance.title_override = validated_data.get(
            "title_override", instance.title_override
        )
        instance.copy_from_course = validated_data.get(
            "copy_from_course", instance.copy_from_course
        )
        instance.reserves = validated_data.get("reserves", instance.reserves)
        instance.additional_instructions = validated_data.get(
            "additional_instructions", instance.additional_instructions
        )
        instance.admin_additional_instructions = validated_data.get(
            "admin_additional_instructions", instance.admin_additional_instructions
        )
        add_enrolls_data = validated_data.get("additional_enrollments")

        if add_enrolls_data:
            AdditionalEnrollment.objects.filter(course_request=instance).delete()

            for enroll_data in add_enrolls_data:
                AdditionalEnrollment.objects.update_or_create(
                    course_request=instance, **enroll_data
                )

        add_sections_data = validated_data.get("additional_sections")
        c_data = instance.additional_sections.all()

        if add_sections_data or instance.additional_sections.all():
            for course in c_data:
                course.multisection_request = None
                course.requested = False
                course.save()
            instance.additional_sections.clear()

            for section_data in add_sections_data:
                section = Course.objects.get(course_code=section_data.course_code)
                section.multisection_request = instance
                section.save()

        instance.save()

        return instance


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = "__all__"

    def create(self, validated_data):
        return Subject.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get("name", instance.name)
        instance.abbreviation = validated_data.get(
            "abbreviation", instance.abbreviation
        )
        instance.visible = validated_data.get("visible", instance.visible)
        instance.save()

        return instance


class SchoolSerializer(serializers.ModelSerializer):
    subjects = SubjectSerializer(many=True, read_only=True)

    class Meta:
        model = School
        fields = (
            "name",
            "abbreviation",
            "visible",
            "subjects",
            "canvas_subaccount",
        )

    def create(self, validated_data):
        return School.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get("name", instance.name)
        instance.abbreviation = validated_data.get(
            "abbreviation", instance.abbreviation
        )
        instance.visible = validated_data.get("visible", instance.visible)
        instance.canvas_subaccount = validated_data.get(
            "canvas_subaccount", instance.canvas_subaccount
        )
        instance.save()

        return instance


class NoticeSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")
    id = serializers.ReadOnlyField()

    class Meta:
        model = Notice
        fields = "__all__"

    def create(self, validated_data):
        return Notice.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.notice_text = validated_data.get("notice_text", instance.notice_text)
        instance.save()

        return instance


class AutoAddSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.SlugRelatedField(
        many=False,
        queryset=User.objects.all(),
        slug_field="username",
        style={"base_template": "input.html"},
    )
    school = serializers.SlugRelatedField(
        many=False, queryset=School.objects.all(), slug_field="abbreviation"
    )
    subject = serializers.SlugRelatedField(
        many=False,
        queryset=Subject.objects.all(),
        slug_field="abbreviation",
        style={"base_template": "input.html"},
    )
    id = serializers.ReadOnlyField()

    class Meta:
        model = AutoAdd
        fields = "__all__"

    def create(self, validated_data):
        return AutoAdd.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.save()

        return instance


class UpdateLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UpdateLog
        fields = "__all__"

    def create(self, validated_data):
        return AutoAdd.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.save()

        return instance
