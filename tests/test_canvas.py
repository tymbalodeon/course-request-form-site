from unittest.mock import patch

from canvasapi.user import User as CanvasUser
from django.test import TestCase

from config.config import TEST_KEY, TEST_URL
from form.canvas import (
    MAIN_ACCOUNT_ID,
    get_all_canvas_accounts,
    get_canvas,
    get_canvas_enrollment_term_id,
    get_canvas_main_account,
    get_canvas_user_by_login_id,
    get_canvas_user_id_by_pennkey,
    update_canvas_course,
)
from form.terms import CURRENT_TERM
from tests.mocks import LOGIN_ID, SUB_ACCOUNTS, MockAccount, MockCanvas

CANVAS_MODULE = "form.canvas"
GET_CANVAS = f"{CANVAS_MODULE}.get_canvas"


class CanvasApiTest(TestCase):
    user_id = 1234567

    def test_get_canvas(self):
        canvas = get_canvas()
        self.assertEqual(canvas._Canvas__requester.original_url, TEST_URL)
        self.assertEqual(canvas._Canvas__requester.access_token, TEST_KEY)

    @patch(GET_CANVAS)
    def test_get_canvas_main_account(self, mock_get_canvas):
        mock_get_canvas.return_value = MockCanvas()
        main_account = get_canvas_main_account()
        self.assertEqual(main_account.id, MAIN_ACCOUNT_ID)

    @patch(f"{CANVAS_MODULE}.get_canvas_main_account")
    def test_get_all_canvas_accounts(self, mock_get_canvas_main_account):
        mock_get_canvas_main_account.return_value = MockAccount(1)
        sub_accounts = get_all_canvas_accounts()
        self.assertEqual(sub_accounts, SUB_ACCOUNTS)

    @patch(GET_CANVAS)
    def test_get_canvas_user_by_login_id(self, mock_get_canvas):
        mock_get_canvas.return_value = MockCanvas()
        user = get_canvas_user_by_login_id(LOGIN_ID)
        self.assertIsInstance(user, CanvasUser)
        self.assertEqual(user.login_id, LOGIN_ID)
        user = get_canvas_user_by_login_id("")
        self.assertIsNone(user)

    @patch(f"{CANVAS_MODULE}.get_canvas_user_by_login_id")
    def test_get_canvas_user_id_by_pennkey(self, mock_get_canvas_user_by_login_id):
        mock_get_canvas_user_by_login_id.return_value = CanvasUser(
            None, {"id": self.user_id, "login_id": LOGIN_ID}
        )
        user_id = get_canvas_user_id_by_pennkey(LOGIN_ID)
        self.assertEqual(user_id, self.user_id)
        mock_get_canvas_user_by_login_id.return_value = None
        user_id = get_canvas_user_id_by_pennkey(LOGIN_ID)
        self.assertIsNone(user_id)

    @patch(GET_CANVAS)
    def test_get_canvas_enrollment_term_id(self, mock_get_canvas):
        mock_get_canvas.return_value = MockCanvas()
        term_id = get_canvas_enrollment_term_id(CURRENT_TERM)
        self.assertTrue(term_id)
        term_id = get_canvas_enrollment_term_id(1000)
        self.assertFalse(term_id)

    @patch(GET_CANVAS)
    def test_update_canvas_course(self, mock_get_canvas):
        canvas = MockCanvas()
        mock_get_canvas.return_value = canvas
        new_name = "New Name"
        new_term_id = 2
        new_storage_quota_mb = 3000
        course = {
            "name": new_name,
            "sis_course_id": f"BAN_SUBJ-1000-200 {CURRENT_TERM}",
            "term_id": new_term_id,
            "storage_quota_mb": new_storage_quota_mb,
        }
        update_canvas_course(course)
        mock_course = next(iter(canvas.courses))
        self.assertEqual(mock_course.name, new_name)
        self.assertEqual(mock_course.term_id, new_term_id)
        self.assertEqual(mock_course.storage_quota_mb, new_storage_quota_mb)
        course = {
            "name": "Failed new name",
            "sis_course_id": "bad value",
            "term_id": 0,
            "storage_quota_mb": 5000,
        }
        update_canvas_course(course)
        self.assertEqual(mock_course.name, new_name)
        self.assertEqual(mock_course.term_id, new_term_id)
        self.assertEqual(mock_course.storage_quota_mb, new_storage_quota_mb)
