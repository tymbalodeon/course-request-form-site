from datetime import datetime

from django.test import TestCase

from course.models import (
    Activity,
    CanvasSite,
    Course,
    Notice,
    PageContent,
    School,
    Subject,
    User,
)
from helpers.helpers import get_config_username

USERNAME = get_config_username()
SCHOOL_NAME = "School"
SCHOOL_ABBREVIATION = "SCH"
SUBJECT_NAME = "Subject"
SUBJECT_ABBREVIATION = "SUBJ"
ACTIVITY_NAME = "Activity"
ACTIVITY_ABBR = "ACT"
MARKDOWN = "Content"
HTML = "<p>Content</p>"


def create_user():
    return User.objects.create(username=USERNAME)


class ActivityTest(TestCase):
    def setUp(self):
        Activity.objects.create(name=ACTIVITY_NAME, abbr=ACTIVITY_ABBR)

    def test_str(self):
        activity = Activity.objects.get(abbr=ACTIVITY_ABBR)
        self.assertEqual(str(activity), ACTIVITY_ABBR)


class CanvasSiteTest(TestCase):
    canvas_id = 1
    name = "Canvas Site"
    workflow_state = "active"
    owners = ["user_one", "user_two"]
    owners_string = "\n".join(owners)

    def setUp(self):
        owners = [User.objects.create(username=owner) for owner in self.owners]
        canvas_site = CanvasSite.objects.create(
            canvas_id=self.canvas_id,
            name=self.name,
            workflow_state=self.workflow_state,
        )
        canvas_site.owners.set(owners)
        canvas_site.added_permissions.set(owners)

    def test_str(self):
        canvas_site = CanvasSite.objects.get(canvas_id=self.canvas_id)
        self.assertEqual(str(canvas_site), f"{self.name}")

    def test_get_owners(self):
        canvas_site = CanvasSite.objects.get(canvas_id=self.canvas_id)
        self.assertEqual(canvas_site.get_owners(), self.owners_string)

    def test_get_added_permissions(self):
        canvas_site = CanvasSite.objects.get(canvas_id=self.canvas_id)
        self.assertEqual(canvas_site.get_added_permissions(), self.owners_string)


class CourseTest(TestCase):
    course_number = "123"
    course_section = "456"
    year = str(datetime.now().year)
    course_term = "A"
    course_code = (
        f"{SUBJECT_ABBREVIATION}{course_number}{course_section}{year}{course_term}"
    )
    course_str = "_".join(
        [
            SUBJECT_ABBREVIATION,
            course_number,
            course_section,
            f"{year}{course_term}",
        ]
    )

    def setUp(self):
        school = School.objects.create(
            name=SCHOOL_NAME, abbreviation=SCHOOL_ABBREVIATION
        )
        subject = Subject.objects.create(
            name=SUBJECT_NAME, abbreviation=SUBJECT_ABBREVIATION
        )
        activity = Activity.objects.create(name=ACTIVITY_NAME, abbr=ACTIVITY_ABBR)
        Course.objects.create(
            course_code=self.course_code,
            course_subject=subject,
            course_number=self.course_number,
            course_section=self.course_section,
            year=self.year,
            course_term=self.course_term,
            course_activity=activity,
            course_primary_subject=subject,
            course_schools=school,
            owner=create_user(),
        )

    def test_str(self):
        course = Course.objects.get(course_code=self.course_code)
        self.assertEqual(str(course), self.course_str)


class NoticeTest(TestCase):
    notice_heading = "Heading"

    def setUp(self):
        Notice.objects.create(
            notice_heading=self.notice_heading,
            notice_text=MARKDOWN,
            owner=create_user(),
        )

    def test_str(self):
        notice = Notice.objects.get(notice_heading=self.notice_heading)
        self.assertEqual(str(notice), self.notice_heading)

    def test_get_html(self):
        notice = Notice.objects.get(notice_heading=self.notice_heading)
        self.assertEqual(notice.get_html(), HTML)


class PageContentTest(TestCase):
    location = "Location"

    def setUp(self):
        PageContent.objects.create(location=self.location, markdown_text=MARKDOWN)

    def test_str(self):
        page = PageContent.objects.get(location=self.location)
        self.assertEqual(str(page), self.location)

    def test_get_html(self):
        page = PageContent.objects.get(location=self.location)
        self.assertEqual(page.get_html(), HTML)


class SchoolTest(TestCase):
    def setUp(self):
        school = School.objects.create(
            name=SCHOOL_NAME, abbreviation=SCHOOL_ABBREVIATION
        )
        Subject.objects.create(
            name=SCHOOL_NAME,
            abbreviation=SCHOOL_ABBREVIATION,
            schools=school,
        )

    def test_str(self):
        school = School.objects.get(name=SCHOOL_NAME)
        self.assertEqual(str(school), f"{SCHOOL_NAME} ({SCHOOL_ABBREVIATION})")

    def test_get_subjects(self):
        school = School.objects.get(name=SCHOOL_NAME)
        subjects = Subject.objects.filter(schools=school)
        self.assertQuerysetEqual(school.get_subjects(), subjects, transform=lambda x: x)

    def test_save(self):
        def get_school_and_subject():
            school = School.objects.get(name=SCHOOL_NAME)
            return (
                school,
                next(subject for subject in school.get_subjects()),
            )

        school, subject = get_school_and_subject()
        self.assertTrue(school.visible)
        self.assertTrue(subject.visible)
        school.visible = False
        school.save()
        school, subject = get_school_and_subject()
        self.assertFalse(school.visible)
        self.assertFalse(subject.visible)


class SubjectTest(TestCase):
    def setUp(self):
        Subject.objects.create(name=SUBJECT_NAME, abbreviation=SUBJECT_ABBREVIATION)

    def test_str(self):
        subject = Subject.objects.get(name=SUBJECT_NAME)
        self.assertEqual(str(subject), f"{SUBJECT_NAME} ({SUBJECT_ABBREVIATION})")
