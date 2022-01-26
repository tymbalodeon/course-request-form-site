from logging import getLogger

from bleach import clean
from bleach_allowlist import markdown_attrs, markdown_tags
from django.contrib.auth.models import User
from django.db.models import (
    CASCADE,
    SET_NULL,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    IntegerField,
    Manager,
    ManyToManyField,
    Model,
    OneToOneField,
    Q,
    TextField,
)
from django.utils.safestring import mark_safe
from markdown import markdown

from .terms import FALL, SPRING, SUMMER, USE_BANNER

logger = getLogger(__name__)
SIS_PREFIX = "BAN" if USE_BANNER else "SRS"


class Profile(Model):
    user = OneToOneField(User, on_delete=CASCADE)
    penn_id = CharField(max_length=10, unique=True)
    canvas_id = CharField(max_length=10, unique=True, null=True)


class Activity(Model):
    name = CharField(max_length=40)
    abbr = CharField(max_length=3, unique=True, primary_key=True)

    class Meta:
        ordering = ["abbr"]
        verbose_name_plural = "Activites"

    def __str__(self):
        return self.abbr


class School(Model):
    name = CharField(max_length=50, unique=True)
    abbreviation = CharField(max_length=10, unique=True, primary_key=True)
    visible = BooleanField(default=True)
    open_data_abbreviation = CharField(max_length=2)
    canvas_subaccount = IntegerField(null=True)
    form_additional_enrollments = BooleanField(
        default=True, verbose_name="Additional Enrollments Form Field"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

    def get_subjects(self):
        return Subject.objects.filter(schools=self)

    def save(self, *args, **kwargs):
        for subject in self.get_subjects():
            subject.visible = self.visible
            subject.save()

        super().save(*args, **kwargs)


class Subject(Model):
    name = CharField(max_length=50)
    abbreviation = CharField(max_length=10, unique=True, primary_key=True)
    visible = BooleanField(default=True)
    schools = ForeignKey(
        School, related_name="subjects", on_delete=CASCADE, blank=True, null=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"


class CanvasSite(Model):
    canvas_id = CharField(max_length=10, blank=False, default=None, primary_key=True)
    request_instance = ForeignKey(
        "Request", on_delete=SET_NULL, null=True, default=None, blank=True
    )
    owners = ManyToManyField(User, related_name="canvas_sites", blank=True)
    added_permissions = ManyToManyField(
        User, related_name="added_permissions", blank=True, default=None
    )
    name = CharField(max_length=50, blank=False, default=None)
    sis_course_id = CharField(max_length=50, blank=True, default=None, null=True)
    workflow_state = CharField(max_length=15, blank=False, default=None)

    class Meta:
        ordering = ["canvas_id"]

    def __str__(self):
        return self.name

    def get_owners(self):
        return "\n".join([owner.username for owner in self.owners.all()])

    def get_added_permissions(self):
        return "\n".join([owner.username for owner in self.added_permissions.all()])


class Course(Model):
    OLD_SPRING = "A"
    OLD_SUMMER = "B"
    OLD_FALL = "C"
    TERM_CHOICES = (
        (SPRING, "Spring"),
        (SUMMER, "Summer"),
        (FALL, "Fall"),
        (OLD_SPRING, "Old Spring"),
        (OLD_SUMMER, "Old Summer"),
        (OLD_FALL, "Old Fall"),
    )
    course_activity = ForeignKey(Activity, related_name="courses", on_delete=CASCADE)
    course_code = CharField(
        max_length=150, unique=True, primary_key=True, editable=False
    )
    course_name = CharField(max_length=250)
    course_number = CharField(max_length=4, blank=False)
    course_primary_subject = ForeignKey(Subject, on_delete=CASCADE)
    course_schools = ForeignKey(School, related_name="courses", on_delete=CASCADE)
    course_section = CharField(max_length=4, blank=False)
    course_subject = ForeignKey(Subject, on_delete=CASCADE, related_name="courses")
    course_term = CharField(max_length=2, choices=TERM_CHOICES)
    created = DateTimeField(auto_now_add=True)
    crosslisted = ManyToManyField("self", blank=True, symmetrical=True, default=None)
    crosslisted_request = ForeignKey(
        "course.Request",
        on_delete=SET_NULL,
        related_name="tied_course",
        default=None,
        blank=True,
        null=True,
    )
    instructors = ManyToManyField(User, related_name="courses", blank=True)
    multisection_request = ForeignKey(
        "course.Request",
        on_delete=SET_NULL,
        related_name="additional_sections",
        default=None,
        blank=True,
        null=True,
    )
    owner = ForeignKey("auth.User", related_name="created", on_delete=CASCADE)
    primary_crosslist = CharField(max_length=20, default="", blank=True)
    requested = BooleanField(default=False)
    requested_override = BooleanField(default=False)
    sections = ManyToManyField("self", blank=True, symmetrical=True, default=None)
    updated = DateTimeField(auto_now=True)
    year = CharField(max_length=4, blank=False)
    objects = Manager()

    class Meta:
        ordering = ["-year", "course_code"]

    def __str__(self):
        return "_".join(
            [
                self.course_subject.abbreviation,
                self.course_number,
                self.course_section,
                f"{self.year}{self.course_term}",
            ]
        )

    def get_requested(self):
        if self.requested_override:
            return True
        else:
            try:
                request = Request.objects.get(course_requested=self.course_code)
            except Exception:
                request = False
            return bool(
                request or self.multisection_request or self.crosslisted_request
            )

    def set_requested(self, requested):
        self.requested = requested
        self.save()

    def get_crosslisted(self):
        cross_courses = Course.objects.filter(
            Q(course_primary_subject=self.course_primary_subject)
            & Q(course_number=self.course_number)
            & Q(course_section=self.course_section)
            & Q(course_term=self.course_term)
            & Q(year=self.year)
        )
        for course in cross_courses:
            self.crosslisted.add(course)
            self.save()

    def update_crosslists(self):
        cross_courses = Course.objects.filter(
            Q(course_primary_subject=self.course_primary_subject)
            & Q(course_number=self.course_number)
            & Q(course_section=self.course_section)
            & Q(course_term=self.course_term)
            & Q(year=self.year)
        )
        for course in cross_courses:
            course.requested_override = self.requested_override
        try:
            request = Request.objects.get(course_requested=self.course_code)
        except Exception:
            request = None
        if request:
            for course in cross_courses:
                course.crosslisted_request = request

    def save(self, *args, **kwargs):
        self.course_code = (
            f"{self.course_subject.abbreviation}"
            f"{self.course_number}"
            f"{self.course_section}"
            f"{self.year}"
            f"{self.course_term}"
        )
        if self._state.adding is True:
            super().save(*args, **kwargs)
        else:
            self.sections.set(self.find_sections())
            self.requested = self.get_requested()
            self.update_crosslists()
            super().save(*args, **kwargs)

    def get_request(self):
        try:
            return Request.objects.get(course_requested=self.course_code)
        except Exception as error:
            if self.multisection_request:
                request = self.multisection_request
            elif self.crosslisted_request:
                request = self.crosslisted_request
            else:
                request = None

            if not request and self.requested:
                logger.warning(f"Request NOT FOUND for {self.course_code} ({error}).")
            return request

    def get_subjects(self):
        return self.course_subject.abbreviation

    def get_schools(self):
        return self.course_schools

    def get_instructors(self):
        return (
            "STAFF"
            if not self.instructors.all().exists()
            else ", ".join(
                [instructor.username for instructor in self.instructors.all()]
            )
        )

    def get_year_and_term(self):
        return f"{self.year}{self.course_term}"

    def find_sections(self):
        courses = list(
            Course.objects.filter(
                Q(course_subject=self.course_subject)
                & Q(course_number=self.course_number)
                & Q(course_term=self.course_term)
                & Q(year=self.year)
            ).exclude(course_code=self.course_code)
        )
        for course in courses:
            section = int(course.course_section)
            if section >= 300 and section < 400:
                courses.remove(course)
        return courses

    def sis_format(self):
        return (
            f"{self.course_subject.abbreviation}-"
            f"{self.course_number}-"
            f"{self.course_section}"
            f" {self.year}{self.course_term}"
        )

    def sis_format_primary(self, sis_id=True):
        primary_crosslist = self.primary_crosslist
        year_and_term = self.get_year_and_term()

        if primary_crosslist:
            if year_and_term in primary_crosslist and len(primary_crosslist) > 9:
                primary_crosslist = primary_crosslist.replace(year_and_term, "")

            subject = "".join(
                character for character in primary_crosslist if str.isalpha(character)
            )
            number_section = "".join(
                character
                for character in primary_crosslist
                if not str.isalpha(character)
            )
            number = number_section[:3]
            section = number_section[3:]

            if sis_id:
                return f"{subject}-{number}-{section} {year_and_term}"
            else:
                return f"{subject} {number}-{section} {year_and_term}"
        else:
            return self.sis_format()


class Notice(Model):
    creation_date = DateTimeField(auto_now_add=True)
    notice_heading = CharField(max_length=100)
    notice_text = TextField(max_length=1000)
    owner = ForeignKey("auth.User", related_name="notices", on_delete=CASCADE)
    updated_date = DateTimeField(auto_now=True)

    class Meta:
        get_latest_by = "updated_date"

    def __str__(self):
        return self.notice_heading

    def get_html(self):
        return mark_safe(
            clean(markdown(self.notice_text), markdown_tags, markdown_attrs)
        )


class Request(Model):
    REQUEST_PROCESS_CHOICES = (
        ("COMPLETED", "Completed"),
        ("IN_PROCESS", "In Process"),
        ("CANCELED", "Canceled"),
        ("APPROVED", "Approved"),
        ("SUBMITTED", "Submitted"),
        ("LOCKED", "Locked"),
    )
    course_requested = OneToOneField(Course, on_delete=CASCADE, primary_key=True)
    copy_from_course = CharField(max_length=100, null=True, default=None, blank=True)
    title_override = CharField(max_length=100, null=True, default=None, blank=True)
    lps_online = BooleanField(default=False, verbose_name="LPS Online")
    exclude_announcements = BooleanField(default=False)
    additional_instructions = TextField(blank=True, default=None, null=True)
    admin_additional_instructions = TextField(blank=True, default=None, null=True)
    reserves = BooleanField(default=False)
    process_notes = TextField(blank=True, default="")
    canvas_instance = ForeignKey(
        CanvasSite,
        related_name="canvas",
        on_delete=CASCADE,
        null=True,
        blank=True,
    )
    status = CharField(
        max_length=20, choices=REQUEST_PROCESS_CHOICES, default="SUBMITTED"
    )
    created = DateTimeField(auto_now_add=True)
    updated = DateTimeField(auto_now=True)
    owner = ForeignKey("auth.User", related_name="requests", on_delete=CASCADE)
    masquerade = CharField(max_length=20, null=True)

    class Meta:
        ordering = ["-status", "-created"]

    def save(self, *args, **kwargs):
        super(Request, self).save(*args, **kwargs)

    def delete(self):
        course = Course.objects.get(course_code=self.course_requested.course_code)
        multi_section_courses = Course.objects.filter(
            multisection_request=course.course_code
        )
        crosslisted_courses = Course.objects.filter(
            crosslisted_request=course.course_code
        )

        if crosslisted_courses:
            for crosslisted_course in crosslisted_courses:
                crosslisted_course.crosslisted_request = None
                crosslisted_course.requested = False
                crosslisted_course.save()

        if multi_section_courses:
            for multi_section_course in multi_section_courses:
                multi_section_course.multisection_request = None
                multi_section_course.requested = False
                multi_section_course.save()

        super(Request, self).delete()
        course.requested = False
        course.save()

        if crosslisted_courses:
            for crosslisted_course in crosslisted_courses:
                if course != crosslisted_course:
                    crosslisted_course.requested = False
                    crosslisted_course.save()

        if multi_section_courses:
            for multi_section_course in multi_section_courses:
                multi_section_course.requested = False
                multi_section_course.save()


class AdditionalEnrollment(Model):
    ENROLLMENT_TYPE = (
        ("TA", "TA"),
        ("INST", "Instructor"),
        ("DES", "Designer"),
        ("LIB", "Librarian"),
        ("OBS", "Observer"),
    )
    user = ForeignKey(User, on_delete=CASCADE)
    role = CharField(max_length=4, choices=ENROLLMENT_TYPE, default="TA")
    course_request = ForeignKey(
        Request,
        related_name="additional_enrollments",
        on_delete=CASCADE,
        default=None,
    )


class AutoAdd(Model):
    ROLE_CHOICES = (
        ("TA", "TA"),
        ("INST", "Instructor"),
        ("DES", "Designer"),
        ("LIB", "Librarian"),
        ("OBS", "Observer"),
    )
    user = ForeignKey(User, on_delete=CASCADE, blank=False)
    school = ForeignKey(School, on_delete=CASCADE, blank=False)
    subject = ForeignKey(Subject, on_delete=CASCADE, blank=False)
    role = CharField(
        max_length=10,
        choices=ROLE_CHOICES,
    )
    created = DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        ordering = ("user__username",)


class UpdateLog(Model):
    MANAGER_CHOICES = (
        ("a", "A"),
        ("b", "B"),
        ("c", "C"),
    )
    created = DateTimeField(auto_now_add=True, null=True, blank=True)
    finished = DateTimeField(null=True, blank=True)
    process = CharField(max_length=10, choices=MANAGER_CHOICES)


class PageContent(Model):
    location = CharField(max_length=100)
    markdown_text = TextField(max_length=4000)
    updated_date = DateTimeField(auto_now=True)

    def __str__(self):
        return self.location

    def get_html(self):
        return mark_safe(
            clean(markdown(self.markdown_text), markdown_tags, markdown_attrs)
        )


class RequestSummary(Request):
    class Meta:
        proxy = True
        verbose_name_plural = "Requests summaries"
