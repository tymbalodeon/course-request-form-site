import collections

from rest_framework.serializers import (
    BooleanField,
    CharField,
    DateTimeField,
    HyperlinkedModelSerializer,
    ModelSerializer,
    ReadOnlyField,
    SerializerMethodField,
    SlugRelatedField,
    ValidationError,
)

from data_warehouse.data_warehouse import get_user_by_pennkey

from .models import (
    AdditionalEnrollment,
    AutoAdd,
    Course,
    Notice,
    Request,
    ScheduleType,
    School,
    Subject,
    User,
)


class SubjectSerializer(ModelSerializer):
    class Meta:
        model = Subject
        fields = "__all__"

    def create(self, validated_data):
        return Subject.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get("name", instance.name)
        instance.subject_code = validated_data.get(
            "subject_code", instance.subject_code
        )
        instance.visible = validated_data.get("visible", instance.visible)
        instance.save()
        return instance


class SchoolSerializer(ModelSerializer):
    subjects = SubjectSerializer(many=True, read_only=True)

    class Meta:
        model = School
        fields = (
            "school_code",
            "school_desc_long",
            "visible",
            "subjects",
            "canvas_sub_account_id",
        )

    def create(self, validated_data):
        return School.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get("name", instance.name)
        instance.school_code = validated_data.get("school_code", instance.school_code)
        instance.visible = validated_data.get("visible", instance.visible)
        instance.canvas_sub_account_id = validated_data.get(
            "canvas_sub_account_id", instance.canvas_subaccount
        )
        instance.save()
        return instance


class DynamicFieldsModelSerializer(ModelSerializer):
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop("fields", None)
        super().__init__(*args, **kwargs)

        if fields:
            disallowed_fields = set(self.fields) - set(fields)
            for field in disallowed_fields:
                self.fields.pop(field)


class CourseSerializer(DynamicFieldsModelSerializer):
    id = ReadOnlyField()
    owner = ReadOnlyField(source="owner.username")
    course_code = CharField()
    crosslisted = SlugRelatedField(
        many=True,
        queryset=Course.objects.all(),
        slug_field="course_code",
        required=False,
    )
    requested = BooleanField(default=False)
    sections = SerializerMethodField()
    instructors = SlugRelatedField(
        many=True, queryset=User.objects.all(), slug_field="username"
    )
    course_schools = SlugRelatedField(
        many=False, queryset=School.objects.all(), slug_field="school_code"
    )
    course_subject = SlugRelatedField(
        many=False, queryset=Subject.objects.all(), slug_field="subject_code"
    )
    schedule_type = SlugRelatedField(
        many=False, queryset=ScheduleType.objects.all(), slug_field="sched_type_code"
    )
    requested_override = ReadOnlyField()
    associated_request = SerializerMethodField()

    class Meta:
        model = Course
        fields = "__all__"
        read_only_fields = ("sections",)

    def get_associated_request(self, obj):
        request = obj.get_request()
        if not request:
            return None
        return request.course_requested.course_code

    def get_sections(self, obj):
        sections = obj.sections.all()
        return [
            (course.course_code, course.schedule_type.sched_type_code, course.requested)
            for course in sections
        ]

    def create(self, validated_data):
        instructors = validated_data.pop("instructors")
        course = Course.objects.create(**validated_data)
        for instructor in instructors:
            course.instructors.add(instructor)
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
            for course in crosslistings:
                crosslistings.remove(course)
                current = course.crosslisted.all()
                new = list(current) + list(crosslistings)
                course.crosslisted.set(new)
                course.requested = validated_data.get("requested", instance.requested)
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
            for course in crosslistings:
                crosslistings.remove(course)
                current = course.crosslisted.all()
                new = list(current) + list(crosslistings)
                course.crosslisted.set(new)
                course.requested = validated_data.get("requested", instance.requested)
            return instance


class AdditionalEnrollmentSerializer(ModelSerializer):
    user = SlugRelatedField(
        queryset=User.objects.all(),
        slug_field="username",
        style={"base_template": "input.html"},
    )

    class Meta:
        model = AdditionalEnrollment
        exclude = ("id", "request")


class RequestSerializer(DynamicFieldsModelSerializer):
    owner = ReadOnlyField(source="owner.username", required=False)
    course_info = CourseSerializer(source="course_requested", read_only=True)
    masquerade = ReadOnlyField()
    course_requested = SlugRelatedField(
        many=False,
        queryset=Course.objects.all(),
        slug_field="course_code",
        style={"base_template": "input.html"},
    )
    title_override = CharField(
        allow_null=True,
        required=False,
        max_length=255,
        style={"base_template": "input.html"},
    )
    lps_online = BooleanField(default=False)
    exclude_announcements = BooleanField(default=False)
    additional_enrollments = AdditionalEnrollmentSerializer(
        many=True,
        default=[],
        style={"base_template": "list_fieldset.html"},
        required=False,
    )
    created = DateTimeField(format="%I:%M%p %b,%d %Y", required=False)
    updated = DateTimeField(format="%I:%M%p %b,%d %Y", required=False)
    additional_sections = SlugRelatedField(
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
                user = get_user_by_pennkey(enrollment["user"])
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
        if "additional_enrollments" in data.keys() and data["additional_enrollments"]:
            for enrollment in data["additional_enrollments"]:
                print(f"Checking Users for {enrollment['user']}...")
                user = get_user_by_pennkey(enrollment["user"])
                if not user:
                    print(f"FAILED to find User {enrollment['user']}.")
                    raise ValidationError(
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


class NoticeSerializer(HyperlinkedModelSerializer):
    id = ReadOnlyField()
    author = ReadOnlyField(source="author.username")

    class Meta:
        model = Notice
        fields = "__all__"

    def create(self, validated_data):
        return Notice.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.content = validated_data.get("content", instance.content)
        instance.save()
        return instance


class AutoAddSerializer(HyperlinkedModelSerializer):
    id = ReadOnlyField()
    user = SlugRelatedField(
        many=False, queryset=User.objects.all(), slug_field="username"
    )
    school = SlugRelatedField(
        many=False, queryset=School.objects.all(), slug_field="school_code"
    )
    subject = SlugRelatedField(
        many=False, queryset=Subject.objects.all(), slug_field="subject_code"
    )

    class Meta:
        model = AutoAdd
        fields = "__all__"

    def create(self, validated_data):
        return AutoAdd.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.school = validated_data.get("school", instance.school)
        instance.subject = validated_data.get("subject", instance.subject)
        instance.save()
        return instance
