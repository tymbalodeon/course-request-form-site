from datetime import datetime
from pathlib import Path
from shutil import rmtree

from django.test import TestCase

from helpers.helpers import get_data_directory, separate_year_and_term


class HelpersTest(TestCase):
    year = str(datetime.now().year)
    term = "A"
    year_and_term = f"{year}{term}"
    data_directory_name = "test_data"

    def test_separate_year_and_term(self):
        year, term = separate_year_and_term(self.year_and_term)
        self.assertEqual(year, self.year)
        self.assertEqual(term, self.term)

    def test_get_data_directory(self):
        data_directory = Path.cwd() / self.data_directory_name
        self.assertFalse(data_directory.exists())
        get_data_directory(data_directory)
        self.assertTrue(data_directory.exists())
        rmtree(data_directory)
