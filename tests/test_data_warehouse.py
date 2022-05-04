from os import remove
from pathlib import Path

from django.test import TestCase

from config.config import EMAIL, USERNAME
from course.models import User
from course.terms import CURRENT_YEAR_AND_TERM
from data_warehouse.data_warehouse import (
    delete_data_warehouse_canceled_courses, format_title, get_course,
    get_instructor, get_staff_account, get_user_by_pennkey)
from open_data.open_data import OpenData


class DataWarehouseTest(TestCase):
    def test_format_title(self):
        roman_numeral_title = format_title("Roman numeral title iv")
        self.assertEqual(roman_numeral_title, "Roman Numeral Title IV")
        era_title = format_title("Era Title bce")
        self.assertEqual(era_title, "Era Title BCE")
        colon_title = format_title("Colon:Title")
        self.assertEqual(colon_title, "Colon: Title")

    def test_get_staff_account(self):
        user = get_staff_account()
        self.assertFalse(user)
        user = get_staff_account(penn_key=USERNAME)
        self.assertEqual(EMAIL, user["email"].lower().rstrip())
        keys = user.keys()
        for key in ["first_name", "last_name", "email", "penn_id"]:
            self.assertIn(key, keys)
        penn_id = user["penn_id"]
        user = get_staff_account(penn_id=penn_id)
        keys = user.keys()
        self.assertEqual(EMAIL, user["email"].lower().rstrip())
        self.assertIn(USERNAME, user.values())
        for key in ["first_name", "last_name", "email", "penn_key"]:
            self.assertIn(key, keys)

    def test_get_user_by_pennkey(self):
        user = get_user_by_pennkey(USERNAME)
        self.assertIsInstance(user, User)
        user = get_user_by_pennkey("invaliduser")
        self.assertIsNone(user)

    def test_get_course(self):
        open_data_course = next(
            iter(OpenData().get_courses_by_term(CURRENT_YEAR_AND_TERM))
        )
        data_warehouse_course = get_course(open_data_course["section_id"])
        self.assertTrue(len(data_warehouse_course))
        data_warehouse_course = get_course(
            f"{open_data_course['section_id']}{CURRENT_YEAR_AND_TERM}",
            CURRENT_YEAR_AND_TERM,
        )
        self.assertTrue(len(data_warehouse_course))

    def test_get_instructor(self):
        instructor = get_instructor(USERNAME)
        self.assertIsNone(instructor)

    def test_delete_canceled_courses(self):
        log_path = Path.cwd() / "test_canceled_courses.log"
        delete_data_warehouse_canceled_courses(log_path=log_path)
        with open(log_path) as log:
            lines = log.readlines()
            self.assertIsNotNone(lines)
        remove(log_path)
