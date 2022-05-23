from enum import Enum
from logging import getLogger
from time import sleep
from typing import Optional, Union

from canvasapi.course import Course
from canvasapi.tab import Tab
from django.contrib.auth.models import AbstractUser
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    IntegerField,
    ManyToManyField,
    Model,
    OneToOneField,
    TextChoices,
    TextField,
    UniqueConstraint,
)

from .canvas import (
    create_course_section,
    delete_announcements,
    delete_zoom_events,
    get_all_canvas_accounts,
    get_canvas_enrollment_term_id,
    get_canvas_main_account,
    get_canvas_user_id_by_pennkey,
    update_or_create_canvas_course,
)
from .data_warehouse import execute_query
from .terms import CURRENT_TERM, NEXT_TERM

logger = getLogger(__name__)


class User(AbstractUser):
    penn_id = IntegerField(unique=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.penn_id:
            self.sync_dw_info()
        super().save(*args, **kwargs)

    @staticmethod
    def log_field(username: str, field: str, value):
        if value:
            logger.info(f"FOUND {field} '{value}' for '{username}'")
        else:
            logger.warning(f"{field} NOT FOUND for '{username}'")

    @classmethod
    def sync_user(cls, pennkey: str):
        logger.info(f"Getting {pennkey}'s info from Data Warehouse...")
        query = """
                SELECT first_name, last_name, penn_id, email_address
                FROM employee_general
                WHERE pennkey = :username
                """
        cursor = execute_query(query, {"username": pennkey})
        for first_name, last_name, penn_id, email in cursor:
            first_name = first_name.title() if first_name else ""
            cls.log_field(pennkey, "first name", first_name)
            last_name = last_name.title() if last_name else ""
            cls.log_field(pennkey, "last name", last_name)
            cls.log_field(pennkey, "Penn id", penn_id)
            email = email.strip().lower() if email else ""
            cls.log_field(pennkey, "email", email)
            User.objects.update_or_create(
                username=pennkey,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "penn_id": penn_id,
                    "email": email,
                },
            )

    def sync_dw_info(self):
        self.sync_user(self.username)

    def get_canvas_id(self) -> int:
        logger.info(f"Getting Canvas user id for '{self.username}'...")
        canvas_id = get_canvas_user_id_by_pennkey(self.username)
        self.log_field(self.username, "Canvas user id", canvas_id)
        if canvas_id:
            return canvas_id
        account = get_canvas_main_account()
        pseudonym = {"unique_id": self.username, "sis_user_id": self.penn_id}
        full_name = f"{self.first_name} {self.last_name}"
        user = {"name": full_name}
        communication_channel = {"type": "email", "address": self.email}
        canvas_user = account.create_user(
            pseudonym, user=user, communication_channel=communication_channel
        )
        return canvas_user.id


class ScheduleType(Model):
    QUERY = """
            SELECT sched_type_code, sched_type_desc
            FROM dwngss.v_sched_type
            """
    sched_type_code = CharField(max_length=255, primary_key=True)
    sched_type_desc = CharField(max_length=255)

    def __str__(self):
        return f"{self.sched_type_desc} ({self.sched_type_code})"

    @classmethod
    def update_or_create(cls, query: str, kwargs: Optional[dict] = None):
        cursor = execute_query(query, kwargs)
        schedule_type = None
        for sched_type_code, sched_type_desc in cursor:
            try:
                schedule_type, created = cls.objects.update_or_create(
                    sched_type_code=sched_type_code,
                    defaults={"sched_type_desc": sched_type_desc},
                )
                action = "ADDED" if created else "UPDATED"
                logger.info(f"{action} {schedule_type}")
            except Exception as error:
                logger.error(
                    f"FAILED to update or create schedule type '{sched_type_code}':"
                    f" {error}"
                )
        return schedule_type

    @classmethod
    def sync_all(cls):
        logger.info("Syncing Schedule Types...")
        cls.update_or_create(cls.QUERY)

    @classmethod
    def sync_schedule_type(cls, sched_type_code: str):
        query = f"{cls.QUERY} WHERE sched_type_code = :sched_type_code"
        kwargs = {"sched_type_code": sched_type_code}
        return cls.update_or_create(query, kwargs)

    @classmethod
    def get_schedule_type(cls, sched_type_code: str):
        try:
            return cls.objects.get(sched_type_code=sched_type_code)
        except Exception:
            return cls.sync_schedule_type(sched_type_code)


class School(Model):
    QUERY = """
            SELECT school_code, school_desc_long
            FROM dwngss.v_school
            """
    DENTAL_MEDICINE_CODE = "D"
    DENTAL_MEDICINE_NAME = "Penn Dental Medicine"
    LAW_SCHOOL_CODE = "L"
    PROVOST_CENTER_CODE = "P"
    SAS_SCHOOL_CODE = "A"
    VETERINARY_MEDICINE_CODE = "V"
    VETERINARY_MEDICINE_NAME = "Penn Vet"
    LPS_ONLINE_ACCOUNT_ID = 132413
    school_code = CharField(max_length=10, primary_key=True)
    school_desc_long = CharField(max_length=50, unique=True)
    visible = BooleanField(default=True)
    canvas_sub_account_id = IntegerField(null=True)

    def __str__(self):
        return f"{self.school_desc_long} ({self.school_code})"

    def save(self, *args, **kwargs):
        for subject in self.get_subjects():
            subject.visible = self.visible
            subject.save()
        super().save(*args, **kwargs)

    def get_subjects(self):
        return Subject.objects.filter(school=self)

    def get_canvas_school_name(self) -> str:
        if self.school_code == self.VETERINARY_MEDICINE_CODE:
            return self.VETERINARY_MEDICINE_NAME
        elif self.school_code == self.DENTAL_MEDICINE_CODE:
            return self.DENTAL_MEDICINE_NAME
        else:
            return self.school_desc_long.replace("&", "and")

    def get_canvas_sub_account(self):
        accounts = get_all_canvas_accounts()
        school_name = self.get_canvas_school_name()
        account_ids = (
            account.id for account in accounts if account.name in school_name
        )
        account_id = next(account_ids, None)
        if account_id:
            self.canvas_sub_account_id = account_id
            self.save()

    @classmethod
    def is_canvas_school(cls, school_code: str) -> bool:
        return not (
            school_code == cls.LAW_SCHOOL_CODE or school_code == cls.PROVOST_CENTER_CODE
        )

    @classmethod
    def update_or_create(cls, query: str, kwargs: Optional[dict] = None):
        cursor = execute_query(query, kwargs)
        school = None
        for school_code, school_desc_long in cursor:
            if not cls.is_canvas_school(school_code):
                logger.info(f"SKIPPING school '{school_desc_long}' (not in Canvas)")
                continue
            try:
                school, created = cls.objects.update_or_create(
                    school_code=school_code,
                    defaults={"school_desc_long": school_desc_long},
                )
                school.get_canvas_sub_account()
                action = "ADDED" if created else "UPDATED"
                logger.info(f"{action} {school}")
            except Exception as error:
                logger.error(
                    f"FAILED to update or create school '{school_code}': {error}"
                )
        return school

    @classmethod
    def sync_all(cls):
        logger.info("Syncing Schools...")
        cls.update_or_create(cls.QUERY)

    @classmethod
    def sync_school(cls, school_code: str):
        query = f"{cls.QUERY} WHERE school_code = :school_code"
        kwargs = {"school_code": school_code}
        return cls.update_or_create(query, kwargs)

    @classmethod
    def get_school(cls, school_code: str):
        try:
            school = cls.objects.get(school_code=school_code)
        except Exception:
            school = cls.sync_school(school_code)
        return school


class Subject(Model):
    QUERY = """
            SELECT subject_code, subject_desc_long, school_code
            FROM dwngss.v_subject
            """
    subject_code = CharField(max_length=10, primary_key=True)
    subject_desc_long = CharField(max_length=255, null=True)
    visible = BooleanField(default=True)
    school = ForeignKey(
        School, related_name="subjects", on_delete=CASCADE, blank=True, null=True
    )

    def __str__(self):
        return f"{self.subject_desc_long} ({self.subject_code})"

    @classmethod
    def update_or_create(cls, query: str, kwargs: Optional[dict] = None):
        cursor = execute_query(query, kwargs)
        subject = None
        for subject_code, subject_desc_long, school_code in cursor:
            try:
                school = School.get_school(school_code)
                subject, created = cls.objects.update_or_create(
                    subject_code=subject_code,
                    defaults={"subject_desc_long": subject_desc_long, "school": school},
                )
                action = "ADDED" if created else "UPDATED"
                logger.info(f"{action} {subject}")
            except Exception as error:
                logger.error(
                    f"FAILED to update or create subject '{subject_code}': {error}"
                )
        return subject

    @classmethod
    def sync_all(cls):
        logger.info("Syncing Subjects...")
        cls.update_or_create(cls.QUERY)

    @classmethod
    def sync_subject(cls, subject_code: str):
        query = f"{cls.QUERY} WHERE subject_code = :subject_code"
        kwargs = {"subject_code": subject_code}
        return cls.update_or_create(query, kwargs)

    @classmethod
    def get_subject(cls, subject_code: str):
        try:
            return cls.objects.get(subject_code=subject_code)
        except Exception:
            return cls.sync_subject(subject_code)


class Section(Model):
    RELATED_NAME = "sections"
    ACTIVE_SECTION_STATUS_CODE = "A"
    LECTURE_CODE = "LEC"
    QUERY = """
            SELECT
                section_id || term,
                section_id,
                school,
                subject,
                course_num,
                section_num,
                term,
                title,
                schedule_type,
                section_status,
                primary_course_id,
                primary_section_id,
                primary_subject,
                course_id,
                xlist_family
            FROM dwngss_ps.crse_section section
            WHERE schedule_type NOT IN (
                'MED',
                'DIS',
                'FLD',
                'F01',
                'F02',
                'F03',
                'F04',
                'IND',
                'I01',
                'I02',
                'I03',
                'I04',
                'MST',
                'SRT'
            )
            AND school NOT IN ('W', 'L', 'P')
            """
    QUERY_SECTION_ID = f"{QUERY} AND term = :term AND section_id = :section_id"
    DEFAULT_TERMS = [CURRENT_TERM, NEXT_TERM]
    section_code = CharField(max_length=150, primary_key=True, editable=False)
    section_id = CharField(max_length=150, editable=False)
    school = ForeignKey(School, on_delete=CASCADE, related_name=RELATED_NAME)
    subject = ForeignKey(
        Subject, on_delete=CASCADE, related_name=RELATED_NAME, editable=False
    )
    course_num = CharField(max_length=4, editable=False)
    section_num = CharField(max_length=4, editable=False)
    term = IntegerField(editable=False)
    title = CharField(max_length=250)
    schedule_type = ForeignKey(
        ScheduleType, on_delete=CASCADE, related_name=RELATED_NAME
    )
    instructors = ManyToManyField(User, blank=True, related_name=RELATED_NAME)
    primary_course_id = CharField(max_length=150)
    primary_section = ForeignKey("self", on_delete=CASCADE, blank=True, null=True)
    primary_subject = ForeignKey(Subject, on_delete=CASCADE)
    xlist_family = CharField(max_length=255, blank=True, null=True, editable=False)
    also_offered_as = ManyToManyField("self", blank=True)
    course_sections = ManyToManyField("self", blank=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    def __str__(self):
        return self.section_code

    def sync_instructors(self):
        query = """
                SELECT
                    employee.pennkey,
                    instructor.instructor_first_name,
                    instructor.instructor_last_name,
                    instructor.instructor_penn_id,
                    instructor.instructor_email
                FROM dwngss_ps.crse_sect_instructor instructor
                JOIN employee_general_v employee
                ON instructor.instructor_penn_id = employee.penn_id
                WHERE instructor.section_id = :section_id
                AND term = :term
                """
        kwargs = {"section_id": f"{self.section_id}", "term": self.term}
        cursor = execute_query(query, kwargs)
        instructors = list()
        for pennkey, first_name, last_name, penn_id, email in cursor:
            try:
                user, created = User.objects.update_or_create(
                    username=pennkey,
                    defaults={
                        "first_name": first_name,
                        "last_name": last_name,
                        "penn_id": penn_id,
                        "email": email or "",
                    },
                )
                if user:
                    instructors.append(user)
                action = "ADDED" if created else "UPDATED"
                logger.info(f"{action} {user}")
            except Exception as error:
                logger.error(
                    f"FAILED to update or create instructor '{pennkey}': {error}"
                )
        self.instructors.set(instructors)

    def get_related_sections(self, cursor) -> list:
        related_sections = list()
        for section_id in cursor:
            section_id = next(iter(section_id))
            section = self.get_section(section_id, self.term, sync_related_data=False)
            if section:
                related_sections.append(section)
        return related_sections

    def sync_also_offered_as_sections(self):
        query = """
                SELECT section_id
                FROM dwngss_ps.crse_section
                WHERE xlist_family = :xlist_family
                """
        kwargs = {"xlist_family": self.xlist_family}
        cursor = execute_query(query, kwargs)
        also_offered_as_sections = self.get_related_sections(cursor)
        self.also_offered_as.set(also_offered_as_sections)

    def sync_course_sections(self):
        query = """
                SELECT section_id
                FROM dwngss_ps.crse_section
                WHERE term = :term
                AND course_id = :course_id
                AND section_id != :section_id
                """
        term = self.term
        course_id = f"{self.subject}{self.course_num}"
        kwargs = {"term": term, "course_id": course_id, "section_id": self.section_id}
        cursor = execute_query(query, kwargs)
        course_sections = self.get_related_sections(cursor)
        self.course_sections.set(course_sections)

    @classmethod
    def delete_canceled_section(cls, section_code: str):
        try:
            section = cls.objects.get(section_code=section_code)
        except Exception:
            section = None
        if section:
            section.delete()

    @classmethod
    def update_or_create(
        cls,
        query: str,
        kwargs: Optional[dict] = None,
        sync_related_data=True,
    ):
        cursor = execute_query(query, kwargs)
        section = None
        for (
            section_code,
            section_id,
            school_code,
            subject_code,
            course_num,
            section_num,
            term,
            title,
            sched_type_code,
            section_status,
            primary_course_id,
            primary_section_id,
            primary_subject_code,
            course_id,
            xlist_family,
        ) in cursor:
            if section_status != cls.ACTIVE_SECTION_STATUS_CODE:
                cls.delete_canceled_section(section_code)
                continue
            school = School.get_school(school_code)
            subject = Subject.get_subject(subject_code)
            primary_subject = Subject.get_subject(primary_subject_code) or subject
            schedule_type = ScheduleType.get_schedule_type(sched_type_code)
            if primary_section_id != section_id:
                primary_section = cls.get_section(
                    primary_section_id, term, sync_related_data=False
                )
            else:
                primary_section = None
            try:
                section, created = cls.objects.update_or_create(
                    section_code=section_code,
                    defaults={
                        "section_id": section_id,
                        "school": school,
                        "subject": subject,
                        "course_num": course_num,
                        "section_num": section_num,
                        "term": term,
                        "title": title,
                        "schedule_type": schedule_type,
                        "primary_course_id": primary_course_id or course_id,
                        "primary_section": primary_section,
                        "primary_subject": primary_subject,
                        "xlist_family": xlist_family,
                    },
                )
                if sync_related_data:
                    section.sync_instructors()
                    section.sync_also_offered_as_sections()
                    section.sync_course_sections()
                action = "ADDED" if created else "UPDATED"
                logger.info(f"{action} {section}")
            except Exception as error:
                logger.error(
                    f"FAILED to update or create section '{section_code}': {error}"
                )
        return section

    @classmethod
    def get_terms_query_and_bindings(
        cls, terms: Optional[Union[int, list[int]]]
    ) -> tuple[str, dict]:
        if terms:
            terms = terms if isinstance(terms, list) else [terms]
        else:
            terms = cls.DEFAULT_TERMS
        placeholders = [f":{index + 1}" for index in range(len(terms))]
        placeholders_and_values = zip(placeholders, terms)
        bindings = {placeholder: term for placeholder, term in placeholders_and_values}
        placeholders_string = ",".join(f":{index + 1}" for index in range(len(terms)))
        placeholders_string = f"({placeholders_string})"
        query = f"{cls.QUERY} AND term IN {placeholders_string}"
        return query, bindings

    @classmethod
    def sync_all(cls, terms: Optional[Union[int, list[int]]] = None):
        logger.info(
            f"Syncing sections for terms {terms if terms else cls.DEFAULT_TERMS}..."
        )
        query, bindings = cls.get_terms_query_and_bindings(terms)
        cls.update_or_create(query, bindings)

    @classmethod
    def sync_section(
        cls, section_id: str, term: Optional[int] = None, sync_related_data=True
    ):
        term = term or CURRENT_TERM
        kwargs = {"section_id": section_id, "term": term}
        return cls.update_or_create(cls.QUERY_SECTION_ID, kwargs, sync_related_data)

    def sync(self):
        kwargs = {"section_id": self.section_id, "term": self.term}
        self.update_or_create(self.QUERY_SECTION_ID, kwargs)

    @classmethod
    def get_section(
        cls, section_id: str, term: Optional[int] = None, sync_related_data=True
    ):
        term = term or CURRENT_TERM
        try:
            return cls.objects.get(section_id=section_id, term=term)
        except Exception:
            return cls.sync_section(section_id, term, sync_related_data)

    def get_canvas_course_code(
        self, sis_format=False, include_schedule_type=False
    ) -> str:
        subject = self.subject.subject_code
        divider = "-" if sis_format else " "
        course_and_section = f"{self.course_num}-{self.section_num}"
        canvas_course_code = f"{subject}{divider}{course_and_section} {self.term}"
        if include_schedule_type:
            is_lecture_section = self.schedule_type.sched_type_code == self.LECTURE_CODE
            if not is_lecture_section:
                schedule_type = self.schedule_type.sched_type_code
                canvas_course_code = f"{canvas_course_code} {schedule_type}"
        return canvas_course_code

    def get_canvas_sis_id(self) -> str:
        sis_prefix = "BAN"
        canvas_course_code = self.get_canvas_course_code(sis_format=True)
        return f"{sis_prefix}_{canvas_course_code}"

    def get_canvas_name(
        self, title_override: Optional[str], related_section=False
    ) -> str:
        title = title_override if title_override else self.title
        canvas_course_code = self.get_canvas_course_code(
            include_schedule_type=related_section
        )
        return f"{canvas_course_code} {title}"


class Enrollment(Model):
    class CanvasRole(Enum):
        TA = "TaEnrollment"
        INSTRUCTOR = "TeacherEnrollment"
        DESIGNER = "DesignerEnrollment"
        LIBRARIAN = "DesignerEnrollment"

        @classmethod
        @property
        def choices(cls):
            return [(member.name, member.value) for member in cls]

    LIBRARIAN_ROLE_ID = 1383
    user = ForeignKey(User, on_delete=CASCADE)
    role = CharField(max_length=18, choices=CanvasRole.choices, default=CanvasRole.TA)

    class Meta:
        managed = False
        abstract = True


class SectionEnrollment(Enrollment):
    request = ForeignKey("form.Request", on_delete=CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["user", "role", "request"], name="unique_section_enrollment"
            )
        ]


class AutoAdd(Enrollment):
    school = ForeignKey(School, on_delete=CASCADE)
    subject = ForeignKey(Subject, on_delete=CASCADE)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["school", "subject", "user", "role"], name="unique_auto_add"
            )
        ]


class Request(Model):
    class Status(TextChoices):
        SUBMITTED = "Submitted"
        APPROVED = "Approved"
        LOCKED = "Locked"
        CANCELED = "Canceled"
        IN_PROCESS = "In Process"
        ERROR = "Error"
        COMPLETED = "Completed"

    RELATED_NAME = "requests"
    STORAGE_QUOTA = 2000
    RESERVES_TAB_ID = "context_external_tool_139969"
    RESERVES_TAB_LABEL = "Course Materials @ Penn Libraries"
    section = OneToOneField(Section, on_delete=CASCADE, primary_key=True)
    included_sections = ManyToManyField(Section, blank=True, related_name=RELATED_NAME)
    requester = ForeignKey(User, on_delete=CASCADE, related_name=RELATED_NAME)
    proxy_requester = ForeignKey(
        User, on_delete=CASCADE, blank=True, null=True, related_name="proxy_requests"
    )
    title_override = CharField(max_length=255, null=True, default=None, blank=True)
    copy_from_course = IntegerField(null=True, default=None, blank=True)
    reserves = BooleanField(default=False)
    lps_online = BooleanField(default=False)
    exclude_announcements = BooleanField(default=False)
    additional_enrollments = ManyToManyField(
        SectionEnrollment, blank=True, related_name="section_enrollments"
    )
    additional_instructions = TextField(blank=True, default=None, null=True)
    admin_additional_instructions = TextField(blank=True, default=None, null=True)
    process_notes = TextField(blank=True, default="")
    status = CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    def __str__(self):
        return self.section.section_code

    def set_status(self, status: str):
        self.status = status
        self.save()

    def get_canvas_course_data(self) -> dict:
        section = self.section
        name = section.get_canvas_name(self.title_override)
        sis_course_id = section.get_canvas_sis_id()
        term_id = get_canvas_enrollment_term_id(section.term)
        return {
            "name": name,
            "sis_course_id": sis_course_id,
            "course_code": sis_course_id,
            "term_id": term_id,
            "storage_quota_mb": self.STORAGE_QUOTA,
        }

    def get_canvas_sub_account_id(self) -> int:
        if (
            self.lps_online
            and self.section.school.school_code == School.SAS_SCHOOL_CODE
        ):
            return School.LPS_ONLINE_ACCOUNT_ID
        else:
            return self.section.school.canvas_sub_account_id

    def create_related_sections(self, canvas_course: Course):
        related_sections = self.section.course_sections.all()
        for section in related_sections:
            name = section.get_canvas_name(self.title_override, related_section=True)
            sis_course_id = section.get_canvas_sis_id()
            create_course_section(name, sis_course_id, canvas_course)

    def get_enrollments(self) -> list[SectionEnrollment]:
        section = self.section
        instructors = section.instructors.all()
        instructor_enrollments = [
            SectionEnrollment(
                user=instructor, role=Enrollment.CanvasRole.INSTRUCTOR, request=self
            )
            for instructor in instructors
        ]
        additional_enrollments = list(self.additional_enrollments.all())
        school = section.school
        subject = section.subject
        auto_adds = list(AutoAdd.objects.filter(school=school, subject=subject))
        enrollments = instructor_enrollments + additional_enrollments + auto_adds
        return enrollments

    def enroll_users(self, enrollments: list[SectionEnrollment], canvas_course: Course):
        for enrollment in enrollments:
            canvas_id = enrollment.user.get_canvas_id()
            sections = canvas_course.get_sections()
            name = canvas_course.name
            course_section = next(
                section for section in sections if section.name == name
            )
            enrollment_data = {
                "enrollment_state": "active",
                "course_section_id": course_section.id,
            }
            if enrollment.role == Enrollment.CanvasRole.LIBRARIAN.value:
                enrollment_data["role_id"] = Enrollment.LIBRARIAN_ROLE_ID
            canvas_course.enroll_user(
                canvas_id, enrollment.role, enrollment=enrollment_data
            )

    def set_canvas_course_reserves(self, canvas_course: Course):
        if not self.reserves:
            return
        requester = canvas_course._requester
        reserves_tab = {
            "id": self.RESERVES_TAB_ID,
            "course_id": canvas_course.id,
            "label": self.RESERVES_TAB_LABEL,
        }
        tab = Tab(requester, reserves_tab)
        tab.update(hidden=False)

    def migrate_course(self, canvas_course: Course, sleep_time=5, max_attempts=180):
        source_course_id = self.copy_from_course
        if not source_course_id:
            return
        error_message = f"FAILED to migrate course '{canvas_course}'"
        try:
            exclude_announcements = self.exclude_announcements
            announcements = " WITHOUT announcements" if exclude_announcements else ""
            logger.info(
                "Copying course data from course id"
                f" '{source_course_id}'{announcements}..."
            )
            content_migration = canvas_course.create_content_migration(
                migration_type="course_copy_importer",
                settings={"source_course_id": source_course_id},
            )
            migration_status = content_migration.get_progress().workflow_state
            attempts = 0
            while (
                migration_status in {"queued", "running"} and attempts <= max_attempts
            ):
                logger.info(f"Migration {migration_status}...")
                sleep(sleep_time)
                migration_status = content_migration.get_progress().workflow_state
                attempts += 1
            if not migration_status == "complete":
                logger.error(error_message)
                return
            logger.info("COMPLETED content migration")
            delete_zoom_events(canvas_course)
            if exclude_announcements:
                delete_announcements(canvas_course)
        except Exception as error:
            logger.error(f"{error_message}: {error}")

    def create_canvas_site(self):
        self.set_status(self.Status.IN_PROCESS)
        course = self.get_canvas_course_data()
        sub_account_id = self.get_canvas_sub_account_id()
        created, canvas_course = update_or_create_canvas_course(course, sub_account_id)
        if not canvas_course:
            self.set_status(self.Status.ERROR)
            return
        self.create_related_sections(canvas_course)
        enrollments = self.get_enrollments()
        self.enroll_users(enrollments, canvas_course)
        self.set_canvas_course_reserves(canvas_course)
        self.migrate_course(canvas_course)
        action = "CREATED" if created else "UPDATED"
        name = canvas_course.name
        canvas_id = canvas_course.id
        logger.info(f"{action} Canvas course '{name} ({canvas_id})'")
        self.set_status(self.Status.COMPLETED)

    @classmethod
    def get_approved_requests(cls):
        return cls.objects.filter(status=cls.Status.APPROVED)

    @classmethod
    def create_all_approved_sites(cls):
        approved_requests = cls.get_approved_requests()
        for request in approved_requests:
            request.create_canvas_site()
