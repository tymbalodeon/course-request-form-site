from django.test import TestCase

from course.models import School


class SchoolTest(TestCase):
    name = "School Name"
    abbreviation = "SCHOOL"

    def setUp(self):
        School.objects.create(name=self.name, abbreviation=self.abbreviation)

    def test_school_str(self):
        """School string should be in the format: Name (ABBREVIATION)"""
        school = School.objects.get(name=self.name)
        self.assertEqual(str(school), f"{self.name} ({self.abbreviation})")
