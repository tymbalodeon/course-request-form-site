from django.test import TestCase

from course.terms import CURRENT_YEAR_AND_TERM, NEXT_YEAR_AND_TERM
from open_data.open_data import OpenData


class OpenDataTest(TestCase):
    open_data = OpenData()

    def test_get_available_terms(self):
        terms = self.open_data.get_available_terms()
        self.assertEqual(terms, [NEXT_YEAR_AND_TERM, CURRENT_YEAR_AND_TERM])
