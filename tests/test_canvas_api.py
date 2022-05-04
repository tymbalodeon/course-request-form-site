from datetime import datetime

from django.test import TestCase

from canvas.api import (MAIN_ACCOUNT_ID, create_canvas_user,
                        get_canvas_account, get_term_id, get_user_by_login_id,
                        get_user_courses)
from config.config import USERNAME


class CanvasAPITest(TestCase):
    username = USERNAME
    none_account_id = -1

    def test_get_canvas_account(self):
        account = get_canvas_account(MAIN_ACCOUNT_ID)
        none_account = get_canvas_account(self.none_account_id)
        self.assertTrue(account)
        self.assertIsNone(none_account)

    def test_create_canvas_user(self):
        user = create_canvas_user(None, None, None, None, test=True)
        self.assertIsNone(user)

    def test_get_user_by_sis(self):
        canvas_user = get_user_by_login_id(self.username)
        self.assertEqual(canvas_user.login_id, self.username)
        none_user = get_user_by_login_id("noneuser")
        self.assertIsNone(none_user)

    def test_get_user_courses(self):
        courses = get_user_courses(self.username)
        none_courses = get_user_courses(None)
        self.assertTrue(courses)
        self.assertFalse(none_courses)

    def test_get_term_id(self):
        year_and_term = f"{datetime.now().year}A"
        term_id = get_term_id(MAIN_ACCOUNT_ID, year_and_term)
        none_term_id = get_term_id(self.none_account_id, year_and_term)
        self.assertTrue(term_id)
        self.assertIsNone(none_term_id)
