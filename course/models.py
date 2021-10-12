from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.utils.html import mark_safe
from markdown import markdown


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    penn_id = models.CharField(max_length=10, unique=True)
    canvas_id = models.CharField(max_length=10, unique=True, null=True)


class Activity(models.Model):
    name = models.CharField(max_length=40)
    abbr = models.CharField(max_length=3, unique=True, primary_key=True)

    def __str__(self):
        return self.abbr

    def __repr__(self):
        return self.abbr

    def get_name(self):
        return self.abbr

    class Meta:
        verbose_name = "Activity Type"
        verbose_name_plural = "Activity Types"
        ordering = ("abbr",)


class School(models.Model):
    name = models.CharField(max_length=50, unique=True)
    abbreviation = models.CharField(max_length=10, unique=True, primary_key=True)
    visible = models.BooleanField(default=True)
    opendata_abbr = models.CharField(max_length=2)
    canvas_subaccount = models.IntegerField(null=True)
    form_additional_enrollments = models.BooleanField(
        default=True, verbose_name="Additional Enrollments Form Field"
    )

    def get_subjects(self):
        try:
            subjects = Subject.objects.filter(schools=self)
        except Exception:
            subjects = None

        return subjects

    def save(self, *args, **kwargs):
        subjects = Subject.objects.filter(schools=self.abbreviation)

        for subject in subjects:
            subject.visible = self.visible
            subject.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

    class Meta:
        ordering = ("name",)
        verbose_name = "School // Sub Account"
        verbose_name_plural = "Schools // Sub Accounts"


class Subject(models.Model):
    name = models.CharField(max_length=50)
    abbreviation = models.CharField(max_length=10, unique=True, primary_key=True)
    visible = models.BooleanField(default=True)
    schools = models.ForeignKey(
        School, related_name="subjects", on_delete=models.CASCADE, blank=True, null=True
    )

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

    class Meta:
        ordering = ("name",)
        verbose_name = "Subject // Deptartment "
        verbose_name_plural = "Subjects // Departments"


class CanvasSite(models.Model):
    canvas_id = models.CharField(
        max_length=10, blank=False, default=None, primary_key=True
    )
    request_instance = models.ForeignKey(
        "Request", on_delete=models.SET_NULL, null=True, default=None, blank=True
    )
    owners = models.ManyToManyField(User, related_name="canvas_sites", blank=True)
    added_permissions = models.ManyToManyField(
        User, related_name="added_permissions", blank=True, default=None
    )
    name = models.CharField(max_length=50, blank=False, default=None)
    sis_course_id = models.CharField(max_length=50, blank=True, default=None, null=True)
    workflow_state = models.CharField(max_length=15, blank=False, default=None)

    def get_owners(self):
        return "\n".join([p.username for p in self.owners.all()])

    def get_added_permissions(self):
        return "\n".join([p.username for p in self.added_permissions.all()])

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("canvas_id",)
        verbose_name = "Canvas Site"
        verbose_name_plural = "Canvas Sites"


class CourseManager(models.Manager):
    def has_request(self):
        return super().get_queryset().filter(requested=True)


class Course(models.Model):
    SPRING = "A"
    SUMMER = "B"
    FALL = "C"

    TERM_CHOICES = ((SPRING, "Spring"), (SUMMER, "Summer"), (FALL, "Fall"))

    course_activity = models.ForeignKey(
        Activity, related_name="courses", on_delete=models.CASCADE
    )
    course_code = models.CharField(
        max_length=150, unique=True, primary_key=True, editable=False
    )
    course_name = models.CharField(max_length=250)
    course_number = models.CharField(max_length=4, blank=False)
    course_primary_subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    course_schools = models.ForeignKey(
        School, related_name="courses", on_delete=models.CASCADE
    )
    course_section = models.CharField(max_length=4, blank=False)
    course_subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="courses"
    )
    course_term = models.CharField(
        max_length=1,
        choices=TERM_CHOICES,
    )
    created = models.DateTimeField(auto_now_add=True)
    crosslisted = models.ManyToManyField(
        "self", blank=True, symmetrical=True, default=None
    )
    crosslisted_request = models.ForeignKey(
        "course.Request",
        on_delete=models.SET_NULL,
        related_name="tied_course",
        default=None,
        blank=True,
        null=True,
    )
    instructors = models.ManyToManyField(User, related_name="courses", blank=True)
    multisection_request = models.ForeignKey(
        "course.Request",
        on_delete=models.SET_NULL,
        related_name="additional_sections",
        default=None,
        blank=True,
        null=True,
    )
    owner = models.ForeignKey(
        "auth.User", related_name="created", on_delete=models.CASCADE
    )
    primary_crosslist = models.CharField(max_length=20, default="", blank=True)
    requested = models.BooleanField(default=False)
    requested_override = models.BooleanField(default=False)
    sections = models.ManyToManyField(
        "self", blank=True, symmetrical=True, default=None
    )
    updated = models.DateTimeField(auto_now=True)
    year = models.CharField(max_length=4, blank=False)

    class Meta:
        ordering = (
            "-year",
            "course_code",
        )

    def find_requested(self):
        if self.requested_override is True:
            return True
        else:
            multi_section_request = self.multisection_request
            crosslisted_request = self.crosslisted_request

            try:
                request = Request.objects.get(course_requested=self.course_code)
            except Exception:
                request = None

            exists = request or multi_section_request or crosslisted_request

            return bool(exists)

    def set_requested(self, requested):
        self.requested = requested
        self.save()

    def find_crosslisted(self):
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
            if not (int(self.course_section) >= 300 and int(self.course_section) < 400):
                self.sections.set(self.find_sections())

            self.requested = self.find_requested()
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
                print(f"Request NOT FOUND for {self.course_code} ({error}).")

            return request

    def get_subjects(self):
        return self.course_subject.abbreviation

    def get_schools(self):
        return self.course_schools

    def get_instructors(self):
        return (
            "STAFF"
            if not self.instructors.all().exists()
            else ",\n".join([inst.username for inst in self.instructors.all()])
        )

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

    def srs_format(self):
        return (
            f"{self.course_subject.abbreviation}-"
            f"{self.course_number}-"
            f"{self.course_section}"
            f" {self.year}{self.course_term}"
        )

    def srs_format_primary(self, sis_id=True):
        primary_crosslist = self.primary_crosslist
        year_and_term = f"{self.year}{self.course_term}"

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
            return self.srs_format()

    def __str__(self):
        return "_".join(
            [
                self.course_subject.abbreviation,
                self.course_number,
                self.course_section,
                self.year + self.course_term,
            ]
        )

    def __unicode__(self):
        return "_".join(
            [
                self.course_subject.abbreviation,
                self.course_number,
                self.course_section,
                self.year,
                self.course_term,
            ]
        )

    objects = models.Manager()
    CourseManager = CourseManager()


class Notice(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    notice_heading = models.CharField(max_length=100)
    notice_text = models.TextField(max_length=1000)
    owner = models.ForeignKey(
        "auth.User", related_name="notices", on_delete=models.CASCADE
    )
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        get_latest_by = "updated_date"

    def get_notice_as_markdown(self):
        return mark_safe(markdown(self.notice_text, safe_mode="escape"))

    def __str__(self):

        return (
            "(#"
            + str(self.pk)
            + ") "
            + self.creation_date.strftime("%m-%d-%Y")
            + ': "'
            + self.notice_heading
            + '" by '
            + self.owner.username
        )


class Request(models.Model):
    REQUEST_PROCESS_CHOICES = (
        ("COMPLETED", "Completed"),
        ("IN_PROCESS", "In Process"),
        ("CANCELED", "Canceled"),
        ("APPROVED", "Approved"),
        ("SUBMITTED", "Submitted"),
        ("LOCKED", "Locked"),
    )
    course_requested = models.OneToOneField(
        Course, on_delete=models.CASCADE, primary_key=True
    )
    copy_from_course = models.CharField(
        max_length=100, null=True, default=None, blank=True
    )
    title_override = models.CharField(
        max_length=100, null=True, default=None, blank=True
    )
    lps_online = models.BooleanField(default=False)
    exclude_announcements = models.BooleanField(default=False)
    additional_instructions = models.TextField(blank=True, default=None, null=True)
    admin_additional_instructions = models.TextField(
        blank=True, default=None, null=True
    )
    reserves = models.BooleanField(default=False)
    process_notes = models.TextField(blank=True, default="")
    canvas_instance = models.ForeignKey(
        CanvasSite,
        related_name="canvas",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20, choices=REQUEST_PROCESS_CHOICES, default="SUBMITTED"
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(
        "auth.User", related_name="requests", on_delete=models.CASCADE
    )
    masquerade = models.CharField(max_length=20, null=True)

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


class AdditionalEnrollment(models.Model):
    ENROLLMENT_TYPE = (
        ("TA", "TA"),
        ("INST", "Instructor"),
        ("DES", "Designer"),
        ("LIB", "Librarian"),
        ("OBS", "Observer"),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=4, choices=ENROLLMENT_TYPE, default="TA")
    course_request = models.ForeignKey(
        Request,
        related_name="additional_enrollments",
        on_delete=models.CASCADE,
        default=None,
    )


class AutoAdd(models.Model):
    ROLE_CHOICES = (
        ("TA", "TA"),
        ("INST", "Instructor"),
        ("DES", "Designer"),
        ("LIB", "Librarian"),
        ("OBS", "Observer"),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, blank=False)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, blank=False)
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
    )
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        ordering = ("user__username",)


class UpdateLog(models.Model):
    MANAGER_CHOICES = (
        ("a", "A"),
        ("b", "B"),
        ("c", "C"),
    )
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)
    process = models.CharField(max_length=10, choices=MANAGER_CHOICES)


class PageContent(models.Model):
    location = models.CharField(max_length=100)
    markdown_text = models.TextField(max_length=4000)
    updated_date = models.DateTimeField(auto_now=True)

    def get_page_as_markdown(self):
        return mark_safe(markdown(self.markdown_text, safe_mode="escape"))

    def __str__(self):
        return self.location


class RequestSummary(Request):
    class Meta:
        proxy = True
        verbose_name = "Request Summary"
        verbose_name_plural = "Requests Summary"
