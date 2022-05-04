from logging import getLogger

from bleach import clean
from bleach_allowlist import markdown_attrs, markdown_tags
from django.contrib.auth.models import AbstractUser
from django.db.models import (CASCADE, SET_NULL, BooleanField, CharField,
                              DateTimeField, EmailField, ForeignKey,
                              IntegerField, Manager, ManyToManyField, Model,
                              OneToOneField, Q, TextField)
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from markdown import markdown

from canvas.api import get_all_canvas_accounts, get_canvas_user_id_by_pennkey
from data_warehouse.helpers import get_cursor

from .terms import FALL, SPRING, SUMMER

logger = getLogger(__name__)


class User(AbstractUser):
    penn_id = IntegerField(unique=True, null=True)
    email_address = EmailField(unique=True, null=True)
    canvas_id = IntegerField(unique=True, null=True)

    @staticmethod
    def log_field(username: str, field: str, value):
        if value:
            logger.info(f"FOUND {field} '{value}' for {username}")
        else:
            logger.warning(f"{field} NOT FOUND for {username}")

    def get_dw_info(self):
        logger.info(f"Getting {self.username}'s info from Data Warehouse...")
        cursor = get_cursor()
        if not cursor:
            return
        query = """
                SELECT
                    first_name, last_name, penn_id, email_address
                FROM employee_general
                WHERE pennkey = :username
                """
        cursor.execute(query, username=self.username)
        for first_name, last_name, penn_id, email_address in cursor:
            self.log_field(self.username, "first name", first_name)
            self.first_name = first_name
            self.log_field(self.username, "last name", last_name)
            self.last_name = last_name
            self.log_field(self.username, "Penn id", penn_id)
            self.penn_id = penn_id
            self.log_field(self.username, "email address", email_address)
            self.email_address = email_address
        self.save()

    def get_canvas_id(self):
        logger.info(f"Getting {self.username}'s Canvas user id...")
        canvas_user_id = get_canvas_user_id_by_pennkey(self.username)
        self.log_field(self.username, "Canvas user id", canvas_user_id)
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
        cursor = get_cursor()
        if not cursor:
            return
        query = "SELECT sched_type_code, sched_type_desc FROM dwngss.v_sched_type"
        cursor.execute(query)
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
        cursor = get_cursor()
        if not cursor:
            return
        query = "SELECT school_code, school_desc_long FROM dwngss.v_school"
        cursor.execute(query)
        if not cursor:
            return
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
        cursor = get_cursor()
        if not cursor:
            return
        cursor.execute(query)
        for subject_code, subject_desc_long, school_code in cursor:
            try:
                school = School.objects.get(school_code=school_code)
            except Exception:
                school = None
                query = (
                    "SELECT school_code, school_desc_long FROM dwngss.v_school WHERE"
                    " school_code = :school_code"
                )
                cursor.execute(query, {"school_code": school_code})
                if not cursor:
                    return
                for school_code, school_desc_long in cursor:
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


class Course(Model):
    TERM_CHOICES = ((SPRING, "Spring"), (SUMMER, "Summer"), (FALL, "Fall"))
    course_code = CharField(
        max_length=150, unique=True, primary_key=True, editable=False
    )
    school = ForeignKey(School, related_name="courses", on_delete=CASCADE)
    subject = ForeignKey(Subject, on_delete=CASCADE, related_name="courses")
    primary_subject = ForeignKey(Subject, on_delete=CASCADE)
    course_num = CharField(max_length=4, blank=False)
    section_num = CharField(max_length=4, blank=False)
    schedule_type = ForeignKey(ScheduleType, related_name="courses", on_delete=CASCADE)
    year = CharField(max_length=4, blank=False)
    term = CharField(max_length=2, choices=TERM_CHOICES)
    title = CharField(max_length=250)
    instructors = ManyToManyField(User, related_name="courses", blank=True)
    owner = ForeignKey(User, related_name="owner", on_delete=CASCADE)
    sections = ManyToManyField("self", blank=True, symmetrical=True, default=None)
    primary_crosslist = CharField(max_length=20, default="", blank=True)
    crosslisted = ManyToManyField("self", blank=True, symmetrical=True, default=None)
    crosslisted_request = ForeignKey(
        "course.Request",
        on_delete=SET_NULL,
        related_name="tied_course",
        default=None,
        blank=True,
        null=True,
    )
    multisection_request = ForeignKey(
        "course.Request",
        on_delete=SET_NULL,
        related_name="additional_sections",
        default=None,
        blank=True,
        null=True,
    )
    requested = BooleanField(default=False)
    requested_override = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    objects = Manager()

    class Meta:
        ordering = ("-year", "course_code")

    def __str__(self):
        return (
            f"{self.subject.subject_code}_{self.course_num}"
            f"_{self.section_num}_{self.year_and_term}"
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

    def set_requested(self, requested: bool):
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
            f"{self.subject.subject_code}"
            f"{self.course_num}"
            f"{self.section_num}"
            f"{self.year}"
            f"{self.term}"
        )
        if not self._state.adding:
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

    @cached_property
    def school_code(self):
        return self.school.school_code

    @cached_property
    def subject_code(self):
        return self.subject.subject_code

    @cached_property
    def year_and_term(self):
        return f"{self.year}{self.term}"

    @cached_property
    def instructor_list(self):
        instructors = self.instructors.all().exists()
        if not instructors:
            return "STAFF"
        return ", ".join(instructor.username for instructor in self.instructors.all())

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

    @cached_property
    def sis_course_code(self):
        return (
            f"{self.subject.subject_code}-"
            f"{self.course_num}-"
            f"{self.section_num}"
            f" {self.year_and_term}"
        )

    def sis_format_primary(self, sis_id=True):
        primary_crosslist = self.primary_crosslist
        year_and_term = self.year_and_term
        if not primary_crosslist:
            return self.sis_course_code()
        if year_and_term in primary_crosslist and len(primary_crosslist) > 9:
            primary_crosslist = primary_crosslist.replace(year_and_term, "")
        subject = "".join(
            character for character in primary_crosslist if str.isalpha(character)
        )
        number_section = "".join(
            character for character in primary_crosslist if not str.isalpha(character)
        )
        number = number_section[:4] if self.term.isnumeric() else number_section[:3]
        section = number_section[3:]
        if sis_id:
            return f"{subject}-{number}-{section} {year_and_term}"
        else:
            return f"{subject} {number}-{section} {year_and_term}"


class Request(Model):
    STATUSES = (
        ("COMPLETED", "Completed"),
        ("IN_PROCESS", "In Process"),
        ("CANCELED", "Canceled"),
        ("APPROVED", "Approved"),
        ("SUBMITTED", "Submitted"),
        ("LOCKED", "Locked"),
    )
    course_requested = OneToOneField(Course, on_delete=CASCADE, primary_key=True)
    requester = ForeignKey(User, related_name="requests", on_delete=CASCADE)
    masquerade = CharField(max_length=20, null=True)
    title_override = CharField(max_length=255, null=True, default=None, blank=True)
    copy_from_course = IntegerField(null=True, default=None, blank=True)
    reserves = BooleanField(default=False)
    lps_online = BooleanField(default=False, verbose_name="LPS Online")
    exclude_announcements = BooleanField(default=False)
    additional_instructions = TextField(blank=True, default=None, null=True)
    admin_additional_instructions = TextField(blank=True, default=None, null=True)
    process_notes = TextField(blank=True, default="")
    status = CharField(max_length=20, choices=STATUSES, default="SUBMITTED")
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-status", "-created_at")

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


CANVAS_ROLES = (
    ("TA", "TA"),
    ("INST", "Instructor"),
    ("DES", "Designer"),
    ("LIB", "Librarian"),
    ("OBS", "Observer"),
)


class AdditionalEnrollment(Model):
    user = ForeignKey(User, on_delete=CASCADE)
    role = CharField(max_length=4, choices=CANVAS_ROLES, default="TA")
    request = ForeignKey(
        Request, related_name="additional_enrollments", on_delete=CASCADE, default=None
    )


class AutoAdd(Model):
    user = ForeignKey(User, on_delete=CASCADE, blank=False)
    school = ForeignKey(School, on_delete=CASCADE, blank=False)
    subject = ForeignKey(Subject, on_delete=CASCADE, blank=False)
    role = CharField(max_length=4, choices=CANVAS_ROLES)
    created_at = DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        ordering = ("user__username",)


class Message(Model):
    content = TextField(max_length=4000)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    def get_html(self):
        return mark_safe(clean(markdown(self.content), markdown_tags, markdown_attrs))


class Notice(Message):
    header = CharField(max_length=100)
    author = ForeignKey(User, related_name="notices", on_delete=CASCADE)

    class Meta:
        get_latest_by = "updated_at"

    def __str__(self):
        return self.header


class PageContent(Message):
    page = CharField(max_length=100)

    def __str__(self):
        return self.page
