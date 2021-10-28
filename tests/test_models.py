from django.test import TestCase

from course.models import School, Subject


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

    def test_school_str(self):
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

    def test_subject_str(self):
        """Subject string should be in the format: Name (ABBREVIATION)"""
        subject = Subject.objects.get(name=self.name)
        self.assertEqual(str(subject), f"{self.name} ({self.abbreviation})")
