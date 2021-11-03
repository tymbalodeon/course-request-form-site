from datetime import datetime
from pathlib import Path
from shutil import rmtree

from django.test import TestCase

from course.utils import get_data_directory, split_year_and_term


class UtilsTest(TestCase):
    year = str(datetime.now().year)
    term = "A"
    year_and_term = f"{year}{term}"
    data_directory = "test_data"
    data_directory_path = Path.cwd() / data_directory

    def test_split_year_and_term(self):
        year, term = split_year_and_term(self.year_and_term)
        self.assertEqual(year, self.year)
        self.assertEqual(term, self.term)

    def test_get_data_directory(self):
        self.assertFalse(self.data_directory_path.exists())
        data_directory = get_data_directory(self.data_directory)
        self.assertTrue(data_directory.exists())
        rmtree(data_directory)
