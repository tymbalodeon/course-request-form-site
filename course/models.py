import copy
import datetime

import django.core.exceptions
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import models
from django.db.models import Q
from django.db.models.signals import pre_delete
from django.utils.html import mark_safe
from markdown import markdown

# This model is to represent a Course object in the CRF
# the meta-data that is important with this is information that will help the course be
# discoverable in the CRF2. all of these objects with be populated from the data
# provided by the Registrar.

# https://docs.djangoproject.com/en/2.1/ref/models/fields/#choices

# add help text: https://docs.djangoproject.com/en/2.1/ref/models/fields/#help-text


"""
profile was created out of a need to store the users penn_id
https://github.com/jlooney/extended-user-example
"""


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    penn_id = models.CharField(max_length=10, unique=True)
    canvas_id = models.CharField(max_length=10, unique=True, null=True)


# class Instructor(models.auth.User):
"""
        this class expands on the User model
"""


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


#    def __str__(self):
#        return self.username


class School(models.Model):
    """
    mapping of School (i.e. 'Arts & Sciences') to SubjectArea objects
    and their associated subjects
    """

    name = models.CharField(max_length=50, unique=True)
    abbreviation = models.CharField(max_length=10, unique=True, primary_key=True)
    visible = models.BooleanField(default=True)
    opendata_abbr = models.CharField(max_length=2)
    canvas_subaccount = models.IntegerField(null=True)
    form_additional_enrollments = models.BooleanField(
        default=True, verbose_name="Additional Enrollments Form Field"
    )

    def get_subjects(self):
        return self.subjects

    # def set_subjects(self,visibility):

    def save(self, *args, **kwargs):
        """
        some text
        """
        # print("saving school instance")
        # print(self.subjects)
        # print(self.get_subjects())
        # print("args,kwargs", args, kwargs)
        subjects = Subject.objects.filter(schools=self.abbreviation)
        # print("subjects", subjects)

        for subject in subjects:
            subject.visible = self.visible
            subject.save()
        # print("self.pk", self.pk)
        super().save(*args, **kwargs)  # super(Course, self)

    def __str__(self):
        return "%s (%s)" % (self.name, self.abbreviation)

    class Meta:
        ordering = ("name",)
        verbose_name = "School // Sub Account"
        verbose_name_plural = "Schools // Sub Accounts"


class Subject(models.Model):
    """
    mapping of Subject (i.e. 'ANAT' -> Anatomy ) to SubjectArea objects
    requires list_asView but not individual object view
    """

    name = models.CharField(max_length=50)
    abbreviation = models.CharField(max_length=10, unique=True, primary_key=True)
    visible = models.BooleanField(default=True)
    schools = models.ForeignKey(
        School, related_name="subjects", on_delete=models.CASCADE, blank=True, null=True
    )

    def __str__(self):
        return "%s (%s)" % (self.name, self.abbreviation)

    class Meta:
        ordering = ("name",)
        verbose_name = "Subject // Deptartment "
        verbose_name_plural = "Subjects // Departments"


class CanvasSite(models.Model):
    """
    this contains all the relevant info about the canvas site once it has been created
    """

    # url = models.URLField()
    canvas_id = models.CharField(
        max_length=10, blank=False, default=None, primary_key=True
    )
    request_instance = models.ForeignKey(
        "Request", on_delete=models.SET_NULL, null=True, default=None, blank=True
    )  # there doesnt have to be one!
    owners = models.ManyToManyField(
        User, related_name="canvas_sites", blank=True
    )  # should be allowed to be null --> "STAFF"
    added_permissions = models.ManyToManyField(
        User, related_name="added_permissions", blank=True, default=None
    )
    name = models.CharField(
        max_length=50, blank=False, default=None
    )  # CHEM 101 2019C General Chemistry I
    sis_course_id = models.CharField(
        max_length=50, blank=True, default=None, null=True
    )  # SRS_CHEM-101-003 2019C
    workflow_state = models.CharField(max_length=15, blank=False, default=None)
    # sis_section_id = models.CharField(max_length=50,blank=False,default=None)#SRS_CHEM-101-003 2019C
    # section_name = models.CharField(max_length=50,blank=False,default=None)#CHEM 101-003 2019C General Chemistry I

    # i think this should be a school object ...
    # subaccount = models.CharField(max_length=50,blank=False,default=None)
    # term = models.CharField(max_length=5,blank=False,default=None)#2019C
    # name = models.CharField(max_length=50,unique=True)#BMIN 521 2019C AI II: Machine Learning
    """
    sis_course_id = #SRS_BMIN-521-401 2019C
    sis_section_id = #SRS_BMIN-521-401 2019C
    section_name = #BMIN 521-401 2019C AI II: Machine Learning
    subaccount = #Perelman School of Medicine
    term = #2019C
    additional_enrollments = models.  #https://stackoverflow.com/questions/1110153/what-is-the-most-efficient-way-to-store-a-list-in-the-django-models
    """

    #
    # def get_additional_enrollements(self):

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

    # def submitted(self)


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
        if self.requested_override == True:
            return True
        else:
            try:
                exists = self.request
                return True
            except:

                exists = self.multisection_request
                exists_cross = self.crosslisted_request
                if exists or exists_cross:
                    return True
                else:
                    return False
                return False

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
            request = self.request

            for course in cross_courses:
                course.crosslisted_request = request

        except Exception as error:
            print(error)

    def save(self, *args, **kwargs):
        self.course_code = (
            self.course_subject.abbreviation
            + self.course_number
            + self.course_section
            + self.year
            + self.course_term
        )

        if self._state.adding == True:
            super().save(*args, **kwargs)
        else:
            self.sections.set(self.find_sections())
            self.requested = self.find_requested()
            self.update_crosslists()
            super().save(*args, **kwargs)

    def get_request(self):
        try:
            requestinfo = self.request
            return requestinfo
        except Request.DoesNotExist:
            print("Request.DoesNotExist!")

        if self.multisection_request:
            return self.multisection_request
        elif self.crosslisted_request:
            return self.crosslisted_request
        else:
            return None

    def get_subjects(self):
        return self.course_subject.abbreviation
        cross_listed = self.crosslisted
        print(cross_listed)
        if cross_listed == None:
            return self.course_subject.abbreviation
        return ",\n".join([sub.abbreviation for sub in cross_listed])

    def get_schools(self):
        return self.course_schools

    def get_instructors(self):
        if not self.instructors.all().exists():
            return "STAFF"

        return ",\n".join([inst.username for inst in self.instructors.all()])

    def find_sections(self):
        courses = Course.objects.filter(
            Q(course_subject=self.course_subject)
            & Q(course_number=self.course_number)
            & Q(course_term=self.course_term)
            & Q(year=self.year)
        ).exclude(course_code=self.course_code)

        return courses

    def srs_format(self):
        term = self.year + self.course_term

        return "%s-%s-%s %s" % (
            self.course_subject.abbreviation,
            self.course_number,
            self.course_section,
            term,
        )

    def srs_format_primary(self, sis_id=True):
        term = self.year + self.course_term
        pc = self.primary_crosslist

        if pc:
            term = pc[-5:]
            section = pc[:-5][-3:]
            number = pc[:-5][:-3][-3:]
            subj = pc[:-5][:-6]

            if sis_id:
                srs_pc = "%s-%s-%s %s" % (subj, number, section, term)

                return srs_pc
            else:
                srs_pc = "%s %s-%s %s" % (subj, number, section, term)

                return srs_pc
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
    """
    this is a class that handles system wide notifications
    for earilest and latest methods see: https://simpleisbetterthancomplex.com/tips/2016/10/06/django-tip-17-earliest-and-latest.html
    """

    # TODO
    # [ ] fix __str__ and add better admin table view instead
    # [ ] put on request form not just home page

    creation_date = models.DateTimeField(auto_now_add=True)
    notice_heading = models.CharField(max_length=100)
    notice_text = models.TextField(max_length=1000)  # this should be some html ?
    owner = models.ForeignKey(
        "auth.User", related_name="notices", on_delete=models.CASCADE
    )  # this is who edited it
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        get_latest_by = "updated_date"  # allows .latest()

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


# class RequestManager(models.Manager):
#    def submitted(self):


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

    # additional_sections = models.ForeignKey(Course,null=True,default=None,blank=True,related_name='sections')
    copy_from_course = models.CharField(
        max_length=100, null=True, default=None, blank=True
    )
    title_override = models.CharField(
        max_length=100, null=True, default=None, blank=True
    )
    additional_instructions = models.TextField(blank=True, default=None, null=True)
    admin_additional_instructions = models.TextField(
        blank=True, default=None, null=True
    )
    reserves = models.BooleanField(default=False)
    # libguide = models.BooleanField(default=False)
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
    # additional_enrollments = models.ManyToManyField(AdditionalEnrollment,related_name='additional_enrollments',blank=True)

    class Meta:
        ordering = ["-status", "-created"]

    def save(self, *args, **kwargs):
        super(Request, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
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


# class SubjectArea(models.Model):
"""
 mapping of Subject area code and name. boolean value of displayed in CRF2 or not
 requires list_asView but not individual object view
"""


# https://simpleisbetterthancomplex.com/tutorial/2016/07/22/how-to-extend-django-user-model.html
# see section on Extending User Model Using a One-To-One Link
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

    # def __str__(self):
    #    return self.

    class Meta:
        ordering = ("user__username",)


class UpdateLog(models.Model):
    """
    this is how to store Task Process history and status
    """

    MANAGER_CHOICES = (
        ("a", "A"),
        ("b", "B"),
        ("c", "C"),
    )

    # consult this: https://medium.freecodecamp.org/how-to-build-a-progress-bar-for-the-web-with-django-and-celery-12a405637440

    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)
    process = models.CharField(max_length=10, choices=MANAGER_CHOICES)
    # log = this should be a link to the log file associated with the task


# This class is to allow any Courseware Support people to edit some of the pages content without halting the appilication


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


## this is currently not in use!
class Tools(models.Model):
    """
    this is a table of all tools that we can configure in Canvas
    this should only include tools that can be used in any course at penn
    these are tools that would show up in the side navigation menu
    """

    name = models.CharField(max_length=25, blank=False)

    visibility = models.BooleanField(default=True)

    # schools
