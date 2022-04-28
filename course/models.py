from logging import getLogger

from bleach import clean
from bleach_allowlist import markdown_attrs, markdown_tags
from django.contrib.auth.models import AbstractUser
from django.db.models import (
    CASCADE,
    SET_NULL,
    BooleanField,
    CharField,
    DateTimeField,
    EmailField,
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

from canvas.api import get_canvas_main_account, get_canvas_user_id_by_pennkey
from data_warehouse.helpers import get_cursor, log_field

from .terms import FALL, SPRING, SUMMER, USE_BANNER

logger = getLogger(__name__)
SIS_PREFIX = "BAN" if USE_BANNER else "SRS"


class User(AbstractUser):
    penn_id = IntegerField(unique=True, null=True)
    email_address = EmailField(unique=True, null=True)
    canvas_id = IntegerField(unique=True, null=True)

    def get_dw_info(self):
        logger.info(f"Getting {self.username}'s info from Data Warehouse...")
        cursor = get_cursor()
        query = """
                SELECT
                    first_name, last_name, penn_id, email_address
                FROM employee_general
                WHERE pennkey = :username
                """
        cursor.execute(query, username=self.username)
        for first_name, last_name, penn_id, email_address in cursor:
            log_field(logger, "first name", first_name, self.username)
            self.first_name = first_name
            log_field(logger, "last name", last_name, self.username)
            self.last_name = last_name
            log_field(logger, "Penn id", penn_id, self.username)
            self.penn_id = penn_id
            log_field(logger, "email address", email_address, self.username)
            self.email_address = email_address
        self.save()

    def get_canvas_id(self):
        logger.info(f"Getting {self.username}'s Canvas user id...")
        canvas_user_id = get_canvas_user_id_by_pennkey(self.username)
        log_field(logger, "Canvas user id", canvas_user_id, self.username)
        if canvas_user_id:
            self.canvas_id = canvas_user_id
            self.save()

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.get_dw_info()
            self.get_canvas_id()
        super().save(*args, **kwargs)


class ScheduleType(Model):
    sched_type_code = CharField(max_length=255, unique=True, primary_key=True)
    sched_type_desc = CharField(max_length=255)

    @classmethod
    def sync(cls):
        query = "SELECT sched_type_code, sched_type_desc FROM dwngss.v_sched_type"
        cursor = get_query_cursor(query)
        for sched_type_code, sched_type_desc in cursor:
            schedule_type, created = cls.objects.update_or_create(
                sched_type_code=sched_type_code,
                defaults={"sched_type_desc": sched_type_desc},
            )
            action = "ADDED" if created else "UPDATED"
            logger.info(f"{action} {schedule_type}")

    def __str__(self):
        return f"{self.sched_type_desc} ({self.sched_type_code})"


class School(Model):
    school_code = CharField(max_length=10, unique=True, primary_key=True)
    school_desc_long = CharField(max_length=50, unique=True)
    visible = BooleanField(default=True)
    canvas_sub_account_id = IntegerField(null=True)
    form_additional_enrollments = BooleanField(
        default=True, verbose_name="Additional Enrollments Form Field"
    )

    @classmethod
    def sync(cls):
        query = "SELECT school_code, school_desc_long FROM dwngss.v_school"
        cursor = get_query_cursor(query)
        for school_code, school_desc_long in cursor:
            school, created = cls.objects.update_or_create(
                school_code=school_code,
                defaults={"school_desc_long": school_desc_long},
            )
            school.get_canvas_sub_account()
            action = "ADDED" if created else "UPDATED"
            logger.info(f"{action} {school}")

    class Meta:
        ordering = ["school_desc_long"]

    def __str__(self):
        return f"{self.school_desc_long} ({self.school_code})"

    def get_subjects(self):
        return Subject.objects.filter(schools=self)

    def save(self, *args, **kwargs):
        for subject in self.get_subjects():
            subject.visible = self.visible
            subject.save()
        super().save(*args, **kwargs)

    def get_canvas_sub_account(self):
        accounts = get_all_canvas_accounts()
        account_ids = (
            account.id for account in accounts if self.school_desc_long == account.name
        )
        account_id = next(account_ids, None)
        if account_id:
            self.canvas_sub_account_id = account_id
            self.save()


class Subject(Model):
    subject_desc_long = CharField(max_length=255)
    subject_code = CharField(max_length=10, unique=True, primary_key=True)
    visible = BooleanField(default=True)
    school = ForeignKey(
        School, related_name="subjects", on_delete=CASCADE, blank=True, null=True
    )

    @classmethod
    def sync(cls):
        query = (
            "SELECT subject_code, subject_desc_long, school_code FROM dwngss.v_subject"
        )
        cursor = get_query_cursor(query)
        for subject_code, subject_desc_long, school_code in cursor:
            try:
                school = School.objects.get(school_code=school_code)
            except Exception:
                query = "SELECT school_code, school_desc_long FROM dwngss.v_school WHERE school_code = :school_code"
                cursor = get_query_cursor(query, {"school_code": school_code})
                school, created = School.objects.update_or_create(
                    school_code=school_code,
                    defaults={"school_desc_long": school_desc_long},
                )
                school.get_canvas_sub_account()
                action = "ADDED" if created else "UPDATED"
                logger.info(f"{action} {school}")
            subject, created = cls.objects.update_or_create(
                subject_code=subject_code,
                defaults={"subject_desc_long": subject_desc_long, "school": school},
            )
            action = "ADDED" if created else "UPDATED"
            logger.info(f"{action} {subject}")

    class Meta:
        ordering = ["subject_desc_long"]

    def __str__(self):
        return f"{self.subject_desc_long} ({self.subject_code})"


class CanvasCourse(Model):
    canvas_id = IntegerField(blank=False, default=None, primary_key=True)
    name = CharField(max_length=255, blank=False, default=None)
    sis_course_id = CharField(max_length=50, blank=True, default=None, null=True)
    workflow_state = CharField(max_length=15, blank=False, default=None)
    request = ForeignKey(
        "Request", on_delete=SET_NULL, null=True, default=None, blank=True
    )
    owners = ManyToManyField(User, related_name="canvas_sites", blank=True)
    added_permissions = ManyToManyField(
        User, related_name="added_permissions", blank=True, default=None
    )

    class Meta:
        ordering = ["canvas_id"]

    def __str__(self):
        return self.name

    def get_owners(self):
        return "\n".join(owner.username for owner in self.owners.all())

    def get_added_permissions(self):
        return "\n".join(owner.username for owner in self.added_permissions.all())


class Course(Model):
    TERM_CHOICES = (
        (SPRING, "Spring"),
        (SUMMER, "Summer"),
        (FALL, "Fall"),
    )
    course_code = CharField(
        max_length=150, unique=True, primary_key=True, editable=False
    )
    schedule_type = ForeignKey(ScheduleType, related_name="courses", on_delete=CASCADE)
    title = CharField(max_length=250)
    course_num = CharField(max_length=4, blank=False)
    primary_subject = ForeignKey(Subject, on_delete=CASCADE)
    school = ForeignKey(School, related_name="courses", on_delete=CASCADE)
    section_num = CharField(max_length=4, blank=False)
    subject = ForeignKey(Subject, on_delete=CASCADE, related_name="courses")
    term = CharField(max_length=2, choices=TERM_CHOICES)
    created_at = DateTimeField(auto_now_add=True)
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
    owner = ForeignKey(User, related_name="created_at", on_delete=CASCADE)
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
        return (
            f"{self.subject.subject_code}_{self.course_num}"
            f"_{self.section_num}_{self.year}{self.term}"
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
            Q(course_primary_subject=self.primary_subject)
            & Q(course_number=self.course_num)
            & Q(course_section=self.section_num)
            & Q(course_term=self.term)
            & Q(year=self.year)
        )
        for course in cross_courses:
            self.crosslisted.add(course)
            self.save()

    def update_crosslists(self):
        cross_courses = Course.objects.filter(
            Q(course_primary_subject=self.primary_subject)
            & Q(course_number=self.course_num)
            & Q(course_section=self.section_num)
            & Q(course_term=self.term)
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
            f"{self.subject.abbreviation}"
            f"{self.course_num}"
            f"{self.section_num}"
            f"{self.year}"
            f"{self.term}"
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
        return self.subject.abbreviation

    def get_schools(self):
        return self.school

    def get_instructors(self):
        return (
            "STAFF"
            if not self.instructors.all().exists()
            else ", ".join(
                [instructor.username for instructor in self.instructors.all()]
            )
        )

    def get_year_and_term(self):
        return f"{self.year}{self.term}"

    def find_sections(self):
        courses = list(
            Course.objects.filter(
                Q(course_subject=self.subject)
                & Q(course_number=self.course_num)
                & Q(course_term=self.term)
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
            f"{self.subject.abbreviation}-"
            f"{self.course_num}-"
            f"{self.section_num}"
            f" {self.year}{self.term}"
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
            number = number_section[:4] if self.term.isnumeric() else number_section[:3]
            section = number_section[3:]

            if sis_id:
                return f"{subject}-{number}-{section} {year_and_term}"
            else:
                return f"{subject} {number}-{section} {year_and_term}"
        else:
            return self.sis_format()


class Notice(Model):
    header = CharField(max_length=100)
    content = TextField(max_length=1000)
    author = ForeignKey(User, related_name="notices", on_delete=CASCADE)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        get_latest_by = "updated_at"

    def __str__(self):
        return self.header

    def get_html(self):
        return mark_safe(clean(markdown(self.content), markdown_tags, markdown_attrs))


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
    copy_from_course = IntegerField(null=True, default=None, blank=True)
    title_override = CharField(max_length=255, null=True, default=None, blank=True)
    lps_online = BooleanField(default=False, verbose_name="LPS Online")
    exclude_announcements = BooleanField(default=False)
    additional_instructions = TextField(blank=True, default=None, null=True)
    admin_additional_instructions = TextField(blank=True, default=None, null=True)
    reserves = BooleanField(default=False)
    process_notes = TextField(blank=True, default="")
    canvas_instance = ForeignKey(
        CanvasCourse,
        related_name="canvas",
        on_delete=CASCADE,
        null=True,
        blank=True,
    )
    status = CharField(
        max_length=20, choices=REQUEST_PROCESS_CHOICES, default="SUBMITTED"
    )
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    requester = ForeignKey(User, related_name="requests", on_delete=CASCADE)
    masquerade = CharField(max_length=20, null=True)

    class Meta:
        ordering = ("-status", "-created_at")

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


ROLES = (
    ("TA", "TA"),
    ("INST", "Instructor"),
    ("DES", "Designer"),
    ("LIB", "Librarian"),
    ("OBS", "Observer"),
)


class AdditionalEnrollment(Model):
    user = ForeignKey(User, on_delete=CASCADE)
    role = CharField(max_length=4, choices=ROLES, default="TA")
    course_request = ForeignKey(
        Request, related_name="additional_enrollments", on_delete=CASCADE, default=None
    )


class AutoAdd(Model):
    user = ForeignKey(User, on_delete=CASCADE, blank=False)
    school = ForeignKey(School, on_delete=CASCADE, blank=False)
    subject = ForeignKey(Subject, on_delete=CASCADE, blank=False)
    role = CharField(max_length=4, choices=ROLES)
    created_at = DateTimeField(auto_now_add=True, null=True, blank=True)

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
    page = CharField(max_length=100)
    content = TextField(max_length=4000)
    updated_at = DateTimeField(auto_now=True)

    def __str__(self):
        return self.page

    def get_html(self):
        return mark_safe(clean(markdown(self.content), markdown_tags, markdown_attrs))


class RequestSummary(Request):
    class Meta:
        proxy = True
        verbose_name_plural = "Requests summaries"
