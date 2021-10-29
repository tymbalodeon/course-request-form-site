from django.test import TestCase

from course.models import (
    Activity,
    CanvasSite,
    Notice,
    PageContent,
    School,
    Subject,
    User,
)
from helpers.helpers import get_config_username


class ActivityTest(TestCase):
    name = "Activity"
    abbr = "ACT"

    def setUp(self):
        Activity.objects.create(name=self.name, abbr=self.abbr)

    def test_str(self):
        activity = Activity.objects.get(abbr=self.abbr)
        self.assertEqual(str(activity), f"{self.abbr}")


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


class NoticeTest(TestCase):
    notice_heading = "Heading"
    notice_text = "Content"
    owner = User.objects.get(username=get_config_username())

    def setUp(self):
        Notice.objects.create(
            notice_heading=self.notice_heading,
            notice_text=self.notice_text,
            owner=self.owner,
        )

    def test_str(self):
        notice = Notice.objects.get(notice_heading=self.notice_heading)
        self.assertEqual(str(notice), f"{self.notice_heading}")

    def test_get_html(self):
        notice = Notice.objects.get(notice_heading=self.notice_heading)
        self.assertEqual(notice.get_html(), "<p>Content</p>")


class PageContentTest(TestCase):
    location = "Location"
    markdown_text = "Content"

    def setUp(self):
        PageContent.objects.create(
            location=self.location, markdown_text=self.markdown_text
        )

    def test_str(self):
        page = PageContent.objects.get(location=self.location)
        self.assertEqual(str(page), f"{self.location}")

    def test_get_html(self):
        page = PageContent.objects.get(location=self.location)
        self.assertEqual(page.get_html(), "<p>Content</p>")


class SchoolTest(TestCase):
    name = "School Name"
    abbreviation = "SCHOOL"

    def setUp(self):
        school = School.objects.create(name=self.name, abbreviation=self.abbreviation)
        Subject.objects.create(
            name=self.name,
            abbreviation=self.abbreviation,
            schools=school,
        )

    def test_str(self):
        school = School.objects.get(name=self.name)
        self.assertEqual(str(school), f"{self.name} ({self.abbreviation})")

    def test_get_subjects(self):
        school = School.objects.get(name=self.name)
        subjects = Subject.objects.filter(schools=school)
        self.assertQuerysetEqual(school.get_subjects(), subjects, transform=lambda x: x)

    def test_save(self):
        def get_school_and_subject():
            school = School.objects.get(name=self.name)
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
    name = "Subject Name"
    abbreviation = "SUBJECT"

    def setUp(self):
        Subject.objects.create(name=self.name, abbreviation=self.abbreviation)

    def test_str(self):
        subject = Subject.objects.get(name=self.name)
        self.assertEqual(str(subject), f"{self.name} ({self.abbreviation})")
