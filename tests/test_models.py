from django.test import TestCase

from config.config import USERNAME
from course.models import (Course, Notice, PageContent, Request, ScheduleType,
                           School, Subject, User)
from course.terms import CURRENT_YEAR, get_current_term

SCHOOL_NAME = "School"
SCHOOL_ABBREVIATION = "SCH"
SUBJECT_NAME = "Subject"
SUBJECT_ABBREVIATION = "SUBJ"
ACTIVITY_NAME = "ScheduleType"
ACTIVITY_ABBR = "ACT"
MARKDOWN = "Content"
HTML = "<p>Content</p>"


def create_user():
    return User.objects.create(username=USERNAME)


class ScheduleTypeTest(TestCase):
    def setUp(self):
        ScheduleType.objects.create(name=ACTIVITY_NAME, abbr=ACTIVITY_ABBR)

    def test_str(self):
        activity = ScheduleType.objects.get(abbr=ACTIVITY_ABBR)
        self.assertEqual(str(activity), ACTIVITY_ABBR)


class CourseTest(TestCase):
    course_number = "123"
    course_section = "456"
    year = CURRENT_YEAR
    course_term = get_current_term()
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
        activity = ScheduleType.objects.create(name=ACTIVITY_NAME, abbr=ACTIVITY_ABBR)
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

    def test_get_requested(self):
        course = Course.objects.get(course_code=self.course_code)
        self.assertFalse(course.get_requested())
        course.requested_override = True
        course.save
        self.assertTrue(course.get_requested())
        course.requested_override = False
        course.save
        Request.objects.create(
            course_requested=course, owner=User.objects.get(username=USERNAME)
        )
        self.assertTrue(course.get_requested())

    def test_get_crosslisted(self):
        course = Course.objects.get(course_code=self.course_code)
        self.assertFalse(course.crosslisted.all().exists())
        Course.objects.create(
            course_code=self.course_code,
            course_subject=Subject.objects.create(
                name=SCHOOL_NAME, abbreviation="TEST"
            ),
            course_number=self.course_number,
            course_section=self.course_section,
            year=self.year,
            course_term=self.course_term,
            course_activity=ScheduleType.objects.get(abbr=ACTIVITY_ABBR),
            course_primary_subject=Subject.objects.get(
                abbreviation=SUBJECT_ABBREVIATION
            ),
            course_schools=School.objects.get(abbreviation=SCHOOL_ABBREVIATION),
            owner=User.objects.get(username=USERNAME),
        )
        course.get_crosslisted()
        course = Course.objects.get(course_code=self.course_code)
        self.assertTrue(course.crosslisted.all().exists())


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
        self.assertQuerysetEqual(school.subjects.all(), subjects, transform=lambda x: x)

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
