from datetime import datetime
from pathlib import Path
from shutil import rmtree

from django.test import TestCase

from config.config import (
    USER_SECTION,
    get_config_email,
    get_config_option,
    get_config_username,
    get_config_username_and_password,
)
from helpers.helpers import get_data_directory, separate_year_and_term


class HelpersTest(TestCase):
    year = str(datetime.now().year)
    term = "A"
    year_and_term = f"{year}{term}"
    data_directory_name = "test_data"
    username = get_config_username()
    password = get_config_option(USER_SECTION, "password")
    email = get_config_option(USER_SECTION, "email")

    def test_get_config_username_and_password(self):
        username, password = get_config_username_and_password()
        self.assertEqual(username, self.username)
        self.assertEqual(password, self.password)

    def test_get_config_email(self):
        email = get_config_email()
        self.assertTrue(email, self.email)

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
