from datetime import datetime

from django.test import TestCase

from helpers.helpers import separate_year_and_term


class HelpersTest(TestCase):
    year = str(datetime.now().year)
    term = "A"
    year_and_term = f"{year}{term}"

    def setUp(self):
        pass

    def test_separate_year_and_term(self):
        year, term = separate_year_and_term(self.year_and_term)
        self.assertEqual(year, self.year)
        self.assertEqual(term, self.term)
